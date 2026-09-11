from __future__ import annotations

import base64
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable


SHORTCUT_NAME = "Nenolink AI Marker.lnk"


class ShortcutError(Exception):
    """The desktop shortcut could not be created."""


def _powershell_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def shortcut_script(executable: Path) -> str:
    target = _powershell_literal(str(executable))
    name = _powershell_literal(SHORTCUT_NAME)
    return ";".join(
        (
            "$ErrorActionPreference='Stop'",
            f"$target={target}",
            "$desktop=[Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)",
            f"$shortcutPath=Join-Path $desktop {name}",
            "$shell=New-Object -ComObject WScript.Shell",
            "$shortcut=$shell.CreateShortcut($shortcutPath)",
            "$shortcut.TargetPath=$target",
            "$shortcut.WorkingDirectory=[IO.Path]::GetDirectoryName($target)",
            "$shortcut.IconLocation=\"$target,0\"",
            "$shortcut.Description='Nenolink AI Marker'",
            "$shortcut.Save()",
        )
    )


def create_desktop_shortcut(
    *,
    executable: Path | None = None,
    frozen: bool | None = None,
    platform: str | None = None,
    runner: Callable[..., object] = subprocess.run,
) -> None:
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    current_platform = sys.platform if platform is None else platform
    target = Path(executable or sys.executable).resolve()
    if current_platform != "win32" or not is_frozen or target.suffix.lower() != ".exe" or not target.is_file():
        raise ShortcutError("A packaged Windows executable is required")
    encoded = base64.b64encode(shortcut_script(target).encode("utf-16le")).decode("ascii")
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    try:
        runner(
            [str(powershell), "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-EncodedCommand", encoded],
            check=True,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ShortcutError("Windows could not create the shortcut") from error
