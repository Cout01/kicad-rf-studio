# SPDX-License-Identifier: GPL-3.0-or-later
"""An antenna's results (Stage 3 design 5.5, 5.6): S11's resonance, bandwidth and mismatch at the band's markers, the
far field's efficiencies and gains, and the files of results/, each labelled relative with its stated limits; no loss
budget, radiation being the "loss". matplotlib is imported inside antenna_png and compare_png only (C-5)."""
import csv
import io
import re
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import numpy as np
import skrf as rf

from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.model.parts import Z0
from kicad_rf_studio.core.post.farfield import efficiencies, eta_lines, port_powers, read_far_field

ANTENNA_OUTPUTS = re.compile(r"(layout|chain)\.s\d+p|farfield\.csv|antenna_summary\.(png|csv)")  # matched whole
# verify's files for an antenna (Stage 3 design 5.6, 5.7), which ANTENNA_OUTPUTS never matches, so a retune leaves them
ANTENNA_VERIFY_OUTPUTS = re.compile(r"verify\.s1p|verify_(farfield\.csv|summary\.(png|csv))")
COMPARE_OUTPUTS = re.compile(r"compare\.(png|csv)")  # compare's files (Stage 3 design 5.8), matched whole
ANTENNA_LIMITS = ("I_LIMIT_FREE_SPACE", "I_LIMIT_PEC_ETA", "I_LIMIT_SURROUNDINGS", "I_LIMIT_BODIES",
                  "I_LIMIT_PARTS_OFF_CHAIN")  # design 5.6: stated after every antenna result
LEVELS_DB = (-10.0, -6.0)  # the bandwidth's levels: -10 dB, and the -6 dB marker (design 5.6)
FARFIELD_COLUMNS = ("f_hz", "theta_deg", "phi_deg", "e_theta_re", "e_theta_im", "e_phi_re", "e_phi_im", "d_dbi",
                    "gain_dbi", "realized_gain_dbi")
ANTENNA_COLUMNS = ("f_hz", "s11_db", "s11_deg", "zin_re", "zin_im", "mismatch", "p_acc_w", "p_inc_w", "p_rad_w",
                   "eta_rad", "eta_tot", "d_max_dbi", "gain_dbi", "realized_gain_dbi")
CUT_RANGE_DB = 30.0  # the cuts show D down to this far below their peak: a null's -150 dBi would squash the lobes


def zin(s11: np.ndarray) -> np.ndarray:
    """The input impedance in Ω of the reflection `s11` against Z0: Z0·(1 + S11)/(1 − S11)."""
    return Z0 * (1 + s11) / (1 - s11)


def shown_zin(z: complex) -> str:
    """The impedance `z` as the lines show it, as in 48.2 - j3.1."""
    return f"{z.real:.1f} {'+' if z.imag >= 0 else '-'} j{abs(z.imag):.1f}"


def _db(s: np.ndarray) -> np.ndarray:
    """|s| in dB."""
    return 20 * np.log10(np.abs(s))


def resonance(f: np.ndarray, s11: np.ndarray) -> tuple[int, float]:
    """The resonance of `s11` on `f` (Hz) (design 5.6): the index k of the lowest |S11| and the frequency there,
    refined by a parabola through |S11| in dB at k − 1, k and k + 1; f[k] itself at the grid's first or last point.
    band_grid's step is 0.12 % of f0, against plan 3's 0.3 % significance threshold."""
    db = _db(s11)
    k = int(np.argmin(db))
    if k in (0, len(f) - 1):
        return k, float(f[k])
    a, b, _ = np.polyfit(f[k - 1:k + 2] - f[k], db[k - 1:k + 2], 2)
    return k, float(f[k] - b / (2 * a))


def dip_resonance(f: np.ndarray, s11: np.ndarray) -> float | None:
    """The refined resonance (resonance) of `s11` on `f` when its lowest |S11| marks a dip: at or below the −6 dB
    marker (LEVELS_DB) at a point inside the grid; else None, as the argmin of a shallow minimum, or one at the grid's
    edge, moves with the model's noise (Stage 3 plan 3)."""
    # ponytail: P3-D (docs/validation/2026-11-01-p3-d.md): the repeat and the whole shift move a dip's depth by under
    # 3e-6 dB, the antenna moved by ±0.3 mm by 1.25 dB (its position, not noise); every P3-D dip lay 5.5 dB or more
    # under −6 dB, P3-E's pour 0.99 dB; still a depth screen, which a broad −7 dB minimum passes
    k, f_res = resonance(f, s11)
    return f_res if 0 < k < len(f) - 1 and _db(s11[k]) <= LEVELS_DB[1] else None


