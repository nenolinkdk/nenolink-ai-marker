from collections.abc import Collection


def show_welcome(sources: Collection[object]) -> bool:
    """The welcome panel is the empty-state view for Single File."""
    return not sources
