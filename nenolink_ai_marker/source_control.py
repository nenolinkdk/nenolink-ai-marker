"""Stateless source/file presentation for workspace control columns."""
from typing import Any, Callable
import customtkinter as ctk

class SourceControl:
    def __init__(self, parent: Any, *, choose_command: Callable[[], Any], choose_label: str = "Choose file", width: int = 280, compact: bool = False) -> None:
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.compact = compact
        columns = 2 if compact else 1
        self.choose_button = ctk.CTkButton(self.frame, text=choose_label, command=choose_command, width=min(width, 160) if compact else width)
        self.choose_button.grid(row=0, column=0, sticky="ew")
        self.filename_label = ctk.CTkLabel(self.frame, text="No file selected", anchor="w", justify="left", wraplength=width)
        self.filename_label.grid(row=1, column=0, columnspan=columns, pady=(3, 0), sticky="ew")
        self.metadata_label = ctk.CTkLabel(self.frame, text="", anchor="w", justify="left", wraplength=width, text_color="gray60")
        self.metadata_label.grid(row=2, column=0, columnspan=columns, pady=(1, 3), sticky="ew")
        for column in range(columns): self.frame.grid_columnconfigure(column, weight=1)

    def project(self, *, filename: str, metadata: str = "", empty_text: str = "No file selected") -> None:
        self.filename_label.configure(text=filename or empty_text)
        self.metadata_label.configure(text=metadata)

    def set_label(self, label: str) -> None:
        self.choose_button.configure(text=label)
