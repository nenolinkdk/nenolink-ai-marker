from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.config import ConfigStore
from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.update_check import (
    APPROVED_UPDATE_URL,
    MANIFEST_URL,
    NETWORK_TIMEOUT_SECONDS,
    UpdateCheckError,
    check_for_update,
    is_approved_update_url,
    should_check_automatically,
    validate_manifest,
)


def manifest(version="1.0.2", url=APPROVED_UPDATE_URL):
    return {
        "schema": 1,
        "latest_version": version,
        "release_date": "2026-09-10",
        "update_url": url,
        "minimum_supported_version": "1.0.1",
    }


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _size):
        return self.payload


def opener_for(payload, captured=None):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def opener(request, timeout):
        if captured is not None:
            captured.update(request=request, timeout=timeout)
        return Response(raw)

    return opener


def test_same_version_has_no_update_and_newer_version_does():
    current = check_for_update("1.0.1", opener=opener_for(manifest("1.0.1")))
    newer = check_for_update("1.0.1", opener=opener_for(manifest("1.0.2")))
    assert current.update_available is False
    assert newer.update_available is True
    assert newer.manifest.latest_version == "1.0.2"


def test_comparison_is_version_aware_not_lexicographic():
    assert check_for_update("1.0.9", opener=opener_for(manifest("1.0.10"))).update_available
    assert not check_for_update("1.0.10", opener=opener_for(manifest("1.0.9"))).update_available


@pytest.mark.parametrize(
    "change",
    [
        lambda value: "not-json",
        lambda value: {**value, "latest_version": ""},
        lambda value: {key: item for key, item in value.items() if key != "latest_version"},
        lambda value: {**value, "schema": True},
        lambda value: {**value, "release_date": "10-09-2026"},
        lambda value: {**value, "unexpected": "field"},
        lambda value: {**value, "update_url": "https://evil.example/update/"},
        lambda value: {**value, "update_url": "http://nenolink.com/en/about/ai-marker/update/"},
    ],
)
def test_invalid_json_fields_versions_and_urls_are_ignored_safely(change):
    changed = change(manifest())
    payload = changed.encode() if isinstance(changed, str) else changed
    with pytest.raises(UpdateCheckError):
        check_for_update("1.0.1", opener=opener_for(payload))


@pytest.mark.parametrize("failure", [OSError("offline"), TimeoutError(), RuntimeError("500"), RuntimeError("404")])
def test_network_timeout_and_server_failures_are_graceful(failure):
    def failing_opener(*_args, **_kwargs):
        raise failure

    with pytest.raises(UpdateCheckError):
        check_for_update("1.0.1", opener=failing_opener)


def test_request_is_https_short_and_contains_no_media_or_user_content():
    captured = {}
    check_for_update("1.0.1", opener=opener_for(manifest(), captured))
    request = captured["request"]
    assert request.full_url == MANIFEST_URL
    assert request.get_method() == "GET"
    assert request.data is None
    assert captured["timeout"] == NETWORK_TIMEOUT_SECONDS
    headers = dict(request.header_items())
    assert set(headers) == {"Accept", "User-agent"}
    assert headers["User-agent"] == "Nenolink-AI-Marker/1.0.1"


def test_automatic_interval_is_at_least_30_days():
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    assert should_check_automatically("", now)
    assert not should_check_automatically((now - timedelta(days=29, hours=23)).isoformat(), now)
    assert should_check_automatically((now - timedelta(days=30)).isoformat(), now)
    assert should_check_automatically("malformed", now)


def test_update_preferences_persist_and_old_1_0_0_settings_load():
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
        store = ConfigStore(Path(directory) / "settings.json")
        store.save(MarkerSettings(automatic_update_check=False, last_update_check="2026-09-10T12:00:00+00:00"))
        restored = ConfigStore(store.path).load()
        assert restored.automatic_update_check is False
        assert restored.last_update_check == "2026-09-10T12:00:00+00:00"

        store.path.write_text('{"language":"da","badge_name":"ai-assisted.png"}', encoding="utf-8")
        old = store.load()
        assert old.language == "da"
        assert old.automatic_update_check is True
        assert old.last_update_check == ""


