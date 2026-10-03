from pathlib import Path
from types import SimpleNamespace

from nenolink_ai_marker.badges import BadgeSourceManager
from nenolink_ai_marker.app import MarkerApp


def test_standard_badge_repository_enumerates_assets_and_manifest():
    root = Path(__file__).parents[1] / "assets" / "badges"
    repository = BadgeSourceManager(root).standard_repository()
    badges = repository.display_badges()
    assert len(badges) == 11
    assert all(path.is_file() for path in badges)
    assert all(repository.metadata(path.name) is not None for path in badges)


def test_continue_cleanup_calls_pptx_workspace_clear_runtime_state():
    called = []
    app = MarkerApp.__new__(MarkerApp)
    app.pptx_workspace_state = SimpleNamespace(clear_runtime_state=lambda: called.append(True))
    app.pptx_path = app.pptx_metrics = object()
    app.pptx_current_slide = 4; app.pptx_preview_photo = object()
    app.pptx_scope_mode = "selected"; app.pptx_active_scope = (2, 4); app.pptx_scope_input = "2,4"
    MarkerApp._clear_workspace_runtime(app, "pptx")
    assert called == [True]
    assert app.pptx_path is None and app.pptx_metrics is None
    assert app.pptx_current_slide == 0 and app.pptx_active_scope == ()