def compare_s11(a: np.ndarray, b: np.ndarray, f: np.ndarray, k0: int) -> dict:
    """How the retune's S11 `b` differs from verify's `a`, each (F,) on f (Stage 3 design 5.7), as checks.compare does
    for v1: |ΔS11| at the grid index k0 (f0), the largest |ΔS11| over f (up to f2), each one's dip_resonance and, only
    when both have one, the shift (f_a − f_b)/f_b; plain floats, None for a resonance or a shift there is not."""
    fa, fb = dip_resonance(f, a), dip_resonance(f, b)
    return {"ds11_f0": float(abs(a[k0] - b[k0])), "ds11_max": float(np.abs(a - b).max()), "f_res_hz": fa,
            "f_res_retune_hz": fb, "shift": None if fa is None or fb is None else (fa - fb) / fb}


def bandwidth(f: np.ndarray, s11: np.ndarray, k: int, level_db: float) -> tuple[float | None, float | None] | None:
    """The crossings (f_lo, f_hi) in Hz of `level_db` by |S11| on either side of the index `k` of `f` (design 5.6),
    each interpolated linearly in dB between its two grid points; a side with no crossing is None, |S11| staying
    below the level to the grid's end. None when |S11| at k is above the level."""
    db = _db(s11)
    if db[k] > level_db:
        return None
    above = np.flatnonzero(db > level_db)
    lo, hi = above[above < k], above[above > k]

    def cross(a: int, b: int) -> float:  # where the line from point a, above the level, to point b meets it
        return float(f[a] + (level_db - db[a]) * (f[b] - f[a]) / (db[b] - db[a]))

    return cross(lo[-1], lo[-1] + 1) if lo.size else None, cross(hi[0], hi[0] - 1) if hi.size else None


def _markers(project: dict, f: np.ndarray) -> dict[str, int]:
    """The indices in `f` of the band's markers f_lo, f0 and f_hi: their nearest points, themselves on band_grid."""
    band = project["band"]
    return {name: int(np.abs(f - v).argmin())
            for name, v in (("f_lo", band["f_lo_hz"]), ("f0", project["f0_hz"]), ("f_hi", band["f_hi_hz"]))}


def s11_lines(project: dict, f: np.ndarray, s11: np.ndarray) -> list[tuple[str, dict]]:
    """The lines of `s11` (F,) on `f` (Hz) (design 5.6), Zin as seen at the chain's start pad: I_ANTENNA_RELATIVE;
    the resonance, then W_RESONANCE_EDGE when it is the grid's first or last point; |S11|, Zin and the mismatch
    efficiency 1 − |S11|² at f_lo, f0 and f_hi; then at each of LEVELS_DB the bandwidth, W_BANDWIDTH_EDGE with the
    grid's end for a side that never crosses, or I_ANTENNA_NO_BANDWIDTH."""
    port, db, z = project["chain"]["start"], _db(s11), zin(s11)
    k, f_res = resonance(f, s11)
    lines = [("I_ANTENNA_RELATIVE", {}),
             ("I_ANTENNA_RESONANCE", {"f_mhz": f"{f_res / 1e6:.1f}", "s11_db": f"{db[k]:.1f}", "zin": shown_zin(z[k]),
                                      "port": port})]
    if k in (0, len(f) - 1):
        lines.append(("W_RESONANCE_EDGE", {"f_mhz": f"{f[k] / 1e6:.1f}"}))
    lines += [("I_ANTENNA_POINT", {"marker": marker, "f_mhz": f"{f[n] / 1e6:.1f}", "s11_db": f"{db[n]:.1f}",
                                   "zin": shown_zin(z[n]), "port": port,
                                   "mismatch_pct": f"{100 * (1 - abs(s11[n]) ** 2):.1f}"})
              for marker, n in _markers(project, f).items()]
    for level in LEVELS_DB:
        crossings, level_db = bandwidth(f, s11, k, level), f"{level:g}"
        if crossings is None:
            lines.append(("I_ANTENNA_NO_BANDWIDTH", {"level_db": level_db}))
            continue
        lo, hi = crossings
        shown = {"level_db": level_db, "f_lo_mhz": f"{(f[0] if lo is None else lo) / 1e6:.1f}",
                 "f_hi_mhz": f"{(f[-1] if hi is None else hi) / 1e6:.1f}"}
        if lo is None or hi is None:
            lines.append(("W_BANDWIDTH_EDGE", shown))
        else:
            lines.append(("I_ANTENNA_BANDWIDTH", {**shown, "bw_mhz": f"{(hi - lo) / 1e6:.1f}"}))
    return lines


