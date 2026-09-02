from pathlib import Path
import tempfile
import unittest

from nenolink_ai_marker.badges import BadgeRepository
from nenolink_ai_marker.config import ConfigStore
from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.paths import application_root, badge_directory


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

    def test_empty_badge_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.txt").touch()
            (root / ".gitkeep").touch()
            self.assertEqual(BadgeRepository(root).list_badges(), [])

    def test_source_mode_path(self):
        module = Path("C:/project/nenolink_ai_marker/paths.py")
        self.assertEqual(application_root(frozen=False, module_file=module), Path("C:/project"))
        self.assertEqual(
            badge_directory(frozen=False, module_file=module),
            Path("C:/project/assets/badges"),
        )

    def test_packaged_mode_path(self):
        executable = Path("C:/Apps/Nenolink-AI-Marker/Nenolink-AI-Marker.exe")
        self.assertEqual(
            badge_directory(frozen=True, executable=executable),
            Path("C:/Apps/Nenolink-AI-Marker/assets/badges"),
        )

    def test_path_is_independent_of_working_directory(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                import os
                os.chdir(directory)
                executable = Path("C:/Apps/Nenolink-AI-Marker/Nenolink-AI-Marker.exe")
                self.assertEqual(
                    badge_directory(frozen=True, executable=executable),
                    Path("C:/Apps/Nenolink-AI-Marker/assets/badges"),
                )
            finally:
                os.chdir(original)


if __name__ == "__main__":
    unittest.main()
