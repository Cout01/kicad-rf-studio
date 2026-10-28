# SPDX-License-Identifier: GPL-3.0-or-later
"""The main window (Stage 2 design 5.1, 5.3, 5.4): it creates a project from a board (NewForm) or opens one, shows its
cost, starts, follows and stops a run, its own or one it re-attaches through the project lock, replays the project's
last run and shows its results (ResultsView), driven by one 500 ms timer (`tick`). The project is read, a board's pads
listed and new run on a pool thread (control.open_project, control.pads, cli.new); cost and run start as a detached
orchestrator (control.start), so this process never reaches runs.run_jobs."""
import subprocess
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QLocale, Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QMainWindow, QMessageBox, QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)
# after PySide6: matplotlib's Qt backend then wraps the binding already loaded, never another one installed beside it
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from kicad_rf_studio import cli, pipeline, runs
from kicad_rf_studio.core.kicad.stackup import PRESETS as STACKUPS
from kicad_rf_studio.core.kicad.values import parse_frequency
from kicad_rf_studio.core.messages import KrsError, detail, reason, render
from kicad_rf_studio.core.post.outputs import LIMITS, draw_summary
from kicad_rf_studio.core.project import DEFAULT_PRESET, HARMONICS
from kicad_rf_studio.gui import control

COLUMNS = ("G_COL_PORT", "G_COL_TIME", "G_COL_RESIDUAL", "G_COL_SPEED", "G_COL_VERDICT")
PROGRESS = ("port", "t_ns", "residual_db", "speed_mcs")  # a progress event's params, in the first four columns


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
    """A form's field: `widgets` in a row."""
    layout = QHBoxLayout()
    for widget in widgets:
        layout.addWidget(widget)
    return layout


class ResultsView(QWidget):
    """The Results tab (Stage 2 design 5.3, 5.4): summary.png's drawing on a FigureCanvasQTAgg, the what-if label over
    it while RETUNE_VALIDATED is False, and the result's lines and stated limits; or why there is none."""

    def __init__(self):
        super().__init__()
        self.what_if, self.problem, self.lines = QLabel(control.text("I_WHAT_IF", {})), QLabel(), QListWidget()
        self.canvas = FigureCanvasQTAgg(Figure(layout="constrained"))
        for label in (self.what_if, self.problem):
            label.setWordWrap(True)  # its sentence, some 200 characters, would otherwise set the window's minimum width
            label.hide()  # until a read shows it
        layout = QVBoxLayout(self)
        for widget in (self.what_if, self.problem, self.canvas, self.lines):
            layout.addWidget(widget)

    def display(self, opened: control.Opened, name: str) -> None:
        """Shows the project read `opened`, `name` being the project folder's name, which summary.png's title shows:
        the figure and the lines cleared; the what-if label only when the results carry what_if, and the problem's
        line only with one; with results whose chain is closed on 2 external ports, summary.png's plots (draw_summary)
        with the label as their title's second line; with any results, plot or not, their lines, then LIMITS (C-32).
        Qt redraws the canvas once its event loop runs (draw_idle)."""
        res, fig = opened.results, self.canvas.figure
        fig.clear()
        self.lines.clear()
        label = self.what_if.text() if res is not None and res.what_if else None
        self.what_if.setVisible(label is not None)
        self.problem.setText("" if opened.problem is None else control.text(*opened.problem))
        self.problem.setVisible(opened.problem is not None)
        if res is not None:
            if res.chain is not None and len(res.ext) == 2:
                draw_summary(fig, res.lay, res.chain, res.ideal, name, label)
            self.lines.addItems([control.text(c, p) for c, p in res.lines] + [render(c) for c in LIMITS])
        self.canvas.draw_idle()


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


