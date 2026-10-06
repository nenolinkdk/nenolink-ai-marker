import inspect

from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.image_workspace import ImageWorkspace


def test_image_project_does_not_call_removed_markerapp_badge_preview():
    source = inspect.getsource(ImageWorkspace.project)
    assert "refresh_image_badges" not in source
    assert "update_image_badge_preview" not in source


def test_image_badge_refresh_has_no_removed_preview_target():
    source = inspect.getsource(MarkerApp.refresh_image_badges)
    assert "update_image_badge_preview" not in source
