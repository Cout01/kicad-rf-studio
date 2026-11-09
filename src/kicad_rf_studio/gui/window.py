# SPDX-License-Identifier: GPL-3.0-or-later
"""The main window (Stage 2 design 5.1, 5.3, 5.4): it creates a project from a board (NewForm) or opens one, shows its
cost, starts, follows and stops a run, its own or one it re-attaches through the project lock, replays the project's
last run and shows its results, which its parts' rows retune in this process (ResultsView), Apply stores through the
CLI's retune and Verify checks; Compare compares an antenna or an SI project with a variant of its kind (CompareView);
Advanced edits project.json's fields and saves them under the project lock (AdvancedView); all driven by one 500 ms
timer (`tick`). The project is read, a board's pads and antennas listed, a KiCad button press read, the board refilled
and saved in KiCad, new run, retune and compare waited for on a pool thread (control.open_project,
control.board_choices, control.handed, button.refill, cli.new, cli.new_antenna or cli.new_si, control.apply,
control.compare); an SI project's retune (Stage 4 design 5.10) runs on a thread of its own (control.retuned on
`tuner`), polled every TUNE_MS (take_retune); cost, run and verify start as a detached orchestrator (control.start),
so this process never reaches runs.run_jobs. Its Help menu shows About (control.about) and Qt's About."""
import html
import json
import subprocess
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QLocale, QLockFile, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtNetwork import QLocalServer
from PySide6.QtWidgets import (QAbstractScrollArea, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListView, QListWidget, QMainWindow,
                               QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)
# after PySide6: matplotlib's Qt backend then wraps the binding already loaded, never another one installed beside it
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from kicad_rf_studio import button, cli, pipeline, runs
from kicad_rf_studio.core.kicad.stackup import PRESETS as STACKUPS
from kicad_rf_studio.core.kicad.values import parse_band, parse_frequency
from kicad_rf_studio.core.messages import KrsError, detail, reason, render
from kicad_rf_studio.core.post.antenna import ANTENNA_LIMITS, draw_antenna, retrace_antenna
from kicad_rf_studio.core.post.outputs import LIMITS, draw_summary, retrace_summary
from kicad_rf_studio.core.post.si import draw_si, retrace_si, si_limits
from kicad_rf_studio.core.project import (DEFAULT_PRESET, HARMONICS, INTERFACES, SI_F_MAX, antenna, check_project,
                                          load_project, save_project, si)
from kicad_rf_studio.gui import control

COLUMNS = ("G_COL_PORT", "G_COL_TIME", "G_COL_RESIDUAL", "G_COL_SPEED", "G_COL_VERDICT")
# an SI cost's 2D table, which the Cost tab lists and Run…'s confirmation leaves out (Stage 4 design 5.9, 5.10)
TABLE_2D = ("I_SI_2D_HEADER", "I_SI_2D_PAIR", "I_SI_2D_LEG", "I_SI_2D_LINE", "W_2D_SHORT", "I_SI_SHORT_ROUTE")
# an SI retune's poll: about 70 ms of scikit-rf on the tuner's thread, then its blit (Stage 2 design 2 goal 4)
TUNE_MS = 20
PROGRESS = ("port", "t_ns", "residual_db", "speed_mcs")  # a progress event's params, in the first four columns
PART, VALUE, SNAP, S2P, FIXTURE = range(5)  # the parts table's columns
PART_COLUMNS = ("G_COL_PART", "G_COL_VALUE", "G_COL_SNAP", "G_COL_S2P", "G_COL_FIXTURE")
FIELD_COLUMNS = ("G_COL_FIELD", "G_COL_VALUE", "G_COL_DEFAULT", "G_COL_UNIT")  # Advanced's table; Value alone edited
DEFAULT_COLUMN_MAX = 320  # Advanced's Default column's width at most, in px
# Compare's table: compare.csv's DELTA_COLUMNS, as control.compare gives them
COMPARE_COLUMNS = ("G_COL_QUANTITY", "G_COL_MARKER", "G_COL_F_MHZ", "T_BASE", "T_VARIANT", "G_COL_UNIT", "G_COL_DELTA",
                   "G_COL_DELTA_UNIT", "G_COL_THRESHOLD", "G_COL_RESOLVED")
SNAPPING = tuple(zip(control.SERIES, ("G_SNAP_OFF", "G_SNAP_E12", "G_SNAP_E24")))  # a Snapping combo's (data, code)
FIXTURES = tuple(control.FIXTURE_LABELS.items())  # an S2P fixture combo's (data, code)


def mtime_ns(path: Path) -> int | None:
    """`path`'s st_mtime_ns, None when it cannot be stat'ed."""
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def page(*widgets: QWidget) -> QWidget:
    """A tab's page: `widgets` in a column."""
    holder = QWidget()
    layout = QVBoxLayout(holder)
    for widget in widgets:
        layout.addWidget(widget)
    return holder


def beside(*widgets: QWidget) -> QHBoxLayout:
    """`widgets` in a row: a form's field, or a row of a tab."""
    layout = QHBoxLayout()
    for widget in widgets:
        layout.addWidget(widget)
    return layout


def sentences() -> QListWidget:
    """A list of sentences, each wrapped at the list's width, and again when the list resizes."""
    return QListWidget(wordWrap=True, resizeMode=QListView.ResizeMode.Adjust)


def combo(choices: tuple, current: str, slot) -> QComboBox:
    """A combo box (a table cell's, or New's kind) of `choices`, (data, code) pairs shown as their code's text,
    `current`'s selected and only then its currentIndexChanged connected to `slot`, so that filling it emits nothing."""
    box = QComboBox()
    for data, code in choices:
        box.addItem(render(code), data)
    box.setCurrentIndex(box.findData(current))
    box.currentIndexChanged.connect(slot)
    return box


