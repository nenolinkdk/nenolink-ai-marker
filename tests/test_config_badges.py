from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from nenolink_ai_marker.badges import BadgeRepository, BadgeSourceManager, EXPECTED_STANDARD_BADGES, choose_badge_selection, custom_badge_display_name
from nenolink_ai_marker.config import ConfigStore, default_config_path
from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.paths import application_root, badge_directory, locale_directory, welcome_image_path


class ConfigAndBadgeTests(unittest.TestCase):
    def test_missing_settings_file_returns_sensible_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = ConfigStore(Path(directory) / "missing.json").load()
            self.assertEqual(settings.language, "en")
            self.assertEqual(settings.badge_source, "standard")
            self.assertEqual(settings.custom_badge_folder, "")

    def test_default_settings_path_uses_roaming_appdata(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"APPDATA": directory}):
            self.assertEqual(default_config_path(), Path(directory) / "Nenolink" / "AI Marker" / "settings.json")

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
            (root / "photo.jpg").touch()
            (root / "portrait.JPEG").touch()
            (root / "label.webp").touch()
            (root / "ignore.txt").touch()
            self.assertEqual(
                [p.name for p in BadgeRepository(root).list_badges()],
                ["a.PNG", "B.png", "label.webp", "photo.jpg", "portrait.JPEG"],
            )

    def test_custom_filename_becomes_readable_display_name(self):
        self.assertEqual(custom_badge_display_name("my-company-ai-assisted.png"), "My Company AI Assisted")
        self.assertEqual(custom_badge_display_name("human_reviewed_red.png"), "Human Reviewed Red")
        self.assertEqual(custom_badge_display_name("ai-generated-company-x.webp"), "AI Generated Company X")

    def test_standard_badges_use_documented_ui_order_and_names(self):
        repository = BadgeRepository(Path("assets/badges"), standard=True)
        self.assertEqual([path.name for path in repository.display_badges()], list(EXPECTED_STANDARD_BADGES))
        self.assertEqual(
            [repository.display_name(path.name) for path in repository.display_badges()],
            ["AI Assisted", "AI Generated", "AI Modified", "Human Reviewed", "AI Image",
             "AI Video", "AI Audio", "AI Software", "AI Translation", "AI Localization"],
        )

    def test_standard_gallery_ignores_nonstandard_image_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ai-assisted.png").touch(); (root / "unofficial.jpg").touch()
            self.assertEqual(
                [path.name for path in BadgeRepository(root, standard=True).display_badges()],
                ["ai-assisted.png"],
            )

    def test_default_badge_is_ai_assisted(self):
        self.assertEqual(MarkerSettings().badge_name, "ai-assisted.png")

    def test_batch_suffix_is_persistent_and_invalid_values_are_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            store=ConfigStore(Path(directory)/"settings.json")
            store.save(MarkerSettings(batch_filename_suffix="_published"))
            self.assertEqual(store.load().batch_filename_suffix,"_published")
        self.assertEqual(MarkerSettings(batch_filename_suffix="").validated().batch_filename_suffix,"_ai")
        self.assertEqual(MarkerSettings(batch_filename_suffix='<>:"/\\|?*').validated().batch_filename_suffix,"_ai")

    def test_video_mode_and_duration_persist_with_safe_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            store=ConfigStore(Path(directory)/"settings.json")
            store.save(MarkerSettings(video_mode="end",video_duration=10))
            restored=store.load()
            self.assertEqual((restored.video_mode,restored.video_duration),("end",10))
        defaults=MarkerSettings()
        self.assertEqual((defaults.video_mode,defaults.video_duration),("permanent",5))
        invalid=MarkerSettings(video_mode="unknown",video_duration=0).validated()
        self.assertEqual((invalid.video_mode,invalid.video_duration),("permanent",1))

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

    def test_missing_custom_folder_stays_custom_and_reports_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            standard = Path(directory) / "standard"; standard.mkdir()
            (standard / "standard.png").touch()
            manager = BadgeSourceManager(standard)
            repository = manager.repository("custom", str(Path(directory) / "missing"))
            self.assertEqual(repository.directory, Path(directory) / "missing")
            self.assertEqual(repository.list_badges(), [])
            self.assertTrue(manager.fallback_reason)

    def test_empty_custom_folder_returns_no_badges(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "notes.txt").touch()
            manager = BadgeSourceManager(root / "standard")
            self.assertEqual(manager.repository("custom", str(root)).list_badges(), [])
            self.assertFalse(manager.fallback_reason)

    def test_source_switching_restores_standard_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); standard = root / "standard"; custom = root / "custom"
            standard.mkdir(); custom.mkdir()
            (standard / "ai-assisted.png").touch(); (custom / "my-ai.webp").touch()
            manager = BadgeSourceManager(standard)
            self.assertEqual(manager.repository("custom", str(custom)).list_badges()[0].name, "my-ai.webp")
            self.assertEqual(manager.repository("standard", str(custom)).list_badges()[0].name, "ai-assisted.png")

    def test_badge_selection_fallback_rules(self):
        standard = ["ai-generated.png", "ai-assisted.png"]
        custom = ["company-one.jpg", "company-two.webp"]
        self.assertEqual(choose_badge_selection("standard", standard, "missing.png"), "ai-assisted.png")
        self.assertEqual(choose_badge_selection("custom", custom, "missing.png"), "company-one.jpg")
        self.assertEqual(choose_badge_selection("custom", custom, "company-two.webp"), "company-two.webp")
        self.assertEqual(choose_badge_selection("custom", [], "missing.png"), "")

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
            restarted_store = ConfigStore(store.path)
            restored = restarted_store.load()
            self.assertEqual(restored.language, "da")
            self.assertEqual(restored.badge_source, "custom")
            self.assertEqual(restored.custom_badge_folder, "C:/badges")
            self.assertEqual(restored.badge_name, "custom.png")
            self.assertEqual(restored, expected)

    def test_locale_resource_paths(self):
        module = Path("C:/project/nenolink_ai_marker/paths.py")
        self.assertEqual(locale_directory(frozen=False, module_file=module), Path("C:/project/locales"))
        executable = Path("C:/Apps/Nenolink-AI-Marker/Nenolink-AI-Marker.exe")
        self.assertEqual(locale_directory(frozen=True, executable=executable), Path("C:/Apps/Nenolink-AI-Marker/locales"))

    def test_packaged_resources_fall_back_to_embedded_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "locales").mkdir()
            (bundle / "assets" / "badges").mkdir(parents=True)
            (bundle / "docs").mkdir()
            executable = Path("C:/Standalone/Nenolink-AI-Marker.exe")
            self.assertEqual(locale_directory(frozen=True, executable=executable, bundle_root=bundle), bundle / "locales")
            self.assertEqual(badge_directory(frozen=True, executable=executable, bundle_root=bundle), bundle / "assets" / "badges")

    def test_welcome_image_uses_source_and_packaged_resource_roots(self):
        module = Path("C:/project/nenolink_ai_marker/paths.py")
        self.assertEqual(welcome_image_path(frozen=False,module_file=module),Path("C:/project/assets/ui/welcome-europe.png"))
        executable = Path("C:/Apps/Nenolink-AI-Marker/Nenolink-AI-Marker.exe")
        self.assertEqual(welcome_image_path(frozen=True,executable=executable),Path("C:/Apps/Nenolink-AI-Marker/assets/ui/welcome-europe.png"))


if __name__ == "__main__":
    unittest.main()
