"""PDF workspace lifecycle boundary.

This first migration step deliberately keeps the existing PDF view builder in
``MarkerApp``.  The workspace owns the lifecycle surface and delegates the
legacy view construction through a narrow compatibility adapter.  State and
event ownership move in the following PDF migration checkpoints.
"""
from __future__ import annotations


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
        # B1 retains the existing synchronization direction.  B2 will replace
        # this with state-owned event projections.
        sync = getattr(self.app, "_sync_pdf_state", None)
        if callable(sync):
            sync()

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

