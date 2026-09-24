from hashlib import sha256
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from PIL import Image

from nenolink_ai_marker import __version__
from nenolink_ai_marker.docx_preview import DocxPreviewRenderer
from nenolink_ai_marker.docx_processor import A, CONTENT_TYPES, PIC, DocxProcessor, W, WP, _q
from nenolink_ai_marker.document_processing import DisclosureSettings, LogoSettings, ProcessingRequest
from nenolink_ai_marker.inspection import inspect_file
from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.app import MarkerApp


R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
WP14 = "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"


def _create_docx(
    path: Path, *, sections: int = 1, existing_metadata: bool = True,
    first_page_headers: bool = False, later_title_page: bool = False,
) -> None:
    section_xml = "".join(
        f'<w:p><w:pPr><w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr></w:pPr><w:r><w:t>Section {index}</w:t></w:r></w:p>'
        for index in range(1, sections)
    )
    document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{W}" xmlns:r="{R}" xmlns:wp="{WP}" xmlns:a="{A}" xmlns:pic="{PIC}" xmlns:mc="{MC}" xmlns:w14="{W14}" xmlns:wp14="{WP14}" mc:Ignorable="w14 wp14"><w:body>
<w:p><w:r><w:t>Ordinary Unicode text ÆØÅ 日本語</w:t></w:r></w:p>
<w:p><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="914400" cy="457200"/><wp:docPr id="7" name="Existing picture"/><wp:cNvGraphicFramePr/><a:graphic><a:graphicData uri="{PIC}"><pic:pic><pic:nvPicPr><pic:cNvPr id="7" name="Existing picture"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="rId1"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="914400" cy="457200"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>
<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Table value</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
<w:p><w:r><w:t>Additional realistic body content before page two.</w:t><w:br w:type="page"/></w:r></w:p>
<w:p><w:r><w:t>Page two contains ordinary paragraphs, a table and an image.</w:t><w:br w:type="page"/></w:r></w:p>
<w:p><w:r><w:t>Page three verifies multi-page footer behaviour.</w:t></w:r></w:p>
{section_xml}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>
</w:body></w:document>'''
    content_types = f'''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
<Override PartName="/word/headerFirst.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
<Override PartName="/word/footerFirst.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
<Override PartName="/docProps/custom.xml" ContentType="application/vnd.openxmlformats-officedocument.custom-properties+xml"/>
</Types>'''
    root_rels = f'''<Relationships xmlns="{PKG}">
