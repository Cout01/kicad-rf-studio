# SPDX-License-Identifier: GPL-3.0-or-later
"""The files of results/ (spec 7.5, C-27..C-32): the Touchstone files with their port map and verify's grid lines,
summary.csv and summary.png; the marker lines and the stated limits; and the writer that replaces only its own
files."""
import contextlib
import csv
import io
import os
import re
from pathlib import Path

import numpy as np
import skrf as rf

from kicad_rf_studio.core.messages import KrsError, reason, render
from kicad_rf_studio.core.model.parts import Z0
from kicad_rf_studio.core.post.checks import recip_err, sigma_max
from kicad_rf_studio.core.post.waves import Layout
from kicad_rf_studio.core.project import parts, shown_reference

OUTPUTS = re.compile(r"(layout|chain)\.s\d+p|summary\.(png|csv)")  # the files of run and retune, matched whole
VERIFY_OUTPUT = re.compile(r"verify\.s\d+p")  # verify's file
COLUMNS = ("f_hz", "marker", "a_db", "s11_db", "s11_deg", "s21_db", "s21_deg", "ideal_s11_db", "ideal_s11_deg",
           "ideal_s21_db", "ideal_s21_deg", "sigma_max", "recip_err", "loss", "loss_expected")  # C-29
LIMITS = ("I_LIMIT_MAGNETIC", "I_LIMIT_LID", "I_LIMIT_S2P_PLANE", "I_LIMIT_PEC", "I_LIMIT_WALLS", "I_LIMIT_ACCURACY",
          "I_LIMIT_50_OHM", "I_LIMIT_IDEAL", "I_LIMIT_LOSS")  # C-32: stated after every result


def _ascii(text: str) -> str:
    """`text` with every non-ASCII character escaped: µ becomes \\xb5."""
    return text.encode("ascii", "backslashreplace").decode()


def _marker(n: int) -> str:
    """The n-th marker's name: f0, 2f0, 3f0, …"""
    return "f0" if n == 1 else f"{n}f0"


def touchstone(s: np.ndarray, f: np.ndarray, names: list[str], comments: list[str]) -> bytes:
    """S (F, N, N) on f (Hz) as scikit-rf writes Touchstone 1.1, `# Hz S RI R 50.0`, Z0 at every port (C-28): the
    `comments` lines (a port map) before the option line, the port `names` after it; ASCII only, every name and line
    escaped by _ascii."""
    network = rf.Network(frequency=rf.Frequency.from_f(f, unit="Hz"), s=s, z0=Z0, name="out")
    network.port_names = [_ascii(name) for name in names]
    network.comments = "\n".join(" " + _ascii(line) for line in comments)
    return network.write_touchstone(return_string=True, form="ri").encode("ascii")


def port_map(project: dict, results: dict, lay: Layout, idx: list[int]) -> list[str]:
    """The port map of a Touchstone file of the run `results` (C-28): its basis, the run folder's name, the preset and
    each job's verdict, with its residual when flat or t_max; then each port k of `lay` in `idx`, numbered from 1:
    an external port's signal and reference, or a part's value or S2P file, pads and C_box, and whether its row and
    column were negated (lay.flipped); then each part port of `lay` not in `idx`, with what closed it."""
    by_ref, c_box = parts(project), results["c_box"]
    external = {port["name"]: port for port in project["ports"]}

    def part(ref: str) -> str:
        s2p = by_ref[ref]["s2p"]
        return f"part s2p {s2p['file']}:{s2p['connection']}" if s2p else f"part {by_ref[ref]['value']}"

    jobs = ", ".join(f"{job['port']} {job['verdict']}"
                     + (f" at {job['residual_db']:.1f} dB" if job["verdict"] in ("flat", "t_max") else "")
                     for job in results["jobs"])
    lines = [f"run {Path(results['run_dir']).name}, preset {results['preset']}: {jobs}"]
    for n, k in enumerate(idx, 1):
        name = lay.ports[k]["name"]
        if lay.ports[k]["part"]:
            pads = by_ref[name]["pads"]
            what = f"{part(name)}, signal {pads[0]}, reference {pads[1]}, C_box {c_box[name]:.6g} F"
        else:
            port = external[name]
            what = f"external, signal {port['signal']}, reference {shown_reference(port['reference'])}"
        lines.append(f"port {n} {name}: {what}, {'row and column negated' if lay.flipped[k] else 'as built'}")
    return lines + [f"terminated {port['name']}: {part(port['name'])}, C_box {c_box[port['name']]:.6g} F"
                    for k, port in enumerate(lay.ports) if port["part"] and k not in idx]


