"""Make the bundled MinGW Tcl/Tk scripts readable before tkinter starts."""
from pathlib import Path
import os
import shutil
import sys

if getattr(sys, "frozen", False):
    log_path = os.environ.get("NENOLINK_BOOT_LOG")
    def log(message: str) -> None:
        if log_path:
            with open(log_path, "a", encoding="utf-8") as stream:
                stream.write(message + "\n")
    log("runtime hook started")
    bundle = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    override = os.environ.get("NENOLINK_RUNTIME_ROOT")
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    runtime = Path(override) if override else local / "Nenolink" / "AI Marker" / "tk-runtime-8.6.13"
    tcl_target = runtime / "tcl8.6"
    tk_target = runtime / "tk8.6"
    if not (tcl_target / "init.tcl").is_file():
        shutil.copytree(bundle / "_tcl_data", tcl_target, dirs_exist_ok=True)
    if not (tk_target / "tk.tcl").is_file():
        shutil.copytree(bundle / "_tk_data", tk_target, dirs_exist_ok=True)
    os.environ["TCL_LIBRARY"] = str(tcl_target)
    os.environ["TK_LIBRARY"] = str(tk_target)
    log(f"runtime hook ready: {tcl_target}")
