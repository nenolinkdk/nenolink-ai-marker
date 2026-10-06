import inspect

from nenolink_ai_marker.app import MarkerApp


def test_removed_image_badge_overwrite_helper_is_not_production_api():
    assert not hasattr(MarkerApp, "_update_badge_controls")


def test_production_registry_has_four_workspace_instances():
    source = inspect.getsource(MarkerApp.__init__)
    for token in ("image_workspace_owner", "video_workspace_owner", "pdf_workspace_owner", "pptx_workspace_state"):
        assert token in source


def test_workspace_mount_adapters_are_thin_lifecycle_delegates():
    for name in ("_mount_image_workspace", "_mount_video_workspace", "_mount_pdf_workspace", "_mount_pptx_workspace"):
        source = inspect.getsource(getattr(MarkerApp, name))
        assert ".mount(" in source
