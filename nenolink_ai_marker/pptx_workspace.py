"""Authoritative, incremental PPTX workspace.

Phase 1 deliberately implements only FILE and AI BADGE.  The shell owns
navigation; this class owns its runtime state and projects it into widgets.
"""

from __future__ import annotations

from pathlib import Path
import customtkinter as ctk
from PIL import Image
from tkinter import filedialog
from .models import MarkerSettings
from .pptx_state import (PptxWorkspaceState, PptxEvent, PptxEventReceipt, apply_pptx_visual_event,
                          apply_pptx_scope_event, choose_file_success, project_file, project_badge)
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
        return self.state.loaded

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
        ctk.CTkLabel(controls, text="SLIDES", font=ctk.CTkFont(weight="bold")).grid(row=4, column=0, padx=12, pady=(4, 2), sticky="w")
        self.scope_var = ctk.StringVar(value="All")
        self.scope_menu = ctk.CTkOptionMenu(controls, variable=self.scope_var, values=["All", "First", "Selected", "Range"], command=self._scope_mode, width=190)
        self.scope_menu.grid(row=5, column=0, padx=12, pady=2, sticky="w")
        self.scope_input_var = ctk.StringVar(value="")
        self.scope_input = ctk.CTkEntry(controls, textvariable=self.scope_input_var, width=190, placeholder_text="e.g. 2,4-6,9")
        self.scope_input.grid(row=6, column=0, padx=12, pady=2, sticky="w")
        self.scope_input.bind("<KeyRelease>", lambda _event: self._scope_text_changed())
        self.scope_update = ctk.CTkButton(controls, text="Update", command=self._scope_update, width=90)
        self.scope_update.grid(row=7, column=0, padx=12, pady=2, sticky="w")
        self.scope_status = ctk.CTkLabel(controls, text="All slides", anchor="w")
        self.scope_status.grid(row=8, column=0, padx=12, pady=(2, 8), sticky="w")
        ctk.CTkLabel(controls, text="AI BADGE", font=ctk.CTkFont(weight="bold")).grid(row=9, column=0, padx=12, pady=(4, 2), sticky="w")
        self.enabled_var = ctk.BooleanVar(value=self.state.badge.enabled)
        ctk.CTkCheckBox(controls, text="Add AI badge", variable=self.enabled_var, command=lambda: self._dispatch(PptxEvent.BADGE_ENABLE, self.enabled_var.get())).grid(row=10, column=0, padx=12, pady=2, sticky="w")
        names = list(getattr(getattr(self.app, "badge_display_to_file", None), "keys", lambda: [])()) or ["AI Assisted"]
        self.badge_var = ctk.StringVar(value="AI Assisted" if "AI Assisted" in names else names[0])
        self.badge_menu = ctk.CTkOptionMenu(controls, variable=self.badge_var, values=names, command=lambda v: self._dispatch(PptxEvent.BADGE_SELECT, v), width=190); self.badge_menu.grid(row=11, column=0, padx=12, pady=2, sticky="w")
        self.badge_visual = ctk.CTkLabel(controls, text=self.badge_var.get(), anchor="w", height=62); self.badge_visual.grid(row=12, column=0, padx=12, pady=(2, 8), sticky="w")
        self.construction_receipt.badge_section_created = True
        self._build_visual_controls(controls)
        self.preview_label = ctk.CTkLabel(preview, text="PowerPoint preview", fg_color=("gray92", "gray13"), height=260); self.preview_label.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        self.previous_button = ctk.CTkButton(preview, text="◀", width=40, command=lambda: self._change_slide(-1)); self.previous_button.grid(row=1, column=0, sticky="w", padx=12)
        self.slide_status = ctk.CTkLabel(preview, text="—"); self.slide_status.grid(row=1, column=0)
        self.next_button = ctk.CTkButton(preview, text="▶", width=40, command=lambda: self._change_slide(1)); self.next_button.grid(row=1, column=0, sticky="e", padx=12)
        self.save_button = ctk.CTkButton(controls, text="Save Marked PowerPoint", command=self._save_as, width=190); self.save_button.grid(row=30, column=0, padx=12, pady=8, sticky="w")
        self.construction_receipt.preview_host_created = True
        preview.grid_columnconfigure(0, weight=1); preview.grid_rowconfigure(0, weight=1)
        self._project_badge()
        self._project_file()
        self._project_scope()
        self._dispatch(PptxEvent.BADGE_SELECT, self.badge_var.get(), record_only=True)
        self.state_token_reached = True
        self.receipts.record(self.construction_receipt)
        self.mounted = True

    def _build_visual_controls(self, controls):
        row = 13
        ctk.CTkLabel(controls, text="Badge Position").grid(row=row, column=0, padx=12, pady=1, sticky="w")
        positions = ["top-left", "top-right", "bottom-left", "bottom-right", "center"]
        self.badge_position_var = ctk.StringVar(value=self.state.badge.position)
        ctk.CTkOptionMenu(controls, variable=self.badge_position_var, values=positions, command=lambda v: self._dispatch(PptxEvent.BADGE_POSITION, v), width=190).grid(row=row+1, column=0, padx=12, pady=1, sticky="w")
        self._slider(controls, row+2, "Badge Size", "badge", "size", 1, 100, self.state.badge.size)
        self._slider(controls, row+3, "Badge Margin", "badge", "margin", 0, 250, self.state.badge.margin)
        self._slider(controls, row+4, "Badge Opacity", "badge", "opacity", 0, 100, self.state.badge.opacity)
        ctk.CTkLabel(controls, text="OWN LOGO", font=ctk.CTkFont(weight="bold")).grid(row=row+5, column=0, padx=12, pady=(6,2), sticky="w")
        self.logo_enabled_var = ctk.BooleanVar(value=self.state.logo.enabled)
        ctk.CTkCheckBox(controls, text="Add own logo", variable=self.logo_enabled_var, command=lambda: self._dispatch(PptxEvent.LOGO_ENABLE, self.logo_enabled_var.get())).grid(row=row+6, column=0, padx=12, pady=1, sticky="w")
        ctk.CTkButton(controls, text="Choose Logo", command=self._choose_logo, width=120).grid(row=row+7, column=0, padx=12, pady=1, sticky="w")
        self.logo_label = ctk.CTkLabel(controls, text="No logo selected", anchor="w"); self.logo_label.grid(row=row+8, column=0, padx=12, pady=1, sticky="w")
        self.logo_position_var = ctk.StringVar(value=self.state.logo.position)
        ctk.CTkOptionMenu(controls, variable=self.logo_position_var, values=positions, command=lambda v: self._dispatch(PptxEvent.LOGO_POSITION, v), width=190).grid(row=row+9, column=0, padx=12, pady=1, sticky="w")
        self._slider(controls, row+10, "Logo Size", "logo", "size", 1, 100, self.state.logo.size)
        self._slider(controls, row+11, "Logo Margin", "logo", "margin", 0, 250, self.state.logo.margin)
        self._slider(controls, row+12, "Logo Opacity", "logo", "opacity", 0, 100, self.state.logo.opacity)

    def _slider(self, host, row, label, group, field, low, high, value):
        var = ctk.IntVar(value=value); setattr(self, f"{group}_{field}_var", var)
        value_label = ctk.CTkLabel(host, text=f"{label}: {value}", anchor="w"); value_label.grid(row=row, column=0, padx=12, pady=1, sticky="w")
        setattr(self, f"{group}_{field}_label", value_label)
        slider = ctk.CTkSlider(host, from_=low, to=high, variable=var, command=lambda v: self._slider_event(group, field, v), width=190)
        slider.grid(row=row+1, column=0, padx=12, pady=1, sticky="w")

    def _slider_event(self, group, field, value):
        event = getattr(PptxEvent, f"{group.upper()}_{field.upper()}")
        normalized = round(float(value))
        getattr(self, f"{group}_{field}_label").configure(text=f"{field.title() if field != 'opacity' else 'Opacity'}: {normalized}{'%' if field in {'size','opacity'} else ' px'}")
        self._dispatch(event, normalized)

    def _choose_logo(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg")])
        if path:
            self._dispatch(PptxEvent.LOGO_CHOOSE, path)
            self.logo_label.configure(text=Path(path).name)

    def _change_slide(self, delta):
        event = PptxEvent.PREVIEW_NEXT if delta > 0 else PptxEvent.PREVIEW_PREVIOUS
        apply_pptx_scope_event(self.state, event)
        self._render_preview()

    def _render_preview(self):
        if not self.state.loaded:
            return
        renderer = getattr(self.app, "pptx_preview_renderer", None)
        repository = getattr(self.app, "badges", None)
        if not renderer or not repository:
            return
        try:
            badge = project_badge(self.state, repository).get("asset") if self.state.badge.enabled and self.state.current_slide in self.state.active_scope else None
            settings = MarkerSettings(badge_name=self.state.badge.badge_id, position=self.state.badge.position, size_percent=self.state.badge.size, margin=self.state.badge.margin, opacity=self.state.badge.opacity, logo_enabled=self.state.logo.enabled, logo_position=self.state.logo.position, logo_size_percent=self.state.logo.size, logo_margin=self.state.logo.margin, logo_opacity=self.state.logo.opacity)
            result = renderer.render(self.state.path, self.state.current_slide, badge, settings, self.state.logo.path if self.state.logo.enabled else None)
            self.preview_photo = ctk.CTkImage(result.image, size=result.image.size)
            self.preview_label.configure(image=self.preview_photo, text="")
            self.slide_status.configure(text=f"{result.slide_number} / {result.slide_count}")
            self.previous_button.configure(state="normal" if self.state.current_slide > 1 else "disabled")
            self.next_button.configure(state="normal" if self.state.current_slide < self.state.slide_count else "disabled")
        except Exception as error:
            self.preview_label.configure(image=None, text=f"Could not render slide: {error}")

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
            self._project_scope()
            self._project_file()
            self._render_preview()
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
        self._render_preview()

    def _save_as(self):
        """Delegate only the output side effect; state remains workspace-owned."""
        handler = getattr(self.app, "process_pptx", None)
        if callable(handler):
            handler()

    def _scope_mode(self, value):
        mode = str(value).lower()
        try:
            apply_pptx_scope_event(self.state, PptxEvent.SCOPE_MODE, mode)
            self._scope_receipt(PptxEvent.SCOPE_MODE, mode)
            self._project_scope()
        except ValueError as error:
            self.scope_status.configure(text=str(error))

    def _scope_update(self):
        value = self.scope_input_var.get()
        before = self.state.active_scope
        try:
            apply_pptx_scope_event(self.state, PptxEvent.SCOPE_TEXT_CHANGED, value)
            apply_pptx_scope_event(self.state, PptxEvent.SCOPE_UPDATE, value)
            self._scope_receipt(PptxEvent.SCOPE_UPDATE, value)
            self._project_scope()
        except ValueError as error:
            self.state.active_scope = before
            self.scope_status.configure(text=str(error))

    def _scope_text_changed(self):
        value = self.scope_input_var.get()
        apply_pptx_scope_event(self.state, PptxEvent.SCOPE_TEXT_CHANGED, value)
        self._scope_receipt(PptxEvent.SCOPE_TEXT_CHANGED, value)

    def _scope_receipt(self, event, value):
        self.state_token_reached = True
        self.receipts.record({"layer": "pptx", "event": "SCOPE_EVENT", "scope_event": event.value, "value": value})
        self.receipts.record({"layer": "pptx", "event": "SCOPE_REDUCER_APPLIED", "scope_mode": self.state.scope_mode})
        self.receipts.record({"layer": "pptx", "event": "SCOPE_STATE_UPDATED", "active_scope": self.state.active_scope})
        self.receipts.record({"layer": "pptx", "event": "SCOPE_PROJECTED", "result": "ok"})
        self.receipts.record({"layer": "pptx", "event": "SCOPE_WIDGETS_UPDATED", "result": "ok"})

    def _project_scope(self):
        if hasattr(self, "scope_var"):
            self.scope_var.set(self.state.scope_mode.title())
            self.scope_input_var.set(self.state.scope_input)
            self.scope_status.configure(text=f"{len(self.state.active_scope)} slide(s) selected")

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
        self.state.clear()
        self.unmount()
