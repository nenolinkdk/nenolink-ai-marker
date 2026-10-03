"""Minimal authoritative PPTX workspace used to prove the shell mount path."""

from __future__ import annotations

import customtkinter as ctk


class PptxWorkspace:
    def __init__(self) -> None:
        self.root = None
        self.mounted = False

    def has_active_work(self) -> bool:
        return False

    def mount(self, content_host) -> None:
        for child in content_host.winfo_children():
            child.destroy()
        self.root = ctk.CTkFrame(content_host, fg_color="transparent")
        self.root.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.root, text="PowerPoint", font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, padx=24, pady=24, sticky="nw"
        )
        self.mounted = True

    def unmount(self) -> None:
        if self.root is not None and self.root.winfo_exists():
            self.root.destroy()
        self.root = None
        self.mounted = False

    def clear_runtime_state(self) -> None:
        self.unmount()
