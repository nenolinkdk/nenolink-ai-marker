import os
import sys
from pathlib import Path

project_root = Path(SPECPATH)
tcl_library = Path(os.environ["NENOLINK_TCL_LIBRARY"])
tk_library = Path(os.environ["NENOLINK_TK_LIBRARY"])
python_bin = Path(os.environ["NENOLINK_PYTHON_BIN"])
python_runtime_binaries = [
    (str(candidate), ".")
    for name in ("libiconv-2.dll", "libintl-8.dll")
    if (candidate := python_bin / name).is_file()
]

if not (tcl_library / "init.tcl").is_file():
    raise SystemExit(f"Tcl runtime is incomplete: {tcl_library}")
if not (tk_library / "tk.tcl").is_file():
    raise SystemExit(f"Tk runtime is incomplete: {tk_library}")

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=python_runtime_binaries,
    datas=[
        (str(tcl_library), "_tcl_data"), (str(tk_library), "_tk_data"),
        (str(project_root / "locales"), "locales"),
        (str(project_root / "assets" / "badges"), "assets/badges"),
        (str(project_root / "docs"), "docs"),
    ],
    hiddenimports=["tkinter", "tkinter.filedialog", "tkinter.messagebox"],
    hookspath=[], hooksconfig={}, runtime_hooks=[str(project_root / "scripts" / "pyi-runtime-tk.py")], excludes=[], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name="Nenolink-AI-Marker",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    upx_exclude=[], runtime_tmpdir=None, console=False,
    disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)
