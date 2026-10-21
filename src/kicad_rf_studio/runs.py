# SPDX-License-Identifier: GPL-3.0-or-later
"""What a run needs besides the project: the per-user data folder with its settings.json, openEMS in this Python, the
run and job folders, the project lock, events.jsonl, and the pool of worker processes with its size. `setup-openems`
installs the wheels of the official Windows package; `check_openems` reads the installed versions."""
import contextlib
import ctypes
import json
import os
import re
import secrets
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

from kicad_rf_studio.core.messages import KrsError, reason, render
from kicad_rf_studio.core.project import save_project
from kicad_rf_studio.worker import ERR, LOG, SETUP_FAILED

WINDOWS = sys.platform == "win32"  # tests patch it, so the Windows API calls below test sys.platform itself
# metadata only, so no openEMS DLL loads; run with -I, which sees what a worker sees
PROBE = "import importlib.metadata as m; print(m.version('openEMS'), m.version('CSXCAD'))"
MB_PER_MCELL, MB_PER_WORKER = 170, 50  # ponytail: provisional (spec 6.4); P0-C measures RAM
WORKER = ("-I", "-u", "-m", "kicad_rf_studio.worker")  # after sys.executable; -u: log.txt follows the run
POLL_S = 1.0  # how often the pool looks at its jobs
ABORT_WAIT_S = 60.0  # how long a stopped job may take to write its data before it is killed


def data_dir() -> Path:
    """The per-user data folder, never a temp folder (spec 3.3): %LOCALAPPDATA% on Windows, else $XDG_DATA_HOME."""
    name, default = ("LOCALAPPDATA", "~/AppData/Local") if WINDOWS else ("XDG_DATA_HOME", "~/.local/share")
    return Path(os.environ.get(name) or default).expanduser() / "kicad-rf-studio"


def load_settings() -> dict:
    """settings.json in data_dir(), or {} before anything wrote it."""
    path = data_dir() / "settings.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))  # -sig: as load_project, for a hand edit
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:  # ValueError: UnicodeError or json.JSONDecodeError
        raise KrsError("E_SETTINGS_UNREADABLE", path=str(path), reason=reason(e)) from None
    if not isinstance(data, dict):
        raise KrsError("E_SETTINGS_UNREADABLE", path=str(path), reason="not a JSON object")
    return data


def save_settings(data: dict) -> None:
    """Writes settings.json, making data_dir() first."""
    data_dir().mkdir(parents=True, exist_ok=True)
    save_project(data_dir() / "settings.json", data)


def install_command() -> str:
    """How to give this Python openEMS, as the E_OPENEMS_* messages say it."""
    if WINDOWS:
        return "kicad-rf-studio setup-openems <openEMS folder>"
    return "update_openEMS.sh <prefix> --python with this venv active (see README)"


def openems_versions() -> tuple[str, str]:
    """The openEMS and CSXCAD versions installed in this Python. Raises E_OPENEMS_MISSING."""
    probe = subprocess.run([sys.executable, "-I", "-c", PROBE], capture_output=True, text=True, timeout=120)
    if probe.returncode:
        raise KrsError("E_OPENEMS_MISSING", python=sys.executable, command=install_command())
    openems, csxcad = probe.stdout.split()
    return openems, csxcad


def check_openems() -> list[tuple[str, dict]]:
    """W_OPENEMS_UNTESTED outside openEMS 0.37.x. Raises E_OPENEMS_MISSING, or E_OPENEMS_OLD below openEMS 0.37 or
    CSXCAD 0.7."""
    openems, csxcad = openems_versions()
    em, cs = (tuple(map(int, re.match(r"(\d+)\.(\d+)", v).groups())) for v in (openems, csxcad))
    if em < (0, 37) or cs < (0, 7):
        raise KrsError("E_OPENEMS_OLD", openems=openems, csxcad=csxcad, command=install_command())
    return [] if em == (0, 37) else [("W_OPENEMS_UNTESTED", {"openems": openems, "command": install_command()})]


def setup_openems(folder: Path) -> list[tuple[str, dict]]:
    """Installs the openEMS and CSXCAD wheels of the official Windows package in `folder` into this Python, without
    their dependencies (pyproject.toml lists them), and records the folder in settings.json."""
    if not WINDOWS:
        raise KrsError("E_SETUP_OPENEMS_WINDOWS")
    tag, wheels = f"cp{sys.version_info.major}{sys.version_info.minor}", folder / "python"
    has_wheels = all(any(wheels.glob(f"{name}-*-{tag}-*.whl")) for name in ("openems", "csxcad"))
    if not (has_wheels and (folder / "openEMS.exe").exists()):
        raise KrsError("E_SETUP_OPENEMS_DIR", dir=str(folder), tag=tag)
    # --no-index: neither name is claimed on PyPI, so pip must never look there for them. --force-reinstall: else pip
    # keeps an installed openEMS of another version while settings.json names this folder
    pip = subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", "--force-reinstall",
                          "--find-links", str(wheels), "openEMS", "CSXCAD"])
    if pip.returncode:
        raise KrsError("E_SETUP_OPENEMS_PIP", exit_code=pip.returncode)
    settings = load_settings()
    settings["openems_dir"] = str(folder.resolve())
    save_settings(settings)
    openems, csxcad = openems_versions()
    return [("I_OPENEMS_INSTALLED", {"openems": openems, "csxcad": csxcad, "dir": settings["openems_dir"],
                                     "settings": str(data_dir() / "settings.json")})]


