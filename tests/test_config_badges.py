from pathlib import Path
import tempfile
import unittest

from nenolink_ai_marker.badges import BadgeRepository, BadgeSourceManager
from nenolink_ai_marker.config import ConfigStore
from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.paths import application_root, badge_directory, locale_directory


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

    def test_standard_and_custom_badge_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard = root / "standard"; custom = root / "custom"
            standard.mkdir(); custom.mkdir()
            (standard / "standard.png").touch(); (custom / "custom.png").touch()
            manager = BadgeSourceManager(standard)
            self.assertEqual([p.name for p in manager.repository("standard").list_badges()], ["standard.png"])
            self.assertEqual([p.name for p in manager.repository("custom", str(custom)).list_badges()], ["custom.png"])
            self.assertEqual([p.name for p in manager.repository("standard", str(custom)).list_badges()], ["standard.png"])

    def test_missing_custom_folder_falls_back_to_standard(self):
        with tempfile.TemporaryDirectory() as directory:
            standard = Path(directory) / "standard"; standard.mkdir()
            (standard / "standard.png").touch()
            manager = BadgeSourceManager(standard)
            repository = manager.repository("custom", str(Path(directory) / "missing"))
            self.assertEqual(repository.directory, standard)
            self.assertTrue(manager.fallback_reason)

    def test_refresh_discovers_new_badge(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = BadgeRepository(root)
            self.assertEqual(repository.list_badges(), [])
            (root / "new.png").touch()
            self.assertEqual([p.name for p in repository.list_badges()], ["new.png"])

    def test_badge_and_language_settings_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "settings.json")
            expected = MarkerSettings(
                badge_name="custom.png", position="top-right", size_percent=42,
                margin=9, opacity=75, language="da", badge_source="custom",
                custom_badge_folder="C:/badges",
            )
            store.save(expected)
            self.assertEqual(store.load(), expected)

    def test_locale_resource_paths(self):
        module = Path("C:/project/nenolink_ai_marker/paths.py")
        self.assertEqual(locale_directory(frozen=False, module_file=module), Path("C:/project/locales"))
        executable = Path("C:/Apps/Nenolink-AI-Marker/Nenolink-AI-Marker.exe")
        self.assertEqual(locale_directory(frozen=True, executable=executable), Path("C:/Apps/Nenolink-AI-Marker/locales"))


if __name__ == "__main__":
    unittest.main()
