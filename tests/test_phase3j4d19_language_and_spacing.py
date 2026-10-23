from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.badge_control import BadgeControl
from nenolink_ai_marker.image_workspace import ImageWorkspace
from nenolink_ai_marker.logo_control import LogoControl
from nenolink_ai_marker.pptx_state import PptxWorkspaceState
from nenolink_ai_marker.workspace_control_panel import (
    BADGE_PREVIEW_PADY,
    PARAM_LABEL_PADY,
    PARAM_SLIDER_PADY,
    PARAM_CONTROL_WIDTH,
    PARAM_LABEL_WIDTH,
    PARAM_ROW_PADY,
    ParameterRow,
)
from nenolink_ai_marker.workspace_state import (
    ImageWorkspaceState,
    PdfWorkspaceState,
    VideoWorkspaceState,
)


class FakeTranslator:
    def __init__(self):
        self.language = "en"

    def set_language(self, language):
        self.language = language

    def text(self, key, **values):
        result = f"{self.language}:{key}"
        return result.format(**values) if values else result


class FakeWidget:
    instances = []

    def __init__(self, *_args, **kwargs):
        self.options = kwargs
        self.grid_options = None
        self.configured = {}
        self.instances.append(self)

    def grid(self, **kwargs):
        self.grid_options = kwargs

    def grid_columnconfigure(self, *_args, **_kwargs):
        pass

    def configure(self, **kwargs):
        self.configured.update(kwargs)

    def set(self, value):
        self.value = value


class FakeVariable:
    def __init__(self, value=None):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeWorkspace:
    def __init__(self, state, *, pptx=False):
        self.state = state
        self.root = SimpleNamespace(winfo_exists=lambda: True)
        if pptx:
            self.mounted = True
            self.apply_language = self._apply_language
        self.translation_calls = 0
        self.language_calls = 0

    def apply_translations(self):
        self.translation_calls += 1

    def _apply_language(self, _translator):
        self.language_calls += 1


class FakeShellController:
    def __init__(self, content):
        self.active_content_type = content


def _language_callback_harness(content, tool):
    states = {
        "image": ImageWorkspaceState(),
        "video": VideoWorkspaceState(),
        "pdf": PdfWorkspaceState(),
        "pptx": PptxWorkspaceState(),
    }
    workspaces = {
        key: FakeWorkspace(state, pptx=(key == "pptx"))
        for key, state in states.items()
    }
    widgets = {key: FakeWidget() for key in MarkerApp._label_keys}
    group_labels = {key: FakeWidget() for key in (
        "content.media_group", "content.documents_group", "content.tools_group"
    )}
    app = SimpleNamespace(
        translator=FakeTranslator(),
        language_var=FakeVariable("English"),
        content_buttons=widgets,
        shell_group_labels=group_labels,
        reset_button=FakeWidget(),
        guide_button=FakeWidget(),
        shell_controller=FakeShellController(content),
        _workspace_registry=workspaces,
        _mounted_tool_name=tool,
        _save=lambda: None,
        tool_back_button=FakeWidget() if tool else None,
        tool_badge_source_heading=FakeWidget() if tool == "badges" else None,
        tool_badge_standard_radio=FakeWidget() if tool == "badges" else None,
        tool_badge_custom_radio=FakeWidget() if tool == "badges" else None,
        tool_badge_choose_folder=FakeWidget() if tool == "badges" else None,
        tool_badge_refresh=FakeWidget() if tool == "badges" else None,
        tool_inspect_heading=FakeWidget() if tool == "inspect" else None,
        tool_inspect_choose=FakeWidget() if tool == "inspect" else None,
        tool_inspect_result=FakeWidget() if tool == "inspect" else None,
        _tool_inspection_projection=None,
    )
    before = {key: asdict(state) for key, state in states.items()}
    return app, workspaces, states, before


