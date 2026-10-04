"""PDF workspace lifecycle boundary.

This first migration step deliberately keeps the existing PDF view builder in
``MarkerApp``.  The workspace owns the lifecycle surface and delegates the
legacy view construction through a narrow compatibility adapter.  State and
event ownership move in the following PDF migration checkpoints.
"""
from __future__ import annotations

from pathlib import Path
import customtkinter as ctk
from .pdf_processor import PdfProcessor
from .document_preview_layout import fit_preview_size


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
        self.root = getattr(self.app, "pdf_workspace", None)

    def unmount(self) -> None:
        root = self.root or getattr(self.app, "pdf_workspace", None)
        if root is not None and root.winfo_exists():
            root.grid_remove()

    def project(self) -> None:
        app = self.app; state = self.state
        app.pdf_path = state.path
        app.pdf_current_page = state.current_page
        app.pdf_scope_mode = state.scope_mode
        app.pdf_scope_input = state.scope_input
        app.pdf_active_scope = tuple(state.active_scope)
        if state.path is None: app.pdf_info = None
        for name, value in (("pdf_badge_enabled_var", state.badge.enabled), ("badge_var", state.badge.badge_id), ("position_var", state.badge.position), ("size_var", state.badge.size), ("margin_var", state.badge.margin), ("opacity_var", state.badge.opacity), ("logo_enabled_var", state.logo.enabled), ("logo_path_var", str(state.logo.path or "")), ("logo_position_var", state.logo.position), ("logo_size_var", state.logo.size), ("logo_margin_var", state.logo.margin), ("logo_opacity_var", state.logo.opacity)):
            variable = getattr(app, name, None)
            if variable is not None: variable.set(value)

    def accept_file(self, path, info) -> None:
        self.state.path = path; self.state.page_count = info.metrics.item_count; self.state.current_page = 1
        self.state.scope_mode = "all"; self.state.scope_input = ""; self.state.active_scope = tuple(range(1, self.state.page_count + 1)); self.state.preview_image = None
        self.app.pdf_info = info
        self.project()

    def set_current_page(self, page: int) -> None:
        self.state.current_page = max(1, min(self.state.page_count, int(page))); self.project()

    def set_scope(self, mode: str, values: tuple[int, ...], text: str = "") -> None:
        self.state.scope_mode = mode; self.state.scope_input = text; self.state.active_scope = tuple(values)
        if values: self.state.current_page = values[0]
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
            self.project()
            self.preview_photo = ctk.CTkImage(light_image=result.image, dark_image=result.image, size=result.image.size)
            app.pdf_preview_label.configure(image=self.preview_photo, text="")
            app.pdf_preview_photo = self.preview_photo
            app.pdf_page_status.configure(text=f"{state.current_page} / {state.page_count}")
            app.pdf_previous_button.configure(state="normal" if state.current_page > 1 else "disabled")
            app.pdf_next_button.configure(state="normal" if state.current_page < state.page_count else "disabled")
            app._boot(f"PDF_HOST={width}x{height} PDF_FIT={max_size[0]}x{max_size[1]} PDF_RENDER={result.image.width}x{result.image.height} PDF_CTKIMAGE={result.image.width}x{result.image.height} PDF_LABEL={app.pdf_preview_label.winfo_width()}x{app.pdf_preview_label.winfo_height()}")
        except (OSError, ValueError) as error:
            app.pdf_preview_label.configure(image=None, text=f"Could not render PDF page: {error}")

    def has_active_work(self) -> bool:
        if getattr(self.state, "path", None) is not None:
            return True
        # Temporary compatibility fallback required until B2 migrates file
        # selection and removes MarkerApp.pdf_path.
        return getattr(self.app, "pdf_path", None) is not None

    def clear_runtime_state(self) -> None:
        self.state.clear()
        # B1 intentionally performs dual cleanup so existing Reset semantics
        # remain unchanged.  These fields/resources are removed in B2/B3.
        clear = getattr(self.app, "_clear_pdf_runtime_compat", None)
        if callable(clear):
            clear()

