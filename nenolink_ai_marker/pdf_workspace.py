"""PDF workspace lifecycle boundary.

This first migration step deliberately keeps the existing PDF view builder in
``MarkerApp``.  The workspace owns the lifecycle surface and delegates the
legacy view construction through a narrow compatibility adapter.  State and
event ownership move in the following PDF migration checkpoints.
"""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from tkinter import filedialog, messagebox
import customtkinter as ctk
from .pdf_processor import PdfProcessor
from .document_preview_layout import fit_preview_size
from .document_processing import ItemSelection, ProcessingRequest, settings_for_documents
from .metadata import marker_metadata
from dataclasses import replace
from .workspace_state import PdfEvent, PdfWorkspaceState, apply_pdf_event
from .save_control import SaveControl
from .badge_control import BadgeControl, BadgeProjection
from .workspace_ui import build_badge_visual
from .source_control import SourceControl
from .logo_control import LogoControl, LogoProjection
from .preview_shell import PreviewShell
from .document_controls import PhysicalNavigationControl, DocumentScopeControl
from .workspace_control_panel import WorkspaceControlPanel


@dataclass(frozen=True, slots=True)
class PdfProcessingRequest:
    request: ProcessingRequest
    selection: ItemSelection


class PdfWorkspace:
    """Lifecycle facade around the existing PDF implementation."""

    def __init__(self, app, state) -> None:
        self.app = app
        self.state = state
        self.root = None
        self.presentation_generation = 0

    def _dispose_view(self):
        root = self.root
        if root is not None:
            try:
                if root.winfo_exists():
                    root.destroy()
            except Exception:
                pass
        self.root = None
        self.badge_control = None
        self.source_control = None
        self.logo_control = None
        self.preview_photo = None
        for name in ("pdf_workspace", "pdf_workspace_root", "pdf_controls_host", "pdf_preview_host", "pdf_preview_label", "pdf_process_button", "pdf_save_control", "pdf_badge_enable", "pdf_badge_menu", "pdf_badge_visual", "pdf_badge_image_label", "pdf_badge_name_label"):
            if hasattr(self.app, name):
                setattr(self.app, name, None)

    def mount(self, host) -> None:
        self._dispose_view()
        app = self.app; t = app.translator.text
        self.root = ctk.CTkFrame(host, fg_color="transparent"); self.root.grid(row=0, column=0, sticky="nsew")
        self.presentation_generation += 1
        self.root.grid_columnconfigure(0, weight=0, minsize=320); self.root.grid_columnconfigure(1, weight=1); self.root.grid_rowconfigure(0, weight=1)
        self.control_panel = WorkspaceControlPanel(self.root, width=320)
        for section in ("FILE", "PAGES", "AI_BADGE", "OWN_LOGO"):
            self.control_panel.declare_section(section)
        controls = self.control_panel.frame; controls.grid(row=0, column=0, padx=(4,8), pady=4, sticky="nsew")
        self.preview_shell = PreviewShell(self.root); self.preview_shell.frame.grid(row=0, column=1, padx=(8,4), pady=4, sticky="nsew"); preview_host = self.preview_shell.viewport
        app.pdf_workspace = controls; app.pdf_workspace_root = self.root; app.pdf_controls_host = controls; app.pdf_preview_host = preview_host
        file_section = ctk.CTkFrame(controls, fg_color="transparent"); self.control_panel.add_section("FILE", file_section)
        file_section.grid_columnconfigure(0, weight=1); file_section.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(file_section, text="FILE", font=ctk.CTkFont(weight="bold")).grid(row=0,column=0,columnspan=2,padx=2,pady=(2,1),sticky="w")
        self.source_control = SourceControl(file_section, choose_command=self.choose_file, choose_label=t("pdf.choose"), width=280, compact=True); self.source_control.frame.grid(row=1,column=0,padx=(2,4),pady=(2,2),sticky="ew"); app.pdf_choose_button = self.source_control.choose_button; app.pdf_file_label = self.source_control.filename_label
        pages_section = ctk.CTkFrame(controls, fg_color="transparent"); self.control_panel.add_section("PAGES", pages_section)
        ctk.CTkLabel(pages_section, text="PAGES", font=ctk.CTkFont(weight="bold")).grid(row=0,column=0,padx=2,pady=(2,1),sticky="w")
        self.scope_control = DocumentScopeControl(pages_section, on_mode=self.set_scope_mode, on_text=lambda text: apply_pdf_event(self.state, PdfEvent.SCOPE_TEXT_CHANGED, {"text": text}), on_update=lambda: self.project(), values=("All", "First", "Selected", "Range"), placeholder="pages")
        self.scope_control.frame.grid(row=1, column=0, padx=2, pady=2, sticky="ew")
        badge_section = ctk.CTkFrame(controls, fg_color="transparent"); self.control_panel.add_section("AI_BADGE", badge_section)
        self.badge_control = BadgeControl(badge_section, on_enabled_changed=self.visual_changed, on_badge_selected=self.select_badge)
        self.badge_control.frame.grid(row=0, column=0, sticky="ew")
        app.pdf_badge_enable = self.badge_control.enabled_widget; app.pdf_badge_menu = self.badge_control.selector_widget; app.badge_display_var = self.badge_control.selector_var; app.pdf_badge_visual = self.badge_control.graphic_widget; app.pdf_badge_image_label=app.pdf_badge_visual; app.pdf_badge_name_label=app.pdf_badge_visual
        logo_section = ctk.CTkFrame(controls, fg_color="transparent"); self.control_panel.add_section("OWN_LOGO", logo_section)
        self.logo_control = LogoControl(logo_section, on_enabled=lambda value: self.set_logo(enabled=value), on_choose=self.choose_logo, on_size=lambda value: self.set_logo(size=value), on_margin=lambda value: self.set_logo(margin=value), on_opacity=lambda value: self.set_logo(opacity=value))
        self.logo_control.frame.grid(row=0, column=0, sticky="ew")
        app.pdf_preview_label = ctk.CTkLabel(preview_host,text="PDF page preview",fg_color=("gray92","gray13")); app.pdf_preview_label.grid(row=0,column=0,pady=(12,4),sticky="nsew")
        self.navigation_control = PhysicalNavigationControl(preview_host, on_previous=lambda:self.set_current_page(self.state.current_page-1), on_next=lambda:self.set_current_page(self.state.current_page+1)); self.navigation_control.frame.grid(row=1,column=0,pady=4)
        self._preview_resize_job = None
        preview_host.bind("<Configure>", self._schedule_preview_refresh, add="+")
        app.pdf_previous_button=self.navigation_control.previous; app.pdf_page_status=self.navigation_control.status; app.pdf_next_button=self.navigation_control.next
        app.pdf_save_control=SaveControl(file_section,label="Save As...",command=self.save,width=160); app.pdf_process_button=app.pdf_save_control.button; app.pdf_process_button.grid(row=1,column=1,padx=(4,2),pady=2,sticky="ew")

    def unmount(self) -> None:
        self._dispose_view()

    def project(self) -> None:
        app = self.app; state = self.state
        # Keep the authoritative badge state explicit at the projection boundary.
        _authoritative_badge = self.state.badge
        self._ensure_badge_selection()
        app.pdf_path = state.path
        app.pdf_current_page = state.current_page
        app.pdf_scope_mode = state.scope_mode
        app.pdf_scope_input = state.scope_input
        app.pdf_active_scope = tuple(state.active_scope)
        if state.path is None: app.pdf_info = None
        for name, value in (("pdf_badge_enabled_var", state.badge.enabled), ("badge_var", state.badge.badge_id), ("position_var", state.badge.position), ("size_var", state.badge.size), ("margin_var", state.badge.margin), ("opacity_var", state.badge.opacity), ("logo_enabled_var", state.logo.enabled), ("logo_path_var", str(state.logo.path or "")), ("logo_position_var", state.logo.position), ("logo_size_var", state.logo.size), ("logo_margin_var", state.logo.margin), ("logo_opacity_var", state.logo.opacity)):
            variable = getattr(app, name, None)
            if variable is not None: variable.set(value)
        if getattr(app, "pdf_file_label", None) is not None:
            app.pdf_file_label.configure(text=(state.path.name if state.path else app.translator.text("pdf.no_file")))
        if getattr(self, "source_control", None) is not None:
            self.source_control.project(filename=(state.path.name if state.path else ""), empty_text=app.translator.text("pdf.no_file"))
        if getattr(self, "logo_control", None) is not None:
            self.logo_control.project(LogoProjection(enabled=state.logo.enabled, filename=state.logo.path.name if state.logo.path else "", position=state.logo.position, size=state.logo.size, margin=state.logo.margin, opacity=state.logo.opacity))
        if getattr(self, "scope_control", None) is not None:
            self.scope_control.project(mode=state.scope_mode.title(), draft=state.scope_input, status=str(len(state.active_scope)))
        if getattr(app, "pdf_page_status", None) is not None:
            app.pdf_page_status.configure(text=(f"{state.current_page} / {state.page_count}" if state.path else "—"))
        if state.path and getattr(app, "pdf_info", None) is not None:
            self.refresh_preview()
        else:
            if getattr(app, "pdf_preview_label", None) is not None: app.pdf_preview_label.configure(image=None, text="PDF page preview")
            self.preview_photo = None; app.pdf_preview_photo = None
        self._project_badge_controls()

    def _ensure_badge_selection(self) -> None:
        """Seed a valid default badge through the PDF event boundary."""
        state = self.state
        if state.badge.badge_id:
            return
        app = self.app
        badges = getattr(app, "badges", None)
        preferred = getattr(getattr(app, "_saved_settings", None), "badge_name", "")
        candidate = preferred if badges is not None and badges.find(preferred) else ""
        if not candidate:
            paths = tuple(badges.display_badges()) if badges is not None else ()
            candidate = paths[0].name if paths else ""
        if candidate:
            apply_pdf_event(state, PdfEvent.BADGE_CHANGED, {"badge_id": candidate})

    def _project_badge_controls(self) -> None:
        app = self.app; state = self.state
        badges = getattr(app, "badges", None)
        if badges is None:
            return
        names = [path.name for path in badges.display_badges()]
        displays = [app.badges.display_name(name) for name in names]
        display = app.badges.display_name(state.badge.badge_id) if state.badge.badge_id else "—"
        badge = next((path for path in app.badges.display_badges() if path.name == state.badge.badge_id), None)
        self.badge_control.project(BadgeProjection(bool(state.badge.enabled), display, tuple(displays), badge, state.badge.position, state.badge.size, state.badge.margin, state.badge.opacity, app.translator.text("pdf.add_badge")))
        app.pdf_badge_enabled_var.set(state.badge.enabled)

    def visual_changed(self, enabled=None, *_args) -> None:
        self.set_badge(enabled=bool(self.state.badge.enabled) if enabled is None else bool(enabled))

    def select_badge(self, display_name: str) -> None:
        badge_id = self.app.badge_display_to_file.get(display_name, display_name)
        self.set_badge(badge_id=badge_id, enabled=bool(self.state.badge.enabled))

    def accept_file(self, path, info) -> None:
        apply_pdf_event(self.state, PdfEvent.FILE_SELECTED, {"path": path, "page_count": info.metrics.item_count})
        self.app.pdf_info = info
        self.project()

    def set_current_page(self, page: int) -> None:
        apply_pdf_event(self.state, PdfEvent.PREVIEW_PAGE_SELECTED, {"page": page}); self.project()

    def set_badge(self, **changes) -> None:
        apply_pdf_event(self.state, PdfEvent.BADGE_CHANGED, changes)
        self.project()
        self.refresh_preview()

    def choose_logo(self) -> None:
        from tkinter import filedialog
        selected = filedialog.askopenfilename(title="Choose logo", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")])
        if selected:
            self.set_logo(path=Path(selected), enabled=True)

    def set_logo(self, **changes) -> None:
        apply_pdf_event(self.state, PdfEvent.LOGO_CHANGED, changes)
        self.project()
        self.refresh_preview()

    def set_scope(self, mode: str, values: tuple[int, ...], text: str = "") -> None:
        apply_pdf_event(self.state, PdfEvent.SCOPE_MODE, {"mode": mode})
        if mode in {"selected", "range"}:
            apply_pdf_event(self.state, PdfEvent.SCOPE_TEXT_CHANGED, {"text": text})
            apply_pdf_event(self.state, PdfEvent.SCOPE_UPDATE, {"values": tuple(values), "text": text})
        self.project()

    def set_scope_mode(self, mode: str) -> None:
        apply_pdf_event(self.state, PdfEvent.SCOPE_MODE, {"mode": mode})
        self.project()

    def refresh_preview(self) -> None:
        """Render the current physical page from authoritative workspace state."""
        app = self.app; state = self.state
        if not state.path or not getattr(app, "pdf_preview_label", None):
            return
        info = getattr(app, "pdf_info", None)
        if info is None or not state.page_count:
            return
        try:
            current = max(1, min(state.page_count, state.current_page))
            marked = current in set(state.active_scope)
            badge = app.badges.find(state.badge.badge_id) if marked and state.badge.enabled else None
            logo = state.logo.path if marked and state.logo.enabled else None
            host = app.pdf_preview_host
            host.update_idletasks()
            width = max(1, host.winfo_width()); height = max(1, host.winfo_height())
            try:
                page = PdfProcessor._reader(state.path).pages[current - 1]
                aspect = float(page.mediabox.width) / max(1.0, float(page.mediabox.height))
            except (OSError, ValueError, IndexError):
                aspect = 1.0
            max_size = fit_preview_size(width, height, aspect, padding=16, navigation_height=48, target_fraction=0.8)
            result = app.pdf_preview_renderer.render(state.path, current, badge, app.settings(), logo, max_size=max_size)
            state.current_page = result.page_number
            self.preview_photo = ctk.CTkImage(light_image=result.image, dark_image=result.image, size=result.image.size)
            app.pdf_preview_label.configure(image=self.preview_photo, text="")
            app.pdf_preview_photo = self.preview_photo
            app.pdf_page_status.configure(text=f"{state.current_page} / {state.page_count}")
            app.pdf_previous_button.configure(state="normal" if state.current_page > 1 else "disabled")
            app.pdf_next_button.configure(state="normal" if state.current_page < state.page_count else "disabled")
            app._boot(f"PDF_HOST={width}x{height} PDF_FIT={max_size[0]}x{max_size[1]} PDF_RENDER={result.image.width}x{result.image.height} PDF_CTKIMAGE={result.image.width}x{result.image.height} PDF_LABEL={app.pdf_preview_label.winfo_width()}x{app.pdf_preview_label.winfo_height()}")
        except (OSError, ValueError) as error:
            app.pdf_preview_label.configure(image=None, text=f"Could not render PDF page: {error}")

    def _schedule_preview_refresh(self, _event=None):
        app = self.app
        if self._preview_resize_job is not None:
            try: app.pdf_preview_host.after_cancel(self._preview_resize_job)
            except Exception: pass
        self._preview_resize_job = app.pdf_preview_host.after(120, self.refresh_preview)

    def build_processing_request(self, destination: Path) -> PdfProcessingRequest:
        state = self.state; app = self.app
        badge = app.badges.find(state.badge.badge_id) if state.badge.enabled else None
        label = app.badges.display_name(state.badge.badge_id) if badge else ""
        settings = replace(app.settings(), position=state.badge.position, size_percent=state.badge.size, margin=state.badge.margin, opacity=state.badge.opacity, logo_enabled=state.logo.enabled, logo_path=str(state.logo.path or ""), logo_position=state.logo.position, logo_size_percent=state.logo.size, logo_margin=state.logo.margin, logo_opacity=state.logo.opacity)
        disclosure, logo = settings_for_documents(settings, label=label, disclosure_language=app.translator.language)
        request = ProcessingRequest(state.path, destination, disclosure, badge_path=badge, logo=logo, metadata=marker_metadata(disclosure.badge_name, disclosure.label))
        return PdfProcessingRequest(request, ItemSelection("selected", tuple(state.active_scope)))

    def save(self) -> None:
        app = self.app; state = self.state
        diagnostic = getattr(app, "_pdf_runtime_diagnostic", None)
        if callable(diagnostic):
            diagnostic("pdf_workspace_save_entered", {"callback": "PdfWorkspace.save", "owner_id": id(self), "state_path": str(state.path) if state.path else None, "badge_enabled": bool(state.badge.enabled), "badge_id": state.badge.badge_id})
        if not state.path or not getattr(app, "pdf_info", None):
            messagebox.showwarning(app.translator.text("warning.title"), app.translator.text("pdf.choose_first")); return
        if not app._confirm_pdf_limits_phase6() or not app._confirm_pdf_signature(): return
        destination_name = f"{state.path.stem}_ai.pdf"
        selected = filedialog.asksaveasfilename(title=app.translator.text("pdf.save_as"), initialdir=str(state.path.parent), initialfile=destination_name, defaultextension=".pdf", filetypes=[("PDF (*.pdf)", "*.pdf")], confirmoverwrite=True)
        if not selected: return
        destination = Path(selected)
        if destination.resolve() == state.path.resolve():
            messagebox.showerror(app.translator.text("error.title"), app.translator.text("pdf.extension_error")); return
        try:
            prepared = self.build_processing_request(destination)
            if prepared.request.badge_path is None and not prepared.request.logo.enabled:
                messagebox.showwarning(app.translator.text("warning.title"), app.translator.text("pdf.overlay_required")); return
            result = app.pdf_processor.process(prepared.request, prepared.selection)
        except (OSError, ValueError) as error:
            messagebox.showerror(app.translator.text("error.title"), app.translator.text("pdf.error", error=error)); return
        text = app.translator.text("pdf.saved", name=result.destination.name, count=len(result.selected_pages))
        app.status_var.set(text)
        messagebox.showinfo(app.translator.text("complete.title"), text)

    def has_active_work(self) -> bool:
        return getattr(self.state, "path", None) is not None

    def clear_runtime_state(self) -> None:
        if isinstance(self.state, PdfWorkspaceState):
            apply_pdf_event(self.state, PdfEvent.CLEAR_RUNTIME)
        else:
            self.state.clear()
        # B1 intentionally performs dual cleanup so existing Reset semantics
        # remain unchanged.  These fields/resources are removed in B2/B3.
        clear = getattr(self.app, "_clear_pdf_runtime_compat", None)
        if callable(clear):
            clear()

    def dispatch(self, event, payload=None):
        return apply_pdf_event(self.state, event, payload)

    def enter_clean(self):
        result = self.dispatch(PdfEvent.CLEAR_RUNTIME)
        self._ensure_badge_selection()
        # A clean lifecycle transition is complete only after its state has
        # been projected; file selection must not be required to populate the
        # default badge visual.
        if self.root is not None:
            self.project()
        return result

    def choose_file(self) -> None:
        app = self.app
        selected = filedialog.askopenfilename(title=app.translator.text("pdf.choose"), filetypes=[("PDF (*.pdf)", "*.pdf"), (app.translator.text("files.all"), "*.*")])
        if not selected:
            return
        path = Path(selected)
        try:
            info = app.pdf_processor.inspect(path)
        except Exception as error:
            messagebox.showerror(app.translator.text("error.title"), app.translator.text("pdf.error", error=error))
            return
        self.accept_file(path, info)
        app.pdf_info = info
        app.pdf_file_label.configure(text=f"{path.name}\n{info.metrics.size_bytes} · {info.metrics.item_count} pages")
        self.project()

        self.refresh_preview()
        diagnostic = getattr(app, "_pdf_runtime_diagnostic", None)
        if callable(diagnostic): diagnostic("pdf_choose_file_projected", {"owner_id": id(self), "state_path": str(self.state.path) if self.state.path else None})

