from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from PIL import Image

from nenolink_ai_marker import __version__
from nenolink_ai_marker.docx_preview import DocxPreviewRenderer
from nenolink_ai_marker.docx_processor import DocxProcessor, W, WP, _q
from nenolink_ai_marker.document_processing import DisclosureSettings, LogoSettings, ProcessingRequest
from nenolink_ai_marker.inspection import inspect_file
from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.app import MarkerApp


R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


def _create_docx(
    path: Path, *, sections: int = 1, existing_metadata: bool = True,
    first_page_headers: bool = False, later_title_page: bool = False,
) -> None:
    section_xml = "".join(
        f'<w:p><w:pPr><w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr></w:pPr><w:r><w:t>Section {index}</w:t></w:r></w:p>'
        for index in range(1, sections)
    )
    document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{W}" xmlns:r="{R}"><w:body>
<w:p><w:r><w:t>Ordinary Unicode text ÆØÅ 日本語</w:t></w:r></w:p>
<w:p><w:r><w:drawing><w:t>Existing image anchor</w:t></w:drawing></w:r></w:p>
<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Table value</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
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
        archive.writestr("word/media/existing.png", b"existing-image-bytes")
        archive.writestr("custom/untouched.bin", b"untouched-package-part")
        if existing_metadata:
            archive.writestr("docProps/custom.xml", custom)


def _overlay(path: Path, colour, size=(180, 60)) -> None:
    Image.new("RGBA", size, colour).save(path)


def _request(
    tmp_path: Path, *, badge=True, logo=False, unicode=False, sections=1,
    first_page_headers=False, later_title_page=False,
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
        DisclosureSettings("ai-assisted.png", "AI Assisted", language="en", position="bottom-right", size_percent=20, margin=17, opacity=65),
        badge_path=badge_path if badge else None,
        logo=LogoSettings(enabled=logo, path=logo_path, position="top-left", size_percent=12, margin=9, opacity=45),
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
                    values[(kind, reference_type)] = {
                        "target": target,
                        "anchors": len(root.findall(f".//{_q(WP, 'anchor')}")),
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
        anchors = 0
        for name in archive.namelist():
            if name.startswith(("word/header", "word/footer")) and name.endswith(".xml"):
                anchors += len(ET.fromstring(archive.read(name)).findall(f".//{_q(WP, 'anchor')}"))
        assert anchors == int(badge) + int(logo)


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
    assert parts[0][("header", "first")]["anchors"] == 1
    assert parts[0][("footer", "first")]["anchors"] == 1
    assert "Existing first header" in parts[0][("header", "first")]["text"]
    assert "Existing first footer" in parts[0][("footer", "first")]["text"]
    assert parts[0][("header", "default")]["anchors"] == 0
    assert parts[0][("footer", "default")]["anchors"] == 0
    # The later section already uses Different First Page and originally linked
    # to section one. It must be detached from the newly marked first-page part.
    assert parts[1]["title_page"]
    assert parts[1][("header", "first")]["anchors"] == 0
    assert parts[1][("footer", "first")]["anchors"] == 0
    assert "Existing first header" in parts[1][("header", "first")]["text"]


def test_docx_first_page_scope_enables_different_first_page_and_preserves_defaults(tmp_path):
    request = _request(tmp_path, badge=True, logo=False)
    result = DocxProcessor().process(request, "first-page")
    parts = _section_parts(result.destination)
    assert parts[0]["title_page"]
    assert parts[0][("footer", "first")]["anchors"] == 1
    assert "Existing footer" in parts[0][("footer", "first")]["text"]
    assert parts[0][("footer", "default")]["anchors"] == 0
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
        assert section[("header", "default")]["anchors"] == 1
        assert section[("footer", "default")]["anchors"] == 1
        assert section[("header", "first")]["anchors"] == 1
        assert section[("footer", "first")]["anchors"] == 1


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
    result = DocxProcessor().process(request)
    assert sha256(request.source.read_bytes()).hexdigest() == source_hash
    with ZipFile(result.destination) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        text = " ".join(node.text or "" for node in document.findall(f".//{_q(W, 't')}"))
        assert "Ordinary Unicode text" in text and "Table value" in text
        assert document.find(f".//{_q(W, 'tbl')}") is not None
        assert archive.read("word/media/existing.png") == existing_image
        assert archive.read("custom/untouched.bin") == untouched
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
