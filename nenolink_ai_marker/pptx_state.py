"""Authoritative internal state for the PPTX workspace.

The outer content FSM remains owned by ShellController.  This model keeps
physical preview, processing scope, badge and logo state orthogonal so widgets
cannot accidentally become a second state owner.
"""
from dataclasses import dataclass, field
from pathlib import Path


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
