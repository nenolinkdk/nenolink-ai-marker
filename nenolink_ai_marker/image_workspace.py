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
from .workspace_control_panel import (
    WorkspaceControlPanel, PARAM_ROW_PADY, PARAM_LABEL_WIDTH,
    PARAM_DROPDOWN_WIDTH, ParameterRow,
)
from .paths import welcome_image_path


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
        return self.dispatch(ImageEvent.RESET_TO_DEFAULTS)

    def project(self):
        """Project authoritative state through the current Image presentation."""
        if getattr(self, "root", None) is not None and self.root.winfo_exists():
            self.apply_translations()
            files = self.state.selected_files
            if getattr(self.app, "file_label", None) is not None:
                self.app.file_label.configure(text=(f"{files[0].name} · {human_file_size(files[0].stat().st_size)}" if files else self.app.translator.text("files.none")))
            if getattr(self, "source_control", None) is not None:
                self.source_control.project(filename=(files[0].name if files else ""), metadata=(human_file_size(files[0].stat().st_size) if files else ""), empty_text=self.app.translator.text("files.none"))
            badge_path = self.app.badges.find(self.state.badge.badge_id) if self.state.badge.badge_id else None
            self.badge_control.project(BadgeProjection(bool(self.state.badge.enabled), self.app.badges.display_name(self.state.badge.badge_id), tuple(self.app.badges.display_name(p.name) for p in self.app.badges.display_badges()), badge_path, self.state.badge.position, self.state.badge.size, self.state.badge.margin, self.state.badge.opacity, self.app.translator.text("pdf.add_badge"), self.app.translator.text("section.ai_badge")))
            if getattr(self, "logo_control", None):
                self.logo_control.project(LogoProjection(enabled=self.state.logo.enabled, filename=self.state.logo.path.name if self.state.logo.path else "", position=self.state.logo.position, size=self.state.logo.size, margin=self.state.logo.margin, opacity=self.state.logo.opacity, labels=self._logo_labels()))
            self.app.sources = list(files)
            self.app.media_sources["image"] = list(files)
            self.refresh_preview()

    def apply_translations(self):
        """Project locale presentation onto the current Image view only."""
        root = self.root
        if root is None or not root.winfo_exists():
            return
        t = self.app.translator.text
        if self.source_control is not None:
            self.source_control.choose_button.configure(text=t("button.open_images"))
            self.source_control.metadata_label.configure(text=t("files.size_guidance"))
            files = self.state.selected_files
            self.source_control.project(
                filename=files[0].name if files else "",
                metadata=(human_file_size(files[0].stat().st_size) if files else ""),
                empty_text=t("files.none"),
            )
        save_control = getattr(self.app, "process_save_control", None)
        if save_control is not None:
            save_control.set_label(t("dialog.save_as_generic"))
        if getattr(self, "preview_shell", None) is not None:
            self.preview_shell.heading.configure(text=t("section.preview"))
        if self.badge_control is not None:
            badge_path = self.app.badges.find(self.state.badge.badge_id) if self.state.badge.badge_id else None
            self.badge_control.project(BadgeProjection(
                bool(self.state.badge.enabled),
                self.app.badges.display_name(self.state.badge.badge_id),
                tuple(self.app.badges.display_name(p.name) for p in self.app.badges.display_badges()),
                badge_path, self.state.badge.position, self.state.badge.size,
                self.state.badge.margin, self.state.badge.opacity,
                t("pdf.add_badge"), t("section.ai_badge"),
            ))
        for field, key in (("size", "size.value"), ("margin", "margin.value"), ("opacity", "opacity.value")):
            row = getattr(self, "badge_parameter_rows", {}).get(field)
            if row is not None:
                value = getattr(self.state.badge, field)
                row.project(text=t(key, value=value), value=value)
        if getattr(self, "position_menu", None) is not None:
            mapping = {t("position.top_left"): "top-left", t("position.top_right"): "top-right", t("position.bottom_left"): "bottom-left", t("position.bottom_right"): "bottom-right", t("position.center"): "center"}
            self.position_display_to_value = mapping
            self.position_menu.configure(values=list(mapping))
            selected = next((label for label, value in mapping.items() if value == self.state.badge.position), "")
            self.position_display_var.set(selected)
        if self.logo_control is not None:
            self.logo_control.project(LogoProjection(enabled=self.state.logo.enabled, filename=self.state.logo.path.name if self.state.logo.path else "", position=self.state.logo.position, size=self.state.logo.size, margin=self.state.logo.margin, opacity=self.state.logo.opacity, labels=self._logo_labels()))
        for widget, key in ((getattr(self, "file_heading", None), "section.file"),):
            if widget is not None:
                widget.configure(text=t(key))
        for name, key in (("position_label", "position"), ("welcome_title", "welcome.title"), ("welcome_tagline", "welcome.tagline"), ("welcome_description1", "welcome.description1"), ("welcome_description2", "welcome.description2")):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.configure(text=t(key))

    def _logo_labels(self):
        t = self.app.translator.text
        return {"heading": t("section.own_logo"), "enabled": t("logo.enable"),
                "choose": t("logo.choose"), "none": t("logo.no_file"),
                "position": t("logo.position_value"), "size": t("logo.size"),
                "margin": t("logo.margin"), "opacity": t("logo.opacity"),
                "mode.front": t("logo.mode.front"), "mode.entire": t("logo.mode.entire"), "mode.back": t("logo.mode.back"),
                **{f"position.{name}": t("position." + name.replace("-", "_")) for name in ("top-left", "top-right", "bottom-left", "bottom-right", "center")}}

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
        if getattr(self, "root", None) is not None: self.project()

    def refresh_preview(self):
        """Project ImageWorkspaceState through the existing renderer."""
        app = self.app
        files = self.state.selected_files
        if not files:
            self.state.preview_image = None
            app.preview_photo = app.preview_image = None
            self._show_welcome()
            return
        badge = app.badges.find(self.state.badge.badge_id) if self.state.badge.enabled else None
        logo = self.state.logo.path if self.state.logo.enabled else None
        settings = replace(app.settings(), position=self.state.badge.position, size_percent=self.state.badge.size, margin=self.state.badge.margin, opacity=self.state.badge.opacity, logo_enabled=self.state.logo.enabled, logo_position=self.state.logo.position, logo_size_percent=self.state.logo.size, logo_margin=self.state.logo.margin, logo_opacity=self.state.logo.opacity)
        self._show_preview()
        try:
            image = app.preview_renderer.render(files[0], badge, settings, logo)
            self.state.preview_image = image.copy()
            app.preview_image = self.state.preview_image
            app.preview_photo = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
            self.preview_label.configure(image=app.preview_photo, text=""); self.preview_label.image = app.preview_photo
        except (OSError, ValueError) as error:
            self.preview_label.configure(image=None, text=app.translator.text("error.preview", error=error))

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
        if displayed is None and self.badge_control is not None:
            displayed = self.badge_control.selector_var.get()
        if displayed is None:
            return
        badge_id = next((path.name for path in self.app.badges.display_badges()
                         if self.app.badges.display_name(path.name) == displayed), displayed)
        apply_image_event(self.state, ImageEvent.BADGE_CHANGED, {"badge_id": badge_id})
        if getattr(self, "root", None) is not None: self.project()
        self.refresh_preview()

    def position_changed(self, label):
        value = self.position_display_to_value.get(label, label)
        apply_image_event(self.state, ImageEvent.VISUAL_CHANGED, {"position": value})
        if getattr(self, "root", None) is not None: self.project()
        self.refresh_preview()

    def badge_parameter_changed(self, field, value):
        """Dispatch only the badge parameter changed by its slider."""
        if field not in {"size", "margin", "opacity"}:
            raise ValueError(f"Unsupported badge parameter: {field}")
        apply_image_event(self.state, ImageEvent.VISUAL_CHANGED, {field: int(float(value))})
        if getattr(self, "root", None) is not None: self.project()
        self.refresh_preview()

    def choose_logo(self):
        selected = filedialog.askopenfilename(title=self.app.translator.text("dialog.open_logo"), filetypes=[(self.app.translator.text("files.supported_images"), "*.png *.jpg *.jpeg *.webp"), (self.app.translator.text("files.all"), "*.*")])
        if not selected:
            return
        self.logo_changed(path=Path(selected), enabled=True)

    def logo_position_changed(self, label):
        value = self.logo_position_display_to_value.get(label, label)
        self.logo_changed(position=value)
    def logo_changed(self, *_args, **changes):
        payload = {}
        for field in ("enabled", "path", "position", "size", "margin", "opacity"):
            if field in changes:
                value = changes[field]
                if field in {"size", "margin", "opacity"}:
                    value = int(value)
                payload[field] = value
        apply_image_event(self.state, ImageEvent.LOGO_CHANGED, payload)
        if getattr(self, "root", None) is not None: self.project()
        self.refresh_preview()

    def visual_changed(self, enabled=None, *_args):
        # BadgeControl's checkbox passes bool. A numeric slider callback must
        # never be interpreted as enabled state; sliders have their own route.
        payload = {"enabled": enabled} if isinstance(enabled, bool) else {}
        apply_image_event(self.state, ImageEvent.VISUAL_CHANGED, payload)
        if getattr(self, "root", None) is not None: self.project()
        self.refresh_preview()

    def _slider(self, parent, variable, start, end, row, label_key):
        value = int(variable.get())
        control = ParameterRow(
            parent, text=self.app.translator.text(label_key, value=value),
            start=start, end=end, value=value, variable=variable,
            command=lambda value: self.badge_parameter_changed(label_key.split(".")[0], value),
        )
        control.frame.grid(row=row, column=0, pady=PARAM_ROW_PADY, sticky="ew")
        self.badge_parameter_rows[label_key.split(".")[0]] = control
        return control.label

    def _show_welcome(self):
        self.preview_label.grid_remove(); self.welcome_frame.grid(row=0, column=0, padx=18, pady=14, sticky="nsew"); self._resize_welcome()

    def _show_preview(self):
        self.welcome_frame.grid_remove(); self.preview_label.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

    def _resize_welcome(self, event=None):
        if self.welcome_image is None: return
        width = max(240, (event.width if event else self.welcome_frame.winfo_width()) - 48); height = max(135, (event.height if event else self.welcome_frame.winfo_height()) - 210)
        ratio = min(width / self.welcome_image.width, height / self.welcome_image.height); size = (max(1, int(self.welcome_image.width * ratio)), max(1, int(self.welcome_image.height * ratio)))
        self.welcome_photo = ctk.CTkImage(light_image=self.welcome_image, dark_image=self.welcome_image, size=size); self.welcome_illustration.configure(image=self.welcome_photo, text="")

    def _build_ui(self, workspace):
        """Build the existing Image controls; this is the sole UI builder."""
        app = self.app
        workspace.grid_columnconfigure(1, weight=1)
        workspace.grid_rowconfigure(0, weight=1)
        self.control_panel = WorkspaceControlPanel(workspace, width=320, scrollable_frame_cls=self.scrollable_frame_cls)
        for section in ("FILE", "AI_BADGE", "OWN_LOGO"):
            self.control_panel.declare_section(section)
        left = self.control_panel.frame
        app.image_controls = left
        left.grid(row=0, column=0, padx=(4, 8), pady=4, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)
        file_section = ctk.CTkFrame(left, fg_color="transparent"); self.control_panel.add_section("FILE", file_section)
        file_section.grid_columnconfigure(0, weight=1)
        self.file_heading = ctk.CTkLabel(file_section, text=app.translator.text("section.file"), font=ctk.CTkFont(weight="bold")); self.file_heading.grid(row=0, column=0, padx=2, pady=(2, 1), sticky="w")
        self.source_control = SourceControl(file_section, choose_command=self.choose_files, choose_label=app.translator.text("button.open_images"), empty_label=app.translator.text("files.none"), width=280, compact=True)
        self.source_control.frame.grid(row=1, column=0, padx=2, pady=(1, 0), sticky="ew")
        app.open_button = self.source_control.choose_button; app.file_label = self.source_control.filename_label; app.file_size_guidance = self.source_control.metadata_label
        app.image_badge_group = ctk.CTkFrame(left, fg_color="transparent"); self.control_panel.add_section("AI_BADGE", app.image_badge_group)
        app.image_badge_group.grid_columnconfigure(0, weight=1)
        self.badge_control = BadgeControl(app.image_badge_group, on_enabled_changed=self.visual_changed, on_badge_selected=self.badge_changed, heading_label=app.translator.text("section.ai_badge"))
        self.badge_control.frame.grid(row=0, column=0, sticky="ew")
        app.badge_enable = self.badge_control.enabled_widget; app.badge_menu = self.badge_control.selector_widget
        app.single_badge_preview_label = self.badge_control.graphic_widget; app.single_badge_name_label = self.badge_control.graphic_widget
        app.position_label = ctk.CTkLabel(app.image_badge_group, width=PARAM_LABEL_WIDTH)
        app.position_label.grid(row=1, column=0, padx=8, pady=(2, 0), sticky="w")
        self.position_label = app.position_label
        self.position_display_var = ctk.StringVar(value="")
        self.position_display_to_value = {}
        self.position_menu = ctk.CTkOptionMenu(app.image_badge_group, variable=self.position_display_var, values=["—"], command=self.position_changed)
        self.position_menu.configure(width=PARAM_DROPDOWN_WIDTH)
        self.position_menu.grid(row=2, column=0, padx=8, pady=(0, 2), sticky="w")
        self.badge_parameter_rows = {}
        self.badge_size_var = ctk.IntVar(value=self.state.badge.size)
        self.badge_margin_var = ctk.IntVar(value=self.state.badge.margin)
        self.badge_opacity_var = ctk.IntVar(value=self.state.badge.opacity)
        app.size_label = self._slider(app.image_badge_group, self.badge_size_var, 1, 100, 3, "size.value")
        app.margin_label = self._slider(app.image_badge_group, self.badge_margin_var, 0, 250, 4, "margin.value")
        app.opacity_label = self._slider(app.image_badge_group, self.badge_opacity_var, 0, 100, 5, "opacity.value")
        logo_section = ctk.CTkFrame(left, fg_color="transparent"); self.control_panel.add_section("OWN_LOGO", logo_section)
        self.logo_control = LogoControl(logo_section, on_enabled=lambda value: self.logo_changed(enabled=value), on_choose=self.choose_logo, on_size=lambda value: self.logo_changed(size=value), on_margin=lambda value: self.logo_changed(margin=value), on_opacity=lambda value: self.logo_changed(opacity=value), labels=self._logo_labels())
        self.logo_control.frame.grid(row=0, column=0, sticky="ew")
        self.logo_position_display_to_value = {
            app.translator.text("position.top_left"): "top-left",
            app.translator.text("position.top_right"): "top-right",
            app.translator.text("position.bottom_left"): "bottom-left",
            app.translator.text("position.bottom_right"): "bottom-right",
            app.translator.text("position.center"): "center",
        }
        app.logo_controls = self.logo_control.frame
        app.logo_heading = self.logo_control.heading; app.logo_enable = self.logo_control.enabled_widget; app.logo_choose = self.logo_control.choose_button; app.logo_filename = self.logo_control.filename_label; app.logo_position_label = self.logo_control.position_label; app.logo_size_slider = self.logo_control.size_widget; app.logo_margin_slider = self.logo_control.margin_widget; app.logo_opacity_slider = self.logo_control.opacity_widget
        app.process_save_control = SaveControl(self.source_control.action_row, label=app.translator.text("dialog.save_as_generic"), command=self.save)
        self.source_control.place_save_control(app.process_save_control)
        app.process_button = app.process_save_control.button
        self.preview_shell = PreviewShell(workspace); self.preview_shell.frame.grid(row=0, column=1, padx=(8, 4), pady=4, sticky="nsew"); right = self.preview_shell.viewport
        self.preview_label = ctk.CTkLabel(right)
        self.welcome_frame = ctk.CTkFrame(right, fg_color="transparent"); self.welcome_frame.grid(row=0, column=0, padx=18, pady=14, sticky="nsew"); self.welcome_frame.grid_columnconfigure(0, weight=1); self.welcome_frame.grid_rowconfigure(4, weight=1)
        self.welcome_title = ctk.CTkLabel(self.welcome_frame, font=ctk.CTkFont(size=28, weight="bold")); self.welcome_title.grid(row=0, column=0, padx=12, pady=(12, 4))
        self.welcome_tagline = ctk.CTkLabel(self.welcome_frame, font=ctk.CTkFont(size=18, weight="bold"), text_color=("#2469a0", "#65b6ef")); self.welcome_tagline.grid(row=1, column=0, padx=12, pady=(0, 10))
        self.welcome_description1 = ctk.CTkLabel(self.welcome_frame, wraplength=720, justify="center"); self.welcome_description1.grid(row=2, column=0, padx=18, pady=2)
        self.welcome_description2 = ctk.CTkLabel(self.welcome_frame, wraplength=720, justify="center"); self.welcome_description2.grid(row=3, column=0, padx=18, pady=(2, 10))
        self.welcome_illustration = ctk.CTkLabel(self.welcome_frame, anchor="center"); self.welcome_illustration.grid(row=4, column=0, padx=12, pady=(4, 12), sticky="nsew")
        self._load_welcome(); self.welcome_frame.bind("<Configure>", self._resize_welcome)

    def _load_welcome(self):
        try:
            with Image.open(welcome_image_path()) as opened: self.welcome_image = opened.convert("RGBA")
        except OSError:
            self.welcome_illustration.configure(text="◇")
