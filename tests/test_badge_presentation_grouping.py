from pathlib import Path
import customtkinter as ctk

from nenolink_ai_marker.save_control import SaveControl
from nenolink_ai_marker.source_control import SourceControl
from nenolink_ai_marker.workspace_control_panel import (
    FILE_CHOOSE_WIDTH, FILE_SAVE_WIDTH, PARAM_CONTROL_WIDTH,
    PARAM_LABEL_WIDTH, PARAM_ROW_PADY, ParameterRow,
)


ROOT = Path(__file__).parents[1] / "nenolink_ai_marker"


def test_image_badge_group_contains_badge_and_visual_controls_before_logo():
    source = (ROOT / "image_workspace.py").read_text(encoding="utf-8")
    assert "image_badge_group" in source
    assert "self.badge_control.frame.grid(row=0, column=0" in source
    assert "_slider(app.image_badge_group" in source
    assert "self.logo_control.frame.grid(row=0, column=0" in source


def test_image_control_panel_is_the_only_outer_left_geometry_owner():
    source = (ROOT / "image_workspace.py").read_text(encoding="utf-8")
    assert source.count("WorkspaceControlPanel(") == 1
    assert 'add_section("FILE", file_section)' in source
    assert 'add_section("AI_BADGE", app.image_badge_group)' in source
    assert 'add_section("OWN_LOGO", logo_section)' in source
    assert source.index('add_section("FILE", file_section)') < source.index('add_section("AI_BADGE", app.image_badge_group)') < source.index('add_section("OWN_LOGO", logo_section)')
    assert "process_button.grid(row=4" not in source
    assert "image_badge_group.grid(row=2" not in source
    assert "logo_control.frame.grid(row=3" not in source


def test_video_badge_group_precedes_options_and_output():
    source = (ROOT / "video_workspace.py").read_text(encoding="utf-8")
    assert "video_badge_group" in source
    assert "ParameterRow(app.video_badge_group" in source
    assert 'add_section("AI_BADGE", app.video_badge_group)' in source
    assert 'add_section("OWN_LOGO", logo_section)' in source
    assert 'add_section("VIDEO_OPTIONS", options_section)' in source
    assert 'SaveControl(self.source_control.action_row' in source


def test_all_workspace_panels_use_canonical_section_order():
    expected = {
        "image_workspace.py": ['"FILE", "AI_BADGE", "OWN_LOGO"'],
        "video_workspace.py": ['"FILE", "AI_BADGE", "OWN_LOGO", "VIDEO_OPTIONS"'],
        "pdf_workspace.py": ['"FILE", "PAGES", "AI_BADGE", "OWN_LOGO"'],
        "pptx_workspace.py": ['"FILE", "SLIDES", "AI_BADGE", "OWN_LOGO"'],
    }
    for filename, tokens in expected.items():
        source = (ROOT / filename).read_text(encoding="utf-8")
        assert "WorkspaceControlPanel" in source
        assert any(token in source for token in tokens)


def test_shared_compact_file_and_parameter_geometry_contract():
    source = (ROOT / "source_control.py").read_text(encoding="utf-8")
    panel = (ROOT / "workspace_control_panel.py").read_text(encoding="utf-8")
    assert "compact: bool = False" in source
    assert "self.action_row.grid(row=0, column=0" in source
    assert "def place_save_control" in source
    assert "PARAM_ROW_PADY = (0, 2)" in panel
    assert "PARAM_LABEL_WIDTH = 110" in panel
    assert "PARAM_CONTROL_WIDTH = 205" in panel
    for filename in ("image_workspace.py", "video_workspace.py", "pdf_workspace.py", "pptx_workspace.py"):
        workspace = (ROOT / filename).read_text(encoding="utf-8")
        assert "compact=True" in workspace
        assert "SaveControl(self.source_control.action_row" in workspace
        assert "self.source_control.place_save_control" in workspace


class FakeWidget:
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.options = kwargs
        self.grid_options = None
        self.configured = {}

    def grid(self, **kwargs):
        self.grid_options = kwargs

    def grid_columnconfigure(self, *_args, **_kwargs):
        pass

    def grid_remove(self):
        self.grid_options = None

    def configure(self, **kwargs):
        self.configured.update(kwargs)

    def set(self, value):
        self.value = value


