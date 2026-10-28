# SPDX-License-Identifier: GPL-3.0-or-later
"""The main window (Stage 2 design 5.1, 5.3, 5.4): it creates a project from a board (NewForm) or opens one, shows its
cost, starts, follows and stops a run, its own or one it re-attaches through the project lock, replays the project's
last run and shows its results, which its parts' rows retune in this process (ResultsView), Apply stores through the
CLI's retune and Verify checks; Advanced edits project.json's fields and saves them under the project lock
(AdvancedView); all driven by one 500 ms timer (`tick`). The project is read, a board's pads listed, new run and retune
waited for on a pool thread (control.open_project, control.pads, cli.new, control.apply); cost, run and verify start as
a detached orchestrator (control.start), so this process never reaches runs.run_jobs. Its Help menu shows About
(control.about) and Qt's About."""
import json
import subprocess
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QLocale, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)
# after PySide6: matplotlib's Qt backend then wraps the binding already loaded, never another one installed beside it
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from kicad_rf_studio import cli, pipeline, runs
from kicad_rf_studio.core.kicad.stackup import PRESETS as STACKUPS
from kicad_rf_studio.core.kicad.values import parse_frequency
from kicad_rf_studio.core.messages import KrsError, detail, reason, render
from kicad_rf_studio.core.post.outputs import LIMITS, draw_summary, retrace_summary
from kicad_rf_studio.core.project import DEFAULT_PRESET, HARMONICS, check_project, load_project, save_project
from kicad_rf_studio.gui import control

COLUMNS = ("G_COL_PORT", "G_COL_TIME", "G_COL_RESIDUAL", "G_COL_SPEED", "G_COL_VERDICT")
PROGRESS = ("port", "t_ns", "residual_db", "speed_mcs")  # a progress event's params, in the first four columns
PART, VALUE, SNAP, S2P, FIXTURE = range(5)  # the parts table's columns
PART_COLUMNS = ("G_COL_PART", "G_COL_VALUE", "G_COL_SNAP", "G_COL_S2P", "G_COL_FIXTURE")
FIELD_COLUMNS = ("G_COL_FIELD", "G_COL_VALUE", "G_COL_DEFAULT", "G_COL_UNIT")  # Advanced's table; Value alone edited
SNAPPING = tuple(zip(control.SERIES, ("G_SNAP_OFF", "G_SNAP_E12", "G_SNAP_E24")))  # a Snapping combo's (data, code)
FIXTURES = (("series", "G_FIXTURE_SERIES"), ("shunt", "G_FIXTURE_SHUNT"))  # an S2P fixture combo's (data, code)


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


def combo(choices: tuple, current: str, slot) -> QComboBox:
    """A table cell's combo box of `choices`, (data, code) pairs shown as their code's text, `current`'s selected and
    only then its currentIndexChanged connected to `slot`, so that filling it emits nothing."""
    box = QComboBox()
    for data, code in choices:
        box.addItem(render(code), data)
    box.setCurrentIndex(box.findData(current))
    box.currentIndexChanged.connect(slot)
    return box


