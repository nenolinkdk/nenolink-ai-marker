"""Minimal machine-readable metadata written to marked output files."""

from dataclasses import dataclass
from xml.sax.saxutils import escape

from . import __version__
from .badges import custom_badge_display_name


@dataclass(frozen=True, slots=True)
class MarkerMetadata:
    software: str
    ai_label: str
    marker_version: str
    identifier: str = "1"

    @property
    def description(self) -> str:
        return (
            f"Nenolink AI Marker; AI Label={self.ai_label}; "
            f"Version={self.marker_version}"
        )

    @property
    def xmp(self) -> bytes:
        values = {
            "software": escape(self.software, {'"': "&quot;"}),
            "label": escape(self.ai_label, {'"': "&quot;"}),
            "version": escape(self.marker_version, {'"': "&quot;"}),
            "identifier": escape(self.identifier, {'"': "&quot;"}),
        }
        return (
            '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
            '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
            '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            '<rdf:Description rdf:about="" '
            'xmlns:xmp="http://ns.adobe.com/xap/1.0/" '
            'xmlns:nenolink="https://nenolink.com/ns/ai-marker/1.0/" '
            f'xmp:CreatorTool="{values["software"]}" '
            f'nenolink:AILabel="{values["label"]}" '
            f'nenolink:MarkerVersion="{values["version"]}" '
            f'nenolink:Marker="{values["identifier"]}"/>'
            '</rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
        ).encode("utf-8")


def marker_metadata(badge_filename: str, badge_display_name: str | None = None) -> MarkerMetadata:
    """Build privacy-safe metadata from the active badge and application version."""
    return MarkerMetadata(
        software="Nenolink AI Marker",
        ai_label=badge_display_name or custom_badge_display_name(badge_filename),
        marker_version=__version__,
    )
