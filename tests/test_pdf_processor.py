from __future__ import annotations

import hashlib
from types import SimpleNamespace

from PIL import Image, ImageChops
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, BooleanObject
import pytest

from nenolink_ai_marker.document_processing import DisclosureSettings, ItemSelection, LogoSettings, ProcessingRequest
from nenolink_ai_marker import __version__
from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.pdf_preview import PdfPreviewRenderer
from nenolink_ai_marker.pdf_processor import PasswordProtectedPdfError, PdfProcessor
from nenolink_ai_marker.app import MarkerApp


def _pdf(path,pages=4,password=None):
    writer=PdfWriter()
    for index in range(pages):writer.add_blank_page(width=612+index,height=792)
    if password:writer.encrypt(password)
    with path.open("wb") as stream:writer.write(stream)


def _hash(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def _badge(path):Image.new("RGBA",(180,54),(0,145,75,220)).save(path)


def _logo(path):Image.new("RGBA",(80,80),(210,25,25,160)).save(path)


def test_pdf_inspection_reports_size_and_page_count(tmp_path):
    source=tmp_path/"source.pdf"; _pdf(source,7)
    info=PdfProcessor.inspect(source)
    assert info.metrics.size_bytes==source.stat().st_size
    assert info.metrics.item_count==7
    assert not info.signed


def test_encrypted_pdf_fails_gracefully(tmp_path):
    source=tmp_path/"locked.pdf"; _pdf(source,2,"secret")
    with pytest.raises(PasswordProtectedPdfError,match="password-protected"):
        PdfProcessor.inspect(source)


def test_signed_pdf_is_detected_for_ui_warning(tmp_path):
    source=tmp_path/"signed.pdf"; writer=PdfWriter(); writer.add_blank_page(width=612,height=792); writer._root_object[NameObject("/Perms")]=DictionaryObject({NameObject("/DocMDP"):BooleanObject(True)})
    with source.open("wb") as stream:writer.write(stream)
    assert PdfProcessor.inspect(source).signed


def test_signed_pdf_requires_explicit_ui_acknowledgement(monkeypatch,tmp_path):
    calls=[]; monkeypatch.setattr("nenolink_ai_marker.app.messagebox.askokcancel",lambda *args:calls.append(args) or False)
    app=SimpleNamespace(pdf_path=tmp_path/"signed.pdf",pdf_info=SimpleNamespace(signed=True,metrics=SimpleNamespace(size_bytes=42)),_pdf_signature_approved=None,translator=SimpleNamespace(text=lambda key:key))
    assert not MarkerApp._confirm_pdf_signature(app)
    assert calls and calls[0][0]=="pdf.signature_title"


@pytest.mark.parametrize(("selection","expected"),[(ItemSelection("single",(2,)),(2,)),(ItemSelection("selected",(1,4)),(1,4)),(ItemSelection("range",start=2,end=3),(2,3)),(ItemSelection(),(1,2,3,4))])
def test_pdf_badge_overlay_selected_pages_preserves_source(tmp_path,selection,expected):
    source=tmp_path/"source.pdf"; output=tmp_path/"source_ai.pdf"; badge=tmp_path/"badge.png"; _pdf(source); _badge(badge); before=_hash(source)
    request=ProcessingRequest(source,output,DisclosureSettings("ai-assisted.png","AI Assisted",position="top-right",size_percent=20,margin=15,opacity=70),badge_path=badge)
    result=PdfProcessor().process(request,selection)
    assert result.selected_pages==expected and result.page_count==4
    assert _hash(source)==before and output.is_file()
    reader=PdfReader(output)
    for ordinal,page in enumerate(reader.pages,1):
        assert bool(page.get("/Contents"))==(ordinal in expected)


def test_pdf_never_overwrites_source(tmp_path):
    source=tmp_path/"source.pdf"; badge=tmp_path/"badge.png"; _pdf(source); _badge(badge)
    with pytest.raises(ValueError,match="different from the source"):
        PdfProcessor().process(ProcessingRequest(source,source,DisclosureSettings("badge.png","AI"),badge_path=badge))


def test_pdf_preview_is_lazy_single_page_and_updates_placement(tmp_path):
    source=tmp_path/"source.pdf"; badge=tmp_path/"badge.png"; _pdf(source,5); _badge(badge); before=_hash(source); renderer=PdfPreviewRenderer()
    first=renderer.render(source,1,badge,MarkerSettings(position="top-left",size_percent=10))
    last=renderer.render(source,5,badge,MarkerSettings(position="bottom-right",size_percent=25))
    assert (first.page_number,first.page_count)==(1,5) and last.page_number==5
    assert ImageChops.difference(first.image.convert("RGB"),last.image.convert("RGB")).getbbox()
    assert _hash(source)==before


def test_pdf_logo_only_and_badge_plus_logo(tmp_path):
    source=tmp_path/"source.pdf"; badge=tmp_path/"badge.png"; logo=tmp_path/"logo.png"; _pdf(source,2); _badge(badge); _logo(logo); disclosure=DisclosureSettings("ai-assisted.png","AI Assisted")
    logo_settings=LogoSettings(True,logo,position="top-left",size_percent=12,margin=8,opacity=55)
    logo_only=PdfProcessor().process(ProcessingRequest(source,tmp_path/"logo-only.pdf",disclosure,logo=logo_settings),ItemSelection("single",(1,)))
    both=PdfProcessor().process(ProcessingRequest(source,tmp_path/"both.pdf",disclosure,badge_path=badge,logo=logo_settings),ItemSelection("single",(2,)))
    assert (logo_only.badge_pages,logo_only.logo_pages)==(0,1)
    assert (both.badge_pages,both.logo_pages)==(1,1)


def test_pdf_preview_shows_badge_and_logo(tmp_path):
    source=tmp_path/"source.pdf"; badge=tmp_path/"badge.png"; logo=tmp_path/"logo.png"; _pdf(source); _badge(badge); _logo(logo); renderer=PdfPreviewRenderer()
    settings=MarkerSettings(logo_enabled=True,logo_path=str(logo),logo_position="top-left",position="bottom-right")
    badge_only=renderer.render(source,1,badge,MarkerSettings()).image
    both=renderer.render(source,1,badge,settings,logo).image
    assert ImageChops.difference(badge_only.convert("RGB"),both.convert("RGB")).getbbox()


def test_pdf_metadata_round_trip_preserves_unrelated_metadata_and_unicode_path(tmp_path):
    source=tmp_path/"Årsrapport_日本語.pdf"; output=tmp_path/"Årsrapport_日本語_ai.pdf"; badge=tmp_path/"mærke.png"; writer=PdfWriter(); writer.add_blank_page(width=612,height=792); writer.add_metadata({"/Title":"Existing title","/Subject":"Keep me"})
    with source.open("wb") as stream:writer.write(stream)
    _badge(badge); before=_hash(source)
    result=PdfProcessor().process(ProcessingRequest(source,output,DisclosureSettings("ai-assisted.png","AI Assisted",language="en"),badge_path=badge))
    metadata=PdfProcessor.read_metadata(output); raw=PdfReader(output).metadata
    assert result.metadata_written and metadata["AILabel"]=="AI Assisted" and metadata["MarkerVersion"]==__version__
    assert metadata["AITransparencyNotice"].startswith("Disclosure statement only")
    assert raw.title=="Existing title" and raw.subject=="Keep me"
    assert _hash(source)==before and str(source).encode("utf-8") not in output.read_bytes()
