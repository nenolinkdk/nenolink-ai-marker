"""Video preview ownership boundary."""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from PIL import Image
import customtkinter as ctk

from .batch import extract_video_frame, find_ffmpeg
from .models import MarkerSettings
from .metadata import marker_metadata
from .workspace_state import VideoEvent, apply_video_event
from .save_control import SaveControl
from .badge_control import BadgeControl, BadgeProjection
from .source_control import SourceControl
from .logo_control import LogoControl, LogoProjection
from .preview_shell import PreviewShell


@dataclass(frozen=True, slots=True)
class VideoProcessingRequest:
    source: Path
    destination: Path
    badge: Path | None
    logo: Path | None
    settings: MarkerSettings


class VideoWorkspace:
    def __init__(self, app, state):
        self.app = app
        self.state = state
        self.preview_photo = None
        self.root = None
        self.presentation_generation = 0

    def _dispose_view(self):
        root = self.root
        if root is not None:
            try:
                if root.winfo_exists():
                    root.destroy()
            except Exception:
                pass
        self.root = None
        self.badge_control = None
        self.source_control = None
        self.logo_controls = None
        self.logo_control = None
        self.preview_photo = None
        for name in ("video_workspace", "video_file_label", "video_preview_label", "video_badge_enable", "video_badge_menu", "video_badge_var", "video_badge_preview_label", "video_badge_name_label", "video_process_button", "video_save_control"):
            if hasattr(self.app, name):
                setattr(self.app, name, None)

    def mount(self, host):
        self._dispose_view()
        self.root = ctk.CTkFrame(host, fg_color="transparent"); self.root.grid(row=0, column=0, sticky="nsew")
        self.presentation_generation += 1
        self.root.grid_columnconfigure(0, weight=0, minsize=320); self.root.grid_columnconfigure(1, weight=1); self.root.grid_rowconfigure(0, weight=1)
        self._build_ui(self.root)

    def unmount(self):
        self._dispose_view()

    def project(self):
        if self.root is not None and self.root.winfo_exists():
            self._project_controls()
            loaded = self.state.path is not None
            self.app.video_sources = [self.state.path] if loaded else []
            self.app.media_sources["video"] = list(self.app.video_sources)
            self.app.video_file_label.configure(text=self.state.path.name if loaded else self.app.translator.text("files.none"))
            if getattr(self, "source_control", None) is not None:
                self.source_control.project(filename=(self.state.path.name if loaded else ""), empty_text=self.app.translator.text("files.none"))
            if loaded:
                self.refresh_preview()
            else:
                self.app.video_preview_label.configure(image=None, text="Video preview")
                self.preview_photo = None; self.app.video_preview_photo = None

    def _project_controls(self):
        app = self.app
        app.video_mode_var.set(self.state.mode)
        app.video_duration_var.set(max(1, int(self.state.duration)))
        app.video_badge_var.set(app.badges.display_name(self.state.badge.badge_id))
        app.video_position_var.set(self.state.badge.position)
        app.video_size_var.set(self.state.badge.size); app.video_margin_var.set(self.state.badge.margin); app.video_opacity_var.set(self.state.badge.opacity)
        names = [path.name for path in app.badges.display_badges()]
        displays = [app.badges.display_name(name) for name in names]
        badge = self._badge_path()
        self.badge_control.project(BadgeProjection(bool(self.state.badge.enabled), app.badges.display_name(self.state.badge.badge_id), tuple(displays), badge, self.state.badge.position, self.state.badge.size, self.state.badge.margin, self.state.badge.opacity, app.translator.text("pdf.add_badge")))
        if getattr(self, "logo_enabled_var", None) is not None:
            self.logo_enabled_var.set(self.state.logo.enabled)
            self.logo_mode_var.set(self.state.logo.mode)
            self.logo_size_var.set(self.state.logo.size); self.logo_margin_var.set(self.state.logo.margin); self.logo_opacity_var.set(self.state.logo.opacity)
            self.logo_file_label.configure(text=self.state.logo.path.name if self.state.logo.path else "No logo selected")
            if getattr(self, "logo_control", None):
                self.logo_control.project(LogoProjection(enabled=self.state.logo.enabled, filename=self.state.logo.path.name if self.state.logo.path else "", mode=self.state.logo.mode, modes=("Front", "Entire", "Back"), size=self.state.logo.size, margin=self.state.logo.margin, opacity=self.state.logo.opacity))

    def _badge_path(self):
        return next((path for path in self.app.badges.display_badges() if path.name == self.state.badge.badge_id), None)

    def has_active_work(self):
        return self.state.path is not None

    def clear_runtime_state(self):
        self.state.clear_runtime_state(); self.preview_photo = None

    def dispatch(self, event, payload=None):
        return apply_video_event(self.state, event, payload)

    def enter_clean(self):
        return self.dispatch(VideoEvent.CLEAR_RUNTIME)

    def choose_video(self):
        from tkinter import filedialog
        selected = filedialog.askopenfilename(title=self.app.translator.text("dialog.open_media"), filetypes=[(self.app.translator.text("files.supported_videos"), "*.mp4 *.mov *.mkv *.avi *.webm"), (self.app.translator.text("files.all"), "*.*")])
        if selected:
            path = Path(selected); apply_video_event(self.state, VideoEvent.FILE_SELECTED, {"path": path})
            self.project()

    def change_mode(self, label):
        apply_video_event(self.state, VideoEvent.MODE_CHANGED, {"mode": self.app.video_mode_display_to_value[label]})
        self.project(); self.app._update_video_duration_visibility(); self.app._save_image_settings()

    def change_duration(self, value=None):
        try: value = int(self.app.video_duration_var.get() if value is None else value)
        except (TypeError, ValueError): value = self.state.duration
        apply_video_event(self.state, VideoEvent.DURATION_CHANGED, {"duration": value})
        self.project(); self.app._update_video_duration_visibility(); self.app._save_image_settings()

    def change_badge(self, label):
        apply_video_event(self.state, VideoEvent.BADGE_CHANGED, {"badge_id": self.app.badge_display_to_file.get(label, label)})
        self.project(); self.refresh_preview(); self.app._save_image_settings()

    def change_visual(self, enabled=None, *_args):
        apply_video_event(self.state, VideoEvent.VISUAL_CHANGED, {
            "enabled": bool(self.state.badge.enabled) if enabled is None else bool(enabled), "position": self.app.video_position_display_to_value.get(self.app.video_position_display_var.get(), self.app.video_position_display_var.get()), "size": int(self.app.video_size_var.get()),
            "margin": int(self.app.video_margin_var.get()), "opacity": int(self.app.video_opacity_var.get()),
        })
        self.project(); self.refresh_preview(); self.app._save_image_settings()

    def choose_logo(self):
        from tkinter import filedialog
        selected = filedialog.askopenfilename(title="Choose logo", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")])
        if selected:
            apply_video_event(self.state, VideoEvent.LOGO_FILE_CHANGED, {"path": selected, "enabled": True})
            self.project(); self.refresh_preview()

    def change_logo(self, *_args):
        apply_video_event(self.state, VideoEvent.LOGO_ENABLED_CHANGED, {"enabled": bool(self.logo_enabled_var.get())})
        apply_video_event(self.state, VideoEvent.LOGO_SIZE_CHANGED, {"size": int(self.logo_size_var.get())})
        apply_video_event(self.state, VideoEvent.LOGO_MARGIN_CHANGED, {"margin": int(self.logo_margin_var.get())})
        apply_video_event(self.state, VideoEvent.LOGO_OPACITY_CHANGED, {"opacity": int(self.logo_opacity_var.get())})
        self.project(); self.refresh_preview()

    def change_logo_mode(self, mode):
        apply_video_event(self.state, VideoEvent.LOGO_MODE_CHANGED, {"mode": mode.lower()})
        self.project(); self.refresh_preview()

    def _build_ui(self, workspace):
        self.badge_control = BadgeControl(workspace, on_enabled_changed=self.change_visual, on_badge_selected=self.change_badge)
        app = self.app
        left = app.AutoHideScrollableFrame(workspace, width=320, fg_color=("gray86", "gray17")) if hasattr(app, "AutoHideScrollableFrame") else ctk.CTkScrollableFrame(workspace, width=320, fg_color=("gray86", "gray17"))
        app.video_controls_host = left; left.grid(row=0, column=0, padx=(4, 8), pady=4, sticky="nsew"); left.grid_columnconfigure(0, weight=1)
        self.preview_shell = PreviewShell(workspace); self.preview_shell.frame.grid(row=0, column=1, padx=(8, 4), pady=4, sticky="nsew"); right = self.preview_shell.viewport; app.video_preview_host = right
        def heading(text, row): ctk.CTkLabel(left, text=text, font=ctk.CTkFont(weight="bold")).grid(row=row, column=0, padx=14, pady=(8, 2), sticky="w")
        heading("FILE", 0); self.source_control = SourceControl(left, choose_command=self.choose_video, choose_label="Choose Video", width=280); self.source_control.frame.grid(row=1, column=0, padx=14, pady=2, sticky="ew"); app.video_open_button = self.source_control.choose_button; app.video_file_label = self.source_control.filename_label
        heading("AI BADGE", 2)
        app.video_badge_group = ctk.CTkFrame(left, fg_color="transparent"); app.video_badge_group.grid(row=3, column=0, padx=14, pady=2, sticky="ew"); app.video_badge_group.grid_columnconfigure(0, weight=1)
        self.badge_control.frame.grid(row=0, column=0, sticky="ew")
        app.video_badge_enable = self.badge_control.enabled_widget; app.video_badge_menu = self.badge_control.selector_widget; app.video_badge_var = self.badge_control.selector_var; app.video_badge_preview_label = self.badge_control.graphic_widget; app.video_badge_name_label = self.badge_control.graphic_widget
        app.video_position_var = ctk.StringVar(value="bottom-right"); app.video_position_display_var = ctk.StringVar(value="Bottom right"); app.video_position_display_to_value = {"Top left":"top-left", "Top right":"top-right", "Bottom left":"bottom-left", "Bottom right":"bottom-right", "Center":"center"}
        app.video_position_label = ctk.CTkLabel(app.video_badge_group, text="Badge Position"); app.video_position_label.grid(row=1, column=0, padx=8, pady=1, sticky="w"); app.video_position_menu = ctk.CTkOptionMenu(app.video_badge_group, variable=app.video_position_display_var, values=list(app.video_position_display_to_value), command=lambda _label: self.change_visual()); app.video_position_menu.grid(row=2, column=0, padx=8, pady=2, sticky="ew")
        app.video_size_var = ctk.IntVar(value=20); app.video_margin_var = ctk.IntVar(value=20); app.video_opacity_var = ctk.IntVar(value=100)
        app.video_size_label = app._video_slider(app.video_badge_group, app.video_size_var, 1, 100, 3, "Badge Size", self.change_visual); app.video_margin_label = app._video_slider(app.video_badge_group, app.video_margin_var, 0, 250, 5, "Badge Margin", self.change_visual); app.video_opacity_label = app._video_slider(app.video_badge_group, app.video_opacity_var, 0, 100, 7, "Badge Opacity", self.change_visual)
        self.logo_control = LogoControl(left, on_enabled=lambda value: self.change_logo(value), on_choose=self.choose_logo, on_mode=self.change_logo_mode, on_size=lambda value: self.change_logo(), on_margin=lambda value: self.change_logo(), on_opacity=lambda value: self.change_logo())
        self.logo_control.frame.grid(row=4, column=0, padx=14, pady=2, sticky="ew")
        self.logo_enabled_var = self.logo_control.enabled_var; self.logo_mode_var = self.logo_control.mode_var; self.logo_file_label = self.logo_control.filename_label; self.logo_size_var = ctk.IntVar(value=15); self.logo_margin_var = ctk.IntVar(value=20); self.logo_opacity_var = ctk.IntVar(value=100)
        heading("VIDEO OPTIONS", 5); app.video_mode_var = ctk.StringVar(value="permanent"); app.video_mode_display_var = ctk.StringVar(); app.video_mode_display_to_value = {"Permanent":"permanent", "Beginning":"beginning", "End":"end"}
        app.video_mode_label = ctk.CTkLabel(left, text="Video badge mode"); app.video_mode_label.grid(row=6, column=0, padx=14, pady=1, sticky="w"); app.video_mode_menu = ctk.CTkOptionMenu(left, variable=app.video_mode_display_var, values=list(app.video_mode_display_to_value), command=self.change_mode); app.video_mode_menu.grid(row=7, column=0, padx=14, pady=2, sticky="ew")
        app.video_duration_var = ctk.IntVar(value=5); app.video_duration_label = ctk.CTkLabel(left, text="Duration"); app.video_duration_entry = ctk.CTkEntry(left, textvariable=app.video_duration_var); app.video_seconds_label = ctk.CTkLabel(left, text="seconds"); app.video_duration_label.grid(row=8, column=0, padx=14, pady=1, sticky="w"); app.video_duration_entry.grid(row=9, column=0, padx=14, pady=2, sticky="ew"); app.video_duration_entry.bind("<FocusOut>", lambda _event: self.change_duration())
        heading("OUTPUT", 10); app.video_save_control = SaveControl(left, label="Save As...", command=self.save); app.video_process_button = app.video_save_control.button; app.video_process_button.grid(row=11, column=0, padx=14, pady=(2, 10), sticky="ew")
        app.video_preview_label = ctk.CTkLabel(right, text="Video preview"); app.video_preview_label.grid(row=0, column=0, padx=20, pady=20)

    def refresh_preview(self):
        app = self.app
        path = self.state.path
        label = getattr(app, "video_preview_label", None)
        if path is None or label is None:
            return
        try:
            ffmpeg = find_ffmpeg()
            if not ffmpeg:
                raise ValueError(app.translator.text("error.video_component_missing"))
            frame = extract_video_frame(ffmpeg, path)
            frame.thumbnail((720, 600), Image.Resampling.LANCZOS)
            badge = self._badge_path() if self.state.badge.enabled else None
            logo = self.state.logo.path if self.state.logo.enabled and self.state.logo.path else None
            if badge:
                with Image.open(badge) as opened:
                    frame = app.processor.compose(frame, opened.convert("RGBA"), MarkerSettings(
                        badge_name=badge.name, position=self.state.badge.position,
                        size_percent=self.state.badge.size, margin=self.state.badge.margin,
                        opacity=self.state.badge.opacity,
                    ), Image.open(logo).convert("RGBA") if logo else None)
            self.preview_photo = ctk.CTkImage(light_image=frame, dark_image=frame, size=frame.size)
            label.configure(image=self.preview_photo, text="")
            label.image = self.preview_photo
            app.video_preview_photo = self.preview_photo  # compatibility UI-resource alias
        except (OSError, ValueError) as error:
            self.preview_photo = None
            label.configure(image=None, text=app.translator.text("error.preview", error=error))

    def save(self):
        app = self.app
        source = self.state.path
        if source is None:
            from tkinter import messagebox
            messagebox.showwarning(app.translator.text("warning.title"), app.translator.text("warning.nothing_to_save")); return
        from tkinter import filedialog, messagebox
        suggested = source.with_name(f"{source.stem}_ai{source.suffix}")
        target = filedialog.asksaveasfilename(title=app.translator.text("dialog.save_video_as"), initialdir=str(source.parent), initialfile=suggested.name, defaultextension=source.suffix, filetypes=[(app.translator.text("files.supported_videos"), "*.mp4 *.mov *.mkv *.avi *.webm"), (app.translator.text("files.all"), "*.*")], confirmoverwrite=True)
        if not target: return
        destination = Path(target)
        if destination.resolve() == source.resolve():
            messagebox.showwarning(app.translator.text("warning.title"), app.translator.text("warning.nothing_to_save")); return
        badge = self._badge_path() if self.state.badge.enabled else None
        logo = self.state.logo.path if self.state.logo.enabled and self.state.logo.path else None
        if badge is None and logo is None:
            messagebox.showwarning(app.translator.text("warning.title"), app.translator.text("warning.nothing_to_save")); return
        settings = MarkerSettings(badge_name=badge.name if badge else "", position=self.state.badge.position, size_percent=self.state.badge.size, margin=self.state.badge.margin, opacity=self.state.badge.opacity, video_mode=self.state.mode, video_duration=self.state.duration, logo_mode=self.state.logo.mode, logo_enabled=bool(logo), logo_path=str(logo or ""), logo_position="top-left", logo_size_percent=self.state.logo.size, logo_margin=self.state.logo.margin, logo_opacity=self.state.logo.opacity)
        request = VideoProcessingRequest(source, destination, badge, logo, settings)
        try:
            if not find_ffmpeg(): raise ValueError(app.translator.text("error.video_component_missing"))
            from .batch import BatchProcessor
            BatchProcessor(app.processor).process_video(request.source, request.badge, request.destination, request.settings, marker_metadata(request.badge.name if request.badge else "", app.badges.display_name(request.badge.name) if request.badge else ""), logo=request.logo)
            app.status_var.set(app.translator.text("video.saved_name", name=destination.name))
        except (OSError, ValueError) as error:
            messagebox.showerror(app.translator.text("error.title"), str(error))

