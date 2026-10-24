from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import pytest
from PIL import Image

from nenolink_ai_marker.document_processing import ItemSelection, MarkerSettings
from nenolink_ai_marker.document_controls import DocumentScopeControl
from nenolink_ai_marker.pptx_state import (
    PPTX_TRANSITION_TABLE,
    PptxEvent,
    PptxWorkspaceState,
    apply_pptx_event,
    pptx_transition,
)
from nenolink_ai_marker.pptx_workspace import PptxWorkspace
from nenolink_ai_marker.pptx_processor import P, PptxProcessor
from test_pptx_processor import _create_pptx, _request, _write_overlay


class _Translator:
    language = "en"

    def text(self, key, **values):
        return {
            "pptx.saved": "Saved {name} ({count} slides)",
            "pptx.choose_before_save": "Choose a file first",
            "pptx.logo_scope": "Apply logo to",
            "pptx.scope.first": "First slide",
            "pptx.scope.all": "All slides",
        }.get(key, key).format(**values)


class _Repository:
    def __init__(self, badge):
        self.badge = badge

    def canonical_filename(self, _value):
        return "ai-assisted.png"

    def find(self, _value):
        return self.badge

    def display_name(self, _value):
        return "AI Assisted"

    def display_badges(self):
        return [self.badge]


def _scope_for(mode):
    return {
        "all": (PptxEvent.SCOPE_MODE, "all", (1, 2, 3)),
        "first": (PptxEvent.SCOPE_MODE, "first", (1,)),
        "selected": (PptxEvent.SCOPE_UPDATE, "2", (2,)),
        "range": (PptxEvent.SCOPE_UPDATE, "2-3", (2, 3)),
    }[mode]


def _apply_badge_scope(state, mode):
    if mode in {"all", "first"}:
        event, value, expected = _scope_for(mode)
        apply_pptx_event(state, event, value)
        return expected
    apply_pptx_event(state, PptxEvent.SCOPE_MODE, mode)
    event, value, expected = _scope_for(mode)
    apply_pptx_event(state, PptxEvent.SCOPE_TEXT_CHANGED, value)
    apply_pptx_event(state, event, value)
    return expected


def test_pdf_scope_validation_status_wrap_tracks_available_width():
    class Frame:
        def winfo_width(self):
            return 280

    class Status:
        def __init__(self):
            self.values = {}

        def configure(self, **values):
            self.values.update(values)

    control = DocumentScopeControl.__new__(DocumentScopeControl)
    control.frame = Frame()
    control.status = Status()
    control._resize_status_wrap(SimpleNamespace(width=300))
    assert control.status.values["wraplength"] == 296
    control._resize_status_wrap(SimpleNamespace(width=220))
    assert control.status.values["wraplength"] == 216


def test_pptx_logo_scope_is_table_driven_and_independent_from_badge_scope():
    state = PptxWorkspaceState()
    assert state.logo.scope_mode == "all"
    assert pptx_transition(PptxEvent.LOGO_SCOPE_MODE).mutates == ("logo.scope_mode",)
    assert {row.event for row in PPTX_TRANSITION_TABLE} == set(PptxEvent)

    state.scope_mode, state.active_scope = "selected", (2,)
    apply_pptx_event(state, PptxEvent.LOGO_SCOPE_MODE, "first")
    assert state.logo.scope_mode == "first"
    assert state.scope_mode == "selected" and state.active_scope == (2,)
    apply_pptx_event(state, PptxEvent.LOGO_SCOPE_MODE, "all")
    assert state.logo.scope_mode == "all"
    assert state.scope_mode == "selected" and state.active_scope == (2,)
    with pytest.raises(ValueError, match="Unknown PPTX logo scope"):
        apply_pptx_event(state, PptxEvent.LOGO_SCOPE_MODE, "range")


