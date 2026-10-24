"""Stateless Own Logo presentation control."""
from typing import Any, Callable, Iterable
import customtkinter as ctk
from .workspace_control_panel import (
    PARAM_LABEL_WIDTH, PARAM_PADX,
    PARAM_LABEL_PADY, PARAM_ROW_PADY, ParameterRow,
)


class LogoProjection:
    def __init__(self, *, enabled=False, filename="", mode="entire", modes=(), position="top-left", fixed_position=True, size=15, margin=20, opacity=100, labels=None):
        self.enabled = bool(enabled); self.filename = filename or ""; self.mode = mode
        self.modes = tuple(modes); self.position = position; self.fixed_position = fixed_position
        self.size = size; self.margin = margin; self.opacity = opacity; self.labels = labels or {}


class LogoControl:
    """Presentation-only logo controls; all policy is injected by the workspace."""
    def __init__(self, parent: Any, *, on_enabled: Callable[[bool], Any], on_choose: Callable[[], Any], on_mode: Callable[[str], Any] | None = None, show_mode: bool = False, on_size: Callable[[float], Any] | None = None, on_margin: Callable[[float], Any] | None = None, on_opacity: Callable[[float], Any] | None = None, labels=None):
        labels = labels or {}
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.enabled_var = ctk.BooleanVar(value=False)
        self.mode_var = ctk.StringVar(value="entire") if show_mode else None
        self.heading = ctk.CTkLabel(self.frame, text=labels.get("heading", "OWN LOGO"), font=ctk.CTkFont(weight="bold")); self.heading.grid(row=0, column=0, sticky="w")
        self.enabled_widget = ctk.CTkCheckBox(self.frame, text=labels.get("enabled", "Add own logo"), variable=self.enabled_var, command=lambda: on_enabled(bool(self.enabled_var.get()))); self.enabled_widget.grid(row=1, column=0, sticky="w")
        self.choose_button = ctk.CTkButton(self.frame, text=labels.get("choose", "Choose Logo"), command=on_choose, width=140); self.choose_button.grid(row=2, column=0, sticky="w")
        self.filename_label = ctk.CTkLabel(self.frame, text=labels.get("none", "No logo selected"), anchor="w"); self.filename_label.grid(row=3, column=0, sticky="ew")
        self.mode_widget = None
        next_row = 4
        if show_mode:
            self.mode_widget = ctk.CTkOptionMenu(self.frame, variable=self.mode_var, values=[labels.get("mode.front", "Front"), labels.get("mode.entire", "Entire"), labels.get("mode.back", "Back")], command=on_mode or (lambda _value: None), width=140)
            self.mode_widget.grid(row=next_row, column=0, sticky="w")
            next_row += 1
        self.position_label = ctk.CTkLabel(self.frame, text=labels.get("position", "Position: {position}").format(position=labels.get("position.top-left", "Top left")), width=PARAM_LABEL_WIDTH); self.position_label.grid(row=next_row, column=0, padx=PARAM_PADX, pady=PARAM_LABEL_PADY, sticky="w")
        self.size_row = ParameterRow(self.frame, text=labels.get("size", "Logo size: {value}%").format(value=15), start=1, end=100, value=15, command=on_size or (lambda _value: None)); self.size_row.frame.grid(row=next_row + 1, column=0, pady=PARAM_ROW_PADY, sticky="ew")
        self.margin_row = ParameterRow(self.frame, text=labels.get("margin", "Logo margin: {value} px").format(value=20), start=0, end=250, value=20, command=on_margin or (lambda _value: None)); self.margin_row.frame.grid(row=next_row + 2, column=0, pady=PARAM_ROW_PADY, sticky="ew")
        self.opacity_row = ParameterRow(self.frame, text=labels.get("opacity", "Logo opacity: {value}%").format(value=100), start=0, end=100, value=100, command=on_opacity or (lambda _value: None)); self.opacity_row.frame.grid(row=next_row + 3, column=0, pady=PARAM_ROW_PADY, sticky="ew")
        self.size_widget = self.size_row.slider; self.margin_widget = self.margin_row.slider; self.opacity_widget = self.opacity_row.slider
        self.frame.grid_columnconfigure(0, weight=1)

    def project(self, projection: LogoProjection) -> None:
        labels = projection.labels
        self.enabled_var.set(projection.enabled)
        if self.mode_widget is not None:
            self.mode_var.set(labels.get(f"mode.{projection.mode}", str(projection.mode).title()))
            self.mode_widget.configure(values=list(projection.modes or (labels.get("mode.front", "Front"), labels.get("mode.entire", "Entire"), labels.get("mode.back", "Back"))))
            self.mode_widget.configure(state="normal" if projection.modes else "disabled")
        self.heading.configure(text=labels.get("heading", "OWN LOGO"))
        self.enabled_widget.configure(text=labels.get("enabled", "Add own logo"))
        self.choose_button.configure(text=labels.get("choose", "Choose Logo"))
        position = labels.get(f"position.{projection.position}", projection.position.replace('-', ' ').title())
        self.position_label.configure(text=labels.get("position", "Position: {position}").format(position=position))
        self.filename_label.configure(text=projection.filename or labels.get("none", "No logo selected"))
        self.size_row.project(text=labels.get("size", "Logo size: {value}%").format(value=projection.size), value=projection.size)
        self.margin_row.project(text=labels.get("margin", "Logo margin: {value} px").format(value=projection.margin), value=projection.margin)
        self.opacity_row.project(text=labels.get("opacity", "Logo opacity: {value}%").format(value=projection.opacity), value=projection.opacity)
