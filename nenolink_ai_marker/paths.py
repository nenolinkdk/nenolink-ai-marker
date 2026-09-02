from __future__ import annotations

from pathlib import Path
import sys


def application_root(
    *,
    frozen: bool | None = None,
    executable: str | Path | None = None,
    module_file: str | Path | None = None,
) -> Path:
    """Return the installation root without consulting the working directory."""
    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if is_frozen:
        return Path(executable or sys.executable).resolve().parent
    source_file = Path(module_file or __file__).resolve()
    return source_file.parent.parent


def badge_directory(**kwargs: object) -> Path:
    return application_root(**kwargs) / "assets" / "badges"
