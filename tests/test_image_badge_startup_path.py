import inspect

from nenolink_ai_marker.app import LegacyMarkerApp, MarkerApp
from nenolink_ai_marker.image_workspace import ImageWorkspace
from nenolink_ai_marker.video_workspace import VideoWorkspace
from nenolink_ai_marker.pdf_workspace import PdfWorkspace
from nenolink_ai_marker.pptx_workspace import PptxWorkspace
from nenolink_ai_marker.workspace_state import ImageWorkspaceState, VideoWorkspaceState


def test_image_project_does_not_call_removed_markerapp_badge_preview():
    source = inspect.getsource(ImageWorkspace.project)
    assert "refresh_image_badges" not in source
    assert "update_image_badge_preview" not in source


def test_image_badge_refresh_has_no_removed_preview_target():
    source = inspect.getsource(MarkerApp.refresh_image_badges)
    assert "update_image_badge_preview" not in source


def test_image_translation_does_not_reference_removed_badge_widget():
    source = inspect.getsource(MarkerApp.apply_image_translations)
    assert "single_badge_label" not in source
    assert "logo_position_menu" not in source


def test_image_projection_uses_workspace_translation_projection():
    source = inspect.getsource(ImageWorkspace.project)
    assert "apply_image_translations" not in source
    assert "apply_translations" in source


def test_workspace_projection_does_not_call_markerapp_translation_routines():
    for workspace_type in (ImageWorkspace, VideoWorkspace, PdfWorkspace, PptxWorkspace):
        source = inspect.getsource(workspace_type.project)
        assert "apply_image_translations" not in source
        assert "apply_video_translations" not in source
        assert "apply_pdf_translations" not in source
        assert "apply_pptx_translations" not in source


def test_global_translation_does_not_reference_removed_image_badge_widget():
    source = inspect.getsource(LegacyMarkerApp.apply_translations)
    assert "single_badge_label" not in source


def test_clean_image_and_video_state_has_valid_default_badge_id():
    assert ImageWorkspaceState().badge.enabled is True
    assert ImageWorkspaceState().badge.badge_id == "ai-assisted.png"
    assert VideoWorkspaceState().badge.enabled is True
    assert VideoWorkspaceState().badge.badge_id == "ai-assisted.png"