def far_field_of(paths: dict[str, Path], waves: Path, f_hz: Sequence[float] = ()) -> dict:
    """A run's far field (design 5.5): each transform file of `paths` (sphere, elevation, azimuth) read back under its
    grid's name; "p_acc" and "p_inc" at the sphere's frequencies from port 1 of the job's `waves` file, u[0] and i[0]
    over the whole record; and "eff", efficiencies' dict. `f_hz` (project.json's far_field.f_hz): openEMS stores the
    recorded frequencies as float32, up to about 128 Hz off at 2.4 GHz, so each is snapped to the nearest of them
    within a relative 1e-6 and keeps its recorded value otherwise; with none, none is snapped. E_RESULTS_WAVES for the
    first file missing, in that order."""
    for path in (*paths.values(), waves):
        if not path.is_file():
            raise KrsError("E_RESULTS_WAVES", path=str(path))
    far = {grid: read_far_field(path) for grid, path in paths.items()}
    exact = np.asarray(f_hz, dtype=float)
    if exact.size:
        # ponytail: a frequency within 1e-6 of none of f_hz keeps openEMS's float32 value; nothing records another today
        for grid, g in far.items():
            nearest = exact[np.abs(g.f[:, None] - exact).argmin(axis=1)]
            far[grid] = replace(g, f=np.where(np.isclose(nearest, g.f, rtol=1e-6, atol=0), nearest, g.f))
    with np.load(waves) as w:
        p_acc, p_inc = port_powers(w["t_u"], w["u"][0], w["t_i"], w["i"][0], far["sphere"].f)
    return {**far, "p_acc": p_acc, "p_inc": p_inc, "eff": efficiencies(far["sphere"], p_acc, p_inc)}


def far_field_lines(far: dict) -> list[tuple[str, dict]]:
    """The lines of far_field_of's `far` (design 5.5, 5.6): one I_ANTENNA_FAR_FIELD per recorded frequency, ascending,
    with η_rad and η_tot in % and D_max, the gain and the realized gain in dBi; then eta_lines' W_ETA_RAD."""
    f, d_max, eff = far["sphere"].f, far["sphere"].d_max, far["eff"]
    lines = [("I_ANTENNA_FAR_FIELD", {"f_mhz": f"{f[n] / 1e6:.1f}", "eta_rad_pct": f"{100 * eff['eta_rad'][n]:.1f}",
                                      "eta_tot_pct": f"{100 * eff['eta_tot'][n]:.1f}",
                                      "d_dbi": f"{10 * np.log10(d_max[n]):.2f}",
                                      "gain_dbi": f"{10 * np.log10(eff['gain'][n]):.2f}",
                                      "realized_dbi": f"{10 * np.log10(eff['realized_gain'][n]):.2f}"})
             for n in np.argsort(f)]
    return lines + eta_lines(f, eff["eta_rad"])


def eta_what_if_lines(far: dict, p: np.ndarray) -> list[tuple[str, dict]]:
    """The instant retune's total efficiency where the project has a current verify with a far field (Stage 3 design
    5.7): one I_ANTENNA_ETA_WHAT_IF per frequency of far_field_of's `far`, ascending, η_tot = η_rad·p, with η_rad from
    `far` and `p` (in far's order) the share of the incident power this retune's network passes to the board,
    loss_budget's P_layout: the design's 1 − |S11|² for a lossless network, less the parts' own loss otherwise;
    labelled what-if, as a lossless network that does not radiate leaves η_rad and the pattern as they are."""
    f, eta_rad = far["sphere"].f, far["eff"]["eta_rad"]
    return [("I_ANTENNA_ETA_WHAT_IF", {"f_mhz": f"{f[n] / 1e6:.1f}", "eta_tot_pct": f"{100 * eta_rad[n] * p[n]:.1f}",
                                       "eta_rad_pct": f"{100 * eta_rad[n]:.1f}", "delivered_pct": f"{100 * p[n]:.1f}"})
            for n in np.argsort(f)]


