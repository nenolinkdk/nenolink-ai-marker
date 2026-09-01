import os
from pathlib import Path

project_root = Path(SPECPATH)
tcl_library = Path(os.environ["NENOLINK_TCL_LIBRARY"])
tk_library = Path(os.environ["NENOLINK_TK_LIBRARY"])

if not (tcl_library / "init.tcl").is_file():
    raise SystemExit(f"Tcl runtime is incomplete: {tcl_library}")
if not (tk_library / "tk.tcl").is_file():
    raise SystemExit(f"Tk runtime is incomplete: {tk_library}")

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[(str(tcl_library), "_tcl_data"), (str(tk_library), "_tk_data")],
    hiddenimports=["tkinter", "tkinter.filedialog", "tkinter.messagebox"],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name="Nenolink-AI-Marker",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    upx_exclude=[], runtime_tmpdir=None, console=False,
    disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)
