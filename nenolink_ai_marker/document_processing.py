"""Shared contracts for safe, local processing across media and documents.

Format adapters own their file-format details.  These models deliberately keep
UI language separate from the language of the disclosure written to output.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from .models import MarkerSettings, Position, validated_filename_suffix


ContentKind = Literal["image", "video", "pdf", "pptx", "docx"]


@dataclass(frozen=True, slots=True)
class DisclosureSettings:
    badge_name: str
    label: str
    language: str = "en"
    position: Position = "bottom-right"
    size_percent: int = 20
    margin: int = 20
    opacity: int = 100

    def validated(self) -> "DisclosureSettings":
        positions = {"top-left", "top-right", "bottom-left", "bottom-right", "center"}
        return replace(
            self,
            badge_name=str(self.badge_name or "").strip(),
            label=str(self.label or "").strip(),
            language=str(self.language or "en").strip() or "en",
            position=self.position if self.position in positions else "bottom-right",
            size_percent=min(100, max(1, int(self.size_percent))),
            margin=min(2000, max(0, int(self.margin))),
            opacity=min(100, max(0, int(self.opacity))),
        )


@dataclass(frozen=True, slots=True)
class LogoSettings:
    enabled: bool = False
    path: Path | None = None
    position: Position = "top-left"
    size_percent: int = 15
    margin: int = 20
    opacity: int = 100

    def validated(self) -> "LogoSettings":
        positions = {"top-left", "top-right", "bottom-left", "bottom-right", "center"}
        return replace(
            self,
            enabled=bool(self.enabled),
            path=Path(self.path) if self.path else None,
            position=self.position if self.position in positions else "top-left",
            size_percent=min(100, max(1, int(self.size_percent))),
            margin=min(2000, max(0, int(self.margin))),
            opacity=min(100, max(0, int(self.opacity))),
        )


@dataclass(frozen=True, slots=True)
class OutputSettings:
    filename_suffix: str = "_ai"
    directory: Path | None = None

    def validated(self) -> "OutputSettings":
        return replace(
            self,
            filename_suffix=validated_filename_suffix(self.filename_suffix),
            directory=Path(self.directory) if self.directory else None,
        )


@dataclass(frozen=True, slots=True)
class ProcessorCapabilities:
    content_kind: ContentKind
    extensions: frozenset[str]
    supports_logo: bool = False
    supports_metadata: bool = False
    supports_preview: bool = False
    supports_batch: bool = False
    supports_selection: bool = False

    def supports(self, path: Path) -> bool:
        return path.suffix.casefold() in {extension.casefold() for extension in self.extensions}


@dataclass(frozen=True, slots=True)
class ProcessingRequest:
    source: Path
    destination: Path
    disclosure: DisclosureSettings
    logo: LogoSettings = LogoSettings()
    output: OutputSettings = OutputSettings()

    def validated(self) -> "ProcessingRequest":
        source = Path(self.source)
        destination = Path(self.destination)
        ensure_distinct_paths(source, destination)
        return replace(
            self,
            source=source,
            destination=destination,
            disclosure=self.disclosure.validated(),
            logo=self.logo.validated(),
            output=self.output.validated(),
        )


@runtime_checkable
class DocumentProcessor(Protocol):
    capabilities: ProcessorCapabilities

    def process(self, request: ProcessingRequest) -> object: ...


def ensure_distinct_paths(source: Path, destination: Path) -> None:
    """Reject a destination that would overwrite the source file."""
    if Path(source).resolve() == Path(destination).resolve():
        raise ValueError("Output path must be different from the source path.")


def settings_for_documents(
    settings: MarkerSettings,
    *,
    label: str,
    disclosure_language: str = "en",
) -> tuple[DisclosureSettings, LogoSettings]:
    """Adapt existing persisted settings without coupling document adapters to the GUI."""
    validated = settings.validated()
    disclosure = DisclosureSettings(
        badge_name=validated.badge_name,
        label=label,
        language=disclosure_language,
        position=validated.position,
        size_percent=validated.size_percent,
        margin=validated.margin,
        opacity=validated.opacity,
    ).validated()
    logo = LogoSettings(
        enabled=validated.logo_enabled,
        path=Path(validated.logo_path) if validated.logo_path else None,
        position=validated.logo_position,
        size_percent=validated.logo_size_percent,
        margin=validated.logo_margin,
        opacity=validated.logo_opacity,
    ).validated()
    return disclosure, logo
