"""Adjustable shared safeguards for document processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


MIB = 1024 * 1024
DocumentKind = Literal["pptx", "pdf"]
LimitStatus = Literal["normal", "warning", "hard"]


@dataclass(frozen=True, slots=True)
class DocumentLimitProfile:
    warning_bytes: int
    warning_items: int
    hard_bytes: int
    hard_items: int
    item_name: str


DOCUMENT_LIMITS: dict[DocumentKind, DocumentLimitProfile] = {
    "pptx": DocumentLimitProfile(100 * MIB, 150, 300 * MIB, 500, "slides"),
    "pdf": DocumentLimitProfile(100 * MIB, 300, 300 * MIB, 1_000, "pages"),
}


@dataclass(frozen=True, slots=True)
class DocumentMetrics:
    size_bytes: int
    item_count: int


@dataclass(frozen=True, slots=True)
class DocumentLimitAssessment:
    kind: DocumentKind
    metrics: DocumentMetrics
    profile: DocumentLimitProfile
    status: LimitStatus

    @property
    def requires_warning(self) -> bool:
        return self.status == "warning"

    @property
    def blocked(self) -> bool:
        return self.status == "hard"


class DocumentHardLimitError(ValueError):
    pass


def assess_document(kind: DocumentKind, metrics: DocumentMetrics) -> DocumentLimitAssessment:
    profile = DOCUMENT_LIMITS[kind]
    if metrics.size_bytes > profile.hard_bytes or metrics.item_count > profile.hard_items:
        status: LimitStatus = "hard"
    elif metrics.size_bytes > profile.warning_bytes or metrics.item_count > profile.warning_items:
        status = "warning"
    else:
        status = "normal"
    return DocumentLimitAssessment(kind, metrics, profile, status)


def enforce_hard_limit(kind: DocumentKind, metrics: DocumentMetrics) -> None:
    assessment = assess_document(kind, metrics)
    if assessment.blocked:
        raise DocumentHardLimitError(
            f"{kind.upper()} exceeds the hard limit of "
            f"{assessment.profile.hard_bytes // MIB} MB or "
            f"{assessment.profile.hard_items:,} {assessment.profile.item_name}."
        )