@pytest.mark.parametrize("logo_mode", ["first", "all"])
def test_constructed_logo_scope_callback_updates_fsm_and_projection(logo_mode):
    workspace = PptxWorkspace(SimpleNamespace(pptx_preview_renderer=None))
    workspace._logo_scope_display = {"first": "First slide", "all": "All slides"}
    workspace._logo_scope_value = {label: mode for mode, label in workspace._logo_scope_display.items()}
    class Variable:
        value = None
        def set(self, value): self.value = value
    workspace.logo_scope_var = Variable()

    workspace._logo_scope_changed(workspace._logo_scope_display[logo_mode])

    assert workspace.state.logo.scope_mode == logo_mode
    assert workspace.logo_scope_var.value == workspace._logo_scope_display[logo_mode]
    assert workspace.last_receipt.event is PptxEvent.LOGO_SCOPE_MODE


def test_logo_scope_option_menu_dispatches_typed_event_and_projects_state(monkeypatch):
    import nenolink_ai_marker.pptx_workspace as module

    class Variable:
        def __init__(self, value=None): self.value = value
        def set(self, value): self.value = value

    class Widget:
        def __init__(self, *_args, **kwargs): self.options = kwargs
        def grid(self, **_kwargs): pass
        def configure(self, **kwargs): self.options.update(kwargs)

    class Logo:
        def __init__(self, _parent, **kwargs):
            self.frame = Widget()
            self.enabled_var = Variable(False)
            self.choose_button = Widget()
            self.filename_label = Widget()
            self.projected = None
        def project(self, projection): self.projected = projection

    class Row:
        def __init__(self, _parent, **kwargs):
            self.frame = Widget()
            self.label = Widget()
        def grid(self, **kwargs): self.frame.grid(**kwargs)

    monkeypatch.setattr(module.ctk, "CTkLabel", Widget)
    monkeypatch.setattr(module.ctk, "CTkOptionMenu", Widget)
    monkeypatch.setattr(module.ctk, "StringVar", Variable)
    monkeypatch.setattr(module.ctk, "IntVar", Variable)
    monkeypatch.setattr(module, "LogoControl", Logo)
    monkeypatch.setattr(module, "ParameterRow", Row)
    workspace = PptxWorkspace(SimpleNamespace(translator=_Translator(), pptx_preview_renderer=None))
    workspace._build_visual_controls(Widget(), Widget())

    assert workspace.state.logo.scope_mode == "all"
    assert workspace.logo_scope_menu.options["values"] == ["First slide", "All slides"]
    workspace.logo_scope_menu.options["command"]("First slide")

    assert workspace.state.logo.scope_mode == "first"
    assert workspace.logo_scope_var.value == "First slide"
    assert workspace.last_receipt.event is PptxEvent.LOGO_SCOPE_MODE


@pytest.mark.parametrize("badge_mode", ["all", "first", "selected", "range"])
@pytest.mark.parametrize("logo_mode", ["first", "all"])
def test_pptx_save_callback_outputs_independent_badge_and_logo_scopes(
    tmp_path, monkeypatch, badge_mode, logo_mode
):
    from tkinter import filedialog

    source = tmp_path / "three-slides.pptx"
    _create_pptx(source, 3)
    badge_path = tmp_path / "ai-assisted.png"
    logo_path = tmp_path / "own-logo.png"
    _write_overlay(badge_path, (20, 130, 200, 255))
    _write_overlay(logo_path, (200, 40, 30, 255))
    destination = tmp_path / f"out-{badge_mode}-{logo_mode}.pptx"
    app = SimpleNamespace(
        badges=_Repository(badge_path), translator=_Translator(),
        settings=lambda: MarkerSettings(), pptx_processor=PptxProcessor(),
        status_var=SimpleNamespace(set=lambda _value: None),
    )
    workspace = PptxWorkspace(app)
    workspace.state.path = source
    workspace.state.slide_count = 3
    expected_badge = _apply_badge_scope(workspace.state, badge_mode)
    workspace.state.badge.enabled = True
    workspace.state.badge.badge_id = "AI Assisted"
    workspace.state.logo.enabled = True
    workspace.state.logo.path = logo_path
    workspace._logo_scope_display = {"first": "First slide", "all": "All slides"}
    workspace._logo_scope_value = {label: mode for mode, label in workspace._logo_scope_display.items()}
    workspace._logo_scope_changed(workspace._logo_scope_display[logo_mode])
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **_kwargs: str(destination))

    workspace._save_as()

    expected_logo = (1,) if logo_mode == "first" else (1, 2, 3)
    assert destination.is_file()
    with ZipFile(destination) as archive:
        for slide in range(1, 4):
            pictures = len(ET.fromstring(archive.read(f"ppt/slides/slide{slide}.xml")).findall(f".//{{{P}}}pic"))
            assert pictures == int(slide in expected_badge) + int(slide in expected_logo)


