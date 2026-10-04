"""Stateless document preview fitting shared by PDF and PPTX projections."""

from __future__ import annotations


def fit_preview_size(viewport_width: int, viewport_height: int, aspect_ratio: float,
                     *, padding: int = 20, navigation_height: int = 0,
                     target_fraction: float = 0.8) -> tuple[int, int]:
    """Return an aspect-preserving rectangle inside the available viewport.

    This helper owns no document state.  Callers provide the projected source
    aspect ratio and actual host dimensions; PDF and PPTX retain independent
    renderers and state machines.
    """
    usable_width = max(1, int(viewport_width) - 2 * padding)
    usable_height = max(1, int(viewport_height) - 2 * padding - int(navigation_height))
    fraction = min(1.0, max(0.01, float(target_fraction)))
    width = max(1, round(usable_width * fraction))
    height = max(1, round(usable_height * fraction))
    ratio = max(0.01, float(aspect_ratio))
    fitted_width = min(width, max(1, round(height * ratio)))
    fitted_height = min(height, max(1, round(fitted_width / ratio)))
    return fitted_width, fitted_height
