import inspect

from nenolink_ai_marker.source_control import SourceControl
from nenolink_ai_marker.image_workspace import ImageWorkspace
from nenolink_ai_marker.video_workspace import VideoWorkspace
from nenolink_ai_marker.pdf_workspace import PdfWorkspace
from nenolink_ai_marker.pptx_workspace import PptxWorkspace
from nenolink_ai_marker.badge_control import BadgeControl
from nenolink_ai_marker.workspace_control_panel import WorkspaceControlPanel
from nenolink_ai_marker import workspace_ui


def test_source_control_is_stateless_presentation_only():
    source = inspect.getsource(SourceControl)
    assert "WorkspaceState" not in source
    assert "MarkerApp" not in source
    assert "def project" in source


def test_each_workspace_constructs_its_own_source_control():
    for workspace in (ImageWorkspace, VideoWorkspace, PdfWorkspace, PptxWorkspace):
        source = inspect.getsource(workspace._build_ui if hasattr(workspace, "_build_ui") else workspace.mount)
        assert "SourceControl" in source


def test_source_callbacks_are_injected_per_workspace():
    for workspace in (ImageWorkspace, VideoWorkspace, PdfWorkspace, PptxWorkspace):
        source = inspect.getsource(workspace._build_ui if hasattr(workspace, "_build_ui") else workspace.mount)
        assert "choose_command=" in source


def test_video_pdf_and_pptx_filename_projection_has_no_legacy_widget_writer():
    from pathlib import Path

    root = Path(__file__).parents[1] / "nenolink_ai_marker"
    video = (root / "video_workspace.py").read_text(encoding="utf-8")
    pdf = (root / "pdf_workspace.py").read_text(encoding="utf-8")
    pptx = (root / "pptx_workspace.py").read_text(encoding="utf-8")
    assert "video_file_label" not in video
    assert "pdf_file_label" not in pdf
    assert "self.file_label" not in pptx
    assert "self.source_control.project" in pdf
    assert "self.source_control.project" in pptx


def test_video_pdf_and_pptx_filename_projection_has_no_legacy_widget_writer():
    from pathlib import Path

    root = Path(__file__).parents[1] / "nenolink_ai_marker"
    video = (root / "video_workspace.py").read_text(encoding="utf-8")
    pdf = (root / "pdf_workspace.py").read_text(encoding="utf-8")
    pptx = (root / "pptx_workspace.py").read_text(encoding="utf-8")
    assert "video_file_label" not in video
    assert "pdf_file_label" not in pdf
    assert "self.file_label" not in pptx
    assert "self.source_control.project" in pdf
    assert "self.source_control.project" in pptx

def test_section_and_badge_controls_are_presentation_only():
    assert "WorkspaceState" not in inspect.getsource(WorkspaceControlPanel)
    source = inspect.getsource(BadgeControl)
    assert "WorkspaceState" not in source
    assert "processor" not in source.lower()
    assert "AI BADGE" in source


def test_historical_workspace_ui_builders_are_removed():
    for name in ("build_badge_visual", "build_badge_section", "build_logo_section", "build_workspace_control_template"):
        assert not hasattr(workspace_ui, name)


class _ProjectedLabel:
    def __init__(self):
        self.options = {}
        self.removed = False

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def grid(self, **kwargs):
        self.grid_options = kwargs
        self.removed = False

    def grid_remove(self):
        self.removed = True


def test_source_control_projects_long_filename_metadata_and_language_changes():
    source = object.__new__(SourceControl)
    source.filename_label = _ProjectedLabel()
    source.metadata_label = _ProjectedLabel()

    long_filename = "a-very-long-source-filename-that-wraps-within-the-fixed-file-column.pptx"
    source.project(filename=long_filename, metadata="4.2 MB · 18 slides", empty_text="Ingen fil valgt")
    assert source.filename_label.options["text"] == long_filename
    assert source.metadata_label.options["text"] == "4.2 MB · 18 slides"
    assert source.metadata_label.removed is False

    # Language changes reproject presentation copy without replacing source data.
    source.project(filename=long_filename, metadata="4,2 MB · 18 dias", empty_text="Nenhum arquivo selecionado")
    assert source.filename_label.options["text"] == long_filename
    assert source.metadata_label.options["text"] == "4,2 MB · 18 dias"

    source.project(filename="", empty_text="Nenhum arquivo selecionado")
    assert source.filename_label.options["text"] == "Nenhum arquivo selecionado"
    assert source.metadata_label.removed is True
