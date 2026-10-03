"""Authoritative internal state for the PPTX workspace.

The outer content FSM remains owned by ShellController.  This model keeps
physical preview, processing scope, badge and logo state orthogonal so widgets
cannot accidentally become a second state owner.
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


@dataclass
class PptxBadgeState:
    enabled: bool = True
    badge_id: str = ""
    position: str = "bottom-right"
    size: int = 20
    margin: int = 20
    opacity: int = 100


@dataclass
class PptxLogoState:
    enabled: bool = False
    path: Path | None = None
    position: str = "top-left"
    size: int = 15
    margin: int = 20
    opacity: int = 100


@dataclass
class PptxWorkspaceState:
    path: Path | None = None
    slide_count: int = 0
    current_slide: int = 1
    scope_mode: str = "all"
    active_scope: tuple[int, ...] = ()
    scope_input: str = ""
    badge: PptxBadgeState = field(default_factory=PptxBadgeState)
    logo: PptxLogoState = field(default_factory=PptxLogoState)
    output_status: str = ""

    @property
    def loaded(self) -> bool:
        return self.path is not None and self.slide_count > 0

    def clear(self) -> None:
        self.path = None; self.slide_count = 0; self.current_slide = 1
        self.scope_mode = "all"; self.active_scope = (); self.scope_input = ""; self.output_status = ""


class PptxEvent(str, Enum):
    CHOOSE_FILE = "choose_file"
    SAVE_AS = "save_as"
    BADGE_ENABLE = "badge_enable"
    BADGE_SELECT = "badge_select"
    BADGE_POSITION = "badge_position"
    BADGE_SIZE = "badge_size"
    BADGE_MARGIN = "badge_margin"
    BADGE_OPACITY = "badge_opacity"
    LOGO_ENABLE = "logo_enable"
    LOGO_CHOOSE = "logo_choose"
    LOGO_POSITION = "logo_position"
    LOGO_SIZE = "logo_size"
    LOGO_MARGIN = "logo_margin"
    LOGO_OPACITY = "logo_opacity"
    SCOPE_MODE = "scope_mode"
    SCOPE_TEXT_CHANGED = "scope_text_changed"
    SCOPE_UPDATE = "scope_update"
    PREVIEW_PREVIOUS = "preview_previous"
    PREVIEW_NEXT = "preview_next"


@dataclass(frozen=True)
class PptxEventReceipt:
    event: PptxEvent
    before: dict[str, Any]
    after: dict[str, Any]
    changed: tuple[str, ...]
    preserved: tuple[str, ...]
    projection_updated: bool = True


@dataclass(frozen=True)
class PptxTransition:
    event: PptxEvent
    valid_sources: tuple[str, ...] = ("empty", "loaded")
    mutates: tuple[str, ...] = ()
    preserves: tuple[str, ...] = ("path", "current_slide", "active_scope", "badge", "logo")
    rerender: bool = False
    output: bool = False
    remount: bool = False


PPTX_TRANSITION_TABLE: tuple[PptxTransition, ...] = (
    PptxTransition(PptxEvent.CHOOSE_FILE, mutates=("path", "slide_count", "current_slide", "active_scope")),
    PptxTransition(PptxEvent.SAVE_AS, output=True),
    *(PptxTransition(event, mutates=(f"badge.{field}",), preserves=("path", "current_slide", "active_scope", "logo"), rerender=True)
      for event, field in ((PptxEvent.BADGE_ENABLE, "enabled"), (PptxEvent.BADGE_SELECT, "badge_id"),
                           (PptxEvent.BADGE_POSITION, "position"), (PptxEvent.BADGE_SIZE, "size"),
                           (PptxEvent.BADGE_MARGIN, "margin"), (PptxEvent.BADGE_OPACITY, "opacity"))),
    *(PptxTransition(event, mutates=(f"logo.{field}",), preserves=("path", "current_slide", "active_scope", "badge"), rerender=True)
      for event, field in ((PptxEvent.LOGO_ENABLE, "enabled"), (PptxEvent.LOGO_CHOOSE, "path"),
                           (PptxEvent.LOGO_POSITION, "position"), (PptxEvent.LOGO_SIZE, "size"),
                           (PptxEvent.LOGO_MARGIN, "margin"), (PptxEvent.LOGO_OPACITY, "opacity"))),
    PptxTransition(PptxEvent.SCOPE_MODE, mutates=("scope_mode",), rerender=True),
    PptxTransition(PptxEvent.SCOPE_TEXT_CHANGED, mutates=("scope_input",)),
    PptxTransition(PptxEvent.SCOPE_UPDATE, mutates=("scope_mode", "active_scope", "current_slide"), rerender=True),
    PptxTransition(PptxEvent.PREVIEW_PREVIOUS, mutates=("current_slide",), preserves=("path", "active_scope", "badge", "logo"), rerender=True),
    PptxTransition(PptxEvent.PREVIEW_NEXT, mutates=("current_slide",), preserves=("path", "active_scope", "badge", "logo"), rerender=True),
)


def pptx_transition(event: PptxEvent) -> PptxTransition:
    return next(spec for spec in PPTX_TRANSITION_TABLE if spec.event == PptxEvent(event))


def apply_pptx_visual_event(state: PptxWorkspaceState, event: PptxEvent, value):
    """Apply one validated visual event; unrelated state is untouched."""
    mapping = {
        PptxEvent.BADGE_ENABLE: (state.badge, "enabled", bool),
        PptxEvent.BADGE_SELECT: (state.badge, "badge_id", str),
        PptxEvent.BADGE_POSITION: (state.badge, "position", str),
        PptxEvent.BADGE_SIZE: (state.badge, "size", lambda v: max(1, min(100, int(v)))),
        PptxEvent.BADGE_MARGIN: (state.badge, "margin", lambda v: max(0, min(250, int(v)))),
        PptxEvent.BADGE_OPACITY: (state.badge, "opacity", lambda v: max(0, min(100, int(v)))),
        PptxEvent.LOGO_ENABLE: (state.logo, "enabled", bool),
        PptxEvent.LOGO_CHOOSE: (state.logo, "path", lambda v: Path(v) if v else None),
        PptxEvent.LOGO_POSITION: (state.logo, "position", str),
        PptxEvent.LOGO_SIZE: (state.logo, "size", lambda v: max(1, min(100, int(v)))),
        PptxEvent.LOGO_MARGIN: (state.logo, "margin", lambda v: max(0, min(250, int(v)))),
        PptxEvent.LOGO_OPACITY: (state.logo, "opacity", lambda v: max(0, min(100, int(v)))),
    }
    target, field, normalizer = mapping[PptxEvent(event)]
    setattr(target, field, normalizer(value))
    return state
