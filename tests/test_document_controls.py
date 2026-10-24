import inspect
from nenolink_ai_marker.document_controls import DocumentScopeControl, PhysicalNavigationControl

def test_document_controls_are_stateless():
    for cls in (DocumentScopeControl, PhysicalNavigationControl):
        source = inspect.getsource(cls)
        assert "WorkspaceState" not in source
        assert "processor" not in source.lower()

def test_document_controls_are_presentation_components():
    assert "def project" in inspect.getsource(DocumentScopeControl)
    assert "def project" in inspect.getsource(PhysicalNavigationControl)


def test_scope_projection_disables_and_dashes_non_editable_modes():
    class Var:
        def __init__(self): self.value = None
        def set(self, value): self.value = value

    class Widget:
        def configure(self, **kwargs): self.options.update(kwargs)
        def __init__(self): self.options = {}

    class Status(Widget): pass

    control = DocumentScopeControl.__new__(DocumentScopeControl)
    control.mode_var = Var(); control.input_var = Var()
    control.input = Widget(); control.status = Status()
    for mode in ("All", "First page"):
        control.project(mode=mode, draft="2-3", input_enabled=False)
        assert control.mode_var.value == mode
        assert control.input_var.value == "—"
        assert control.input.options["state"] == "disabled"
    for mode in ("Selected pages", "Page range"):
        control.project(mode=mode, draft="2-3", input_enabled=True)
        assert control.input_var.value == "2-3"
        assert control.input.options["state"] == "normal"
