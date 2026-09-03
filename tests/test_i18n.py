import json
from pathlib import Path
import tempfile
import unittest

from nenolink_ai_marker.i18n import LANGUAGES, Translator


class TranslationTests(unittest.TestCase):
    def test_all_declared_languages_load(self):
        locales = Path(__file__).resolve().parent.parent / "locales"
        self.assertEqual(len(LANGUAGES), 12)
        for code in LANGUAGES.values():
            data = json.loads((locales / f"{code}.json").read_text(encoding="utf-8"))
            self.assertEqual(data["app.window"], Translator(locales, code).text("app.window"))

    def test_welcome_keys_and_guide_button_exist_in_every_locale(self):
        locales = Path(__file__).resolve().parent.parent / "locales"
        keys = {"welcome.title", "welcome.tagline", "welcome.description1", "welcome.description2", "button.user_guide"}
        for code in LANGUAGES.values():
            data = json.loads((locales / f"{code}.json").read_text(encoding="utf-8"))
            self.assertTrue(keys.issubset(data),code)
            self.assertNotIn("Text unavailable",[data[key] for key in keys])

    def test_custom_badge_help_and_status_keys_exist_in_every_locale(self):
        locales = Path(__file__).resolve().parent.parent / "locales"
        keys = {"badge.help", "badge.custom_missing", "badge.custom_empty", "badge.loaded_custom"}
        for code in LANGUAGES.values():
            data = json.loads((locales / f"{code}.json").read_text(encoding="utf-8"))
            self.assertTrue(keys.issubset(data), code)
            self.assertNotIn("Text unavailable", [data[key] for key in keys])

    def test_position_values_are_localized_human_readable_labels(self):
        locales = Path(__file__).resolve().parent.parent / "locales"
        keys = {"position.top_left", "position.top_right", "position.bottom_left", "position.bottom_right", "position.center"}
        for code in LANGUAGES.values():
            data = json.loads((locales / f"{code}.json").read_text(encoding="utf-8"))
            self.assertTrue(keys.issubset(data), code)
            self.assertTrue(all("-" not in data[key] for key in keys), code)

    def test_file_size_guidance_is_translated_in_every_locale(self):
        locales=Path(__file__).resolve().parent.parent/"locales"
        keys={"files.size_guidance","files.size_guidance_short","warning.large_file","batch.oversized"}
        for code in LANGUAGES.values():
            data=json.loads((locales/f"{code}.json").read_text(encoding="utf-8"))
            self.assertTrue(keys.issubset(data),code)

    def test_reset_labels_are_translated_in_every_locale(self):
        locales=Path(__file__).resolve().parent.parent/"locales"
        for code in LANGUAGES.values():
            data=json.loads((locales/f"{code}.json").read_text(encoding="utf-8"))
            self.assertTrue({"button.reset","button.back","dialog.save_as","batch.filename_suffix","status.reset","video.badge","video.mode.permanent","video.mode.beginning","video.mode.end","video.duration","video.seconds","video.settings","batch.output","batch.options","batch.progress_heading","button.process_video","warning.metadata_failed"}.issubset(data),code)
            self.assertNotIn("-",data["button.back"].removeprefix("←"),code)

    def test_live_welcome_language_change_and_english_return(self):
        locales = Path(__file__).resolve().parent.parent / "locales"
        translator = Translator(locales,"en")
        self.assertEqual(translator.text("welcome.title"),"Welcome to Nenolink AI Marker")
        translator.set_language("da")
        self.assertEqual(translator.text("welcome.title"),"Velkommen til Nenolink AI Marker")
        translator.set_language("de")
        self.assertEqual(translator.text("welcome.title"),"Willkommen bei Nenolink AI Marker")
        translator.set_language("en")
        self.assertEqual(translator.text("welcome.title"),"Welcome to Nenolink AI Marker")

    def test_missing_key_falls_back_to_english(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "en.json").write_text('{"known": "English", "fallback": "Fallback"}', encoding="utf-8")
            (root / "da.json").write_text('{"known": "Dansk"}', encoding="utf-8")
            translator = Translator(root, "da")
            self.assertEqual(translator.text("known"), "Dansk")
            self.assertEqual(translator.text("fallback"), "Fallback")
            self.assertEqual(translator.text("unknown"), "Text unavailable")

    def test_missing_language_uses_english(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "en.json").write_text('{"key": "English"}', encoding="utf-8")
            self.assertEqual(Translator(root, "unsupported").text("key"), "English")

    def test_unavailable_locale_directory_uses_built_in_english(self):
        translator = Translator(Path("C:/definitely/missing/locales"), "da")
        self.assertEqual(translator.text("button.open_images"), "Choose Image")
        self.assertEqual(translator.text("button.user_guide"), "User Guide (PDF)")
        self.assertEqual(translator.text("unknown.internal.key"), "Text unavailable")


if __name__ == "__main__":
    unittest.main()