# design 5.8: a delta is resolved above 0.3 % of f0 for a frequency and 0.2 dB for an efficiency or a gain
# gate P3-D (docs/validation/2026-11-01-p3-d.md): three times the model's measured noise floor (the same verify twice,
# the board shifted by one fine cell and the even parts of the antenna moved by ± one fine cell: 0.029 % and
# 0.029 dB) lies under the design's 0.3 % and 0.2 dB, which therefore stand
SHIFT_LIMIT, DB_LIMIT = 0.003, 0.2
DELTA_COLUMNS = ("quantity", "marker", "f_hz", "base", "variant", "unit", "delta", "delta_unit", "threshold",
                 "resolved")


def deltas(project: dict, f: np.ndarray, base: tuple[np.ndarray, dict | None],
           variant: tuple[np.ndarray, dict | None]) -> list[dict]:
    """The deltas of `variant` against `base` (Stage 3 design 5.8), each (S11 (F,) on f, far_field_of's dict or None),
    as rows of DELTA_COLUMNS (None for no value): `unit` is base's and variant's, `delta_unit` the delta's and the
    threshold's."""
    def row(quantity, marker, f_hz, b, v, unit, delta, delta_unit, threshold):  # numbers as Python floats
        f_hz, b, v, delta = (None if x is None else float(x) for x in (f_hz, b, v, delta))
        return dict(zip(DELTA_COLUMNS, (quantity, marker, f_hz, b, v, unit, delta, delta_unit, threshold,
                                        None if delta is None else abs(delta) > threshold)))

    def res_mhz(s11):  # dip_resonance in MHz, None without a dip
        f_res = dip_resonance(f, s11)
        return None if f_res is None else f_res / 1e6

    def bw_mhz(s11):  # the -10 dB bandwidth at the lowest |S11| in MHz, None unless bounded on both sides
        crossings = bandwidth(f, s11, resonance(f, s11)[0], LEVELS_DB[0])
        return None if crossings is None or None in crossings else (crossings[1] - crossings[0]) / 1e6

    # ponytail: the bandwidth's change is judged by the frequency threshold, as gate P3-D left it: three times its
    # noise, 0.037 % of f0, lies under 0.3 % (docs/validation/2026-11-01-p3-d.md)
    limit, rows = SHIFT_LIMIT * project["f0_hz"] / 1e6, []
    for quantity, value in (("resonance", res_mhz), ("bandwidth_10db", bw_mhz)):
        b, v = value(base[0]), value(variant[0])
        rows.append(row(quantity, "", None, b, v, "MHz", None if b is None or v is None else v - b, "MHz", limit))
    far_b, far_v = base[1], variant[1]
    if far_b is None or far_v is None:
        return rows
    at_b, at_v = _markers(project, far_b["sphere"].f), _markers(project, far_v["sphere"].f)  # nearest recorded
    for marker, n in at_b.items():
        b, v = far_b["eff"]["eta_tot"][n], far_v["eff"]["eta_tot"][at_v[marker]]
        rows.append(row("eta_tot", marker, far_b["sphere"].f[n], 100 * b, 100 * v, "%", 10 * np.log10(v / b), "dB",
                        DB_LIMIT))
    b, v = (10 * np.log10(far["eff"]["gain"][at["f0"]]) for far, at in ((far_b, at_b), (far_v, at_v)))
    rows.append(row("peak_gain", "f0", far_b["sphere"].f[at_b["f0"]], b, v, "dBi", v - b, "dB", DB_LIMIT))
    return rows