class ResultsView(QWidget):
    """The Results and retune tab (Stage 2 design 5.3, 5.4): the row (`header`) of the what-if label while
    RETUNE_VALIDATED is False, the stale indicator (`stale`, which the window sets) and Verify, the last two only with
    part ports; why there are no results; the retune box, shown only with part ports: the parts table (`parts`), as tall
    as its rows, a row per part port with its value, its Snapping, its S2P file and that file's fixture, then the row
    (`buttons`) of S2P file…, Revert, Apply and the retune's status line; summary.png's drawing on a FigureCanvasQTAgg;
    and the row (`footer`) of the result's lines and stated limits, then the last verify's comparison (`verify_lines`),
    shown only with part ports. `series` holds each part's Snapping as the user set it. `shown` is the read on display
    (display sets it), whose project and far field an antenna's chain is drawn with, and whose project an SI chain is.
    A row's edit emits `edited`; the window answers it with the chain of the rows (show_chain), an SI project's once
    its retune ends off the GUI thread (MainWindow.take_retune). The plot: its `axes` as draw_summary, draw_antenna or
    draw_si drew them (None without a plot, or to draw the next one in full) and its `curves`, animated, which a retune
    moves and blits (retrace_summary, retrace_antenna or retrace_si, blit) on the background (`bg`) that the last full
    draw kept (on_draw), None until one."""

    edited = Signal()

    def __init__(self):
        super().__init__()
        self.shown = control.Opened(None, None, None, None, None, None)
        self.what_if, self.problem, self.lines = QLabel(control.text("I_WHAT_IF", {})), QLabel(), sentences()
        self.stale, self.verify_button, self.verify_lines = QLabel(), QPushButton(render("G_VERIFY")), sentences()
        self.canvas = FigureCanvasQTAgg(Figure(layout="constrained"))
        self.axes, self.curves, self.bg = None, [], None
        self.parts, self.retune_box, self.buttons = QTableWidget(0, len(PART_COLUMNS)), QWidget(), QHBoxLayout()
        self.s2p_button, self.revert_button = QPushButton(render("G_CHOOSE_S2P")), QPushButton(render("G_REVERT"))
        self.apply_button, self.retune_status, self.series = QPushButton(render("G_APPLY")), QLabel(), {}
        for label in (self.what_if, self.stale, self.problem, self.retune_status):
            label.setWordWrap(True)  # its sentence, some 200 characters, would otherwise set the window's minimum width
        for widget in (self.what_if, self.stale, self.verify_button, self.problem, self.retune_box, self.verify_lines):
            widget.hide()  # until a read shows it
        self.parts.setHorizontalHeaderLabels([render(code) for code in PART_COLUMNS])
        self.parts.horizontalHeader().setSectionResizeMode(S2P, QHeaderView.ResizeMode.Stretch)  # a file's path
        # ponytail: the table grows with its rows, and the window's minimum height with it; a maximum height (a scroll
        # bar past some rows) if a chain's parts outgrow the screen
        self.parts.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.parts.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for widget in (self.s2p_button, self.revert_button, self.apply_button, self.retune_status):
            self.buttons.addWidget(widget)
        box = QVBoxLayout(self.retune_box)
        box.setContentsMargins(0, 0, 0, 0)  # aligned with the tab's other widgets
        box.addWidget(self.parts)
        box.addLayout(self.buttons)
        self.header = beside(self.what_if, self.stale, self.verify_button)
        for k in (0, 1):
            self.header.setStretch(k, 1)  # the labels take the row's width, and Verify keeps its own
        self.footer = beside(self.lines, self.verify_lines)
        layout = QVBoxLayout(self)
        layout.addLayout(self.header)
        for widget in (self.problem, self.retune_box, self.canvas):
            layout.addWidget(widget)
        layout.addLayout(self.footer)
        self.parts.itemChanged.connect(self.item_changed)
        self.s2p_button.clicked.connect(self.choose_s2p)
        self.canvas.mpl_connect("draw_event", self.on_draw)

    def display(self, opened: control.Opened, folder: Path | None) -> None:
        """Shows the project read `opened` of the project folder `folder` (None for none), kept first as `shown`, the
        read on display: the problem's line only with one; the rows of the results' part ports as project.json stores
        them (control.rows, S2P files against `folder`), none without part ports, and only with them Verify and the
        last verify's comparison (opened.verified); then the results' chain (show_chain), under the folder's name, drawn
        in full (`axes` None): a read, Revert and the re-read after Apply. Never touches retune_status or the stale
        indicator."""
        self.shown = opened
        res = opened.results
        self.problem.setText("" if opened.problem is None else control.text(*opened.problem))
        self.problem.setVisible(opened.problem is not None)
        rows = control.rows(opened.project, folder, res.refs) if res is not None and res.refs else []
        self.show_rows(rows)
        self.verify_lines.clear()
        self.verify_lines.addItems([control.text(c, p) for c, p in opened.verified])
        for widget in (self.verify_button, self.verify_lines):
            widget.setVisible(bool(rows))
        self.axes = None
        self.show_chain(res, folder.name if folder else "")

    def show_rows(self, rows: list[control.Row]) -> None:
        """`rows` in the parts table, its signals blocked: Part read-only; Value and S2P file editable; Snapping the
        part's series as the user set it (`series`), else its default in the project on display (control.default_series:
        E24 for every part of an SI project); S2P fixture the row's connection. The retune box shows only with rows."""
        with QSignalBlocker(self.parts):
            self.parts.setRowCount(len(rows))
            for k, row in enumerate(rows):
                part = QTableWidgetItem(row.ref)
                part.setFlags(part.flags() & ~Qt.ItemFlag.ItemIsEditable)
                for column, item in ((PART, part), (VALUE, QTableWidgetItem(row.value)),
                                     (S2P, QTableWidgetItem(row.s2p))):
                    self.parts.setItem(k, column, item)
                series = self.series.get(row.ref, control.default_series(row.ref, self.shown.project))
                self.parts.setCellWidget(k, SNAP, combo(SNAPPING, series, self.snapping_changed))
                self.parts.setCellWidget(k, FIXTURE, combo(FIXTURES, row.connection, self.fixture_changed))
        self.retune_box.setVisible(bool(rows))

    def rows(self) -> list[control.Row]:
        """The table's rows: each part's ref, its value as typed, its S2P file (stripped) and its fixture's
        connection."""
        t = self.parts
        return [control.Row(t.item(k, PART).text(), t.item(k, VALUE).text(), t.item(k, S2P).text().strip(),
                            t.cellWidget(k, FIXTURE).currentData()) for k in range(t.rowCount())]

    def snap_row(self, k: int) -> None:
        """Row k's value snapped to its Snapping (control.snapped), written back with the table's signals blocked when
        it differs."""
        item, series = self.parts.item(k, VALUE), self.parts.cellWidget(k, SNAP).currentData()
        text = control.snapped(self.parts.item(k, PART).text(), item.text(), series)
        if text != item.text():
            with QSignalBlocker(self.parts):
                item.setText(text)

    def item_changed(self, item: QTableWidgetItem) -> None:
        """A cell edited (itemChanged): a value snapped (snap_row), then `edited` emitted."""
        if item.column() == VALUE:
            self.snap_row(item.row())
        self.edited.emit()

    def snapping_changed(self, index: int) -> None:
        """A row's Snapping set: its row, the one whose Snapping combo sent it, keeps that series in `series` and has
        its value snapped to it; then `edited` emitted."""
        box = self.sender()
        k = next(k for k in range(self.parts.rowCount()) if self.parts.cellWidget(k, SNAP) is box)
        self.series[self.parts.item(k, PART).text()] = box.currentData()
        self.snap_row(k)
        self.edited.emit()

    def fixture_changed(self, index: int) -> None:
        """A row's S2P fixture set: `edited` emitted."""
        self.edited.emit()

    def choose_s2p(self) -> None:
        """S2P file…: the file picked in the dialog into the current row's S2P file cell, whose itemChanged emits
        `edited`; nothing without a current row, or on Cancel."""
        k = self.parts.currentRow()
        if k < 0:
            return
        name, _ = QFileDialog.getOpenFileName(self, render("G_CHOOSE_S2P"), "", render("G_S2P_FILTER"))
        if name:
            self.parts.item(k, S2P).setText(str(Path(name)))  # the system's separators, as a stored file's row shows

    def show_chain(self, res: pipeline.ChainResults | None, name: str) -> None:
        """Shows the chain results `res` (None for none), `name` being the project folder's name, which summary.png's
        title shows: the lines cleared; the what-if label only when `res` carries what_if; with any results, plot or
        not, their lines, then LIMITS (C-32), an antenna's ANTENNA_LIMITS. With a chain closed on 2 external ports and
        the plot drawn (`axes`), its curves moved in place (retrace_summary) and blitted (blit). Otherwise the figure
        cleared, then, with such a chain, summary.png's plots (draw_summary) with the label as their title's second
        line, their curves (`curves`) animated, which a full draw leaves to on_draw; Qt redraws the canvas once its
        event loop runs (draw_idle). An antenna's chain (Stage 3 design 5.10) draws draw_antenna's figure for the window
        (gui: the six panels in one row, the limits in the lines) with the far field of the read (the run's, or the
        current verify's while the retune moves S11), the title's last line saying which run it comes from, and is
        moved by retrace_antenna. An SI chain (Stage 4 design 5.10) draws draw_si's figure for the window (gui: no
        foot, the limits in the lines) with its reading, moved by retrace_si."""
        # ponytail: the curves keep the limits of the last full draw (the stored values', or the first good values after
        # a refusal); a retune far off clips until Revert or Apply draws again
        fig = self.canvas.figure
        self.lines.clear()
        label = self.what_if.text() if res is not None and res.what_if else None
        self.what_if.setVisible(label is not None)
        ant = res is not None and antenna(self.shown.project)  # a result always comes with its project
        is_si = res is not None and si(self.shown.project)
        if res is not None:
            limits = si_limits(self.shown.project) if is_si else ANTENNA_LIMITS if ant else LIMITS
            self.lines.addItems([control.text(c, p) for c, p in res.lines] + [render(c) for c in limits])
        plot = res is not None and (res.reading is not None if is_si
                                    else res.chain is not None and len(res.ext) == (1 if ant else 2))
        if plot and self.axes is not None:
            if is_si:
                moved = retrace_si(self.axes, res.reading)
            elif ant:
                moved = retrace_antenna(self.axes, res.lay.f, res.chain[:, 0, 0], self.shown.project)
            else:
                moved = retrace_summary(self.axes, res.lay, res.chain, res.ideal)
            if moved is not None:  # an SI reading with another count of levels is drawn in full below
                self.blit()
                return
        fig.clear()
        self.axes, self.curves, self.bg = None, [], None
        if plot and is_si:
            self.axes = draw_si(fig, [(name, res.reading)], self.shown.project, render("I_PLOT_SI_TITLE", name=name),
                                label, gui=True)
            self.curves = retrace_si(self.axes, res.reading)  # the data unchanged
        elif plot and ant:
            # ponytail: with part ports the η and cut panels stay the current verify's while the retune moves S11,
            # labelled so; the instant far field by superposition (design 7) would move them too
            p, source = self.shown.project, self.shown.far_source
            far_from = source and render("G_FAR_FIELD_FROM", source=source[0], run_dir=Path(source[1]).name)
            label = "\n".join(filter(None, (label, far_from))) or None
            self.axes = draw_antenna(fig, res.lay.f, res.chain[:, 0, 0], p, self.shown.far, name, label, gui=True)
            self.curves = retrace_antenna(self.axes, res.lay.f, res.chain[:, 0, 0], p)  # the data unchanged
        elif plot:
            self.axes = draw_summary(fig, res.lay, res.chain, res.ideal, name, label)
            self.curves = retrace_summary(self.axes, res.lay, res.chain, res.ideal)  # the data unchanged
        for curve in self.curves:
            curve.set_animated(True)
        self.canvas.draw_idle()

    def blit(self) -> None:
        """The curves drawn on the background that the last full draw kept (`bg`), then the figure copied to the screen
        (canvas.blit); without a background, the canvas drawn in full, whose draw_event keeps one (on_draw)."""
        # ponytail: a status line that changes height (G_APPLIED cleared, the stale indicator lit) resizes the canvas,
        # which Qt then redraws once in full (about 0.1 s for v1's figure, a quarter of a second for an antenna's six
        # panels or an SI figure's three, as on the first edit after a verify); fixed-height status lines
        # (setRetainSizeWhenHidden) if that is felt
        if self.bg is None:
            self.canvas.draw()
            return
        self.canvas.restore_region(self.bg)
        for curve in self.curves:
            curve.axes.draw_artist(curve)
        self.canvas.blit(self.canvas.figure.bbox)

    def on_draw(self, event) -> None:
        """A full draw's draw_event (the first one, a resize's, a draw_idle's): the figure as drawn, without the
        animated curves, kept as the background of the blits (`bg`), then the curves drawn on it. A blit was measured
        at 1.1–1.6 ms on lpf915, against 103–108 ms for a full redraw."""
        self.bg = self.canvas.copy_from_bbox(self.canvas.figure.bbox)
        for curve in self.curves:
            curve.axes.draw_artist(curve)


