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
