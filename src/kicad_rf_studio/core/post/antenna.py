# SPDX-License-Identifier: GPL-3.0-or-later
"""An antenna's results (Stage 3 design 5.5, 5.6): S11's resonance, bandwidth and mismatch at the band's markers, the
far field's efficiencies and gains, and the files of results/, each labelled relative with its stated limits; no loss
budget, radiation being the "loss". matplotlib is imported inside antenna_png only (C-5)."""
import csv
import io
import re
from pathlib import Path

import numpy as np
import skrf as rf

from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.model.parts import Z0
from kicad_rf_studio.core.post.farfield import efficiencies, eta_lines, port_powers, read_far_field

ANTENNA_OUTPUTS = re.compile(r"(layout|chain)\.s\d+p|farfield\.csv|antenna_summary\.(png|csv)")  # matched whole
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


def far_field_of(paths: dict[str, Path], waves: Path) -> dict:
    """A run's far field (design 5.5): each transform file of `paths` (sphere, elevation, azimuth) read back under its
    grid's name; "p_acc" and "p_inc" at the sphere's frequencies from port 1 of the job's `waves` file, u[0] and i[0]
    over the whole record; and "eff", efficiencies' dict. E_RESULTS_WAVES for the first file missing, in that order."""
    for path in (*paths.values(), waves):
        if not path.is_file():
            raise KrsError("E_RESULTS_WAVES", path=str(path))
    far = {grid: read_far_field(path) for grid, path in paths.items()}
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


def draw_antenna(fig, f: np.ndarray, s11: np.ndarray, project: dict, far: dict | None, name: str,
                 label: str | None = None) -> None:
    """antenna_summary.png's plots (design 5.6) on the matplotlib Figure `fig` (antenna_png's, or plan 5's GUI
    canvas), as draw_summary draws v1's: |S11| in dB against GHz with the band [f_lo, f_hi] shaded and lines at
    LEVELS_DB, and S11 on a Smith chart with dots at f_lo, f0 and f_hi; with far_field_of's `far`, η_rad and η_tot in
    % against GHz and the cuts of D in dBi at f0, XY (θ 90°), XZ (φ 0°) and YZ (φ 90°), down to CUT_RANGE_DB below
    their peak. Under I_PLOT_ANTENNA_TITLE with I_ANTENNA_RELATIVE as its second line and `label` (the what-if label,
    D-15, as draw_summary's) as its third when given, and with the rendered ANTENNA_LIMITS, one a line, in the last of
    fig.texts, at the foot."""
    rows, cols = (2, 3) if far else (1, 2)
    ax11, ax_smith = fig.add_subplot(rows, cols, 1), fig.add_subplot(rows, cols, 2)
    band, dots = project["band"], list(_markers(project, f).values())
    ax11.plot(f / 1e9, _db(s11))
    ax11.axvspan(band["f_lo_hz"] / 1e9, band["f_hi_hz"] / 1e9, color="grey", alpha=0.2)
    for level in LEVELS_DB:
        ax11.axhline(level, color="grey", linewidth=0.5)
    ax11.set(xlabel=render("I_PLOT_FREQUENCY"), ylabel="|S11| (dB)")
    rf.plotting.smith(ax=ax_smith, draw_labels=True)
    line, = ax_smith.plot(s11.real, s11.imag)
    ax_smith.plot(s11[dots].real, s11[dots].imag, "o", color=line.get_color())
    if far:
        sphere, el, az = far["sphere"], far["elevation"], far["azimuth"]
        ax_eta, order = fig.add_subplot(rows, cols, 3), np.argsort(sphere.f)
        for key, legend in (("eta_rad", "η_rad"), ("eta_tot", "η_tot")):
            ax_eta.plot(sphere.f[order] / 1e9, 100 * far["eff"][key][order], "o-", label=legend)
        ax_eta.set(xlabel=render("I_PLOT_FREQUENCY"), ylabel="η (%)")
        ax_eta.legend()
        cuts = (("XY", az.phi, az.d[0, 0]), ("XZ", el.theta, el.d[0, :, 0]), ("YZ", el.theta, el.d[0, :, 1]))
        top = 10 * np.log10(max(d.max() for _, _, d in cuts))
        for n, (plane, angle, d) in enumerate(cuts, 4):
            ax = fig.add_subplot(rows, cols, n, projection="polar")
            if plane != "XY":  # θ from the z axis, drawn up
                ax.set_theta_zero_location("N")
                ax.set_theta_direction(-1)
            ax.plot(np.radians(angle), np.maximum(10 * np.log10(d), top - CUT_RANGE_DB))
            ax.set(title=plane, ylim=(top - CUT_RANGE_DB, top))
    fig.suptitle(render("I_PLOT_ANTENNA_TITLE", name=name) + "\n" + render("I_ANTENNA_RELATIVE")
                 + ("\n" + label if label else ""), wrap=True)
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
