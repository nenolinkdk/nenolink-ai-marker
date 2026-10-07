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
from .pptx_state import (PptxWorkspaceState, PptxEvent, PptxEventReceipt, apply_pptx_event,
                          apply_pptx_scope_event, choose_file_success, project_file, project_badge)
from .diagnostic_receipts import ReceiptLog
from .document_preview_layout import fit_preview_geometry
from .workspace_ui import build_badge_visual
from .save_control import SaveControl
from .badge_control import BadgeControl, BadgeProjection
from .source_control import SourceControl
from .logo_control import LogoControl, LogoProjection
from .preview_shell import PreviewShell
from .document_controls import PhysicalNavigationControl, DocumentScopeControl
from .workspace_control_panel import WorkspaceControlPanel, PARAM_LABEL_WIDTH, PARAM_CONTROL_WIDTH
from .document_processing import ItemSelection, ProcessingRequest, settings_for_documents
from .metadata import marker_metadata
from dataclasses import replace


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
        self.presentation_generation = 0

    def _dispose_view(self) -> None:
        root = self.root
        if root is not None:
            try:
                if root.winfo_exists():
                    root.destroy()
            except Exception:
                pass
        self.root = None
        self.mounted = False
        self.preview_photo = None
        self.source_control = None
        for name in ("badge_control", "save_control", "preview_host", "preview_label", "file_label", "choose_button", "save_button", "scope_menu", "scope_input", "scope_status", "previous_button", "next_button", "slide_status"):
            if hasattr(self, name):
                setattr(self, name, None)

    def has_active_work(self) -> bool:
        return self.state.loaded

    def mount(self, content_host) -> None:
        self._dispose_view()
        self.presentation_generation += 1
        self.root = ctk.CTkFrame(content_host, fg_color="transparent")
        self.root.grid(row=0, column=0, sticky="nsew")
        self.root.grid_columnconfigure(0, weight=0, minsize=360)
        self.root.grid_columnconfigure(1, weight=1)
        self.mount_token_reached = True
        self.construction_receipt = PptxConstructionReceipt()
        self.construction_receipt.authoritative_state_created = True
        self.construction_receipt.workspace_created = True
        self.control_panel = WorkspaceControlPanel(self.root, width=360)
        for section in ("FILE", "SLIDES", "AI_BADGE", "OWN_LOGO"):
            self.control_panel.declare_section(section)
        controls = self.control_panel.frame; controls.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        controls.bind("<MouseWheel>", lambda event: controls._parent_canvas.yview_scroll(-int(event.delta / 120), "units"))
        self.preview_shell = PreviewShell(self.root); self.preview_shell.frame.grid(row=0, column=1, padx=8, pady=8, sticky="nsew"); preview = self.preview_shell.viewport
        self.preview_host = preview
        t = getattr(getattr(self.app, "translator", None), "text", lambda key: key)
        file_section = ctk.CTkFrame(controls, fg_color="transparent"); self.control_panel.add_section("FILE", file_section)
        self.heading_label = ctk.CTkLabel(file_section, text=t("content.powerpoint"), font=ctk.CTkFont(size=24, weight="bold")); self.heading_label.grid(row=0, column=0, padx=2, pady=(2, 2), sticky="w")
        file_section.grid_columnconfigure(0, weight=1); file_section.grid_columnconfigure(1, weight=1)
        self.file_heading = ctk.CTkLabel(file_section, text=t("pptx.file_heading"), font=ctk.CTkFont(weight="bold")); self.file_heading.grid(row=1, column=0, columnspan=2, padx=2, pady=(2, 1), sticky="w")
        self.source_control = SourceControl(file_section, choose_command=self._choose_file, choose_label=t("pptx.choose"), width=280, compact=True); self.source_control.frame.grid(row=2, column=0, padx=(2,4), pady=2, sticky="ew"); self.choose_button = self.source_control.choose_button
        self.save_control = SaveControl(file_section, label="Save As...", command=self._save_as, width=160); self.save_button = self.save_control.button; self.save_button.grid(row=2, column=1, padx=(4,2), pady=2, sticky="ew")
        self.file_label = self.source_control.filename_label; self.file_metadata_label = self.source_control.metadata_label
        self.construction_receipt.file_section_created = True
        slides_section = ctk.CTkFrame(controls, fg_color="transparent"); self.control_panel.add_section("SLIDES", slides_section)
        self.slides_heading = ctk.CTkLabel(slides_section, text=t("pptx.slides_heading"), font=ctk.CTkFont(weight="bold")); self.slides_heading.grid(row=0, column=0, padx=2, pady=(2, 1), sticky="w")
        self.scope_control = DocumentScopeControl(slides_section, on_mode=self._scope_mode, on_text=lambda text: self._scope_text_changed(), on_update=self._scope_update, values=(t("pptx.scope.all"), t("pptx.scope.first"), t("pptx.scope.selected"), t("pptx.scope.range")), placeholder=t("pptx.selected_hint"))
        self.scope_control.frame.grid(row=1, column=0, padx=2, pady=2, sticky="ew")
        self.scope_var = self.scope_control.mode_var; self.scope_menu = self.scope_control.menu; self.scope_input_var = self.scope_control.input_var; self.scope_input = self.scope_control.input; self.scope_update = self.scope_control.update; self.scope_status = self.scope_control.status
        self._scope_display = {"all": t("pptx.scope.all"), "first": t("pptx.scope.first"), "selected": t("pptx.scope.selected"), "range": t("pptx.scope.range")}; self._scope_value = {v: k for k, v in self._scope_display.items()}
        badge_section = ctk.CTkFrame(controls, fg_color="transparent"); self.control_panel.add_section("AI_BADGE", badge_section)
        self.badge_control = BadgeControl(badge_section, on_enabled_changed=lambda value: self._dispatch(PptxEvent.BADGE_ENABLE, value), on_badge_selected=lambda value: self._dispatch(PptxEvent.BADGE_SELECT, value))
        self.badge_control.frame.grid(row=0, column=0, sticky="ew")
        self.enabled_var = self.badge_control.enabled_var; self.badge_var = self.badge_control.selector_var
        self.badge_enable = self.badge_control.enabled_widget; self.badge_menu = self.badge_control.selector_widget; self.badge_visual = self.badge_control.graphic_widget; self.badge_image = self.badge_visual; self.badge_name = self.badge_visual
        self.construction_receipt.badge_section_created = True
        logo_section = ctk.CTkFrame(controls, fg_color="transparent"); self.control_panel.add_section("OWN_LOGO", logo_section)
        self._build_visual_controls(badge_section, logo_section)
        # Keep a fixed viewport: rendered slide pixels must never determine
        # workspace geometry or displace the compact navigation row.
        self.preview_viewport = ctk.CTkFrame(preview, fg_color=("gray92", "gray13"))
        self.preview_viewport.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        self.preview_label = ctk.CTkLabel(self.preview_viewport, text=t("pptx.preview_hint"), fg_color="transparent", width=740, height=430, anchor="center")
        self.preview_label.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.preview_viewport.grid_columnconfigure(0, weight=1); self.preview_viewport.grid_rowconfigure(0, weight=1)
        self.navigation_control = PhysicalNavigationControl(preview, on_previous=lambda: self._change_slide(-1), on_next=lambda: self._change_slide(1)); self.navigation_control.frame.grid(row=1, column=0, pady=(0, 6))
        self.navigation = self.navigation_control.frame; self.previous_button = self.navigation_control.previous; self.slide_status = self.navigation_control.status; self.next_button = self.navigation_control.next
        self.construction_receipt.preview_host_created = True
        preview.grid_columnconfigure(0, weight=1); preview.grid_rowconfigure(0, weight=1)
        self._preview_resize_job = None
        self.preview_viewport.bind("<Configure>", self._schedule_preview_refresh, add="+")
        self.state_token_reached = True
        self.receipts.record(self.construction_receipt)
        self.receipts.record({"layer": "pptx", "event": "PPTX_CONTROLS_LAYOUT_READY", "controls_column": True, "logo_controls": True})
        self.receipts.record({"layer": "pptx", "event": "PPTX_PREVIEW_NAV_READY", "previous": True, "counter": True, "next": True})
        self.receipts.record({"layer": "pptx", "event": "PPTX_FILE_ACTIONS_READY", "choose": True, "save": True, "same_row": True})
        self.mounted = True

    def _build_visual_controls(self, controls, logo_host=None):
        row = 1
        t = getattr(getattr(self.app, "translator", None), "text", lambda key: key)
        self.badge_position_label = ctk.CTkLabel(controls, text=t("position")); self.badge_position_label.grid(row=row, column=0, padx=12, pady=1, sticky="w")
        positions = ["top-left", "top-right", "bottom-left", "bottom-right", "center"]
        self._position_display = {p: t("position." + p.replace("-", "_")) for p in positions}; self._position_value = {v: k for k, v in self._position_display.items()}
        self.badge_position_var = ctk.StringVar(value=self._position_display.get(self.state.badge.position, self.state.badge.position))
        self.badge_position_menu = ctk.CTkOptionMenu(controls, variable=self.badge_position_var, values=list(self._position_display.values()), command=lambda v: self._dispatch(PptxEvent.BADGE_POSITION, self._position_value.get(v, v)), width=190); self.badge_position_menu.grid(row=row+1, column=0, padx=12, pady=1, sticky="w")
        self._slider(controls, row+2, "size.value", "badge", "size", 1, 100, self.state.badge.size)
        self._slider(controls, row+3, "margin.value", "badge", "margin", 0, 250, self.state.badge.margin)
        self._slider(controls, row+4, "opacity.value", "badge", "opacity", 0, 100, self.state.badge.opacity)
        logo_host = logo_host or controls
        self.logo_control = LogoControl(logo_host, on_enabled=lambda value: self._dispatch(PptxEvent.LOGO_ENABLE, value), on_choose=self._choose_logo, on_size=lambda value: self._dispatch(PptxEvent.LOGO_SIZE, round(value)), on_margin=lambda value: self._dispatch(PptxEvent.LOGO_MARGIN, round(value)), on_opacity=lambda value: self._dispatch(PptxEvent.LOGO_OPACITY, round(value)))
        self.logo_control.frame.grid(row=0, column=0, sticky="ew")
        self.logo_enabled_var = self.logo_control.enabled_var; self.logo_choose_button = self.logo_control.choose_button; self.logo_label = self.logo_control.filename_label; self.logo_position_var = ctk.StringVar(value="Top left")

    def _slider(self, host, row, label, group, field, low, high, value):
        row_host = ctk.CTkFrame(host, fg_color="transparent"); row_host.grid(row=row, column=0, columnspan=2, padx=12, pady=1, sticky="ew")
        row_host.grid_columnconfigure(1, weight=1)
        var = ctk.IntVar(value=value); setattr(self, f"{group}_{field}_var", var)
        translator = getattr(getattr(self.app, "translator", None), "text", lambda key, **v: key)
        templates = {"size.value": "size.value", "margin.value": "margin.value", "opacity.value": "opacity.value", "logo.size": "logo.size", "logo.margin": "logo.margin", "logo.opacity": "logo.opacity"}
        key = templates.get(label, label)
        value_label = ctk.CTkLabel(row_host, text=translator(key, value=value), anchor="w", width=PARAM_LABEL_WIDTH); value_label.grid(row=0, column=0, padx=(0, 6), sticky="w")
        setattr(self, f"{group}_{field}_label", value_label); setattr(self, f"{group}_{field}_label_key", key)
        slider = ctk.CTkSlider(row_host, from_=low, to=high, variable=var, command=lambda v: self._slider_event(group, field, v), width=PARAM_CONTROL_WIDTH)
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
        apply_pptx_event(self.state, event)
        self.receipts.record({"layer": "pptx", "event": "PREVIEW_NAVIGATION", "current_slide": self.state.current_slide, "active_scope": self.state.active_scope})
        self._render_preview()

    def _preview_geometry(self):
        viewport_width = max(1, self.preview_viewport.winfo_width())
        viewport_height = max(1, self.preview_viewport.winfo_height())
        app = self.__dict__.get("app")
        renderer = getattr(app, "pptx_preview_renderer", None)
        source_width, source_height = renderer.slide_dimensions(self.state.path) if renderer and self.state.path else (16.0, 9.0)
        return fit_preview_geometry(viewport_width, viewport_height, source_width, source_height, target_fraction=0.8)

    def _preview_fit_rect(self) -> tuple[int, int]:
        """Compatibility result for callers; geometry remains viewport-measured."""
        geometry = self._preview_geometry()
        return geometry.rendered_width, geometry.rendered_height

    def _schedule_preview_refresh(self, _event=None):
        if self._preview_resize_job is not None:
            try: self.preview_viewport.after_cancel(self._preview_resize_job)
            except Exception: pass
        self._preview_resize_job = self.preview_viewport.after(120, self._render_preview)

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
            if hasattr(self.preview_viewport, "update_idletasks"):
                self.preview_viewport.update_idletasks()
            host_width = max(1, self.preview_viewport.winfo_width())
            host_height = max(1, self.preview_viewport.winfo_height())
            geometry = self._preview_geometry()
            available_width, available_height = geometry.rendered_width, geometry.rendered_height
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
            self.geometry_receipt = geometry
            self.receipts.record({"layer": "pptx", "event": "PPTX_PREVIEW_GEOMETRY", "viewport": [geometry.viewport_width, geometry.viewport_height], "rendered": [result.image.width, result.image.height], "measured_fraction": geometry.measured_fraction, "limiting_dimension": geometry.limiting_dimension})
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
            apply_pptx_event(self.state, PptxEvent.CHOOSE_FILE, (Path(path), count))
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
        apply_pptx_event(self.state, event, value)
        self.state_token_reached = True
        self.last_receipt = PptxEventReceipt(event, before, {"badge": self.state.badge.__dict__.copy()}, (event.value,), ("path", "current_slide", "active_scope", "logo"), True, value)
        self.receipts.record(self.last_receipt)
        self._project_badge()
        if getattr(self, "logo_control", None):
            self.logo_control.project(LogoProjection(enabled=self.state.logo.enabled, filename=self.state.logo.path.name if self.state.logo.path else "", position=self.state.logo.position, size=self.state.logo.size, margin=self.state.logo.margin, opacity=self.state.logo.opacity))
        self._render_preview()

    def _save_as(self):
        """Save through the authoritative workspace state and PPTX processor."""
        self.receipts.record({"layer": "pptx", "event": "PPTX_SAVE_CLICK"})
        self.receipts.record({"layer": "pptx", "event": "PPTX_SAVE_AS_ENTER"})
        if not self.state.path or not Path(self.state.path).is_file():
            self.receipts.record({"layer": "pptx", "event": "PPTX_SAVE_STATE_VALID", "valid": False})
            self.scope_status.configure(text="Choose a PowerPoint file before saving.")
            return
        self.receipts.record({"layer": "pptx", "event": "PPTX_SAVE_STATE_VALID", "valid": True})
        from tkinter import filedialog, messagebox
        destination_name = f"{self.state.path.stem}_ai.pptx"
        selected = filedialog.asksaveasfilename(
            title="Save As...", initialdir=str(self.state.path.parent),
            initialfile=destination_name, defaultextension=".pptx",
            filetypes=[("PowerPoint (*.pptx)", "*.pptx")], confirmoverwrite=True,
        )
        if not selected:
            self.receipts.record({"layer": "pptx", "event": "PPTX_SAVE_CANCELLED"})
            return
        destination = Path(selected)
        if destination.resolve() == self.state.path.resolve():
            messagebox.showwarning("Save", "Choose a different output file.")
            return
        badge = self.app.badges.find(self.state.badge.badge_id) if self.state.badge.enabled else None
        label = self.app.badges.display_name(self.state.badge.badge_id) if badge else ""
        settings = replace(
            self.app.settings(), position=self.state.badge.position,
            size_percent=self.state.badge.size, margin=self.state.badge.margin,
            opacity=self.state.badge.opacity,
            logo_enabled=self.state.logo.enabled,
            logo_path=str(self.state.logo.path or ""),
            logo_position=self.state.logo.position,
            logo_size_percent=self.state.logo.size,
            logo_margin=self.state.logo.margin,
            logo_opacity=self.state.logo.opacity,
        )
        disclosure, logo = settings_for_documents(settings, label=label, disclosure_language=self.app.translator.language)
        request = ProcessingRequest(
            self.state.path, destination, disclosure, badge_path=badge,
            logo=logo, metadata=marker_metadata(disclosure.badge_name, disclosure.label),
        )
        try:
            self.app.pptx_processor.process(request, ItemSelection("selected", tuple(self.state.active_scope)))
            self.state.output_status = str(destination)
            self.receipts.record({"layer": "pptx", "event": "PPTX_SAVE_COMPLETED", "destination": str(destination)})
            self.app.status_var.set(f"Saved {destination.name}")
        except (OSError, ValueError) as error:
            self.receipts.record({"layer": "pptx", "event": "PPTX_SAVE_FAILED", "error": str(error)})
            messagebox.showerror("Save", str(error))

    def _scope_mode(self, value):
        mode = self._scope_value.get(str(value), str(value).lower())
        try:
            apply_pptx_event(self.state, PptxEvent.SCOPE_MODE, mode)
            self._scope_receipt(PptxEvent.SCOPE_MODE, mode)
            self._project_scope()
        except ValueError as error:
            self.scope_status.configure(text=str(error))

    def _scope_update(self):
        value = self.scope_input_var.get()
        before = self.state.active_scope
        try:
            apply_pptx_event(self.state, PptxEvent.SCOPE_TEXT_CHANGED, value)
            apply_pptx_event(self.state, PptxEvent.SCOPE_UPDATE, value)
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
        apply_pptx_event(self.state, PptxEvent.SCOPE_TEXT_CHANGED, value)
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
        if hasattr(self, "badge_control"):
            repository = getattr(self.app, "badges", None)
            if repository and (hasattr(repository, "display_badges") or hasattr(repository, "all")):
                model = project_badge(self.state, repository)
                asset = model.get("asset")
                names = tuple(repository.display_name(path.name) for path in repository.display_badges())
                self.badge_control.project(BadgeProjection(bool(self.state.badge.enabled), model["display_name"], names, asset, self.state.badge.position, self.state.badge.size, self.state.badge.margin, self.state.badge.opacity, self.app.translator.text("pptx.badge_enable")))

    def _project_file(self):
        t = getattr(getattr(self.app, "translator", None), "text", lambda key, **v: key)
        model = project_file(self.state, t)
        if hasattr(self, "file_label"):
            self.file_label.configure(text=model["status"] if not model["filename"] else f"{model['filename']}\n{model['details']}")
        if hasattr(self, "source_control"):
            self.source_control.project(filename=model["filename"], metadata=model["details"], empty_text=model["status"])

    def project(self) -> None:
        """Project the authoritative PPTX state into the mounted view."""
        if self.root is None or not self.root.winfo_exists():
            return
        self._project_file()
        self._project_scope()
        self._project_badge()
        if self.state.loaded:
            self._render_preview()
        else:
            self.preview_photo = None; self.preview_label.configure(image=None, text=self.app.translator.text("pptx.preview_hint")); self.slide_status.configure(text="—")

    def unmount(self) -> None:
        if self.root is not None and self.root.winfo_exists():
            self.root.destroy()
        self.root = None
        self.mounted = False

    def clear_runtime_state(self) -> None:
        apply_pptx_event(self.state, PptxEvent.CLEAR_RUNTIME)
        self.unmount()

    def dispatch(self, event, value=None):
        return apply_pptx_event(self.state, event, value)

    def enter_clean(self):
        return self.dispatch(PptxEvent.CLEAR_RUNTIME)
