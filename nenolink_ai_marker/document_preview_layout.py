"""Stateless document preview fitting shared by PDF and PPTX projections."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PreviewGeometryReceipt:
    viewport_width: int
    viewport_height: int
    source_width: float
    source_height: float
    target_fraction: float
    rendered_width: int
    rendered_height: int
    limiting_dimension: str
    measured_fraction: float
    actual_available_width: int
    actual_available_height: int
    canonical_max_width: int
    canonical_max_height: int
    effective_width: int
    effective_height: int


def fit_preview_geometry(viewport_width: int, viewport_height: int, source_width: float,
                         source_height: float, *, target_fraction: float = 0.8,
                         canonical_max: tuple[int, int] = (760, 470)) -> PreviewGeometryReceipt:
    """Fit a source into the measured black viewport and return a receipt."""
    actual_w = max(1, int(viewport_width)); actual_h = max(1, int(viewport_height))
    max_w, max_h = max(1, int(canonical_max[0])), max(1, int(canonical_max[1]))
    vw, vh = min(actual_w, max_w), min(actual_h, max_h)
    sw = max(1.0, float(source_width)); sh = max(1.0, float(source_height))
    fraction = min(1.0, max(0.01, float(target_fraction)))
    target_w = vw * fraction; target_h = vh * fraction
    width_scale = target_w / sw; height_scale = target_h / sh
    scale = min(width_scale, height_scale)
    rendered_w = max(1, round(sw * scale)); rendered_h = max(1, round(sh * scale))
    limiting = "width" if width_scale <= height_scale else "height"
    measured = rendered_w / vw if limiting == "width" else rendered_h / vh
    return PreviewGeometryReceipt(vw, vh, sw, sh, fraction, rendered_w, rendered_h, limiting, measured, actual_w, actual_h, max_w, max_h, vw, vh)


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
