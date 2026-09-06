"""Initialize the Tcl/Tk scripts embedded by PyInstaller before tkinter."""
import ctypes
from pathlib import Path
import os
import sys

if getattr(sys, "frozen", False):
    log_path = os.environ.get("NENOLINK_BOOT_LOG")
    def log(message: str) -> None:
        if log_path:
            with open(log_path, "a", encoding="utf-8") as stream:
                stream.write(message + "\n")
    log("runtime hook started")
    bundle = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    tcl_target = bundle / "_tcl_data"
    tk_target = bundle / "_tk_data"
    if not (tcl_target / "init.tcl").is_file():
        raise RuntimeError(f"Bundled Tcl runtime is incomplete: {tcl_target}")
    if not (tk_target / "tk.tcl").is_file():
        raise RuntimeError(f"Bundled Tk runtime is incomplete: {tk_target}")
    # The relocatable Windows runtime needs its Tcl library initialized before
    # _tkinter creates the GUI interpreter. This remains packaging-only and
    # avoids relying on PATH, an installed Python, or a machine-specific path.
    library = ctypes.CDLL(str(bundle / "tcl86t.dll"))
    library.Tcl_FindExecutable.argtypes = [ctypes.c_char_p]
    library.Tcl_FindExecutable(Path(sys.executable).name.encode("utf-8"))
    library.Tcl_CreateInterp.restype = ctypes.c_void_p
    interpreter = library.Tcl_CreateInterp()
    library.Tcl_Eval.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    command = (
        f"set tcl_library {{{tcl_target.as_posix()}}}; "
        "source [file join $tcl_library init.tcl]"
    )
    if library.Tcl_Eval(interpreter, command.encode("utf-8")) != 0:
        raise RuntimeError("Bundled Tcl runtime could not be initialized")
    os.environ["TCL_LIBRARY"] = tcl_target.as_posix()
    os.environ["TK_LIBRARY"] = tk_target.as_posix()
    log(f"runtime hook ready: {tcl_target}")
