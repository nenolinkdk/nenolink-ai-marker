from pathlib import Path
import pytest

from nenolink_ai_marker.workspace_state import (
    PDF_TRANSITION_TABLE, PdfEvent, PdfWorkspaceState,
    apply_pdf_event, pdf_transition,
)


@pytest.mark.parametrize("spec", PDF_TRANSITION_TABLE)
def test_every_pdf_table_transition_executes(spec):
    assert pdf_transition(spec.event) is spec
    state = PdfWorkspaceState(path=Path("doc.pdf"), page_count=6, current_page=2, active_scope=(2, 4))
    payloads = {
        PdfEvent.FILE_SELECTED: {"path": Path("new.pdf"), "page_count": 4},
        PdfEvent.SCOPE_MODE: {"mode": "selected"},
        PdfEvent.SCOPE_TEXT_CHANGED: {"text": "2,4"},
        PdfEvent.SCOPE_UPDATE: {"values": (2, 4), "text": "2,4"},
        PdfEvent.PREVIEW_PREVIOUS: {}, PdfEvent.PREVIEW_NEXT: {},
        PdfEvent.PREVIEW_PAGE_SELECTED: {"page": 3},
        PdfEvent.BADGE_CHANGED: {"badge_id": "AI Translation"},
        PdfEvent.LOGO_CHANGED: {"enabled": True, "path": Path("logo.png")},
        PdfEvent.VISUAL_CHANGED: {"size": 35, "logo_size": 25},
        PdfEvent.CLEAR_RUNTIME: {},
        PdfEvent.RESET_TO_DEFAULTS: {},
    }
    apply_pdf_event(state, spec.event, payloads[spec.event])
    assert state is not None


def test_pdf_draft_edit_does_not_change_effective_scope():
    state = PdfWorkspaceState(path=Path("doc.pdf"), page_count=6, current_page=2, scope_mode="selected", scope_input="2", active_scope=(2,))
    apply_pdf_event(state, PdfEvent.SCOPE_TEXT_CHANGED, {"text": "3,5"})
    assert state.scope_input == "3,5" and state.active_scope == (2,) and state.current_page == 2


def test_pdf_invalid_update_preserves_scope_and_page():
    state = PdfWorkspaceState(path=Path("doc.pdf"), page_count=6, current_page=2, scope_mode="selected", scope_input="2", active_scope=(2,))
    with pytest.raises(ValueError):
        apply_pdf_event(state, PdfEvent.SCOPE_UPDATE, {"values": (9,), "text": "9"})
    assert state.active_scope == (2,) and state.current_page == 2


@pytest.mark.parametrize(("mode", "text", "expected"), [
    ("selected", "1,3-4", (1, 3, 4)),
    ("range", "2-3,5-6", (2, 3, 5, 6)),
])
def test_pdf_scope_update_parses_ui_draft_through_table(mode, text, expected):
    state = PdfWorkspaceState(path=Path("doc.pdf"), page_count=6, current_page=5, active_scope=(5,))
    apply_pdf_event(state, PdfEvent.SCOPE_MODE, {"mode": mode})
    apply_pdf_event(state, PdfEvent.SCOPE_TEXT_CHANGED, {"text": text})
    apply_pdf_event(state, PdfEvent.SCOPE_UPDATE, {"text": state.scope_input})
    assert state.active_scope == expected
    assert state.current_page == expected[0]


@pytest.mark.parametrize(("mode", "text"), [
    ("selected", ""), ("selected", "0"), ("selected", "5-2"),
    ("range", "2,4"), ("entire", "1-2"),
])
def test_pdf_invalid_scope_mode_or_draft_is_transactional(mode, text):
    state = PdfWorkspaceState(path=Path("doc.pdf"), page_count=6, current_page=3,
                              scope_mode="selected", scope_input="1,3", active_scope=(1, 3))
    before = (state.scope_mode, state.active_scope, state.current_page)
    if mode == "entire":
        with pytest.raises(ValueError):
            apply_pdf_event(state, PdfEvent.SCOPE_MODE, {"mode": mode})
    else:
        apply_pdf_event(state, PdfEvent.SCOPE_MODE, {"mode": mode})
        with pytest.raises(ValueError):
            apply_pdf_event(state, PdfEvent.SCOPE_UPDATE, {"text": text})
    assert (state.active_scope, state.current_page) == before[1:]
    if mode == "entire":
        assert state.scope_mode == before[0]
    else:
        assert state.scope_mode == mode


def test_pdf_physical_navigation_preserves_scope():
    state = PdfWorkspaceState(path=Path("doc.pdf"), page_count=10, current_page=2, active_scope=(2, 7))
    apply_pdf_event(state, PdfEvent.PREVIEW_NEXT)
    assert state.current_page == 3 and state.active_scope == (2, 7)


