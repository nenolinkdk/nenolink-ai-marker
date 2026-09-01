from pathlib import Path
import tempfile
import unittest

from nenolink_ai_marker.badges import BadgeRepository
from nenolink_ai_marker.config import ConfigStore
from nenolink_ai_marker.models import MarkerSettings


class ConfigAndBadgeTests(unittest.TestCase):
    def test_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "settings.json")
            expected = MarkerSettings("approved.png", "top-left", 33, 12, 70)
            store.save(expected)
            self.assertEqual(store.load(), expected)

    def test_invalid_config_returns_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("not json", encoding="utf-8")
            self.assertEqual(ConfigStore(path).load(), MarkerSettings())

    def test_badge_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "B.png").touch()
            (root / "a.PNG").touch()
            (root / "ignore.jpg").touch()
            self.assertEqual([p.name for p in BadgeRepository(root).list_badges()], ["a.PNG", "B.png"])


if __name__ == "__main__":
    unittest.main()
