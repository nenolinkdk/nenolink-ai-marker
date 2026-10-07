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