def test_pdf_file_replacement_resets_document_scope_preserves_visuals():
    state = PdfWorkspaceState(path=Path("old.pdf"), page_count=8, current_page=5, active_scope=(2, 7))
    state.badge.badge_id = "AI Assisted"
    apply_pdf_event(state, PdfEvent.FILE_SELECTED, {"path": Path("new.pdf"), "page_count": 3})
    assert state.path == Path("new.pdf") and state.page_count == 3 and state.current_page == 1
    assert state.active_scope == (1, 2, 3) and state.badge.badge_id == "AI Assisted"


def test_pdf_reset_to_defaults_restores_local_scope_and_visual_state():
    state = PdfWorkspaceState(path=Path("doc.pdf"), page_count=3, current_page=2,
                              scope_mode="selected", scope_input="2", active_scope=(2,))
    state.badge.size = 44; state.logo.enabled = True; state.logo.path = Path("logo.png")
    owner = id(state)
    apply_pdf_event(state, PdfEvent.RESET_TO_DEFAULTS)
    assert id(state) == owner
    assert state == PdfWorkspaceState()


def test_pdf_workspace_enter_clean_uses_pdf_defaults_not_saved_global_badge(tmp_path):
    from types import SimpleNamespace
    from nenolink_ai_marker.pdf_workspace import PdfWorkspace

    default_badge = Path("ai-assisted.png")
    app = SimpleNamespace(
        badges=SimpleNamespace(
            find=lambda badge_id: default_badge if badge_id == default_badge.name else None,
            display_badges=lambda: (default_badge,),
        ),
        _saved_settings=SimpleNamespace(badge_name="different-global-selection"),
    )
    state = PdfWorkspaceState(path=tmp_path / "old.pdf", page_count=3, current_page=2,
                              scope_mode="selected", scope_input="2", active_scope=(2,))
    state.badge.badge_id = "other-badge.png"; state.logo.enabled = True
    workspace = PdfWorkspace(app, state)
    workspace.enter_clean()
    assert state == PdfWorkspaceState()
    assert state.badge.badge_id == "ai-assisted.png"


def test_pdf_clean_uses_first_repository_badge_if_own_default_is_unavailable():
    from types import SimpleNamespace
    from nenolink_ai_marker.pdf_workspace import PdfWorkspace

    available = Path("human-reviewed.png")
    app = SimpleNamespace(badges=SimpleNamespace(
        find=lambda badge_id: available if badge_id == available.name else None,
        display_badges=lambda: (available,),
    ))
    workspace = PdfWorkspace(app, PdfWorkspaceState())
    workspace.enter_clean()
    assert workspace.state.badge.badge_id == available.name


def test_pdf_scope_validation_uses_actual_three_page_document(tmp_path):
    from pypdf import PdfWriter
    from nenolink_ai_marker.pdf_processor import PdfProcessor

    source = tmp_path / "three-pages.pdf"
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=200, height=300)
    with source.open("wb") as stream:
        writer.write(stream)
    page_count = PdfProcessor.inspect(source).metrics.item_count
    assert page_count == 3

    state = PdfWorkspaceState()
    apply_pdf_event(state, PdfEvent.FILE_SELECTED, {"path": source, "page_count": page_count})
    apply_pdf_event(state, PdfEvent.SCOPE_MODE, {"mode": "selected"})
    apply_pdf_event(state, PdfEvent.SCOPE_TEXT_CHANGED, {"text": "2-3"})
    apply_pdf_event(state, PdfEvent.SCOPE_UPDATE, {"text": state.scope_input})
    assert state.active_scope == (2, 3) and state.current_page == 2

    for invalid in ("0", "4", "2-4", "3-1", ""):
        apply_pdf_event(state, PdfEvent.SCOPE_TEXT_CHANGED, {"text": invalid})
        before = (state.active_scope, state.current_page)
        with pytest.raises(ValueError):
            apply_pdf_event(state, PdfEvent.SCOPE_UPDATE, {"text": state.scope_input})
        assert (state.active_scope, state.current_page) == before


@pytest.mark.parametrize("locale", ["en", "da", "de", "fr", "es", "it", "pt", "nl", "sv", "no", "pl", "cs"])
def test_pdf_invalid_scope_feedback_is_localized_in_each_supported_locale(locale):
    import json
    from nenolink_ai_marker.i18n import DEFAULT_ENGLISH, Translator
    from nenolink_ai_marker.paths import locale_directory
    from nenolink_ai_marker.pdf_workspace import PdfWorkspace

    class Status:
        def configure(self, **kwargs): self.text = kwargs["text"]

    workspace = PdfWorkspace.__new__(PdfWorkspace)
    directory = locale_directory()
    locale_data = json.loads((directory / f"{locale}.json").read_text(encoding="utf-8"))
    translator = Translator(directory, locale)
    assert locale_data["document.scope_invalid"].strip()
    if locale != "en":
        assert locale_data["document.scope_invalid"] != DEFAULT_ENGLISH["document.scope_invalid"]
    workspace.app = type("App", (), {"translator": translator})()
    workspace.root = None
    workspace.scope_control = type("Control", (), {"status": Status()})()
    workspace._show_scope_error()
    assert workspace.scope_control.status.text == locale_data["document.scope_invalid"]