def test_manual_check_bypasses_interval_and_automatic_can_be_disabled():
    manual = SimpleNamespace(_start_update_check=Mock())
    MarkerApp.check_for_updates(manual)
    manual._start_update_check.assert_called_once_with(True)

    disabled = SimpleNamespace(
        _automatic_update_attempted=False,
        automatic_update_var=SimpleNamespace(get=lambda: False),
        last_update_check="",
        _start_update_check=Mock(),
    )
    MarkerApp._automatic_update_check(disabled)
    disabled._start_update_check.assert_not_called()


def test_failed_automatic_check_is_not_retried_in_same_session():
    app = SimpleNamespace(
        _automatic_update_attempted=False,
        automatic_update_var=SimpleNamespace(get=lambda: True),
        last_update_check="",
        _start_update_check=Mock(),
    )
    MarkerApp._automatic_update_check(app)
    MarkerApp._automatic_update_check(app)
    app._start_update_check.assert_called_once_with(False)


def test_failed_automatic_check_is_silent_and_leaves_app_usable():
    app = SimpleNamespace(
        _update_check_running=True,
        translator=SimpleNamespace(text=lambda key: key),
    )
    with patch("nenolink_ai_marker.app.messagebox.showerror") as showerror:
        MarkerApp._finish_update_check(app, None, UpdateCheckError("offline"), False)
    showerror.assert_not_called()
    assert app._update_check_running is False


def test_only_the_exact_approved_update_page_can_be_opened():
    assert is_approved_update_url(APPROVED_UPDATE_URL)
    for unsafe in (
        "https://evil.example/update/",
        "http://nenolink.com/en/aimarkerupdate/",
        "https://nenolink.com@evil.example/en/aimarkerupdate/",
        "https://nenolink.com/en/aimarkerupdate/?download=app.exe",
    ):
        assert not is_approved_update_url(unsafe)

    app = SimpleNamespace(_available_update_url="https://evil.example/update/")
    with patch("nenolink_ai_marker.app.webbrowser.open") as opened:
        MarkerApp._open_update_page(app)
        opened.assert_not_called()
        app._available_update_url = APPROVED_UPDATE_URL
        MarkerApp._open_update_page(app)
        opened.assert_called_once_with(APPROVED_UPDATE_URL)


def test_header_notification_is_localized_and_hidden_when_current():
    widget = Mock()
    app = SimpleNamespace(
        _available_update_version="1.0.2",
        update_notification=widget,
        translator=SimpleNamespace(text=lambda key, **values: f"New version available: {values['version']}"),
    )
    MarkerApp._render_update_notification(app)
    widget.configure.assert_called_once_with(text="New version available: 1.0.2")
    widget.grid.assert_called_once_with()
    app._available_update_version = ""
    MarkerApp._render_update_notification(app)
    widget.grid_remove.assert_called_once_with()


def test_check_is_started_on_a_daemon_worker_not_the_ui_thread():
    started = []

    class FakeThread:
        def __init__(self, *, target, name, daemon):
            started.append((target, name, daemon))

        def start(self):
            return None

    app = SimpleNamespace(
        _update_check_running=False,
        status_var=Mock(),
        translator=SimpleNamespace(text=lambda key: key),
    )
    with patch("nenolink_ai_marker.app.threading.Thread", FakeThread):
        MarkerApp._start_update_check(app, True)
    assert started and started[0][1:] == ("NenolinkUpdateCheck", True)
    assert app._update_check_running is True


def test_manifest_validator_returns_only_data_never_commands():
    result = validate_manifest(manifest())
    assert result.update_url == APPROVED_UPDATE_URL
    assert not hasattr(result, "command")
