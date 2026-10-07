from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
import hashlib
import json
import os
import shutil
import sys
import threading
import time
import subprocess
import webbrowser
from tkinter import TclError, filedialog, messagebox
import customtkinter as ctk
from PIL import Image

from . import __version__
from .badges import BadgeSourceManager, choose_badge_selection
from .batch import BatchProcessor, BatchResult, FolderScan, VIDEO_EXTENSIONS, destination_root, extract_video_frame, find_ffmpeg, hidden_subprocess_kwargs, is_above_recommended_size, scan_folder
from .config import ConfigStore
from .document_processing import ItemSelection, ProcessingRequest, settings_for_documents
from .image_output import ImageProcessingRequest
from .document_limits import DocumentMetrics, assess_document
from .guide import open_user_guide
from .i18n import LANGUAGES, Translator
from .inspection import INSPECT_EXTENSIONS, InspectionResult, human_file_size, inspect_file
from .metadata import marker_metadata
from .models import MarkerSettings
from .paths import badge_directory, locale_directory, localized_user_guide_path, welcome_image_path
from .processor import ImageProcessor, SUPPORTED_EXTENSIONS
from .preview import ImagePreviewRenderer
from .pptx_processor import PptxProcessor
from .pptx_preview import PptxPreviewRenderer
from .pptx_state import PptxWorkspaceState, PptxEvent, apply_pptx_visual_event
from .pptx_workspace import PptxWorkspace, PPTX_STATE_TOKEN
from .workspace_state import ImageWorkspaceState, VideoWorkspaceState, PdfWorkspaceState, visual_projection, PdfEvent, apply_pdf_event
from .image_workspace import ImageWorkspace
from .video_workspace import VideoWorkspace
from .pdf_workspace import PdfWorkspace
from .workspace_ui import WORKSPACE_LAYOUT, build_badge_section, build_logo_section, build_workspace_control_template, build_badge_visual
from .pdf_processor import PasswordProtectedPdfError, PdfInfo, PdfProcessor
from .pdf_preview import PdfPreviewRenderer
from .docx_processor import DocxInfo, DocxProcessor
from .docx_preview import DocxPreviewRenderer
from .shortcut import ShortcutError, create_desktop_shortcut
from .ui_state import DocumentPreviewState, DocumentScopeState, pptx_item_selection, show_welcome
from .update_check import UpdateCheckError, check_for_update, is_approved_update_url, should_check_automatically
from .shell_controller import DESTINATIONS, ShellController, placeholder_for, shell_transition_spec, ShellTransitionExecutor
from .workspace_control_panel import PARAM_LABEL_WIDTH, PARAM_CONTROL_WIDTH

def _runtime_boot_logger():
    """Return a flushed application logger for packaged runtime diagnostics."""
    path = os.environ.get("NENOLINK_BOOT_LOG")
    def write(message: str) -> None:
        if not path:
            return
        try:
            with open(path, "a", encoding="utf-8") as stream:
                stream.write(str(message) + "\n")
                stream.flush()
        except OSError:
            return
    return write

class _ShellRuntimeAdapter:
    def __init__(self, app):
        self.app = app
        self.destination_lookup = "not_attempted"
        self.resolved_workspace = ""
        self.mount_result = "not_attempted"
        self.project_result = "not_attempted"
        self.tool_result = "not_attempted"
        self.cleared_workspaces = []
        self.clear_failures = []
    def begin_receipt(self, spec):
        self.destination_lookup = "not_attempted"
        self.resolved_workspace = ""
        self.mount_result = "not_attempted"
        self.project_result = "not_attempted"
        self.tool_result = "not_attempted"
        self.cleared_workspaces = []
        self.clear_failures = []
    def preserve_source(self): return None
    def clear_source(self, source): self.app._workspace_registry[source].clear_runtime_state()
    def clean_destination(self, destination): self.app._workspace_registry[destination].enter_clean()
    def clear_all_workspaces(self):
        for source in DESTINATIONS:
            try:
                self.app._workspace_registry[source].clear_runtime_state()
                self.cleared_workspaces.append(source)
            except Exception as error:
                self.clear_failures.append(f"{source}: {type(error).__name__}: {error}")
                raise
    def unmount_source(self, source): self.app._workspace_registry[source].unmount()
    def mount_destination(self, destination):
        self.destination_lookup = "success" if destination in self.app._workspace_registry else "failure"
        workspace = self.app._workspace_registry[destination]
        self.resolved_workspace = type(workspace).__name__
        # Commit the destination in the authoritative Shell FSM before any
        # destination mount/projection can observe or render it.
        if self.app.shell_controller.active_content_type != destination:
            self.app.shell_controller.commit_content(destination)
        workspace.mount(self.app.content_host)
        self.mount_result = "success"
    def project_destination(self, destination):
        self.app._workspace_registry[destination].project()
        self.project_result = "success"
        self.app.mounted_view = destination.upper()
    def mount_tool(self, tool):
        self.app._mount_tool(tool)
        self.app.shell_controller.commit_tool(tool)
        self.tool_result = "success"
        self.app.mounted_view = tool.upper()
    def unmount_tool(self): self.app._unmount_tool()
    def clear_tool(self): self.app.shell_controller.active_tool = None
    def record_receipt(self, receipt):
        self.app.last_shell_receipt = receipt
        self.app.shell_controller.receipts.append(receipt)


