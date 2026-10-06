"""Stateless presentation for a workspace Save action."""
from typing import Any, Callable
import customtkinter as ctk

class SaveControl:
    """Own only a button widget and forward the supplied callback."""
    def __init__(self, parent: Any, *, command: Callable[[], Any], label: str = "Save", **button_options: Any) -> None:
        self.button = ctk.CTkButton(parent, text=label, command=command, **button_options)
    def set_enabled(self, enabled: bool) -> None:
        self.button.configure(state="normal" if enabled else "disabled")
    def set_label(self, label: str) -> None:
        self.button.configure(text=label)
    def configure(self, **options: Any) -> None:
        self.button.configure(**options)
