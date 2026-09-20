from pathlib import Path

import pytest

from nenolink_ai_marker.ui_state import ContentWorkspaceState, pptx_item_selection, show_welcome


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