class MainWindow(QMainWindow):
    """The main window; `prefix` is the command that starts the orchestrator (control.orchestrator() by default).
    Its state: `path`, the resolved project file; `opened`, its last read (control.Opened) and `loading`, the read
    going on (a Future); `cost`, the folder of this model's last cost, which Run… confirms on; the watch: `command`,
    `run_dir`, its events' `tail`, its `end` event and `proc`, only a process this window started; `live`, whether
    the watched process goes on; `mtime`, project.json's and the board file's st_mtime_ns at the last read (stamp);
    `started`, every process this window started, polled every tick, so that none is left a zombie on Linux; and the
    New form's work going on (Futures): `pads_read`, the chosen board's pads, and `creating`, new.
    Every slot is a bound method: a lambda or partial slot would keep a closed window alive (probed on PySide6
    6.12)."""

    def __init__(self, prefix: list[str] | None = None):
        super().__init__()
        self.setWindowTitle(render("G_APP"))
        self.resize(1200, 800)
        self.prefix = prefix or control.orchestrator()
        self.path = self.opened = self.loading = self.cost = self.mtime = self.pads_read = self.creating = None
        self.command = self.run_dir = self.tail = self.end = self.proc = None
        self.live, self.started = False, []
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
        self.results = ResultsView()
        self.tabs.addTab(self.results, render("G_TAB_RESULTS"))
        self.setCentralWidget(self.tabs)
        form = self.new_form
        for button, slot in ((self.open_button, self.browse), (self.cost_button, self.estimate),
                             (self.run_button, self.run), (self.stop_button, self.stop),
                             (form.board_button, self.pick_board), (form.folder_button, self.pick_folder),
                             (form.create_button, self.create_project)):
            button.clicked.connect(slot)
        form.board.editingFinished.connect(self.board_chosen)
        for button in (self.cost_button, self.run_button, self.stop_button):  # no project yet
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
        then its read and a tick. A process this window started goes on, no longer watched."""
        self.path = pipeline.project_path(str(path)).resolve()
        self.command = self.run_dir = self.tail = self.end = self.proc = self.cost = self.opened = None
        for view in (self.cost_lines, self.cost_status, self.log, self.run_status):
            view.clear()
        self.jobs.setRowCount(0)
        self.results.display(control.Opened(None, None, None, None, None, None), "")  # no plot, no lines, no labels
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
        finished, shown (a display that fails shows E_INTERNAL, and the tick goes on); the watched folder's new events,
        then its state (control.run_state, given that holder); the G_LOCKED banner while another's live run holds the
        lock and this window watches no process of its own; a read when the stamp changed (a save of project.json or of
        the board file); the buttons: Cost while nothing watched goes on and no run holds the lock, Run… also only with
        a cost of this model, Stop only while the watch goes on. A holder whose run folder is the project's results/ is
        a retune (pipeline.retune, r2 §1): waited for, never watched or bannered. Any other holder's run folder, when it
        names one other than the watched one, is watched when this window's own process was not running at the last tick
        (`live`) and the holder lives, or when the holder is dead and nothing is watched (on open), so a cost meanwhile
        keeps its tab. Before all that, with or without a project, New's pad list and new itself when done (show_pads,
        created, which opens the project new wrote, whose own tick runs inside this one)."""
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
                self.opened = done.result()
                if self.mtime[1] is None:  # its board, now known: stamped alone, so a project.json saved since counts
                    # ponytail: a board saved during that first read is seen at its next save
                    self.mtime = (self.mtime[0], self.stamp()[1])
                self.show_project(self.opened)
            except Exception as e:  # a display that fails: this tick goes on, and so do the next ones
                self.project_status.setText(control.text("E_INTERNAL", {"detail": detail(e)}))
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
        self.cost_button.setEnabled(not (self.live or held))
        self.run_button.setEnabled(not (self.live or held) and self.cost is not None)
        self.stop_button.setEnabled(self.live)

    def show_event(self, event: dict) -> None:
        """One event of the watched folder: an end sets `end` and is never listed, and a cost that ended with exit
        code 0 reads the project again, which finds that cost as the model's (control.last_cost) off the GUI thread.
        Under a cost every other event is a line of the Cost tab; under a run a progress fills its job's row, and every
        other event is a line of the log, a job's verdict also filling its row's port and verdict cells."""
        kind, job, params = event["kind"], event["job"], event["params"]
        if kind == "end":
            self.end = event
            if self.command == "cost" and params["exit_code"] == 0:
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
        """Starts `command` (cost or run) on the project as a detached orchestrator in a new run folder and watches
        it; a program that cannot start is G_START_FAILED in that command's status, and nothing starts."""
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
        (G_COST_REUSED), or says there is none (G_NO_COST). Last, the Results tab shows the read (ResultsView)."""
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
        self.results.display(opened, self.path.parent.name)

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

    def closeEvent(self, event: QCloseEvent) -> None:
        """Closing the window stops its timer and drops the pool's work not yet begun (project reads, a pad list, a
        New); what it started goes on (design 5.1: a run outlives its window, and the next window re-attaches it)."""
        self.timer.stop()
        self.pool.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)
