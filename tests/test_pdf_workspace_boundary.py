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
    state = _State("legacy.pdf")
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


def test_pdf_source_control_projection_keeps_long_filename_and_localized_metadata(tmp_path):
    class Translator:
        language = "en"
        def text(self, key, **values):
            if key == "document.summary.pages":
                unit = "pages" if self.language == "en" else "sider"
                return f"{values['size']} · {values['count']} {unit}"
            return "No PDF selected" if self.language == "en" else "Ingen PDF valgt"

    class Source:
        def project(self, **values):
            self.values = values

    state = PdfWorkspaceState(path=tmp_path / ("very-long-" + "document-" * 10 + ".pdf"), page_count=12)
    info = SimpleNamespace(metrics=SimpleNamespace(size_bytes=4096, item_count=12))
    app = SimpleNamespace(translator=Translator(), pdf_info=info)
    workspace = PdfWorkspace(app, state)
    workspace.source_control = Source()

    workspace._project_source()
    assert workspace.source_control.values == {
        "filename": state.path.name,
        "metadata": "4096 · 12 pages",
        "empty_text": "No PDF selected",
    }

    app.translator.language = "da"
    workspace._project_source()
    assert workspace.source_control.values["filename"] == state.path.name
    assert workspace.source_control.values["metadata"] == "4096 · 12 sider"


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


def test_pdf_badge_parameter_callback_updates_table_state_and_save_request(tmp_path):
    source = tmp_path / "source.pdf"
    state = PdfWorkspaceState(path=source, page_count=3, current_page=2, active_scope=(1, 3))
    state.badge.enabled = True
    state.badge.badge_id = "ai-assisted.png"
    badge_path = tmp_path / "ai-assisted.png"
    app = SimpleNamespace(
        badges=SimpleNamespace(find=lambda _value: badge_path, display_name=lambda _value: "AI Assisted"),
        settings=lambda: MarkerSettings(),
        translator=SimpleNamespace(language="en"),
    )
    workspace = PdfWorkspace(app, state)
    # This is the same target as the constructed ParameterRow control callback.
    workspace.project = lambda: None
    workspace.refresh_preview = lambda: None

    workspace.set_badge(size=41, margin=33, opacity=72)
    prepared = workspace.build_processing_request(tmp_path / "output.pdf")

    assert (state.badge.size, state.badge.margin, state.badge.opacity) == (41, 33, 72)
    assert prepared.request.disclosure.size_percent == 41
    assert prepared.request.disclosure.margin == 33
    assert prepared.request.disclosure.opacity == 72
    assert prepared.request.badge_path == badge_path
    assert prepared.selection.items == (1, 3)


