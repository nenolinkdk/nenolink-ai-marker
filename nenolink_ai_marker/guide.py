from __future__ import annotations

import os
from pathlib import Path


def open_user_guide(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"User guide not found: {path}")
    if os.name != "nt":
        raise OSError("Opening the local PDF is supported on Windows.")
    os.startfile(str(path))  # type: ignore[attr-defined]
