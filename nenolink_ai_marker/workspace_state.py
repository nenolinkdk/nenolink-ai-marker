"""Small common contract for production workspace runtime state.

This is intentionally not an event bus: workspaces validate events locally and
project the resulting state to preview/output adapters.
"""
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Protocol
import re


def reset_workspace_state(state):
    """Reset one local FSM state object to its workspace-specific defaults."""
    defaults = type(state)()
    state.__dict__.clear()
    state.__dict__.update(defaults.__dict__)
    return state


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
    mode: str = "entire"
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
    selected_files: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        # Clean Image state is valid before the first projection: an enabled
        # badge always has a concrete repository identity.
        if self.badge.enabled and not self.badge.badge_id:
            self.badge.badge_id = "ai-assisted.png"

    def set_session(self, files: tuple[Path, ...] | list[Path]) -> None:
        self.selected_files = tuple(Path(value) for value in files)
        self.path = self.selected_files[0] if self.selected_files else None

    def clear_runtime_state(self) -> None:
        super().clear_runtime_state()
        self.selected_files = ()


class ImageEvent(str, Enum):
    FILE_SELECTED = "file_selected"
    BADGE_CHANGED = "badge_changed"
    LOGO_CHANGED = "logo_changed"
    VISUAL_CHANGED = "visual_changed"
    CLEAR_RUNTIME = "clear_runtime"
    RESET_TO_DEFAULTS = "reset_to_defaults"


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
    ImageTransition(ImageEvent.CLEAR_RUNTIME, ("selected_files", "path", "output_status"), ("badge", "logo")),
    ImageTransition(ImageEvent.RESET_TO_DEFAULTS, ("path", "selected_files", "badge", "logo", "output_status"), ()),
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
        for key in ("enabled", "position", "size", "margin", "opacity"):
            if key in payload:
                setattr(state.badge, key, payload[key])
        for key in ("enabled", "path", "position", "size", "margin", "opacity"):
            if f"logo_{key}" in payload:
                value = payload[f"logo_{key}"]
                setattr(state.logo, key, Path(value) if key == "path" and value else value)
    elif event is ImageEvent.CLEAR_RUNTIME:
        state.clear_runtime_state()
    elif event is ImageEvent.RESET_TO_DEFAULTS:
        reset_workspace_state(state)
    return state


@dataclass
class VideoWorkspaceState(WorkspaceRuntimeState):
    mode: str = "beginning"
    duration: int = 5

    def __post_init__(self) -> None:
        if self.badge.enabled and not self.badge.badge_id:
            self.badge.badge_id = "ai-assisted.png"


class VideoEvent(str, Enum):
    FILE_SELECTED = "file_selected"
    MODE_CHANGED = "mode_changed"
    DURATION_CHANGED = "duration_changed"
    BADGE_CHANGED = "badge_changed"
    VISUAL_CHANGED = "visual_changed"
    LOGO_FILE_CHANGED = "logo_file_changed"
    LOGO_ENABLED_CHANGED = "logo_enabled_changed"
    LOGO_MODE_CHANGED = "logo_mode_changed"
    LOGO_SIZE_CHANGED = "logo_size_changed"
    LOGO_MARGIN_CHANGED = "logo_margin_changed"
    LOGO_OPACITY_CHANGED = "logo_opacity_changed"
    CLEAR_RUNTIME = "clear_runtime"
    RESET_TO_DEFAULTS = "reset_to_defaults"


@dataclass(frozen=True)
class VideoTransition:
    event: VideoEvent
    mutates: tuple[str, ...]
    preserves: tuple[str, ...]