def test_constructed_source_and_save_controls_share_one_action_row(monkeypatch):
    monkeypatch.setattr(ctk, "CTkFrame", FakeWidget)
    monkeypatch.setattr(ctk, "CTkButton", FakeWidget)
    monkeypatch.setattr(ctk, "CTkLabel", FakeWidget)
    source = SourceControl(object(), choose_command=lambda: None, compact=True, width=280)
    save = SaveControl(source.action_row, command=lambda: None, width=999)
    source.place_save_control(save)

    assert source.choose_button.parent is save.button.parent is source.action_row
    assert source.choose_button.grid_options["row"] == save.button.grid_options["row"] == 0
    assert source.choose_button.grid_options["column"] == 0
    assert save.button.grid_options["column"] == 1
    assert source.filename_label.grid_options["row"] == 1
    assert source.metadata_label.grid_options is None
    assert source.choose_button.options["width"] == FILE_CHOOSE_WIDTH
    assert save.button.configured["width"] == FILE_SAVE_WIDTH
    assert source.metadata_label.grid_options is None
    source.project(filename="a-very-long-source-name-that-must-not-resize-the-panel.pptx", metadata="3.4 MB")
    assert source.filename_label.configured["text"].startswith("a-very-long-source-name")
    assert source.metadata_label.grid_options["row"] == 2
    assert source.choose_button.options["width"] == FILE_CHOOSE_WIDTH
    assert save.button.configured["width"] == FILE_SAVE_WIDTH
    source.project(filename="", metadata="")
    assert source.metadata_label.grid_options is None


def test_shared_parameter_rows_use_one_constructed_geometry(monkeypatch):
    for name in ("CTkFrame", "CTkLabel", "CTkSlider"):
        monkeypatch.setattr(ctk, name, FakeWidget)
    badge = ParameterRow(object(), text="Badge size", start=1, end=100, value=20, command=lambda _v: None)
    logo = ParameterRow(object(), text="Logo size", start=1, end=100, value=15, command=lambda _v: None)
    assert badge.label.options["width"] == logo.label.options["width"] == PARAM_LABEL_WIDTH
    assert badge.slider.options["width"] == logo.slider.options["width"] == PARAM_CONTROL_WIDTH
    assert badge.slider.options["from_"] == logo.slider.options["from_"] == 1
    assert badge.slider.options["to"] == logo.slider.options["to"] == 100
    assert badge.slider.options["number_of_steps"] == logo.slider.options["number_of_steps"] == 99
    assert badge.label.grid_options == logo.label.grid_options
    assert badge.slider.grid_options == logo.slider.grid_options
    assert badge.frame is not logo.frame


def test_all_workspace_badge_position_rows_use_shared_geometry_tokens():
    for filename in ("image_workspace.py", "video_workspace.py", "pdf_workspace.py", "pptx_workspace.py"):
        source = (ROOT / filename).read_text(encoding="utf-8")
        assert "PARAM_LABEL_WIDTH" in source
        assert "PARAM_DROPDOWN_WIDTH" in source
    panel = (ROOT / "workspace_control_panel.py").read_text(encoding="utf-8")
    assert "PARAM_DROPDOWN_WIDTH = 205" in panel


def test_file_sections_use_one_column_around_nested_choose_save_row():
    for filename in ("image_workspace.py", "video_workspace.py", "pdf_workspace.py", "pptx_workspace.py"):
        source = (ROOT / filename).read_text(encoding="utf-8")
        assert "file_heading.grid(row=0, column=0, columnspan=2" not in source
        assert "source_control.frame.grid(row=1, column=0, columnspan=2" not in source


def test_pdf_badge_controls_are_constructed_and_projected_from_pdf_state():
    source = (ROOT / "pdf_workspace.py").read_text(encoding="utf-8")
    assert "self.badge_position_menu = ctk.CTkOptionMenu" in source
    assert "ParameterRow(badge_section" in source
    assert 'self.set_badge(**{field: round(new_value)})' in source
    assert "row.project(text=app.translator.text(key, value=value), value=value)" in source
