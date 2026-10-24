from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from nenolink_ai_marker.badge_control import BadgeControl
from nenolink_ai_marker.i18n import LANGUAGES, Translator
from nenolink_ai_marker.logo_control import LogoControl
from nenolink_ai_marker.pptx_state import (
    PptxEvent,
    PptxWorkspaceState,
    pptx_transition,
)
from nenolink_ai_marker.pptx_workspace import PptxWorkspace
from nenolink_ai_marker.workspace_control_panel import (
    BADGE_SELECTOR_PADY,
    LOGO_CHOOSE_PADY,
    PARAM_PADX,
)
from nenolink_ai_marker.workspace_state import (
    PDF_TRANSITION_TABLE,
    PdfEvent,
    PdfWorkspaceState,
    pdf_transition,
)
from nenolink_ai_marker.pdf_workspace import PdfWorkspace


ROOT = Path(__file__).resolve().parents[1]


class _Widget:
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.options = kwargs
        self.grid_options = None
        self.value = None

    def grid(self, **kwargs):
        self.grid_options = kwargs

    def grid_columnconfigure(self, *_args, **_kwargs):
        pass

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def set(self, value):
        self.value = value


class _Variable:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _FakeCtk:
    CTkFrame = CTkLabel = CTkCheckBox = CTkOptionMenu = CTkButton = CTkSlider = _Widget
    BooleanVar = StringVar = IntVar = _Variable
    CTkFont = staticmethod(lambda **_kwargs: None)


@pytest.mark.parametrize("workspace_file", [
    "image_workspace.py", "video_workspace.py", "pdf_workspace.py", "pptx_workspace.py",
])
def test_workspace_panel_row_expands_and_panel_fills_its_own_height(workspace_file):
    source = (ROOT / "nenolink_ai_marker" / workspace_file).read_text(encoding="utf-8")
    mount_body = source.split("    def mount(", 1)[1].split("\n    def ", 1)[0]
    assert "grid_rowconfigure(0, weight=1)" in mount_body
    assert "sticky=\"nsew\"" in mount_body
    assert "WorkspaceControlPanel" in source


def test_pptx_control_panel_height_is_not_bound_to_preview_or_fixed_height():
    source = (ROOT / "nenolink_ai_marker" / "pptx_workspace.py").read_text(encoding="utf-8")
    mount_body = source.split("    def mount(", 1)[1].split("\n    def ", 1)[0]
    assert "self.root.grid_rowconfigure(0, weight=1)" in mount_body
    assert "controls.grid(row=0, column=0" in mount_body
    assert "sticky=\"nsew\"" in mount_body
    assert "controls.configure(height=" not in mount_body
    assert "controls.grid_configure(height=" not in mount_body


def test_badge_and_logo_components_use_shared_left_edge_and_small_control_gaps(monkeypatch):
    import nenolink_ai_marker.badge_control as badge_module
    import nenolink_ai_marker.logo_control as logo_module
    import nenolink_ai_marker.workspace_control_panel as panel_module

    monkeypatch.setattr(badge_module, "ctk", _FakeCtk)
    monkeypatch.setattr(logo_module, "ctk", _FakeCtk)
    monkeypatch.setattr(panel_module, "ctk", _FakeCtk)

    badge = BadgeControl(object())
    logo = LogoControl(object(), on_enabled=lambda _value: None, on_choose=lambda: None, show_mode=True)

    assert badge.enabled_widget.grid_options["padx"] == PARAM_PADX
    assert badge.selector_widget.grid_options["padx"] == PARAM_PADX
    assert badge.selector_widget.grid_options["pady"] == BADGE_SELECTOR_PADY
    assert logo.enabled_widget.grid_options["padx"] == PARAM_PADX
    assert logo.choose_button.grid_options["padx"] == PARAM_PADX
    assert logo.choose_button.grid_options["pady"] == LOGO_CHOOSE_PADY
    assert logo.filename_label.grid_options["padx"] == PARAM_PADX
    assert logo.position_label.options["anchor"] == "w"
    assert logo.position_label.grid_options["padx"] == logo.size_row.label.grid_options["padx"]
    assert logo.mode_widget.grid_options["padx"] == PARAM_PADX


