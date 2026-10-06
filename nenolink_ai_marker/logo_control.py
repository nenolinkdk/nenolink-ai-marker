"""Stateless Own Logo presentation control."""
from typing import Any, Callable, Iterable
import customtkinter as ctk


class LogoProjection:
    def __init__(self, *, enabled=False, filename="", mode="entire", modes=(), position="top-left", fixed_position=True, size=15, margin=20, opacity=100, labels=None):
        self.enabled = bool(enabled); self.filename = filename or ""; self.mode = mode
        self.modes = tuple(modes); self.position = position; self.fixed_position = fixed_position
        self.size = size; self.margin = margin; self.opacity = opacity; self.labels = labels or {}


class LogoControl:
    """Presentation-only logo controls; all policy is injected by the workspace."""
    def __init__(self, parent: Any, *, on_enabled: Callable[[bool], Any], on_choose: Callable[[], Any], on_mode: Callable[[str], Any] | None = None, on_size: Callable[[float], Any] | None = None, on_margin: Callable[[float], Any] | None = None, on_opacity: Callable[[float], Any] | None = None):
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.enabled_var = ctk.BooleanVar(value=False); self.mode_var = ctk.StringVar(value="entire")
        self.heading = ctk.CTkLabel(self.frame, text="OWN LOGO", font=ctk.CTkFont(weight="bold")); self.heading.grid(row=0, column=0, sticky="w")
        self.enabled_widget = ctk.CTkCheckBox(self.frame, text="Add own logo", variable=self.enabled_var, command=lambda: on_enabled(bool(self.enabled_var.get()))); self.enabled_widget.grid(row=1, column=0, sticky="w")
        self.choose_button = ctk.CTkButton(self.frame, text="Choose logo", command=on_choose, width=140); self.choose_button.grid(row=2, column=0, sticky="w")
        self.filename_label = ctk.CTkLabel(self.frame, text="No logo selected", anchor="w"); self.filename_label.grid(row=3, column=0, sticky="ew")
        self.mode_widget = ctk.CTkOptionMenu(self.frame, variable=self.mode_var, values=["Front", "Entire", "Back"], command=on_mode or (lambda _value: None), width=140); self.mode_widget.grid(row=4, column=0, sticky="w")
        self.position_label = ctk.CTkLabel(self.frame, text="Position: Top left"); self.position_label.grid(row=5, column=0, sticky="w")
        self.size_widget = ctk.CTkSlider(self.frame, from_=1, to=100, command=on_size or (lambda _value: None)); self.size_widget.grid(row=6, column=0, sticky="ew")
        self.margin_widget = ctk.CTkSlider(self.frame, from_=0, to=250, command=on_margin or (lambda _value: None)); self.margin_widget.grid(row=7, column=0, sticky="ew")
        self.opacity_widget = ctk.CTkSlider(self.frame, from_=0, to=100, command=on_opacity or (lambda _value: None)); self.opacity_widget.grid(row=8, column=0, sticky="ew")
        self.frame.grid_columnconfigure(0, weight=1)

    def project(self, projection: LogoProjection) -> None:
        self.enabled_var.set(projection.enabled); self.mode_var.set(projection.mode)
        self.mode_widget.configure(values=list(projection.modes or ("Front", "Entire", "Back")))
        self.mode_widget.configure(state="normal" if projection.modes else "disabled")
        self.position_label.configure(text=f"Position: {projection.position.replace('-', ' ').title()}")
        self.filename_label.configure(text=projection.filename or "No logo selected")
        self.size_widget.set(projection.size); self.margin_widget.set(projection.margin); self.opacity_widget.set(projection.opacity)
