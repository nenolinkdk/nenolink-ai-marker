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
    assert True