class AutoHideScrollableFrame(ctk.CTkScrollableFrame):
    """A local scroll area whose scrollbar is only shown on overflow."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scrollbar_needed = True
        self.bind("<Configure>", self._schedule_scrollbar_update, add="+")
        self._parent_canvas.bind("<Configure>", self._schedule_scrollbar_update, add="+")

    def _schedule_scrollbar_update(self, _event=None):
        self.after_idle(self.update_scrollbar_visibility)

    def update_scrollbar_visibility(self):
        bounds = self._parent_canvas.bbox("all")
        needed = bool(bounds and bounds[3] - bounds[1] > self._parent_canvas.winfo_height() + 1)
        if needed and not self.scrollbar_needed:
            self._scrollbar.grid(row=1, column=1, sticky="nsew")
        elif not needed and self.scrollbar_needed:
            self._scrollbar.grid_remove(); self._parent_canvas.yview_moveto(0)
        self.scrollbar_needed = needed




class MarkerApp(ctk.CTk):
    """Outer shell with the production Image workspace mounted as a child.

    The shell remains the sole owner of destinations.  Image is deliberately
    a hosted module: it can render and process images, but cannot select a
    top-level destination or replace the common host.
    """

    _labels = {
        "image": "Images", "video": "Video", "pdf": "PDF",
        "pptx": "PowerPoint / Slides", "badges": "Badges", "inspect": "Inspect File",
    }

    def __init__(self) -> None:
        super().__init__()
        self._boot = _runtime_boot_logger()
        self._boot('PDF_DIAGNOSTIC ' + json.dumps({'event': 'app_runtime_ready', 'app_id': id(self)}, sort_keys=True))
        self.geometry("1280x720"); self.minsize(980, 680)
        self.shell_controller = ShellController()
        self.active_content_type = self.shell_controller.destination
        self.active_tool = None
        self.mounted_view = ""
        self.image_workspace = None
        self.video_workspace = None
        self.pdf_workspace = None
        self.pptx_workspace = None
        self.pptx_workspace_state = PptxWorkspace(self)
        self._shell_executor = ShellTransitionExecutor()
        self.shell_trace = []
        self.tool_workspace = None
        self.content_buttons: dict[str, ctk.CTkButton] = {}
        self._initialize_image_services()
        self.image_workspace_owner = ImageWorkspace(
            self, self.image_state, scrollable_frame_cls=AutoHideScrollableFrame
        )
        self.video_workspace_owner = VideoWorkspace(self, self.video_state)
        self.pdf_workspace_owner = PdfWorkspace(self, self.pdf_state)
        # One shell-level registry for all peer content workspaces.  Format
        # specific state stays inside the mounted workspace; the shell only
        # resolves and mounts the selected peer.
        self._workspace_registry = {
            "image": self.image_workspace_owner,
            "video": self.video_workspace_owner,
            "pdf": self.pdf_workspace_owner,
            "pptx": self.pptx_workspace_state,
        }
        self._build_shell_ui()
        self.render_shell_state()

    def _build_shell_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(2, weight=1)
        header = ctk.CTkFrame(self, corner_radius=0); header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Nenolink AI Marker", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, padx=20, pady=14, sticky="w")
        self.language_var = ctk.StringVar(value=Translator.language_name(self.translator.language))
        self.language_menu = ctk.CTkOptionMenu(header, values=list(LANGUAGES), variable=self.language_var, command=self.change_image_language, width=150); self.language_menu.grid(row=0, column=1, padx=8)
        self.reset_button = ctk.CTkButton(header, text="Reset", command=self._reset_button_command, width=100); self.reset_button.grid(row=0, column=2, padx=8)
        self.guide_button = ctk.CTkButton(header, text="User Guide (PDF)", command=self.open_image_guide, width=170); self.guide_button.grid(row=0, column=3, padx=(8,20))

        navigation = ctk.CTkFrame(self, corner_radius=0); navigation.grid(row=1, column=0, sticky="ew")
        self._shell_group(navigation, "MEDIA", ("image", "video"), 0)
        self._shell_group(navigation, "DOCUMENTS", ("pdf", "pptx"), 1)
        self._shell_group(navigation, "TOOLS", ("badges", "inspect"), 2)

        self.content_host = ctk.CTkFrame(self); self.content_host.grid(row=2, column=0, padx=16, pady=(8,8), sticky="nsew")
        self.content_host.grid_columnconfigure(0, weight=1); self.content_host.grid_rowconfigure(0, weight=1)
        self.placeholder_label = ctk.CTkLabel(self.content_host, font=ctk.CTkFont(size=28, weight="bold")); self.placeholder_label.grid(row=0, column=0)
        self.status_var = ctk.StringVar()
        self.status_label = ctk.CTkLabel(self, textvariable=self.status_var, text_color="gray60", anchor="e")
        self.status_label.grid(row=3, column=0, padx=20, pady=(0,8), sticky="ew")

    def _shell_group(self, parent, title: str, destinations: tuple[str, ...], column: int) -> None:
        group = ctk.CTkFrame(parent, fg_color="transparent"); group.grid(row=0, column=column, padx=(20 if column == 0 else 8, 8), pady=7, sticky="w")
        ctk.CTkLabel(group, text=title, font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w")
        buttons = ctk.CTkFrame(group, fg_color="transparent"); buttons.grid(row=1, column=0, pady=(1,0), sticky="w")
        for index, destination in enumerate(destinations):
            button = ctk.CTkButton(buttons, text=self._labels[destination], height=28, width=0,
                command=self._shell_button_command(destination))
            button.grid(row=0, column=index, padx=(0 if index == 0 else 4, 0))
            self.content_buttons[destination] = button

    def _shell_button_command(self, destination: str):
        """Command seam used by every constructed content/tool button."""
        return lambda: self.dispatch_shell_event(destination)

    def _reset_button_command(self):
        return self.reset_shell()

    def dispatch_shell_event(self, event: str) -> None:
        if event == "pptx": self.shell_trace.append("PPTX_BUTTON")
        if event in {"image", "video", "pdf", "pptx"}:
            if event == "pptx": self.shell_trace.append("PPTX_TRANSITION")
            self.request_content_transition(event)
            return
        source = self.shell_controller.active_content_type
        if event in {"badges", "inspect"} or event == "back":
            spec = shell_transition_spec(source, self.shell_controller.active_tool, event, self._format_has_active_work(source))
            self.last_shell_spec = spec
            try:
                self._shell_executor.execute(spec, _ShellRuntimeAdapter(self))
            except RuntimeError:
                return
            # Tool transitions must remount the requested overlay.  The
            # underlying content is preserved by the executor; only the tool
            # view is replaced.
            self.render_shell_state(remount=True)
            return
        # All global shell events, including reset, use the same table-driven
        # executor.  No legacy MarkerApp runtime field is consulted or cleared
        # here; workspace lifecycle methods own those values.
        if event == "reset":
            self.reset_shell()
            return
        spec = shell_transition_spec(source, self.shell_controller.active_tool, event, self._format_has_active_work(source))
        self.last_shell_spec = spec
        try:
            self._shell_executor.execute(spec, _ShellRuntimeAdapter(self))
        except RuntimeError:
            return
        self.render_shell_state(remount=False)

    def request_content_transition(self, destination: str) -> bool:
        """Apply the single external content transition algorithm."""
        if destination not in self._workspace_registry:
            raise ValueError(f"Unknown content destination: {destination}")
        source = self.shell_controller.active_content_type
        active = self._format_has_active_work(source)
        self.last_shell_spec = shell_transition_spec(source, self.shell_controller.active_tool, destination, active)
        # A tool is an overlay, not a content state. Returning to the
        # underlying destination must close only the overlay and restore the
        # existing workspace without warning, clearing or remounting it.
        if self.shell_controller.active_tool is not None and destination == source:
            spec = shell_transition_spec(source, self.shell_controller.active_tool, "back", False)
            self.last_shell_spec = spec
            self._shell_executor.execute(spec, _ShellRuntimeAdapter(self))
            self.render_shell_state()
            return True
        if destination == source and self.shell_controller.active_tool is None:
            self.render_shell_state()
            return True
        if active and not self._confirm_format_switch(source, destination):
            self.last_shell_spec = shell_transition_spec(source, self.shell_controller.active_tool, destination, True, "cancel")
            return False
        spec = shell_transition_spec(source, self.shell_controller.active_tool, destination, active, "continue" if active else None)
        self.last_shell_spec = spec
        try:
            self._shell_executor.execute(spec, _ShellRuntimeAdapter(self))
        except RuntimeError:
            return False
        self.render_shell_state(remount=False)
        return True

    def _confirm_format_switch(self, source: str, destination: str) -> bool:
        return messagebox.askokcancel(
            self.translator.text("navigation.switch_title"),
            self.translator.text("navigation.switch_message"),
        )

    def _clear_workspace_runtime(self, format_type: str) -> None:
        workspace = self._workspace_registry[format_type]
        workspace.clear_runtime_state()
        workspace.unmount()

    def reset_shell(self) -> None:
        source = self.shell_controller.active_content_type
        active = any(self._format_has_active_work(content) for content in DESTINATIONS)
        self.last_shell_spec = shell_transition_spec(source, self.shell_controller.active_tool, "reset", active)
        if active:
            workspace = getattr(self, "pptx_workspace_state", None) if source == "pptx" else None
            if not messagebox.askokcancel(
                self.translator.text("navigation.switch_title"),
                self.translator.text("navigation.switch_message"),
            ):
                if workspace is not None:
                    workspace.receipts.record({"layer": "pptx", "event": "GLOBAL_RESET_WARNING_SHOWN", "result": "cancel"})
                self.last_shell_spec = shell_transition_spec(source, self.shell_controller.active_tool, "reset", True, "cancel")
                return
            if workspace is not None:
                workspace.receipts.record({"layer": "pptx", "event": "GLOBAL_RESET_WARNING_SHOWN", "result": "continue"})
        spec = shell_transition_spec(source, self.shell_controller.active_tool, "reset", active, "continue" if active else None)
        self.last_shell_spec = spec
        try:
            self._shell_executor.execute(spec, _ShellRuntimeAdapter(self))
        except RuntimeError:
            return
        self.render_shell_state(remount=False)
        workspace=getattr(self,"pptx_workspace_state",None)
        if workspace is not None:
            workspace.receipts.record({"layer":"pptx","event":"GLOBAL_RESET_PPTX_CLEARED","result":"ok"})

    def _format_has_active_work(self, format_type: str) -> bool:
        if format_type == "image": return self.image_workspace_owner.has_active_work()
        if format_type == "video": return self.video_workspace_owner.has_active_work()
        if format_type == "pdf":
            workspace = getattr(self, "pdf_workspace_owner", None)
            return workspace.has_active_work() if workspace is not None else self.pdf_path is not None
        if format_type == "pptx":
            workspace = getattr(self, "pptx_workspace_state", None)
            if workspace is not None:
                return workspace.has_active_work()
            return False
        return False

    def render_shell_state(self, remount: bool = True) -> None:
        self._pdf_runtime_diagnostic("render_shell_state", {
            "active_content": getattr(self.__dict__.get("shell_controller"), "active_content_type", None),
            "active_tool": getattr(self.__dict__.get("shell_controller"), "active_tool", None),
            "buttons": {k: {"id": id(v), "selected": k == (getattr(self.__dict__.get("shell_controller"), "active_tool", None) or getattr(self.__dict__.get("shell_controller"), "active_content_type", None)), "mapped": bool(v.winfo_ismapped()) if v.winfo_exists() else False} for k, v in self.__dict__.get("content_buttons", {}).items()},
        })
        destination = self.shell_controller.active_content_type
        tool = self.shell_controller.active_tool
        self.active_content_type = destination
        self.active_tool = tool
        for key, button in self.content_buttons.items():
            selected = key == (tool or destination)
            button.configure(fg_color=("#2474ad", "#1f6aa5") if selected else ("#6b6b6b", "#454545"))
        if tool:
            for workspace in (self.__dict__.get("image_workspace"), self.__dict__.get("video_workspace"), self.__dict__.get("pdf_workspace"), self.__dict__.get("pptx_workspace")):
                if workspace is not None and hasattr(workspace, "winfo_exists") and workspace.winfo_exists(): workspace.grid_remove()
            if remount:
                self._mount_tool(tool)
            self.mounted_view = placeholder_for(tool)
            return
        self._unmount_tool()
        if destination in self._workspace_registry:
            trace = self.__dict__.get("shell_trace")
            if destination == "pptx" and trace is not None: trace.append("PPTX_REGISTRY")
            workspace = self._workspace_registry[destination]
            if remount:
                workspace.mount(self.content_host)
            workspace.project()
            self._project_active_status(destination)
            self.mounted_view = destination.upper()
        else:
            self._clear_content_host()
            self.mounted_view = placeholder_for(destination)
            self.placeholder_label = ctk.CTkLabel(self.content_host, text=self.mounted_view, font=ctk.CTkFont(size=28, weight="bold"))
            self.placeholder_label.grid(row=0, column=0)

    def _pdf_runtime_diagnostic(self, event: str, extra: dict | None = None) -> None:
        """Emit observational PDF widget identity data to the boot log."""
        pdf = self.__dict__.get("pdf_workspace_owner")
        state = getattr(pdf, "state", None)
        widgets = {}
        for name in ("pdf_workspace", "pdf_workspace_root", "pdf_process_button", "pdf_badge_menu", "pdf_badge_visual", "pdf_badge_image_label"):
            widget = self.__dict__.get(name)
            if widget is not None:
                try: widgets[name] = {"id": id(widget), "mapped": bool(widget.winfo_ismapped()), "exists": bool(widget.winfo_exists())}
                except Exception: widgets[name] = {"id": id(widget)}
        controller = self.__dict__.get("shell_controller")
        badge_var = self.__dict__.get("badge_display_var")
        menu = self.__dict__.get("pdf_badge_menu")
        photo = self.__dict__.get("pdf_badge_photo")
        payload = {"event": event, "active_content": getattr(controller, "active_content_type", None), "pdf_owner_id": id(pdf) if pdf else None, "state_badge": repr(getattr(state, "badge", None)), "badge_display": badge_var.get() if badge_var is not None else None, "selector_values": list(getattr(menu, "_values", []) or []) if menu is not None else [], "badge_asset": str(photo) if photo else None, "widgets": widgets}
        if extra: payload.update(extra)
        try: self._boot("PDF_DIAGNOSTIC " + json.dumps(payload, default=str, sort_keys=True))
        except Exception: pass

    def _project_active_status(self, destination: str) -> None:
        """Single shell-owned status projection sink.

        Workspace status is derived from its authoritative state after every
        lifecycle projection.  ``status_var`` is deliberately write-only UI
        output; no transition or workspace decision reads it.
        """
        workspace = self._workspace_registry.get(destination)
        state = getattr(workspace, "state", None)
        path = getattr(state, "path", None)
        files = getattr(state, "selected_files", ())
        if path is not None:
            text = f"{getattr(path, 'name', path)}"
        elif files:
            text = f"{getattr(files[0], 'name', files[0])}"
        else:
            text = ""
        status_var = self.__dict__.get("status_var")
        if status_var is not None:
            status_var.set(text)

    # --- Image module lifecycle -------------------------------------------------

    def _initialize_image_services(self) -> None:
        self.config_store = ConfigStore()
        saved = self.config_store.load()
        self._saved_settings = saved
        self.processor = ImageProcessor()
        self.preview_renderer = ImagePreviewRenderer(self.processor)
        # Clean v1.0.3 sessions start in English; locale changes are explicit
        # global events and are projected without rebuilding workspaces.
        self.translator = Translator(locale_directory(), "en")
        self.badge_sources = BadgeSourceManager(badge_directory())
        self.badges = self.badge_sources.repository(saved.badge_source, saved.custom_badge_folder)
        self.sources: list[Path] = []
        # Compatibility projection for legacy consumers; workspace state remains authoritative.
        self.media_sources = {"image": [], "video": []}
        self.image_state = ImageWorkspaceState()
        self.video_state = VideoWorkspaceState()
        self.pdf_state = PdfWorkspaceState()
        self.preview_photo = self.preview_image = self.badge_photo = self.single_badge_photo = None
        self.welcome_photo = self.welcome_image = None
        self.badge_display_to_file = {}
        self.badge_var = ctk.StringVar(value=saved.badge_name); self.badge_display_var = ctk.StringVar()
        self.badge_enabled_var = ctk.BooleanVar(value=True)
        self.badge_name_var = ctk.StringVar(); self.badge_description_var = ctk.StringVar()
        self.position_var = ctk.StringVar(value=saved.position); self.position_display_var = ctk.StringVar()
        self.size_var = ctk.IntVar(value=saved.size_percent); self.margin_var = ctk.IntVar(value=saved.margin); self.opacity_var = ctk.IntVar(value=saved.opacity)
        self.logo_enabled_var = ctk.BooleanVar(value=saved.logo_enabled); self.logo_path_var = ctk.StringVar(value=saved.logo_path)
        self.logo_filename_var = ctk.StringVar(value=Path(saved.logo_path).name if saved.logo_path else "—")
        self.logo_position_var = ctk.StringVar(value=saved.logo_position); self.logo_position_display_var = ctk.StringVar()
        self.logo_size_var = ctk.IntVar(value=saved.logo_size_percent); self.logo_margin_var = ctk.IntVar(value=saved.logo_margin); self.logo_opacity_var = ctk.IntVar(value=saved.logo_opacity)
        self.position_display_to_value = {"Top left": "top-left", "Top right": "top-right", "Bottom left": "bottom-left", "Bottom right": "bottom-right", "Center": "center"}
        self.position_display_var.set(next((k for k,v in self.position_display_to_value.items() if v == self.position_var.get()), "Bottom right"))
        self.badge_source_var = ctk.StringVar(value=saved.badge_source); self.custom_badge_var = ctk.StringVar(value=saved.custom_badge_folder)
        self.pdf_path = None; self.pdf_info = None; self.pdf_processor = PdfProcessor(); self.pdf_preview_renderer = PdfPreviewRenderer(self.processor); self.pdf_current_page = 0; self.pdf_preview_photo = None
        self.pdf_scope_mode = "all"; self.pdf_active_scope: tuple[int, ...] = (); self.pdf_scope_input = ""
        self.pdf_badge_enabled_var = ctk.BooleanVar(value=True)
        self.pptx_path = None; self.pptx_metrics = None; self.pptx_processor = PptxProcessor(); self.pptx_preview_renderer = PptxPreviewRenderer(self.processor); self.pptx_current_slide = 0; self.pptx_preview_photo = None
        self.pptx_scope_mode = "all"; self.pptx_active_scope: tuple[int, ...] = (); self.pptx_scope_input = ""
        self.pptx_state = PptxWorkspaceState()
        # PPTX visual settings are independent from the media/PDF controls.
        self.pptx_badge_position_var=ctk.StringVar(value=saved.position); self.pptx_badge_size_var=ctk.IntVar(value=saved.size_percent); self.pptx_badge_margin_var=ctk.IntVar(value=saved.margin); self.pptx_badge_opacity_var=ctk.IntVar(value=saved.opacity)
        self.pptx_logo_position_var=ctk.StringVar(value=saved.logo_position); self.pptx_logo_size_var=ctk.IntVar(value=saved.logo_size_percent); self.pptx_logo_margin_var=ctk.IntVar(value=saved.logo_margin); self.pptx_logo_opacity_var=ctk.IntVar(value=saved.logo_opacity)

    def _clear_content_host(self) -> None:
        for child in self.content_host.winfo_children():
            child.destroy()
        self.image_workspace = self.video_workspace = self.pdf_workspace = self.pptx_workspace = self.tool_workspace = None

    def _mount_pdf_workspace(self) -> None:
        """Temporary shell entry adapter for the PDF workspace boundary."""
        self.pdf_workspace_owner.mount(self.content_host)

    def _clear_pdf_runtime_compat(self) -> None:
        """B1 compatibility cleanup; removed once PDF state owns file events."""
        self.pdf_path = self.pdf_info = None
        self.pdf_current_page = 0
        self.pdf_preview_photo = None
        self.pdf_scope_mode = "all"
        self.pdf_active_scope = ()
        self.pdf_scope_input = ""

    def _mount_pptx_workspace(self) -> None:
        """Mount the single minimal authoritative PPTX workspace."""
        self.pptx_workspace_state.mount(self.content_host)
        self.pptx_workspace = self.pptx_workspace_state.root
        if not self.pptx_workspace_state.mounted or self.pptx_workspace is None:
            raise RuntimeError("PPTX workspace failed to mount")

    def pptx_visual_changed(self, *_args) -> None:
        self._sync_pptx_visual_state()
        if getattr(self, "pptx_badge_menu", None): self.pptx_badge_menu.configure(state="normal" if self.pptx_badge_enabled_var.get() else "disabled")
        self.pptx_workspace_state.project(); self._save()

    def _project_pptx_badge_visual(self) -> None:
        """Project the common selected badge into the PPTX controls."""
        badge_id = self.pptx_state.badge.badge_id or self.badge_var.get()
        badge = self.badges.find(badge_id) if badge_id else None
        if not badge:
            self.pptx_badge_photo = None
            if getattr(self, "pptx_badge_name_label", None): self.pptx_badge_name_label.configure(image=None, text="")
            return
        with Image.open(badge) as opened: image = opened.convert("RGBA")
        image.thumbnail((WORKSPACE_LAYOUT.badge_thumbnail_width, WORKSPACE_LAYOUT.badge_thumbnail_height), Image.Resampling.LANCZOS)
        self.pptx_badge_photo = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
        display_name = self.badges.display_name(badge.name)
        self.badge_name_var.set(display_name); self.pptx_state.badge.badge_id = badge.name
        self.badge_display_var.set(display_name)
        if getattr(self, "pptx_badge_name_label", None): self.pptx_badge_name_label.configure(image=self.pptx_badge_photo, text=display_name)

    def _sync_pptx_visual_state(self) -> None:
        if not hasattr(self, "pptx_state"): return
        self.pptx_workspace_state.state_token_reached = True
        events = ((PptxEvent.BADGE_ENABLE, self.pptx_badge_enabled_var.get()), (PptxEvent.BADGE_SELECT, self.badge_var.get()), (PptxEvent.BADGE_POSITION, self.pptx_badge_position_var.get()), (PptxEvent.BADGE_SIZE, self.pptx_badge_size_var.get()), (PptxEvent.BADGE_MARGIN, self.pptx_badge_margin_var.get()), (PptxEvent.BADGE_OPACITY, self.pptx_badge_opacity_var.get()), (PptxEvent.LOGO_ENABLE, self.logo_enabled_var.get()), (PptxEvent.LOGO_CHOOSE, self._logo_path()), (PptxEvent.LOGO_POSITION, self.pptx_logo_position_var.get()), (PptxEvent.LOGO_SIZE, self.pptx_logo_size_var.get()), (PptxEvent.LOGO_MARGIN, self.pptx_logo_margin_var.get()), (PptxEvent.LOGO_OPACITY, self.pptx_logo_opacity_var.get()))
        for event, value in events:
            apply_pptx_visual_event(self.pptx_state, event, value)

    def _pptx_visual_projection_settings(self):
        """Build renderer/output settings from authoritative PPTX state."""
        self._sync_pptx_visual_state()
        return replace(self.settings(), position=self.pptx_state.badge.position,
                       size_percent=self.pptx_state.badge.size,
                       margin=self.pptx_state.badge.margin,
                       opacity=self.pptx_state.badge.opacity,
                       logo_enabled=self.pptx_state.logo.enabled,
                       logo_path=str(self.pptx_state.logo.path or ""),
                       logo_position=self.pptx_state.logo.position,
                       logo_size_percent=self.pptx_state.logo.size,
                       logo_margin=self.pptx_state.logo.margin,
                       logo_opacity=self.pptx_state.logo.opacity)



        # Scope and visuals come only from the supplied workspace state.




    def _confirm_pdf_signature(self) -> bool:
        """Confirm the non-fatal signature warning before future PDF writes."""
        if not self.pdf_info or not getattr(self.pdf_info, "signed", False):
            return True
        return messagebox.askokcancel(
            self.translator.text("pdf.signature_title"),
            self.translator.text("pdf.signature_warning"),
        )

    def _confirm_pdf_limits_phase6(self) -> bool:
        if not self.pdf_info:
            return False
        assessment = assess_document("pdf", self.pdf_info.metrics)
        if assessment.blocked:
            messagebox.showerror(self.translator.text("document.limit_title"), self.translator.text("document.pdf_hard")); return False
        if assessment.requires_warning:
            return messagebox.askokcancel(self.translator.text("document.warning_title"), self.translator.text("document.pdf_warning"))
        return True

    def _mount_image_workspace(self) -> None:
        """Temporary shell entry adapter; ImageWorkspace owns lifecycle."""
        if getattr(self, "image_workspace_owner", None) is None:
            self.image_workspace_owner = ImageWorkspace(
                self, self.image_state, scrollable_frame_cls=AutoHideScrollableFrame
            )
        self.image_workspace_owner.mount(self.content_host)

    def _mount_video_workspace(self) -> None:
        """Temporary registry entry adapter; VideoWorkspace owns the view."""
        self.video_workspace_owner.mount(self.content_host)


    def _video_slider(self, parent, variable, start, end, row, label, command=None):
        output = ctk.CTkLabel(parent, text=label, width=PARAM_LABEL_WIDTH); output.grid(row=row, column=0, padx=8, pady=(4, 0), sticky="w")
        ctk.CTkSlider(parent, from_=start, to=end, number_of_steps=end-start, width=PARAM_CONTROL_WIDTH, variable=variable, command=command or self.video_workspace_owner.change_visual).grid(row=row+1, column=0, padx=8, pady=(1, 3), sticky="ew")
        return output

    def _mount_tool(self, tool: str) -> None:
        mounted_tool = getattr(self, "_mounted_tool_name", None)
        if self.tool_workspace is not None and self.tool_workspace.winfo_exists():
            if mounted_tool == tool:
                self.tool_workspace.grid()
                return
            self._unmount_tool()
        self.tool_workspace = ctk.CTkFrame(self.content_host); self.tool_workspace.grid(row=0, column=0, sticky="nsew"); self.tool_workspace.grid_columnconfigure(0, weight=1); self.tool_workspace.grid_rowconfigure(1, weight=1)
        ctk.CTkButton(self.tool_workspace, text=self.translator.text("button.back"), command=lambda: self.dispatch_shell_event("back"), width=110).grid(row=0, column=0, padx=16, pady=(10, 4), sticky="w")
        if tool == "badges": self._build_badges_tool()
        else: self._build_inspect_tool()
        self._mounted_tool_name = tool

    def _unmount_tool(self) -> None:
        if self.tool_workspace is not None and self.tool_workspace.winfo_exists(): self.tool_workspace.destroy()
        self.tool_workspace = None
        self._mounted_tool_name = None

    def _unmount_image_workspace(self) -> None:
        self.image_workspace_owner.clear_runtime_state()
        self.image_workspace_owner.unmount()
        self.sources = []
        self.image_state.preview_image = None
        self.preview_renderer.clear(); self.preview_photo = self.preview_image = None

    def _update_video_duration_visibility(self) -> None:
        if not getattr(self, "video_duration_entry", None): return
        visible = self.video_mode_var.get() in {"beginning", "end"}
        (self.video_duration_label.grid if visible else self.video_duration_label.grid_remove)(); (self.video_duration_entry.grid if visible else self.video_duration_entry.grid_remove)()

    def _build_badges_tool(self) -> None:
        panel = ctk.CTkFrame(self.tool_workspace); panel.grid(row=1, column=0, padx=16, pady=6, sticky="nsew"); panel.grid_columnconfigure(0, weight=1); panel.grid_rowconfigure(4, weight=1)
        ctk.CTkLabel(panel, text=self.translator.text("badge.source_label"), font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")
        self.tool_badge_source_var = ctk.StringVar(value=self.badge_source_var.get()); ctk.CTkRadioButton(panel, text=self.translator.text("badge.source_standard"), variable=self.tool_badge_source_var, value="standard", command=self._tool_refresh_badges).grid(row=1, column=0, padx=16, pady=2, sticky="w"); ctk.CTkRadioButton(panel, text=self.translator.text("badge.source_custom"), variable=self.tool_badge_source_var, value="custom", command=self._tool_refresh_badges).grid(row=2, column=0, padx=16, pady=2, sticky="w")
        row = ctk.CTkFrame(panel, fg_color="transparent"); row.grid(row=3, column=0, padx=16, pady=4, sticky="ew"); row.grid_columnconfigure(0, weight=1); self.tool_badge_folder_var = ctk.StringVar(value=self.custom_badge_var.get()); ctk.CTkEntry(row, textvariable=self.tool_badge_folder_var).grid(row=0, column=0, sticky="ew"); ctk.CTkButton(row, text=self.translator.text("button.choose_badge_folder"), command=self._tool_choose_badge_folder, width=170).grid(row=0, column=1, padx=6); ctk.CTkButton(row, text=self.translator.text("badge.refresh"), command=self._tool_refresh_badges, width=100).grid(row=0, column=2)
        self.tool_badge_gallery = ctk.CTkScrollableFrame(panel); self.tool_badge_gallery.grid(row=4, column=0, padx=16, pady=6, sticky="nsew"); self._tool_refresh_badges()

    def _tool_choose_badge_folder(self) -> None:
        value = filedialog.askdirectory(title=self.translator.text("dialog.custom_badges"));
        if value: self.tool_badge_folder_var.set(value); self.tool_badge_source_var.set("custom"); self._tool_refresh_badges()

    def _tool_refresh_badges(self) -> None:
        if not getattr(self, "tool_badge_gallery", None): return
        self.badge_source_var.set(self.tool_badge_source_var.get()); self.custom_badge_var.set(self.tool_badge_folder_var.get())
        if self.tool_badge_source_var.get() == "standard":
            self.badges = self.badge_sources.standard_repository()
            names = [path.name for path in self.badges.display_badges()]
            displays = [self.badges.display_name(name) for name in names]
            self.badge_display_to_file = dict(zip(displays, names))
            self.badge_var.set(choose_badge_selection("standard", names, self.badge_var.get()))
            self.badge_display_var.set(self.badges.display_name(self.badge_var.get()))
        else:
            self.image_workspace_owner.project()
        for child in self.tool_badge_gallery.winfo_children(): child.destroy()
        self.tool_badge_photos = []
        for index, path in enumerate(self.badges.display_badges()):
            card = ctk.CTkFrame(self.tool_badge_gallery, fg_color="transparent", border_width=1)
            card.grid(row=index // 4, column=index % 4, padx=5, pady=5, sticky="nsew")
            try:
                with Image.open(path) as opened:
                    image = opened.convert("RGBA")
                image.thumbnail((150, 72), Image.Resampling.LANCZOS)
                photo = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
                self.tool_badge_photos.append(photo)
                graphic = ctk.CTkLabel(card, image=photo, text="")
                graphic.pack(padx=6, pady=(6, 2))
            except (OSError, ValueError):
                graphic = ctk.CTkLabel(card, text=self.badges.display_name(path.name))
                graphic.pack(padx=6, pady=(6, 2))
            name_label = ctk.CTkLabel(card, text=self.badges.display_name(path.name), anchor="center")
            name_label.pack(padx=6, pady=(0, 6))
            select = lambda _event=None, name=path.name: self._tool_select_badge(name)
            for widget in (card, graphic, name_label):
                widget.bind("<Button-1>", select, add="+")

    def _tool_select_badge(self, name: str) -> None:
        self.badge_var.set(name)
        self.badge_display_var.set(self.badges.display_name(name))
        self.image_workspace_owner.badge_changed()
        self._tool_refresh_badges()

    def _build_inspect_tool(self) -> None:
        panel = ctk.CTkFrame(self.tool_workspace); panel.grid(row=1, column=0, padx=16, pady=6, sticky="nsew"); panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text=self.translator.text("inspect.title"), font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")
        ctk.CTkButton(panel, text=self.translator.text("inspect.choose"), command=self._tool_choose_inspection).grid(row=1, column=0, padx=12, pady=6, sticky="w")
        self.tool_inspect_result = ctk.CTkLabel(panel, text=self.translator.text("inspect.none"), justify="left", anchor="w"); self.tool_inspect_result.grid(row=2, column=0, padx=12, pady=8, sticky="ew")

    def _tool_choose_inspection(self) -> None:
        selected = filedialog.askopenfilename(title=self.translator.text("inspect.choose"), filetypes=[(self.translator.text("files.all"), "*.*")]);
        if not selected: return
        path = Path(selected)
        if path.suffix.lower() in {".pdf", ".pptx"}:
            self.tool_inspect_result.configure(text=self.translator.text("inspect.document_unsupported")); return
        try:
            result = inspect_file(path); label = result.ai_label or self.translator.text("inspect.not_available"); self.tool_inspect_result.configure(text=f"{path.name}\n{self.translator.text('inspect.status')} {self.translator.text('inspect.found') if result.found else self.translator.text('inspect.not_found')}\n{self.translator.text('inspect.ai_label')} {label}")
        except (OSError, ValueError) as error: self.tool_inspect_result.configure(text=self.translator.text("inspect.error_message", reason=error))

    # --- Image module -----------------------------------------------------------







    def change_image_language(self, name: str) -> None:
        # One application-wide locale owner; changing locale is not a content
        # transition and must not rebuild the active workspace.
        self.translator.set_language(LANGUAGES.get(name, "en"))
        if getattr(self, "image_workspace_owner", None) is not None:
            self.image_workspace_owner.apply_translations()
        t = self.translator.text
        for kind, key in (("image", "content.images"), ("video", "content.video"), ("pdf", "content.pdf"), ("pptx", "content.powerpoint")):
            button = getattr(self, "content_buttons", {}).get(kind)
            if button is not None: button.configure(text=t(key))
        if getattr(self, "reset_button", None) is not None: self.reset_button.configure(text=t("button.reset"))
        if getattr(self, "guide_button", None) is not None: self.guide_button.configure(text=t("button.user_guide"))
        workspace = getattr(self, "pptx_workspace_state", None)
        if self.active_content_type == "pptx" and workspace is not None:
            workspace.apply_language(self.translator)
        self._save()

    def open_image_guide(self) -> None:
        try: open_user_guide(localized_user_guide_path(self.translator.language))
        except (OSError, FileNotFoundError) as error: messagebox.showerror(self.translator.text("error.title"), self.translator.text("guide.missing", error=error))






    def _logo_path(self) -> Path | None:
        path = Path(self.logo_path_var.get()).expanduser() if self.logo_path_var.get() else None
        return path if path and path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS else None

    def _validate_saved_logo(self) -> None:
        """Validate persisted logo settings without owning workspace UI."""
        if self.logo_enabled_var.get() and not self._logo_path():
            self.logo_enabled_var.set(False); self.status_var.set(self.translator.text("logo.missing")); self._save()



    def settings(self) -> MarkerSettings:
        return replace(self._saved_settings, badge_name=self.badge_var.get(), position=self.position_var.get(), size_percent=self.size_var.get(), margin=self.margin_var.get(), opacity=self.opacity_var.get(), language=self.translator.language, badge_source=self.badge_source_var.get(), custom_badge_folder=self.custom_badge_var.get(), logo_enabled=self.logo_enabled_var.get(), logo_path=self.logo_path_var.get(), logo_position=self.logo_position_var.get(), logo_size_percent=self.logo_size_var.get(), logo_margin=self.logo_margin_var.get(), logo_opacity=self.logo_opacity_var.get()).validated()

    def _save(self) -> None:
        try:
            self._saved_settings = self.settings(); self.config_store.save(self._saved_settings)
        except OSError: pass

    def _save_image_settings(self) -> None:
        """Persist shared preferences without letting Video own shell state."""
        self._save()


def run():
    ctk.set_appearance_mode("system"); ctk.set_default_color_theme("blue"); MarkerApp().mainloop()
