"""Stateless right-side preview presentation shell."""
from typing import Any
import customtkinter as ctk


class PreviewShell:
    def __init__(self, parent: Any, *, title: str = "PREVIEW"):
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.grid_columnconfigure(0, weight=1); self.frame.grid_rowconfigure(1, weight=1)
        self.heading = ctk.CTkLabel(self.frame, text=title, font=ctk.CTkFont(weight="bold"))
        self.heading.grid(row=0, column=0, padx=8, pady=(4, 2), sticky="w")
        self.viewport = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.viewport.grid(row=1, column=0, sticky="nsew")
        self.viewport.grid_columnconfigure(0, weight=1); self.viewport.grid_rowconfigure(0, weight=1)
