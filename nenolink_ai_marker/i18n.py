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
    "tab.batch": "Batch Processing", "tab.badges": "Badges",
    "button.open_images": "Choose Image", "files.none": "No file selected",
    "position": "Badge Position", "size.value": "Badge Size: {value}%",
    "margin.value": "Margin: {value} px", "opacity.value": "Opacity: {value}%",
    "button.process": "Process Image", "preview.select_image": "Choose an image to preview",
    "badge_not_found": "Badge not found", "badge": "Selected Badge",
    "badge.standard": "Nenolink Standard Badges", "badge.custom": "Custom Badge Folder",
    "badge.custom_path": "Custom badge folder", "badge.refresh": "Refresh Badges",
    "badge.none": "No badges found", "button.choose_badge_folder": "Choose Badge Folder",
    "guide.missing": "User Guide could not be found.", "error.title": "Error",
    "button.browse": "Browse", "badge.found": "Found {count} badge(s) in {folder}",
    "badge.not_found": "No badge PNG files found. Folder searched: {folder}",
    "badge.not_found_preview": "No badge PNG files available. Folder searched: {folder}",
    "badge.custom_missing": "Custom badge folder is unavailable: {folder}. Using standard badges from {fallback}.",
    "position.top_left": "Top left", "position.top_right": "Top right",
    "position.bottom_left": "Bottom left", "position.bottom_right": "Bottom right",
    "files.none_supported": "No supported images selected",
    "files.selected": "{count} image(s) selected - {name}", "files.supported": "Supported images",
    "files.all": "All files", "dialog.open_images": "Choose Image",
    "dialog.output_folder": "Choose Output Folder", "dialog.custom_badges": "Choose Badge Folder",
    "preview.showing": "Previewing {name}", "error.preview": "Preview error: {error}",
    "error.settings": "Settings could not be saved: {error}", "warning.title": "Action required",
    "warning.nothing_to_save": "Choose an image and badge first.",
    "process.summary": "Saved {saved} of {total} image(s). Originals were not changed.",
    "error.completed": "Completed with errors", "complete.title": "Complete",
    "button.choose_input": "Choose Input Folder", "button.choose_output": "Choose Output Folder",
    "button.scan_folder": "Scan Folder", "button.start_batch": "Start Batch Processing",
    "button.cancel_batch": "Cancel Batch", "badge.custom_description": "Custom badge image",
    "batch.input": "Input Folder", "batch.output_subfolder": "Create output subfolder inside input folder",
    "batch.output_separate": "Use separate output folder", "batch.recursive": "Include subfolders",
    "batch.preserve": "Preserve folder structure", "batch.images": "Process images",
    "batch.videos": "Process videos", "batch.skip": "Skip files that appear already processed",
    "batch.invalid_input": "Input folder does not exist: {folder}",
    "batch.scan_first": "Choose and scan an input folder before starting batch processing.",
    "batch.scan_summary": "Images: {images} | Videos: {videos} | Unsupported: {unsupported} | Total selected: {total}\nOutput: {output}",
    "batch.progress": "Current: {name} | Completed: {completed}/{total} | Successful: {success} | Skipped: {skipped} | Errors: {errors}",
    "batch.done": "Batch complete. Successful: {success}, skipped: {skipped}, errors: {errors}.",
    "batch.cancelled": "Batch cancelled.",
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