class NewForm(QGroupBox):
    """New from a board (Stage 2 design 5.3, 5.5; Stage 3 design 5.10; Stage 4 design 5.10): the board and the project
    folder, each with its Browse…, and Refill zones and save in KiCad after the board's (`refill_button`, disabled until
    the window enables it); the project's kind (`kind`: a matching chain, an antenna or signal integrity), which shows
    its own rows alone (kind_changed); the start pad, picked from the board's pads or typed; the end pad of a chain or
    an SI line, picked or typed too, with Swap beside it; a chain's f0 and its harmonics; an antenna's footprint
    (`antenna`), picked from the board's antennas (show_antennas), and its band (`band`), one of control.BANDS or
    Custom, whose F_LO:F_HI is typed in `band_text` (band_changed); an SI project's `interface`, a preset of INTERFACES,
    whose f_max and target the rows show disabled, or Custom, whose `f_max` (text, as f0) and `target` (Ω) are typed
    (interface_changed); its `pair`, None for a single-ended net, the partner by KiCad's pair rule, or the partner's two
    end pads picked in `pair_with` (pair_changed); and up to two victims, each a row of its start and end pickers
    (`victims`); new's options at new's defaults (the board's own stackup, and a lid height of 0 for none); Create, its
    status line and new's notes. `chosen` is the board text whose pads were last read; `form` is the form's layout, and
    `end_row`, `band_row`, `pair_row` and `victim_rows` are the layouts of the end's row, the band's, the pair's and
    the victims'."""

    def __init__(self):
        super().__init__(render("G_NEW"))
        self.board, self.board_button = QLineEdit(), QPushButton(render("G_BROWSE"))
        self.refill_button = QPushButton(render("G_REFILL"))
        self.refill_button.setEnabled(False)  # until a press gives a KiCad to ask
        self.kind = combo((("chain", "G_KIND_CHAIN"), ("antenna", "G_KIND_ANTENNA"), ("si", "G_KIND_SI")), "chain",
                          self.kind_changed)
        self.start, self.end, self.f0 = QComboBox(editable=True), QComboBox(editable=True), QLineEdit()
        self.swap_button = QPushButton(render("G_SWAP"))
        self.antenna, self.band, self.band_text = QComboBox(), QComboBox(), QLineEdit()
        for label, f_lo, f_hi in control.BANDS:
            self.band.addItem(label, (f_lo, f_hi))
        self.band.addItem(render("G_BAND_CUSTOM"), None)
        # 2.4 GHz by its index: findData finds None and text, but a tuple only as the very object stored (probed on
        # PySide6 6.12)
        self.band.setCurrentIndex(2)
        self.harmonics = QSpinBox(minimum=1, maximum=99, value=HARMONICS)
        self.interface, self.f_max = QComboBox(), QLineEdit()
        for name in INTERFACES:
            self.interface.addItem(name, name)
        self.interface.addItem(render("G_INTERFACE_CUSTOM"), "custom")
        self.target = QDoubleSpinBox(minimum=1, maximum=1000, decimals=1, locale=QLocale.c())  # C, as the lid's
        # ponytail: a partner by the rule is shown in new's notes (I_SI_PAIR), not before Create; a live preview if
        # users ask for it
        self.pair = combo(((None, "G_PAIR_NONE"), ("rule", "G_PAIR_RULE"), ("given", "G_PAIR_PICK")), "rule",
                          self.pair_changed)
        self.pair_with = (QComboBox(editable=True), QComboBox(editable=True))
        self.victims = tuple((QComboBox(editable=True), QComboBox(editable=True)) for _ in range(2))
        self.preset, self.stackup = QComboBox(), QComboBox()
        self.preset.addItems(cli.PRESETS)
        self.preset.setCurrentText(DEFAULT_PRESET)
        self.stackup.addItem(render("G_STACKUP_BOARD"), None)
        for name in STACKUPS:
            self.stackup.addItem(name, name)
        # the C locale: project.json and the CLI write 2.5, and the system's locale may show 2,50
        self.lid = QDoubleSpinBox(maximum=100, decimals=2, locale=QLocale.c(), specialValueText=render("T_NONE"))
        self.folder, self.folder_button = QLineEdit(), QPushButton(render("G_BROWSE"))
        self.create_button, self.status, self.notes = QPushButton(render("G_CREATE")), QLabel(), sentences()
        self.status.setWordWrap(True)  # a refusal names a path, which would otherwise widen the window
        self.chosen = ""
        self.form, self.end_row = QFormLayout(self), beside(self.end, self.swap_button)
        self.end_row.setStretch(0, 1)  # the end picker takes the row's width, as the start one does; Swap keeps its own
        self.band_row = beside(self.band, self.band_text)
        self.pair_row = beside(self.pair, *self.pair_with)
        self.victim_rows = tuple(beside(*boxes) for boxes in self.victims)
        for code, field in (("G_NEW_BOARD", beside(self.board, self.board_button, self.refill_button)),
                            ("G_NEW_KIND", self.kind), ("G_NEW_START", self.start), ("G_NEW_END", self.end_row),
                            ("G_NEW_ANTENNA", self.antenna), ("G_NEW_F0", self.f0),
                            ("G_NEW_HARMONICS", self.harmonics), ("G_NEW_BAND", self.band_row),
                            ("G_NEW_INTERFACE", self.interface), ("G_NEW_F_MAX", self.f_max),
                            ("G_NEW_TARGET", self.target), ("G_NEW_PAIR", self.pair_row)):
            self.form.addRow(render(code), field)
        for n, row in enumerate(self.victim_rows, 1):
            self.form.addRow(render("G_NEW_VICTIM", n=n), row)
        for code, field in (("G_NEW_PRESET", self.preset), ("G_NEW_STACKUP", self.stackup), ("G_NEW_LID", self.lid),
                            ("G_NEW_FOLDER", beside(self.folder, self.folder_button))):
            self.form.addRow(render(code), field)
        for widget in (self.create_button, self.status, self.notes):
            self.form.addRow(widget)
        self.swap_button.clicked.connect(self.swap)
        self.band.currentIndexChanged.connect(self.band_changed)
        self.interface.currentIndexChanged.connect(self.interface_changed)
        self.kind_changed()
        self.band_changed()
        self.interface_changed()
        self.pair_changed()

    def swap(self) -> None:
        """Swap: start and end exchange their texts."""
        start, end = self.start.currentText(), self.end.currentText()
        self.start.setCurrentText(end)
        self.end.setCurrentText(start)

    def kind_changed(self) -> None:
        """The kind set (kind's currentIndexChanged, and once at the start): the antenna's and the band's rows shown
        for an antenna, the end's for a chain or SI, f0's and the harmonics' for a chain, and the interface's, f_max's,
        the target's, the pair's and both victims' for SI; the rows to hide first, since a row shown lays the form out
        at once, which would keep the space of a row still to hide until the event loop runs (probed: a grab then shows
        the gap)."""
        kind = self.kind.currentData()
        si_rows = (self.interface, self.f_max, self.target, self.pair_row, *self.victim_rows)
        rows = ((self.antenna, kind == "antenna"), (self.band_row, kind == "antenna"),
                (self.end_row, kind != "antenna"), (self.f0, kind == "chain"), (self.harmonics, kind == "chain"),
                *((row, kind == "si") for row in si_rows))
        for row, shown in sorted(rows, key=lambda pair: pair[1]):  # False first
            self.form.setRowVisible(row, shown)

    def band_changed(self) -> None:
        """The band set (band's currentIndexChanged, and once at the start): its F_LO:F_HI text enabled only for
        Custom."""
        self.band_text.setEnabled(self.band.currentData() is None)

    def interface_changed(self) -> None:
        """The interface set (interface's currentIndexChanged, and once at the start): f_max and the target enabled
        only for Custom, which keeps what they hold; a preset shows its band (SI_F_MAX) and its target there, and sets
        the pair's mode to its own, by the rule for a pair's preset and None for a net's."""
        name = self.interface.currentData()
        custom = name == "custom"
        self.f_max.setEnabled(custom)
        self.target.setEnabled(custom)
        if not custom:
            preset = INTERFACES[name]
            self.f_max.setText(f"{SI_F_MAX / 1e9:g}GHz")
            self.target.setValue(preset["target_ohm"])
            self.pair.setCurrentIndex(self.pair.findData("rule" if preset["pair"] else None))

    def pair_changed(self) -> None:
        """The pair's mode set (pair's currentIndexChanged, and once at the start): the partner's two end pickers
        (`pair_with`) enabled only for a partner picked here ("given")."""
        for box in self.pair_with:
            box.setEnabled(self.pair.currentData() == "given")

    def show_antennas(self, kinds: dict[str, str], antenna: str = "") -> None:
        """The antenna footprints `kinds` (control._antennas: each one's kind by its reference) in the footprint combo,
        each as its reference; a module's or a chip antenna's item disabled, with its refusal in the window's words
        (control.text of E_ANTENNA_MODULE or E_ANTENNA_CHIP) as its tooltip, in rich text, which Qt word-wraps (a plain
        tooltip of some 250 characters runs about 1600 px wide). `antenna` is picked when given and listed, else the
        first printed antenna, else none: Qt keeps a disabled first item current otherwise."""
        # ponytail: a disabled entry's reason is its tooltip; a 200-character item would widen the window past 1200
        box = self.antenna
        box.clear()
        for k, (ref, kind) in enumerate(kinds.items()):
            box.addItem(ref, ref)
            if kind != "printed":
                item = box.model().item(k)
                item.setEnabled(False)
                why = control.text("E_ANTENNA_MODULE" if kind == "module" else "E_ANTENNA_CHIP", {"ref": ref})
                item.setToolTip(f"<p>{html.escape(why, quote=False)}</p>")
        pick = antenna if antenna in kinds else next((ref for ref, kind in kinds.items() if kind == "printed"), "")
        box.setCurrentIndex(box.findData(pick))  # -1, none picked, for "": no reference is empty


