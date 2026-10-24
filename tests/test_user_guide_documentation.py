from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pypdf import PdfReader

from nenolink_ai_marker import __version__
from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.paths import localized_user_guide_path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
GUIDES = {
    "DA": {
        "markdown": DOCS / "USER_GUIDE_DA.md",
        "pdf": DOCS / "Nenolink-AI-Marker-User-Guide-DA.pdf",
        "required": (
            "Undersøg fil", "Fundet", "Ikke fundet", "DOCX", "PDF",
            "Første slide", "Første 5 sekunder", "asynkront",
            "uafhængig verificering", "AI ikke blev brugt",
        ),
    },
    "EN": {
        "markdown": DOCS / "USER_GUIDE_EN.md",
        "pdf": DOCS / "Nenolink-AI-Marker-User-Guide-EN.pdf",
        "required": (
            "Inspect File", "Found", "Not found", "DOCX", "PDF",
            "First slide", "First 5 seconds", "asynchronously",
            "independent verification", "AI was not used",
        ),
    },
}


def _pdf_text(path: Path) -> str:
    return " ".join((page.extract_text() or "") for page in PdfReader(path).pages)


class UserGuideDocumentationTests(unittest.TestCase):
    def test_danish_and_english_sources_and_pdfs_cover_current_features(self):
        for language, guide in GUIDES.items():
            with self.subTest(language=language):
                source = guide["markdown"].read_text(encoding="utf-8")
                pdf_path = guide["pdf"]
                self.assertTrue(pdf_path.is_file(), pdf_path)
                text = " ".join(_pdf_text(pdf_path).split())
                self.assertIn(__version__, text)
                for phrase in guide["required"]:
                    self.assertIn(phrase.casefold(), text.casefold(), phrase)
                self.assertIn("Nulstil" if language == "DA" else "Reset", source)
                self.assertIn("PPTX", source)
                self.assertIn("Inspect File" if language == "DA" else "Inspect File", source)

    def test_guides_explain_declaration_not_verification_and_not_found_limit(self):
        for language, guide in GUIDES.items():
            source = guide["markdown"].read_text(encoding="utf-8").casefold()
            with self.subTest(language=language):
                self.assertTrue("uafhængig verificering" in source if language == "DA" else "independent verification" in source)
                self.assertTrue("ai ikke blev brugt" in source if language == "DA" else "ai was not used" in source)

    def test_obsolete_inspection_and_logo_claims_are_absent(self):
        da = GUIDES["DA"]["markdown"].read_text(encoding="utf-8").casefold()
        en = GUIDES["EN"]["markdown"].read_text(encoding="utf-8").casefold()
        self.assertNotIn("pdf-inspektion er endnu ikke understøttet", da)
        self.assertNotIn("pdf inspect is not supported yet", en)
        self.assertNotIn("det tilføjes ikke til video", da)
        self.assertNotIn("not applied to video", en)

    def test_actual_application_guide_command_selects_pdf_by_ui_language(self):
        for language in ("da", "en"):
            dummy = SimpleNamespace(translator=SimpleNamespace(language=language))
            with self.subTest(language=language), patch("nenolink_ai_marker.app.open_user_guide") as open_guide:
                MarkerApp.open_image_guide(dummy)
                open_guide.assert_called_once_with(localized_user_guide_path(language))

    def test_both_pdf_guides_are_in_pyinstaller_and_windows_distribution(self):
        spec = (ROOT / "Nenolink-AI-Marker.spec").read_text(encoding="utf-8")
        build = (ROOT / "build.ps1").read_text(encoding="utf-8")
        self.assertIn('"docs"', spec)
        self.assertIn('"docs")', spec)
        self.assertIn('docs\\*.pdf', build)


if __name__ == "__main__":
    unittest.main()
