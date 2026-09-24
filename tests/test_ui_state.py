from pathlib import Path
import inspect

import pytest

from nenolink_ai_marker.ui_state import ContentWorkspaceState, pptx_item_selection, show_welcome
from nenolink_ai_marker.app import MarkerApp


def test_welcome_is_visible_without_an_image():
    assert show_welcome([])


def test_welcome_is_hidden_after_image_selection():
    assert not show_welcome(["selected.png"])


def test_welcome_returns_when_images_are_cleared():
    sources = ["selected.png"]
    sources.clear()
    assert show_welcome(sources)


def test_content_workspaces_preserve_image_and_video_selections_independently():
    state=ContentWorkspaceState()
    assert state.switch("video",[Path("photo.png")])==[]
    assert state.media_sources["image"]==[Path("photo.png")]
    assert state.switch("image",[Path("clip.mp4")])==[Path("photo.png")]
    assert state.media_sources["video"]==[Path("clip.mp4")]


def test_document_workspace_keeps_media_selections_and_reset_clears_all():
    state=ContentWorkspaceState(); state.switch("video",[Path("photo.png")]); state.switch("pptx",[Path("clip.mp4")])
    assert state.media_sources=={"image":[Path("photo.png")],"video":[Path("clip.mp4")]}
    assert state.switch("image",[])==[Path("photo.png")]
    state.clear()
    assert state.active=="image" and state.media_sources=={"image":[],"video":[]}


@pytest.mark.parametrize(
    ("mode", "values", "expected"),
    [
        ("single", {"single": "3"}, (3,)),
        ("selected", {"selected": "2, 4, 7"}, (2, 4, 7)),
        ("range", {"start": "3", "end": "6"}, (3, 4, 5, 6)),
        ("all", {}, (1, 2, 3, 4, 5, 6, 7)),
    ],
)
def test_pptx_ui_selection_modes(mode, values, expected):
    assert pptx_item_selection(mode, **values).resolve(7) == expected


def test_pptx_ui_rejects_invalid_slide_input():
    with pytest.raises(ValueError, match="whole numbers"):
        pptx_item_selection("selected", selected="2, slide 4")


def test_document_workspace_headings_share_the_compact_top_row():
    source = inspect.getsource(MarkerApp._document_ui)
    assert 'document_format_label=ctk.CTkLabel(panel' in source
    assert 'document_format_label.grid(row=0,column=0' in source
    assert 'pptx_scope_label=ctk.CTkLabel(panel' in source
    assert 'pptx_scope_label.grid(row=0,column=1' in source
    assert 'panel.grid(row=0,column=0,padx=20,pady=(4,8)' in source
    assert 'pptx_controls.grid(row=1,column=0,columnspan=2,rowspan=2,padx=12,pady=(0,8)' in source


def test_production_navigation_exposes_pdf_and_powerpoint_but_not_word():
    build_source = inspect.getsource(MarkerApp._build_ui)
    translation_source = inspect.getsource(MarkerApp.apply_translations)
    assert 'values=["PDF","PowerPoint / Slides"]' in build_source
    assert 'values=["PDF","PowerPoint / Slides","Word"]' not in build_source
    assert 'content_pairs=(("image","content.images"),("video","content.video"),("pdf","content.pdf"),("pptx","content.powerpoint"))' in translation_source
    assert 'self.document_navigation.configure(values=[t("content.pdf"),t("content.powerpoint")])' in translation_source
    assert '("docx","content.word")' not in translation_source


def test_navigation_groups_are_compact_and_aligned_to_workspace_boundary():
    source = inspect.getsource(MarkerApp._build_ui)
    assert 'content_navigation_frame.grid(row=1,column=0,padx=20,pady=(6,0),sticky="w")' in source
    assert 'self.tabs.grid(row=2,column=0,padx=16,pady=(0,8),sticky="nsew")' in source
    document_navigation = next(line for line in source.splitlines() if 'self.document_navigation=ctk.CTkSegmentedButton' in line)
    assert 'width=' not in document_navigation


def test_docx_ui_exposes_only_reliable_alignment_and_hides_margin_controls():
    source = inspect.getsource(MarkerApp.apply_translations)
    assert 't("docx.position.left"):"bottom-left"' in source
    assert 't("docx.position.center"):"center"' in source
    assert 't("docx.position.right"):"bottom-right"' in source
    assert 'self.pptx_margin_label.grid_remove()' in source
    assert 'self.pptx_logo_margin_label.grid_remove()' in source
