from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path

from .document_processing import ItemSelection


def show_welcome(sources: Collection[object]) -> bool:
    """The welcome panel is the empty-state view for Single File."""
    return not sources


@dataclass(slots=True)
class ContentWorkspaceState:
    """Track the active format while treating every format switch as new work."""

    active: str = "image"
    media_sources: dict[str, list[Path]] = field(
        default_factory=lambda: {"image": [], "video": []}
    )

    def switch(self, target: str, current_sources: Collection[Path]) -> list[Path]:
        if self.active in self.media_sources:
            self.media_sources[self.active].clear()
        if target in self.media_sources:
            self.media_sources[target].clear()
        self.active = target
        return []

    def clear(self) -> None:
        for sources in self.media_sources.values():
            sources.clear()
        self.active = "image"


@dataclass(slots=True)
class DocumentPreviewState:
    """Preview position constrained to the active document processing scope."""

    current: int = 1
    count: int = 0
    items: tuple[int, ...] = ()

    @property
    def can_previous(self) -> bool:
        return self.current in self.items and self.items.index(self.current) > 0

    @property
    def can_next(self) -> bool:
        return self.current in self.items and self.items.index(self.current) < len(self.items) - 1

    def initialize(self, item_count: int, items: Collection[int] | None = None) -> int | None:
        self.count = max(0, item_count)
        candidates = tuple(items) if items is not None else tuple(range(1, self.count + 1))
        self.items = tuple(item for item in candidates if 1 <= item <= self.count)
        self.current = self.items[0] if self.items else 1
        return self.current if self.items else None

    def move(self, delta: int) -> int | None:
        if not self.items:
            return None
        if self.current not in self.items:
            self.current = self.items[0]
        position = self.items.index(self.current)
        position = min(len(self.items) - 1, max(0, position + delta))
        self.current = self.items[position]
        return self.current

    def clear(self) -> None:
        self.current = 1
        self.count = 0
        self.items = ()


@dataclass(slots=True)
class DocumentScopeState:
    """Selection fields owned by one document type."""

    mode: str = "all"
    single: str = "1"
    selected: str = "1"
    range_start: str = "1"
    range_end: str = "2"

    def reset(self, mode: str = "all") -> None:
        self.mode = mode
        self.single = "1"
        self.selected = "1"
        self.range_start = "1"
        self.range_end = "2"

    def preview_items(self, item_count: int) -> tuple[int, ...]:
        """Resolve the one active scope into its ordered preview sequence."""
        selection = pptx_item_selection(
            self.mode,
            single=self.single,
            selected=self.selected,
            start=self.range_start,
            end=self.range_end,
        )
        return selection.resolve(item_count)


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
