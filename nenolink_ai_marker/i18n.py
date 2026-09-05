from __future__ import annotations

import json
from pathlib import Path


LANGUAGES = {
    "English": "en", "Dansk": "da", "Deutsch": "de", "Français": "fr",
    "Español": "es", "Italiano": "it", "Português": "pt", "Nederlands": "nl",
    "Svenska": "sv", "Norsk": "no", "Polski": "pl", "Čeština": "cs",
}

# Last-resort strings keep the packaged GUI usable even if locale files are
# deleted or damaged. Full translations remain in the external JSON files.
DEFAULT_ENGLISH = {
    "app.window": "AI disclosure badges", "language": "Language", "menu.settings": "Badge Source",
    "button.user_guide": "User Guide (PDF)", "tab.single": "Single File",
    "button.reset": "Reset", "button.back": "← Back", "status.reset": "Settings reset",
    "tab.batch": "Batch Processing", "tab.badges": "Badges", "tab.inspect": "Inspect File",
    "inspect.title": "Inspect File", "inspect.intro": "Choose an image or video to inspect its AI Marker metadata.", "inspect.choose": "Choose File", "inspect.selected": "Selected file", "inspect.file": "File:", "inspect.format_size": "Format / size:", "inspect.metadata": "AI Marker metadata", "inspect.status": "Status:", "inspect.software": "Software:", "inspect.ai_label": "AI Label:", "inspect.marker_version": "Marker Version:", "inspect.found": "Found", "inspect.not_found": "Not found", "inspect.not_available": "Not available", "inspect.error": "Inspection error", "inspect.ready": "Ready", "inspect.none": "No file selected", "inspect.not_found_message": "No Nenolink AI Marker metadata was found in this file.", "inspect.no_ai_warning": "No metadata does not mean no AI. Metadata can be absent or removed.", "inspect.info": "Metadata can be removed or changed by editing software and online platforms.", "inspect.error_message": "This file could not be inspected. {reason}", "inspect.supported": "Supported images and videos",
    "button.open_images": "Choose Image", "button.open_media": "Choose Image or Video", "button.process_video": "Save Marked Video…", "files.none": "No file selected",
    "position": "Badge Position", "size.value": "Badge Size: {value}%",
    "margin.value": "Margin: {value} px", "opacity.value": "Opacity: {value}%",
    "button.process": "Save Marked Image…", "preview.select_image": "Choose an image to preview",
    "badge_not_found": "Badge not found", "badge": "Selected Badge",
    "badge.standard": "Nenolink Standard Badges", "badge.custom": "Custom Badge Folder",
    "badge.custom_path": "Custom badge folder", "badge.refresh": "Refresh Badges",
    "badge.none": "No badges found", "button.choose_badge_folder": "Choose Badge Folder",
    "badge.source_label": "Badge Source:", "badge.source_standard": "Nenolink Standard Badges",
    "badge.source_custom": "Custom Badge Folder", "badge.gallery": "Available Badges",
    "badge.loaded_standard": "{count} standard badges loaded", "badge.loaded_custom": "{count} custom badges loaded",
    "badge.help": "Use Nenolink Standard Badges or select a folder containing your own badge images.\n\nUse clear filenames, for example:\nmy-company-ai-assisted.png\n\nThe filename is used as the display name for custom badges.\n\nSupported formats: PNG, JPG, JPEG and WEBP.\nTransparent PNG is recommended.",
    "badge.custom_empty": "No supported badge images found in this folder.",
    "guide.missing": "User Guide could not be found.", "error.title": "Error",
    "button.browse": "Browse", "badge.found": "Found {count} badge(s) in {folder}",
    "badge.not_found": "No badge PNG files found. Folder searched: {folder}",
    "badge.not_found_preview": "No badge PNG files available. Folder searched: {folder}",
    "badge.custom_missing": "Custom badge folder could not be found.",
    "position.top_left": "Top left", "position.top_right": "Top right",
    "position.bottom_left": "Bottom left", "position.bottom_right": "Bottom right", "position.center": "Center",
    "logo.title": "Own Logo", "logo.enable": "Add own logo to images",
    "logo.choose": "Choose Logo", "logo.position": "Logo Position",
    "logo.size": "Logo Size: {value}%", "logo.margin": "Logo Margin: {value} px",
    "logo.opacity": "Logo Opacity: {value}%", "logo.images_only": "Images only",
    "logo.supported": "Supported logo formats: PNG, JPG, JPEG and WEBP. Transparent PNG is recommended.",
    "logo.missing": "The selected logo file could not be found. Own Logo has been disabled.",
    "logo.invalid": "The selected file is not a supported logo image.",
    "logo.disabled": "Disabled",
    "error.video_component_missing": "Video processing is unavailable because the required video component could not be found. Reinstall or repair Nenolink AI Marker.",
    "files.none_supported": "No supported images selected",
    "files.size_guidance": "Images: recommended up to 50 MB\nVideos: recommended up to 2 GB\nPractical limits depend on resolution, codec, duration, memory and disk space.",
    "files.size_guidance_short": "Recommended: images up to 50 MB; videos up to 2 GB",
    "warning.large_title": "Large file", "warning.large_file": "This file is larger than the recommended size. Processing may require more time, memory and temporary disk space. Continue?",
    "warning.metadata_failed": "The file was marked successfully, but AI Marker metadata could not be written.",
    "batch.oversized": "Files above recommended size: {count}",
    "files.selected": "{count} file(s) selected - {name}", "files.supported": "Supported images",
    "files.all": "All files", "files.supported_media": "Supported images and videos", "files.supported_videos": "Supported videos", "dialog.open_images": "Choose Image", "dialog.open_media": "Choose Image or Video",
    "dialog.output_folder": "Choose Output Folder", "dialog.save_as": "Save marked image as", "dialog.save_video_as": "Save marked video as", "dialog.custom_badges": "Choose Badge Folder",
    "preview.video_selected": "Video selected: {name}", "video.saved_name": "Video saved successfully: {name}", "error.unsupported_video_output": "Unsupported video output format: {extension}",
    "preview.showing": "Previewing {name}", "error.preview": "Preview error: {error}",
    "error.settings": "Settings could not be saved: {error}", "warning.title": "Action required",
    "warning.nothing_to_save": "Choose an image and badge first.",
    "process.summary": "Saved {saved} of {total} image(s). Originals were not changed.",
    "error.completed": "Completed with errors", "complete.title": "Complete",
    "button.choose_input": "Choose Input Folder", "button.choose_output": "Choose Output Folder",
    "button.scan_folder": "Scan Folder", "button.start_batch": "Start Batch Processing",
    "button.cancel_batch": "Cancel", "badge.custom_description": "Custom badge image",
    "video.settings": "Video settings", "batch.output": "Output", "batch.options": "Options", "batch.progress_heading": "Progress",
    "video.badge": "Video badge:", "video.mode.permanent": "Permanent", "video.mode.beginning": "Beginning", "video.mode.end": "End",
    "video.duration": "Duration:", "video.seconds": "seconds",
    "batch.input": "Input Folder", "batch.output_subfolder": "Create output subfolder inside input folder",
    "batch.output_separate": "Use separate output folder", "batch.filename_suffix": "Output filename suffix:", "batch.recursive": "Include subfolders",
    "batch.preserve": "Preserve folder structure", "batch.images": "Process images",
    "batch.videos": "Process videos", "batch.skip": "Skip files that appear already processed",
    "batch.invalid_input": "Input folder does not exist: {folder}",
    "batch.scan_first": "Choose and scan an input folder before starting batch processing.",
    "batch.scan_summary": "Images: {images} | Videos: {videos} | Unsupported: {unsupported} | Total selected: {total}\nOutput: {output}",
    "batch.progress": "Current: {name} | Completed: {completed}/{total} | Successful: {success} | Skipped: {skipped} | Errors: {errors}",
    "batch.done": "Batch complete. Successful: {success}, skipped: {skipped}, errors: {errors}.",
    "batch.cancelled": "Batch cancelled.",
    "welcome.title": "Welcome to Nenolink AI Marker",
    "welcome.tagline": "Make AI use visible. Build trust.",
    "welcome.description1": "Clearly show when and how artificial intelligence has been used in images and videos.",
    "welcome.description2": "Choose a badge, place it on your content, and help make AI use more transparent.",
}


class Translator:
    def __init__(self, directory: Path, language: str = "en") -> None:
        self.directory = directory
        self._english = {**DEFAULT_ENGLISH, **self._load("en")}
        self.language = "en"
        self._active = self._english
        self.set_language(language)

    def _load(self, language: str) -> dict[str, str]:
        try:
            data = json.loads((self.directory / f"{language}.json").read_text(encoding="utf-8"))
            return {str(key): str(value) for key, value in data.items()}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {}

    def set_language(self, language: str) -> None:
        self.language = language if language in LANGUAGES.values() else "en"
        loaded = self._load(self.language)
        self._active = loaded if loaded else self._english

    def text(self, key: str, **values: object) -> str:
        template = self._active.get(key, self._english.get(key, "Text unavailable"))
        try:
            return template.format(**values)
        except (KeyError, ValueError):
            return template

    @staticmethod
    def language_name(code: str) -> str:
        return next((name for name, value in LANGUAGES.items() if value == code), "English")