VIDEO_TRANSITION_TABLE: tuple[VideoTransition, ...] = (
    VideoTransition(VideoEvent.FILE_SELECTED, ("path",), ("mode", "duration", "badge", "logo")),
    VideoTransition(VideoEvent.MODE_CHANGED, ("mode",), ("path", "duration", "badge", "logo")),
    VideoTransition(VideoEvent.DURATION_CHANGED, ("duration",), ("path", "mode", "badge", "logo")),
    VideoTransition(VideoEvent.BADGE_CHANGED, ("badge",), ("path", "mode", "duration", "logo")),
    VideoTransition(VideoEvent.VISUAL_CHANGED, ("badge",), ("path", "mode", "duration", "logo")),
    VideoTransition(VideoEvent.LOGO_FILE_CHANGED, ("logo",), ("path", "mode", "duration", "badge")),
    VideoTransition(VideoEvent.LOGO_ENABLED_CHANGED, ("logo",), ("path", "mode", "duration", "badge")),
    VideoTransition(VideoEvent.LOGO_MODE_CHANGED, ("logo",), ("path", "mode", "duration", "badge")),
    VideoTransition(VideoEvent.LOGO_SIZE_CHANGED, ("logo",), ("path", "mode", "duration", "badge")),
    VideoTransition(VideoEvent.LOGO_MARGIN_CHANGED, ("logo",), ("path", "mode", "duration", "badge")),
    VideoTransition(VideoEvent.LOGO_OPACITY_CHANGED, ("logo",), ("path", "mode", "duration", "badge")),
    VideoTransition(VideoEvent.CLEAR_RUNTIME, ("path", "output_status"), ("mode", "duration", "badge", "logo")),
    VideoTransition(VideoEvent.RESET_TO_DEFAULTS, ("path", "mode", "duration", "badge", "logo", "output_status"), ()),
)


def video_transition(event: VideoEvent | str) -> VideoTransition:
    value = VideoEvent(event)
    return next(spec for spec in VIDEO_TRANSITION_TABLE if spec.event is value)


def apply_video_event(state: VideoWorkspaceState, event: VideoEvent | str, payload=None) -> VideoWorkspaceState:
    event = VideoEvent(event)
    video_transition(event)
    payload = payload or {}
    if event is VideoEvent.FILE_SELECTED:
        state.path = Path(payload["path"]) if payload.get("path") else None
    elif event is VideoEvent.MODE_CHANGED:
        state.mode = str(payload["mode"])
    elif event is VideoEvent.DURATION_CHANGED:
        state.duration = max(1, int(payload["duration"]))
    elif event is VideoEvent.BADGE_CHANGED:
        for key in ("enabled", "badge_id", "position", "size", "margin", "opacity"):
            if key in payload:
                setattr(state.badge, key, payload[key])
    elif event is VideoEvent.VISUAL_CHANGED:
        for key in ("enabled", "position", "size", "margin", "opacity"):
            if key in payload:
                setattr(state.badge, key, payload[key])
    elif event in {VideoEvent.LOGO_FILE_CHANGED, VideoEvent.LOGO_ENABLED_CHANGED,
                   VideoEvent.LOGO_MODE_CHANGED, VideoEvent.LOGO_SIZE_CHANGED,
                   VideoEvent.LOGO_MARGIN_CHANGED, VideoEvent.LOGO_OPACITY_CHANGED}:
        if "path" in payload: state.logo.path = Path(payload["path"]) if payload["path"] else None
        if "enabled" in payload: state.logo.enabled = bool(payload["enabled"])
        if event is VideoEvent.LOGO_MODE_CHANGED and "mode" in payload: state.logo.mode = str(payload["mode"])
        state.logo.position = "top-left"
        if "size" in payload: state.logo.size = int(payload["size"])
        if "margin" in payload: state.logo.margin = int(payload["margin"])
        if "opacity" in payload: state.logo.opacity = int(payload["opacity"])
    elif event is VideoEvent.CLEAR_RUNTIME:
        state.clear_runtime_state()
    elif event is VideoEvent.RESET_TO_DEFAULTS:
        reset_workspace_state(state)
    return state


@dataclass
class PdfWorkspaceState(WorkspaceRuntimeState):
    """Authoritative PDF runtime; physical preview and processing scope stay separate."""
    page_count: int = 0
    current_page: int = 0
    scope_mode: str = "all"
    scope_input: str = ""
    active_scope: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.badge.enabled and not self.badge.badge_id:
            self.badge.badge_id = "ai-assisted.png"


