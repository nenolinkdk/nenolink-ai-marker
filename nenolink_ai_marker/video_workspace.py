"""Video preview ownership boundary."""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from PIL import Image
import customtkinter as ctk

from .batch import extract_video_frame, find_ffmpeg
from .models import MarkerSettings
from .metadata import marker_metadata


@dataclass(frozen=True, slots=True)
class VideoProcessingRequest:
    source: Path
    destination: Path
    badge: Path
    settings: MarkerSettings


class VideoWorkspace:
    def __init__(self, app, state):
        self.app = app
        self.state = state
        self.preview_photo = None
        self.root = None

    def mount(self, host):
        if self.root is not None and self.root.winfo_exists():
            self.root.grid(); self.project(); self.refresh_preview(); return
        self.app._clear_content_host()
        self.root = ctk.CTkFrame(host, fg_color="transparent"); self.root.grid(row=0, column=0, sticky="nsew")
        self.root.grid_columnconfigure(0, weight=0, minsize=320); self.root.grid_columnconfigure(1, weight=1); self.root.grid_rowconfigure(0, weight=1)
        self._build_ui(self.root); self.project()

    def unmount(self):
        if self.root is not None and self.root.winfo_exists(): self.root.grid_remove()

    def project(self):
        if self.root is not None and self.root.winfo_exists():
            self.app._project_video_state(); self.app._refresh_video_labels(); self.app._refresh_video_badges()

    def has_active_work(self):
        return self.state.path is not None

    def clear_runtime_state(self):
        self.state.clear_runtime_state(); self.preview_photo = None

    def _build_ui(self, workspace):
        app = self.app
        left = app.AutoHideScrollableFrame(workspace, width=320, fg_color=("gray86", "gray17")) if hasattr(app, "AutoHideScrollableFrame") else ctk.CTkScrollableFrame(workspace, width=320, fg_color=("gray86", "gray17"))
        app.video_controls_host = left; left.grid(row=0, column=0, padx=(4, 8), pady=4, sticky="nsew"); left.grid_columnconfigure(0, weight=1)
        right = ctk.CTkFrame(workspace); app.video_preview_host = right; right.grid(row=0, column=1, padx=(8, 4), pady=4, sticky="nsew"); right.grid_columnconfigure(0, weight=1); right.grid_rowconfigure(0, weight=1)
        def heading(text, row): ctk.CTkLabel(left, text=text, font=ctk.CTkFont(weight="bold")).grid(row=row, column=0, padx=14, pady=(8, 2), sticky="w")
        heading("FILE", 0); app.video_open_button = ctk.CTkButton(left, text="Choose Video", command=app.open_video); app.video_open_button.grid(row=1, column=0, padx=14, pady=2, sticky="ew")
        app.video_file_label = ctk.CTkLabel(left, text="No video selected", anchor="w", justify="left", wraplength=280); app.video_file_label.grid(row=2, column=0, padx=14, pady=(2, 6), sticky="ew")
        heading("AI BADGE", 3); app.video_badge_enable = ctk.CTkCheckBox(left, text="Add AI badge", variable=app.badge_enabled_var, command=app._video_changed); app.video_badge_enable.grid(row=4, column=0, padx=14, pady=2, sticky="w")
        app.video_badge_label = ctk.CTkLabel(left, text="Selected Badge", anchor="w"); app.video_badge_label.grid(row=5, column=0, padx=14, pady=1, sticky="w")
        app.video_badge_var = ctk.StringVar(value=app.badge_display_var.get()); app.video_badge_menu = ctk.CTkOptionMenu(left, variable=app.video_badge_var, values=["—"], command=app.change_video_badge); app.video_badge_menu.grid(row=6, column=0, padx=14, pady=2, sticky="ew")
        badge_preview = ctk.CTkFrame(left); badge_preview.grid(row=7, column=0, padx=14, pady=3, sticky="ew"); badge_preview.grid_columnconfigure(1, weight=1)
        app.video_badge_preview_label = ctk.CTkLabel(badge_preview, width=90, height=44); app.video_badge_preview_label.grid(row=0, column=0, padx=5, pady=5)
        app.video_badge_name_label = ctk.CTkLabel(badge_preview, textvariable=app.badge_name_var, font=ctk.CTkFont(weight="bold"), anchor="w", wraplength=155); app.video_badge_name_label.grid(row=0, column=1, padx=(3, 5), pady=5, sticky="ew")
        app.video_position_var = ctk.StringVar(value="bottom-right"); app.video_position_display_var = ctk.StringVar(value="Bottom right"); app.video_position_display_to_value = {"Top left":"top-left", "Top right":"top-right", "Bottom left":"bottom-left", "Bottom right":"bottom-right", "Center":"center"}
        app.video_position_label = ctk.CTkLabel(left, text="Badge Position"); app.video_position_label.grid(row=8, column=0, padx=14, pady=1, sticky="w"); app.video_position_menu = ctk.CTkOptionMenu(left, variable=app.video_position_display_var, values=list(app.video_position_display_to_value), command=app.change_video_position); app.video_position_menu.grid(row=9, column=0, padx=14, pady=2, sticky="ew")
        app.video_size_var = ctk.IntVar(value=20); app.video_margin_var = ctk.IntVar(value=20); app.video_opacity_var = ctk.IntVar(value=100)
        app.video_size_label = app._video_slider(left, app.video_size_var, 1, 100, 10, "Badge Size"); app.video_margin_label = app._video_slider(left, app.video_margin_var, 0, 250, 12, "Badge Margin"); app.video_opacity_label = app._video_slider(left, app.video_opacity_var, 0, 100, 14, "Badge Opacity")
        heading("VIDEO OPTIONS", 16); app.video_mode_var = ctk.StringVar(value="permanent"); app.video_mode_display_var = ctk.StringVar(); app.video_mode_display_to_value = {"Permanent":"permanent", "Beginning":"beginning", "End":"end"}
        app.video_mode_label = ctk.CTkLabel(left, text="Video badge mode"); app.video_mode_label.grid(row=17, column=0, padx=14, pady=1, sticky="w"); app.video_mode_menu = ctk.CTkOptionMenu(left, variable=app.video_mode_display_var, values=list(app.video_mode_display_to_value), command=app.change_video_mode); app.video_mode_menu.grid(row=18, column=0, padx=14, pady=2, sticky="ew")
        app.video_duration_var = ctk.IntVar(value=5); app.video_duration_label = ctk.CTkLabel(left, text="Duration"); app.video_duration_entry = ctk.CTkEntry(left, textvariable=app.video_duration_var); app.video_seconds_label = ctk.CTkLabel(left, text="seconds"); app.video_duration_label.grid(row=19, column=0, padx=14, pady=1, sticky="w"); app.video_duration_entry.grid(row=20, column=0, padx=14, pady=2, sticky="ew"); app.video_duration_entry.bind("<FocusOut>", app.change_video_duration)
        heading("OUTPUT", 21); app.video_process_button = ctk.CTkButton(left, text="Save Marked Video...", command=self.save); app.video_process_button.grid(row=22, column=0, padx=14, pady=(2, 10), sticky="ew")
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
            badge = app._video_badge_path() if self.state.badge.enabled else None
            if badge:
                with Image.open(badge) as opened:
                    frame = app.processor.compose(frame, opened.convert("RGBA"), MarkerSettings(
                        badge_name=badge.name, position=self.state.badge.position,
                        size_percent=self.state.badge.size, margin=self.state.badge.margin,
                        opacity=self.state.badge.opacity,
                    ))
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
        badge = app._video_badge_path() if self.state.badge.enabled else None
        if badge is None:
            messagebox.showwarning(app.translator.text("warning.title"), app.translator.text("warning.nothing_to_save")); return
        settings = MarkerSettings(badge_name=badge.name, position=self.state.badge.position, size_percent=self.state.badge.size, margin=self.state.badge.margin, opacity=self.state.badge.opacity, video_mode=self.state.mode, video_duration=self.state.duration)
        request = VideoProcessingRequest(source, destination, badge, settings)
        try:
            if not find_ffmpeg(): raise ValueError(app.translator.text("error.video_component_missing"))
            from .batch import BatchProcessor
            BatchProcessor(app.processor).process_video(request.source, request.badge, request.destination, request.settings, marker_metadata(request.badge.name, app.badges.display_name(request.badge.name)))
            app.status_var.set(app.translator.text("video.saved_name", name=destination.name))
        except (OSError, ValueError) as error:
            messagebox.showerror(app.translator.text("error.title"), str(error))

