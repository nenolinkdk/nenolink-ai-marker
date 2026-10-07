"""Image workspace UI ownership during the Image migration.

The workspace receives the existing ImageWorkspaceState and injected legacy
callbacks/resources.  MarkerApp remains a temporary lifecycle entry adapter;
widget construction lives here.
"""
from __future__ import annotations

import customtkinter as ctk
from pathlib import Path
from dataclasses import replace
from tkinter import filedialog, messagebox
from PIL import Image
from .batch import is_above_recommended_size
from .inspection import human_file_size
from .processor import SUPPORTED_EXTENSIONS
from .image_output import ImageProcessingRequest
from .metadata import marker_metadata
from .workspace_state import ImageEvent, apply_image_event
from .save_control import SaveControl
from .badge_control import BadgeControl, BadgeProjection
from .source_control import SourceControl
from .logo_control import LogoControl, LogoProjection
from .preview_shell import PreviewShell


class ImageWorkspace:
    def __init__(self, app, state, *, scrollable_frame_cls):
        self.app = app
        self.state = state
        self.scrollable_frame_cls = scrollable_frame_cls
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
        for name in ("image_workspace", "image_controls", "file_label", "preview_label", "welcome_frame", "process_button", "process_save_control", "badge_enable", "badge_menu", "single_badge_preview_label", "single_badge_name_label"):
            if hasattr(self.app, name):
                setattr(self.app, name, None)

    def mount(self, host):
        """Own Image view creation and projection; registry switch is deferred."""
        self._dispose_view()
        self.root = ctk.CTkFrame(host, fg_color="transparent")
        self.presentation_generation += 1
        self.root.grid(row=0, column=0, sticky="nsew")
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self.app.image_workspace = self.root
        self._build_ui(self.root)

    def unmount(self):
        self._dispose_view()

    def has_active_work(self):
        return bool(self.state.selected_files)

    def clear_runtime_state(self):
        apply_image_event(self.state, ImageEvent.CLEAR_RUNTIME)

    def dispatch(self, event, payload=None):
        return apply_image_event(self.state, event, payload)

    def enter_clean(self):
        return self.dispatch(ImageEvent.CLEAR_RUNTIME)

    def project(self):
        """Project authoritative state through the current Image presentation."""
        if self.root is not None and self.root.winfo_exists():
            self.apply_translations()
            files = self.state.selected_files
            if getattr(self.app, "file_label", None) is not None:
                self.app.file_label.configure(text=(f"{files[0].name} · {human_file_size(files[0].stat().st_size)}" if files else self.app.translator.text("files.none")))
            if getattr(self, "source_control", None) is not None:
                self.source_control.project(filename=(files[0].name if files else ""), metadata=(human_file_size(files[0].stat().st_size) if files else ""), empty_text=self.app.translator.text("files.none"))
            badge_path = self.app.badges.find(self.state.badge.badge_id) if self.state.badge.badge_id else None
            self.badge_control.project(BadgeProjection(bool(self.state.badge.enabled), self.app.badges.display_name(self.state.badge.badge_id), tuple(self.app.badges.display_name(p.name) for p in self.app.badges.display_badges()), badge_path, self.state.badge.position, self.state.badge.size, self.state.badge.margin, self.state.badge.opacity, self.app.translator.text("pdf.add_badge")))
            if getattr(self, "logo_control", None):
                self.logo_control.project(LogoProjection(enabled=self.state.logo.enabled, filename=self.state.logo.path.name if self.state.logo.path else "", position=self.state.logo.position, size=self.state.logo.size, margin=self.state.logo.margin, opacity=self.state.logo.opacity))
            self.app.sources = list(files)
            self.app.media_sources["image"] = list(files)
            self.refresh_preview()

    def apply_translations(self):
        """Project locale presentation onto the current Image view only."""
        t = self.app.translator.text
        if self.source_control is not None:
            self.source_control.choose_button.configure(text="1. " + t("button.open_media"))
            self.source_control.metadata_label.configure(text=t("files.size_guidance"))
        if self.badge_control is not None:
            self.badge_control.enabled_widget.configure(text=t("pdf.add_badge"))
        if getattr(self, "position_menu", None) is not None:
            mapping = {t("position.top_left"): "top-left", t("position.top_right"): "top-right", t("position.bottom_left"): "bottom-left", t("position.bottom_right"): "bottom-right", t("position.center"): "center"}
            self.position_display_to_value = mapping
            self.app.position_display_to_value = mapping
            self.position_menu.configure(values=list(mapping))
        if self.logo_control is not None:
            self.logo_control.heading.configure(text=t("logo.title"))
            self.logo_control.enabled_widget.configure(text=t("logo.enable"))
            self.logo_control.choose_button.configure(text=t("logo.choose"))
            self.logo_control.position_label.configure(text=t("logo.position"))
        for name, key in (("position_label", "position"), ("welcome_title", "welcome.title"), ("welcome_tagline", "welcome.tagline"), ("welcome_description1", "welcome.description1"), ("welcome_description2", "welcome.description2")):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.configure(text=t(key))

    def choose_files(self):
        """Own the Image file event; dialog and status are injected services."""
        app = self.app
        selected = filedialog.askopenfilenames(title=app.translator.text("dialog.open_media"), filetypes=[(app.translator.text("files.supported_media"), " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))), (app.translator.text("files.all"), "*.*")])
        if not selected:
            return
        candidates = [Path(path) for path in selected if Path(path).suffix.lower() in SUPPORTED_EXTENSIONS]
        if any(is_above_recommended_size(path) for path in candidates) and not messagebox.askokcancel(app.translator.text("warning.large_title"), app.translator.text("warning.large_file")):
            return
        apply_image_event(self.state, ImageEvent.FILE_SELECTED, {"files": tuple(candidates)})
        self.project()

    def refresh_preview(self):
        """Project ImageWorkspaceState through the existing renderer."""
        app = self.app
        files = self.state.selected_files
        if not files:
            self.state.preview_image = None
            app.preview_photo = app.preview_image = None
            app._show_welcome()
            return
        badge = app.badges.find(self.state.badge.badge_id) if self.state.badge.enabled else None
        logo = self.state.logo.path if self.state.logo.enabled else None
        settings = replace(app.settings(), position=self.state.badge.position, size_percent=self.state.badge.size, margin=self.state.badge.margin, opacity=self.state.badge.opacity, logo_enabled=self.state.logo.enabled, logo_position=self.state.logo.position, logo_size_percent=self.state.logo.size, logo_margin=self.state.logo.margin, logo_opacity=self.state.logo.opacity)
        app._show_preview()
        try:
            image = app.preview_renderer.render(files[0], badge, settings, logo)
            self.state.preview_image = image.copy()
            app.preview_image = self.state.preview_image
            app.preview_photo = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
            app.preview_label.configure(image=app.preview_photo, text=""); app.preview_label.image = app.preview_photo
        except (OSError, ValueError) as error:
            app.preview_label.configure(image=None, text=app.translator.text("error.preview", error=error))

    def save(self):
        """Save from authoritative workspace state through the existing processor."""
        app = self.app
        badge = app.badges.find(self.state.badge.badge_id) if self.state.badge.enabled else None
        logo = self.state.logo.path if self.state.logo.enabled else None
        settings = replace(app.settings(), badge_name=self.state.badge.badge_id,
                           position=self.state.badge.position,
                           size_percent=self.state.badge.size,
                           margin=self.state.badge.margin,
                           opacity=self.state.badge.opacity,
                           logo_enabled=self.state.logo.enabled,
                           logo_path=str(self.state.logo.path or ""),
                           logo_position=self.state.logo.position,
                           logo_size_percent=self.state.logo.size,
                           logo_margin=self.state.logo.margin,
                           logo_opacity=self.state.logo.opacity)
        request = ImageProcessingRequest(tuple(self.state.selected_files), badge, logo, settings)
        if not request.sources or (request.badge is None and request.logo is None):
            messagebox.showwarning(app.translator.text("warning.title"), app.translator.text("warning.nothing_to_save"))
            return
        metadata = marker_metadata(self.state.badge.badge_id, app.badges.display_name(self.state.badge.badge_id)) if badge else None
        saved, failures, metadata_warnings = [], [], []
        for source in request.sources:
            suggested = source.with_name(f"{source.stem}_ai{source.suffix}")
            selected = filedialog.asksaveasfilename(title=app.translator.text("dialog.save_as"), initialdir=str(source.parent), initialfile=suggested.name, defaultextension=source.suffix, filetypes=[(app.translator.text("files.supported"), f"*{source.suffix}"), (app.translator.text("files.all"), "*.*")], confirmoverwrite=True)
            if not selected:
                continue
            try:
                written = app.processor.save(app.processor.process(source, request.badge, request.settings, request.logo), Path(selected), metadata)
                saved.append(Path(selected))
                if metadata and not written:
                    metadata_warnings.append(source.name)
            except (OSError, ValueError) as error:
                failures.append(f"{source.name}: {error}")
        summary = app.translator.text("process.summary", saved=len(saved), total=len(request.sources))
        app.status_var.set(summary)
        warning = "\n\n" + app.translator.text("warning.metadata_failed") if metadata_warnings else ""
        (messagebox.showerror if failures else messagebox.showinfo)(app.translator.text("error.completed") if failures else app.translator.text("complete.title"), summary + ("\n\n" + "\n".join(failures[:8]) if failures else "") + warning)

    def badge_changed(self, displayed=None):
        selector = getattr(self.app, "badge_display_var", None)
        displayed = displayed if displayed is not None else (selector.get() if selector is not None else self.app.badge_var.get())
        badge_id = getattr(self.app, "badge_display_to_file", {}).get(displayed, displayed)
        apply_image_event(self.state, ImageEvent.BADGE_CHANGED, {"badge_id": badge_id})
        self.app._project_image_visual_state()
        self.refresh_preview()

    def position_changed(self, label):
        value = getattr(self.app, "position_display_to_value", {}).get(label, label)
        apply_image_event(self.state, ImageEvent.VISUAL_CHANGED, {"position": value})
        self.project(); self.refresh_preview()

    def choose_logo(self):
        selected = filedialog.askopenfilename(title=self.app.translator.text("logo.choose"), filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")])
        if not selected:
            return
        self.logo_changed(path=Path(selected), enabled=True)

    def logo_position_changed(self, label):
        value = getattr(self.app, "logo_position_display_to_value", {}).get(label, label)
        self.logo_changed(position=value)
    def logo_changed(self, *_args, **changes):
        apply_image_event(self.state, ImageEvent.LOGO_CHANGED, {
            "enabled": changes.get("enabled", bool(self.app.logo_enabled_var.get())), "path": changes.get("path", self.app._logo_path()),
            "position": changes.get("position", self.app.logo_position_var.get()), "size": int(self.app.logo_size_var.get()),
            "margin": int(self.app.logo_margin_var.get()), "opacity": int(self.app.logo_opacity_var.get()),
        })
        self.app._project_image_visual_state()
        self.refresh_preview()

    def visual_changed(self, enabled=None, *_args):
        apply_image_event(self.state, ImageEvent.VISUAL_CHANGED, {
            "enabled": bool(self.app.badge_enabled_var.get()) if enabled is None else bool(enabled),
            "position": self.app.position_var.get(), "size": int(self.app.size_var.get()),
            "margin": int(self.app.margin_var.get()), "opacity": int(self.app.opacity_var.get()),
            "logo_enabled": bool(self.app.logo_enabled_var.get()), "logo_path": self.app._logo_path(),
            "logo_position": self.app.logo_position_var.get(), "logo_size": int(self.app.logo_size_var.get()),
            "logo_margin": int(self.app.logo_margin_var.get()), "logo_opacity": int(self.app.logo_opacity_var.get()),
        })
        self.app._project_image_visual_state()
        self.refresh_preview()

    def _slider(self, parent, variable, start, end, row):
        app = self.app
        label = ctk.CTkLabel(parent)
        label.grid(row=row, column=0, padx=14, pady=(4, 0), sticky="w")
        ctk.CTkSlider(parent, from_=start, to=end, number_of_steps=end-start,
                      variable=variable, command=self.visual_changed).grid(
                          row=row + 1, column=0, padx=14, pady=(1, 3), sticky="ew")
        return label

    def _build_ui(self, workspace):
        self.badge_control = BadgeControl(workspace, on_enabled_changed=self.visual_changed, on_badge_selected=self.badge_changed)
        """Build the existing Image controls; this is the sole UI builder."""
        app = self.app
        workspace.grid_columnconfigure(1, weight=1)
        workspace.grid_rowconfigure(0, weight=1)
        left = self.scrollable_frame_cls(workspace, width=320, fg_color=("gray86", "gray17"))
        app.image_controls = left
        left.grid(row=0, column=0, padx=(4, 8), pady=4, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)
        self.source_control = SourceControl(left, choose_command=self.choose_files, choose_label="Choose file", width=280)
        self.source_control.frame.grid(row=0, column=0, padx=14, pady=(10, 4), sticky="ew")
        app.open_button = self.source_control.choose_button; app.file_label = self.source_control.filename_label; app.file_size_guidance = self.source_control.metadata_label
        app.image_badge_group = ctk.CTkFrame(left, fg_color="transparent")
        app.image_badge_group.grid(row=3, column=0, padx=14, pady=(4, 4), sticky="ew")
        app.image_badge_group.grid_columnconfigure(0, weight=1)
        self.badge_control.frame.grid(row=0, column=0, sticky="ew")
        app.badge_enable = self.badge_control.enabled_widget; app.badge_menu = self.badge_control.selector_widget
        app.single_badge_preview_label = self.badge_control.graphic_widget; app.single_badge_name_label = self.badge_control.graphic_widget
        app.position_label = ctk.CTkLabel(app.image_badge_group)
        app.position_label.grid(row=1, column=0, padx=8, pady=(5, 1), sticky="w")
        self.position_label = app.position_label
        self.position_menu = ctk.CTkOptionMenu(app.image_badge_group, variable=app.position_display_var, values=["—"], command=self.position_changed)
        self.position_menu.grid(row=2, column=0, padx=8, pady=2, sticky="ew")
        app.size_label = self._slider(app.image_badge_group, app.size_var, 1, 100, 3)
        app.margin_label = self._slider(app.image_badge_group, app.margin_var, 0, 250, 5)
        app.opacity_label = self._slider(app.image_badge_group, app.opacity_var, 0, 100, 7)
        self.logo_control = LogoControl(left, on_enabled=lambda value: self.logo_changed(enabled=value), on_choose=self.choose_logo, on_size=lambda value: self.logo_changed(size=value), on_margin=lambda value: self.logo_changed(margin=value), on_opacity=lambda value: self.logo_changed(opacity=value))
        self.logo_control.frame.grid(row=12, column=0, padx=14, pady=(5, 8), sticky="ew")
        app.logo_controls = self.logo_control.frame
        app.logo_heading = self.logo_control.heading; app.logo_enable = self.logo_control.enabled_widget; app.logo_choose = self.logo_control.choose_button; app.logo_filename = self.logo_control.filename_label; app.logo_position_label = self.logo_control.position_label; app.logo_size_slider = self.logo_control.size_widget; app.logo_margin_slider = self.logo_control.margin_widget; app.logo_opacity_slider = self.logo_control.opacity_widget
        """
        app.logo_heading = ctk.CTkLabel(app.logo_controls, font=ctk.CTkFont(weight="bold")); app.logo_heading.grid(row=0, column=0, columnspan=2, padx=8, pady=(6, 2), sticky="w")
        app.logo_enable = ctk.CTkCheckBox(app.logo_controls, variable=app.logo_enabled_var, command=self.logo_changed); app.logo_enable.grid(row=1, column=0, columnspan=2, padx=8, pady=3, sticky="w")
        app.logo_choose = ctk.CTkButton(app.logo_controls, command=self.choose_logo, height=28); app.logo_choose.grid(row=2, column=0, padx=8, pady=3, sticky="w")
        app.logo_filename = ctk.CTkLabel(app.logo_controls, textvariable=app.logo_filename_var, anchor="w", wraplength=155); app.logo_filename.grid(row=2, column=1, padx=(2, 8), pady=3, sticky="ew")
        app.logo_position_label = ctk.CTkLabel(app.logo_controls); app.logo_position_label.grid(row=3, column=0, padx=8, pady=2, sticky="w")
        app.logo_position_menu = ctk.CTkOptionMenu(app.logo_controls, variable=app.logo_position_display_var, values=["—"], command=self.logo_position_changed, height=28); app.logo_position_menu.grid(row=3, column=1, padx=8, pady=2, sticky="ew")
        app.logo_size_label = ctk.CTkLabel(app.logo_controls); app.logo_size_label.grid(row=4, column=0, columnspan=2, padx=8, sticky="w")
        app.logo_size_slider = ctk.CTkSlider(app.logo_controls, from_=1, to=100, number_of_steps=99, variable=app.logo_size_var, command=self.logo_changed); app.logo_size_slider.grid(row=5, column=0, columnspan=2, padx=8, pady=(0, 2), sticky="ew")
        app.logo_margin_label = ctk.CTkLabel(app.logo_controls); app.logo_margin_label.grid(row=6, column=0, columnspan=2, padx=8, sticky="w")
        app.logo_margin_slider = ctk.CTkSlider(app.logo_controls, from_=0, to=250, number_of_steps=250, variable=app.logo_margin_var, command=self.logo_changed); app.logo_margin_slider.grid(row=7, column=0, columnspan=2, padx=8, pady=(0, 2), sticky="ew")
        app.logo_opacity_label = ctk.CTkLabel(app.logo_controls); app.logo_opacity_label.grid(row=8, column=0, columnspan=2, padx=8, sticky="w")
        app.logo_opacity_slider = ctk.CTkSlider(app.logo_controls, from_=0, to=100, number_of_steps=100, variable=app.logo_opacity_var, command=self.logo_changed); app.logo_opacity_slider.grid(row=9, column=0, columnspan=2, padx=8, pady=(0, 2), sticky="ew")
        app.logo_images_only = self.logo_control.position_label
        """
        app.process_save_control = SaveControl(left, command=self.save)
        app.process_button = app.process_save_control.button; app.process_button.grid(row=13, column=0, padx=14, pady=(2, 10), sticky="ew")
        self.preview_shell = PreviewShell(workspace); self.preview_shell.frame.grid(row=0, column=1, padx=(8, 4), pady=4, sticky="nsew"); right = self.preview_shell.viewport
        app.preview_label = ctk.CTkLabel(right)
        app.welcome_frame = ctk.CTkFrame(right, fg_color="transparent"); app.welcome_frame.grid(row=0, column=0, padx=18, pady=14, sticky="nsew"); app.welcome_frame.grid_columnconfigure(0, weight=1); app.welcome_frame.grid_rowconfigure(4, weight=1)
        app.welcome_title = ctk.CTkLabel(app.welcome_frame, font=ctk.CTkFont(size=28, weight="bold")); app.welcome_title.grid(row=0, column=0, padx=12, pady=(12, 4))
        app.welcome_tagline = ctk.CTkLabel(app.welcome_frame, font=ctk.CTkFont(size=18, weight="bold"), text_color=("#2469a0", "#65b6ef")); app.welcome_tagline.grid(row=1, column=0, padx=12, pady=(0, 10))
        app.welcome_description1 = ctk.CTkLabel(app.welcome_frame, wraplength=720, justify="center"); app.welcome_description1.grid(row=2, column=0, padx=18, pady=2)
        app.welcome_description2 = ctk.CTkLabel(app.welcome_frame, wraplength=720, justify="center"); app.welcome_description2.grid(row=3, column=0, padx=18, pady=(2, 10))
        app.welcome_illustration = ctk.CTkLabel(app.welcome_frame, anchor="center"); app.welcome_illustration.grid(row=4, column=0, padx=12, pady=(4, 12), sticky="nsew")
        app._load_image_welcome(); app.welcome_frame.bind("<Configure>", app._resize_image_welcome)
