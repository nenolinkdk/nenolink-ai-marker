from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
from typing import Callable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from packaging.version import InvalidVersion, Version


MANIFEST_URL = "https://nenolink.com/downloads/ai-marker/latest.json"
APPROVED_UPDATE_URL = "https://nenolink.com/en/about/ai-marker/update/"
CHECK_INTERVAL = timedelta(days=30)
NETWORK_TIMEOUT_SECONDS = 5
MAX_MANIFEST_BYTES = 32 * 1024
MANIFEST_FIELDS = {
    "schema",
    "latest_version",
    "release_date",
    "update_url",
    "minimum_supported_version",
}


class UpdateCheckError(Exception):
    """An expected network or manifest failure that must not stop the app."""


@dataclass(frozen=True, slots=True)
class UpdateManifest:
    latest_version: str
    release_date: str
    update_url: str
    minimum_supported_version: str


@dataclass(frozen=True, slots=True)
class UpdateCheckResult:
    manifest: UpdateManifest
    update_available: bool
    checked_at: str


def _version(value: object, field: str) -> Version:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise UpdateCheckError(f"Invalid {field}")
    try:
        parsed = Version(value)
    except InvalidVersion as error:
        raise UpdateCheckError(f"Invalid {field}") from error
    if str(parsed) != value:
        raise UpdateCheckError(f"Non-canonical {field}")
    return parsed


def is_approved_update_url(value: object) -> bool:
    if not isinstance(value, str) or value != APPROVED_UPDATE_URL:
        return False
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "nenolink.com"
        and parsed.username is None
        and parsed.password is None
        and parsed.port is None
        and not parsed.query
        and not parsed.fragment
    )


def validate_manifest(payload: object) -> UpdateManifest:
    if not isinstance(payload, dict) or set(payload) != MANIFEST_FIELDS:
        raise UpdateCheckError("Invalid manifest fields")
    schema = payload["schema"]
    if type(schema) is not int or schema != 1:
        raise UpdateCheckError("Unsupported manifest schema")
    latest = _version(payload["latest_version"], "latest_version")
    minimum = _version(payload["minimum_supported_version"], "minimum_supported_version")
    release_date = payload["release_date"]
    if not isinstance(release_date, str):
        raise UpdateCheckError("Invalid release_date")
    try:
        if date.fromisoformat(release_date).isoformat() != release_date:
            raise ValueError
    except ValueError as error:
        raise UpdateCheckError("Invalid release_date") from error
    update_url = payload["update_url"]
    if not is_approved_update_url(update_url):
        raise UpdateCheckError("Unapproved update_url")
    return UpdateManifest(str(latest), release_date, update_url, str(minimum))


def should_check_automatically(last_check: str, now: datetime | None = None) -> bool:
    if not last_check:
        return True
    try:
        previous = datetime.fromisoformat(last_check.replace("Z", "+00:00"))
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return True
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc) - previous.astimezone(timezone.utc) >= CHECK_INTERVAL


def check_for_update(
    installed_version: str,
    *,
    opener: Callable[..., object] = urlopen,
    now: datetime | None = None,
) -> UpdateCheckResult:
    installed = _version(installed_version, "installed_version")
    request = Request(
        MANIFEST_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": f"Nenolink-AI-Marker/{installed_version}",
        },
        method="GET",
    )
    try:
        with opener(request, timeout=NETWORK_TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_MANIFEST_BYTES + 1)
    except Exception as error:
        raise UpdateCheckError("Update service unavailable") from error
    if len(raw) > MAX_MANIFEST_BYTES:
        raise UpdateCheckError("Manifest too large")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UpdateCheckError("Invalid manifest JSON") from error
    manifest = validate_manifest(payload)
    checked = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    return UpdateCheckResult(
        manifest=manifest,
        update_available=Version(manifest.latest_version) > installed,
        checked_at=checked,
    )
