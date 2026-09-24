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
            self.assertTrue({"button.reset","button.back","dialog.save_as","batch.filename_suffix","status.reset","video.badge","video.mode.permanent","video.mode.beginning","video.mode.end","video.duration","video.seconds","video.settings","batch.output","batch.options","batch.progress_heading","button.process_video","warning.metadata_failed","tab.inspect","inspect.title","inspect.intro","inspect.choose","inspect.selected","inspect.file","inspect.format_size","inspect.metadata","inspect.status","inspect.software","inspect.ai_label","inspect.marker_version","inspect.found","inspect.not_found","inspect.not_available","inspect.error","inspect.ready","inspect.none","inspect.not_found_message","inspect.no_ai_warning","inspect.info","inspect.error_message","inspect.supported"}.issubset(data),code)
            self.assertNotIn("-",data["button.back"].removeprefix("←"),code)

    def test_update_check_is_translated_in_every_locale(self):
        locales=Path(__file__).resolve().parent.parent/"locales"
        keys={"update.automatic","update.check","update.checking","update.available","update.error","update.title","update.current","update.privacy"}
        for code in LANGUAGES.values():
            data=json.loads((locales/f"{code}.json").read_text(encoding="utf-8"))
            self.assertTrue(keys.issubset(data),code)

    def test_desktop_shortcut_is_translated_in_every_locale(self):
        locales=Path(__file__).resolve().parent.parent/"locales"
        keys={"shortcut.create","shortcut.title","shortcut.success","shortcut.error","shortcut.offer_title","shortcut.offer_message","shortcut.offer_create","shortcut.offer_not_now","badge.no_ai_disclaimer"}
        for code in LANGUAGES.values():
            data=json.loads((locales/f"{code}.json").read_text(encoding="utf-8"))
            self.assertTrue(keys.issubset(data),code)

    def test_content_type_shell_is_translated_in_every_locale(self):
        locales=Path(__file__).resolve().parent.parent/"locales"
        keys={"content.images","content.video","content.pdf","content.powerpoint","content.word","content.workspace","content.planned_title","content.planned_message"}
        for code in LANGUAGES.values():
            data=json.loads((locales/f"{code}.json").read_text(encoding="utf-8"))
            self.assertTrue(keys.issubset(data),code)
            self.assertTrue(all(data[key].strip() for key in keys),code)

    def test_powerpoint_workspace_is_translated_in_every_locale(self):
        locales=Path(__file__).resolve().parent.parent/"locales"
        keys={"pptx.choose","pptx.no_file","pptx.selected","pptx.scope","pptx.scope.single","pptx.scope.selected","pptx.scope.range","pptx.scope.all","pptx.slide","pptx.selected_hint","pptx.from","pptx.to","pptx.output_language","pptx.metadata_note","pptx.process","pptx.choose_first","pptx.save_as","pptx.extension_error","pptx.error","pptx.saved","pptx.preview_hint","pptx.preview_unavailable","pptx.slide_status","content.media_group","content.documents_group","document.summary.slides","document.warning_title","document.limit_title","document.pptx_warning","document.pptx_hard"}
        keys.update({"document.summary.pages","document.pdf_warning","document.pdf_hard","pdf.choose","pdf.no_file","pdf.selected","pdf.page","pdf.selected_hint","pdf.metadata_note","pdf.add_badge","pdf.overlay_required","pdf.process","pdf.scope","pdf.scope.single","pdf.scope.selected","pdf.scope.range","pdf.scope.all","pdf.preview_hint","pdf.preview_unavailable","pdf.page_status","pdf.encrypted","pdf.error","pdf.choose_first","pdf.save_as","pdf.extension_error","pdf.saved","pdf.signature_title","pdf.signature_warning"})
        for code in LANGUAGES.values():
            data=json.loads((locales/f"{code}.json").read_text(encoding="utf-8"))
            self.assertTrue(keys.issubset(data),code)
            self.assertTrue(all(data[key].strip() for key in keys),code)

    def test_word_workspace_is_translated_in_every_locale(self):
        locales=Path(__file__).resolve().parent.parent/"locales"
        keys={"document.summary.docx","document.docx_warning","document.docx_hard","docx.choose","docx.no_file","docx.selected","docx.whole_document","docx.scope","docx.scope.first","docx.scope.all","docx.add_badge","docx.process","docx.preview_hint","docx.preview_unavailable","docx.preview_approximate","docx.metadata_note","docx.overlay_required","docx.error","docx.choose_first","docx.save_as","docx.extension_error","docx.saved"}
        for code in LANGUAGES.values():
            data=json.loads((locales/f"{code}.json").read_text(encoding="utf-8"))
            self.assertTrue(keys.issubset(data),code)
            self.assertTrue(all(data[key].strip() for key in keys),code)

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
