from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path


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