def ascii_name(text: str) -> str:
    """`text` as a folder name: every character but A-Z, a-z, 0-9, _ and - becomes _, and an empty text _."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", text) or "_"


def run_dir_for(stem: str) -> Path:
    """A new run folder, not created (C-23): runs/<stem>-<YYYYMMDD-HHMMSS>-<4 hex digits> in data_dir(), where `stem`
    is the project folder's name, or "calibrate"."""
    # ponytail: run folders are never deleted (C-23)
    return data_dir() / "runs" / f"{ascii_name(stem)}-{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"


def job_dir(run_dir: Path, k: int, name: str) -> Path:
    """The folder of job `k`, named `name`: k is 1-based for the run's jobs and 0 for job-0-setup and job-0-xml."""
    return run_dir / f"job-{k}-{ascii_name(name)}"


def write_spec(run_dir: Path, spec: dict) -> None:
    """Writes the run's model.json, making `run_dir` if `run` has not yet (runs/ may not exist either)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "model.json").write_text(json.dumps(spec), encoding="utf-8")


def write_job(job: Path, port: int, mode: str, threads: int, t_max: float) -> Path:
    """Makes the job folder `job` and its job.json, as worker.py reads it, and returns `job`."""
    job.mkdir(parents=True)
    (job / "job.json").write_text(json.dumps({"spec": "../model.json", "port": port, "mode": mode,
                                              "threads": threads, "t_max": t_max}), encoding="utf-8")
    return job


def _alive(pid: int) -> bool:
    """Whether process `pid` is running. Never os.kill on Windows: there it terminates the process."""
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
        except OSError as e:
            return isinstance(e, PermissionError)  # alive, but another user's
        return True
    kernel32, code = ctypes.WinDLL("kernel32"), ctypes.c_ulong()
    kernel32.OpenProcess.restype = ctypes.c_void_p  # a HANDLE, which the default int would cut to 32 bits
    handle = ctypes.c_void_p(kernel32.OpenProcess(0x1000, False, pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle.value:
        return False
    try:
        kernel32.GetExitCodeProcess(handle, ctypes.byref(code))  # a failure leaves code 0
        return code.value == 259  # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


@contextlib.contextmanager
def project_lock(project_path: Path, run_dir: Path) -> Iterator[None]:
    """Holds <project>.lock, {"pid", "run_dir", "started"}, while a run of `project_path` into `run_dir` goes on (C-24).
    Raises E_LOCKED while a live run holds it; reclaims a dead run's with W_STALE_LOCK. Removed on exit, exceptions
    included, but only when this call made it: a refused second run leaves the holder's lock alone (spec 3.3)."""
    # ponytail: one lock per project, so two projects share the CPU; a reused pid keeps a stale lock alive, and E_LOCKED
    # says to delete it
    lock = project_path.with_name(project_path.name + ".lock")
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            holder = json.loads(lock.read_text(encoding="utf-8"))
        if _alive(holder["pid"]):
            raise KrsError("E_LOCKED", lock=str(lock), run=holder["run_dir"], started=holder["started"])
        print(render("W_STALE_LOCK", lock=str(lock), run=holder["run_dir"]))
        lock.unlink(missing_ok=True)  # missing: another run reclaimed it first
    try:  # the write too: a lock left empty by a full disk would block every later run
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "run_dir": str(run_dir), "started": time.strftime("%Y-%m-%dT%H:%M:%S")}, f)
        yield
    finally:
        lock.unlink(missing_ok=True)  # missing: the user deleted it, as E_LOCKED invites


