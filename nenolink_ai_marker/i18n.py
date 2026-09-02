from __future__ import annotations

import json
from pathlib import Path


LANGUAGES = {
    "English": "en", "Dansk": "da", "Deutsch": "de", "Français": "fr",
    "Español": "es", "Italiano": "it", "Português": "pt", "Nederlands": "nl",
    "Svenska": "sv", "Norsk": "no", "Polski": "pl", "Čeština": "cs",
}


class Translator:
    def __init__(self, directory: Path, language: str = "en") -> None:
        self.directory = directory
        self._english = self._load("en")
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
        template = self._active.get(key, self._english.get(key, key))
        try:
            return template.format(**values)
        except (KeyError, ValueError):
            return template

    @staticmethod
    def language_name(code: str) -> str:
        return next((name for name, value in LANGUAGES.items() if value == code), "English")
