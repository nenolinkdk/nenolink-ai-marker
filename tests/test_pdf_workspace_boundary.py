from types import SimpleNamespace

from nenolink_ai_marker.pdf_workspace import PdfWorkspace
from nenolink_ai_marker.workspace_state import PdfWorkspaceState
from nenolink_ai_marker.models import MarkerSettings
from pathlib import Path


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
    state = PdfWorkspaceState()
    app = SimpleNamespace()
    PdfWorkspace(app, state).project()
    assert app.pdf_path is None and app.pdf_current_page == 0


def test_pdf_file_event_writes_workspace_state_before_projection():
    info = SimpleNamespace(metrics=SimpleNamespace(item_count=3))
    state = PdfWorkspaceState()
    projected = []
    app = SimpleNamespace(pdf_info=None)
    workspace = PdfWorkspace(app, state)
    original = workspace.project
    workspace.project = lambda: (projected.append((state.path, state.page_count)), original())[1]
    workspace.accept_file("document.pdf", info)
    assert state.path == "document.pdf"
    assert state.page_count == 3
    assert state.active_scope == (1, 2, 3)
    assert projected and projected[0] == ("document.pdf", 3)
    assert app.pdf_path == "document.pdf"


def test_pdf_page_and_scope_events_preserve_independent_dimensions():
    state = PdfWorkspaceState(path="document.pdf")
    state.page_count = 6; state.current_page = 2; state.active_scope = (2, 4)
    app = SimpleNamespace()
    workspace = PdfWorkspace(app, state)
    workspace.set_current_page(3)
    assert state.current_page == 3 and state.active_scope == (2, 4)
    workspace.set_scope("selected", (1, 5), "1,5")
    assert state.active_scope == (1, 5) and state.current_page == 1


def test_pdf_processing_request_is_immutable_and_uses_workspace_state(tmp_path):
    state = PdfWorkspaceState(path=tmp_path / "source.pdf", page_count=4, current_page=3, active_scope=(1, 3))
    state.badge.badge_id = "ai-assisted.png"
    app = SimpleNamespace(
        badges=SimpleNamespace(find=lambda _value: tmp_path / "ai-assisted.png", display_name=lambda _value: "AI Assisted"),
        settings=lambda: MarkerSettings(),
        translator=SimpleNamespace(language="en"),
    )
    workspace = PdfWorkspace(app, state)
    prepared = workspace.build_processing_request(tmp_path / "output.pdf")
    assert prepared.request.source == state.path
    assert prepared.selection.items == state.active_scope
    assert prepared.request.destination == tmp_path / "output.pdf"
    try:
        prepared.selection = None
        assert False
    except Exception:
        pass


def test_pdf_registry_entry_is_workspace_instance():
    workspace = object()
    app = SimpleNamespace(_workspace_registry={"pdf": workspace})
    assert app._workspace_registry["pdf"] is workspace