@pytest.mark.parametrize("content", ("image", "video", "pdf", "pptx"))
@pytest.mark.parametrize("tool", (None, "badges", "inspect"))
def test_shell_language_selection_reprojects_current_workspace_and_tool_without_state_change(content, tool):
    app, workspaces, states, before = _language_callback_harness(content, tool)

    MarkerApp.change_language(app, "Dansk")

    active = workspaces[content]
    if content == "pptx":
        assert active.language_calls == 1
        assert active.translation_calls == 0
    else:
        assert active.translation_calls == 1
        assert active.language_calls == 0
    assert all(
        ws.translation_calls == ws.language_calls == 0
        for key, ws in workspaces.items() if key != content
    )
    assert {key: asdict(state) for key, state in states.items()} == before
    assert app.translator.language == "da"
    assert app.language_var.get() == "Dansk"
    if tool == "badges":
        assert app.tool_badge_refresh.configured["text"] == "da:badge.refresh"
        assert app.tool_back_button.configured["text"] == "da:button.back"
    elif tool == "inspect":
        assert app.tool_inspect_choose.configured["text"] == "da:inspect.choose"
        assert app.tool_inspect_result.configured["text"] == "da:inspect.none"


def test_constructed_shell_language_menu_uses_global_language_callback():
    import inspect

    source = inspect.getsource(MarkerApp._build_shell_ui)
    assert "command=self.change_language" in source


def test_badge_logo_and_all_workspace_parameter_spacing_share_tokens(monkeypatch):
    import customtkinter as ctk

    for name in ("CTkFrame", "CTkCheckBox", "CTkOptionMenu", "CTkLabel", "CTkButton", "CTkSlider"):
        monkeypatch.setattr(ctk, name, FakeWidget)
    for name in ("StringVar", "BooleanVar"):
        monkeypatch.setattr(ctk, name, FakeVariable)
    monkeypatch.setattr(ctk, "CTkFont", lambda **_kwargs: object())

    badge = BadgeControl(FakeWidget())
    assert badge.graphic_widget.grid_options["pady"] == BADGE_PREVIEW_PADY

    logo = LogoControl(FakeWidget(), on_enabled=lambda _value: None, on_choose=lambda: None)
    assert logo.position_label.grid_options["pady"] == PARAM_LABEL_PADY
    assert all(widget.grid_options["pady"] == PARAM_SLIDER_PADY for widget in (
        logo.size_widget, logo.margin_widget, logo.opacity_widget
    ))
    assert all(row.frame.grid_options["pady"] == PARAM_ROW_PADY for row in (
        logo.size_row, logo.margin_row, logo.opacity_row
    ))
    assert all(row.label.options["width"] == PARAM_LABEL_WIDTH for row in (
        logo.size_row, logo.margin_row, logo.opacity_row
    ))
    assert all(row.slider.options["width"] == PARAM_CONTROL_WIDTH for row in (
        logo.size_row, logo.margin_row, logo.opacity_row
    ))

    image_workspace = SimpleNamespace(
        app=SimpleNamespace(translator=FakeTranslator()),
        visual_changed=lambda *_args: None,
        badge_parameter_rows={},
    )
    image_label = ImageWorkspace._slider(image_workspace, FakeWidget(), FakeVariable(20), 1, 100, 3, "size.value")
    image_row = image_workspace.badge_parameter_rows["size"]
    assert image_row.label is image_label
    assert image_row.label.grid_options["pady"] == PARAM_LABEL_PADY
    assert image_row.slider.grid_options["pady"] == PARAM_SLIDER_PADY
    assert image_row.frame.grid_options["pady"] == PARAM_ROW_PADY

    video_workspace_source = (Path(__file__).parents[1] / "nenolink_ai_marker" / "video_workspace.py").read_text(encoding="utf-8")
    pptx_workspace_source = (Path(__file__).parents[1] / "nenolink_ai_marker" / "pptx_workspace.py").read_text(encoding="utf-8")
    pdf_workspace_source = (Path(__file__).parents[1] / "nenolink_ai_marker" / "pdf_workspace.py").read_text(encoding="utf-8")
    assert "ParameterRow(app.video_badge_group" in video_workspace_source
    assert "ParameterRow(host" in pptx_workspace_source
    assert "ParameterRow(badge_section" in pdf_workspace_source
