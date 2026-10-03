"""Minimal authoritative PPTX workspace used to prove the shell mount path."""

from __future__ import annotations

import customtkinter as ctk
from .workspace_ui import build_workspace_control_template

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
        if self.app is None:
            ctk.CTkLabel(self.root, text="PowerPoint", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, padx=24, pady=24, sticky="nw")
        else:
            app = self.app
            self.root.grid_columnconfigure(0, weight=0, minsize=300)
            self.root.grid_columnconfigure(1, weight=1)
            app.pptx_badge_enabled_var = ctk.BooleanVar(value=app.pptx_state.badge.enabled)
            view = build_workspace_control_template(
                self.root, format_label="PowerPoint", choose_command=app.choose_pptx_phase2,
                save_command=app.process_pptx, scope_label="SLIDES", scope_command=app.change_pptx_scope_mode,
                scope_update=app.update_pptx_scope, badge_enabled_var=app.pptx_badge_enabled_var,
                badge_var=app.badge_display_var, badge_values=list(app.badge_display_to_file) or ["AI Assisted"],
                badge_callbacks=(app.pptx_visual_changed, app.select_badge_display, app.pptx_visual_changed,
                                 app.pptx_visual_changed, app.pptx_visual_changed, app.pptx_visual_changed),
                logo_enabled_var=app.logo_enabled_var,
                logo_callbacks=(app.pptx_visual_changed, app.choose_logo, app.pptx_visual_changed,
                                app.pptx_visual_changed, app.pptx_visual_changed, app.pptx_visual_changed),
                position_values=list(app.position_display_to_value),
            )
            view["root"].grid(row=0, column=0, sticky="nw")
            app.pptx_controls_view = view
            app.pptx_choose_button, app.pptx_process_button = view["choose"], view["save"]
            app.pptx_file_label = view["file_label"]
            app.pptx_preview_host = ctk.CTkFrame(self.root, fg_color="transparent")
            app.pptx_preview_host.grid(row=0, column=1, padx=(24, 0), sticky="nsew")
            app.pptx_preview_label = ctk.CTkLabel(app.pptx_preview_host, text="PowerPoint preview")
            app.pptx_preview_label.grid(row=0, column=0, padx=12, pady=12)
        self.mounted = True

    def unmount(self) -> None:
        if self.root is not None and self.root.winfo_exists():
            self.root.destroy()
        self.root = None
        self.mounted = False

    def clear_runtime_state(self) -> None:
        self.unmount()
