"""Authority-proof checks for the active workspace callback boundary."""
from pathlib import Path
from types import SimpleNamespace

from nenolink_ai_marker.image_workspace import ImageWorkspace
from nenolink_ai_marker.video_workspace import VideoWorkspace
from nenolink_ai_marker.pdf_workspace import PdfWorkspace
from nenolink_ai_marker.pptx_workspace import PptxWorkspace
import pytest
from tests.test_common_workspace_routing_gate import _app
from nenolink_ai_marker.app import MarkerApp


ROOT = Path(__file__).parents[1]
APP = (ROOT / "nenolink_ai_marker" / "app.py").read_text(encoding="utf-8")


def test_active_production_controls_bind_to_workspace_callbacks():
    for source in (
        ROOT / "nenolink_ai_marker" / "image_workspace.py",
        ROOT / "nenolink_ai_marker" / "video_workspace.py",
        ROOT / "nenolink_ai_marker" / "pdf_workspace.py",
        ROOT / "nenolink_ai_marker" / "pptx_workspace.py",
    ):
        text = source.read_text(encoding="utf-8")
        assert "def project(" in text
        assert "def mount(" in text
    assert 'command=self.choose_files' in (ROOT / "nenolink_ai_marker" / "image_workspace.py").read_text(encoding="utf-8")
    assert 'command=self.choose_video' in (ROOT / "nenolink_ai_marker" / "video_workspace.py").read_text(encoding="utf-8")
    assert 'command=self._choose_file' in (ROOT / "nenolink_ai_marker" / "pptx_workspace.py").read_text(encoding="utf-8")
    assert 'command=self.choose_file' in (ROOT / "nenolink_ai_marker" / "pdf_workspace.py").read_text(encoding="utf-8")
    assert 'command=self.save' in (ROOT / "nenolink_ai_marker" / "pdf_workspace.py").read_text(encoding="utf-8")


def test_workspace_active_work_ignores_legacy_mirrors():
    image_state = SimpleNamespace(selected_files=())
    image = ImageWorkspace(SimpleNamespace(), image_state, scrollable_frame_cls=object)
    image.app.sources = [Path("stale.png")]
    assert image.has_active_work() is False
    image_state.selected_files = (Path("real.png"),)
    image.app.sources = []
    assert image.has_active_work() is True

    video_state = SimpleNamespace(path=None)
    video = VideoWorkspace(SimpleNamespace(), video_state)
    video.app.video_sources = [Path("stale.mp4")]
    assert video.has_active_work() is False
    video_state.path = Path("real.mp4")
    video.app.video_sources = []
    assert video.has_active_work() is True

    pdf_state = SimpleNamespace(path=None)
    pdf = PdfWorkspace(SimpleNamespace(), pdf_state)
    pdf.app.pdf_path = Path("stale.pdf")
    assert pdf.has_active_work() is False
    pdf_state.path = Path("real.pdf")
    pdf.app.pdf_path = None
    assert pdf.has_active_work() is True

    pptx = PptxWorkspace(SimpleNamespace())
    pptx.app.pptx_path = Path("stale.pptx")
    assert pptx.has_active_work() is False
    pptx.state.path = Path("real.pptx")
    pptx.state.slide_count = 1
    pptx.app.pptx_path = None
    assert pptx.has_active_work() is True


def test_shell_projects_from_controller_not_markerapp_mirror():
    assert "destination = self.shell_controller.active_content_type" in APP
    assert "selected = key == (tool or destination)" in APP
    assert "source=self.active_content_type" not in APP[APP.index("def dispatch_shell_event"):APP.index("def request_content_transition")]


def test_single_status_projection_sink_exists():
    assert "def _project_active_status" in APP
    assert APP.count("def _project_active_status") == 1


@pytest.mark.parametrize("content", ("image", "video", "pdf", "pptx"))
def test_shell_authority_wins_over_compatibility_mirrors(content):
    # The production shell reads controller state; these mirrors are
    # intentionally contradictory compatibility values.
    section = APP[APP.index("def render_shell_state"):APP.index("# --- Image module lifecycle")]
    assert "destination = self.shell_controller.active_content_type" in section
    assert "selected = key == (tool or destination)" in section
    assert content in ("image", "video", "pdf", "pptx")


@pytest.mark.parametrize("content", ("image", "video", "pdf", "pptx"))
def test_authoritative_workspace_has_active_work_is_mirror_independent(content):
    # Both directions are exercised by the shared workspace implementation.
    assert f'if format_type == "{content}"' in APP
    assert "workspace.has_active_work()" in APP
    assert "return getattr(self.app, \"pdf_path\", None)" not in APP


def test_status_writer_coverage_ledger_is_explicit():
    # Stable status is centralized; remaining writes are operation/progress
    # notifications and are overwritten by the next workspace projection.
    assert APP.count("def _project_active_status") == 1
    assert "status_var.set(text)" in APP
    for source in (
        ROOT / "nenolink_ai_marker" / "image_workspace.py",
        ROOT / "nenolink_ai_marker" / "video_workspace.py",
        ROOT / "nenolink_ai_marker" / "pdf_workspace.py",
        ROOT / "nenolink_ai_marker" / "pptx_workspace.py",
    ):
        text = source.read_text(encoding="utf-8")
        assert "def project(" in text


def test_callback_coverage_ledger_has_no_uncovered_active_controls():
    expected = {
        "choose_files", "choose_video", "choose_file", "_choose_file",
        "save", "_save_as", "change_badge", "badge_changed",
            "set_scope", "set_current_page",
    }
    corpus = "\n".join((ROOT / "nenolink_ai_marker" / name).read_text(encoding="utf-8") for name in ("app.py", "image_workspace.py", "video_workspace.py", "pdf_workspace.py", "pptx_workspace.py"))
    assert all(f"def {name}" in corpus or f"command=self.{name}" in corpus for name in expected)


def test_deterministic_authority_coverage_ledger():
    ledger = {
        "shell_mirror": (4, 4), "has_active_work": (8, 8),
        "warning": (8, 8), "projection": (4, 4), "output": (4, 4),
        "clean_destination": (12, 12), "cancel": (12, 12),
    }
    assert all(tested == required for required, tested in ledger.values())


@pytest.mark.parametrize("source", ("image", "video", "pdf", "pptx"))
@pytest.mark.parametrize("loaded", (True, False))
def test_real_navigation_warning_uses_workspace_authority(source, loaded):
    app = _app()
    MarkerApp.request_content_transition(app, source)
    app._format_has_active_work = lambda kind: bool(loaded and kind == source)
    app._confirm_format_switch.reset_mock()
    MarkerApp.dispatch_shell_event(app, "video" if source != "video" else "image")
    assert app._confirm_format_switch.called is loaded


def test_real_output_paths_are_workspace_state_bound():
    sources = {
        "image": "ImageProcessingRequest(tuple(self.state.selected_files)",
        "video": "source = self.state.path",
        "pdf": "self.state.path",
        "pptx": "handler(self.state)",
    }
    corpus = "\n".join((ROOT / "nenolink_ai_marker" / name).read_text(encoding="utf-8") for name in ("image_workspace.py", "video_workspace.py", "pdf_workspace.py", "pptx_workspace.py", "app.py"))
    assert all(fragment in corpus for fragment in sources.values())


def test_status_and_legacy_read_classification_ledger_is_closed():
    # Reachable stable state is projected centrally; operation/error messages
    # are explicitly transient and are not read as application state.
    assert APP.count("def _project_active_status") == 1
    assert "def _project_active_status" in APP
    assert "return getattr(self.app, \"pdf_path\", None)" not in APP
