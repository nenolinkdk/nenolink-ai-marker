"""Small common contract for production workspace runtime state.

This is intentionally not an event bus: workspaces validate events locally and
project the resulting state to preview/output adapters.
"""
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Protocol


class WorkspaceEvent(str, Enum):
    FILE_SELECTED = "file_selected"
    BADGE_ENABLED_CHANGED = "badge_enabled_changed"
    BADGE_SELECTED = "badge_selected"
    BADGE_POSITION_CHANGED = "badge_position_changed"
    BADGE_SIZE_CHANGED = "badge_size_changed"
    BADGE_MARGIN_CHANGED = "badge_margin_changed"
    BADGE_OPACITY_CHANGED = "badge_opacity_changed"
    LOGO_ENABLED_CHANGED = "logo_enabled_changed"
    LOGO_SELECTED = "logo_selected"
    LOGO_POSITION_CHANGED = "logo_position_changed"
    LOGO_SIZE_CHANGED = "logo_size_changed"
    LOGO_MARGIN_CHANGED = "logo_margin_changed"
    LOGO_OPACITY_CHANGED = "logo_opacity_changed"
    SAVE_REQUESTED = "save_requested"
    CLEAR_RUNTIME = "clear_runtime"


@dataclass
class BadgeVisualState:
    enabled: bool = True
    badge_id: str = ""
    position: str = "bottom-right"
    size: int = 20
    margin: int = 20
    opacity: int = 100


@dataclass
class LogoVisualState:
    enabled: bool = False
    path: Path | None = None
    position: str = "top-left"
    size: int = 15
    margin: int = 20
    opacity: int = 100


@dataclass
class WorkspaceRuntimeState:
    """Format-neutral runtime pieces; scope remains format-specific."""
    path: Path | None = None
    badge: BadgeVisualState = field(default_factory=BadgeVisualState)
    logo: LogoVisualState = field(default_factory=LogoVisualState)
    output_status: str = ""

    def has_active_work(self) -> bool:
        return self.path is not None

    def clear_runtime_state(self) -> None:
        self.path = None
        self.output_status = ""


@dataclass
class ImageWorkspaceState(WorkspaceRuntimeState):
    """Image reference workspace state; image has no document scope."""
    preview_image: Any = None
    selected_files: tuple[Path, ...] = ()

    def set_session(self, files: tuple[Path, ...] | list[Path]) -> None:
        self.selected_files = tuple(Path(value) for value in files)
        self.path = self.selected_files[0] if self.selected_files else None

    def clear_runtime_state(self) -> None:
        super().clear_runtime_state()
        self.selected_files = ()
        self.preview_image = None


class ImageEvent(str, Enum):
    FILE_SELECTED = "file_selected"
    BADGE_CHANGED = "badge_changed"
    LOGO_CHANGED = "logo_changed"
    VISUAL_CHANGED = "visual_changed"
    CLEAR_RUNTIME = "clear_runtime"


@dataclass(frozen=True)
class ImageTransition:
    event: ImageEvent
    mutates: tuple[str, ...]
    preserves: tuple[str, ...]


IMAGE_TRANSITION_TABLE: tuple[ImageTransition, ...] = (
    ImageTransition(ImageEvent.FILE_SELECTED, ("selected_files", "path"), ("badge", "logo")),
    ImageTransition(ImageEvent.BADGE_CHANGED, ("badge",), ("selected_files", "path", "logo")),
    ImageTransition(ImageEvent.LOGO_CHANGED, ("logo",), ("selected_files", "path", "badge")),
    ImageTransition(ImageEvent.VISUAL_CHANGED, ("badge", "logo"), ("selected_files", "path")),
    ImageTransition(ImageEvent.CLEAR_RUNTIME, ("selected_files", "path", "preview_image", "output_status"), ("badge", "logo")),
)


def image_transition(event: ImageEvent | str) -> ImageTransition:
    value = ImageEvent(event)
    return next(spec for spec in IMAGE_TRANSITION_TABLE if spec.event is value)


def apply_image_event(state: ImageWorkspaceState, event: ImageEvent | str, payload=None) -> ImageWorkspaceState:
    """The single Image runtime transition boundary."""
    event = ImageEvent(event)
    image_transition(event)  # validate that the event is normative
    payload = payload or {}
    if event is ImageEvent.FILE_SELECTED:
        state.set_session(tuple(Path(value) for value in payload.get("files", ())))
    elif event is ImageEvent.BADGE_CHANGED:
        for key in ("enabled", "badge_id", "position", "size", "margin", "opacity"):
            if key in payload:
                setattr(state.badge, key, payload[key])
    elif event is ImageEvent.LOGO_CHANGED:
        for key in ("enabled", "path", "position", "size", "margin", "opacity"):
            if key in payload:
                setattr(state.logo, key, Path(payload[key]) if key == "path" and payload[key] else payload[key])
    elif event is ImageEvent.VISUAL_CHANGED:
        for key in ("position", "size", "margin", "opacity"):
            if key in payload:
                setattr(state.badge, key, payload[key])
        for key in ("enabled", "path", "position", "size", "margin", "opacity"):
            if f"logo_{key}" in payload:
                value = payload[f"logo_{key}"]
                setattr(state.logo, key, Path(value) if key == "path" and value else value)
    elif event is ImageEvent.CLEAR_RUNTIME:
        state.clear_runtime_state()
    return state


@dataclass
class VideoWorkspaceState(WorkspaceRuntimeState):
    mode: str = "permanent"
    duration: int = 5


@dataclass
class PdfWorkspaceState(WorkspaceRuntimeState):
    """Authoritative PDF runtime; physical preview and processing scope stay separate."""
    page_count: int = 0
    current_page: int = 0
    scope_mode: str = "all"
    scope_input: str = ""
    active_scope: tuple[int, ...] = ()
    preview_image: Any = None


class WorkspaceAdapter(Protocol):
    state: WorkspaceRuntimeState

    def render_preview(self, state: WorkspaceRuntimeState) -> Any: ...
    def process_output(self, state: WorkspaceRuntimeState) -> Any: ...


def visual_projection(state: WorkspaceRuntimeState) -> tuple[BadgeVisualState, LogoVisualState]:
    """Return immutable-by-convention inputs shared by preview and output."""
    return replace(state.badge), replace(state.logo)