def emit(run_dir: Path, kind: str, code: str, params: dict, job: int | None = None) -> None:
    """Appends an event to events.jsonl in `run_dir` (C-21) and prints its message. `kind` is progress, verdict, cost,
    result or message; `job` is the job's k, 0 for job-0-*, None for the whole run. The params travel as one dict, so a
    field named kind or job cannot collide."""
    event = {"t": round(time.time(), 3), "kind": kind, "job": job, "code": code, "params": params}
    with open(run_dir / "events.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    print(render(code, **params))


def free_ram_mb() -> float:
    """The free RAM in MB: GlobalMemoryStatusEx's ullAvailPhys on Windows, MemAvailable of /proc/meminfo elsewhere."""
    if sys.platform == "win32":
        status = (ctypes.c_ulonglong * 8)(64)  # MEMORYSTATUSEX as 8 uint64s: dwLength (its size) is the first's low half
        ctypes.WinDLL("kernel32").GlobalMemoryStatusEx(status)
        return status[2] / 2**20  # ullAvailPhys, after dwLength with dwMemoryLoad, and ullTotalPhys
    meminfo = Path("/proc/meminfo").read_text(encoding="ascii")
    return int(re.search(r"^MemAvailable:\s+(\d+) kB", meminfo, re.M)[1]) / 1024


def pool_size(cells: int, threads: int, free_mb: float, cpus: int) -> int:
    """How many workers of `threads` threads run at once on a model of `cells` cells (spec 6.4): as many as the cores
    and the free RAM allow, and never fewer than one."""
    return max(1, min(cpus // threads, int(free_mb // (MB_PER_MCELL * cells / 1e6 + MB_PER_WORKER))))


def worker_env(settings: dict) -> dict:
    """A worker's environment: this one with OpenBLAS on one thread, as openEMS has the cores, and CSXCAD_INSTALL_PATH
    (where CSXCAD looks for openEMS's DLLs) set to settings.json's openems_dir when it has one."""
    env = {**os.environ, "OPENBLAS_NUM_THREADS": "1"}
    if settings.get("openems_dir"):
        env["CSXCAD_INSTALL_PATH"] = settings["openems_dir"]
    return env


def run_jobs(jobs: list[Path], pool: int, run_dir: Path, settings: dict,
             watch: Callable[[Path], bool] | None = None) -> dict[Path, dict]:
    """Runs a worker in each job folder of `jobs`, up to `pool` at once in list order (spec 6.1, C-25), and returns
    each job's {"code": its exit code, None if it never started, "stopped": whether the run was stopped}. A STOP file
    in `run_dir`, or Ctrl+C, stops the run (C-26): ABORT goes into every running job's folder and no other job starts;
    a job with no port_ut_1 yet is still in setup, where openEMS never looks for ABORT, and is killed at once, any
    other one if it still runs ABORT_WAIT_S later. Otherwise a running job for which `watch(job)` is true gets ABORT
    once. No worker outlives the call."""
    out = {job: {"code": None, "stopped": False} for job in jobs}
    todo, running, env = list(jobs), {}, worker_env(settings)
    spawn = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
             if sys.platform == "win32" else {"start_new_session": True})  # so Ctrl+C reaches only this process
    try:
        try:
            while todo or running:
                if (run_dir / "STOP").exists():
                    raise KeyboardInterrupt  # a STOP file stops the run as Ctrl+C does
                while todo and len(running) < pool:
                    job = todo.pop(0)
                    with open(job / LOG, "wb") as log, open(job / ERR, "wb") as err:
                        running[job] = subprocess.Popen([sys.executable, *WORKER, "job.json"], cwd=job, env=env,
                                                        stdout=log, stderr=err, **spawn)
                time.sleep(POLL_S)
                for job, proc in list(running.items()):
                    if proc.poll() is not None:
                        out[job]["code"] = running.pop(job).returncode
                    elif watch and not (job / "ABORT").exists() and watch(job):
                        (job / "ABORT").write_text("")
        except KeyboardInterrupt:
            for job, proc in running.items():
                (job / "ABORT").write_text("")
                if not (job / "port_ut_1").exists():
                    proc.kill()
                    proc.wait()
            deadline = time.monotonic() + ABORT_WAIT_S
            while time.monotonic() < deadline and any(proc.poll() is None for proc in running.values()):
                time.sleep(POLL_S)
            for result in out.values():
                result["stopped"] = True
    finally:  # kills what still runs, whatever ended the loop
        for job, proc in running.items():
            if proc.poll() is None:
                proc.kill()
            out[job]["code"] = proc.wait()
    return out


def check_job(job: Path, result: dict, name: str, settings: dict) -> None:
    """The one map from a job's exit to its outcome, `result` being the job's entry in what run_jobs returns:
    KeyboardInterrupt when the run was stopped, E_OPENEMS_DLL for exit code 2 (openEMS did not import, C-31),
    E_SETUP_FAILED for SETUP_FAILED and E_WORKER_FAILED, naming the job `name`, for any other non-zero code."""
    if result["stopped"]:
        raise KeyboardInterrupt
    code, log = result["code"], str(job / LOG)
    if code == 2:
        raise KrsError("E_OPENEMS_DLL", value=worker_env(settings).get("CSXCAD_INSTALL_PATH") or "unset")
    if code == SETUP_FAILED:
        raise KrsError("E_SETUP_FAILED", log=log)
    if code:
        raise KrsError("E_WORKER_FAILED", job=name, exit_code=code, log=log)
