from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path

from .document_processing import ItemSelection


def show_welcome(sources: Collection[object]) -> bool:
    """The welcome panel is the empty-state view for Single File."""
    return not sources


@dataclass(slots=True)
class ContentWorkspaceState:
    """Keep image and video selections independent while navigating workspaces."""

    active: str = "image"
    media_sources: dict[str, list[Path]] = field(
        default_factory=lambda: {"image": [], "video": []}
    )

    def switch(self, target: str, current_sources: Collection[Path]) -> list[Path]:
        if self.active in self.media_sources:
            self.media_sources[self.active] = list(current_sources)
        self.active = target
        return list(self.media_sources.get(target, []))

    def clear(self) -> None:
        for sources in self.media_sources.values():
            sources.clear()
        self.active = "image"


@dataclass(slots=True)
class DocumentPreviewState:
    """Physical document preview position, independent of output selection."""

    current: int = 1
    count: int = 0

    @property
    def can_previous(self) -> bool:
        return self.count > 0 and self.current > 1

    @property
    def can_next(self) -> bool:
        return self.count > 0 and self.current < self.count

    def initialize(self, item_count: int) -> int | None:
        self.count = max(0, item_count)
        self.current = 1
        return self.current if self.count else None

    def move(self, delta: int) -> int | None:
        if not self.count:
            return None
        self.current = min(self.count, max(1, self.current + delta))
        return self.current

    def clear(self) -> None:
        self.current = 1
        self.count = 0


def pptx_item_selection(
    mode: str,
    *,
    single: str = "",
    selected: str = "",
    start: str = "",
    end: str = "",
) -> ItemSelection:
    """Parse compact PowerPoint UI fields into the shared selection model."""
    try:
        if mode == "single":
            return ItemSelection("single", (int(single.strip()),))
        if mode == "selected":
            values = tuple(int(value.strip()) for value in selected.split(",") if value.strip())
            return ItemSelection("selected", values)
        if mode == "range":
            return ItemSelection("range", start=int(start.strip()), end=int(end.strip()))
        if mode == "all":
            return ItemSelection()
    except ValueError as error:
        raise ValueError("Slide numbers must be positive whole numbers.") from error
    raise ValueError(f"Unsupported PowerPoint selection mode: {mode}")
