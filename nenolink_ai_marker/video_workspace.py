"""Video preview ownership boundary."""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from PIL import Image
import customtkinter as ctk

from .batch import extract_video_frame, find_ffmpeg, video_duration_seconds, video_overlay_visible_at
from .models import MarkerSettings
from .metadata import marker_metadata
from .workspace_state import VideoEvent, apply_video_event
from .save_control import SaveControl
from .badge_control import BadgeControl, BadgeProjection
from .source_control import SourceControl
from .logo_control import LogoControl, LogoProjection
from .preview_shell import PreviewShell
from .workspace_control_panel import (
    WorkspaceControlPanel, ParameterRow, PARAM_ROW_PADY,
    PARAM_LABEL_WIDTH, PARAM_DROPDOWN_WIDTH,
)


@dataclass(frozen=True, slots=True)
class VideoProcessingRequest:
    source: Path
    destination: Path
    badge: Path | None
    logo: Path | None
    settings: MarkerSettings


class VideoWorkspace:
    # The preview is a representative frame at one second, not playback state.
    PREVIEW_TIMESTAMP_SECONDS = 1.0
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
        for name in ("video_workspace", "video_preview_label", "video_badge_enable", "video_badge_menu", "video_badge_var", "video_badge_preview_label", "video_badge_name_label", "video_process_button", "video_save_control"):
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
            self.apply_translations()
            loaded = self.state.path is not None
            self.app.video_sources = [self.state.path] if loaded else []
            self.app.media_sources["video"] = list(self.app.video_sources)
            if loaded:
                self.refresh_preview()
            else:
                self.app.video_preview_label.configure(image=None, text=self.app.translator.text("video.preview"))
                self.preview_photo = None; self.app.video_preview_photo = None

    def _project_controls(self):
        app = self.app
        app.video_mode_var.set(self.state.mode)
        app.video_mode_display_var.set(next((label for label, value in app.video_mode_display_to_value.items() if value == self.state.mode), app.translator.text("video.mode.beginning")))
        app.video_duration_var.set(max(1, int(self.state.duration)))
        app.video_badge_var.set(app.badges.display_name(self.state.badge.badge_id))
        app.video_size_var.set(self.state.badge.size); app.video_margin_var.set(self.state.badge.margin); app.video_opacity_var.set(self.state.badge.opacity)
        names = [path.name for path in app.badges.display_badges()]
        displays = [app.badges.display_name(name) for name in names]
        badge = self._badge_path()
        self.badge_control.project(BadgeProjection(bool(self.state.badge.enabled), app.badges.display_name(self.state.badge.badge_id), tuple(displays), badge, self.state.badge.position, self.state.badge.size, self.state.badge.margin, self.state.badge.opacity, app.translator.text("pdf.add_badge"), app.translator.text("section.ai_badge")))
        for field, key in (("size", "size.value"), ("margin", "margin.value"), ("opacity", "opacity.value")):
            row = getattr(self, "badge_parameter_rows", {}).get(field)
            if row is not None:
                value = getattr(self.state.badge, field)
                row.project(text=app.translator.text(key, value=value), value=value)
        if getattr(self, "logo_enabled_var", None) is not None:
            self.logo_enabled_var.set(self.state.logo.enabled)
            self.logo_mode_var.set(self.state.logo.mode)
            self.logo_size_var.set(self.state.logo.size); self.logo_margin_var.set(self.state.logo.margin); self.logo_opacity_var.set(self.state.logo.opacity)
            self.logo_file_label.configure(text=self.state.logo.path.name if self.state.logo.path else app.translator.text("logo.no_file"))
            if getattr(self, "logo_control", None):
                self.logo_control.project(LogoProjection(enabled=self.state.logo.enabled, filename=self.state.logo.path.name if self.state.logo.path else "", mode=self.state.logo.mode, modes=tuple(self.logo_mode_display_to_value), size=self.state.logo.size, margin=self.state.logo.margin, opacity=self.state.logo.opacity, labels=self._logo_labels()))

    def _logo_labels(self):
        t = self.app.translator.text
        return {"heading": t("section.own_logo"), "enabled": t("logo.enable"),
                "choose": t("logo.choose"), "none": t("logo.no_file"),
                "position": t("logo.position_value"), "size": t("logo.size"),
                "margin": t("logo.margin"), "opacity": t("logo.opacity"),
                "mode.front": t("logo.mode.front"), "mode.entire": t("logo.mode.entire"), "mode.back": t("logo.mode.back"),
                **{f"position.{name}": t("position." + name.replace("-", "_")) for name in ("top-left", "top-right", "bottom-left", "bottom-right", "center")}}

    def apply_translations(self):
        """Reproject labels only; workspace state is intentionally untouched."""
        if self.root is None:
            return
        t = self.app.translator.text
        if getattr(self, "file_heading", None): self.file_heading.configure(text=t("section.file"))
        if getattr(self, "source_control", None): self.source_control.set_label(t("video.choose"))
        if getattr(self, "video_position_label", None): self.video_position_label.configure(text=t("position"))
        if getattr(self, "options_heading", None): self.options_heading.configure(text=t("section.video_options"))
        if getattr(self, "video_mode_label", None): self.video_mode_label.configure(text=t("video.badge_mode"))
        if getattr(self, "video_duration_label", None): self.video_duration_label.configure(text=t("video.duration"))
        if getattr(self, "video_seconds_label", None): self.video_seconds_label.configure(text=t("video.seconds"))
        if getattr(self, "save_control", None): self.save_control.set_label(t("dialog.save_as_generic"))
        if getattr(self, "preview_shell", None): self.preview_shell.heading.configure(text=t("section.preview"))
        loaded = self.state.path is not None
        if getattr(self, "source_control", None):
            self.source_control.project(
                filename=self.state.path.name if loaded else "",
                empty_text=t("files.none"),
            )
        if getattr(self.app, "video_preview_label", None) is not None and not loaded:
            self.app.video_preview_label.configure(image=None, text=t("video.preview"))
        position_values = {
            t("position.top_left"): "top-left", t("position.top_right"): "top-right",
            t("position.bottom_left"): "bottom-left", t("position.bottom_right"): "bottom-right",
            t("position.center"): "center",
        }
        self.video_position_display_to_value = position_values
        if getattr(self, "video_position_menu", None):
            self.video_position_menu.configure(values=list(position_values))
            selected_position = next((label for label, value in position_values.items() if value == self.state.badge.position), "")
            self.video_position_display_var.set(selected_position)
        displays = {t("video.mode.beginning"): "beginning", t("video.mode.permanent"): "permanent", t("video.mode.end"): "end"}
        self.app.video_mode_display_to_value = displays
        self.logo_mode_display_to_value = {t("logo.mode.front"): "front", t("logo.mode.entire"): "entire", t("logo.mode.back"): "back"}
        if getattr(self, "video_mode_menu", None): self.video_mode_menu.configure(values=list(displays))
        if getattr(self, "badge_control", None):
            self._project_controls()

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
        payload = {"enabled": enabled} if isinstance(enabled, bool) else {}
        apply_video_event(self.state, VideoEvent.VISUAL_CHANGED, payload)
        self.project(); self.refresh_preview(); self.app._save_image_settings()

    def change_badge_parameter(self, field, value):
        if field not in {"size", "margin", "opacity"}:
            raise ValueError(f"Unsupported badge parameter: {field}")
        apply_video_event(self.state, VideoEvent.VISUAL_CHANGED, {field: int(float(value))})
        self.project(); self.refresh_preview(); self.app._save_image_settings()

    def change_badge_position(self, label):
        value = self.video_position_display_to_value.get(label, label)
        apply_video_event(self.state, VideoEvent.VISUAL_CHANGED, {"position": value})
        self.project(); self.refresh_preview(); self.app._save_image_settings()

    def choose_logo(self):
        from tkinter import filedialog
        selected = filedialog.askopenfilename(title=self.app.translator.text("dialog.open_logo"), filetypes=[(self.app.translator.text("files.supported_images"), "*.png *.jpg *.jpeg *.webp"), (self.app.translator.text("files.all"), "*.*")])
        if selected:
            apply_video_event(self.state, VideoEvent.LOGO_FILE_CHANGED, {"path": selected, "enabled": True})
            self.project(); self.refresh_preview()

    def change_logo(self, enabled=None, *, size=None, margin=None, opacity=None):
        if enabled is not None:
            apply_video_event(self.state, VideoEvent.LOGO_ENABLED_CHANGED, {"enabled": bool(enabled)})
        for event, field, value in (
            (VideoEvent.LOGO_SIZE_CHANGED, "size", size),
            (VideoEvent.LOGO_MARGIN_CHANGED, "margin", margin),
            (VideoEvent.LOGO_OPACITY_CHANGED, "opacity", opacity),
        ):
            if value is not None:
                apply_video_event(self.state, event, {field: int(value)})
        self.project(); self.refresh_preview()

    def change_logo_mode(self, mode):
        apply_video_event(self.state, VideoEvent.LOGO_MODE_CHANGED, {"mode": self.logo_mode_display_to_value.get(mode, mode)})
        self.project(); self.refresh_preview()

    def _build_ui(self, workspace):
        app = self.app
        self.control_panel = WorkspaceControlPanel(workspace, width=320, scrollable_frame_cls=getattr(app, "AutoHideScrollableFrame", ctk.CTkScrollableFrame))
        for section in ("FILE", "AI_BADGE", "OWN_LOGO", "VIDEO_OPTIONS"):
            self.control_panel.declare_section(section)
        left = self.control_panel.frame
        app.video_controls_host = left; left.grid(row=0, column=0, padx=(4, 8), pady=4, sticky="nsew"); left.grid_columnconfigure(0, weight=1)
        self.preview_shell = PreviewShell(workspace); self.preview_shell.frame.grid(row=0, column=1, padx=(8, 4), pady=4, sticky="nsew"); right = self.preview_shell.viewport; app.video_preview_host = right
        file_section = ctk.CTkFrame(left, fg_color="transparent"); self.control_panel.add_section("FILE", file_section)
        file_section.grid_columnconfigure(0, weight=1)
        self.file_heading = ctk.CTkLabel(file_section, text=app.translator.text("section.file"), font=ctk.CTkFont(weight="bold")); self.file_heading.grid(row=0, column=0, padx=2, pady=(2, 1), sticky="w")
        self.source_control = SourceControl(file_section, choose_command=self.choose_video, choose_label=app.translator.text("video.choose"), empty_label=app.translator.text("files.none"), width=280, compact=True); self.source_control.frame.grid(row=1, column=0, padx=2, pady=(1,0), sticky="ew"); app.video_open_button = self.source_control.choose_button
        app.video_badge_group = ctk.CTkFrame(left, fg_color="transparent"); self.control_panel.add_section("AI_BADGE", app.video_badge_group); app.video_badge_group.grid_columnconfigure(0, weight=1)
        self.badge_control = BadgeControl(app.video_badge_group, on_enabled_changed=self.change_visual, on_badge_selected=self.change_badge, heading_label=app.translator.text("section.ai_badge"))
        self.badge_control.frame.grid(row=0, column=0, sticky="ew")
        app.video_badge_enable = self.badge_control.enabled_widget; app.video_badge_menu = self.badge_control.selector_widget; app.video_badge_var = self.badge_control.selector_var; app.video_badge_preview_label = self.badge_control.graphic_widget; app.video_badge_name_label = self.badge_control.graphic_widget
        self.video_position_display_var = ctk.StringVar(value=app.translator.text("position.bottom_right")); self.video_position_display_to_value = {app.translator.text("position.top_left"):"top-left", app.translator.text("position.top_right"):"top-right", app.translator.text("position.bottom_left"):"bottom-left", app.translator.text("position.bottom_right"):"bottom-right", app.translator.text("position.center"):"center"}
        self.video_position_label = ctk.CTkLabel(app.video_badge_group, text=app.translator.text("position"), width=PARAM_LABEL_WIDTH); self.video_position_label.grid(row=1, column=0, padx=8, pady=(2, 0), sticky="w"); app.video_position_label=self.video_position_label; app.video_position_menu = ctk.CTkOptionMenu(app.video_badge_group, variable=self.video_position_display_var, values=list(self.video_position_display_to_value), command=self.change_badge_position, width=PARAM_DROPDOWN_WIDTH); self.video_position_menu=app.video_position_menu; app.video_position_menu.grid(row=2, column=0, padx=8, pady=(0, 2), sticky="w")
        app.video_size_var = ctk.IntVar(value=self.state.badge.size); app.video_margin_var = ctk.IntVar(value=self.state.badge.margin); app.video_opacity_var = ctk.IntVar(value=self.state.badge.opacity)
        self.badge_parameter_rows = {}
        for index, (field, key, low, high, variable) in enumerate((
            ("size", "size.value", 1, 100, app.video_size_var),
            ("margin", "margin.value", 0, 250, app.video_margin_var),
            ("opacity", "opacity.value", 0, 100, app.video_opacity_var),
        ), start=3):
            row = ParameterRow(app.video_badge_group, text=app.translator.text(key, value=getattr(self.state.badge, field)), start=low, end=high, value=getattr(self.state.badge, field), variable=variable, command=lambda value, field=field: self.change_badge_parameter(field, value))
            row.frame.grid(row=index, column=0, pady=PARAM_ROW_PADY, sticky="ew")
            self.badge_parameter_rows[field] = row
            setattr(app, f"video_{field}_label", row.label)
        logo_section = ctk.CTkFrame(left, fg_color="transparent"); self.control_panel.add_section("OWN_LOGO", logo_section)
        self.logo_control = LogoControl(logo_section, on_enabled=lambda value: self.change_logo(value), on_choose=self.choose_logo, on_mode=self.change_logo_mode, show_mode=True, on_size=lambda value: self.change_logo(size=value), on_margin=lambda value: self.change_logo(margin=value), on_opacity=lambda value: self.change_logo(opacity=value), labels=self._logo_labels())
        self.logo_control.frame.grid(row=0, column=0, sticky="ew")
        self.logo_enabled_var = self.logo_control.enabled_var; self.logo_mode_var = self.logo_control.mode_var; self.logo_file_label = self.logo_control.filename_label; self.logo_size_var = ctk.IntVar(value=15); self.logo_margin_var = ctk.IntVar(value=20); self.logo_opacity_var = ctk.IntVar(value=100)
        options_section = ctk.CTkFrame(left, fg_color="transparent"); self.control_panel.add_section("VIDEO_OPTIONS", options_section)
        self.options_heading = ctk.CTkLabel(options_section, text=app.translator.text("section.video_options"), font=ctk.CTkFont(weight="bold")); self.options_heading.grid(row=0, column=0, padx=2, pady=(2, 1), sticky="w"); app.video_mode_var = ctk.StringVar(value="beginning"); app.video_mode_display_var = ctk.StringVar(value=app.translator.text("video.mode.beginning")); app.video_mode_display_to_value = {app.translator.text("video.mode.beginning"):"beginning", app.translator.text("video.mode.permanent"):"permanent", app.translator.text("video.mode.end"):"end"}
        self.video_mode_label = ctk.CTkLabel(options_section, text=app.translator.text("video.badge_mode")); self.video_mode_label.grid(row=1, column=0, padx=2, pady=1, sticky="w"); app.video_mode_label=self.video_mode_label; self.video_mode_menu = ctk.CTkOptionMenu(options_section, variable=app.video_mode_display_var, values=list(app.video_mode_display_to_value), command=self.change_mode); app.video_mode_menu=self.video_mode_menu; self.video_mode_menu.grid(row=2, column=0, padx=2, pady=2, sticky="ew")
        app.video_duration_var = ctk.IntVar(value=5); self.video_duration_label = ctk.CTkLabel(options_section, text=app.translator.text("video.duration")); app.video_duration_label=self.video_duration_label; app.video_duration_entry = ctk.CTkEntry(options_section, textvariable=app.video_duration_var); self.video_seconds_label = ctk.CTkLabel(options_section, text=app.translator.text("video.seconds")); app.video_seconds_label=self.video_seconds_label; self.video_duration_label.grid(row=3, column=0, padx=2, pady=1, sticky="w"); app.video_duration_entry.grid(row=4, column=0, padx=2, pady=2, sticky="ew"); app.video_duration_entry.bind("<FocusOut>", lambda _event: self.change_duration())
        self.save_control = SaveControl(self.source_control.action_row, label=app.translator.text("dialog.save_as_generic"), command=self.save); self.source_control.place_save_control(self.save_control); app.video_save_control = self.save_control; app.video_process_button = self.save_control.button
        app.video_preview_label = ctk.CTkLabel(right, text=app.translator.text("video.preview")); app.video_preview_label.grid(row=0, column=0, padx=20, pady=20)
        self.apply_translations()

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
            actual_duration = None
            needs_duration = (
                (self.state.badge.enabled and self.state.mode != "permanent")
                or (self.state.logo.enabled and self.state.logo.path is not None and self.state.logo.mode != "entire")
            )
            if needs_duration:
                actual_duration = video_duration_seconds(ffmpeg, path)
            # The extractor falls back to t=0 for clips shorter than its
            # requested timestamp. Choose the last valid in-clip instant for
            # short timed clips so preview visibility matches that frame.
            preview_timestamp = (
                min(self.PREVIEW_TIMESTAMP_SECONDS, max(0.0, actual_duration - 0.001))
                if actual_duration is not None else self.PREVIEW_TIMESTAMP_SECONDS
            )
            frame = extract_video_frame(ffmpeg, path, timestamp=preview_timestamp)
            frame.thumbnail((720, 600), Image.Resampling.LANCZOS)
            duration = actual_duration if actual_duration is not None else max(1.0, preview_timestamp)
            badge_path = self._badge_path() if self.state.badge.enabled else None
            badge_active = bool(badge_path) and video_overlay_visible_at(
                self.state.mode, self.state.duration, duration, preview_timestamp,
            )
            logo_path = self.state.logo.path if self.state.logo.enabled and self.state.logo.path else None
            logo_active = bool(logo_path) and video_overlay_visible_at(
                self.state.logo.mode, self.state.duration, duration, preview_timestamp,
            )
            badge_image = None
            logo_image = None
            if badge_active:
                with Image.open(badge_path) as opened:
                    badge_image = opened.convert("RGBA")
            if logo_active:
                with Image.open(logo_path) as opened:
                    logo_image = opened.convert("RGBA")
            settings = MarkerSettings(
                badge_name=badge_path.name if badge_path else "",
                position=self.state.badge.position,
                size_percent=self.state.badge.size,
                margin=self.state.badge.margin,
                opacity=self.state.badge.opacity,
                video_mode=self.state.mode,
                video_duration=self.state.duration,
                logo_mode=self.state.logo.mode,
                logo_enabled=logo_active,
                logo_path=str(logo_path or ""),
                logo_position="top-left",
                logo_size_percent=self.state.logo.size,
                logo_margin=self.state.logo.margin,
                logo_opacity=self.state.logo.opacity,
            )
            frame = app.processor.compose(frame, badge_image, settings, logo_image)
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