class ResultsView(QWidget):
    """The Results and retune tab (Stage 2 design 5.3, 5.4): the row (`header`) of the what-if label while
    RETUNE_VALIDATED is False, the stale indicator (`stale`, which the window sets) and Verify, the last two only with
    part ports; why there are no results; the retune box, shown only with part ports: the parts table (`parts`), a row
    per part port with its value, its Snapping, its S2P file and that file's fixture, then the row (`buttons`) of S2P
    file…, Revert, Apply and the retune's status line; summary.png's drawing on a FigureCanvasQTAgg; and the row
    (`footer`) of the result's lines and stated limits, then the last verify's comparison (`verify_lines`), shown only
    with part ports. `series` holds each part's Snapping as the user set it. A row's edit emits `edited`; the window
    answers it with the chain of the rows (show_chain). The plot: its `axes` as draw_summary drew them (None without a
    plot, or to draw the next one in full) and its `curves`, animated, which a retune moves and blits (retrace_summary,
    blit) on the background (`bg`) that the last full draw kept (on_draw), None until one."""

    edited = Signal()

    def __init__(self):
        super().__init__()
        self.what_if, self.problem, self.lines = QLabel(control.text("I_WHAT_IF", {})), QLabel(), QListWidget()
        self.stale, self.verify_button, self.verify_lines = QLabel(), QPushButton(render("G_VERIFY")), QListWidget()
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
        """Shows the project read `opened` of the project folder `folder` (None for none): the problem's line only
        with one; the rows of the results' part ports as project.json stores them (control.rows, S2P files against
        `folder`), none without part ports, and only with them Verify and the last verify's comparison
        (opened.verified); then the results' chain (show_chain), under the folder's name, drawn in full (`axes` None):
        a read, Revert and the re-read after Apply. Never touches retune_status or the stale indicator."""
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
        part's series as the user set it (`series`), else its default (control.default_series); S2P fixture the row's
        connection. The retune box shows only with rows."""
        with QSignalBlocker(self.parts):
            self.parts.setRowCount(len(rows))
            for k, row in enumerate(rows):
                part = QTableWidgetItem(row.ref)
                part.setFlags(part.flags() & ~Qt.ItemFlag.ItemIsEditable)
                for column, item in ((PART, part), (VALUE, QTableWidgetItem(row.value)),
                                     (S2P, QTableWidgetItem(row.s2p))):
                    self.parts.setItem(k, column, item)
                series = self.series.get(row.ref, control.default_series(row.ref))
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
        not, their lines, then LIMITS (C-32). With a chain closed on 2 external ports and the plot drawn (`axes`), its
        curves moved in place (retrace_summary) and blitted (blit). Otherwise the figure cleared, then, with such a
        chain, summary.png's plots (draw_summary) with the label as their title's second line, their curves (`curves`)
        animated, which a full draw leaves to on_draw; Qt redraws the canvas once its event loop runs (draw_idle)."""
        # ponytail: the curves keep the limits of the last full draw (the stored values', or the first good values after
        # a refusal); a retune far off clips until Revert or Apply draws again
        fig = self.canvas.figure
        self.lines.clear()
        label = self.what_if.text() if res is not None and res.what_if else None
        self.what_if.setVisible(label is not None)
        if res is not None:
            self.lines.addItems([control.text(c, p) for c, p in res.lines] + [render(c) for c in LIMITS])
        plot = res is not None and res.chain is not None and len(res.ext) == 2
        if plot and self.axes is not None:
            retrace_summary(self.axes, res.lay, res.chain, res.ideal)
            self.blit()
            return
        fig.clear()
        self.axes, self.curves, self.bg = None, [], None
        if plot:
            self.axes = draw_summary(fig, res.lay, res.chain, res.ideal, name, label)
            self.curves = retrace_summary(self.axes, res.lay, res.chain, res.ideal)  # the data unchanged
            for curve in self.curves:
                curve.set_animated(True)
        self.canvas.draw_idle()

    def blit(self) -> None:
        """The curves drawn on the background that the last full draw kept (`bg`), then the figure copied to the screen
        (canvas.blit); without a background, the canvas drawn in full, whose draw_event keeps one (on_draw)."""
        # ponytail: a status line that changes height (G_APPLIED cleared, the stale indicator lit) resizes the canvas,
        # which Qt then redraws once in full; fixed-height status lines if that is felt
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
    """New from a board (Stage 2 design 5.3): the board and the project folder, each with its Browse…; the start and
    end pads, picked from the board's pads or typed; f0; new's options at new's defaults (the board's own stackup, and
    a lid height of 0 for none); Create, its status line and new's notes. `chosen` is the board text whose pads were
    last read."""

    def __init__(self):
        super().__init__(render("G_NEW"))
        self.board, self.board_button = QLineEdit(), QPushButton(render("G_BROWSE"))
        self.start, self.end, self.f0 = QComboBox(editable=True), QComboBox(editable=True), QLineEdit()
        self.harmonics = QSpinBox(minimum=1, maximum=99, value=HARMONICS)
        self.preset, self.stackup = QComboBox(), QComboBox()
        self.preset.addItems(cli.PRESETS)
        self.preset.setCurrentText(DEFAULT_PRESET)
        self.stackup.addItem(render("G_STACKUP_BOARD"), None)
        for name in STACKUPS:
            self.stackup.addItem(name, name)
        # the C locale: project.json and the CLI write 2.5, and the system's locale may show 2,50
        self.lid = QDoubleSpinBox(maximum=100, decimals=2, locale=QLocale.c(), specialValueText=render("G_NONE"))
        self.folder, self.folder_button = QLineEdit(), QPushButton(render("G_BROWSE"))
        self.create_button, self.status, self.notes = QPushButton(render("G_CREATE")), QLabel(), QListWidget()
        self.status.setWordWrap(True)  # a refusal names a path, which would otherwise widen the window
        self.chosen = ""
        form = QFormLayout(self)
        for code, field in (("G_NEW_BOARD", beside(self.board, self.board_button)), ("G_NEW_START", self.start),
                            ("G_NEW_END", self.end), ("G_NEW_F0", self.f0), ("G_NEW_HARMONICS", self.harmonics),
                            ("G_NEW_PRESET", self.preset), ("G_NEW_STACKUP", self.stackup), ("G_NEW_LID", self.lid),
                            ("G_NEW_FOLDER", beside(self.folder, self.folder_button))):
            form.addRow(render(code), field)
        for widget in (self.create_button, self.status, self.notes):
            form.addRow(widget)


