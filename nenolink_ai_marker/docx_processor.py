"""Targeted, non-destructive DOCX disclosure pictures and metadata."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
import posixpath
import re
import tempfile
from typing import Literal
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
FOOTER_REL = f"{R}/footer"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
HEADER_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"
FOOTER_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"
CUSTOM_PROPERTIES = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
VT = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
CUSTOM_PROPERTIES_REL = f"{R}/custom-properties"
CUSTOM_PROPERTIES_TYPE = "application/vnd.openxmlformats-officedocument.custom-properties+xml"
CUSTOM_PROPERTIES_FORMAT_ID = "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}"
DEFAULT_PAGE_SIZE = (7_772_400, 10_058_400)  # 8.5 x 11 inches
DocxScope = Literal["first-page", "entire-document"]

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
    scope: DocxScope


class _DrawingIdAllocator:
    """Allocate small positive DrawingML IDs without package-wide collisions."""

    def __init__(self, used: set[int]):
        self.used = {value for value in used if value > 0}
        self.candidate = 1

    def allocate(self) -> int:
        while self.candidate in self.used:
            self.candidate += 1
        value = self.candidate
        self.used.add(value)
        self.candidate += 1
        return value


class DocxProcessor(DocumentProcessor):
    """Add conservative inline pictures to Word footers and write metadata.

    Existing package parts are copied byte-for-byte unless a footer must be
    cloned for a specific section. Inline drawings with paragraph alignment are
    intentionally used instead of floating, page-relative anchors because they
    are substantially more reliable in Microsoft Word.
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

    def process(
        self, request: ProcessingRequest, scope: DocxScope = "entire-document"
    ) -> DocxResult:
        request = request.validated()
        if scope not in {"first-page", "entire-document"}:
            raise ValueError(f"Unsupported DOCX marking scope: {scope}")
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
                document_xml = source_zip.read("word/document.xml")
                document = ET.fromstring(document_xml)
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
                sections = document.findall(f".//{_q(W, 'sectPr')}")
                if not sections:
                    raise ValueError("The document does not define any sections.")
                effective = self._effective_references(sections, relationship_targets)
                shape_counts = {"badge": 0, "logo": 0}
                drawing_ids = _DrawingIdAllocator(self._drawing_ids(source_zip, names))

                def clone_footer(section_index, reference_type, source_part, applicable):
                    part_kind = "footer"
                    part_name = self._available_name(names | set(additions), f"word/{part_kind}", ".xml")
                    if source_part and source_part in names:
                        part_xml = source_zip.read(source_part)
                        source_rels = self._rels_path(source_part)
                        part_rels = source_zip.read(source_rels) if source_rels in names else None
                    else:
                        part_xml = self._empty_part(part_kind); part_rels = None
                    # A cloned footer is a new story part. Its retained pictures
                    # must not reuse the source part's package-wide docPr IDs.
                    part_xml = self._remap_drawing_ids(part_xml, drawing_ids)
                    if applicable:
                        part_xml, part_rels = self._add_overlays(
                            part_xml, part_rels, part_name,
                            self._page_size(sections[section_index]), applicable, media_paths,
                            drawing_ids,
                        )
                        for item in applicable:
                            shape_counts[item[0]] += 1
                    additions[part_name] = part_xml
                    additions[self._rels_path(part_name)] = part_rels or self._serialize(ET.Element(_q(PKG_REL, "Relationships")))
                    self._ensure_part_override(content_types, part_name, part_kind)
                    relation_id = self._add_relationship(
                        document_rels, FOOTER_REL,
                        posixpath.relpath(part_name, "word"),
                    )
                    self._set_reference(sections[section_index], part_kind, reference_type, relation_id)

                if scope == "first-page":
                    first = sections[0]
                    had_title_page = first.find(_q(W, "titlePg")) is not None
                    if not had_title_page:
                        self._enable_title_page(first)
                    source_part = (
                        effective[0].get(("footer", "first"))
                        if had_title_page else effective[0].get(("footer", "default"))
                    )
                    clone_footer(0, "first", source_part, overlays)
                    # A later section with Different First Page and a linked first
                    # header/footer would otherwise inherit the newly marked part.
                    for section_index, section in enumerate(sections[1:], start=1):
                        if section.find(_q(W, "titlePg")) is None:
                            continue
                        if not self._has_reference(section, "footer", "first"):
                            clone_footer(
                                section_index, "first",
                                effective[section_index].get(("footer", "first")), [],
                            )
                else:
                    for section_index, section in enumerate(sections):
                        reference_types = ["default"]
                        if section.find(_q(W, "titlePg")) is not None:
                            reference_types.append("first")
                        if even_pages:
                            reference_types.append("even")
                        for reference_type in reference_types:
                            clone_footer(
                                section_index, reference_type,
                                effective[section_index].get(("footer", reference_type)),
                                overlays,
                            )

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
                    "word/document.xml": self._serialize_preserving_root_namespaces(document, document_xml),
                    "word/_rels/document.xml.rels": self._serialize(document_rels),
                    "[Content_Types].xml": self._serialize_content_types(content_types),
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
                    self._validate_word_package(temporary_path)
                    temporary_path.replace(request.destination)
                finally:
                    temporary_path.unlink(missing_ok=True)
        except (BadZipFile, KeyError, ET.ParseError) as error:
            raise ValueError(f"The document is missing a required DOCX part: {error}") from error

        return DocxResult(
            request.destination, info.section_count, shape_counts["badge"],
            shape_counts["logo"], True, scope,
        )

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
    def _has_reference(section: ET.Element, kind: str, reference_type: str) -> bool:
        return any(
            item.attrib.get(_q(W, "type"), "default") == reference_type
            for item in section.findall(_q(W, f"{kind}Reference"))
        )

    @staticmethod
    def _enable_title_page(section: ET.Element) -> None:
        title_page = ET.Element(_q(W, "titlePg"))
        later_elements = {
            _q(W, name) for name in
            ("textDirection", "bidi", "rtlGutter", "docGrid", "printerSettings", "sectPrChange")
        }
        insertion = next(
            (index for index, child in enumerate(section) if child.tag in later_elements),
            len(section),
        )
        section.insert(insertion, title_page)

    @classmethod
    def _effective_references(
        cls, sections: list[ET.Element], relationship_targets: dict[str, str]
    ) -> list[dict[tuple[str, str], str | None]]:
        """Resolve Word's linked-to-previous inheritance before any references change."""
        current = {
            (kind, reference_type): None
            for kind in ("header", "footer")
            for reference_type in ("default", "first", "even")
        }
        result = []
        for section in sections:
            for key in current:
                kind, reference_type = key
                explicit = cls._referenced_part(
                    section, kind, reference_type, relationship_targets
                )
                if explicit:
                    current[key] = explicit
            result.append(dict(current))
        return result

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
        drawing_ids: _DrawingIdAllocator,
    ) -> tuple[bytes, bytes]:
        root = ET.fromstring(part_xml)
        relationships = (
            ET.fromstring(rels_xml) if rels_xml
            else ET.Element(_q(PKG_REL, "Relationships"))
        )
        for kind, _image_bytes, pixels, settings in overlays:
            doc_id = drawing_ids.allocate()
            relation_id = self._add_relationship(
                relationships, IMAGE_REL,
                posixpath.relpath(media_paths[kind], str(PurePosixPath(part_name).parent)),
            )
            root.append(self._inline_picture_paragraph(
                relation_id, page_size, pixels, settings.position,
                settings.size_percent, f"Nenolink AI Marker {kind}", doc_id,
            ))
        return self._serialize_preserving_root_namespaces(root, part_xml), self._serialize(relationships)

    @staticmethod
    def _drawing_ids(source_zip: ZipFile, names: set[str]) -> set[int]:
        """Collect package-wide WordprocessingDrawing IDs before any cloning."""
        result: set[int] = set()
        for name in sorted(names):
            if not name.startswith("word/") or not name.endswith(".xml"):
                continue
            try:
                root = ET.fromstring(source_zip.read(name))
            except (KeyError, ET.ParseError):
                continue
            for item in root.findall(f".//{_q(WP, 'docPr')}"):
                value = item.attrib.get("id", "")
                if value.isdigit():
                    result.add(int(value))
        return result

    @classmethod
    def _remap_drawing_ids(
        cls, part_xml: bytes, drawing_ids: _DrawingIdAllocator
    ) -> bytes:
        """Give every retained picture in a cloned story part a fresh ID."""
        root = ET.fromstring(part_xml)
        changed = False
        for drawing in root.findall(f".//{_q(W, 'drawing')}"):
            for doc_properties in drawing.findall(f".//{_q(WP, 'docPr')}"):
                old_id = doc_properties.attrib.get("id", "")
                fresh_id = drawing_ids.allocate()
                doc_properties.attrib["id"] = str(fresh_id)
                for picture_properties in drawing.findall(f".//{_q(PIC, 'cNvPr')}"):
                    if picture_properties.attrib.get("id", "") == old_id:
                        picture_properties.attrib["id"] = str(fresh_id)
                changed = True
        return cls._serialize_preserving_root_namespaces(root, part_xml) if changed else part_xml

    @staticmethod
    def _inline_picture_paragraph(
        relation_id: str, page_size: tuple[int, int], pixels: tuple[int, int],
        position: str, size_percent: int, name: str, doc_id: int,
    ) -> ET.Element:
        page_width, page_height = page_size
        width = max(1, round(page_width * size_percent / 100))
        height = max(1, round(width * pixels[1] / max(1, pixels[0])))
        if height > page_height:
            scale = page_height / height; width = round(width * scale); height = page_height
        paragraph = ET.Element(_q(W, "p"))
        props = ET.SubElement(paragraph, _q(W, "pPr"))
        alignment = "center" if position == "center" else "left" if position.endswith("left") else "right"
        ET.SubElement(props, _q(W, "spacing"), {_q(W, "before"): "0", _q(W, "after"): "0"})
        ET.SubElement(props, _q(W, "jc"), {_q(W, "val"): alignment})
        run = ET.SubElement(paragraph, _q(W, "r")); drawing = ET.SubElement(run, _q(W, "drawing"))
        inline = ET.SubElement(drawing, _q(WP, "inline"), {
            "distT": "0", "distB": "0", "distL": "0", "distR": "0",
        })
        ET.SubElement(inline, _q(WP, "extent"), cx=str(width), cy=str(height))
        ET.SubElement(inline, _q(WP, "effectExtent"), l="0", t="0", r="0", b="0")
        ET.SubElement(inline, _q(WP, "docPr"), id=str(doc_id), name=name)
        frame_properties = ET.SubElement(inline, _q(WP, "cNvGraphicFramePr"))
        ET.SubElement(frame_properties, _q(A, "graphicFrameLocks"), noChangeAspect="1")
        graphic = ET.SubElement(inline, _q(A, "graphic"))
        data = ET.SubElement(graphic, _q(A, "graphicData"), uri=PIC)
        picture = ET.SubElement(data, _q(PIC, "pic"))
        non_visual = ET.SubElement(picture, _q(PIC, "nvPicPr"))
        ET.SubElement(non_visual, _q(PIC, "cNvPr"), id=str(doc_id), name=name)
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

    @staticmethod
    def _serialize_content_types(element: ET.Element) -> bytes:
        """Use the OPC-required default namespace accepted by Microsoft Word.

        ElementTree otherwise assigns an ``ns0`` prefix because the package
        relationships namespace is registered as the default namespace. Word's
        OPC reader rejects that representation and offers to repair the DOCX.
        """
        ET.register_namespace("", CONTENT_TYPES)
        try:
            return ET.tostring(element, encoding="utf-8", xml_declaration=True)
        finally:
            ET.register_namespace("", PKG_REL)

    @staticmethod
    def _serialize_preserving_root_namespaces(element: ET.Element, original: bytes) -> bytes:
        """Keep declarations referenced only by values such as mc:Ignorable."""
        serialized = ET.tostring(element, encoding="utf-8", xml_declaration=True)
        original_root_start = original.find(b"<", original.find(b"?>") + 2)
        original_root_end = original.find(b">", original_root_start)
        serialized_root_start = serialized.find(b"<", serialized.find(b"?>") + 2)
        serialized_root_end = serialized.find(b">", serialized_root_start)
        if original_root_start < 0 or original_root_end < 0 or serialized_root_start < 0 or serialized_root_end < 0:
            return serialized
        declarations = re.findall(
            rb"\s(xmlns(?::[A-Za-z_][\w.-]*)?)=(['\"])(.*?)\2",
            original[original_root_start:original_root_end],
        )
        root_tag = serialized[serialized_root_start:serialized_root_end]
        additions = []
        for attribute, quote, value in declarations:
            if re.search(rb"\s" + re.escape(attribute) + rb"=", root_tag):
                continue
            additions.append(b" " + attribute + b"=" + quote + value + quote)
        if not additions:
            return serialized
        return serialized[:serialized_root_end] + b"".join(additions) + serialized[serialized_root_end:]

    @classmethod
    def _validate_word_package(cls, path: Path) -> None:
        """Reject package defects that make Microsoft Word offer a repair.

        This deliberately validates OPC plumbing in addition to parsing XML:
        Python's ZIP and ElementTree readers accept namespace and relationship
        defects that Word's package reader rejects or silently repairs.
        """
        with ZipFile(path, "r") as archive:
            names = set(archive.namelist())
            content_types_xml = archive.read("[Content_Types].xml")
            if f'<Types xmlns="{CONTENT_TYPES}"'.encode() not in content_types_xml:
                raise ValueError("Invalid DOCX content-types namespace serialization.")
            content_types = ET.fromstring(content_types_xml)
            overrides: set[str] = set()
            for item in content_types.findall(_q(CONTENT_TYPES, "Override")):
                part = item.attrib.get("PartName", "").lstrip("/")
                if not part or part in overrides or part not in names:
                    raise ValueError(f"Invalid or duplicate DOCX content-type part: {part}")
                overrides.add(part)

            relationships_by_part: dict[str, set[str]] = {}
            for rels_name in sorted(name for name in names if name.endswith(".rels")):
                root = ET.fromstring(archive.read(rels_name))
                ids: set[str] = set()
                if rels_name == "_rels/.rels":
                    owner, base = "", ""
                else:
                    rels_path = PurePosixPath(rels_name)
                    owner = str(rels_path.parent.parent / rels_path.name[:-5])
                    base = str(PurePosixPath(owner).parent)
                relationships_by_part[owner] = ids
                for relation in root.findall(_q(PKG_REL, "Relationship")):
                    relation_id = relation.attrib.get("Id", "")
                    if not relation_id or relation_id in ids:
                        raise ValueError(f"Duplicate or missing relationship ID in {rels_name}: {relation_id}")
                    ids.add(relation_id)
                    if relation.attrib.get("TargetMode") == "External":
                        continue
                    target = relation.attrib.get("Target", "")
                    resolved = posixpath.normpath(posixpath.join(base, target)).lstrip("/")
                    if not target or resolved not in names:
                        raise ValueError(f"Broken DOCX relationship target in {rels_name}: {target}")

            drawing_ids: set[int] = set()
            for name in sorted(part for part in names if part.startswith("word/") and part.endswith(".xml")):
                part_xml = archive.read(name)
                root = ET.fromstring(part_xml)
                root_start = part_xml.find(b"<", part_xml.find(b"?>") + 2)
                root_end = part_xml.find(b">", root_start)
                declared_prefixes = {
                    match.decode("ascii")
                    for match in re.findall(rb"\sxmlns:([A-Za-z_][\w.-]*)=", part_xml[root_start:root_end])
                }
                for ignorable in re.findall(rb"Ignorable=['\"]([^'\"]+)['\"]", part_xml):
                    missing = set(ignorable.decode("ascii").split()) - declared_prefixes
                    if missing:
                        raise ValueError(f"Undefined ignorable namespace prefix in {name}: {sorted(missing)}")
                relation_ids = relationships_by_part.get(name, set())
                for element in root.iter():
                    for attribute, value in element.attrib.items():
                        if attribute in {_q(R, "id"), _q(R, "embed"), _q(R, "link")} and value not in relation_ids:
                            raise ValueError(f"Missing relationship {value} referenced by {name}.")
                for item in root.findall(f".//{_q(WP, 'docPr')}"):
                    value = item.attrib.get("id", "")
                    if not value.isdigit() or int(value) in drawing_ids:
                        raise ValueError(f"Invalid or duplicate DrawingML ID in {name}: {value}")
                    drawing_ids.add(int(value))
                for inline in root.findall(f".//{_q(WP, 'inline')}"):
                    if (
                        inline.find(_q(WP, "extent")) is None
                        or inline.find(_q(WP, "docPr")) is None
                        or inline.find(_q(A, "graphic")) is None
                    ):
                        raise ValueError(f"Incomplete inline DrawingML picture in {name}.")

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
