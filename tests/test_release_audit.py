import json
from pathlib import Path

from nenolink_ai_marker import __version__


ROOT = Path(__file__).resolve().parents[1]


def test_release_facing_version_is_consistent():
    assert __version__ == "1.0.1"
    for relative in ("README.md", "docs/USER_GUIDE_EN.md", "docs/USER_GUIDE_DA.md"):
        assert "1.0.1" in (ROOT / relative).read_text(encoding="utf-8")


def test_release_artifact_names_are_final_and_derived_from_version():
    build=(ROOT/"build.ps1").read_text(encoding="utf-8")
    spec=(ROOT/"Nenolink-AI-Marker.spec").read_text(encoding="utf-8")
    assert 'releaseName = "Nenolink-AI-Marker-$version"' in build
    assert 'name=f"Nenolink-AI-Marker-{app_version}"' in spec
    assert "own-" + "logo-dev" not in build
    assert "release " + "candidate" not in build.lower()


def test_every_locale_has_the_complete_english_key_set():
    english = json.loads((ROOT / "locales/en.json").read_text(encoding="utf-8"))
    for path in (ROOT / "locales").glob("*.json"):
        values = json.loads(path.read_text(encoding="utf-8"))
        assert set(values) == set(english), path.name


def test_release_docs_cover_current_workflows():
    expectations = {
        "docs/USER_GUIDE_EN.md": ("Save Marked Image", "Permanent", "Beginning", "End", "Back", "Reset", "Inspect File", "Own Logo", "live, scaled preview", "Processing is local"),
        "docs/USER_GUIDE_DA.md": ("Gem mærket billede", "Hele videoen", "I begyndelsen", "I slutningen", "Tilbage", "Nulstil", "Undersøg fil", "Eget logo", "live, skaleret forhåndsvisning", "Behandlingen foregår lokalt"),
    }
    for relative, terms in expectations.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert all(term in text for term in terms), relative


def test_release_docs_cover_eleven_badges_no_ai_and_first_run_offer():
    english=(ROOT/"docs/USER_GUIDE_EN.md").read_text(encoding="utf-8")
    danish=(ROOT/"docs/USER_GUIDE_DA.md").read_text(encoding="utf-8")
    readme=(ROOT/"README.md").read_text(encoding="utf-8")
    assert "eleven files" in english and "eleven documented standard PNGs" in readme
    assert "de elleve filer" in danish
    assert "No AI is a user-selected declaration. Nenolink AI Marker does not verify that content was created without the use of AI." in english
    assert "No AI er en erklæring valgt af brugeren." in danish
    assert "first normal launch" in english and "første normale start" in danish


def test_distribution_notices_cover_runtime_and_ffmpeg():
    runtime = (ROOT / "THIRD_PARTY_NOTICES/RUNTIME_COMPONENTS.md").read_text(encoding="utf-8")
    ffmpeg = (ROOT / "THIRD_PARTY_NOTICES/FFMPEG.md").read_text(encoding="utf-8")
    for component in ("CPython", "Tcl/Tk", "CustomTkinter", "Pillow", "darkdetect", "packaging", "PyInstaller"):
        assert component in runtime
    assert "GNU General Public License version 3" in ffmpeg
    assert "corresponding source" in ffmpeg
