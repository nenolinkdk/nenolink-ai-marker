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


@dataclass
class VideoWorkspaceState(WorkspaceRuntimeState):
    mode: str = "permanent"
    duration: int = 5


class WorkspaceAdapter(Protocol):
    state: WorkspaceRuntimeState

    def render_preview(self, state: WorkspaceRuntimeState) -> Any: ...
    def process_output(self, state: WorkspaceRuntimeState) -> Any: ...


def visual_projection(state: WorkspaceRuntimeState) -> tuple[BadgeVisualState, LogoVisualState]:
    """Return immutable-by-convention inputs shared by preview and output."""
    return replace(state.badge), replace(state.logo)
