"""Targeted, non-destructive DOCX disclosure overlays and metadata."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
import posixpath
import tempfile
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from PIL import Image

from .document_limits import DocumentMetrics, enforce_hard_limit
from .document_processing import DocumentProcessor, ProcessingRequest, ProcessorCapabilities
from .metadata import MarkerMetadata, marker_metadata


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
IMAGE_REL = f"{R}/image"
HEADER_REL = f"{R}/header"
FOOTER_REL = f"{R}/footer"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
HEADER_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"
FOOTER_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"
CUSTOM_PROPERTIES = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
VT = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
CUSTOM_PROPERTIES_REL = f"{R}/custom-properties"
CUSTOM_PROPERTIES_TYPE = "application/vnd.openxmlformats-officedocument.custom-properties+xml"
CUSTOM_PROPERTIES_FORMAT_ID = "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}"
EMU_PER_PIXEL = 9525
DEFAULT_PAGE_SIZE = (7_772_400, 10_058_400)  # 8.5 x 11 inches

for prefix, uri in (("w", W), ("wp", WP), ("a", A), ("pic", PIC), ("r", R)):
    ET.register_namespace(prefix, uri)
ET.register_namespace("", PKG_REL)
ET.register_namespace("cp", CUSTOM_PROPERTIES)
ET.register_namespace("vt", VT)


def _q(namespace: str, local: str) -> str:
    return f"{{{namespace}}}{local}"


@dataclass(frozen=True, slots=True)
class DocxInfo:
    metrics: DocumentMetrics
    section_count: int


@dataclass(frozen=True, slots=True)
class DocxResult:
    destination: Path
    section_count: int
    badge_shapes: int
    logo_shapes: int
    metadata_written: bool


class DocxProcessor(DocumentProcessor):
    """Patch only header/footer relationships, image parts and custom properties.

    Floating page-relative drawings avoid reflowing body paragraphs, tables and
    images. Existing package parts are copied byte-for-byte unless they must be
    cloned to add a disclosure to a specific section.
    """

    capabilities = ProcessorCapabilities(
        "docx", frozenset({".docx"}), supports_logo=True,
        supports_metadata=True, supports_preview=True,
    )

    @classmethod
    def inspect(cls, source: Path) -> DocxInfo:
        source = Path(source)
        if source.suffix.casefold() != ".docx":
            raise ValueError("Only .docx documents are supported.")
        try:
            with ZipFile(source, "r") as archive:
                document = ET.fromstring(archive.read("word/document.xml"))
        except (BadZipFile, KeyError, ET.ParseError, OSError) as error:
            raise ValueError(f"Could not read DOCX: {error}") from error
        sections = document.findall(f".//{_q(W, 'sectPr')}")
        return DocxInfo(DocumentMetrics(source.stat().st_size, 0), max(1, len(sections)))

    def process(self, request: ProcessingRequest) -> DocxResult:
        request = request.validated()
        if not self.capabilities.supports(request.source):
            raise ValueError("Only .docx documents are supported.")
        badge_path = request.badge_path if request.badge_path and request.badge_path.is_file() else None
        logo_path = request.logo.path if request.logo.enabled and request.logo.path and request.logo.path.is_file() else None
        if request.badge_path and not badge_path:
            raise FileNotFoundError(request.badge_path)
        if request.logo.enabled and not logo_path:
            raise FileNotFoundError(request.logo.path)
        if not badge_path and not logo_path:
            raise ValueError("At least one DOCX overlay must be enabled.")

        info = self.inspect(request.source)
        enforce_hard_limit("docx", info.metrics)
        overlays = []
        if badge_path:
            overlays.append(("badge", *self._png_bytes(badge_path, request.disclosure.opacity), request.disclosure))
        if logo_path:
            overlays.append(("logo", *self._png_bytes(logo_path, request.logo.opacity), request.logo))

        try:
            with ZipFile(request.source, "r") as source_zip:
                names = set(source_zip.namelist())
                document = ET.fromstring(source_zip.read("word/document.xml"))
                document_rels = ET.fromstring(source_zip.read("word/_rels/document.xml.rels"))
                content_types = ET.fromstring(source_zip.read("[Content_Types].xml"))
                replacements: dict[str, bytes] = {}
                additions: dict[str, bytes] = {}
                media_paths: dict[str, str] = {}
                for kind, image_bytes, _pixels, _settings in overlays:
                    media_path = self._available_name(names | set(additions), f"word/media/nenolink-{kind}", ".png")
                    additions[media_path] = image_bytes
                    media_paths[kind] = media_path
                self._ensure_png_content_type(content_types)

                relationship_targets = {
                    relation.attrib.get("Id", ""): relation.attrib.get("Target", "")
                    for relation in document_rels.findall(_q(PKG_REL, "Relationship"))
                }
                settings = source_zip.read("word/settings.xml") if "word/settings.xml" in names else b""
                even_pages = b"evenAndOddHeaders" in settings
                shape_count = 0
                sections = document.findall(f".//{_q(W, 'sectPr')}")
                for section_index, section in enumerate(sections or [document], start=1):
                    page_size = self._page_size(section)
                    reference_types = ["default"]
                    if section.find(_q(W, "titlePg")) is not None:
                        reference_types.append("first")
                    if even_pages:
                        reference_types.append("even")
                    for part_kind in ("header", "footer"):
                        applicable = [item for item in overlays if self._part_kind(item[3].position) == part_kind]
                        if not applicable:
                            continue
                        for reference_type in reference_types:
                            source_part = self._referenced_part(
                                section, part_kind, reference_type, relationship_targets
                            )
                            part_name = self._available_name(
                                names | set(additions), f"word/{part_kind}", ".xml"
                            )
                            if source_part and source_part in names:
                                part_xml = source_zip.read(source_part)
                                source_rels = self._rels_path(source_part)
                                part_rels = source_zip.read(source_rels) if source_rels in names else None
                            else:
                                part_xml = self._empty_part(part_kind)
                                part_rels = None
                            part_xml, part_rels = self._add_overlays(
                                part_xml, part_rels, part_name, page_size,
                                applicable, media_paths,
                            )
                            additions[part_name] = part_xml
                            additions[self._rels_path(part_name)] = part_rels
                            self._ensure_part_override(content_types, part_name, part_kind)
                            relation_id = self._add_relationship(
                                document_rels,
                                HEADER_REL if part_kind == "header" else FOOTER_REL,
                                posixpath.relpath(part_name, "word"),
                            )
                            self._set_reference(section, part_kind, reference_type, relation_id)
                            shape_count += len(applicable)

                metadata = request.metadata or marker_metadata(
                    request.disclosure.badge_name, request.disclosure.label
                )
                package_rels = (
                    source_zip.read("_rels/.rels") if "_rels/.rels" in names else None
                )
                custom = (
                    source_zip.read("docProps/custom.xml")
                    if "docProps/custom.xml" in names else None
                )
                package_rels, custom = self._metadata_parts(
                    package_rels, custom, metadata, request.disclosure.language
                )
                self._ensure_custom_override(content_types)
                replacements.update({
                    "word/document.xml": self._serialize(document),
                    "word/_rels/document.xml.rels": self._serialize(document_rels),
                    "[Content_Types].xml": self._serialize(content_types),
                    "_rels/.rels": package_rels,
                    "docProps/custom.xml": custom,
                })
                request.destination.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    prefix="nenolink-docx-", suffix=".tmp",
                    dir=request.destination.parent, delete=False,
                ) as temporary:
                    temporary_path = Path(temporary.name)
                try:
                    with ZipFile(temporary_path, "w", ZIP_DEFLATED) as output_zip:
                        for entry in source_zip.infolist():
                            output_zip.writestr(
                                entry,
                                replacements.pop(entry.filename, additions.pop(entry.filename, source_zip.read(entry.filename))),
                            )
                        for name, data in {**replacements, **additions}.items():
                            output_zip.writestr(name, data)
                    temporary_path.replace(request.destination)
                finally:
                    temporary_path.unlink(missing_ok=True)
        except (BadZipFile, KeyError, ET.ParseError) as error:
            raise ValueError(f"The document is missing a required DOCX part: {error}") from error

        per_section = shape_count
        badge_shapes = per_section if badge_path and not logo_path else (per_section // 2 if badge_path else 0)
        logo_shapes = per_section if logo_path and not badge_path else (per_section // 2 if logo_path else 0)
        return DocxResult(request.destination, info.section_count, badge_shapes, logo_shapes, True)

    @staticmethod
    def _part_kind(position: str) -> str:
        return "footer" if position.startswith("bottom") else "header"

    @staticmethod
    def _page_size(section: ET.Element) -> tuple[int, int]:
        size = section.find(_q(W, "pgSz"))
        if size is None:
            return DEFAULT_PAGE_SIZE
        # Word twips -> EMU.
        return int(size.attrib.get(_q(W, "w"), "12240")) * 635, int(size.attrib.get(_q(W, "h"), "15840")) * 635

    @staticmethod
    def _png_bytes(path: Path, opacity: int) -> tuple[bytes, tuple[int, int]]:
        try:
            with Image.open(path) as opened:
                image = opened.convert("RGBA")
        except (OSError, Image.UnidentifiedImageError) as error:
            raise ValueError(f"Could not read overlay image: {error}") from error
        alpha = image.getchannel("A").point(lambda value: round(value * opacity / 100))
        image.putalpha(alpha)
        stream = BytesIO(); image.save(stream, "PNG")
        return stream.getvalue(), image.size

    @staticmethod
    def _available_name(existing: set[str], stem: str, suffix: str) -> str:
        index = 1
        while True:
            candidate = f"{stem}{'' if index == 1 else index}{suffix}"
            if candidate not in existing:
                return candidate
            index += 1

    @staticmethod
    def _rels_path(part_name: str) -> str:
        part = PurePosixPath(part_name)
        return str(part.parent / "_rels" / f"{part.name}.rels")

    @staticmethod
    def _empty_part(kind: str) -> bytes:
        root = ET.Element(_q(W, "hdr" if kind == "header" else "ftr"))
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _referenced_part(
        section: ET.Element, kind: str, reference_type: str,
        relationship_targets: dict[str, str],
    ) -> str | None:
        for reference in section.findall(_q(W, f"{kind}Reference")):
            if reference.attrib.get(_q(W, "type"), "default") == reference_type:
                target = relationship_targets.get(reference.attrib.get(_q(R, "id"), ""))
                if target:
                    return posixpath.normpath(posixpath.join("word", target)).lstrip("/")
        return None

    @staticmethod
    def _set_reference(section: ET.Element, kind: str, reference_type: str, relation_id: str) -> None:
        matches = [
            item for item in section.findall(_q(W, f"{kind}Reference"))
            if item.attrib.get(_q(W, "type"), "default") == reference_type
        ]
        reference = matches[0] if matches else ET.Element(_q(W, f"{kind}Reference"))
        reference.attrib[_q(W, "type")] = reference_type
        reference.attrib[_q(R, "id")] = relation_id
        if not matches:
            section.insert(0, reference)

    @staticmethod
    def _add_relationship(root: ET.Element, relation_type: str, target: str) -> str:
        used = {item.attrib.get("Id", "") for item in root.findall(_q(PKG_REL, "Relationship"))}
        index = 1
        while f"rId{index}" in used:
            index += 1
        relation_id = f"rId{index}"
        ET.SubElement(root, _q(PKG_REL, "Relationship"), Id=relation_id, Type=relation_type, Target=target)
        return relation_id

    def _add_overlays(
        self, part_xml: bytes, rels_xml: bytes | None, part_name: str,
        page_size: tuple[int, int], overlays: list[tuple], media_paths: dict[str, str],
    ) -> tuple[bytes, bytes]:
        root = ET.fromstring(part_xml)
        relationships = (
            ET.fromstring(rels_xml) if rels_xml
            else ET.Element(_q(PKG_REL, "Relationships"))
        )
        doc_id = 10_000
        for kind, _image_bytes, pixels, settings in overlays:
            relation_id = self._add_relationship(
                relationships, IMAGE_REL,
                posixpath.relpath(media_paths[kind], str(PurePosixPath(part_name).parent)),
            )
            root.append(self._overlay_paragraph(
                relation_id, page_size, pixels, settings.position,
                settings.size_percent, settings.margin, f"Nenolink AI Marker {kind}", doc_id,
            ))
            doc_id += 1
        return self._serialize(root), self._serialize(relationships)

    @staticmethod
    def _overlay_paragraph(
        relation_id: str, page_size: tuple[int, int], pixels: tuple[int, int],
        position: str, size_percent: int, margin_pixels: int, name: str, doc_id: int,
    ) -> ET.Element:
        page_width, page_height = page_size
        width = max(1, round(page_width * size_percent / 100))
        height = max(1, round(width * pixels[1] / max(1, pixels[0])))
        if height > page_height:
            scale = page_height / height; width = round(width * scale); height = page_height
        margin = max(0, margin_pixels * EMU_PER_PIXEL)
        x = margin if position.endswith("left") else page_width - width - margin
        y = margin if position.startswith("top") else page_height - height - margin
        if position == "center":
            x, y = (page_width - width) // 2, (page_height - height) // 2
        x, y = max(0, x), max(0, y)

        paragraph = ET.Element(_q(W, "p"))
        props = ET.SubElement(paragraph, _q(W, "pPr"))
        ET.SubElement(props, _q(W, "spacing"), {_q(W, "before"): "0", _q(W, "after"): "0", _q(W, "line"): "1", _q(W, "lineRule"): "exact"})
        run = ET.SubElement(paragraph, _q(W, "r")); drawing = ET.SubElement(run, _q(W, "drawing"))
        anchor = ET.SubElement(drawing, _q(WP, "anchor"), {
            "distT": "0", "distB": "0", "distL": "0", "distR": "0",
            "simplePos": "0", "relativeHeight": str(251658240 + doc_id),
            "behindDoc": "0", "locked": "0", "layoutInCell": "1", "allowOverlap": "1",
        })
        ET.SubElement(anchor, _q(WP, "simplePos"), x="0", y="0")
        horizontal = ET.SubElement(anchor, _q(WP, "positionH"), relativeFrom="page")
        ET.SubElement(horizontal, _q(WP, "posOffset")).text = str(x)
        vertical = ET.SubElement(anchor, _q(WP, "positionV"), relativeFrom="page")
        ET.SubElement(vertical, _q(WP, "posOffset")).text = str(y)
        ET.SubElement(anchor, _q(WP, "extent"), cx=str(width), cy=str(height))
        ET.SubElement(anchor, _q(WP, "effectExtent"), l="0", t="0", r="0", b="0")
        ET.SubElement(anchor, _q(WP, "wrapNone"))
        ET.SubElement(anchor, _q(WP, "docPr"), id=str(doc_id), name=name)
        ET.SubElement(anchor, _q(WP, "cNvGraphicFramePr"))
        graphic = ET.SubElement(anchor, _q(A, "graphic"))
        data = ET.SubElement(graphic, _q(A, "graphicData"), uri=PIC)
        picture = ET.SubElement(data, _q(PIC, "pic"))
        non_visual = ET.SubElement(picture, _q(PIC, "nvPicPr"))
        ET.SubElement(non_visual, _q(PIC, "cNvPr"), id="0", name=name)
        ET.SubElement(non_visual, _q(PIC, "cNvPicPr"))
        fill = ET.SubElement(picture, _q(PIC, "blipFill"))
        ET.SubElement(fill, _q(A, "blip"), {_q(R, "embed"): relation_id})
        stretch = ET.SubElement(fill, _q(A, "stretch")); ET.SubElement(stretch, _q(A, "fillRect"))
        shape = ET.SubElement(picture, _q(PIC, "spPr"))
        transform = ET.SubElement(shape, _q(A, "xfrm"))
        ET.SubElement(transform, _q(A, "off"), x="0", y="0")
        ET.SubElement(transform, _q(A, "ext"), cx=str(width), cy=str(height))
        geometry = ET.SubElement(shape, _q(A, "prstGeom"), prst="rect")
        ET.SubElement(geometry, _q(A, "avLst"))
        return paragraph

    @staticmethod
    def _ensure_png_content_type(root: ET.Element) -> None:
        if not any(item.attrib.get("Extension", "").casefold() == "png" for item in root.findall(_q(CONTENT_TYPES, "Default"))):
            ET.SubElement(root, _q(CONTENT_TYPES, "Default"), Extension="png", ContentType="image/png")

    @staticmethod
    def _ensure_part_override(root: ET.Element, part_name: str, kind: str) -> None:
        part = f"/{part_name}"
        if not any(item.attrib.get("PartName") == part for item in root.findall(_q(CONTENT_TYPES, "Override"))):
            ET.SubElement(root, _q(CONTENT_TYPES, "Override"), PartName=part, ContentType=HEADER_TYPE if kind == "header" else FOOTER_TYPE)

    @staticmethod
    def _ensure_custom_override(root: ET.Element) -> None:
        if not any(item.attrib.get("PartName") == "/docProps/custom.xml" for item in root.findall(_q(CONTENT_TYPES, "Override"))):
            ET.SubElement(root, _q(CONTENT_TYPES, "Override"), PartName="/docProps/custom.xml", ContentType=CUSTOM_PROPERTIES_TYPE)

    @classmethod
    def _metadata_parts(
        cls, package_rels_xml: bytes | None, custom_xml: bytes | None,
        metadata: MarkerMetadata, language: str,
    ) -> tuple[bytes, bytes]:
        relationships = ET.fromstring(package_rels_xml) if package_rels_xml else ET.Element(_q(PKG_REL, "Relationships"))
        if not any(item.attrib.get("Type") == CUSTOM_PROPERTIES_REL for item in relationships.findall(_q(PKG_REL, "Relationship"))):
            cls._add_relationship(relationships, CUSTOM_PROPERTIES_REL, "docProps/custom.xml")
        properties = ET.fromstring(custom_xml) if custom_xml else ET.Element(_q(CUSTOM_PROPERTIES, "Properties"))
        values = {
            "Nenolink AI Marker": metadata.identifier,
            "Software": metadata.software,
            "AI Label": metadata.ai_label,
            "Marker Version": metadata.marker_version,
            "Disclosure Language": language,
            "AI Transparency Notice": "Disclosure statement only; not proof of authorship or AI provenance.",
        }
        existing = {item.attrib.get("name", ""): item for item in properties.findall(_q(CUSTOM_PROPERTIES, "property"))}
        used = {int(item.attrib["pid"]) for item in existing.values() if item.attrib.get("pid", "").isdigit()}
        next_pid = max(used, default=1) + 1
        for name, value in values.items():
            item = existing.get(name)
            if item is None:
                while next_pid in used:
                    next_pid += 1
                item = ET.SubElement(properties, _q(CUSTOM_PROPERTIES, "property"), fmtid=CUSTOM_PROPERTIES_FORMAT_ID, pid=str(next_pid), name=name)
                used.add(next_pid); next_pid += 1
            else:
                for child in list(item):
                    item.remove(child)
            ET.SubElement(item, _q(VT, "lpwstr")).text = str(value)
        return cls._serialize(relationships), cls._serialize(properties)

    @staticmethod
    def read_metadata(path: Path) -> dict[str, str]:
        try:
            with ZipFile(path, "r") as archive:
                root = ET.fromstring(archive.read("docProps/custom.xml"))
        except (BadZipFile, KeyError, OSError, ET.ParseError):
            return {}
        values = {}
        for item in root.findall(_q(CUSTOM_PROPERTIES, "property")):
            value = next(iter(item), None)
            if item.attrib.get("name") and value is not None:
                values[item.attrib["name"]] = value.text or ""
        return values

    @staticmethod
    def _serialize(element: ET.Element) -> bytes:
        return ET.tostring(element, encoding="utf-8", xml_declaration=True)
