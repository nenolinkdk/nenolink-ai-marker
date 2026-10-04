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

