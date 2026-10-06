"""Stateless projected AI-badge controls.

The owning workspace supplies projections and callbacks; this component never
reads application state or selects a transition.
"""
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional
import customtkinter as ctk

@dataclass(frozen=True)
class BadgeProjection:
    enabled: bool = False
    selected: str = ""
    choices: tuple[str, ...] = ()
    image: Any = None
    position: Optional[str] = None
    size: Optional[float] = None
    margin: Optional[float] = None
    opacity: Optional[float] = None
    enabled_label: str = ""

class BadgeControl:
    """A presentation-only badge control with injected callbacks."""
    def __init__(self, parent: Any, *, on_enabled_changed: Callable[[bool], Any] | None = None,
                 on_badge_selected: Callable[[str], Any] | None = None,
                 on_position_changed: Callable[[str], Any] | None = None,
                 on_size_changed: Callable[[float], Any] | None = None,
                 on_margin_changed: Callable[[float], Any] | None = None,
                 on_opacity_changed: Callable[[float], Any] | None = None,
                 show_position: bool = True, show_size: bool = True,
                 show_margin: bool = True, show_opacity: bool = True) -> None:
        self._on_enabled_changed = on_enabled_changed
        self._on_badge_selected = on_badge_selected
        self._on_position_changed = on_position_changed
        self._on_size_changed = on_size_changed
        self._on_margin_changed = on_margin_changed
        self._on_opacity_changed = on_opacity_changed
        self.capabilities = (show_position, show_size, show_margin, show_opacity)
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.enabled_var = ctk.BooleanVar(value=False)
        self.selector_var = ctk.StringVar(value="")
        self.enabled_widget = ctk.CTkCheckBox(self.frame, variable=self.enabled_var, command=self._enabled)
        self.selector_widget = ctk.CTkOptionMenu(self.frame, variable=self.selector_var, values=["—"], command=self._selected)
        self.graphic_widget = ctk.CTkLabel(self.frame, text="")
        self.enabled_widget.grid(row=0, column=0, sticky="w")
        self.selector_widget.grid(row=1, column=0, sticky="ew")
        self.graphic_widget.grid(row=2, column=0, sticky="w")

    def _enabled(self):
        if self._on_enabled_changed: self._on_enabled_changed(bool(self.enabled_var.get()))
    def _selected(self, value):
        if self._on_badge_selected: self._on_badge_selected(value)
    def project(self, projection: BadgeProjection) -> None:
        self.enabled_var.set(projection.enabled)
        self.enabled_widget.configure(text=projection.enabled_label)
        self.selector_widget.configure(values=list(projection.choices))
        self.selector_var.set(projection.selected)
        self.graphic_widget.configure(image=projection.image, text=projection.selected if projection.image is None else "")
    def set_enabled(self, enabled: bool) -> None: self.enabled_var.set(enabled)
    def set_choices(self, choices: Iterable[str]) -> None: self.selector_widget.configure(values=list(choices))
    def set_selected(self, selected: str) -> None: self.selector_var.set(selected)