@pytest.mark.parametrize("workspace_file,marker", [
    ("image_workspace.py", "app.position_label = ctk.CTkLabel"),
    ("video_workspace.py", "self.video_position_label = ctk.CTkLabel"),
    ("pdf_workspace.py", "self.badge_position_label = ctk.CTkLabel"),
    ("pptx_workspace.py", "self.badge_position_label = ctk.CTkLabel"),
])
def test_badge_position_labels_are_explicitly_left_anchored(workspace_file, marker):
    source = (ROOT / "nenolink_ai_marker" / workspace_file).read_text(encoding="utf-8")
    line = next(line for line in source.splitlines() if marker in line)
    assert 'anchor="w"' in line


@pytest.mark.parametrize("code", LANGUAGES.values())
def test_pdf_selected_page_count_is_localized_for_all_supported_locales(code):
    translator = Translator(ROOT / "locales", code)
    assert translator.text("pdf.selected_count", count=3).strip()
    assert "3" in translator.text("pdf.selected_count", count=3)


def test_pdf_workspace_projects_localized_selected_count_under_update():
    workspace = PdfWorkspace.__new__(PdfWorkspace)
    workspace.app = SimpleNamespace(
        translator=SimpleNamespace(
            text=lambda key, **values: f"{values['count']} pages selected" if key == "pdf.selected_count" else key
        ),
        pdf_info=None,
        pdf_preview_label=None,
    )
    workspace.state = PdfWorkspaceState(
        path=Path("document.pdf"), page_count=5, current_page=2,
        active_scope=(1, 3, 4),
    )
    workspace._scope_display = {"all": "All", "first": "First", "selected": "Selected", "range": "Range"}
    workspace.scope_control = SimpleNamespace(project=lambda **values: setattr(workspace, "scope_projection", values))
    workspace.logo_control = None
    workspace.navigation_control = None
    workspace.apply_translations = lambda: None
    workspace._ensure_badge_selection = lambda: None
    workspace._project_badge_controls = lambda: None

    workspace.project()

    assert workspace.scope_projection["status"] == "3 pages selected"


@pytest.mark.parametrize("old_mode,new_mode", [("selected", "range"), ("range", "selected")])
def test_pdf_scope_mode_callback_clears_draft_and_preserves_applied_scope(old_mode, new_mode):
    workspace = PdfWorkspace.__new__(PdfWorkspace)
    workspace.state = PdfWorkspaceState(
        path=Path("document.pdf"), page_count=5, current_page=4,
        scope_mode=old_mode, scope_input="2-4", active_scope=(2, 4),
    )
    workspace._scope_value = {"Selected pages": "selected", "Page range": "range"}
    projected = []
    workspace.project = lambda: projected.append((workspace.state.scope_input, workspace.state.active_scope))

    workspace.set_scope_mode("Page range" if new_mode == "range" else "Selected pages")

    assert workspace.state.scope_mode == new_mode
    assert workspace.state.scope_input == ""
    assert (workspace.state.active_scope, workspace.state.current_page) == ((2, 4), 4)
    assert projected == [("", (2, 4))]
    assert "scope_input" in pdf_transition(PdfEvent.SCOPE_MODE).mutates


@pytest.mark.parametrize("old_mode,new_mode", [("selected", "range"), ("range", "selected")])
def test_pptx_scope_mode_callback_clears_draft_and_preserves_applied_scope(old_mode, new_mode):
    workspace = PptxWorkspace.__new__(PptxWorkspace)
    workspace.state = PptxWorkspaceState(
        Path("slides.pptx"), 6, 4, old_mode, (2, 4), "2,4",
    )
    workspace._scope_value = {"Selected slides": "selected", "Slide range": "range"}
    workspace.receipts = SimpleNamespace(record=lambda _receipt: None)
    workspace._project_scope = lambda: None

    workspace._scope_mode("Slide range" if new_mode == "range" else "Selected slides")

    assert workspace.state.scope_mode == new_mode
    assert workspace.state.scope_input == ""
    assert (workspace.state.active_scope, workspace.state.current_slide) == ((2, 4), 4)
    assert {"scope_input", "active_scope", "current_slide"} <= set(pptx_transition(PptxEvent.SCOPE_MODE).mutates)


def test_scope_draft_clearing_does_not_change_independent_workspace_defaults():
    assert PdfWorkspaceState().scope_mode == "all"
    assert PptxWorkspaceState().scope_mode == "all"
    assert pdf_transition(PdfEvent.SCOPE_MODE) in PDF_TRANSITION_TABLE
