"""4D17B release gate for the active production localization inventory."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from nenolink_ai_marker.i18n import LANGUAGES, PRODUCTION_UI_KEYS, Translator
from nenolink_ai_marker.pptx_state import PptxWorkspaceState
from nenolink_ai_marker.workspace_state import ImageWorkspaceState, PdfWorkspaceState, VideoWorkspaceState


ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / "locales"
REPRESENTATIVE_KEYS = {
    "Image": ("section.file", "section.ai_badge", "button.open_media", "button.save"),
    "Video": ("section.video_options", "video.badge_mode", "video.mode.beginning", "logo.mode.front"),
    "PDF": ("section.pages", "pdf.scope.all", "pdf.page_status", "pdf.preview_hint"),
    "PPTX": ("section.slides", "pptx.scope.all", "pptx.slide_status", "pptx.preview_hint"),
    "Badges": ("tab.badges", "badge.gallery", "badge.refresh"),
    "Inspect File": ("tab.inspect", "inspect.title", "inspect.choose"),
}


def _locale(code: str) -> dict[str, str]:
    return json.loads((LOCALES / f"{code}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("code", LANGUAGES.values())
def test_every_supported_locale_covers_the_authoritative_production_inventory(code: str):
    values = _locale(code)
    assert not (set(PRODUCTION_UI_KEYS) - set(values)), code
    assert not {key for key in PRODUCTION_UI_KEYS if not values[key].strip()}, code


@pytest.mark.parametrize("code", LANGUAGES.values())
def test_supported_locales_do_not_need_english_fallback_for_normal_ui(code: str):
    translator = Translator(LOCALES, code)
    values = _locale(code)
    for key in PRODUCTION_UI_KEYS:
        # Equality with English is allowed for proper names and technical terms;
        # this assertion proves that the active locale, rather than fallback,
        # supplied the displayed template.
        assert translator._active.get(key) == values[key], (code, key)


@pytest.mark.parametrize("code", LANGUAGES.values())
def test_representative_workspace_and_tool_projections_are_localized(code: str):
    translator = Translator(LOCALES, code)
    for surface, keys in REPRESENTATIVE_KEYS.items():
        for key in keys:
            assert translator.text(key).strip(), (code, surface, key)
    visible_semantics = (
        translator.text("video.mode.beginning"),
        translator.text("video.mode.permanent"),
        translator.text("video.mode.end"),
        translator.text("logo.mode.front"),
        translator.text("logo.mode.entire"),
        translator.text("logo.mode.back"),
    )
    assert not {"beginning", "entire", "first", "selected", "range"} & set(visible_semantics)


def test_language_change_is_presentation_only_for_workspace_state():
    translator = Translator(LOCALES, "en")
    states = (ImageWorkspaceState(), VideoWorkspaceState(), PdfWorkspaceState(), PptxWorkspaceState())
    before = tuple(asdict(state) for state in states)
    for code in LANGUAGES.values():
        translator.set_language(code)
    assert tuple(asdict(state) for state in states) == before