<Relationship Id="rId1" Type="{R}/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="{R}/custom-properties" Target="docProps/custom.xml"/>
</Relationships>'''
    document = document.replace('<w:sectPr><w:pgSz', '<w:sectPr><w:headerReference w:type="default" r:id="rId2"/><w:footerReference w:type="default" r:id="rId3"/><w:pgSz')
    if first_page_headers:
        document = document.replace('<w:sectPr>', '<w:sectPr><w:headerReference w:type="first" r:id="rId4"/><w:footerReference w:type="first" r:id="rId5"/><w:titlePg/>', 1)
    if later_title_page and sections > 1:
        prefix, final = document.rsplit('<w:sectPr>', 1)
        document = prefix + '<w:sectPr><w:titlePg/>' + final
    doc_rels = f'''<Relationships xmlns="{PKG}"><Relationship Id="rId1" Type="{R}/image" Target="media/existing.png"/><Relationship Id="rId2" Type="{R}/header" Target="header1.xml"/><Relationship Id="rId3" Type="{R}/footer" Target="footer1.xml"/><Relationship Id="rId4" Type="{R}/header" Target="headerFirst.xml"/><Relationship Id="rId5" Type="{R}/footer" Target="footerFirst.xml"/></Relationships>'''
    custom = '''<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="2" name="Customer Code"><vt:lpwstr>Preserve me</vt:lpwstr></property></Properties>'''
    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/_rels/document.xml.rels", doc_rels)
        archive.writestr("word/header1.xml", f'<w:hdr xmlns:w="{W}"><w:p><w:r><w:t>Existing header</w:t></w:r></w:p></w:hdr>')
        archive.writestr("word/footer1.xml", f'<w:ftr xmlns:w="{W}"><w:p><w:r><w:t>Existing footer</w:t></w:r></w:p></w:ftr>')
        archive.writestr("word/headerFirst.xml", f'<w:hdr xmlns:w="{W}"><w:p><w:r><w:t>Existing first header</w:t></w:r></w:p></w:hdr>')
        archive.writestr("word/footerFirst.xml", f'<w:ftr xmlns:w="{W}"><w:p><w:r><w:t>Existing first footer</w:t></w:r></w:p></w:ftr>')
        existing_image = BytesIO(); Image.new("RGB", (120, 60), "#336699").save(existing_image, "PNG")
        archive.writestr("word/media/existing.png", existing_image.getvalue())
        archive.writestr("custom/untouched.bin", b"untouched-package-part")
        if existing_metadata:
            archive.writestr("docProps/custom.xml", custom)


def _overlay(path: Path, colour, size=(180, 60)) -> None:
    Image.new("RGBA", size, colour).save(path)


def _request(
    tmp_path: Path, *, badge=True, logo=False, unicode=False, sections=1,
    first_page_headers=False, later_title_page=False,
    badge_position="bottom-right", logo_position="bottom-left",
):
    source = tmp_path / ("Årsrapport_日本語.docx" if unicode else "source.docx")
    _create_docx(
        source, sections=sections, first_page_headers=first_page_headers,
        later_title_page=later_title_page,
    )
    badge_path = tmp_path / "badge.png"; _overlay(badge_path, (0, 140, 80, 220))
    logo_path = tmp_path / "logo.png"; _overlay(logo_path, (200, 20, 20, 128), (80, 80))
    return ProcessingRequest(
        source, tmp_path / ("Årsrapport_日本語_ai.docx" if unicode else "output.docx"),
        DisclosureSettings("ai-assisted.png", "AI Assisted", language="en", position=badge_position, size_percent=20, margin=17, opacity=65),
        badge_path=badge_path if badge else None,
        logo=LogoSettings(enabled=logo, path=logo_path, position=logo_position, size_percent=12, margin=9, opacity=45),
    )


def _section_parts(path: Path):
    with ZipFile(path) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        rels = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in rels}
        result = []
        for section in document.findall(f".//{_q(W, 'sectPr')}"):
            values = {"title_page": section.find(_q(W, "titlePg")) is not None}
            for kind in ("header", "footer"):
                for reference in section.findall(_q(W, f"{kind}Reference")):
                    reference_type = reference.attrib.get(_q(W, "type"), "default")
                    target = "word/" + targets[reference.attrib[f"{{{R}}}id"]]
                    root = ET.fromstring(archive.read(target))
                    picture_paragraphs = [
                        paragraph for paragraph in root.findall(f".//{_q(W, 'p')}")
                        if paragraph.find(f".//{_q(WP, 'inline')}") is not None
                    ]
                    values[(kind, reference_type)] = {
                        "target": target,
                        "anchors": len(root.findall(f".//{_q(WP, 'anchor')}")),
                        "inlines": len(root.findall(f".//{_q(WP, 'inline')}")),
                        "alignments": [
                            paragraph.find(f"./{_q(W, 'pPr')}/{_q(W, 'jc')}").attrib[_q(W, "val")]
                            for paragraph in picture_paragraphs
                        ],
                        "text": " ".join(node.text or "" for node in root.findall(f".//{_q(W, 't')}")),
                    }
            result.append(values)
        return result


@pytest.mark.parametrize(("badge", "logo"), [(True, False), (False, True), (True, True)])
def test_docx_supports_badge_logo_and_combined_overlays(tmp_path, badge, logo):
    request = _request(tmp_path, badge=badge, logo=logo)
    result = DocxProcessor().process(request)
    assert result.badge_shapes > 0 if badge else result.badge_shapes == 0
    assert result.logo_shapes > 0 if logo else result.logo_shapes == 0
    with ZipFile(result.destination) as archive:
        inlines = 0
        for name in archive.namelist():
            if name.startswith(("word/header", "word/footer")) and name.endswith(".xml"):
                root = ET.fromstring(archive.read(name))
                assert not root.findall(f".//{_q(WP, 'anchor')}")
                inlines += len(root.findall(f".//{_q(WP, 'inline')}"))
        assert inlines == int(badge) + int(logo)


@pytest.mark.parametrize(
    ("position", "expected"),
    [("bottom-left", "left"), ("center", "center"), ("bottom-right", "right")],
)
def test_docx_uses_inline_word_pictures_with_paragraph_alignment(tmp_path, position, expected):
    result = DocxProcessor().process(
        _request(tmp_path, badge_position=position), "entire-document"
    )
    parts = _section_parts(result.destination)
    footer = parts[0][("footer", "default")]
    assert footer["anchors"] == 0
    assert footer["inlines"] == 1
    assert footer["alignments"] == [expected]
    with ZipFile(result.destination) as archive:
        footer_xml = ET.fromstring(archive.read(footer["target"]))
        inline = footer_xml.find(f".//{_q(WP, 'inline')}")
        assert inline is not None
        assert inline.find(f"./{_q(WP, 'extent')}") is not None
        assert archive.read("word/media/nenolink-badge.png").startswith(b"\x89PNG")


def test_docx_first_page_scope_uses_first_header_footer_only(tmp_path):
    request = _request(
        tmp_path, badge=True, logo=True, sections=2,
        first_page_headers=True, later_title_page=True,
    )
    result = DocxProcessor().process(request, "first-page")
    parts = _section_parts(result.destination)
    assert result.scope == "first-page"
    assert result.badge_shapes == 1 and result.logo_shapes == 1
    assert parts[0]["title_page"]
    assert parts[0][("header", "first")]["inlines"] == 0
    assert parts[0][("footer", "first")]["inlines"] == 2
    assert "Existing first header" in parts[0][("header", "first")]["text"]
    assert "Existing first footer" in parts[0][("footer", "first")]["text"]
    assert parts[0][("header", "default")]["inlines"] == 0
    assert parts[0][("footer", "default")]["inlines"] == 0
    # The later section already uses Different First Page and originally linked
    # to section one. It must be detached from the newly marked first-page part.
    assert parts[1]["title_page"]
    assert parts[1].get(("header", "first"), {"inlines": 0})["inlines"] == 0
    assert parts[1][("footer", "first")]["inlines"] == 0
    # Headers remain linked and untouched because Word marking now uses footers only.


def test_docx_first_page_scope_enables_different_first_page_and_preserves_defaults(tmp_path):
    request = _request(tmp_path, badge=True, logo=False)
    result = DocxProcessor().process(request, "first-page")
    parts = _section_parts(result.destination)
    assert parts[0]["title_page"]
    assert parts[0][("footer", "first")]["inlines"] == 1
    assert "Existing footer" in parts[0][("footer", "first")]["text"]
    assert parts[0][("footer", "default")]["inlines"] == 0
    assert "Existing footer" in parts[0][("footer", "default")]["text"]


def test_docx_entire_document_marks_normal_and_first_pages_in_every_section(tmp_path):
    request = _request(
        tmp_path, badge=True, logo=True, sections=2,
        first_page_headers=True, later_title_page=True,
    )
    result = DocxProcessor().process(request, "entire-document")
    parts = _section_parts(result.destination)
    assert result.scope == "entire-document"
    assert result.badge_shapes == 4 and result.logo_shapes == 4
    for section in parts:
        assert section[("header", "default")]["inlines"] == 0
        assert section[("footer", "default")]["inlines"] == 2
        assert section.get(("header", "first"), {"inlines": 0})["inlines"] == 0
        assert section[("footer", "first")]["inlines"] == 2


def test_docx_output_uses_word_compatible_opc_namespace_and_unique_drawing_ids(tmp_path):
    """Regression: Word repaired outputs with invalid OPC XML/drawing structures."""
    request = _request(
        tmp_path, badge=True, logo=True, sections=2,
        first_page_headers=True, later_title_page=True,
    )
    result = DocxProcessor().process(request, "entire-document")
    DocxProcessor._validate_word_package(result.destination)
    with ZipFile(result.destination) as archive:
        content_types = archive.read("[Content_Types].xml")
        assert f'<Types xmlns="{CONTENT_TYPES}"'.encode() in content_types
        assert b"ns0:Types" not in content_types
        document_xml = archive.read("word/document.xml")
        assert b'mc:Ignorable="w14 wp14"' in document_xml or b'Ignorable="w14 wp14"' in document_xml
        assert f'xmlns:w14="{W14}"'.encode() in document_xml
        assert f'xmlns:wp14="{WP14}"'.encode() in document_xml
        drawing_ids = []
        for name in archive.namelist():
            if name.startswith("word/") and name.endswith(".xml"):
                root = ET.fromstring(archive.read(name))
                drawing_ids.extend(
                    int(item.attrib["id"])
                    for item in root.findall(f".//{_q(WP, 'docPr')}")
                )
        assert len(drawing_ids) == len(set(drawing_ids)) == 9
        assert all(
            not ET.fromstring(archive.read(name)).findall(f".//{_q(WP, 'anchor')}")
            for name in archive.namelist()
            if name.startswith("word/") and name.endswith(".xml")
        )


def test_docx_package_audit_rejects_the_content_types_form_that_triggered_word_repair(tmp_path):
    result = DocxProcessor().process(_request(tmp_path), "first-page")
    corrupted = tmp_path / "word-repair-warning.docx"
    with ZipFile(result.destination) as source, ZipFile(corrupted, "w") as destination:
        for entry in source.infolist():
            data = source.read(entry.filename)
            if entry.filename == "[Content_Types].xml":
                data = data.replace(b"<Types xmlns=", b"<ns0:Types xmlns:ns0=").replace(
                    b"</Types>", b"</ns0:Types>"
                )
            destination.writestr(entry, data)
    with pytest.raises(ValueError, match="content-types namespace"):
        DocxProcessor._validate_word_package(corrupted)


def test_docx_rejects_unknown_scope(tmp_path):
    request = _request(tmp_path)
    with pytest.raises(ValueError, match="Unsupported DOCX marking scope"):
        DocxProcessor().process(request, "section-2")


def test_docx_ui_scope_change_has_only_first_page_and_entire_document():
    scope = Mock()
    app = SimpleNamespace(
        workspace_state=SimpleNamespace(active="docx"),
        docx_scope_var=scope,
        pptx_selection_display_to_value={
            "First page": "first-page", "Entire document": "entire-document",
        },
    )
    MarkerApp.change_pptx_selection_mode(app, "First page")
    scope.set.assert_called_once_with("first-page")
    assert set(app.pptx_selection_display_to_value.values()) == {"first-page", "entire-document"}


def test_docx_preserves_text_tables_images_unrelated_parts_and_source(tmp_path):
    request = _request(tmp_path, badge=True, logo=True, sections=2)
    source_hash = sha256(request.source.read_bytes()).hexdigest()
    with ZipFile(request.source) as archive:
        existing_image = archive.read("word/media/existing.png")
        untouched = archive.read("custom/untouched.bin")
        original_headers = {
            name: archive.read(name) for name in archive.namelist()
            if name.startswith("word/header") and name.endswith(".xml")
        }
    result = DocxProcessor().process(request)
    assert sha256(request.source.read_bytes()).hexdigest() == source_hash
    with ZipFile(result.destination) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        text = " ".join(node.text or "" for node in document.findall(f".//{_q(W, 't')}"))
        assert "Ordinary Unicode text" in text and "Table value" in text
        assert document.find(f".//{_q(W, 'tbl')}") is not None
        assert archive.read("word/media/existing.png") == existing_image
        assert archive.read("custom/untouched.bin") == untouched
        assert all(archive.read(name) == data for name, data in original_headers.items())
        header_footer_text = " ".join(
            " ".join(node.text or "" for node in ET.fromstring(archive.read(name)).findall(f".//{_q(W, 't')}"))
            for name in archive.namelist() if name.startswith(("word/header", "word/footer")) and name.endswith(".xml")
        )
        assert "Existing header" in header_footer_text and "Existing footer" in header_footer_text
    assert result.section_count == 2


def test_docx_metadata_round_trip_preserves_existing_properties_and_inspects(tmp_path):
    request = _request(tmp_path, unicode=True)
    result = DocxProcessor().process(request)
    values = DocxProcessor.read_metadata(result.destination)
    assert values["Customer Code"] == "Preserve me"
    assert values["Nenolink AI Marker"] == "1"
    assert values["AI Label"] == "AI Assisted"
    assert values["Marker Version"] == __version__
    assert "not proof" in values["AI Transparency Notice"]
    inspected = inspect_file(result.destination)
    assert inspected.found and inspected.media_format == "DOCX"
    assert inspected.ai_label == "AI Assisted" and inspected.marker_version == __version__
    output = result.destination.read_bytes()
    assert str(request.source).encode("utf-8") not in output
    assert str(request.badge_path).encode("utf-8") not in output


def test_docx_unicode_path_reopens_and_source_cannot_be_overwritten(tmp_path):
    request = _request(tmp_path, unicode=True)
    result = DocxProcessor().process(request)
    with ZipFile(result.destination) as archive:
        assert archive.testzip() is None
        ET.fromstring(archive.read("word/document.xml"))
    with pytest.raises(ValueError, match="different from the source"):
        DocxProcessor().process(ProcessingRequest(request.source, request.source, request.disclosure, badge_path=request.badge_path))
    legacy = tmp_path / "legacy.doc"; legacy.write_bytes(b"legacy")
    with pytest.raises(ValueError, match="Only .docx"):
        DocxProcessor().process(ProcessingRequest(legacy, tmp_path / "legacy_ai.docx", request.disclosure, badge_path=request.badge_path))


def test_docx_preview_is_approximate_and_composites_both_overlays(tmp_path):
    request = _request(tmp_path, badge=True, logo=True)
    settings = MarkerSettings(logo_enabled=True, logo_path=str(request.logo.path), position="bottom-right", logo_position="top-left")
    plain = DocxPreviewRenderer().render(request.source, None, MarkerSettings()).image
    marked = DocxPreviewRenderer().render(request.source, request.badge_path, settings, request.logo.path).image
    assert marked.size == plain.size
    assert marked.tobytes() != plain.tobytes()


def test_docx_inspection_reads_size_and_sections_without_rendering(tmp_path):
    source = tmp_path / "sections.docx"; _create_docx(source, sections=3)
    info = DocxProcessor.inspect(source)
    assert info.metrics.size_bytes == source.stat().st_size
    assert info.section_count == 3 and info.metrics.item_count == 0