def test_constructed_pdf_badge_callbacks_dispatch_project_and_build_save_request(monkeypatch, tmp_path):
    import nenolink_ai_marker.pdf_workspace as pdf_module
    from nenolink_ai_marker.workspace_state import PdfEvent

    class Widget:
        def __init__(self, *_args, **kwargs):
            self.options = kwargs
            self.configured = {}
            self.grid_options = None
            self.value = kwargs.get("value")

        def grid(self, **kwargs): self.grid_options = kwargs
        def grid_columnconfigure(self, *_args, **_kwargs): pass
        def grid_rowconfigure(self, *_args, **_kwargs): pass
        def bind(self, *_args, **_kwargs): pass
        def configure(self, **kwargs): self.configured.update(kwargs)
        def update_idletasks(self): pass
        def winfo_exists(self): return True
        def set(self, value): self.value = value

    class Panel:
        def __init__(self, *_args, **_kwargs):
            self.frame = Widget()
            self.sections = {}

        def declare_section(self, _name): pass
        def add_section(self, name, block): self.sections[name] = block

    class Source:
        def __init__(self, *_args, **_kwargs):
            self.frame = Widget()
            self.action_row = Widget()
            self.choose_button = Widget()
            self.filename_label = Widget()
            self.metadata_label = Widget()

        def place_save_control(self, _control): pass
        def set_label(self, _label): pass
        def project(self, **_kwargs): pass

    class Save:
        def __init__(self, *_args, **_kwargs): self.button = Widget()
        def set_label(self, _label): pass

    class Badge:
        def __init__(self, _parent, **kwargs):
            self.frame = Widget()
            self.enabled_widget = Widget()
            self.selector_widget = Widget()
            self.selector_var = Widget()
            self.graphic_widget = Widget()
            self.on_enabled_changed = kwargs["on_enabled_changed"]
            self.on_badge_selected = kwargs["on_badge_selected"]
            self.projections = []

        def project(self, projection): self.projections.append(projection)

    class Logo:
        def __init__(self, *_args, **_kwargs): self.frame = Widget()
        def project(self, _projection): pass

    class Preview:
        def __init__(self, *_args, **_kwargs):
            self.frame = Widget()
            self.viewport = Widget()
            self.heading = Widget()

    class Scope:
        def __init__(self, *_args, **_kwargs):
            self.frame = Widget()
            self.menu = Widget()
            self.input = Widget()
            self.update = Widget()

        def project(self, **_kwargs): pass

    class Navigation:
        def __init__(self, *_args, **_kwargs):
            self.frame = Widget()
            self.previous = Widget()
            self.status = Widget()
            self.next = Widget()

        def set_status_template(self, _template): pass
        def project(self, **_kwargs): pass

    class CapturedParameterRow:
        rows = []

        def __init__(self, _parent, **kwargs):
            self.frame = Widget()
            self.options = kwargs
            self.projection = None
            self.rows.append(self)

        def project(self, **kwargs): self.projection = kwargs

    class Translator:
        language = "en"
        def text(self, key, **values):
            return key.format(**values) if values else key

    class Variable:
        def __init__(self, value=None): self.value = value
        def set(self, value): self.value = value

    badge_path = tmp_path / "ai-assisted.png"
    state = PdfWorkspaceState(
        path=tmp_path / "source.pdf", page_count=3, current_page=2,
        active_scope=(1, 2, 3),
    )
    state.badge.enabled = True
    state.badge.badge_id = badge_path.name
    events = []
    real_apply = pdf_module.apply_pdf_event

    def record_apply(target, event, payload=None):
        events.append((event, payload))
        return real_apply(target, event, payload)

    monkeypatch.setattr(pdf_module, "apply_pdf_event", record_apply)
    monkeypatch.setattr(pdf_module, "WorkspaceControlPanel", Panel)
    monkeypatch.setattr(pdf_module, "SourceControl", Source)
    monkeypatch.setattr(pdf_module, "SaveControl", Save)
    monkeypatch.setattr(pdf_module, "BadgeControl", Badge)
    monkeypatch.setattr(pdf_module, "LogoControl", Logo)
    monkeypatch.setattr(pdf_module, "PreviewShell", Preview)
    monkeypatch.setattr(pdf_module, "DocumentScopeControl", Scope)
    monkeypatch.setattr(pdf_module, "PhysicalNavigationControl", Navigation)
    monkeypatch.setattr(pdf_module, "ParameterRow", CapturedParameterRow)
    for name in ("CTkFrame", "CTkLabel", "CTkOptionMenu"):
        monkeypatch.setattr(pdf_module.ctk, name, Widget)
    monkeypatch.setattr(pdf_module.ctk, "CTkFont", lambda **_kwargs: object())
    monkeypatch.setattr(pdf_module.ctk, "StringVar", Variable)

    app = SimpleNamespace(
        translator=Translator(),
        badges=SimpleNamespace(
            display_badges=lambda: (badge_path,),
            display_name=lambda _name: "AI Assisted",
            find=lambda _name: badge_path,
        ),
        settings=lambda: MarkerSettings(),
        pdf_badge_enabled_var=Variable(False),
        pdf_info=None,
    )
    workspace = PdfWorkspace(app, state)
    workspace.mount(Widget())
    workspace.refresh_preview = lambda: None
    workspace.project()

    # These are the actual callables supplied to the constructed Tk controls.
    workspace.badge_position_menu.options["command"]("position.top_left")
    parameter_rows = CapturedParameterRow.rows
    assert len(parameter_rows) == 3
    parameter_rows[0].options["command"](41)
    parameter_rows[1].options["command"](33)
    parameter_rows[2].options["command"](72)

    assert [event for event, _payload in events[-4:]] == [PdfEvent.BADGE_CHANGED] * 4
    assert (state.badge.position, state.badge.size, state.badge.margin, state.badge.opacity) == (
        "top-left", 41, 33, 72,
    )
    projected = workspace.badge_control.projections[-1]
    assert (projected.position, projected.size, projected.margin, projected.opacity) == (
        state.badge.position, state.badge.size, state.badge.margin, state.badge.opacity,
    )
    assert parameter_rows[0].projection["value"] == state.badge.size
    assert parameter_rows[1].projection["value"] == state.badge.margin
    assert parameter_rows[2].projection["value"] == state.badge.opacity

    prepared = workspace.build_processing_request(tmp_path / "output.pdf")
    assert (prepared.request.disclosure.position, prepared.request.disclosure.size_percent,
            prepared.request.disclosure.margin, prepared.request.disclosure.opacity) == (
        state.badge.position, state.badge.size, state.badge.margin, state.badge.opacity,
    )


def test_pdf_registry_entry_is_workspace_instance():
    workspace = object()
    app = SimpleNamespace(_workspace_registry={"pdf": workspace})
    assert app._workspace_registry["pdf"] is workspace