@pytest.mark.parametrize("logo_mode", ["first", "all"])
@pytest.mark.parametrize("current_slide", [1, 2, 3])
def test_pptx_preview_uses_independent_logo_scope_during_slide_navigation(
    monkeypatch, tmp_path, logo_mode, current_slide
):
    import nenolink_ai_marker.pptx_workspace as module

    source = tmp_path / "three-slides.pptx"
    _create_pptx(source, 3)
    badge_path = tmp_path / "badge.png"
    logo_path = tmp_path / "logo.png"
    _write_overlay(badge_path, (20, 130, 200, 255))
    _write_overlay(logo_path, (200, 40, 30, 255))
    calls = []

    class Renderer:
        def render(self, _path, slide_number, badge, _settings, logo, *, max_size):
            calls.append((slide_number, badge, logo, max_size))
            return SimpleNamespace(image=Image.new("RGBA", (80, 45)), slide_number=slide_number, slide_count=3)

    class Widget:
        def configure(self, **_kwargs): pass
        def winfo_width(self): return 320
        def winfo_height(self): return 220

    monkeypatch.setattr(module.ctk, "CTkImage", lambda *args, **kwargs: object())
    workspace = PptxWorkspace(SimpleNamespace(
        pptx_preview_renderer=Renderer(), badges=_Repository(badge_path),
        translator=_Translator(),
    ))
    workspace.state.path = source
    workspace.state.slide_count = 3
    workspace.state.current_slide = current_slide
    workspace.state.active_scope = (1,)  # Badge remains scoped independently.
    workspace.state.badge.enabled = True
    workspace.state.badge.badge_id = "AI Assisted"
    workspace.state.logo.enabled = True
    workspace.state.logo.path = logo_path
    workspace.state.logo.scope_mode = logo_mode
    workspace.preview_viewport = Widget()
    workspace.preview_label = Widget()
    workspace.slide_status = Widget()
    workspace.previous_button = Widget()
    workspace.next_button = Widget()
    workspace.preview_photo = None
    workspace.receipts = SimpleNamespace(record=lambda _entry: None)
    workspace._preview_geometry = lambda: SimpleNamespace(
        rendered_width=120, rendered_height=90, actual_available_width=300,
        actual_available_height=220, effective_width=300, effective_height=220,
        canonical_max_width=240, canonical_max_height=176,
        measured_fraction=0.8, limiting_dimension="height",
    )

    workspace._render_preview()

    assert calls[0][1] is (badge_path if current_slide == 1 else None)
    should_show_logo = logo_mode == "all" or current_slide == 1
    assert calls[0][2] is (logo_path if should_show_logo else None)


@pytest.mark.parametrize("locale", sorted(Path("locales").glob("*.json")))
def test_pptx_logo_scope_label_is_translated_for_all_supported_locales(locale):
    values = json.loads(locale.read_text(encoding="utf-8"))
    assert values["pptx.logo_scope"].strip()
    assert locale.stem == "en" or values["pptx.logo_scope"] != "Apply logo to"
    assert values["document.scope_invalid"].strip()
