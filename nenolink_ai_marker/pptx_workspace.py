"""Authoritative, incremental PPTX workspace.

Phase 1 deliberately implements only FILE and AI BADGE.  The shell owns
navigation; this class owns its runtime state and projects it into widgets.
"""

from __future__ import annotations

from pathlib import Path
import customtkinter as ctk
from PIL import Image
from .pptx_state import (PptxWorkspaceState, PptxEvent, PptxEventReceipt, apply_pptx_visual_event,
                          choose_file_success, project_file, project_badge)
from .diagnostic_receipts import ReceiptLog


class PptxConstructionReceipt:
    def __init__(self) -> None:
        self.implementation = "pptx_phase1_clean"
        self.implementation_generation = 2
        self.workspace_created = False
        self.file_section_created = False
        self.badge_section_created = False
        self.preview_host_created = False
        self.legacy_pptx_ui_used = False
        self.legacy_document_ui_used = False
        self.pdf_ui_used = False
PPTX_MOUNT_TOKEN = "NENOLINK_PPTX_MOUNT_V103"
PPTX_STATE_TOKEN = "NENOLINK_PPTX_STATE_V103"


class PptxWorkspace:
    def __init__(self, app=None) -> None:
        self.app = app
        self.root = None
        self.mounted = False
        self.mount_token_reached = False
        self.state_token_reached = False
        self.state = PptxWorkspaceState()
        self.last_receipt = None
        self.construction_receipt = None
        self.receipts = ReceiptLog()

    def has_active_work(self) -> bool:
        return False

    def mount(self, content_host) -> None:
        for child in content_host.winfo_children():
            child.destroy()
        self.root = ctk.CTkFrame(content_host, fg_color="transparent")
        self.root.grid(row=0, column=0, sticky="nsew")
        self.root.grid_columnconfigure(0, weight=0, minsize=320)
        self.root.grid_columnconfigure(1, weight=1)
        self.mount_token_reached = True
        self.construction_receipt = PptxConstructionReceipt()
        self.construction_receipt.authoritative_state_created = True
        self.construction_receipt.workspace_created = True
        controls = ctk.CTkFrame(self.root, fg_color=("gray92", "gray17")); controls.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        preview = ctk.CTkFrame(self.root, fg_color="transparent"); preview.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")
        ctk.CTkLabel(controls, text="PowerPoint", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, padx=12, pady=(10, 8), sticky="w")
        ctk.CTkLabel(controls, text="FILE", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, padx=12, pady=(4, 2), sticky="w")
        ctk.CTkButton(controls, text="Choose PowerPoint", command=self._choose_file, width=190).grid(row=2, column=0, padx=12, pady=2, sticky="w")
        self.file_label = ctk.CTkLabel(controls, text="No PowerPoint selected", anchor="w"); self.file_label.grid(row=3, column=0, padx=12, pady=(2, 8), sticky="w")
        self.construction_receipt.file_section_created = True
        ctk.CTkLabel(controls, text="AI BADGE", font=ctk.CTkFont(weight="bold")).grid(row=4, column=0, padx=12, pady=(4, 2), sticky="w")
        self.enabled_var = ctk.BooleanVar(value=self.state.badge.enabled)
        ctk.CTkCheckBox(controls, text="Add AI badge", variable=self.enabled_var, command=lambda: self._dispatch(PptxEvent.BADGE_ENABLE, self.enabled_var.get())).grid(row=5, column=0, padx=12, pady=2, sticky="w")
        names = list(getattr(getattr(self.app, "badge_display_to_file", None), "keys", lambda: [])()) or ["AI Assisted"]
        self.badge_var = ctk.StringVar(value="AI Assisted" if "AI Assisted" in names else names[0])
        self.badge_menu = ctk.CTkOptionMenu(controls, variable=self.badge_var, values=names, command=lambda v: self._dispatch(PptxEvent.BADGE_SELECT, v), width=190); self.badge_menu.grid(row=6, column=0, padx=12, pady=2, sticky="w")
        self.badge_visual = ctk.CTkLabel(controls, text=self.badge_var.get(), anchor="w", height=62); self.badge_visual.grid(row=7, column=0, padx=12, pady=(2, 8), sticky="w")
        self.construction_receipt.badge_section_created = True
        self.preview_label = ctk.CTkLabel(preview, text="PowerPoint preview", fg_color=("gray92", "gray13"), height=260); self.preview_label.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        self.construction_receipt.preview_host_created = True
        preview.grid_columnconfigure(0, weight=1); preview.grid_rowconfigure(0, weight=1)
        self._project_badge()
        self._project_file()
        self._dispatch(PptxEvent.BADGE_SELECT, self.badge_var.get(), record_only=True)
        self.state_token_reached = True
        self.receipts.record(self.construction_receipt)
        self.mounted = True

    def _choose_file(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(filetypes=[("PowerPoint", "*.pptx")])
        self.receipts.record({"layer": "pptx", "event": "FILE_DIALOG_RESULT", "result": "cancel" if not path else "path_selected"})
        if not path: return
        metrics = getattr(self.app, "pptx_processor", None)
        try:
            info = metrics.document_metrics(Path(path)) if metrics and hasattr(metrics, "document_metrics") else None
            count = getattr(info, "item_count", 0) or getattr(info, "slide_count", 0)
        except Exception as error:
            self.receipts.record({"layer": "pptx", "event": "FILE_METRICS_FAILED", "result": "error", "exception_type": type(error).__name__, "error": str(error)[:200]})
            if hasattr(self, "file_label"): self.file_label.configure(text="Could not read PowerPoint file")
            count = 0
        if count:
            self.receipts.record({"layer": "pptx", "event": "CHOOSE_FILE_SUCCESS", "owner": "file_reducer", "result": "accepted"})
            choose_file_success(self.state, Path(path), count)
            self.receipts.record({"layer": "pptx", "event": "FILE_REDUCER_APPLIED", "owner": "file_reducer", "result": "ok"})
            self.receipts.record({"layer": "pptx", "event": "FILE_STATE_UPDATED", "selected_file": self.state.display_filename, "file_size_bytes": self.state.file_size_bytes, "slide_count": self.state.slide_count})
            self._project_file()
            self.receipts.record({"layer": "pptx", "event": "FILE_PROJECTED", "result": "ok"})
            self.receipts.record({"layer": "pptx", "event": "FILE_WIDGETS_UPDATED", "result": "ok"})

    def _dispatch(self, event, value, record_only=False):
        before = {"path": self.state.path, "current_slide": self.state.current_slide,
                  "active_scope": self.state.active_scope, "badge": self.state.badge.__dict__.copy(),
                  "logo": self.state.logo.__dict__.copy()}
        apply_pptx_visual_event(self.state, event, value)
        self.state_token_reached = True
        self.last_receipt = PptxEventReceipt(event, before, {"badge": self.state.badge.__dict__.copy()}, (event.value,), ("path", "current_slide", "active_scope", "logo"), True, value)
        self.receipts.record(self.last_receipt)
        self._project_badge()

    def _project_badge(self):
        if hasattr(self, "badge_visual"):
            repository = getattr(self.app, "badges", None)
            if repository and (hasattr(repository, "display_badges") or hasattr(repository, "all")):
                model = project_badge(self.state, repository)
                self.badge_visual.configure(text=model["display_name"])
                asset = model.get("asset")
                if asset and asset.exists():
                    with Image.open(asset) as opened: image = opened.convert("RGBA")
                    image.thumbnail((110, 54), Image.Resampling.LANCZOS)
                    self.badge_photo = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
                    self.badge_visual.configure(image=self.badge_photo, compound="left")

    def _project_file(self):
        model = project_file(self.state)
        if hasattr(self, "file_label"):
            self.file_label.configure(text=model["status"] if not model["filename"] else f"{model['filename']}\n{model['details']}")

    def unmount(self) -> None:
        if self.root is not None and self.root.winfo_exists():
            self.root.destroy()
        self.root = None
        self.mounted = False

    def clear_runtime_state(self) -> None:
        self.unmount()
