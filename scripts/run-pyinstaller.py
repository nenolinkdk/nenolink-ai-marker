"""Run PyInstaller after initializing Tcl in relocatable Windows Python."""
from __future__ import annotations

import ctypes
from pathlib import Path
import os
import sys


def initialize_build_tcl() -> None:
    root = Path(sys.base_prefix)
    tcl_library = Path(os.environ["NENOLINK_TCL_LIBRARY"])
    tk_library = Path(os.environ["NENOLINK_TK_LIBRARY"])
    library = ctypes.CDLL(str(root / "DLLs" / "tcl86t.dll"))
    library.Tcl_FindExecutable.argtypes = [ctypes.c_char_p]
    library.Tcl_FindExecutable(Path(sys.executable).name.encode("utf-8"))
    library.Tcl_CreateInterp.restype = ctypes.c_void_p
    interpreter = library.Tcl_CreateInterp()
    library.Tcl_Eval.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    command = (
        f"set tcl_library {{{tcl_library.as_posix()}}}; "
        "source [file join $tcl_library init.tcl]"
    )
    if library.Tcl_Eval(interpreter, command.encode("utf-8")) != 0:
        library.Tcl_GetStringResult.argtypes = [ctypes.c_void_p]
        library.Tcl_GetStringResult.restype = ctypes.c_char_p
        detail = library.Tcl_GetStringResult(interpreter).decode("utf-8", errors="replace")
        raise RuntimeError(f"Could not initialize Tcl for PyInstaller analysis: {detail}")
    os.environ["TCL_LIBRARY"] = tcl_library.as_posix()
    os.environ["TK_LIBRARY"] = tk_library.as_posix()


initialize_build_tcl()

from PyInstaller.__main__ import run

run(sys.argv[1:])
