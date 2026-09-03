import json
from pathlib import Path

from nenolink_ai_marker import __version__


ROOT = Path(__file__).resolve().parents[1]


def test_release_facing_version_is_consistent():
    assert __version__ == "0.5.0"
    for relative in ("README.md", "docs/USER_GUIDE_EN.md", "docs/USER_GUIDE_DA.md"):
        assert "0.5.0" in (ROOT / relative).read_text(encoding="utf-8")


def test_every_locale_has_the_complete_english_key_set():
    english = json.loads((ROOT / "locales/en.json").read_text(encoding="utf-8"))
    for path in (ROOT / "locales").glob("*.json"):
        values = json.loads(path.read_text(encoding="utf-8"))
        assert set(values) == set(english), path.name


def test_release_docs_cover_current_workflows():
    expectations = {
        "docs/USER_GUIDE_EN.md": ("Save Marked Image", "Permanent", "Beginning", "End", "Back", "Reset", "Inspect File"),
        "docs/USER_GUIDE_DA.md": ("Gem mærket billede", "Hele videoen", "I begyndelsen", "I slutningen", "Tilbage", "Nulstil", "Undersøg fil"),
    }
    for relative, terms in expectations.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert all(term in text for term in terms), relative


def test_distribution_notices_cover_runtime_and_ffmpeg():
    runtime = (ROOT / "THIRD_PARTY_NOTICES/RUNTIME_COMPONENTS.md").read_text(encoding="utf-8")
    ffmpeg = (ROOT / "THIRD_PARTY_NOTICES/FFMPEG.md").read_text(encoding="utf-8")
    for component in ("CPython", "Tcl/Tk", "CustomTkinter", "Pillow", "darkdetect", "packaging", "NumPy", "PyInstaller"):
        assert component in runtime
    assert "GNU General Public License version 3" in ffmpeg
    assert "corresponding source" in ffmpeg
