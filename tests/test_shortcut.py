from pathlib import Path
from nenolink_ai_marker import __version__
def test_footer_uses_application_version():
    assert __version__ == "1.0.3"
    assert __version__ in (Path(__file__).parents[1] / "nenolink_ai_marker" / "__init__.py").read_text()
def test_packaged_smoke_script_exists():
    assert (Path(__file__).parents[1] / "scripts" / "windows-smoke-test.ps1").is_file()
