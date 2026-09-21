"""Safe, local PDF inspection and selected-page badge overlays."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile

from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation

from .document_limits import DocumentMetrics, enforce_hard_limit
from .document_processing import ItemSelection, ProcessingRequest, ProcessorCapabilities


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


class PdfProcessor:
    capabilities=ProcessorCapabilities("pdf",frozenset({".pdf"}),supports_preview=True,supports_selection=True)

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
        if not request.badge_path or not request.badge_path.is_file():raise FileNotFoundError(request.badge_path)
        info=self.inspect(request.source); enforce_hard_limit("pdf",info.metrics)
        selected=(selection or ItemSelection()).resolve(info.metrics.item_count)
        reader=self._reader(request.source); writer=PdfWriter(clone_from=reader)
        overlay_path=self._badge_pdf(request.badge_path,request.disclosure.opacity)
        try:
            overlay=PdfReader(overlay_path).pages[0]
            badge_width=float(overlay.mediabox.width); badge_height=float(overlay.mediabox.height)
            for ordinal in selected:
                page=writer.pages[ordinal-1]; page_width=float(page.mediabox.width); page_height=float(page.mediabox.height)
                target_width=page_width*request.disclosure.size_percent/100; scale=target_width/badge_width; target_height=badge_height*scale
                margin=request.disclosure.margin*.75
                x,y=self._position(page_width,page_height,target_width,target_height,request.disclosure.position,margin)
                page.merge_transformed_page(overlay,Transformation().scale(scale).translate(x,y),over=True)
            request.destination.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix="nenolink-pdf-",suffix=".tmp",dir=request.destination.parent,delete=False) as stream:temporary=Path(stream.name)
            try:
                with temporary.open("wb") as output:writer.write(output)
                temporary.replace(request.destination)
            finally:temporary.unlink(missing_ok=True)
        finally:overlay_path.unlink(missing_ok=True)
        return PdfResult(request.destination,info.metrics.item_count,selected,info.signed)

    @staticmethod
    def _badge_pdf(badge_path: Path,opacity: int) -> Path:
        with Image.open(badge_path) as opened:
            image=opened.convert("RGBA"); alpha=image.getchannel("A").point(lambda value:round(value*opacity/100)); image.putalpha(alpha); background=Image.new("RGB",image.size,"white"); background.paste(image,mask=alpha)
        with tempfile.NamedTemporaryFile(prefix="nenolink-badge-",suffix=".pdf",delete=False) as stream:path=Path(stream.name)
        background.save(path,"PDF",resolution=72.0)
        return path

    @staticmethod
    def _position(width,height,item_width,item_height,position,margin):
        left=margin; right=max(0,width-item_width-margin); bottom=margin; top=max(0,height-item_height-margin)
        return {"top-left":(left,top),"top-right":(right,top),"bottom-left":(left,bottom),"bottom-right":(right,bottom),"center":((width-item_width)/2,(height-item_height)/2)}.get(position,(right,bottom))
