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
    """Physical document position, independent of the processing scope."""

    current: int = 1
    count: int = 0

    @property
    def can_previous(self) -> bool:
        return self.count > 0 and self.current > 1

    @property
    def can_next(self) -> bool:
        return self.count > 0 and self.current < self.count

    def initialize(self, item_count: int, current: int = 1) -> int | None:
        self.count = max(0, item_count)
        self.current = min(self.count, max(1, current)) if self.count else 1
        return self.current if self.count else None

    def move(self, delta: int) -> int | None:
        if not self.count:
            return None
        self.current = min(self.count, max(1, self.current + delta))
        return self.current

    def clear(self) -> None:
        self.current = 1
        self.count = 0


@dataclass(slots=True)
class DocumentScopeState:
    """Normalised processing scope owned by one document type."""

    mode: str = "all"
    selected: str = ""
    ranges: str = "1-2"
    active_scope: tuple[int, ...] = ()

    def reset(self, mode: str = "all") -> None:
        self.mode = mode
        self.selected = ""
        self.ranges = "1-2"
        self.active_scope = ()

    def begin_edit(self, mode: str) -> None:
        if mode not in {"selected", "range"}:
            raise ValueError(f"Unsupported editable scope: {mode}")
        self.mode = mode

    def normalize(self, item_count: int) -> tuple[int, ...]:
        """Replace the active scope with one validated ordered item set."""
        selection = pptx_item_selection(
            self.mode,
            selected=self.selected,
            ranges=self.ranges,
        )
        self.active_scope = selection.resolve(item_count)
        return self.active_scope


def pptx_item_selection(
    mode: str,
    *,
    selected: str = "",
    ranges: str = "",
) -> ItemSelection:
    """Parse compact PowerPoint UI fields into the shared selection model."""
    try:
        if mode == "first":
            return ItemSelection("selected", (1,))
        if mode == "selected":
            values = tuple(int(value.strip()) for value in selected.split(",") if value.strip())
            return ItemSelection("selected", values)
        if mode == "range":
            values: list[int] = []
            for part in (value.strip() for value in ranges.split(",") if value.strip()):
                bounds = part.split("-")
                if len(bounds) != 2:
                    raise ValueError("Ranges must use start-end syntax.")
                start, end = (int(value.strip()) for value in bounds)
                if start > end:
                    raise ValueError("Range start must not exceed range end.")
                values.extend(range(start, end + 1))
            return ItemSelection("selected", tuple(dict.fromkeys(values)))
        if mode == "all":
            return ItemSelection()
    except ValueError as error:
        raise ValueError("Slide numbers must be positive whole numbers.") from error
    raise ValueError(f"Unsupported PowerPoint selection mode: {mode}")
