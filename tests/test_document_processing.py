from pathlib import Path

import pytest

from nenolink_ai_marker.document_processing import (
    DisclosureSettings,
    LogoSettings,
    OutputSettings,
    ProcessingRequest,
    ProcessorCapabilities,
    ensure_distinct_paths,
    settings_for_documents,
)
from nenolink_ai_marker.models import MarkerSettings


def test_request_rejects_source_overwrite_even_with_relative_spelling(tmp_path):
    source = tmp_path / "præsentation.pptx"
    source.touch()
    with pytest.raises(ValueError, match="different from the source"):
        ProcessingRequest(source, tmp_path / "." / source.name, DisclosureSettings("badge.png", "AI Assisted")).validated()


def test_unicode_paths_and_separate_disclosure_language_are_preserved(tmp_path):
    source = tmp_path / "Årsrapport_日本語.pptx"
    destination = tmp_path / "Årsrapport_日本語_ai.pptx"
    request = ProcessingRequest(
        source,
        destination,
        DisclosureSettings("ai-assisted.png", "Assisté par IA", language="fr"),
    ).validated()
    assert request.source == source
    assert request.destination == destination
    assert request.disclosure.language == "fr"
    assert request.disclosure.label == "Assisté par IA"


def test_shared_values_are_clamped_without_mutating_frozen_input():
    disclosure = DisclosureSettings("badge.png", "AI", position="invalid", size_percent=0, margin=-1, opacity=120)
    logo = LogoSettings(True, Path("logo.png"), position="invalid", size_percent=200, margin=-2, opacity=-1)
    assert disclosure.validated() == DisclosureSettings("badge.png", "AI", position="bottom-right", size_percent=1, margin=0, opacity=100)
    assert logo.validated() == LogoSettings(True, Path("logo.png"), position="top-left", size_percent=100, margin=0, opacity=0)


def test_output_suffix_is_safe_and_never_empty():
    assert OutputSettings("").validated().filename_suffix == "_ai"
    assert OutputSettings("_mærket").validated().filename_suffix == "_mærket"
    assert OutputSettings('<>:"/\\|?*').validated().filename_suffix == "_ai"


def test_capabilities_are_format_specific():
    pptx = ProcessorCapabilities("pptx", frozenset({".pptx"}), supports_logo=True, supports_metadata=True, supports_selection=True)
    assert pptx.supports(Path("slides.PPTX"))
    assert not pptx.supports(Path("legacy.ppt"))
    assert pptx.supports_selection and pptx.supports_logo


def test_existing_marker_settings_adapt_without_changing_ui_language():
    settings = MarkerSettings(
        language="da",
        badge_name="ai-translation.png",
        position="top-right",
        logo_enabled=True,
        logo_path="C:/mærker/logo.png",
    )
    disclosure, logo = settings_for_documents(settings, label="AI Translation", disclosure_language="en")
    assert settings.language == "da"
    assert disclosure.language == "en"
    assert disclosure.badge_name == "ai-translation.png"
    assert logo.path == Path("C:/mærker/logo.png")


def test_source_guard_accepts_distinct_paths(tmp_path):
    ensure_distinct_paths(tmp_path / "source.pdf", tmp_path / "source_ai.pdf")