def delta_lines(project: dict, rows: list[dict]) -> list[tuple[str, dict]]:
    """compare's lines of `deltas`' rows (Stage 3 design 5.8), each with its verdict, T_RESOLVED or T_NOT_RESOLVED:
    the resonance's shift in MHz and in % of f0, or I_RESONANCE_NOT_COMPARED; the -10 dB bandwidth's change, or
    I_COMPARE_NO_BANDWIDTH; η_tot at each marker and the peak gain at f0, or I_COMPARE_NO_FAR_FIELD in their place;
    then I_COMPARE_THRESHOLDS."""
    def line(r):
        verdict = "T_RESOLVED" if r["resolved"] else "T_NOT_RESOLVED"
        if r["quantity"] == "resonance":
            return ("I_RESONANCE_NOT_COMPARED", {}) if r["delta"] is None else (
                "I_COMPARE_RESONANCE", {"base_mhz": f"{r['base']:.1f}", "variant_mhz": f"{r['variant']:.1f}",
                                        "shift_mhz": f"{r['delta']:+.1f}",
                                        "shift_pct": f"{100 * r['delta'] / (project['f0_hz'] / 1e6):+.2f}",
                                        "verdict": verdict})
        if r["quantity"] == "bandwidth_10db":
            return ("I_COMPARE_NO_BANDWIDTH", {}) if r["delta"] is None else (
                "I_COMPARE_BANDWIDTH", {"base_mhz": f"{r['base']:.1f}", "variant_mhz": f"{r['variant']:.1f}",
                                        "change_mhz": f"{r['delta']:+.1f}", "verdict": verdict})
        f_mhz, delta_db = f"{r['f_hz'] / 1e6:.1f}", f"{r['delta']:+.2f}"
        if r["quantity"] == "eta_tot":
            return "I_COMPARE_ETA", {"marker": r["marker"], "f_mhz": f_mhz, "base_pct": f"{r['base']:.1f}",
                                     "variant_pct": f"{r['variant']:.1f}", "delta_db": delta_db, "verdict": verdict}
        return "I_COMPARE_GAIN", {"f_mhz": f_mhz, "base_dbi": f"{r['base']:.2f}", "variant_dbi": f"{r['variant']:.2f}",
                                  "delta_db": delta_db, "verdict": verdict}

    lines = [line(r) for r in rows]
    if not any(r["quantity"] == "peak_gain" for r in rows):  # deltas: no far-field rows unless both have a far field
        lines.append(("I_COMPARE_NO_FAR_FIELD", {}))
    return lines + [("I_COMPARE_THRESHOLDS", {"shift_pct": f"{100 * SHIFT_LIMIT:g}", "db": f"{DB_LIMIT:g}"})]


