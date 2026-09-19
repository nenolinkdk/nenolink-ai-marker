"""Targeted, non-destructive PPTX disclosure overlays."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
import posixpath
import tempfile
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image

from .document_processing import (
    DocumentProcessor,
    ItemSelection,
    ProcessingRequest,
    ProcessorCapabilities,
)


P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
IMAGE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
EMU_PER_PIXEL = 9525

for prefix, uri in (("p", P), ("a", A), ("r", R)):
    ET.register_namespace(prefix, uri)
ET.register_namespace("", PKG_REL)


def _q(namespace: str, local: str) -> str:
    return f"{{{namespace}}}{local}"


@dataclass(frozen=True, slots=True)
class PptxResult:
    destination: Path
    slide_count: int
    selected_slides: tuple[int, ...]
    badge_shapes: int
    logo_shapes: int


class PptxProcessor(DocumentProcessor):
    capabilities = ProcessorCapabilities(
        "pptx",
        frozenset({".pptx"}),
        supports_logo=True,
        supports_metadata=False,
        supports_preview=False,
        supports_batch=False,
        supports_selection=True,
    )

    def process(
        self,
        request: ProcessingRequest,
        selection: ItemSelection | None = None,
    ) -> PptxResult:
        request = request.validated()
        if not self.capabilities.supports(request.source):
            raise ValueError("Only .pptx presentations are supported.")
        if not request.source.is_file():
            raise FileNotFoundError(request.source)
        badge_path = request.badge_path or Path(request.disclosure.badge_name)
        if not badge_path.is_file():
            raise FileNotFoundError(badge_path)
        logo_path = request.logo.path if request.logo.enabled else None
        if logo_path and not logo_path.is_file():
            raise FileNotFoundError(logo_path)

        try:
            with ZipFile(request.source, "r") as source_zip:
                names = set(source_zip.namelist())
                presentation = ET.fromstring(source_zip.read("ppt/presentation.xml"))
                presentation_rels = ET.fromstring(source_zip.read("ppt/_rels/presentation.xml.rels"))
                slides = self._ordered_slides(presentation, presentation_rels)
                selected = (selection or ItemSelection()).resolve(len(slides))
                slide_size = self._slide_size(presentation)
                badge_bytes, badge_pixels = self._png_bytes(badge_path)
                logo_data = self._png_bytes(logo_path) if logo_path else None
                badge_media = self._available_media_name(names, "nenolink-ai-marker-badge")
                logo_media = self._available_media_name(names | {badge_media}, "nenolink-company-logo") if logo_data else None

                replacements: dict[str, bytes] = {
                    badge_media: badge_bytes,
                    "[Content_Types].xml": self._ensure_png_content_type(source_zip.read("[Content_Types].xml")),
                }
                if logo_data and logo_media:
                    replacements[logo_media] = logo_data[0]
                badge_shapes = logo_shapes = 0
                for ordinal in selected:
                    slide_path = slides[ordinal - 1]
                    slide_xml = source_zip.read(slide_path)
                    rels_path = self._rels_path(slide_path)
                    rels_xml = source_zip.read(rels_path) if rels_path in names else None
                    slide_xml, rels_xml = self._add_overlay(
                        slide_xml, rels_xml, slide_size, badge_pixels,
                        request.disclosure.position, request.disclosure.size_percent,
                        request.disclosure.margin, request.disclosure.opacity,
                        slide_path, badge_media, "Nenolink AI Marker badge",
                    )
                    badge_shapes += 1
                    if logo_data and logo_media:
                        slide_xml, rels_xml = self._add_overlay(
                            slide_xml, rels_xml, slide_size, logo_data[1],
                            request.logo.position, request.logo.size_percent,
                            request.logo.margin, request.logo.opacity,
                            slide_path, logo_media, "Nenolink company logo",
                        )
                        logo_shapes += 1
                    replacements[slide_path] = slide_xml
                    replacements[rels_path] = rels_xml

                request.destination.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    prefix="nenolink-pptx-", suffix=".tmp", dir=request.destination.parent, delete=False
                ) as temporary:
                    temporary_path = Path(temporary.name)
                try:
                    with ZipFile(temporary_path, "w", ZIP_DEFLATED) as output_zip:
                        for info in source_zip.infolist():
                            output_zip.writestr(info, replacements.pop(info.filename, source_zip.read(info.filename)))
                        for name, data in replacements.items():
                            output_zip.writestr(name, data)
                    temporary_path.replace(request.destination)
                finally:
                    temporary_path.unlink(missing_ok=True)
        except KeyError as error:
            raise ValueError(f"The presentation is missing a required PPTX part: {error}") from error
        return PptxResult(request.destination, len(slides), selected, badge_shapes, logo_shapes)

    @staticmethod
    def _ordered_slides(presentation: ET.Element, relationships: ET.Element) -> list[str]:
        targets = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in relationships.findall(_q(PKG_REL, "Relationship"))
        }
        result = []
        for slide_id in presentation.findall(f".//{_q(P, 'sldId')}"):
            target = targets.get(slide_id.attrib.get(_q(R, "id"), ""))
            if not target:
                raise ValueError("A slide relationship is missing.")
            if target.startswith("/"):
                result.append(posixpath.normpath(target).lstrip("/"))
            else:
                result.append(posixpath.normpath(str(PurePosixPath("ppt") / target)))
        return result

    @staticmethod
    def _slide_size(presentation: ET.Element) -> tuple[int, int]:
        size = presentation.find(_q(P, "sldSz"))
        if size is None:
            raise ValueError("The presentation does not define a slide size.")
        return int(size.attrib["cx"]), int(size.attrib["cy"])

    @staticmethod
    def _png_bytes(path: Path) -> tuple[bytes, tuple[int, int]]:
        try:
            with Image.open(path) as opened:
                image = opened.convert("RGBA")
        except (OSError, Image.UnidentifiedImageError) as error:
            raise ValueError(f"Could not read overlay image: {error}") from error
        stream = BytesIO(); image.save(stream, format="PNG")
        return stream.getvalue(), image.size

    @staticmethod
    def _available_media_name(existing: set[str], stem: str) -> str:
        index = 1
        while True:
            suffix = "" if index == 1 else f"-{index}"
            candidate = f"ppt/media/{stem}{suffix}.png"
            if candidate not in existing:
                return candidate
            index += 1

    @staticmethod
    def _rels_path(slide_path: str) -> str:
        slide = PurePosixPath(slide_path)
        return str(slide.parent / "_rels" / f"{slide.name}.rels")

    @staticmethod
    def _ensure_png_content_type(xml: bytes) -> bytes:
        root = ET.fromstring(xml)
        has_png = any(
            item.attrib.get("Extension", "").casefold() == "png"
            for item in root.findall(_q(CONTENT_TYPES, "Default"))
        )
        if not has_png:
            ET.SubElement(root, _q(CONTENT_TYPES, "Default"), Extension="png", ContentType="image/png")
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _geometry(
        slide_size: tuple[int, int], pixels: tuple[int, int], position: str,
        size_percent: int, margin_pixels: int,
    ) -> tuple[int, int, int, int]:
        slide_width, slide_height = slide_size
        width = max(1, round(slide_width * size_percent / 100))
        height = max(1, round(width * pixels[1] / max(1, pixels[0])))
        if height > slide_height:
            scale = slide_height / height; width = max(1, round(width * scale)); height = slide_height
        margin = min(margin_pixels * EMU_PER_PIXEL, max(0, (slide_width - width) // 2), max(0, (slide_height - height) // 2))
        x = margin if position.endswith("left") else slide_width - width - margin
        y = margin if position.startswith("top") else slide_height - height - margin
        if position == "center":
            x, y = (slide_width - width) // 2, (slide_height - height) // 2
        return max(0, x), max(0, y), width, height

    def _add_overlay(
        self, slide_xml: bytes, rels_xml: bytes | None, slide_size: tuple[int, int],
        pixels: tuple[int, int], position: str, size_percent: int, margin: int,
        opacity: int, slide_path: str, media_path: str, shape_name: str,
    ) -> tuple[bytes, bytes]:
        slide = ET.fromstring(slide_xml)
        shape_tree = slide.find(f"./{_q(P, 'cSld')}/{_q(P, 'spTree')}")
        if shape_tree is None:
            raise ValueError("A slide has no shape tree.")
        used_ids = [int(item.attrib["id"]) for item in shape_tree.findall(f".//{_q(P, 'cNvPr')}") if item.attrib.get("id", "").isdigit()]
        shape_id = max(used_ids, default=0) + 1
        relationships = ET.fromstring(rels_xml) if rels_xml else ET.Element(_q(PKG_REL, "Relationships"))
        used_rel_ids = {item.attrib.get("Id", "") for item in relationships.findall(_q(PKG_REL, "Relationship"))}
        relation_index = 1
        while f"rId{relation_index}" in used_rel_ids:
            relation_index += 1
        relation_id = f"rId{relation_index}"
        relative_target = posixpath.relpath(media_path, start=str(PurePosixPath(slide_path).parent))
        ET.SubElement(relationships, _q(PKG_REL, "Relationship"), Id=relation_id, Type=IMAGE_REL, Target=relative_target)
        x, y, width, height = self._geometry(slide_size, pixels, position, size_percent, margin)

        picture = ET.Element(_q(P, "pic"))
        non_visual = ET.SubElement(picture, _q(P, "nvPicPr"))
        ET.SubElement(non_visual, _q(P, "cNvPr"), id=str(shape_id), name=shape_name)
        ET.SubElement(non_visual, _q(P, "cNvPicPr")); ET.SubElement(non_visual, _q(P, "nvPr"))
        fill = ET.SubElement(picture, _q(P, "blipFill")); blip = ET.SubElement(fill, _q(A, "blip"), {_q(R, "embed"): relation_id})
        if opacity < 100:
            ET.SubElement(blip, _q(A, "alphaModFix"), amt=str(opacity * 1000))
        stretch = ET.SubElement(fill, _q(A, "stretch")); ET.SubElement(stretch, _q(A, "fillRect"))
        properties = ET.SubElement(picture, _q(P, "spPr")); transform = ET.SubElement(properties, _q(A, "xfrm"))
        ET.SubElement(transform, _q(A, "off"), x=str(x), y=str(y)); ET.SubElement(transform, _q(A, "ext"), cx=str(width), cy=str(height))
        geometry = ET.SubElement(properties, _q(A, "prstGeom"), prst="rect"); ET.SubElement(geometry, _q(A, "avLst"))
        extension = shape_tree.find(_q(P, "extLst")); insertion = list(shape_tree).index(extension) if extension is not None else len(shape_tree)
        shape_tree.insert(insertion, picture)
        return (
            ET.tostring(slide, encoding="utf-8", xml_declaration=True),
            ET.tostring(relationships, encoding="utf-8", xml_declaration=True),
        )
