"""Authoritative internal state for the PPTX workspace.

The outer content FSM remains owned by ShellController.  This model keeps
physical preview, processing scope, badge and logo state orthogonal so widgets
cannot accidentally become a second state owner.
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
import re


@dataclass
class PptxBadgeState:
    enabled: bool = True
    badge_id: str = "AI Assisted"
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

    @property
    def selected_file(self): return self.path
    @property
    def display_filename(self): return self.path.name if self.path else None
    @property
    def file_size_bytes(self):
        try: return self.path.stat().st_size if self.path else None
        except OSError: return None

    def clear(self) -> None:
        self.path = None; self.slide_count = 0; self.current_slide = 1
        self.scope_mode = "all"; self.active_scope = (); self.scope_input = ""; self.output_status = ""

    def visual_projection(self) -> dict[str, Any]:
        """Immutable-style snapshot consumed by preview and output adapters."""
        positions = {"badge": self.badge.position, "logo": self.logo.position}
        if self.logo.enabled and self.badge.enabled and positions["logo"] == positions["badge"]:
            fallback = {"top-left": "top-right", "top-right": "bottom-right", "bottom-left": "top-left", "bottom-right": "bottom-left", "center": "bottom-right"}
            positions["logo"] = fallback[positions["logo"]]
        return {
            "badge": self.badge.__dict__.copy(),
            "logo": self.logo.__dict__.copy(),
            "scope": tuple(self.active_scope),
            "current_slide": self.current_slide,
            "path": self.path,
            "overlay_positions": positions,
        }


def choose_file_success(state: PptxWorkspaceState, path: Path, slide_count: int) -> PptxWorkspaceState:
    state.path = Path(path); state.slide_count = int(slide_count); state.current_slide = 1
    state.scope_mode, state.active_scope, state.scope_input = "all", tuple(range(1, state.slide_count + 1)), ""
    return state

def choose_file_cancel(state: PptxWorkspaceState) -> PptxWorkspaceState:
    return state

def normalize_scope(mode: str, text: str, slide_count: int) -> tuple[int, ...]:
    """Validate and normalize a PPTX scope without touching workspace state."""
    mode = str(mode).lower()
    if slide_count < 1:
        raise ValueError("No slides are available")
    if mode == "all":
        return tuple(range(1, slide_count + 1))
    if mode == "first":
        return (1,)
    if mode not in {"selected", "range"}:
        raise ValueError("Unknown slide scope")
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("Enter slide numbers")
    values: set[int] = set()
    for part in raw.split(","):
        token = part.strip()
        if not re.fullmatch(r"\d+(?:-\d+)?", token):
            raise ValueError("Invalid slide selection")
        ends = [int(value) for value in token.split("-")]
        if len(ends) == 2 and ends[0] > ends[1]:
            raise ValueError("Slide range must be ascending")
        if any(value < 1 or value > slide_count for value in ends):
            raise ValueError(f"Slides must be between 1 and {slide_count}")
        values.update(range(ends[0], ends[-1] + 1))
    if mode == "range" and any("-" not in part.strip() for part in raw.split(",")):
        raise ValueError("Range requires slide intervals")
    return tuple(sorted(values))

def apply_pptx_scope_event(state: PptxWorkspaceState, event: "PptxEvent", value=None) -> PptxWorkspaceState:
    """Apply scope transitions; draft text never changes active_scope."""
    if event == PptxEvent.SCOPE_MODE:
        mode = str(value).lower()
        if mode not in {"all", "first", "selected", "range"}:
            raise ValueError("Unknown slide scope")
        state.scope_mode = mode
        if mode in {"all", "first"}:
            state.active_scope = normalize_scope(mode, state.scope_input, state.slide_count)
            state.current_slide = state.active_scope[0]
        return state
    if event == PptxEvent.SCOPE_TEXT_CHANGED:
        state.scope_input = str(value or "")
        return state
    if event == PptxEvent.SCOPE_UPDATE:
        mode, text = state.scope_mode, str(value if value is not None else state.scope_input)
        scope = normalize_scope(mode, text, state.slide_count)
        state.scope_input = text
        state.active_scope = scope
        state.current_slide = scope[0]
        return state
    if event in {PptxEvent.PREVIEW_PREVIOUS, PptxEvent.PREVIEW_NEXT}:
        if state.loaded:
            delta = -1 if event == PptxEvent.PREVIEW_PREVIOUS else 1
            state.current_slide = max(1, min(state.slide_count, state.current_slide + delta))
        return state
    raise ValueError(f"Unsupported PPTX scope event: {event}")

def project_file(state: PptxWorkspaceState, translate=None) -> dict[str, Any]:
    t = translate or (lambda key, **values: {"pptx.no_file": "No PowerPoint selected", "pptx.selected": "PowerPoint loaded", "document.summary.slides": "{size} · {count} slides"}.get(key, key).format(**values))
    if not state.loaded: return {"status": t("pptx.no_file"), "filename": None, "details": None}
    size = state.file_size_bytes or 0; value = float(size); unit = "B"
    for candidate in ("B", "KB", "MB", "GB"):
        unit = candidate
        if value < 1024 or candidate == "GB": break
        value /= 1024
    return {"status": t("pptx.selected", name=state.display_filename), "filename": state.display_filename, "details": t("document.summary.slides", size=f"{value:.1f} {unit}", count=state.slide_count)}

def project_badge(state: PptxWorkspaceState, repository) -> dict[str, Any]:
    badge_id = state.badge.badge_id or "AI Assisted"; asset = None
    candidates = repository.display_badges() if hasattr(repository, "display_badges") else repository.all()
    for candidate in candidates:
        if candidate.name == badge_id or repository.display_name(candidate.name) == badge_id: asset = candidate; break
    return {"badge_id": badge_id, "display_name": repository.display_name(asset.name) if asset else badge_id, "asset": asset, "enabled": state.badge.enabled, "position": state.badge.position, "size": state.badge.size, "margin": state.badge.margin, "opacity": state.badge.opacity}


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
    input_value: Any = None


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
