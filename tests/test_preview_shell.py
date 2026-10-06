import inspect
from nenolink_ai_marker.preview_shell import PreviewShell
from nenolink_ai_marker.image_workspace import ImageWorkspace
from nenolink_ai_marker.video_workspace import VideoWorkspace
from nenolink_ai_marker.pdf_workspace import PdfWorkspace
from nenolink_ai_marker.pptx_workspace import PptxWorkspace

def test_preview_shell_is_presentation_only():
    source = inspect.getsource(PreviewShell)
    assert "WorkspaceState" not in source
    assert "processor" not in source.lower()
    assert "def __init__" in source

def test_each_workspace_owns_preview_shell_construction():
    for workspace in (ImageWorkspace, VideoWorkspace, PdfWorkspace, PptxWorkspace):
        source = inspect.getsource(workspace)
        assert "PreviewShell" in source
