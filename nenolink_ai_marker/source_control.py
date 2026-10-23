"""Stateless source/file presentation for workspace control columns."""
from typing import Any, Callable
import customtkinter as ctk
from .workspace_control_panel import FILE_CHOOSE_WIDTH, FILE_SAVE_WIDTH, FILE_ACTION_GAP

class SourceControl:
    def __init__(self, parent: Any, *, choose_command: Callable[[], Any], choose_label: str = "Choose file", empty_label: str = "No file selected", width: int = 280, compact: bool = False) -> None:
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.compact = compact
        self.frame.grid_columnconfigure(0, weight=1)
        self.action_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.action_row.grid(row=0, column=0, sticky="ew")
        self.action_row.grid_columnconfigure(0, weight=3)
        if compact:
            self.action_row.grid_columnconfigure(1, weight=2)
        self.choose_button = ctk.CTkButton(
            self.action_row, text=choose_label, command=choose_command,
            width=FILE_CHOOSE_WIDTH if compact else width,
        )
        self.choose_button.grid(row=0, column=0, padx=(0, FILE_ACTION_GAP) if compact else 0, sticky="ew")
        self.filename_label = ctk.CTkLabel(self.frame, text=empty_label, anchor="w", justify="left", wraplength=width)
        self.filename_label.grid(row=1, column=0, pady=(2, 0), sticky="ew")
        self.metadata_label = ctk.CTkLabel(self.frame, text="", anchor="w", justify="left", wraplength=width, text_color="gray60")
        self.metadata_label.grid(row=2, column=0, pady=(0, 2), sticky="ew")
        self.metadata_label.grid_remove()

    def place_save_control(self, save_control) -> None:
        """Place the separate SaveControl beside Choose in the shared action row."""
        if not self.compact:
            raise ValueError("side-by-side Save requires compact SourceControl")
        save_control.button.configure(width=FILE_SAVE_WIDTH)
        save_control.button.grid(row=0, column=1, sticky="ew")

    def project(self, *, filename: str, metadata: str = "", empty_text: str = "No file selected") -> None:
        self.filename_label.configure(text=filename or empty_text)
        self.metadata_label.configure(text=metadata)
        if metadata:
            self.metadata_label.grid(row=2, column=0, pady=(0, 2), sticky="ew")
        else:
            self.metadata_label.grid_remove()

    def set_label(self, label: str) -> None:
        self.choose_button.configure(text=label)