class PdfEvent(str, Enum):
    FILE_SELECTED = "file_selected"
    SCOPE_MODE = "scope_mode"
    SCOPE_TEXT_CHANGED = "scope_text_changed"
    SCOPE_UPDATE = "scope_update"
    PREVIEW_PREVIOUS = "preview_previous"
    PREVIEW_NEXT = "preview_next"
    PREVIEW_PAGE_SELECTED = "preview_page_selected"
    BADGE_CHANGED = "badge_changed"
    LOGO_CHANGED = "logo_changed"
    VISUAL_CHANGED = "visual_changed"
    CLEAR_RUNTIME = "clear_runtime"
    RESET_TO_DEFAULTS = "reset_to_defaults"


@dataclass(frozen=True)
class PdfTransition:
    event: PdfEvent
    mutates: tuple[str, ...]
    preserves: tuple[str, ...]


PDF_TRANSITION_TABLE: tuple[PdfTransition, ...] = (
    PdfTransition(PdfEvent.FILE_SELECTED, ("path", "page_count", "current_page", "scope_mode", "scope_input", "active_scope"), ("badge", "logo")),
    PdfTransition(PdfEvent.SCOPE_MODE, ("scope_mode", "scope_input", "active_scope", "current_page"), ("path", "page_count", "badge", "logo")),
    PdfTransition(PdfEvent.SCOPE_TEXT_CHANGED, ("scope_input",), ("path", "page_count", "active_scope", "current_page", "badge", "logo")),
    PdfTransition(PdfEvent.SCOPE_UPDATE, ("active_scope", "current_page", "scope_input"), ("path", "page_count", "badge", "logo")),
    PdfTransition(PdfEvent.PREVIEW_PREVIOUS, ("current_page",), ("path", "page_count", "active_scope", "scope_input", "badge", "logo")),
    PdfTransition(PdfEvent.PREVIEW_NEXT, ("current_page",), ("path", "page_count", "active_scope", "scope_input", "badge", "logo")),
    PdfTransition(PdfEvent.PREVIEW_PAGE_SELECTED, ("current_page",), ("path", "page_count", "active_scope", "scope_input", "badge", "logo")),
    PdfTransition(PdfEvent.BADGE_CHANGED, ("badge",), ("path", "page_count", "active_scope", "scope_input", "current_page", "logo")),
    PdfTransition(PdfEvent.LOGO_CHANGED, ("logo",), ("path", "page_count", "active_scope", "scope_input", "current_page", "badge")),
    PdfTransition(PdfEvent.VISUAL_CHANGED, ("badge", "logo"), ("path", "page_count", "active_scope", "scope_input", "current_page")),
    PdfTransition(PdfEvent.CLEAR_RUNTIME, ("path", "page_count", "current_page", "scope_mode", "scope_input", "active_scope"), ("badge", "logo")),
    PdfTransition(PdfEvent.RESET_TO_DEFAULTS, ("path", "page_count", "current_page", "scope_mode", "scope_input", "active_scope", "badge", "logo", "output_status"), ()),
)


def pdf_transition(event: PdfEvent | str) -> PdfTransition:
    value = PdfEvent(event)
    return next(spec for spec in PDF_TRANSITION_TABLE if spec.event is value)


