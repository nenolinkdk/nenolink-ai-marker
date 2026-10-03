from pathlib import Path

from nenolink_ai_marker.pptx_state import PptxWorkspaceState, choose_file_cancel, choose_file_success, project_file


def test_file_reducer_and_projection_preserve_badge(tmp_path):
    source = tmp_path / "test.pptx"; source.write_bytes(b"pptx")
    state = PptxWorkspaceState(); state.badge.badge_id = "AI Assisted"
    choose_file_success(state, source, 12)
    assert state.selected_file == source and state.display_filename == "test.pptx"
    assert state.file_size_bytes == 4 and state.slide_count == 12
    assert project_file(state)["details"].endswith("· 12 slides")
    before = state.__dict__.copy(); choose_file_cancel(state)
    assert state.__dict__ == before


def test_empty_file_projection():
    assert project_file(PptxWorkspaceState())["status"] == "No PowerPoint selected"
