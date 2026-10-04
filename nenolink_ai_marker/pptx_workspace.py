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
from .document_preview_layout import fit_preview_size


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
        self.root.grid_columnconfigure(0, weight=0, minsize=360)
        self.root.grid_columnconfigure(1, weight=1)
        self.mount_token_reached = True
        self.construction_receipt = PptxConstructionReceipt()
        self.construction_receipt.authoritative_state_created = True
        self.construction_receipt.workspace_created = True
        controls = ctk.CTkScrollableFrame(self.root, width=360, fg_color=("gray92", "gray17")); controls.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        controls.bind("<MouseWheel>", lambda event: controls._parent_canvas.yview_scroll(-int(event.delta / 120), "units"))
        preview = ctk.CTkFrame(self.root, fg_color="transparent"); preview.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")
        self.preview_host = preview
        t = getattr(getattr(self.app, "translator", None), "text", lambda key: key)
        self.heading_label = ctk.CTkLabel(controls, text=t("content.powerpoint"), font=ctk.CTkFont(size=24, weight="bold")); self.heading_label.grid(row=0, column=0, padx=12, pady=(10, 8), sticky="w")
        self.file_heading = ctk.CTkLabel(controls, text=t("pptx.file_heading"), font=ctk.CTkFont(weight="bold")); self.file_heading.grid(row=1, column=0, padx=12, pady=(4, 2), sticky="w")
        self.choose_button = ctk.CTkButton(controls, text=t("pptx.choose"), command=self._choose_file, width=160); self.choose_button.grid(row=2, column=0, padx=(12, 4), pady=2, sticky="w")
        self.save_button = ctk.CTkButton(controls, text="Save", command=self._save_as, width=58); self.save_button.grid(row=2, column=1, padx=(4, 12), pady=2, sticky="w")
        controls.grid_columnconfigure(0, weight=0, minsize=180); controls.grid_columnconfigure(1, weight=0, minsize=180)
        self.file_label = ctk.CTkLabel(controls, text=t("pptx.no_file"), anchor="w"); self.file_label.grid(row=3, column=0, columnspan=2, padx=12, pady=(2, 5), sticky="w")
        self.construction_receipt.file_section_created = True
        self.slides_heading = ctk.CTkLabel(controls, text=t("pptx.slides_heading"), font=ctk.CTkFont(weight="bold")); self.slides_heading.grid(row=4, column=0, padx=12, pady=(4, 2), sticky="w")
        self.scope_var = ctk.StringVar(value=t("pptx.scope.all"))
        self._scope_display = {"all": t("pptx.scope.all"), "first": t("pptx.scope.first"), "selected": t("pptx.scope.selected"), "range": t("pptx.scope.range")}
        self._scope_value = {v: k for k, v in self._scope_display.items()}
        self.scope_menu = ctk.CTkOptionMenu(controls, variable=self.scope_var, values=list(self._scope_display.values()), command=self._scope_mode, width=190)
        self.scope_menu.grid(row=5, column=0, padx=12, pady=2, sticky="w")
        self.scope_input_var = ctk.StringVar(value="")
        self.scope_input = ctk.CTkEntry(controls, textvariable=self.scope_input_var, width=190, placeholder_text=t("pptx.selected_hint"))
        self.scope_input.grid(row=6, column=0, padx=12, pady=2, sticky="w")
        self.scope_input.bind("<KeyRelease>", lambda _event: self._scope_text_changed())
        self.scope_update = ctk.CTkButton(controls, text=t("pptx.update"), command=self._scope_update, width=90)
        self.scope_update.grid(row=7, column=0, padx=12, pady=2, sticky="w")
        self.scope_status = ctk.CTkLabel(controls, text=t("pptx.selected_count", count=0), anchor="w")
        self.scope_status.grid(row=8, column=0, padx=12, pady=(2, 8), sticky="w")
        ctk.CTkLabel(controls, text=t("badge"), font=ctk.CTkFont(weight="bold")).grid(row=9, column=0, padx=12, pady=(4, 2), sticky="w")
        self.enabled_var = ctk.BooleanVar(value=self.state.badge.enabled)
        self.badge_enable = ctk.CTkCheckBox(controls, text=t("pptx.badge_enable"), variable=self.enabled_var, command=lambda: self._dispatch(PptxEvent.BADGE_ENABLE, self.enabled_var.get())); self.badge_enable.grid(row=10, column=0, padx=12, pady=2, sticky="w")
        names = list(getattr(getattr(self.app, "badge_display_to_file", None), "keys", lambda: [])()) or ["AI Assisted"]
        self.badge_var = ctk.StringVar(value="AI Assisted" if "AI Assisted" in names else names[0])
        self.badge_menu = ctk.CTkOptionMenu(controls, variable=self.badge_var, values=names, command=lambda v: self._dispatch(PptxEvent.BADGE_SELECT, v), width=190); self.badge_menu.grid(row=11, column=0, padx=12, pady=2, sticky="w")
        self.badge_visual = ctk.CTkFrame(controls, fg_color="transparent"); self.badge_visual.grid(row=12, column=0, columnspan=2, padx=12, pady=(2, 4), sticky="w")
        self.badge_image = ctk.CTkLabel(self.badge_visual, text="", width=54, height=48); self.badge_image.grid(row=0, column=0, padx=(0, 8), sticky="w")
        self.badge_name = ctk.CTkLabel(self.badge_visual, text=self.badge_var.get(), anchor="w"); self.badge_name.grid(row=0, column=1, padx=0, sticky="w")
        self.construction_receipt.badge_section_created = True
        self._build_visual_controls(controls)
        # Keep a fixed viewport: rendered slide pixels must never determine
        # workspace geometry or displace the compact navigation row.
        self.preview_viewport = ctk.CTkFrame(preview, width=760, height=470, fg_color=("gray92", "gray13"))
        self.preview_viewport.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        self.preview_viewport.grid_propagate(False)
        self.preview_label = ctk.CTkLabel(self.preview_viewport, text=t("pptx.preview_hint"), fg_color="transparent", width=740, height=430, anchor="center")
        self.preview_label.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.preview_viewport.grid_columnconfigure(0, weight=1); self.preview_viewport.grid_rowconfigure(0, weight=1)
        self.navigation = ctk.CTkFrame(preview, fg_color="transparent"); self.navigation.grid(row=1, column=0, pady=(0, 6))
        self.navigation.grid_columnconfigure(0, weight=1); self.navigation.grid_columnconfigure(2, weight=1)
        self.previous_button = ctk.CTkButton(self.navigation, text="‹", width=34, command=lambda: self._change_slide(-1)); self.previous_button.grid(row=0, column=0, padx=4)
        self.slide_status = ctk.CTkLabel(self.navigation, text="—", width=90); self.slide_status.grid(row=0, column=1, padx=4)
        self.next_button = ctk.CTkButton(self.navigation, text="›", width=34, command=lambda: self._change_slide(1)); self.next_button.grid(row=0, column=2, padx=4)
        self.construction_receipt.preview_host_created = True
        preview.grid_columnconfigure(0, weight=1); preview.grid_rowconfigure(0, weight=1)
        self._project_badge()
        self._project_file()
        self._project_scope()
        self._dispatch(PptxEvent.BADGE_SELECT, self.badge_var.get(), record_only=True)
        self.state_token_reached = True
        self.receipts.record(self.construction_receipt)
        self.receipts.record({"layer": "pptx", "event": "PPTX_CONTROLS_LAYOUT_READY", "controls_column": True, "logo_controls": True})
        self.receipts.record({"layer": "pptx", "event": "PPTX_PREVIEW_NAV_READY", "previous": True, "counter": True, "next": True})
        self.receipts.record({"layer": "pptx", "event": "PPTX_FILE_ACTIONS_READY", "choose": True, "save": True, "same_row": True})
        self.mounted = True

    def _build_visual_controls(self, controls):
        row = 13
        t = getattr(getattr(self.app, "translator", None), "text", lambda key: key)
        self.badge_position_label = ctk.CTkLabel(controls, text=t("position")); self.badge_position_label.grid(row=row, column=0, padx=12, pady=1, sticky="w")
        positions = ["top-left", "top-right", "bottom-left", "bottom-right", "center"]
        self._position_display = {p: t("position." + p.replace("-", "_")) for p in positions}; self._position_value = {v: k for k, v in self._position_display.items()}
        self.badge_position_var = ctk.StringVar(value=self._position_display.get(self.state.badge.position, self.state.badge.position))
        self.badge_position_menu = ctk.CTkOptionMenu(controls, variable=self.badge_position_var, values=list(self._position_display.values()), command=lambda v: self._dispatch(PptxEvent.BADGE_POSITION, self._position_value.get(v, v)), width=190); self.badge_position_menu.grid(row=row+1, column=0, padx=12, pady=1, sticky="w")
        self._slider(controls, row+2, "size.value", "badge", "size", 1, 100, self.state.badge.size)
        self._slider(controls, row+3, "margin.value", "badge", "margin", 0, 250, self.state.badge.margin)
        self._slider(controls, row+4, "opacity.value", "badge", "opacity", 0, 100, self.state.badge.opacity)
        ctk.CTkLabel(controls, text=t("logo.title"), font=ctk.CTkFont(weight="bold")).grid(row=row+5, column=0, padx=12, pady=(6,2), sticky="w")
        self.logo_enabled_var = ctk.BooleanVar(value=self.state.logo.enabled)
        ctk.CTkCheckBox(controls, text=t("logo.enable"), variable=self.logo_enabled_var, command=lambda: self._dispatch(PptxEvent.LOGO_ENABLE, self.logo_enabled_var.get())).grid(row=row+6, column=0, padx=12, pady=1, sticky="w")
        self.logo_choose_button = ctk.CTkButton(controls, text=t("logo.choose"), command=self._choose_logo, width=120); self.logo_choose_button.grid(row=row+7, column=0, padx=12, pady=1, sticky="w")
        self.logo_label = ctk.CTkLabel(controls, text=t("pptx.logo_none"), anchor="w"); self.logo_label.grid(row=row+8, column=0, padx=12, pady=1, sticky="w")
        self.logo_position_var = ctk.StringVar(value=self._position_display.get(self.state.logo.position, self.state.logo.position))
        self.logo_position_menu = ctk.CTkOptionMenu(controls, variable=self.logo_position_var, values=list(self._position_display.values()), command=lambda v: self._dispatch(PptxEvent.LOGO_POSITION, self._position_value.get(v, v)), width=190); self.logo_position_menu.grid(row=row+9, column=0, padx=12, pady=1, sticky="w")
        self._slider(controls, row+10, "logo.size", "logo", "size", 1, 100, self.state.logo.size)
        self._slider(controls, row+11, "logo.margin", "logo", "margin", 0, 250, self.state.logo.margin)
        self._slider(controls, row+12, "logo.opacity", "logo", "opacity", 0, 100, self.state.logo.opacity)

    def _slider(self, host, row, label, group, field, low, high, value):
        row_host = ctk.CTkFrame(host, fg_color="transparent"); row_host.grid(row=row, column=0, columnspan=2, padx=12, pady=1, sticky="ew")
        row_host.grid_columnconfigure(1, weight=1)
        var = ctk.IntVar(value=value); setattr(self, f"{group}_{field}_var", var)
        translator = getattr(getattr(self.app, "translator", None), "text", lambda key, **v: key)
        templates = {"size.value": "size.value", "margin.value": "margin.value", "opacity.value": "opacity.value", "logo.size": "logo.size", "logo.margin": "logo.margin", "logo.opacity": "logo.opacity"}
        key = templates.get(label, label)
        value_label = ctk.CTkLabel(row_host, text=translator(key, value=value), anchor="w", width=110); value_label.grid(row=0, column=0, padx=(0, 6), sticky="w")
        setattr(self, f"{group}_{field}_label", value_label); setattr(self, f"{group}_{field}_label_key", key)
        slider = ctk.CTkSlider(row_host, from_=low, to=high, variable=var, command=lambda v: self._slider_event(group, field, v), width=180)
        slider.grid(row=0, column=1, padx=0, sticky="ew")
        setattr(self, f"{group}_{field}_row", row_host)

    def _slider_event(self, group, field, value):
        event = getattr(PptxEvent, f"{group.upper()}_{field.upper()}")
        normalized = round(float(value))
        translator = getattr(getattr(self.app, "translator", None), "text", lambda key, **v: key)
        key = getattr(self, f"{group}_{field}_label_key")
        getattr(self, f"{group}_{field}_label").configure(text=translator(key, value=normalized))
        self._dispatch(event, normalized)

    def _choose_logo(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg")])
        if path:
            self._dispatch(PptxEvent.LOGO_CHOOSE, path)
            self.logo_label.configure(text=Path(path).name)

    def _change_slide(self, delta):
        event = PptxEvent.PREVIEW_NEXT if delta > 0 else PptxEvent.PREVIEW_PREVIOUS
        apply_pptx_scope_event(self.state, event)
        self.receipts.record({"layer": "pptx", "event": "PREVIEW_NAVIGATION", "current_slide": self.state.current_slide, "active_scope": self.state.active_scope})
        self._render_preview()

    def _preview_fit_rect(self) -> tuple[int, int]:
        """Single owner of PPTX preview geometry and fit padding."""
        viewport_width = max(1, self.preview_viewport.winfo_width())
        viewport_height = max(1, self.preview_viewport.winfo_height())
        # Return the available interior rectangle; the renderer then fits the
        # actual slide aspect ratio inside it.  The helper keeps this calculation
        # deterministic while avoiding source-slide-driven widget geometry.
        return fit_preview_size(viewport_width, viewport_height, 740 / 450, padding=10, target_fraction=0.8)

    def apply_language(self, translator) -> None:
        """Project locale changes without rebuilding or clearing the session."""
        if hasattr(self, "heading_label"):
            self.heading_label.configure(text=translator.text("content.powerpoint")); self.file_heading.configure(text=translator.text("pptx.file_heading")); self.slides_heading.configure(text=translator.text("pptx.slides_heading"))
        self.choose_button.configure(text=translator.text("pptx.choose")); self.save_button.configure(text="Save")
        if hasattr(self, "badge_enable"):
            self.badge_enable.configure(text=translator.text("pptx.badge_enable")); self.scope_update.configure(text=translator.text("pptx.update")); self.logo_choose_button.configure(text=translator.text("logo.choose")); self.badge_position_label.configure(text=translator.text("position")); self.logo_label.configure(text=self.logo_label.cget("text") if self.state.logo.path else translator.text("pptx.logo_none"))
            self._position_display = {p: translator.text("position." + p.replace("-", "_")) for p in ("top-left", "top-right", "bottom-left", "bottom-right", "center")}; self._position_value = {v: k for k, v in self._position_display.items()}; self.badge_position_menu.configure(values=list(self._position_display.values())); self.logo_position_menu.configure(values=list(self._position_display.values()))
        for group, field in (("badge","size"),("badge","margin"),("badge","opacity"),("logo","size"),("logo","margin"),("logo","opacity")):
            if hasattr(self, f"{group}_{field}_label"):
                getattr(self, f"{group}_{field}_label").configure(text=translator.text(getattr(self, f"{group}_{field}_label_key"), value=getattr(self.state, group).__dict__[field]))
        if hasattr(self, "scope_menu"):
            self._scope_display = {"all": translator.text("pptx.scope.all"), "first": translator.text("pptx.scope.first"), "selected": translator.text("pptx.scope.selected"), "range": translator.text("pptx.scope.range")}; self._scope_value = {v: k for k, v in self._scope_display.items()}
            self.scope_menu.configure(values=list(self._scope_display.values()))
        if hasattr(self, "file_label"): self._project_file()
        if hasattr(self, "scope_status"): self._project_scope()
        if hasattr(self, "badge_visual"): self._project_badge()
        self.save_button.configure(text="Save")
        self.preview_label.configure(text=translator.text("pptx.preview_hint") if not self.state.loaded else "")

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
            # Use the fixed viewport's interior, not the source slide's size.
            available_width, available_height = self._preview_fit_rect()
            if hasattr(self.preview_viewport, "update_idletasks"):
                self.preview_viewport.update_idletasks()
            host_width = max(1, self.preview_viewport.winfo_width())
            host_height = max(1, self.preview_viewport.winfo_height())
            available_width, available_height = self._preview_fit_rect()
            result = renderer.render(self.state.path, self.state.current_slide, badge, settings, self.state.logo.path if self.state.logo.enabled else None, max_size=(available_width, available_height))
            self.preview_photo = ctk.CTkImage(result.image, size=result.image.size)
            self.preview_label.configure(image=self.preview_photo, text="")
            self.slide_status.configure(text=f"{result.slide_number} / {result.slide_count}")
            self.previous_button.configure(state="normal" if self.state.current_slide > 1 else "disabled")
            self.next_button.configure(state="normal" if self.state.current_slide < self.state.slide_count else "disabled")
            usable = (max(1, host_width - 20), max(1, host_height - 20))
            target80 = (round(usable[0] * 0.8), round(usable[1] * 0.8))
            boot = getattr(self.app, "_boot", None)
            if callable(boot):
                boot(f"PPTX_HOST={host_width}x{host_height} PPTX_USABLE={usable[0]}x{usable[1]} PPTX_TARGET80={target80[0]}x{target80[1]} PPTX_FIT={available_width}x{available_height} PPTX_RENDER={result.image.width}x{result.image.height} PPTX_CTKIMAGE={result.image.width}x{result.image.height} PPTX_LABEL={self.preview_label.winfo_width()}x{self.preview_label.winfo_height()}")
            self.receipts.record({"layer": "pptx", "event": "PPTX_PREVIEW_GEOMETRY_STABLE", "slide_bbox": result.image.size})
            self.receipts.record({"layer": "pptx", "event": "PPTX_PREVIEW_FIT_RECT", "fit_rect": [available_width, available_height]})
            self.receipts.record({"layer": "pptx", "event": "PPTX_COMPACT_NAV_READY", "counter": True})
        except Exception as error:
            t = getattr(getattr(self.app, "translator", None), "text", lambda key, **v: key)
            self.preview_label.configure(image=None, text=t("pptx.preview_error", error=error))

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
            self.receipts.record({"layer": "pptx", "event": "PPTX_SESSION_LOADED", "slide_count": self.state.slide_count})

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
        handler = getattr(self.app, "process_pptx_from_workspace", None)
        if callable(handler):
            handler(self.state)

    def _scope_mode(self, value):
        mode = self._scope_value.get(str(value), str(value).lower())
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
            # UPDATE_SCOPE owns the physical-preview jump to the first
            # applicable slide; projection then renders that authoritative
            # state without remounting the workspace.
            self._render_preview()
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
            t = getattr(getattr(self.app, "translator", None), "text", lambda key, **v: key)
            self.scope_var.set(getattr(self, "_scope_display", {}).get(self.state.scope_mode, self.state.scope_mode.title()))
            self.scope_input_var.set(self.state.scope_input)
            self.scope_status.configure(text=t("pptx.selected_count", count=len(self.state.active_scope)))

    def _project_badge(self):
        if hasattr(self, "badge_visual"):
            repository = getattr(self.app, "badges", None)
            if repository and (hasattr(repository, "display_badges") or hasattr(repository, "all")):
                model = project_badge(self.state, repository)
                self.badge_name.configure(text=model["display_name"])
                asset = model.get("asset")
                if asset and asset.exists():
                    with Image.open(asset) as opened: image = opened.convert("RGBA")
                    image.thumbnail((110, 54), Image.Resampling.LANCZOS)
                    self.badge_photo = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
                    self.badge_image.configure(image=self.badge_photo, text="")

    def _project_file(self):
        t = getattr(getattr(self.app, "translator", None), "text", lambda key, **v: key)
        model = project_file(self.state, t)
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
