"""Safe, local PDF inspection and selected-page badge overlays."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile

from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation

from .document_limits import DocumentMetrics, enforce_hard_limit
from .document_processing import ItemSelection, ProcessingRequest, ProcessorCapabilities
from .metadata import marker_metadata


class PasswordProtectedPdfError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PdfInfo:
    metrics: DocumentMetrics
    signed: bool


@dataclass(frozen=True, slots=True)
class PdfResult:
    destination: Path
    page_count: int
    selected_pages: tuple[int, ...]
    signed_source: bool
    badge_pages: int
    logo_pages: int
    metadata_written: bool


class PdfProcessor:
    capabilities=ProcessorCapabilities("pdf",frozenset({".pdf"}),supports_logo=True,supports_metadata=True,supports_preview=True,supports_selection=True)

    @staticmethod
    def _reader(source: Path) -> PdfReader:
        try:reader=PdfReader(source,strict=False)
        except Exception as error:raise ValueError(f"Could not read PDF: {error}") from error
        if reader.is_encrypted:raise PasswordProtectedPdfError("Encrypted or password-protected PDFs are not supported.")
        return reader

    @classmethod
    def inspect(cls,source: Path) -> PdfInfo:
        source=Path(source); reader=cls._reader(source)
        metrics=DocumentMetrics(source.stat().st_size,len(reader.pages))
        signed="/Perms" in reader.root_object
        try:
            fields=reader.get_fields() or {}
            signed=signed or any(str(field.get("/FT"))=="/Sig" for field in fields.values())
        except Exception:pass
        return PdfInfo(metrics,signed)

    def process(self,request: ProcessingRequest,selection: ItemSelection | None=None) -> PdfResult:
        request=request.validated()
        if not self.capabilities.supports(request.source):raise ValueError("Only .pdf documents are supported.")
        badge_path=request.badge_path if request.badge_path and request.badge_path.is_file() else None
        logo_path=request.logo.path if request.logo.enabled and request.logo.path and request.logo.path.is_file() else None
        if request.badge_path and not badge_path:raise FileNotFoundError(request.badge_path)
        if request.logo.enabled and not logo_path:raise FileNotFoundError(request.logo.path)
        if not badge_path and not logo_path:raise ValueError("At least one PDF overlay must be enabled.")
        info=self.inspect(request.source); enforce_hard_limit("pdf",info.metrics)
        selected=(selection or ItemSelection()).resolve(info.metrics.item_count)
        reader=self._reader(request.source); writer=PdfWriter(clone_from=reader); temporary_overlays=[]
        try:
            badge_overlay=self._image_pdf(badge_path,request.disclosure.opacity) if badge_path else None
            logo_overlay=self._image_pdf(logo_path,request.logo.opacity) if logo_path else None
            temporary_overlays.extend(path for path in (badge_overlay,logo_overlay) if path)
            for ordinal in selected:
                page=writer.pages[ordinal-1]
                if badge_overlay:self._merge_overlay(page,badge_overlay,request.disclosure.position,request.disclosure.size_percent,request.disclosure.margin)
                if logo_overlay:self._merge_overlay(page,logo_overlay,request.logo.position,request.logo.size_percent,request.logo.margin)
            metadata=request.metadata or marker_metadata(request.disclosure.badge_name,request.disclosure.label)
            existing={str(key):str(value) for key,value in (reader.metadata or {}).items() if value is not None}
            existing.update({"/NenolinkAIMarker":metadata.identifier,"/Software":metadata.software,"/AILabel":metadata.ai_label,"/MarkerVersion":metadata.marker_version,"/DisclosureLanguage":request.disclosure.language,"/AITransparencyNotice":"Disclosure statement only; not proof of authorship or AI provenance."})
            writer.add_metadata(existing)
            request.destination.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix="nenolink-pdf-",suffix=".tmp",dir=request.destination.parent,delete=False) as stream:temporary=Path(stream.name)
            try:
                with temporary.open("wb") as output:writer.write(output)
                temporary.replace(request.destination)
            finally:temporary.unlink(missing_ok=True)
        finally:
            for path in temporary_overlays:path.unlink(missing_ok=True)
        return PdfResult(request.destination,info.metrics.item_count,selected,info.signed,len(selected) if badge_path else 0,len(selected) if logo_path else 0,True)

    @staticmethod
    def _image_pdf(image_path: Path,opacity: int) -> Path:
        with Image.open(image_path) as opened:
            image=opened.convert("RGBA"); alpha=image.getchannel("A").point(lambda value:round(value*opacity/100)); image.putalpha(alpha); background=Image.new("RGB",image.size,"white"); background.paste(image,mask=alpha)
        with tempfile.NamedTemporaryFile(prefix="nenolink-badge-",suffix=".pdf",delete=False) as stream:path=Path(stream.name)
        background.save(path,"PDF",resolution=72.0)
        return path

    @classmethod
    def _merge_overlay(cls,page,overlay_path,position,size_percent,margin):
        overlay=PdfReader(overlay_path).pages[0]; item_width=float(overlay.mediabox.width); item_height=float(overlay.mediabox.height); page_width=float(page.mediabox.width); page_height=float(page.mediabox.height)
        target_width=page_width*size_percent/100; scale=target_width/item_width; target_height=item_height*scale; x,y=cls._position(page_width,page_height,target_width,target_height,position,margin*.75)
        page.merge_transformed_page(overlay,Transformation().scale(scale).translate(x,y),over=True)

    @classmethod
    def read_metadata(cls,source: Path) -> dict[str,str]:
        metadata=cls._reader(source).metadata or {}
        return {key.lstrip("/"):str(metadata.get(key,"")) for key in ("/NenolinkAIMarker","/Software","/AILabel","/MarkerVersion","/DisclosureLanguage","/AITransparencyNotice")}

    @staticmethod
    def _position(width,height,item_width,item_height,position,margin):
        left=margin; right=max(0,width-item_width-margin); bottom=margin; top=max(0,height-item_height-margin)
        return {"top-left":(left,top),"top-right":(right,top),"bottom-left":(left,bottom),"bottom-right":(right,bottom),"center":((width-item_width)/2,(height-item_height)/2)}.get(position,(right,bottom))
