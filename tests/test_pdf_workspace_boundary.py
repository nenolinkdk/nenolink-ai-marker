from types import SimpleNamespace

from nenolink_ai_marker.pdf_workspace import PdfWorkspace


class _State:
    def __init__(self, path=None):
        self.path = path
        self.cleared = False

    def clear(self):
        self.cleared = True
        self.path = None


def test_pdf_workspace_exposes_common_lifecycle_and_uses_existing_state():
    state = _State()
    app = SimpleNamespace(pdf_path="legacy.pdf")
    workspace = PdfWorkspace(app, state)

    assert workspace.state is state
    assert all(callable(getattr(workspace, name)) for name in (
        "mount", "unmount", "project", "has_active_work", "clear_runtime_state"
    ))
    assert workspace.has_active_work() is True


def test_pdf_unmount_does_not_clear_session():
    class Root:
        def winfo_exists(self): return True
        def grid_remove(self): self.removed = True

    state = _State("selected.pdf")
    root = Root()
    workspace = PdfWorkspace(SimpleNamespace(pdf_workspace=root), state)
    workspace.root = root
    workspace.unmount()
    assert state.path == "selected.pdf"


def test_pdf_clear_is_distinct_from_unmount_and_clears_compatibility_state():
    state = _State("selected.pdf")
    app = SimpleNamespace(pdf_path="selected.pdf", pdf_info="info")
    workspace = PdfWorkspace(app, state)

    def clear_compat():
        app.pdf_path = None
        app.pdf_info = None

    app._clear_pdf_runtime_compat = clear_compat
    workspace.clear_runtime_state()
    assert state.cleared is True
    assert app.pdf_path is None and app.pdf_info is None


def test_pdf_project_uses_temporary_existing_sync_boundary():
    calls = []
    state = _State()
    app = SimpleNamespace(_sync_pdf_state=lambda: calls.append("sync"))
    PdfWorkspace(app, state).project()
    assert calls == ["sync"]
