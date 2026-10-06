import inspect

from nenolink_ai_marker.app import LegacyMarkerApp, MarkerApp
from nenolink_ai_marker.image_workspace import ImageWorkspace
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


def test_global_translation_does_not_reference_removed_image_badge_widget():
    source = inspect.getsource(LegacyMarkerApp.apply_translations)
    assert "single_badge_label" not in source


def test_clean_image_and_video_state_has_valid_default_badge_id():
    assert ImageWorkspaceState().badge.enabled is True
    assert ImageWorkspaceState().badge.badge_id == "ai-assisted.png"
    assert VideoWorkspaceState().badge.enabled is True
    assert VideoWorkspaceState().badge.badge_id == "ai-assisted.png"