def grid_lines(grid: list[dict], values: dict[str, str]) -> list[str]:
    """The port-map lines of verify's parts (C-36, C-37): one per entry of a model spec's `grid` that `values` names
    (each part's value text by ref), in grid order, with what it sat in the grid as: a C as its value plus its cell's
    own C, an R as its value, an L with its cell's own C."""
    def element(g: dict) -> str:
        if "L" in g:
            return f"L {g['L']:.6g} H with the cell's C {g['C']:.6g} F"
        return f"R {g['R']:g} ohm" if g["R"] is not None else f"C {g['C']:.6g} F (value + the cell's C)"

    return [f"in grid: {g['name']} {values[g['name']]} as {element(g)}" for g in grid if g["name"] in values]


def marker_lines(lay: Layout, chain: np.ndarray, ideal: np.ndarray | None) -> list[tuple[str, dict]]:
    """The marker lines of `chain` (F, 2, 2) (C-30, spec 5.8): at each marker, its frequency, the excitation level
    there, IL = −20·log10|S21| and RL = −20·log10|S11|, with `ideal`'s beside them when given (I_MARKER, else
    I_MARKER_TRACE); after each harmonic n·f0, its rejection HR = IL(n·f0) − IL(f0) (I_HR, else I_HR_TRACE)."""
    def losses(s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return -20 * np.log10(np.abs(s[:, 1, 0])), -20 * np.log10(np.abs(s[:, 0, 0]))

    (il, rl), lines = losses(chain), []
    il_ideal, rl_ideal = losses(ideal) if ideal is not None else (None, None)
    marker_code, hr_code = ("I_MARKER", "I_HR") if ideal is not None else ("I_MARKER_TRACE", "I_HR_TRACE")
    for n, k in enumerate(lay.markers, 1):
        line = {"marker": _marker(n), "f_mhz": f"{lay.f[k] / 1e6:g}", "a_db": f"{lay.a_db[k]:.1f}",
                "il_db": f"{il[k]:.2f}", "rl_db": f"{rl[k]:.2f}"}
        if ideal is not None:
            line |= {"il_ideal_db": f"{il_ideal[k]:.2f}", "rl_ideal_db": f"{rl_ideal[k]:.2f}"}
        lines.append((marker_code, line))
        if n >= 2:
            k0 = lay.markers[0]  # f0's grid index
            hr = {"marker": line["marker"], "hr_db": f"{il[k] - il[k0]:.1f}"}
            if ideal is not None:
                hr["hr_ideal_db"] = f"{il_ideal[k] - il_ideal[k0]:.1f}"
            lines.append((hr_code, hr))
    return lines


def summary_csv(lay: Layout, chain: np.ndarray, ideal: np.ndarray | None, p_layout: np.ndarray,
                expected: float) -> bytes:
    """summary.csv (C-29): COLUMNS, then one row per grid point: the marker's name or "", the excitation level, S11
    and S21 of `chain` and of `ideal` (each "" without it) in dB and degrees, σ_max and the reciprocity error of the
    layout N-port lay.s, the loss budget `p_layout` and loss_expected's `expected`. Comma-separated, "\\n" line ends,
    numbers as Python's repr."""
    def db_deg(s: np.ndarray) -> list[list[float]]:
        s11, s21 = s[:, 0, 0], s[:, 1, 0]
        return np.column_stack([20 * np.log10(np.abs(s11)), np.angle(s11, deg=True),
                                20 * np.log10(np.abs(s21)), np.angle(s21, deg=True)]).tolist()

    names = {k: _marker(n) for n, k in enumerate(lay.markers, 1)}
    columns = zip(lay.f.tolist(), lay.a_db.tolist(), db_deg(chain),
                  db_deg(ideal) if ideal is not None else [[""] * 4] * len(lay.f),
                  sigma_max(lay.s).tolist(), recip_err(lay.s).tolist(), p_layout.tolist())
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows([f, names.get(k, ""), a, *s, *i, sigma, err, loss, expected]
                     for k, (f, a, s, i, sigma, err, loss) in enumerate(columns))
    return out.getvalue().encode("utf-8")


def _traces(lay: Layout, s: np.ndarray) -> list:
    """The four (x, y) pairs of one curve of S (F, 2, 2) on lay's grid, as draw_summary plots them: |S21| and |S11| in
    dB against GHz, S11's locus on the Smith chart, and its points at lay's markers."""
    ghz, s11 = lay.f / 1e9, s[:, 0, 0]
    return [(ghz, 20 * np.log10(np.abs(s[:, 1, 0]))), (ghz, 20 * np.log10(np.abs(s11))), (s11.real, s11.imag),
            (s11[lay.markers].real, s11[lay.markers].imag)]


def draw_summary(fig, lay: Layout, chain: np.ndarray, ideal: np.ndarray | None, name: str,
                 label: str | None = None) -> tuple:
    """summary.png's plots (C-30) on the matplotlib Figure `fig` (summary_png's, or the GUI canvas's): |S21| and |S11|
    in dB against GHz, with layout solid and the ideal schematic dashed, a thin line at each marker, and S11's locus
    on a Smith chart with the markers as dots, under I_PLOT_TITLE with `label` (the what-if label, D-15) as its second
    line when given. Returns the axes (S21, S11, Smith)."""
    ax21, ax11, ax_smith = fig.subplots(1, 3)
    rf.plotting.smith(ax=ax_smith, draw_labels=True)
    ghz = lay.f / 1e9
    curves = [(chain, "-", "I_PLOT_LAYOUT")] + ([(ideal, "--", "I_PLOT_IDEAL")] if ideal is not None else [])
    for s, style, code in curves:
        s21, s11, locus, dots = _traces(lay, s)
        ax21.plot(*s21, style, label=render(code))
        ax11.plot(*s11, style, label=render(code))
        line, = ax_smith.plot(*locus, style)
        ax_smith.plot(*dots, "o", color=line.get_color())
    for ax, ylabel in ((ax21, "|S21| (dB)"), (ax11, "|S11| (dB)")):
        for k in lay.markers:
            ax.axvline(ghz[k], color="grey", linewidth=0.5)
        ax.set(xlabel=render("I_PLOT_FREQUENCY"), ylabel=ylabel)
        ax.legend()
    fig.suptitle(render("I_PLOT_TITLE", name=name) + ("\n" + label if label else ""), wrap=True)
    return ax21, ax11, ax_smith


def retrace_summary(axes: tuple, lay: Layout, chain: np.ndarray, ideal: np.ndarray | None) -> list:
    """Moves the curves that draw_summary drew on `axes` (its return, with `ideal` present or absent as drawn) to
    `chain`'s and `ideal`'s, through set_data of _traces' pairs, with no draw and no rescale (the GUI's instant retune,
    Stage 2 design 5.4). Curve k of n, layout first, is the k-th line of the S21 and S11 axes and the k-th pair of the
    Smith chart's last 2n lines. Returns those Line2D, per curve: S21, S11, locus, dots."""
    ax21, ax11, ax_smith = axes
    curves = [s for s in (chain, ideal) if s is not None]
    n, lines = len(curves), []
    for k, s in enumerate(curves):
        drawn = (ax21.lines[k], ax11.lines[k], ax_smith.lines[-2 * n + 2 * k], ax_smith.lines[-2 * n + 2 * k + 1])
        for line, xy in zip(drawn, _traces(lay, s)):
            line.set_data(*xy)
        lines += drawn
    return lines


def summary_png(lay: Layout, chain: np.ndarray, ideal: np.ndarray | None, name: str, label: str | None = None) -> bytes:
    """summary.png (C-30): draw_summary on a Figure drawn by Agg, never a pyplot figure, as PNG at 100 dpi."""
    from matplotlib.figure import Figure  # here only: no other code of the core loads matplotlib (C-5)

    fig = Figure(figsize=(15, 4.5), layout="constrained")
    draw_summary(fig, lay, chain, ideal, name, label)
    out = io.BytesIO()
    fig.savefig(out, format="png", dpi=100)
    return out.getvalue()


def write(folder: Path, files: dict[str, bytes], own: re.Pattern, command: str) -> None:
    """Writes `files` (name: bytes) into `folder`, made when missing (C-27): each to .{name}.tmp first, then each
    replaces its name, summary.csv first, then summary.png, then the rest (a person keeps the summaries open, so a
    held one refuses before anything changes); then each file whose whole name `own` matches and that `files` lacks,
    a stale one, is removed. No other file is touched. Any OSError on the way removes the temporary files left and
    raises E_RESULTS_WRITE for the file in hand, with `command` to run again."""
    # ponytail: files replaced before a refused one keep their new contents; the advised command rewrites them all
    order = sorted(files, key=lambda name: {"summary.csv": 0, "summary.png": 1}.get(name, 2))  # stable: the rest kept
    temporary = [folder / f".{name}.tmp" for name in order]
    path = folder
    try:
        folder.mkdir(parents=True, exist_ok=True)
        for name, tmp in zip(order, temporary):
            path = folder / name
            tmp.write_bytes(files[name])
        for name, tmp in zip(order, temporary):
            path = folder / name
            os.replace(tmp, path)
        for name in os.listdir(folder):
            if own.fullmatch(name) and name not in files:
                path = folder / name
                os.remove(path)
    except OSError as err:
        for tmp in temporary:  # the ones not yet replaced; a replaced one is gone already
            with contextlib.suppress(OSError):
                os.remove(tmp)
        raise KrsError("E_RESULTS_WRITE", path=str(path), reason=reason(err, "T_CANNOT_WRITE"),
                       command=command) from None
