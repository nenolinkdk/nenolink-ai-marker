"""Video preview ownership boundary."""
from __future__ import annotations

from pathlib import Path
from PIL import Image
import customtkinter as ctk

from .batch import extract_video_frame, find_ffmpeg
from .models import MarkerSettings


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

