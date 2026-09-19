from __future__ import annotations

import hashlib
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from PIL import Image
import pytest

from nenolink_ai_marker.document_processing import (
    DisclosureSettings,
    ItemSelection,
    LogoSettings,
    ProcessingRequest,
)
from nenolink_ai_marker.pptx_processor import A, P, PKG_REL, R, PptxProcessor


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_overlay(path: Path, colour: tuple[int, int, int, int], size=(120, 40)) -> None:
    Image.new("RGBA", size, colour).save(path)


def _create_pptx(path: Path, slide_count: int = 5) -> bytes:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
</Types>"""
    slide_ids = "".join(f'<p:sldId id="{255 + index}" r:id="rId{index}"/>' for index in range(1, slide_count + 1))
    presentation = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="{A}" xmlns:r="{R}" xmlns:p="{P}">
  <p:sldIdLst>{slide_ids}</p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000"/>
</p:presentation>"""
    relations = "".join(
        f'<Relationship Id="rId{index}" Type="{R}/slide" Target="slides/slide{index}.xml"/>'
        for index in range(1, slide_count + 1)
    )
    presentation_rels = f'<Relationships xmlns="{PKG_REL}">{relations}</Relationships>'
    slide = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="{A}" xmlns:r="{R}" xmlns:p="{P}"><p:cSld><p:spTree>
  <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
  <p:grpSpPr/>
</p:spTree></p:cSld></p:sld>"""
    untouched = b"Unrelated package content must remain unchanged.\x00\xff"
    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("ppt/presentation.xml", presentation)
        archive.writestr("ppt/_rels/presentation.xml.rels", presentation_rels)
        for index in range(1, slide_count + 1):
            archive.writestr(f"ppt/slides/slide{index}.xml", slide)
        archive.writestr("custom/untouched.bin", untouched)
    return untouched


def _request(tmp_path: Path, *, logo: bool = False, unicode_names: bool = False) -> tuple[ProcessingRequest, Path]:
    source_name = "Årsrapport_日本語.pptx" if unicode_names else "source.pptx"
    output_name = "Årsrapport_日本語_ai.pptx" if unicode_names else "output.pptx"
    source = tmp_path / source_name
    _create_pptx(source)
    badge = tmp_path / "badge.png"
    _write_overlay(badge, (0, 140, 80, 220))
    logo_path = tmp_path / "logo.png"
    _write_overlay(logo_path, (200, 20, 20, 128), (80, 80))
    request = ProcessingRequest(
        source=source,
        destination=tmp_path / output_name,
        disclosure=DisclosureSettings(
            "ai-assisted.png", "AI Assisted", position="bottom-right",
            size_percent=20, margin=17, opacity=65,
        ),
        badge_path=badge,
        logo=LogoSettings(
            enabled=logo, path=logo_path, position="top-left",
            size_percent=12, margin=9, opacity=45,
        ),
    )
    return request, source


def _picture_count(archive: ZipFile, slide_number: int) -> int:
    root = ET.fromstring(archive.read(f"ppt/slides/slide{slide_number}.xml"))
    return len(root.findall(f".//{{{P}}}pic"))


@pytest.mark.parametrize(
    ("selection", "selected"),
    [
        (ItemSelection("single", (3,)), (3,)),
        (ItemSelection("selected", (2, 5)), (2, 5)),
        (ItemSelection("range", start=2, end=4), (2, 3, 4)),
        (ItemSelection(), (1, 2, 3, 4, 5)),
    ],
)
def test_pptx_selection_modes_add_badge_only_to_requested_slides(tmp_path, selection, selected):
    request, source = _request(tmp_path)
    source_sha = _sha256(source)

    result = PptxProcessor().process(request, selection)

    assert result.selected_slides == selected
    assert result.badge_shapes == len(selected)
    assert _sha256(source) == source_sha
    with ZipFile(result.destination) as archive:
        for slide_number in range(1, 6):
            assert _picture_count(archive, slide_number) == (1 if slide_number in selected else 0)
        assert "ppt/media/nenolink-ai-marker-badge.png" in archive.namelist()


def test_pptx_badge_and_logo_have_independent_geometry_and_opacity(tmp_path):
    request, _ = _request(tmp_path, logo=True)

    result = PptxProcessor().process(request, ItemSelection("single", (1,)))

    assert result.badge_shapes == result.logo_shapes == 1
    with ZipFile(result.destination) as archive:
        slide = ET.fromstring(archive.read("ppt/slides/slide1.xml"))
        pictures = slide.findall(f".//{{{P}}}pic")
        assert len(pictures) == 2
        names = [picture.find(f"./{{{P}}}nvPicPr/{{{P}}}cNvPr").attrib["name"] for picture in pictures]
        assert names == ["Nenolink AI Marker badge", "Nenolink company logo"]
        opacity = [picture.find(f".//{{{A}}}alphaModFix").attrib["amt"] for picture in pictures]
        assert opacity == ["65000", "45000"]
        offsets = [picture.find(f".//{{{A}}}off").attrib for picture in pictures]
        assert offsets[0] != offsets[1]
        assert "ppt/media/nenolink-company-logo.png" in archive.namelist()


def test_pptx_preserves_unselected_package_parts_and_unicode_paths(tmp_path):
    request, source = _request(tmp_path, unicode_names=True)
    with ZipFile(source) as archive:
        untouched = archive.read("custom/untouched.bin")

    result = PptxProcessor().process(request, ItemSelection("single", (1,)))

    assert result.destination.name == "Årsrapport_日本語_ai.pptx"
    with ZipFile(result.destination) as archive:
        assert archive.read("custom/untouched.bin") == untouched
        ET.fromstring(archive.read("ppt/slides/slide1.xml"))
        ET.fromstring(archive.read("ppt/slides/_rels/slide1.xml.rels"))


def test_pptx_rejects_legacy_format_and_never_overwrites_source(tmp_path):
    badge = tmp_path / "badge.png"
    _write_overlay(badge, (0, 0, 0, 255))
    legacy = tmp_path / "legacy.ppt"
    legacy.write_bytes(b"not a pptx")
    disclosure = DisclosureSettings("ai-assisted.png", "AI Assisted")
    with pytest.raises(ValueError, match="Only .pptx"):
        PptxProcessor().process(ProcessingRequest(legacy, tmp_path / "out.pptx", disclosure, badge_path=badge))
    source = tmp_path / "source.pptx"
    _create_pptx(source)
    with pytest.raises(ValueError, match="different from the source"):
        PptxProcessor().process(ProcessingRequest(source, source, disclosure, badge_path=badge))
