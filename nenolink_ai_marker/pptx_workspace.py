"""Minimal authoritative PPTX workspace used to prove the shell mount path."""

from __future__ import annotations

import customtkinter as ctk
PPTX_MOUNT_TOKEN = "NENOLINK_PPTX_MOUNT_V103"
PPTX_STATE_TOKEN = "NENOLINK_PPTX_STATE_V103"


class PptxWorkspace:
    def __init__(self, app=None) -> None:
        self.app = app
        self.root = None
        self.mounted = False
        self.mount_token_reached = False
        self.state_token_reached = False

    def has_active_work(self) -> bool:
        return False

    def mount(self, content_host) -> None:
        for child in content_host.winfo_children():
            child.destroy()
        self.root = ctk.CTkFrame(content_host, fg_color="transparent")
        self.root.grid(row=0, column=0, sticky="nsew")
        self.mount_token_reached = True
        ctk.CTkLabel(self.root, text="PowerPoint", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, padx=24, pady=24, sticky="nw")
        self.mounted = True

    def unmount(self) -> None:
        if self.root is not None and self.root.winfo_exists():
            self.root.destroy()
        self.root = None
        self.mounted = False

    def clear_runtime_state(self) -> None:
        self.unmount()