def _pdf_values(value, page_count: int, mode: str) -> tuple[int, ...]:
    if mode == "all": return tuple(range(1, page_count + 1))
    if mode == "first": return (1,) if page_count else ()
    if mode not in {"selected", "range"}:
        raise ValueError("Unknown PDF scope")
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise ValueError("PDF scope selection is empty")
        selected: set[int] = set()
        for part in raw.split(","):
            token = part.strip()
            if not re.fullmatch(r"\d+(?:-\d+)?", token):
                raise ValueError("Invalid PDF scope selection")
            ends = tuple(int(item) for item in token.split("-"))
            if len(ends) == 2 and ends[0] > ends[1]:
                raise ValueError("PDF page range must be ascending")
            if any(item < 1 or item > page_count for item in ends):
                raise ValueError("PDF scope is outside the document")
            if mode == "range" and len(ends) != 2:
                raise ValueError("PDF range requires page intervals")
            selected.update(range(ends[0], ends[-1] + 1))
        values = tuple(sorted(selected))
    else:
        values = tuple(sorted(set(int(v) for v in value)))
    if not values or any(v < 1 or v > page_count for v in values):
        raise ValueError("PDF scope is outside the document")
    return values


def apply_pdf_event(state: PdfWorkspaceState, event: PdfEvent | str, payload=None) -> PdfWorkspaceState:
    event = PdfEvent(event); pdf_transition(event); payload = payload or {}
    if event is PdfEvent.FILE_SELECTED:
        state.path = payload["path"]; state.page_count = int(payload["page_count"])
        state.current_page = 1; state.scope_mode = "all"; state.scope_input = ""
        state.active_scope = tuple(range(1, state.page_count + 1))
    elif event is PdfEvent.SCOPE_MODE:
        mode = str(payload["mode"])
        if mode not in {"all", "first", "selected", "range"}:
            raise ValueError("Unknown PDF scope")
        previous_mode = state.scope_mode
        values = _pdf_values((), state.page_count, mode) if mode in {"all", "first"} else None
        state.scope_mode = mode
        if previous_mode != mode and previous_mode in {"selected", "range"} and mode in {"selected", "range"}:
            state.scope_input = ""
        if mode in {"all", "first"}:
            state.active_scope = values; state.current_page = values[0] if values else 0
    elif event is PdfEvent.SCOPE_TEXT_CHANGED:
        state.scope_input = str(payload.get("text", ""))
    elif event is PdfEvent.SCOPE_UPDATE:
        selection = payload.get("text") or payload.get("values", ())
        values = _pdf_values(selection, state.page_count, state.scope_mode)
        state.active_scope = values; state.current_page = values[0] if values else state.current_page
        state.scope_input = str(payload.get("text", state.scope_input))
    elif event in {PdfEvent.PREVIEW_PREVIOUS, PdfEvent.PREVIEW_NEXT}:
        delta = -1 if event is PdfEvent.PREVIEW_PREVIOUS else 1
        state.current_page = max(1, min(state.page_count, state.current_page + delta))
    elif event is PdfEvent.PREVIEW_PAGE_SELECTED:
        state.current_page = max(1, min(state.page_count, int(payload.get("page", state.current_page))))
    elif event is PdfEvent.BADGE_CHANGED:
        for key, value in payload.items(): setattr(state.badge, key, value)
    elif event is PdfEvent.LOGO_CHANGED:
        for key, value in payload.items(): setattr(state.logo, key, Path(value) if key == "path" and value else value)
    elif event is PdfEvent.VISUAL_CHANGED:
        for key, value in payload.items():
            target = state.logo if key.startswith("logo_") else state.badge
            setattr(target, key.removeprefix("logo_"), value)
    elif event is PdfEvent.CLEAR_RUNTIME:
        state.clear_runtime_state(); state.page_count = 0; state.current_page = 0; state.scope_mode = "all"; state.scope_input = ""; state.active_scope = ()
    elif event is PdfEvent.RESET_TO_DEFAULTS:
        reset_workspace_state(state)
    return state


class WorkspaceAdapter(Protocol):
    state: WorkspaceRuntimeState

    def render_preview(self, state: WorkspaceRuntimeState) -> Any: ...
    def process_output(self, state: WorkspaceRuntimeState) -> Any: ...


def visual_projection(state: WorkspaceRuntimeState) -> tuple[BadgeVisualState, LogoVisualState]:
    """Return immutable-by-convention inputs shared by preview and output."""
    return replace(state.badge), replace(state.logo)
