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

    def mount(self, host) -> None:
        # The host is retained for the eventual extracted builder.  For B1 the
        # compatibility builder still uses app.content_host and preserves the
        # verified PDF UI unchanged.
        self.app._build_pdf_workspace_compat(host)
        self.root = getattr(self.app, "pdf_workspace_root", None) or getattr(self.app, "pdf_workspace", None)

    def unmount(self) -> None:
        root = self.root or getattr(self.app, "pdf_workspace", None)
        if root is not None and root.winfo_exists():
            root.grid_remove()

    def project(self) -> None:
        app = self.app; state = self.state
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
        if getattr(app, "pdf_page_status", None) is not None:
            app.pdf_page_status.configure(text=(f"{state.current_page} / {state.page_count}" if state.path else "—"))
        if state.path and getattr(app, "pdf_info", None) is not None:
            self.refresh_preview()
        else:
            if getattr(app, "pdf_preview_label", None) is not None: app.pdf_preview_label.configure(image=None, text="PDF page preview")
            self.preview_photo = None; app.pdf_preview_photo = None
        if getattr(app, "_project_pdf_badge_selection", None): app._project_pdf_badge_selection()

    def _ensure_badge_selection(self) -> None:
        """Seed a valid default badge through the PDF event boundary."""
        state = self.state
        if state.badge.badge_id:
            return
        app = self.app
        candidate = ""
        badge_var = getattr(app, "badge_var", None)
        if badge_var is not None:
            candidate = str(badge_var.get() or "")
        badges = getattr(app, "badges", None)
        if badges is None or not badges.find(candidate):
            paths = tuple(badges.display_badges()) if badges is not None else ()
            candidate = paths[0].name if paths else ""
        if candidate:
            apply_pdf_event(state, PdfEvent.BADGE_CHANGED, {"badge_id": candidate})

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
        app._project_pdf_badge_selection()
        self.refresh_preview()
        diagnostic = getattr(app, "_pdf_runtime_diagnostic", None)
        if callable(diagnostic): diagnostic("pdf_choose_file_projected", {"owner_id": id(self), "state_path": str(self.state.path) if self.state.path else None})

