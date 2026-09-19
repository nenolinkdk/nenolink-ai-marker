from pathlib import Path

from nenolink_ai_marker.ui_state import ContentWorkspaceState, show_welcome


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
