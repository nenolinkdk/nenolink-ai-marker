from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from PIL import Image
from pypdf import PdfReader, PdfWriter

from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.pdf_processor import PdfProcessor
from nenolink_ai_marker.pdf_workspace import PdfWorkspace
from nenolink_ai_marker.pptx_state import PptxEvent, PptxWorkspaceState
from nenolink_ai_marker.pptx_workspace import PptxWorkspace


def _make_pdf(path: Path, count: int = 3) -> None:
    writer = PdfWriter()
    for _ in range(count):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as stream:
        writer.write(stream)


def _make_image(path: Path, color=(30, 180, 70, 220)) -> None:
    Image.new("RGBA", (36, 20), color).save(path)


def test_pdf_preview_settings_are_projected_from_workspace_state(tmp_path, monkeypatch):
    import nenolink_ai_marker.pdf_workspace as module

    source = tmp_path / "source.pdf"
    _make_pdf(source)
    badge = tmp_path / "badge.png"
    logo = tmp_path / "logo.png"
    _make_image(badge)
    _make_image(logo, (200, 20, 20, 170))
    state = module.PdfWorkspaceState(
        path=source, page_count=3, current_page=2, active_scope=(1, 2, 3)
    )
    state.badge.enabled = True
    state.badge.badge_id = badge.name
    state.badge.position, state.badge.size = "top-left", 37
    state.badge.margin, state.badge.opacity = 9, 61
    state.logo.enabled, state.logo.path = True, logo
    state.logo.position, state.logo.size = "bottom-left", 28
    state.logo.margin, state.logo.opacity = 13, 47

    calls = []

    class Renderer:
        def render(self, _source, page, badge_path, settings, logo_path, *, max_size):
            calls.append((page, badge_path, settings, logo_path, max_size))
            return SimpleNamespace(image=Image.new("RGBA", (80, 100)), page_number=page)

    class Widget:
        def update_idletasks(self): pass
        def winfo_width(self): return 400
        def winfo_height(self): return 500
        def configure(self, **_kwargs): pass

    app = SimpleNamespace(
        pdf_info=PdfProcessor.inspect(source),
        pdf_preview_label=Widget(),
        pdf_preview_renderer=Renderer(),
        pdf_preview_host=None,
        badges=SimpleNamespace(find=lambda _name: badge),
        settings=lambda: MarkerSettings(
            position="center", size_percent=2, margin=200, opacity=1,
            logo_enabled=False, logo_path="stale-compatibility-value.png",
        ),
        _boot=lambda _message: None,
    )
    workspace = PdfWorkspace(app, state)
    workspace.navigation_control = SimpleNamespace(project=lambda **_kwargs: None)
    monkeypatch.setattr(module.ctk, "CTkImage", lambda **kwargs: object())

    workspace.refresh_preview()

    page, projected_badge, settings, projected_logo, _size = calls[0]
    assert page == 2
    assert projected_badge == badge
    assert projected_logo == logo
    assert (settings.badge_name, settings.position, settings.size_percent,
            settings.margin, settings.opacity) == (
        badge.name, "top-left", 37, 9, 61,
    )
    assert (settings.logo_enabled, settings.logo_path, settings.logo_position,
            settings.logo_size_percent, settings.logo_margin, settings.logo_opacity) == (
        True, str(logo), "bottom-left", 28, 13, 47,
    )
    assert state.current_page == 2


def test_pdf_save_callback_processes_workspace_badge_logo_and_scope(tmp_path, monkeypatch):
    import nenolink_ai_marker.pdf_workspace as module

    source = tmp_path / "source.pdf"
    output = tmp_path / "marked.pdf"
    _make_pdf(source)
    badge = tmp_path / "badge.png"
    logo = tmp_path / "logo.png"
    _make_image(badge)
    _make_image(logo, (200, 20, 20, 170))
    state = module.PdfWorkspaceState(
        path=source, page_count=3, current_page=1, active_scope=(2,)
    )
    state.badge.enabled = True
    state.badge.badge_id = badge.name
    state.badge.position, state.badge.size = "top-left", 37
    state.badge.margin, state.badge.opacity = 9, 61
    state.logo.enabled, state.logo.path = True, logo
    state.logo.position, state.logo.size = "bottom-left", 28
    state.logo.margin, state.logo.opacity = 13, 47

    class Processor:
        def __init__(self):
            self.request = self.selection = self.result = None
            self.real = PdfProcessor()

        def process(self, request, selection):
            self.request, self.selection = request, selection
            self.result = self.real.process(request, selection)
            return self.result

    processor = Processor()
    app = SimpleNamespace(
        pdf_info=PdfProcessor.inspect(source),
        badges=SimpleNamespace(find=lambda _name: badge,
                               display_name=lambda _name: "AI Assisted"),
        settings=lambda: MarkerSettings(position="center", size_percent=2,
                                        margin=200, opacity=1),
        translator=SimpleNamespace(language="en", text=lambda key, **values: key.format(**values)),
        _confirm_pdf_limits_phase6=lambda: True,
        _confirm_pdf_signature=lambda: True,
        pdf_processor=processor,
        status_var=SimpleNamespace(set=lambda _text: None),
    )
    monkeypatch.setattr(module.filedialog, "asksaveasfilename", lambda **_kwargs: str(output))
    monkeypatch.setattr(module.messagebox, "showinfo", lambda *_args: None)
    workspace = PdfWorkspace(app, state)

    workspace.save()

    assert output.is_file()
    assert processor.selection.items == (2,)
    assert processor.result.selected_pages == (2,)
    assert processor.result.badge_pages == processor.result.logo_pages == 1
    assert (processor.request.disclosure.position,
            processor.request.disclosure.size_percent,
            processor.request.disclosure.margin,
            processor.request.disclosure.opacity) == ("top-left", 37, 9, 61)
    assert (processor.request.logo.position, processor.request.logo.size_percent,
            processor.request.logo.margin, processor.request.logo.opacity) == (
        "bottom-left", 28, 13, 47,
    )
    assert len(PdfReader(output).pages) == 3