class CompareView(QWidget):
    """The Compare tab (Stage 3 and Stage 4 design 5.8, 5.10), for two antenna projects or two SI projects: the row of
    Variant… (`variant_button`), the variant's project file (`variant`, which the window sets) and Compare the projects
    (`compare_button`, which the window enables); its status line (`status`); compare's lines (`lines`); its deltas
    (`table`, control.cells under COMPARE_COLUMNS, an SI row's quantity and mark in the window's words); and
    compare.png (`picture`), at its own size in a scroll area."""

    def __init__(self):
        super().__init__()
        self.variant_button, self.variant = QPushButton(render("G_COMPARE_VARIANT")), QLabel()
        self.compare_button, self.status = QPushButton(render("G_COMPARE")), QLabel(render("G_COMPARE_NONE"))
        self.lines, self.table, self.picture = sentences(), QTableWidget(0, len(COMPARE_COLUMNS)), QLabel()
        self.compare_button.setEnabled(False)  # until the window has a variant
        for label in (self.variant, self.status):
            label.setWordWrap(True)  # a path, or a refusal naming one, would otherwise widen the window
        self.table.setHorizontalHeaderLabels([render(code) for code in COMPARE_COLUMNS])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        # ponytail: compare.png at its own size in a scroll area, which keeps the window's 1200 × 800; scaled to the
        # tab's width if users want it whole
        # resizable: a label whose pixmap is set after setWidget keeps its old size otherwise (probed: 12 × 14 px, no
        # scroll range)
        scroll = QScrollArea(widgetResizable=True)
        scroll.setWidget(self.picture)
        row = beside(self.variant_button, self.variant, self.compare_button)
        row.setStretch(1, 1)  # the variant's path takes the row's width, and the buttons keep their own
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        for widget in (self.status, self.lines, self.table, scroll):
            layout.addWidget(widget)

    def display(self, lines: list[str], cells: list[list[str]], picture: Path | None) -> None:
        """compare's `lines`, its deltas' `cells`, a table row per list, each cell its text, and the image file
        `picture` (None for none, an empty pixmap)."""
        self.lines.clear()
        self.lines.addItems(lines)
        self.table.setRowCount(len(cells))
        for k, row in enumerate(cells):
            for j, text in enumerate(row):
                self.table.setItem(k, j, QTableWidgetItem(text))
        self.picture.setPixmap(QPixmap() if picture is None else QPixmap(str(picture)))


class AdvancedView(QWidget):
    """The Advanced tab (Stage 2 design 5.3): project.json's fields (control.fields) in `table`, a row each with its
    name, its value as JSON, the one cell that can be edited, its default and its unit; then the row of Save
    (`save_button`, which the window enables) and its status line (`status`). `edits` holds the text of each edited
    value by its field's path, and `paths` each row's path. The Default column is fitted to its contents after each
    display, but at most DEFAULT_COLUMN_MAX px (Stage 3 design 5.10): an antenna's far_field.f_hz default, 200
    characters, would otherwise widen it to 2407 px and leave the Value column, the only editable one, 100 px; v1's
    widest default takes 103 px, so v1's columns stay as they are."""

    def __init__(self):
        super().__init__()
        self.table, self.save_button = QTableWidget(0, len(FIELD_COLUMNS)), QPushButton(render("G_SAVE"))
        self.status, self.edits, self.paths = QLabel(), {}, []
        self.table.setHorizontalHeaderLabels([render(code) for code in FIELD_COLUMNS])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)  # a name, a default or a unit unclipped
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # the value: a list, or a path
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)  # the default: fitted in display, capped
        self.save_button.setEnabled(False)  # until an edit
        self.status.setWordWrap(True)  # a refusal names a path, which would otherwise widen the window
        buttons = beside(self.save_button, self.status)
        buttons.setStretch(1, 1)  # the status line takes the row's width, and Save keeps its own
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(buttons)
        self.table.itemChanged.connect(self.item_changed)

    def display(self, stored: dict | None) -> None:
        """project.json as stored (control.Opened.stored; None for none, an empty table) in the table, its signals
        blocked: Field, Default and Unit read-only, Value as json.dumps writes it, non-ASCII text as it is; then `edits`
        cleared and the Default column fitted to its contents, at most DEFAULT_COLUMN_MAX px. Never touches
        `status`."""
        # ponytail: a re-read refills the table and drops unsaved edits; carry them per field, as the retune's rows are,
        # if users lose work
        fields = [] if stored is None else control.fields(stored)
        with QSignalBlocker(self.table):
            self.table.setRowCount(len(fields))
            for k, f in enumerate(fields):
                unit = "" if f.unit is None else render(f.unit)
                for column, text in enumerate((f.name, json.dumps(f.value, ensure_ascii=False), f.default, unit)):
                    item = QTableWidgetItem(text)
                    if column != 1:  # Value alone is edited
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(k, column, item)
        self.paths = [f.path for f in fields]
        self.edits.clear()
        # ponytail: a default past 320 px (an antenna's far-field list) is elided; drag the column to read it whole
        self.table.resizeColumnToContents(2)
        self.table.setColumnWidth(2, min(self.table.columnWidth(2), DEFAULT_COLUMN_MAX))

    def item_changed(self, item: QTableWidgetItem) -> None:
        """A value edited (itemChanged): its text kept in `edits` under its row's path."""
        self.edits[self.paths[item.row()]] = item.text()


