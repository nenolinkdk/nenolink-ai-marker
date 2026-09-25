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
    """Ordered selected items and the current position within that selection."""

    items: tuple[int, ...] = ()
    index: int = 0

    @property
    def current(self) -> int | None:
        return self.items[self.index] if self.items else None

    def rebuild(self, selection: ItemSelection, item_count: int) -> int:
        self.items = selection.resolve(item_count)
        self.index = 0
        return self.items[0]

    def move(self, delta: int) -> int | None:
        if not self.items:
            return None
        self.index = min(len(self.items) - 1, max(0, self.index + delta))
        return self.current

    def clear(self) -> None:
        self.items = ()
        self.index = 0


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