def test_pptx_logo_picker_dispatches_selection_and_enable_events(tmp_path, monkeypatch):
    import nenolink_ai_marker.pptx_workspace as module

    selected_logo = tmp_path / "brand.webp"
    app = SimpleNamespace(translator=SimpleNamespace(
        text=lambda key: key, language="en"))
    workspace = PptxWorkspace(app)
    events = []
    real_apply = module.apply_pptx_event

    def record_apply(state, event, value=None):
        events.append((event, value))
        return real_apply(state, event, value)

    monkeypatch.setattr(module, "apply_pptx_event", record_apply)
    monkeypatch.setattr(module.filedialog, "askopenfilename", lambda **_kwargs: str(selected_logo))

    workspace._choose_logo()

    assert [event for event, _value in events] == [PptxEvent.LOGO_CHOOSE, PptxEvent.LOGO_ENABLE]
    assert workspace.state.logo.path == selected_logo
    assert workspace.state.logo.enabled is True


def test_pptx_preview_logo_all_default_is_independent_from_badge_scope(tmp_path, monkeypatch):
    import nenolink_ai_marker.pptx_workspace as module

    source = tmp_path / "deck.pptx"
    from test_pptx_processor import _create_pptx
    _create_pptx(source, 3)
    logo = tmp_path / "brand.png"
    _make_image(logo)
    state = PptxWorkspaceState(path=source, slide_count=3, current_slide=1,
                              scope_mode="selected", active_scope=(2,))
    state.logo.enabled, state.logo.path = True, logo
    calls = []

    class Renderer:
        def slide_dimensions(self, _path): return 16.0, 9.0
        def render(self, _path, slide, badge, settings, logo_path, *, max_size):
            calls.append((slide, badge, settings, logo_path, max_size))
            return SimpleNamespace(image=Image.new("RGBA", (80, 45)),
                                   slide_number=slide, slide_count=3)

    class Viewport:
        def update_idletasks(self): pass
        def winfo_width(self): return 600
        def winfo_height(self): return 400

    class Label:
        def configure(self, **_kwargs): pass

    app = SimpleNamespace(
        pptx_preview_renderer=Renderer(),
        badges=SimpleNamespace(display_badges=lambda: (), display_name=lambda name: name),
    )
    workspace = PptxWorkspace(app)
    workspace.state = state
    workspace.preview_viewport = Viewport()
    workspace.preview_label = Label()
    workspace.navigation_control = SimpleNamespace(project=lambda **_kwargs: None)
    monkeypatch.setattr(module.ctk, "CTkImage", lambda *_args, **_kwargs: object())

    workspace._render_preview()
    assert calls[-1][0] == 1
    assert calls[-1][3] == logo and calls[-1][2].logo_enabled is True

    workspace._change_slide(1)
    assert state.current_slide == 2
    workspace._render_preview()
    assert calls[-1][0] == 2
    assert calls[-1][3] == logo and calls[-1][2].logo_enabled is True