class MainWindow(QMainWindow):
    """The main window; `prefix` is the command that starts the orchestrator (control.orchestrator() by default).
    Its state: `path`, the resolved project file; `opened`, its last read (control.Opened) and `loading`, the read
    going on (a Future); `applying`, Apply's retune going on (a Future), and `verify_next`, whether its end starts
    verify (Verify's Yes to G_APPLY_FIRST); an SI project's retune session (Stage 4 design 5.10): `tuner`, the
    one-thread executor its retunes run on, `retuning`, the latest one (a Future, None without one), and `tune_timer`,
    which polls it every TUNE_MS while one goes on (take_retune); `cost`, the folder of this model's last cost, which
    Run… confirms on; the Compare tab (`comparison`, a CompareView), with `variant`, the resolved project file it
    compares the project with (None until Variant… picks one), and `comparing`, its compare going on (a Future); the
    watch: `command`, `run_dir`, its events' `tail`, its `end` event and `proc`, only a
    process this window started; `live`, whether the watched process goes on; `mtime`, project.json's and the board
    file's st_mtime_ns at the last read (stamp); `started`, every process this window started, polled every tick, so
    that none is left a zombie on Linux; the New form's work going on (Futures): `pads_read`, the chosen board's
    pads and antennas, or a press (take_handoff), and `creating`, new; and the KiCad button's presses: `handoff`, the
    handoff file of the last press taken, and `handed`, the last press shown (control.Handed), each None before the
    first, and `refilling`, Refill's refill and save in KiCad going on (a Future); one window per user (gui.main,
    serve): `server`, the local server that takes a second start's request, and `lock`, gui.lock, both None in a
    window main did not make.
    Every slot is a bound method: a lambda or partial slot would keep a closed window alive (probed on PySide6
    6.12)."""

    def __init__(self, prefix: list[str] | None = None):
        super().__init__()
        self.setWindowTitle(render("G_APP"))
        self.resize(1200, 800)
        self.prefix = prefix or control.orchestrator()
        self.path = self.opened = self.loading = self.applying = self.cost = self.mtime = None
        self.pads_read = self.creating = self.handoff = self.handed = self.refilling = self.server = self.lock = None
        self.command = self.run_dir = self.tail = self.end = self.proc = None
        self.variant = self.comparing = None
        self.live, self.started, self.verify_next = False, [], False
        self.pool = ThreadPoolExecutor(1)
        self.tuner, self.retuning = ThreadPoolExecutor(1), None
        self.open_button, self.project_status, self.new_form = QPushButton(render("G_OPEN")), QLabel(), NewForm()
        self.cost_lines, self.cost_status = sentences(), QLabel()
        self.cost_button, self.run_button = QPushButton(render("G_COST")), QPushButton(render("G_RUN"))
        self.banner, self.jobs, self.log = QLabel(), QTableWidget(0, len(COLUMNS)), sentences()
        self.run_status, self.stop_button = QLabel(), QPushButton(render("G_STOP"))
        for label in (self.project_status, self.cost_status, self.banner, self.run_status):
            label.setWordWrap(True)  # a long line (two paths) would otherwise widen the window past the screen
        self.project_status.setAlignment(Qt.AlignmentFlag.AlignTop)  # under Open, not in the middle of its page
        self.banner.hide()
        self.jobs.setHorizontalHeaderLabels([render(code) for code in COLUMNS])
        self.jobs.horizontalHeader().setStretchLastSection(True)  # the verdict, the longest cell
        self.tabs = QTabWidget()
        for code, widgets in (("G_TAB_PROJECT", (self.open_button, self.project_status, self.new_form)),
                              ("G_TAB_COST", (self.cost_lines, self.cost_status, self.cost_button, self.run_button)),
                              ("G_TAB_RUN", (self.banner, self.jobs, self.log, self.run_status, self.stop_button))):
            self.tabs.addTab(page(*widgets), render(code))
        self.results, self.comparison, self.advanced = ResultsView(), CompareView(), AdvancedView()
        self.tabs.addTab(self.results, render("G_TAB_RESULTS"))
        self.tabs.addTab(self.comparison, render("G_TAB_COMPARE"))
        self.tabs.addTab(self.advanced, render("G_TAB_ADVANCED"))
        self.setCentralWidget(self.tabs)
        menu = self.menuBar().addMenu(render("G_MENU_HELP"))
        self.about_action = menu.addAction(render("G_ABOUT"))
        self.about_qt_action = menu.addAction(render("G_ABOUT_QT"))
        self.about_action.triggered.connect(self.about)
        self.about_qt_action.triggered.connect(self.about_qt)
        form = self.new_form
        for widget, slot in ((self.open_button, self.browse), (self.cost_button, self.estimate),
                             (self.run_button, self.run), (self.stop_button, self.stop),
                             (form.board_button, self.pick_board), (form.refill_button, self.refill),
                             (form.folder_button, self.pick_folder),
                             (form.create_button, self.create_project), (self.results.revert_button, self.revert),
                             (self.results.apply_button, self.apply), (self.results.verify_button, self.verify),
                             (self.comparison.variant_button, self.pick_variant),
                             (self.comparison.compare_button, self.compare_variant),
                             (self.advanced.save_button, self.save)):
            widget.clicked.connect(slot)
        self.results.edited.connect(self.retune)
        form.board.editingFinished.connect(self.board_chosen)
        for widget in (self.cost_button, self.run_button, self.stop_button, self.results.apply_button,
                       self.results.verify_button):  # no project
            widget.setEnabled(False)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(500)
        self.tune_timer = QTimer(self)
        self.tune_timer.setInterval(TUNE_MS)
        self.tune_timer.timeout.connect(self.take_retune)

    def browse(self) -> None:
        """Open a project…: the project file picked in the dialog; nothing on Cancel."""
        name, _ = QFileDialog.getOpenFileName(self, render("G_OPEN"), "", render("G_OPEN_FILTER"))
        if name:
            self.open_project(Path(name))

    def open_project(self, path: Path) -> None:
        """Opens the project file `path`, a folder standing for its project.json: the views and the watch cleared,
        then its read and a tick. A process this window started goes on, no longer watched, and so does an Apply's
        retune of the previous project, which ends on the pool unread (`applying` None) and starts no verify
        (`verify_next` False), an SI retune of it, which ends on the tuner unshown (`retuning` None), and a compare of
        the previous project, which ends on the pool unread too (`comparing` None); the Compare tab is emptied and says
        G_COMPARE_NONE, its variant kept."""
        self.path = pipeline.project_path(str(path)).resolve()
        self.command = self.run_dir = self.tail = self.end = self.proc = self.cost = self.opened = self.applying = None
        self.verify_next, self.comparing, self.retuning = False, None, None
        self.comparison.display([], [], None)
        self.comparison.status.setText(render("G_COMPARE_NONE"))
        for view in (self.cost_lines, self.cost_status, self.log, self.run_status, self.advanced.status):
            view.clear()
        self.jobs.setRowCount(0)
        self.results.display(control.Opened(None, None, None, None, None, None), None)  # no plot, lines, labels or rows
        self.results.retune_status.clear()
        self.results.series.clear()  # the Snapping choices are the open project's
        self.show_stale()  # no rows: hidden
        self.advanced.display(None)  # no fields, and no edits of the previous project
        self.load()
        self.tick()

    def stamp(self) -> tuple[int | None, int | None]:
        """The st_mtime_ns of project.json and of the board file that the last read names (mtime_ns, Opened.board),
        the board's None while that read names none, so a board that failed to load is read again when it is saved."""
        board = None if self.opened is None else self.opened.board
        return mtime_ns(self.path), None if board is None else mtime_ns(board)

    def load(self) -> None:
        """Reads the project off the GUI thread (control.open_project on the pool, as `loading`), its stamp taken
        first, so that a save is read once, and `cost` cleared, so that Run… waits for the read."""
        self.mtime, self.cost = self.stamp(), None
        self.project_status.setText(render("G_LOADING"))
        self.loading = self.pool.submit(control.open_project, self.path)

    def tick(self) -> None:
        """The window's one driver, every 500 ms (design 5.1), in this order: the project lock's holder
        (runs.lock_holder), through which a run this window did not start is attached (below); a project read that
        finished, shown (a display that fails shows E_INTERNAL, and the tick goes on), with the user's unapplied rows
        carried over it (control.carried) and retuned on its layout, and G_DROPPED when one was lost; Apply's retune
        that ended (applied); the watched folder's new events, then its state (control.run_state, given that holder);
        the G_LOCKED banner while another's live run holds the lock and this window watches no process of its own; a
        read when the stamp changed (a save of project.json, Apply's included, or of the board file); the buttons: Cost
        while nothing watched goes on and no run holds the lock, Run… also only with a cost of this model and no Apply
        going on, Stop only while the watch goes on, the retune box while no read and no Apply goes on, so that its
        table and buttons wait for Apply's re-read, and Apply and Verify also only while nothing watched goes on, no
        run holds the lock and the last read has results; Advanced's table while no holder lives (design 5.1: no model
        edit under the lock), and its Save also only while no read and no Apply goes on and there are edits. A holder
        whose run folder is the project's results/ is a retune (pipeline.retune, r2 §1): waited for, never watched or
        bannered. Any other holder's run folder, when it names one other than the watched one, is watched when this
        window's own process was not running at the last tick (`live`) and the holder lives, or when the holder is dead
        and nothing is watched (on open), so a cost meanwhile keeps its tab. Before all that, with or without a
        project, New's board read, new itself and Refill when done (show_pads; created, which opens the project new
        wrote, whose own tick runs inside this one; refilled), then Refill enabled while a press gave a KiCad to ask
        (`handed`) and no refill goes on; and, with a project, a compare that ended (compared), then Compare the
        projects enabled while a variant is picked (`variant`) and no compare goes on."""
        self.started = [p for p in self.started if p.poll() is None]  # poll() reaps one that ended
        if self.pads_read is not None and self.pads_read.done():
            done, self.pads_read = self.pads_read, None
            self.show_pads(done)
        if self.creating is not None and self.creating.done():
            done, self.creating = self.creating, None
            self.created(done)
        if self.refilling is not None and self.refilling.done():
            done, self.refilling = self.refilling, None
            self.refilled(done)
        self.new_form.refill_button.setEnabled(self.handed is not None and self.refilling is None)
        if self.path is None:
            return
        if self.comparing is not None and self.comparing.done():
            done, self.comparing = self.comparing, None
            self.compared(done)
        self.comparison.compare_button.setEnabled(self.variant is not None and self.comparing is None)
        holder = runs.lock_holder(self.path)
        held = holder is not None and holder["alive"]  # any run's, a retune's included
        if holder and holder["run_dir"] and Path(holder["run_dir"]) == self.path.parent / "results":
            holder = None
        if holder and holder["run_dir"] and Path(holder["run_dir"]) != self.run_dir and (
                self.command is None or (holder["alive"] and (self.proc is None or not self.live))):
            self.watch("run", Path(holder["run_dir"]))
        if self.loading is not None and self.loading.done():
            done, self.loading = self.loading, None
            try:
                before, rows = self.opened, self.results.rows()
                self.opened = done.result()
                if self.mtime[1] is None:  # its board, now known: stamped alone, so a project.json saved since counts
                    # ponytail: a board saved during that first read is seen at its next save
                    self.mtime = (self.mtime[0], self.stamp()[1])
                self.show_project(self.opened)
                fresh = self.results.rows()
                kept, lost = control.carried(before and before.project, self.opened.project, self.path.parent, rows,
                                             fresh)
                if kept != fresh:  # the unapplied rows, computed again on the new read's layout
                    self.results.show_rows(kept)
                    self.retune()
                if lost:
                    self.results.retune_status.setText(render("G_DROPPED"))
            except Exception as e:  # a display that fails: this tick goes on, and so do the next ones
                self.project_status.setText(control.text("E_INTERNAL", {"detail": detail(e)}))
        if self.applying is not None and self.applying.done():
            done, self.applying = self.applying, None
            self.applied(done)
        self.live = False
        if self.command:
            # polled before the tail is read, so an exit seen here has its end event read already
            returncode = None if self.proc is None else self.proc.poll()
            for event in control.latest(self.tail.read()):
                self.show_event(event)
            code, params = control.run_state(self.run_dir, self.end, holder, self.proc is not None, returncode)
            (self.cost_status if self.command == "cost" else self.run_status).setText(render(code, **params))
            self.live = code == "G_RUNNING"
        if holder and holder["alive"] and holder["run_dir"] and self.proc is None:
            self.banner.setText(control.text("E_LOCKED", {"lock": str(runs.lock_file(self.path)),
                                                          "run": holder["run_dir"], "started": holder["started"]}))
            self.banner.show()
        else:
            self.banner.hide()
        if self.stamp() != self.mtime:
            self.load()
        idle = self.loading is None and self.applying is None
        self.cost_button.setEnabled(not (self.live or held))
        self.run_button.setEnabled(not (self.live or held) and self.cost is not None and self.applying is None)
        self.stop_button.setEnabled(self.live)
        self.results.retune_box.setEnabled(idle)  # r2: the last read's layout may be a gone model's
        ready = idle and not (self.live or held) and self.opened is not None and self.opened.results is not None
        for widget in (self.results.apply_button, self.results.verify_button):
            widget.setEnabled(ready)
        self.advanced.table.setEnabled(not held)
        self.advanced.save_button.setEnabled(idle and not held and bool(self.advanced.edits))

    def show_event(self, event: dict) -> None:
        """One event of the watched folder: an end sets `end` and is never listed, and a cost that ended with exit
        code 0 reads the project again, which finds that cost as the model's (control.last_cost) off the GUI thread;
        so does the end of a verify this window started, since verify writes its result events after it saves
        project.json, which the read that save started may miss. Under a cost every other event is a line of the Cost
        tab; under a run or a verify a progress fills its job's row, and every other event is a line of the log, a
        job's verdict also filling its row's port and verdict cells."""
        kind, job, params = event["kind"], event["job"], event["params"]
        if kind == "end":
            self.end = event
            if self.command == "verify" or (self.command == "cost" and params["exit_code"] == 0):
                self.load()
            return
        line = control.text(event["code"], params)
        if self.command == "cost":
            self.cost_lines.addItem(line)
        elif kind == "progress":
            self.fill(job, dict(enumerate(params[name] for name in PROGRESS)))
        else:
            self.log.addItem(line)
            if kind == "verdict" and job:  # a job k ≥ 1; None is the model's gates, 0 the setup's
                self.fill(job, {0: params["port"], COLUMNS.index("G_COL_VERDICT"): line})

    def fill(self, job: int, cells: dict[int, str]) -> None:
        """Job `job`'s row of the table, job − 1, added as needed, with the text of each column in `cells`."""
        self.jobs.setRowCount(max(self.jobs.rowCount(), job))
        for column, text in cells.items():
            self.jobs.setItem(job - 1, column, QTableWidgetItem(text))

    def watch(self, command: str, run_dir: Path, proc: subprocess.Popen | None = None) -> None:
        """Watches `command`'s run folder `run_dir`, and `proc` when this window started it: that command's views
        cleared and its tab selected."""
        self.command, self.run_dir, self.end, self.proc = command, run_dir, None, proc
        self.live = proc is not None  # the tick that start() runs counts the process it just started as live
        self.tail = control.Tail(run_dir / "events.jsonl")
        if command == "cost":
            self.cost_lines.clear()
        else:
            self.jobs.setRowCount(0)
            self.log.clear()
        self.tabs.setCurrentIndex(1 if command == "cost" else 2)

    def start(self, command: str) -> None:
        """Starts `command` (cost, run or verify) on the project as a detached orchestrator in a new run folder and
        watches it; a program that cannot start is G_START_FAILED in that command's status, and nothing starts."""
        run_dir = runs.run_dir_for(self.path.parent.name)
        try:
            proc = control.start(self.prefix, command, self.path, run_dir)
        except OSError as e:
            (self.cost_status if command == "cost" else self.run_status).setText(
                render("G_START_FAILED", program=self.prefix[0], reason=reason(e, "T_CANNOT_START")))
            return
        self.started.append(proc)
        self.watch(command, run_dir, proc)
        self.tick()

    def estimate(self) -> None:
        """Estimate the cost: starts cost."""
        self.start("cost")

    def run(self) -> None:
        """Run…: asks to start the run, showing the cost lines of `cost`'s folder, an SI project's without its 2D table
        (TABLE_2D, which stays in the Cost tab), and starts it on Yes. The project is bound before the question, as
        refill binds its press: when another project opened while the question was open (a later start's request), Yes
        starts nothing."""
        path = self.path
        table = TABLE_2D if si(self.opened.project) else ()
        lines = [control.text(e["code"], e["params"]) for e in control.Tail(self.cost / "events.jsonl").read()
                 if e["kind"] == "cost" and e["code"] not in table]
        if self.ask("\n".join([render("G_CONFIRM_RUN"), "", *lines])) and self.path == path:
            self.start("run")

    def ask(self, text: str, title: str = "G_CONFIRM_TITLE") -> bool:
        """Whether the user answers Yes to `text`, in a box titled with `title`'s text; tests replace it on the
        instance, or QMessageBox.question so that it runs (a modal dialog would block). No is the default button, so
        Enter or Space never starts a run, an Apply or KiCad's save (design 5.5: the save writes every edit KiCad
        holds)."""
        return QMessageBox.question(self, render(title), text,
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def stop(self) -> None:
        """Stop: an empty STOP file in the watched run folder, which stops the run as Ctrl+C does."""
        (self.run_dir / "STOP").touch()

    def show_project(self, opened: control.Opened) -> None:
        """A project read: an SI retune going on dropped (`retuning` None), its rows' read being gone; its line
        (G_PROJECT, an antenna's G_PROJECT_ANTENNA with its antenna and band, an SI project's G_PROJECT_SI with its
        interface, named as New's combo names it, its target and its first line's ends), or its refusal when there is
        no project, and its cost; while nothing is watched and the project has no lock, its newest run or verify that
        ended (opened.last) is watched, which replays it. Unless a cost is watched, live or ended, the Cost tab replays
        the last cost of this model (G_COST_REUSED), or says there is none (G_NO_COST). Last, the Results tab shows the
        read (ResultsView) and its stale indicator (show_stale), and Advanced project.json as stored (AdvancedView),
        which drops unsaved edits."""
        self.retuning = None
        p = opened.project
        if p is None:
            line = control.text(*opened.problem)
        elif antenna(p):
            band = p["band"]
            line = render("G_PROJECT_ANTENNA", path=str(self.path), ref=p["antenna"]["ref"],
                          f_lo_mhz=f"{band['f_lo_hz'] / 1e6:g}", f_hi_mhz=f"{band['f_hi_hz'] / 1e6:g}", preset=p["preset"])
        elif si(p):
            chain = p["lines"][0]["chain"]  # the first line: New's start and end
            # a preset by its name, custom by its label, as New's combo lists them
            interface = render("G_INTERFACE_CUSTOM") if p["interface"] == "custom" else p["interface"]
            line = render("G_PROJECT_SI", path=str(self.path), interface=interface, target=f"{p['target_ohm']:g}",
                          start=chain["start"], end=chain["end"], preset=p["preset"])
        else:
            line = render("G_PROJECT", path=str(self.path), f0_mhz=f"{p['f0_hz'] / 1e6:g}", harmonics=p["harmonics"],
                          preset=p["preset"])
        self.project_status.setText(line)
        self.cost = opened.cost
        if self.command is None and opened.last and runs.lock_holder(self.path) is None:
            self.watch("run", opened.last)
        if self.command != "cost":
            # ponytail: a cost still running when the window opened is not re-attached (cost takes no lock), and a
            # second one may start beside it; a lock for cost if that matters
            self.cost_lines.clear()
            if self.cost is None:
                self.cost_status.setText(render("G_NO_COST"))
            else:
                self.cost_lines.addItems([control.text(e["code"], e["params"]) for e in
                                          control.Tail(self.cost / "events.jsonl").read() if e["kind"] != "end"])
                self.cost_status.setText(render("G_COST_REUSED", folder=self.cost.name))
        self.results.display(opened, self.path.parent)
        self.show_stale()
        self.advanced.display(opened.stored)

    def retune(self) -> None:
        """A row edited (results.edited): the retune's status line cleared, then the chain of the table's rows on the
        last read's layout (control.retuned, which never raises; an antenna's lines on the far field and its layout that
        the read holds, Opened.far and far_lay), shown under the what-if label (show_chain), and the stale indicator of
        those rows (show_stale). An SI project's retune (Stage 4 design 5.10), some 70 ms of scikit-rf, more than Stage
        2's 50 ms (design 2 goal 4), is only submitted here: to the tuner, as `retuning`, the older one cancelled (an
        older edit's, never shown, dropped if not begun), with tune_timer started, whose take_retune shows it."""
        # ponytail: an SI retune queued behind an older one waits for it (about 70 ms each); a coalescing queue if fast
        # typing lags
        self.results.retune_status.clear()
        args = (self.path, self.opened.project, self.opened.results, self.results.rows(), self.opened.far,
                self.opened.far_lay)
        if si(self.opened.project):
            if self.retuning is not None:
                self.retuning.cancel()
            self.retuning = self.tuner.submit(control.retuned, *args)
            self.tune_timer.start()
        else:
            self.results.show_chain(control.retuned(*args), self.path.parent.name)
        self.show_stale()

    def take_retune(self) -> None:
        """The tuner's end, polled every TUNE_MS while an SI retune goes on (tune_timer): once the latest (`retuning`)
        ended, its chain shown (show_chain: moved in place and blitted). An earlier one is never shown, as `retuning`
        names the latest, and open_project, show_project and revert drop the one in flight."""
        if self.retuning is not None and not self.retuning.done():
            return
        self.tune_timer.stop()
        if self.retuning is not None:
            done, self.retuning = self.retuning, None
            self.results.show_chain(done.result(), self.path.parent.name)

    def revert(self) -> None:
        """Revert: an SI retune going on dropped (`retuning` None), the retune's status line cleared, then the last read
        shown again (display): the rows at their stored values, drawn in full, with their stale indicator
        (show_stale)."""
        self.retuning = None
        self.results.retune_status.clear()
        self.results.display(self.opened, self.path.parent)
        self.show_stale()

    def show_stale(self) -> None:
        """The stale indicator (design 5.3): control.verify_stale of the last read's project with the table's rows,
        None without rows; its code's text in `stale`, which shows only with a code."""
        rows = self.results.rows()
        code = control.verify_stale(self.opened.project, rows) if rows else None
        self.results.stale.setText("" if code is None else render(code))
        self.results.stale.setVisible(code is not None)

    def changes(self) -> list[str]:
        """retune's assignments for the table's rows that differ from the last read's project.json (control.changed);
        [] without rows, without a read or without its project."""
        rows, opened = self.results.rows(), self.opened
        if not rows or opened is None or opened.project is None:
            return []
        return control.changed(opened.project, self.path.parent, rows)

    def apply(self) -> None:
        """Apply: retune run to its end on the pool with the changed rows (control.apply, as `applying`), G_APPLYING in
        the retune's status line, then a tick, which disables the retune box until Apply's re-read. With no changes,
        retune writes the outputs alone (C-19), which a run's E_RESULTS_WRITE advises."""
        self.applying = self.pool.submit(control.apply, self.prefix, self.path, self.changes())
        self.results.retune_status.setText(render("G_APPLYING"))
        self.tick()

    def applied(self, done: Future) -> None:
        """Apply's end (`done`, control.apply) in the retune's status line: G_APPLIED on exit code 0, else retune's own
        lines; a program that cannot start (an OSError) G_START_FAILED, and any other exception control.message's
        line, the exception taken as show_pads takes it. On exit code 0 after Verify's Yes (`verify_next`, which this
        takes back first), verify starts on the values Apply stored; any other end starts nothing. project.json's new
        stamp reads the project again (tick)."""
        then, self.verify_next = self.verify_next, False
        status, error = self.results.retune_status, done.exception()
        if isinstance(error, OSError):
            status.setText(render("G_START_FAILED", program=self.prefix[0], reason=reason(error, "T_CANNOT_START")))
        elif error is not None:
            status.setText(control.message(error))
        else:
            code, lines = done.result()
            # ponytail: retune prints rendered lines, not codes, so its refusals read in the CLI's words (E_LOCKED's
            # STOP); retune writing events would let the window word them
            status.setText(render("G_APPLIED", folder=str(self.path.parent / "results")) if code == 0
                           else "\n".join(lines))
            if code == 0 and then:
                self.start("verify")

    def verify(self) -> None:
        """Verify: with changes not applied (changes), asks G_APPLY_FIRST, and Yes applies them, after which an exit-0
        Apply starts verify (`verify_next`, applied), while No does nothing; without changes, starts verify on the
        stored values. No cost confirmation of its own (design 5.3): its cost lines show live in the Run tab, with
        Stop. The project is bound before the question, as refill binds its press: when another project opened while
        the question was open (a later start's request), Yes applies nothing."""
        path = self.path
        if not self.changes():
            self.start("verify")
        elif self.ask(render("G_APPLY_FIRST")) and self.path == path:
            self.verify_next = True
            self.apply()

    def pick_variant(self) -> None:
        """Compare's Variant…: the project file picked in the dialog, a folder standing for its project.json, resolved,
        kept as `variant` and shown; nothing on Cancel. The next tick enables Compare the projects."""
        name, _ = QFileDialog.getOpenFileName(self, render("G_COMPARE_VARIANT"), "", render("G_OPEN_FILTER"))
        if name:
            self.variant = pipeline.project_path(name).resolve()
            self.comparison.variant.setText(str(self.variant))

    def compare_variant(self) -> None:
        """Compare the projects: the project against `variant` on the pool (control.compare, as `comparing`), which
        writes into the project's own folder, never the variant's; G_COMPARING in Compare's status line, then a tick,
        which disables the button until it ends (compared)."""
        self.comparing = self.pool.submit(control.compare, self.path, self.variant)
        self.comparison.status.setText(render("G_COMPARING"))
        self.tick()

    def compared(self, done: Future) -> None:
        """Compare's end (`done`, control.compare): a refusal (compare_projects', else E_INTERNAL) in Compare's status
        line in the window's words (control.message), the view emptied and the exception taken as show_pads takes it;
        else the status line cleared and compare's lines in the window's words (control.text) with its cells and, on
        exit code 0, compare.png from the project's compare folder (control.COMPARE_FOLDER). On 2, a file it could
        not write, there are no cells and no picture, so no stale table or picture shows."""
        view, error = self.comparison, done.exception()
        if error is not None:
            view.status.setText(control.message(error))
            view.display([], [], None)
            return
        code, lines, cells = done.result()
        view.status.clear()
        view.display([control.text(c, p) for c, p in lines], cells,
                     self.path.parent / control.COMPARE_FOLDER / "compare.png" if code == 0 else None)

    def save(self) -> None:
        """Advanced's Save: under the project lock, results/ its run folder as a retune's, project.json read afresh
        (load_project), as run, verify and retune read it, so a save never writes back a stale snapshot and no engine
        writer runs meanwhile; the edits applied to it (control.edited), checked (check_project) and written
        (save_project). Then I_WROTE in Advanced's status line and a tick, whose stamp check reads the project again,
        which marks the results stale when the model changed. An OSError shows G_SAVE_FAILED, and any other exception
        control.message's line (E_LOCKED as G_LOCKED, E_PROJECT_FIELD as G_PROJECT_FIELD); nothing is written then."""
        status = self.advanced.status
        try:
            with runs.project_lock(self.path, self.path.parent / "results"):
                data = control.edited(load_project(self.path), self.advanced.edits)
                save_project(self.path, check_project(data, self.path))
        except OSError as e:
            status.setText(render("G_SAVE_FAILED", path=str(self.path), reason=reason(e, "T_CANNOT_WRITE")))
            return
        except Exception as e:
            status.setText(control.message(e))
            return
        status.setText(render("I_WROTE", path=self.path))
        self.tick()

    def pick_board(self) -> None:
        """New's board Browse…: the board file picked in the dialog, then board_chosen(); nothing on Cancel."""
        name, _ = QFileDialog.getOpenFileName(self, render("G_NEW_BOARD"), "", render("G_BOARD_FILTER"))
        if name:
            self.new_form.board.setText(name)
            self.board_chosen()

    def board_chosen(self) -> None:
        """A board picked, or typed and left (the board field's editingFinished): for a board text, stripped, that is
        not the one whose pads were last read (`chosen`), the project folder beside it, named after it (the README's
        `-o lpf915`), and its pads and antennas read on the pool (control.board_choices, as `pads_read`). The same
        board again keeps a folder the user typed, unless its read was refused (show_pads then clears `chosen`)."""
        f = self.new_form
        text = f.board.text().strip()
        if text and text != f.chosen:
            f.chosen = text
            f.folder.setText(str(Path(text).with_suffix("")))
            self.pads_read = self.pool.submit(control.board_choices, Path(text))

    def take_handoff(self, path: Path) -> None:
        """A press of the KiCad button, in the handoff file `path` (Stage 2 design 5.3, 5.5; Stage 3 and Stage 4 design
        5.10): kept as `handoff`, the Project tab shown and New's status line cleared, unless a refill goes on
        (`refilling`), whose G_REFILLING stays; then the press read on the pool (control.handed) as New's read,
        `pads_read`, which show_pads shows: a matching chain's start and end; for a selected printed antenna, the
        antenna kind with that antenna and its start; or, for a selected track, arc or via, the SI kind with an
        interface that fits its line, its pair's mode and its two end pads. It replaces a read in flight, so a slower
        read of another board never overwrites it, and a board picked after the press wins over it."""
        self.handoff = path
        self.tabs.setCurrentIndex(0)  # the Project tab, New's
        if self.refilling is None:
            self.new_form.status.clear()
        self.pads_read = self.pool.submit(control.handed, path)

    def pick_folder(self) -> None:
        """New's project folder Browse…: the folder picked in the dialog; nothing on Cancel."""
        name = QFileDialog.getExistingDirectory(self, render("G_NEW_FOLDER"))
        if name:
            self.new_form.folder.setText(name)

    def create_project(self) -> None:
        """Create the project: f0 read here, on the GUI thread, then new on the pool with the form's fields, the board
        and the folder stripped (`creating`), the status line saying so and Create disabled until it ends (created). A
        frequency that does not read, or no project folder (new's own default, the working folder, means nothing to a
        GUI), goes to the status line, and nothing starts. The antenna kind (Stage 3 design 5.10) takes the antenna
        footprint picked and the band, a preset's or Custom's text read here (parse_band), in place of the end, f0 and
        the harmonics, and calls new_antenna with the same board, start, options and folder. No antenna picked starts
        nothing: G_NO_ANTENNA in the status line after a read that succeeded (`chosen` set and no `pads_read`
        pending), else the status line as it is (a refused read's refusal, or a read going on, whose end fills the
        combo); then a band that does not read goes to the status line, before the folder's check. The SI kind (Stage 4
        design 5.10) takes the end, the interface, Custom's f_max, read here (parse_frequency), and its target, the
        pair's mode, the partner's two end pads when picked here and each victim whose two end pads are picked, and
        calls new_si with the same board, start, options and folder: a victim with one end pad only, or a partner
        picked with an end pad empty, puts G_SI_ENDS_HALF in the status line before the folder's check, and nothing
        starts; new_si's refusals (a pair's interface without its partner, a net's with one, a partner the rule cannot
        find, two lines on one net) come back as new's do, in the window's words (control.GUI)."""
        f = self.new_form
        kind = f.kind.currentData()
        if kind == "antenna" and f.antenna.currentData() is None:
            if f.chosen and self.pads_read is None:  # a read that succeeded found no printed antenna
                f.status.setText(render("G_NO_ANTENNA"))
            return
        custom = f.interface.currentData() == "custom"
        try:
            if kind == "antenna":
                band = f.band.currentData() or parse_band(f.band_text.text())
            elif kind == "si":
                f_max = parse_frequency(f.f_max.text()) if custom else None
            else:
                f0 = parse_frequency(f.f0.text())
        except KrsError as e:
            f.status.setText(control.message(e))
            return
        if kind == "si":
            mode = f.pair.currentData()
            victims = [tuple(box.currentText().strip() for box in row) for row in f.victims]
            pair_with = tuple(box.currentText().strip() for box in f.pair_with) if mode == "given" else None
            if any(any(v) and not all(v) for v in victims) or pair_with and not all(pair_with):
                f.status.setText(render("G_SI_ENDS_HALF"))
                return
        if not f.folder.text().strip():
            f.status.setText(render("G_NEW_NO_FOLDER"))
            return
        f.status.setText(render("G_CREATING"))
        f.create_button.setEnabled(False)
        board, start = f.board.text().strip(), f.start.currentText().strip()
        options = {"preset": f.preset.currentText(), "stackup": f.stackup.currentData(),
                   "lid_height": f.lid.value() or None,  # a lid height of 0: none, new's default
                   "output": f.folder.text().strip()}
        if kind == "antenna":
            self.creating = self.pool.submit(cli.new_antenna, board, start, f.antenna.currentData(), band, **options)
        elif kind == "si":
            self.creating = self.pool.submit(cli.new_si, board, start, f.end.currentText().strip(),
                                             f.interface.currentData(), pair=mode == "rule", pair_with=pair_with,
                                             victims=[v for v in victims if all(v)], f_max=f_max,
                                             target=f.target.value() if custom else None, **options)
        else:
            self.creating = self.pool.submit(cli.new, board, start, f.end.currentText().strip(), f0,
                                             harmonics=f.harmonics.value(), **options)

    def show_pads(self, done: Future) -> None:
        """New's read (`done`): the board's pads and antennas (control.board_choices), the pads in every pad picker
        (start, end, the partner's two and the victims' four), none picked for the user, and the antennas in the
        footprint combo (NewForm.show_antennas); or a press (control.handed), kept as `handed`: its kind in New's Kind;
        for an SI press that names a line (`net`), the Interface fitted to it, se50, the one single-ended preset, for a
        net with no partner under a pair's preset, usb2-hs, New's default, for a pair under se50, Custom kept, then the
        Pair's mode by KiCad's rule with a partner, else none (one that names no line leaves both); its board's antennas
        in the footprint combo with its antenna picked, its board in the board field and as `chosen` ("" when the press
        has no pads, a refusal, so that the board, fixed and picked again, is read again), the project folder beside it
        as board_chosen sets it, and kept, as there, when the board is `chosen` already, its pads in the pickers with
        its start and end picked and none other, and its problem in the status line, which is otherwise left as it is.
        On a refusal (load_board's, else E_INTERNAL), the pickers and the footprint combo left empty, the refusal in the
        status line and `chosen` cleared, so that the same board, fixed and picked again, is read again. The exception
        is taken, never raised again: its traceback would then hold this frame, and so the window, in a cycle with the
        Future that only the garbage collector frees, maybe on a pool thread (probed)."""
        f, error = self.new_form, done.exception()
        if error is not None:
            f.status.setText(control.message(error))
            f.chosen = ""
        read = ([], {}) if error is not None else done.result()
        start = end = ""
        if isinstance(read, control.Handed):
            self.handed, names, start, end = read, read.pads, read.start, read.end
            f.kind.setCurrentIndex(f.kind.findData(read.kind))
            if read.net:  # an SI press that names a line: an interface that can hold it, and its pair's mode
                preset = INTERFACES.get(f.interface.currentData())  # None for Custom, which is kept
                if preset and preset["pair"] != bool(read.partner):
                    f.interface.setCurrentIndex(f.interface.findData("usb2-hs" if read.partner else "se50"))
                f.pair.setCurrentIndex(f.pair.findData("rule" if read.partner else None))
            f.show_antennas(read.kinds, read.antenna)
            f.board.setText(str(read.board))
            if str(read.board) != f.chosen:
                f.folder.setText(str(read.board.with_suffix("")))
            f.chosen = str(read.board) if read.pads else ""
            if read.problem:
                f.status.setText(control.text(*read.problem))
        else:
            names, kinds = read
            f.show_antennas(kinds)
        others = (*f.pair_with, *(box for row in f.victims for box in row))  # none picked, for the user
        for box, pick in ((f.start, start), (f.end, end), *((box, "") for box in others)):
            box.clear()
            box.addItems(names)
            box.setCurrentIndex(box.findText(pick))  # -1, none picked, for "": no pad's name is empty

    def refill(self) -> None:
        """Refill zones and save in KiCad (design 5.5 Refill, 7): asks G_REFILL_CONFIRM on the board of the last press
        shown (`handed`), under the title G_REFILL. That press is bound before the question: the box is modal, but its
        event loop runs the tick and the local server, so a press can land while it is open and change `handed`, never
        the board confirmed. No sends nothing to KiCad. Yes: button.refill in that press's KiCad on the pool
        (`refilling`), G_REFILLING in New's status line and Refill disabled at once, until its end (refilled)."""
        # ponytail: the pool's one thread waits for the refill (seconds; FILL_WAIT_S at most), so a press or a project
        # read meanwhile waits too; a second executor for KiCad's calls if users meet it
        h = self.handed
        if not self.ask(render("G_REFILL_CONFIRM", board=str(h.board)), "G_REFILL"):
            return
        self.refilling = self.pool.submit(button.refill, h.socket, h.token, h.board)
        self.new_form.status.setText(render("G_REFILLING"))
        self.new_form.refill_button.setEnabled(False)

    def refilled(self, done: Future) -> None:
        """Refill's end (`done`, button.refill): a refusal (button.refill's, else E_INTERNAL) in New's status line, the
        exception taken as show_pads takes it. Else G_REFILLED there, and the press read again on the pool
        (control.handed, as `pads_read`), so that what the save wrote pre-fills New, its status line left as it is
        unless that read has a problem. An open project of that board reads itself again through the tick's board
        stamp."""
        f, error = self.new_form, done.exception()
        if error is not None:
            f.status.setText(control.message(error))
            return
        f.status.setText(render("G_REFILLED", board=str(done.result())))
        self.pads_read = self.pool.submit(control.handed, self.handoff)

    def created(self, done: Future) -> None:
        """new's end (`done`): Create enabled again and the last New's notes cleared; on success the status line
        cleared, new's notes listed in the window's words and the project it wrote opened; on a refusal (new's, else
        E_INTERNAL), the refusal in the status line, the exception taken as show_pads takes it."""
        f, error = self.new_form, done.exception()
        f.create_button.setEnabled(True)
        f.notes.clear()
        if error is not None:
            f.status.setText(control.message(error))
            return
        path, notes = done.result()
        f.status.clear()
        f.notes.addItems([control.text(code, params) for code, params in notes])
        self.open_project(path)

    def about(self) -> None:
        """Help's About: the version, the licence notices and the runtime dependencies (control.about)."""
        QMessageBox.about(self, render("G_ABOUT"), control.about())

    def about_qt(self) -> None:
        """Help's About Qt: Qt's own box, with Qt's version and licence."""
        QMessageBox.aboutQt(self)

    def serve(self, server: QLocalServer, lock: QLockFile) -> None:
        """One window per user (gui.main, design 5.5): keeps `server`, through which a later start's request comes
        (incoming), and `lock`, gui.lock, until the window closes."""
        self.server, self.lock = server, lock
        server.setParent(self)
        server.newConnection.connect(self.incoming)

    def incoming(self) -> None:
        """The server's newConnection: each pending connection's lines taken as they come (forwarded), and the
        connection deleted once its start disconnects."""
        while (sock := self.server.nextPendingConnection()) is not None:
            sock.readyRead.connect(self.forwarded)
            sock.disconnected.connect(sock.deleteLater)

    def forwarded(self) -> None:
        """A connection's readyRead: each complete line, a later start's request (gui.forward), acted on."""
        sock = self.sender()
        while sock.canReadLine():
            self.act(json.loads(bytes(sock.readLine())))  # a QByteArray is not JSON input (TypeError)

    def act(self, request: dict) -> None:
        """A start's request (gui.main), this one's or a later one's (forwarded): the window shown, unminimized, raised
        and activated; then the press taken when it names a handoff file, else the project opened when it names one."""
        # ponytail: Windows' foreground lock may flash the taskbar button instead of raising the window, unless the
        # helper's AllowSetForegroundWindow reached it; the click-through checks
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.raise_()
        self.activateWindow()
        if request["handoff"]:
            self.take_handoff(Path(request["handoff"]))
        elif request["project"]:
            self.open_project(Path(request["project"]))

    def closeEvent(self, event: QCloseEvent) -> None:
        """Closing the window first closes its server and unlocks gui.lock (serve), so that a later start serves itself
        instead of waiting on a closing window whose pool may still run; it then stops its timers and drops the work
        not yet begun of its pool (project reads, a pad list, a New, an Apply, a compare, a refill) and of its tuner (an
        SI retune); what it started goes on (design 5.1: a run outlives its window, and the next window re-attaches it),
        an Apply's retune included, and so does a refill already begun, which ends when KiCad answers, within
        FILL_WAIT_S, as an Apply's retune does."""
        if self.server is not None:  # serve keeps both
            self.server.close()
            self.lock.unlock()
        self.timer.stop()
        self.tune_timer.stop()
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.tuner.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)
