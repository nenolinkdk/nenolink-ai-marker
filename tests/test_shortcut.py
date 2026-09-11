from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from nenolink_ai_marker import __version__
from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.shortcut import SHORTCUT_NAME, ShortcutError, create_desktop_shortcut


def test_footer_uses_application_version_and_existing_row():
    source = (Path(__file__).parents[1] / "nenolink_ai_marker" / "app.py").read_text(encoding="utf-8")
    assert 'v{__version__}' in source
    assert "© Copyright Henrik Nielsen - nenolink.com" in source
    assert __version__ == "1.0.1"


def test_packaged_smoke_test_requires_footer_and_shortcut_evidence():
    source = (Path(__file__).parents[1] / "scripts" / "windows-smoke-test.ps1").read_text(encoding="utf-8-sig")
    assert "packaged_ui_evidence.footer_text" in source
    assert "packaged_ui_evidence.shortcut_visible" in source
    assert 'shortcut_module -ne "nenolink_ai_marker.shortcut"' in source
    assert '$report.version -ne "1.0.1"' in source


def test_packaged_windows_shortcut_targets_current_exe_and_uses_its_icon(tmp_path):
    executable = tmp_path / "Nenolink AI Marker's App.exe"
    executable.touch()
    runner = Mock()
    create_desktop_shortcut(executable=executable, frozen=True, platform="win32", runner=runner)
    command = runner.call_args.args[0]
    encoded = command[command.index("-EncodedCommand") + 1]
    script = base64.b64decode(encoded).decode("utf-16le")
    assert str(executable.resolve()).replace("'", "''") in script
    assert SHORTCUT_NAME in script
    assert "$shortcut.TargetPath=$target" in script
    assert '$shortcut.IconLocation="$target,0"' in script
    assert "Copy-Item" not in script
    assert "taskbar" not in script.lower()
    runner.assert_called_once()
    assert runner.call_args.kwargs["check"] is True


@pytest.mark.parametrize("frozen,platform", [(False, "win32"), (True, "linux")])
def test_shortcut_rejects_source_mode_and_non_windows(tmp_path, frozen, platform):
    executable = tmp_path / "app.exe"
    executable.touch()
    with pytest.raises(ShortcutError):
        create_desktop_shortcut(executable=executable, frozen=frozen, platform=platform, runner=Mock())


def test_shortcut_failure_is_wrapped(tmp_path):
    executable = tmp_path / "app.exe"
    executable.touch()
    runner = Mock(side_effect=OSError("unavailable"))
    with pytest.raises(ShortcutError):
        create_desktop_shortcut(executable=executable, frozen=True, platform="win32", runner=runner)


def test_ui_reports_localized_shortcut_success_and_failure():
    translator = SimpleNamespace(text=lambda key: key)
    app = SimpleNamespace(translator=translator)
    with patch("nenolink_ai_marker.app.create_desktop_shortcut"), patch("nenolink_ai_marker.app.messagebox.showinfo") as info:
        MarkerApp.create_shortcut(app)
        info.assert_called_once_with("shortcut.title", "shortcut.success")
    with patch("nenolink_ai_marker.app.create_desktop_shortcut", side_effect=ShortcutError()), patch("nenolink_ai_marker.app.messagebox.showerror") as error:
        MarkerApp.create_shortcut(app)
        error.assert_called_once_with("shortcut.title", "shortcut.error")
