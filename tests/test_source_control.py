import inspect

from nenolink_ai_marker.source_control import SourceControl
from nenolink_ai_marker.image_workspace import ImageWorkspace
from nenolink_ai_marker.video_workspace import VideoWorkspace
from nenolink_ai_marker.pdf_workspace import PdfWorkspace
from nenolink_ai_marker.pptx_workspace import PptxWorkspace
from nenolink_ai_marker.workspace_ui import Section
from nenolink_ai_marker.badge_control import BadgeControl


def test_source_control_is_stateless_presentation_only():
    source = inspect.getsource(SourceControl)
    assert "WorkspaceState" not in source
    assert "MarkerApp" not in source
    assert "def project" in source


def test_each_workspace_constructs_its_own_source_control():
    for workspace in (ImageWorkspace, VideoWorkspace, PdfWorkspace, PptxWorkspace):
        source = inspect.getsource(workspace._build_ui if hasattr(workspace, "_build_ui") else workspace.mount)
        assert "SourceControl" in source


def test_source_callbacks_are_injected_per_workspace():
    for workspace in (ImageWorkspace, VideoWorkspace, PdfWorkspace, PptxWorkspace):
        source = inspect.getsource(workspace._build_ui if hasattr(workspace, "_build_ui") else workspace.mount)
        assert "choose_command=" in source

def test_section_and_badge_controls_are_presentation_only():
    assert "WorkspaceState" not in inspect.getsource(Section)
    source = inspect.getsource(BadgeControl)
    assert "WorkspaceState" not in source
    assert "processor" not in source.lower()
    assert "AI BADGE" in source
