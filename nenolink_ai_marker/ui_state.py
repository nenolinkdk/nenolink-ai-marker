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