def test_pptx_save_callback_keeps_default_all_logo_scope_independent(tmp_path, monkeypatch):
    from copy import deepcopy
    import nenolink_ai_marker.pptx_workspace as module
    from nenolink_ai_marker.pptx_processor import P, PptxProcessor
    from test_pptx_processor import _create_pptx, _picture_count

    source = tmp_path / "source.pptx"
    output = tmp_path / "output.pptx"
    _create_pptx(source, 3)
    logo = tmp_path / "brand.png"
    _make_image(logo)
    state = PptxWorkspaceState(path=source, slide_count=3, current_slide=1,
                              scope_mode="selected", active_scope=(2,))
    state.logo.enabled, state.logo.path = True, logo
    messages = []
    translator = SimpleNamespace(language="en", text=lambda key, **values: key.format(**values))
    app = SimpleNamespace(
        translator=translator,
        badges=SimpleNamespace(find=lambda _name: None, display_name=lambda _name: "",
                               canonical_filename=lambda _name: None),
        settings=lambda: MarkerSettings(), pptx_processor=PptxProcessor(),
        status_var=SimpleNamespace(set=messages.append),
    )
    workspace = PptxWorkspace(app)
    workspace.state = state
    before_save = deepcopy(state)
    workspace.scope_status = SimpleNamespace(configure=lambda **_kwargs: None)
    monkeypatch.setattr(module.filedialog, "asksaveasfilename", lambda **_kwargs: str(output))
    monkeypatch.setattr("tkinter.messagebox.showerror", lambda *_args: None)
    monkeypatch.setattr("tkinter.messagebox.showwarning", lambda *_args: None)

    workspace._save_as()

    assert state == before_save  # Save is a command; it does not transition PPTX state.
    assert output.is_file()
    with ZipFile(output) as archive:
        assert [_picture_count(archive, page) for page in range(1, 4)] == [1, 1, 1]
        slide = ET.fromstring(archive.read("ppt/slides/slide2.xml"))
        assert len(slide.findall(f".//{{{P}}}pic")) == 1
    assert messages and messages[-1] == "pptx.saved"


def test_invalid_pptx_scope_callback_preserves_effective_scope_and_page():
    from nenolink_ai_marker.pptx_workspace import PptxWorkspace

    class Var:
        def __init__(self, value): self.value = value
        def get(self): return self.value
        def set(self, value): self.value = value

    class Status:
        def configure(self, **kwargs): self.text = kwargs.get("text")

    state = PptxWorkspaceState(path=Path("deck.pptx"), slide_count=8,
                              current_slide=4, scope_mode="selected",
                              active_scope=(2, 4), scope_input="2,4")
    app = SimpleNamespace(translator=SimpleNamespace(
        text=lambda key, **_values: "localized invalid scope" if key == "document.scope_invalid" else key))
    workspace = PptxWorkspace(app)
    workspace.state = state
    workspace.scope_input_var = Var("9")
    workspace.scope_var = Var("Selected slides")
    workspace.scope_status = Status()

    workspace._scope_update()

    assert state.scope_input == "9"
    assert state.active_scope == (2, 4) and state.current_slide == 4
    assert workspace.scope_status.text == "localized invalid scope"


def test_logo_control_exposes_timing_only_when_workspace_supports_it(monkeypatch):
    import nenolink_ai_marker.logo_control as module

    class Widget:
        def __init__(self, *_args, **kwargs):
            self.options = kwargs
            self.grid_calls = []
        def grid(self, **kwargs): self.grid_calls.append(kwargs)
        def grid_columnconfigure(self, *_args, **_kwargs): pass
        def configure(self, **kwargs): self.options.update(kwargs)

    class Variable:
        def __init__(self, value=None): self.value = value
        def set(self, value): self.value = value

    class ParameterRow:
        def __init__(self, *_args, **_kwargs): self.frame = Widget(); self.slider = Widget()
        def project(self, **_kwargs): pass

    monkeypatch.setattr(module.ctk, "CTkFrame", Widget)
    monkeypatch.setattr(module.ctk, "CTkLabel", Widget)
    monkeypatch.setattr(module.ctk, "CTkCheckBox", Widget)
    monkeypatch.setattr(module.ctk, "CTkButton", Widget)
    monkeypatch.setattr(module.ctk, "CTkOptionMenu", Widget)
    monkeypatch.setattr(module.ctk, "BooleanVar", Variable)
    monkeypatch.setattr(module.ctk, "StringVar", Variable)
    monkeypatch.setattr(module.ctk, "CTkFont", lambda **_kwargs: object())
    monkeypatch.setattr(module, "ParameterRow", ParameterRow)

    common = dict(on_enabled=lambda _value: None, on_choose=lambda: None)
    non_video = module.LogoControl(Widget(), **common)
    video = module.LogoControl(Widget(), **common, on_mode=lambda _value: None, show_mode=True)
    non_video.project(module.LogoProjection(labels={}))
    video.project(module.LogoProjection(mode="front", modes=("front", "entire", "back"), labels={}))

    assert non_video.mode_widget is None
    assert non_video.mode_var is None
    assert video.mode_widget is not None
    assert video.mode_var.value == "Front"