class AdvancedView(QWidget):
    """The Advanced tab (Stage 2 design 5.3): project.json's fields (control.fields) in `table`, a row each with its
    name, its value as JSON, the one cell that can be edited, its default and its unit; then the row of Save
    (`save_button`, which the window enables) and its status line (`status`). `edits` holds the text of each edited
    value by its field's path, and `paths` each row's path."""

    def __init__(self):
        super().__init__()
        self.table, self.save_button = QTableWidget(0, len(FIELD_COLUMNS)), QPushButton(render("G_SAVE"))
        self.status, self.edits, self.paths = QLabel(), {}, []
        self.table.setHorizontalHeaderLabels([render(code) for code in FIELD_COLUMNS])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)  # a name, a default or a unit unclipped
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # the value: a list, or a path
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
        cleared. Never touches `status`."""
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

    def item_changed(self, item: QTableWidgetItem) -> None:
        """A value edited (itemChanged): its text kept in `edits` under its row's path."""
        self.edits[self.paths[item.row()]] = item.text()


class MainWindow(QMainWindow):
    """The main window; `prefix` is the command that starts the orchestrator (control.orchestrator() by default).
    Its state: `path`, the resolved project file; `opened`, its last read (control.Opened) and `loading`, the read
    going on (a Future); `applying`, Apply's retune going on (a Future), and `verify_next`, whether its end starts
    verify (Verify's Yes to G_APPLY_FIRST); `cost`, the folder of this model's last cost,
    which Run… confirms on; the watch: `command`, `run_dir`, its events' `tail`, its `end` event and `proc`, only a
    process this window started; `live`, whether the watched process goes on; `mtime`, project.json's and the board
    file's st_mtime_ns at the last read (stamp); `started`, every process this window started, polled every tick, so
    that none is left a zombie on Linux; and the New form's work going on (Futures): `pads_read`, the chosen board's
    pads, and `creating`, new.
    Every slot is a bound method: a lambda or partial slot would keep a closed window alive (probed on PySide6
    6.12)."""

    def __init__(self, prefix: list[str] | None = None):
        super().__init__()
        self.setWindowTitle(render("G_APP"))
        self.resize(1200, 800)
        self.prefix = prefix or control.orchestrator()
        self.path = self.opened = self.loading = self.applying = self.cost = self.mtime = None
        self.pads_read = self.creating = None
        self.command = self.run_dir = self.tail = self.end = self.proc = None
        self.live, self.started, self.verify_next = False, [], False
        self.pool = ThreadPoolExecutor(1)
        self.open_button, self.project_status, self.new_form = QPushButton(render("G_OPEN")), QLabel(), NewForm()
        self.cost_lines, self.cost_status = QListWidget(), QLabel()
        self.cost_button, self.run_button = QPushButton(render("G_COST")), QPushButton(render("G_RUN"))
        self.banner, self.jobs, self.log = QLabel(), QTableWidget(0, len(COLUMNS)), QListWidget()
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
        self.results, self.advanced = ResultsView(), AdvancedView()
        self.tabs.addTab(self.results, render("G_TAB_RESULTS"))
        self.tabs.addTab(self.advanced, render("G_TAB_ADVANCED"))
        self.setCentralWidget(self.tabs)
        menu = self.menuBar().addMenu(render("G_MENU_HELP"))
        self.about_action = menu.addAction(render("G_ABOUT"))
        self.about_qt_action = menu.addAction(render("G_ABOUT_QT"))
        self.about_action.triggered.connect(self.about)
        self.about_qt_action.triggered.connect(self.about_qt)
        form = self.new_form
        for button, slot in ((self.open_button, self.browse), (self.cost_button, self.estimate),
                             (self.run_button, self.run), (self.stop_button, self.stop),
                             (form.board_button, self.pick_board), (form.folder_button, self.pick_folder),
                             (form.create_button, self.create_project), (self.results.revert_button, self.revert),
                             (self.results.apply_button, self.apply), (self.results.verify_button, self.verify),
                             (self.advanced.save_button, self.save)):
            button.clicked.connect(slot)
        self.results.edited.connect(self.retune)
        form.board.editingFinished.connect(self.board_chosen)
        for button in (self.cost_button, self.run_button, self.stop_button, self.results.apply_button,
                       self.results.verify_button):  # no project
            button.setEnabled(False)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(500)

    def browse(self) -> None:
        """Open a project…: the project file picked in the dialog; nothing on Cancel."""
        name, _ = QFileDialog.getOpenFileName(self, render("G_OPEN"), "", render("G_OPEN_FILTER"))
        if name:
            self.open_project(Path(name))

    def open_project(self, path: Path) -> None:
        """Opens the project file `path`, a folder standing for its project.json: the views and the watch cleared,
        then its read and a tick. A process this window started goes on, no longer watched, and so does an Apply's
        retune of the previous project, which ends on the pool unread (`applying` None) and starts no verify
        (`verify_next` False)."""
        self.path = pipeline.project_path(str(path)).resolve()
        self.command = self.run_dir = self.tail = self.end = self.proc = self.cost = self.opened = self.applying = None
        self.verify_next = False
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
        project, New's pad list and new itself when done (show_pads, created, which opens the project new wrote, whose
        own tick runs inside this one)."""
        self.started = [p for p in self.started if p.poll() is None]  # poll() reaps one that ended
        if self.pads_read is not None and self.pads_read.done():
            done, self.pads_read = self.pads_read, None
            self.show_pads(done)
        if self.creating is not None and self.creating.done():
            done, self.creating = self.creating, None
            self.created(done)
        if self.path is None:
            return
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
        for button in (self.results.apply_button, self.results.verify_button):
            button.setEnabled(ready)
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
                render("G_START_FAILED", program=self.prefix[0], reason=reason(e)))
            return
        self.started.append(proc)
        self.watch(command, run_dir, proc)
        self.tick()

    def estimate(self) -> None:
        """Estimate the cost: starts cost."""
        self.start("cost")

    def run(self) -> None:
        """Run…: asks to start the run, showing the cost lines of `cost`'s folder, and starts it on Yes."""
        lines = [control.text(e["code"], e["params"]) for e in control.Tail(self.cost / "events.jsonl").read()
                 if e["kind"] == "cost"]
        if self.ask("\n".join([render("G_CONFIRM_RUN"), "", *lines])):
            self.start("run")

    def ask(self, text: str) -> bool:
        """Whether the user answers Yes to `text`; tests replace it on the instance (a modal dialog would block)."""
        return QMessageBox.question(self, render("G_CONFIRM_TITLE"), text) == QMessageBox.StandardButton.Yes

    def stop(self) -> None:
        """Stop: an empty STOP file in the watched run folder, which stops the run as Ctrl+C does."""
        (self.run_dir / "STOP").touch()

    def show_project(self, opened: control.Opened) -> None:
        """A project read: its line (G_PROJECT), or its refusal when there is no project, and its cost; while nothing
        is watched and the project has no lock, its newest run or verify that ended (opened.last) is watched, which
        replays it. Unless a cost is watched, live or ended, the Cost tab replays the last cost of this model
        (G_COST_REUSED), or says there is none (G_NO_COST). Last, the Results tab shows the read (ResultsView) and its
        stale indicator (show_stale), and Advanced project.json as stored (AdvancedView), which drops unsaved edits."""
        p = opened.project
        self.project_status.setText(control.text(*opened.problem) if p is None else render(
            "G_PROJECT", path=str(self.path), f0_mhz=f"{p['f0_hz'] / 1e6:g}", harmonics=p["harmonics"],
            preset=p["preset"]))
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
        last read's layout (control.retuned, which never raises), shown under the what-if label (show_chain), and the
        stale indicator of those rows (show_stale)."""
        self.results.retune_status.clear()
        self.results.show_chain(control.retuned(self.path, self.opened.project, self.opened.results,
                                                self.results.rows()), self.path.parent.name)
        self.show_stale()

    def revert(self) -> None:
        """Revert: the retune's status line cleared, then the last read shown again (display): the rows at their stored
        values, drawn in full, with their stale indicator (show_stale)."""
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
            status.setText(render("G_START_FAILED", program=self.prefix[0], reason=reason(error)))
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
        Stop."""
        if not self.changes():
            self.start("verify")
        elif self.ask(render("G_APPLY_FIRST")):
            self.verify_next = True
            self.apply()

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
            status.setText(render("G_SAVE_FAILED", path=str(self.path), reason=reason(e, "cannot be written")))
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
        `-o lpf915`), and its pads read on the pool (`pads_read`). The same board again keeps a folder the user
        typed."""
        f = self.new_form
        text = f.board.text().strip()
        if text and text != f.chosen:
            f.chosen = text
            f.folder.setText(str(Path(text).with_suffix("")))
            self.pads_read = self.pool.submit(control.pads, Path(text))

    def pick_folder(self) -> None:
        """New's project folder Browse…: the folder picked in the dialog; nothing on Cancel."""
        name = QFileDialog.getExistingDirectory(self, render("G_NEW_FOLDER"))
        if name:
            self.new_form.folder.setText(name)

    def create_project(self) -> None:
        """Create the project: f0 read here, on the GUI thread, then new on the pool with the form's fields
        (`creating`), the status line saying so and Create disabled until it ends (created). A frequency that does not
        read, or no project folder (new's own default, the working folder, means nothing to a GUI), goes to the status
        line, and nothing starts."""
        f = self.new_form
        try:
            f0 = parse_frequency(f.f0.text())
        except KrsError as e:
            f.status.setText(control.message(e))
            return
        if not f.folder.text().strip():
            f.status.setText(render("G_NEW_NO_FOLDER"))
            return
        f.status.setText(render("G_CREATING"))
        f.create_button.setEnabled(False)
        self.creating = self.pool.submit(
            cli.new, f.board.text(), f.start.currentText().strip(), f.end.currentText().strip(), f0,
            harmonics=f.harmonics.value(), preset=f.preset.currentText(), stackup=f.stackup.currentData(),
            lid_height=f.lid.value() or None, output=f.folder.text())  # a lid height of 0: none, new's default

    def show_pads(self, done: Future) -> None:
        """The board's pads (`done`, control.pads) in the start and end pickers, none picked for the user; on a
        refusal (load_board's, else E_INTERNAL), the pickers left empty and the refusal in the status line. The
        exception is taken, never raised again: its traceback would then hold this frame, and so the window, in a
        cycle with the Future that only the garbage collector frees, maybe on a pool thread (probed)."""
        f, error = self.new_form, done.exception()
        if error is not None:
            f.status.setText(control.message(error))
        for box in (f.start, f.end):
            box.clear()
            box.addItems([] if error is not None else done.result())
            box.setCurrentIndex(-1)

    def created(self, done: Future) -> None:
        """new's end (`done`): Create enabled again; on success the status line cleared, new's notes listed in the
        window's words and the project it wrote opened; on a refusal (new's, else E_INTERNAL), the refusal in the
        status line, the exception taken as show_pads takes it."""
        f, error = self.new_form, done.exception()
        f.create_button.setEnabled(True)
        if error is not None:
            f.status.setText(control.message(error))
            return
        path, notes = done.result()
        f.status.clear()
        f.notes.clear()
        f.notes.addItems([control.text(code, params) for code, params in notes])
        self.open_project(path)

    def about(self) -> None:
        """Help's About: the version, the licence notices and the runtime dependencies (control.about)."""
        QMessageBox.about(self, render("G_ABOUT"), control.about())

    def about_qt(self) -> None:
        """Help's About Qt: Qt's own box, with Qt's version and licence."""
        QMessageBox.aboutQt(self)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Closing the window stops its timer and drops the pool's work not yet begun (project reads, a pad list, a
        New, an Apply); what it started goes on (design 5.1: a run outlives its window, and the next window re-attaches
        it), an Apply's retune included."""
        self.timer.stop()
        self.pool.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)
