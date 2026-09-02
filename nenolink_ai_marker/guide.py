from __future__ import annotations

import os
import subprocess
from pathlib import Path


def open_user_guide(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"User guide not found: {path}")
    if os.name != "nt":
        raise OSError("Opening the local PDF is supported on Windows.")
    try:
        os.startfile(str(path))  # type: ignore[attr-defined]
    except OSError:
        # Explorer uses the user's normal PDF association and is a reliable
        # fallback on restricted Windows desktops.
        subprocess.Popen(["explorer.exe", str(path)])
