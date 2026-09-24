from hashlib import sha256
from pathlib import Path
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


R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


def _create_docx(path: Path, *, sections: int = 1, existing_metadata: bool = True) -> None:
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
<Override PartName="/docProps/custom.xml" ContentType="application/vnd.openxmlformats-officedocument.custom-properties+xml"/>
</Types>'''
    root_rels = f'''<Relationships xmlns="{PKG}">
<Relationship Id="rId1" Type="{R}/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="{R}/custom-properties" Target="docProps/custom.xml"/>
</Relationships>'''
    document = document.replace('<w:sectPr><w:pgSz', '<w:sectPr><w:headerReference w:type="default" r:id="rId2"/><w:footerReference w:type="default" r:id="rId3"/><w:pgSz')
    doc_rels = f'''<Relationships xmlns="{PKG}"><Relationship Id="rId1" Type="{R}/image" Target="media/existing.png"/><Relationship Id="rId2" Type="{R}/header" Target="header1.xml"/><Relationship Id="rId3" Type="{R}/footer" Target="footer1.xml"/></Relationships>'''
    custom = '''<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="2" name="Customer Code"><vt:lpwstr>Preserve me</vt:lpwstr></property></Properties>'''
    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/_rels/document.xml.rels", doc_rels)
        archive.writestr("word/header1.xml", f'<w:hdr xmlns:w="{W}"><w:p><w:r><w:t>Existing header</w:t></w:r></w:p></w:hdr>')
        archive.writestr("word/footer1.xml", f'<w:ftr xmlns:w="{W}"><w:p><w:r><w:t>Existing footer</w:t></w:r></w:p></w:ftr>')
        archive.writestr("word/media/existing.png", b"existing-image-bytes")
        archive.writestr("custom/untouched.bin", b"untouched-package-part")
        if existing_metadata:
            archive.writestr("docProps/custom.xml", custom)


def _overlay(path: Path, colour, size=(180, 60)) -> None:
    Image.new("RGBA", size, colour).save(path)


def _request(tmp_path: Path, *, badge=True, logo=False, unicode=False, sections=1):
    source = tmp_path / ("Årsrapport_日本語.docx" if unicode else "source.docx")
    _create_docx(source, sections=sections)
    badge_path = tmp_path / "badge.png"; _overlay(badge_path, (0, 140, 80, 220))
    logo_path = tmp_path / "logo.png"; _overlay(logo_path, (200, 20, 20, 128), (80, 80))
    return ProcessingRequest(
        source, tmp_path / ("Årsrapport_日本語_ai.docx" if unicode else "output.docx"),
        DisclosureSettings("ai-assisted.png", "AI Assisted", language="en", position="bottom-right", size_percent=20, margin=17, opacity=65),
        badge_path=badge_path if badge else None,
        logo=LogoSettings(enabled=logo, path=logo_path, position="top-left", size_percent=12, margin=9, opacity=45),
    )


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