def deltas_csv(rows: list[dict]) -> bytes:
    """compare.csv: DELTA_COLUMNS, then the rows, None as empty, as plan 2's CSVs are written."""
    out = io.StringIO()
    writer = csv.DictWriter(out, DELTA_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def _csv(columns: tuple[str, ...], rows: np.ndarray) -> bytes:
    """A CSV file of `columns`, then the `rows` (n, len(columns)) by ascending frequency, their first column (a stable
    sort): comma-separated, "\\n" line ends, numbers as Python's repr."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows[np.argsort(rows[:, 0], kind="stable")].tolist())
    return out.getvalue().encode("utf-8")


def farfield_csv(far: dict) -> bytes:
    """farfield.csv (design 5.6) of far_field_of's `far`: FARFIELD_COLUMNS, then one row per frequency, θ and φ of
    the sphere: E_θ and E_φ in V/m at r = 1 m, and D, D·η_rad (the gain) and D·η_tot (the realized gain) in dBi."""
    s, eff = far["sphere"], far["eff"]
    f, theta, phi = np.meshgrid(s.f, s.theta, s.phi, indexing="ij")
    eta_rad, eta_tot = eff["eta_rad"][:, None, None], eff["eta_tot"][:, None, None]
    columns = (f, theta, phi, s.e_theta.real, s.e_theta.imag, s.e_phi.real, s.e_phi.imag, 10 * np.log10(s.d),
               10 * np.log10(s.d * eta_rad), 10 * np.log10(s.d * eta_tot))
    return _csv(FARFIELD_COLUMNS, np.column_stack([c.ravel() for c in columns]))


def antenna_csv(far: dict, s11: np.ndarray) -> bytes:
    """antenna_summary.csv (design 5.6) of far_field_of's `far` and `s11`, S11 at far["sphere"].f in its order:
    ANTENNA_COLUMNS, then one row per far-field frequency: S11 in dB and degrees, Zin, the mismatch efficiency
    1 − |S11|², the port's P_acc and P_inc and P_rad in W, η_rad, η_tot, and D_max, the gain and the realized gain in
    dBi."""
    s, eff, z = far["sphere"], far["eff"], zin(s11)
    columns = (s.f, _db(s11), np.angle(s11, deg=True), z.real, z.imag, 1 - np.abs(s11) ** 2, far["p_acc"],
               far["p_inc"], s.p_rad, eff["eta_rad"], eff["eta_tot"], 10 * np.log10(s.d_max),
               10 * np.log10(eff["gain"]), 10 * np.log10(eff["realized_gain"]))
    return _csv(ANTENNA_COLUMNS, np.column_stack(columns))


def _panels(fig, f: np.ndarray, curves: list[tuple[str, np.ndarray, dict | None]], project: dict,
            one_row: bool = False) -> tuple:
    """The plots of draw_antenna and draw_compare on the matplotlib Figure `fig`, each curve (name, S11 (F,) on `f`,
    far_field_of's dict or None) drawn on every panel (Stage 3 design 5.6, 5.8): |S11| in dB against GHz, each curve
    labelled with its name, with the band [f_lo, f_hi] shaded and lines at LEVELS_DB; S11 on a Smith chart with dots
    at f_lo, f0 and f_hi; and only when every curve has a far field, η_rad and η_tot in % against GHz and the cuts of
    D in dBi at f0, XY (θ 90°), XZ (φ 0°) and YZ (φ 90°), on one radial range down to CUT_RANGE_DB below the highest
    peak. The η panel has a legend; with two curves every panel has one, and the η lines' labels start with the
    curve's name; with `one_row`, the far field's panels beside S11 and the Smith chart in one row. Returns the S11
    axes and the Smith chart's."""
    far_fields, two = all(far for _, _, far in curves), len(curves) > 1
    rows, cols = ((1, 6) if one_row else (2, 3)) if far_fields else (1, 2)
    ax11, ax_smith = fig.add_subplot(rows, cols, 1), fig.add_subplot(rows, cols, 2)
    band, dots = project["band"], list(_markers(project, f).values())
    rf.plotting.smith(ax=ax_smith, draw_labels=True)
    for name, s11, _ in curves:
        ax11.plot(f / 1e9, _db(s11), label=name)
        line, = ax_smith.plot(s11.real, s11.imag, label=name)
        ax_smith.plot(s11[dots].real, s11[dots].imag, "o", color=line.get_color())
    ax11.axvspan(band["f_lo_hz"] / 1e9, band["f_hi_hz"] / 1e9, color="grey", alpha=0.2)
    for level in LEVELS_DB:
        ax11.axhline(level, color="grey", linewidth=0.5)
    ax11.set(xlabel=render("I_PLOT_FREQUENCY"), ylabel="|S11| (dB)")
    legends = [ax11, ax_smith] if two else []
    if far_fields:
        ax_eta = fig.add_subplot(rows, cols, 3)
        for name, _, far in curves:
            sphere, order = far["sphere"], np.argsort(far["sphere"].f)
            for key, legend in (("eta_rad", "η_rad"), ("eta_tot", "η_tot")):
                ax_eta.plot(sphere.f[order] / 1e9, 100 * far["eff"][key][order], "o-",
                            label=f"{name} {legend}" if two else legend)
        ax_eta.set(xlabel=render("I_PLOT_FREQUENCY"), ylabel="η (%)")
        legends.append(ax_eta)
        cuts = [{"XY": (far["azimuth"].phi, far["azimuth"].d[0, 0]),  # each curve's (angles in °, D) by plane
                 "XZ": (far["elevation"].theta, far["elevation"].d[0, :, 0]),
                 "YZ": (far["elevation"].theta, far["elevation"].d[0, :, 1])} for _, _, far in curves]
        top = 10 * np.log10(max(d.max() for cut in cuts for _, d in cut.values()))
        for n, plane in enumerate(("XY", "XZ", "YZ"), 4):
            ax = fig.add_subplot(rows, cols, n, projection="polar")
            if plane != "XY":  # θ from the z axis, drawn up
                ax.set_theta_zero_location("N")
                ax.set_theta_direction(-1)
            for (name, _, _), cut in zip(curves, cuts):
                angle, d = cut[plane]
                ax.plot(np.radians(angle), np.maximum(10 * np.log10(d), top - CUT_RANGE_DB), label=name)
            ax.set(title=plane, ylim=(top - CUT_RANGE_DB, top))
            legends += [ax] if two else []
    for ax in legends:
        ax.legend()
    return ax11, ax_smith


def draw_antenna(fig, f: np.ndarray, s11: np.ndarray, project: dict, far: dict | None, name: str,
                 label: str | None = None, gui: bool = False) -> tuple:
    """antenna_summary.png's plots (design 5.6) on the matplotlib Figure `fig` (antenna_png's, or plan 5's GUI
    canvas), as draw_summary draws v1's: _panels of the one curve `s11` named `name`, with far_field_of's `far` when
    given. Under I_PLOT_ANTENNA_TITLE with I_ANTENNA_RELATIVE as its second line and `label` (the what-if label, D-15,
    as draw_summary's) as its third when given, and with the rendered ANTENNA_LIMITS, one a line, in the last of
    fig.texts, at the foot. Returns the S11 and Smith axes, which retrace_antenna moves. With `gui` (plan 5's Results
    canvas) the far field's panels stand in one row and the limits are left to the window's lines, which end with
    them: at 1200 × 800 the 2 × 3 grid under its title and five-line foot collapses (probed: 28 px axes in English,
    none in pt-BR); antenna_png never passes it, so its bytes stay."""
    axes = _panels(fig, f, [(name, s11, far)], project, one_row=gui)
    fig.suptitle(render("I_PLOT_ANTENNA_TITLE", name=name) + "\n" + render("I_ANTENNA_RELATIVE")
                 + ("\n" + label if label else ""), wrap=True)
    if not gui:
        fig.supxlabel("\n".join(render(code) for code in ANTENNA_LIMITS), x=0.01, ha="left", fontsize="small",
                      wrap=True)
    return axes


def retrace_antenna(axes: tuple, f: np.ndarray, s11: np.ndarray, project: dict) -> list:
    """Moves the curve that draw_antenna drew on `axes` (its return) to `s11` (F,) on `f`, as retrace_summary moves
    v1's (the GUI's instant retune, Stage 3 design 5.10): |S11| in dB, the S11 axes' first line; the Smith locus and
    its dots at f_lo, f0 and f_hi, the chart's last two lines. Returns those Line2D."""
    ax11, ax_smith = axes
    dots = list(_markers(project, f).values())
    lines = [ax11.lines[0], ax_smith.lines[-2], ax_smith.lines[-1]]  # the band's level lines come after the curve
    for line, xy in zip(lines, ((f / 1e9, _db(s11)), (s11.real, s11.imag), (s11[dots].real, s11[dots].imag))):
        line.set_data(*xy)  # no draw, no rescale
    return lines


def draw_compare(fig, f: np.ndarray, curves: list[tuple[str, np.ndarray, dict | None]], project: dict) -> None:
    """compare.png's overlays (Stage 3 design 5.8) on the Figure `fig`: _panels of both curves, under
    I_PLOT_COMPARE_TITLE {base, variant} (the curves' names) with I_ANTENNA_RELATIVE as its second line, and the
    rendered ANTENNA_LIMITS at the foot, as draw_antenna."""
    _panels(fig, f, curves, project)
    (base, _, _), (variant, _, _) = curves
    fig.suptitle(render("I_PLOT_COMPARE_TITLE", base=base, variant=variant) + "\n" + render("I_ANTENNA_RELATIVE"),
                 wrap=True)
    fig.supxlabel("\n".join(render(code) for code in ANTENNA_LIMITS), x=0.01, ha="left", fontsize="small", wrap=True)


def antenna_png(f: np.ndarray, s11: np.ndarray, project: dict, far: dict | None, name: str,
                label: str | None = None) -> bytes:
    """antenna_summary.png (design 5.6): draw_antenna on a Figure drawn by Agg, never a pyplot figure, as PNG at 100
    dpi, as summary_png builds v1's, `label` (the what-if label) passed through."""
    from matplotlib.figure import Figure  # here only: no other code of the core loads matplotlib (C-5)

    fig = Figure(figsize=(15, 10.5) if far else (15, 6), layout="constrained")
    draw_antenna(fig, f, s11, project, far, name, label)
    out = io.BytesIO()
    fig.savefig(out, format="png", dpi=100)
    return out.getvalue()


def compare_png(f: np.ndarray, curves: list[tuple[str, np.ndarray, dict | None]], project: dict) -> bytes:
    """compare.png (Stage 3 design 5.8): draw_compare on a Figure drawn by Agg, never a pyplot figure, as PNG at 100
    dpi, sized as antenna_png sizes it: taller when the far field's panels are drawn, which takes both far fields."""
    from matplotlib.figure import Figure  # here only: no other code of the core loads matplotlib (C-5)

    fig = Figure(figsize=(15, 10.5) if all(far for _, _, far in curves) else (15, 6), layout="constrained")
    draw_compare(fig, f, curves, project)
    out = io.BytesIO()
    fig.savefig(out, format="png", dpi=100)
    return out.getvalue()
