from pathlib import Path
from typing import Protocol

from PIL import Image, PngImagePlugin

from .metadata import MarkerMetadata
from .models import MarkerSettings

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class MediaProcessor(Protocol):
    """Extension point for image processing now and video processing in v0.2."""

    def supports(self, path: Path) -> bool: ...

    def process(self, source: Path, overlay: Path, settings: MarkerSettings, logo: Path | None = None) -> Image.Image: ...


class ImageProcessor:
    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in SUPPORTED_EXTENSIONS

    @staticmethod
    def _position(
        image_size: tuple[int, int], badge_size: tuple[int, int], position: str, margin: int
    ) -> tuple[int, int]:
        image_width, image_height = image_size
        badge_width, badge_height = badge_size
        left = margin
        right = max(0, image_width - badge_width - margin)
        top = margin
        bottom = max(0, image_height - badge_height - margin)
        positions = {
            "top-left": (left, top),
            "top-right": (right, top),
            "bottom-left": (left, bottom),
            "bottom-right": (right, bottom),
            "center": (max(0,(image_width-badge_width)//2),max(0,(image_height-badge_height)//2)),
        }
        return positions[settings_position(position)]

    def process(self, source: Path, overlay: Path, settings: MarkerSettings, logo: Path | None = None) -> Image.Image:
        settings.validated()
        if not self.supports(source):
            raise ValueError(f"Unsupported image type: {source.suffix or 'no extension'}")
        try:
            with Image.open(source) as opened:
                base = opened.convert("RGBA")
            with Image.open(overlay) as opened_badge:
                badge = opened_badge.convert("RGBA")
        except (OSError, Image.UnidentifiedImageError) as error:
            raise ValueError(f"Could not open image: {error}") from error

        result = base.copy()
        self._composite(result, badge, settings.position, settings.size_percent, settings.margin, settings.opacity)
        if settings.logo_enabled and logo:
            if logo.suffix.lower() not in SUPPORTED_EXTENSIONS:
                raise ValueError(f"Unsupported logo type: {logo.suffix or 'no extension'}")
            try:
                with Image.open(logo) as opened_logo:
                    logo_image = opened_logo.convert("RGBA")
            except (OSError, Image.UnidentifiedImageError) as error:
                raise ValueError(f"Could not open logo: {error}") from error
            self._composite(result, logo_image, settings.logo_position, settings.logo_size_percent, settings.logo_margin, settings.logo_opacity)
        return result

    def _composite(self, base: Image.Image, overlay: Image.Image, position: str, size_percent: int, margin: int, opacity: int) -> None:
        effective_margin = min(margin, (base.width - 1) // 2, (base.height - 1) // 2)
        available_width = max(1, base.width - (2 * effective_margin))
        available_height = max(1, base.height - (2 * effective_margin))
        target_width = min(available_width, max(1, round(base.width * size_percent / 100)))
        target_height = max(1, round(overlay.height * target_width / max(1, overlay.width)))
        if target_height > available_height:
            scale = available_height / target_height
            target_width = max(1, round(target_width * scale))
            target_height = available_height
        overlay = overlay.resize((target_width, target_height), Image.Resampling.LANCZOS)
        if opacity < 100:
            alpha = overlay.getchannel("A").point(lambda value: round(value * opacity / 100))
            overlay.putalpha(alpha)
        base.alpha_composite(overlay, self._position(base.size, overlay.size, position, effective_margin))

    def save(self, image: Image.Image, destination: Path, metadata: MarkerMetadata | None = None) -> bool:
        """Save an image and return whether requested AI Marker metadata was written.

        If a format encoder rejects metadata, retry the otherwise valid visible
        output without metadata instead of losing the user's marked file.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        suffix = destination.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported output type: {suffix}")

        def write(include_metadata: bool) -> None:
            if suffix in {".jpg", ".jpeg"}:
                options = {"format": "JPEG", "quality": 95}
                if include_metadata and metadata:
                    exif = Image.Exif()
                    exif[270] = metadata.description
                    exif[305] = metadata.software
                    exif[37510] = b"ASCII\x00\x00\x00" + metadata.description.encode("utf-8")
                    options["exif"] = exif
                    options["xmp"] = metadata.xmp
                image.convert("RGB").save(destination, **options)
            elif suffix == ".png":
                options = {"format": "PNG"}
                if include_metadata and metadata:
                    pnginfo = PngImagePlugin.PngInfo()
                    pnginfo.add_text("Software", metadata.software)
                    pnginfo.add_text("AI Label", metadata.ai_label)
                    pnginfo.add_text("Marker Version", metadata.marker_version)
                    pnginfo.add_text("NenolinkAIMarker", metadata.identifier)
                    options["pnginfo"] = pnginfo
                image.save(destination, **options)
            else:
                options = {"format": "WEBP", "quality": 95}
                if include_metadata and metadata:
                    exif = Image.Exif()
                    exif[270] = metadata.description
                    exif[305] = metadata.software
                    options["exif"] = exif.tobytes()
                    options["xmp"] = metadata.xmp
                image.save(destination, **options)

        if metadata:
            try:
                write(True)
                return True
            except (OSError, ValueError, TypeError):
                write(False)
                return False
        write(False)
        return False


def settings_position(position: str) -> str:
    return position if position in {"top-left", "top-right", "bottom-left", "bottom-right", "center"} else "bottom-right"


def output_path(source: Path, output_directory: Path | None = None, filename_suffix: str = "_ai") -> Path:
    directory = output_directory or source.parent
    candidate = directory / f"{source.stem}{filename_suffix}{source.suffix}"
    counter = 2
    while candidate.exists() or candidate.resolve() == source.resolve():
        candidate = directory / f"{source.stem}{filename_suffix}_{counter}{source.suffix}"
        counter += 1
    return candidate
