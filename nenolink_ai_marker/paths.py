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


def bundled_root(*, bundle_root: str | Path | None = None) -> Path | None:
    """Return PyInstaller's extracted resource root, when available."""
    value = bundle_root if bundle_root is not None else getattr(sys, "_MEIPASS", None)
    return Path(value).resolve() if value else None


def resource_directory(relative: Path, **kwargs: object) -> Path:
    """Prefer editable files beside the app, then use the embedded fallback."""
    bundle = kwargs.pop("bundle_root", None)
    external = application_root(**kwargs) / relative
    if external.is_dir():
        return external
    embedded_root = bundled_root(bundle_root=bundle)
    embedded = embedded_root / relative if embedded_root else None
    return embedded if embedded and embedded.is_dir() else external


def badge_directory(**kwargs: object) -> Path:
    return resource_directory(Path("assets") / "badges", **kwargs)


def locale_directory(**kwargs: object) -> Path:
    return resource_directory(Path("locales"), **kwargs)


def docs_directory(**kwargs: object) -> Path:
    return resource_directory(Path("docs"), **kwargs)


def user_guide_path(**kwargs: object) -> Path:
    return docs_directory(**kwargs) / "Nenolink-AI-Marker-User-Guide-EN.pdf"
