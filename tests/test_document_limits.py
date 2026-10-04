from pathlib import Path
from types import SimpleNamespace

import pytest

from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.document_limits import (
    DOCUMENT_LIMITS,
    MIB,
    DocumentHardLimitError,
    DocumentMetrics,
    assess_document,
    enforce_hard_limit,
)


@pytest.mark.parametrize(
    ("kind", "warning_items", "hard_items"),
    [("pptx", 150, 500), ("pdf", 300, 1_000)],
)
def test_item_boundaries_are_strictly_above_configured_limits(kind, warning_items, hard_items):
    profile=DOCUMENT_LIMITS[kind]
    assert assess_document(kind,DocumentMetrics(100*MIB,warning_items)).status=="normal"
    assert assess_document(kind,DocumentMetrics(1,warning_items+1)).status=="warning"
    assert assess_document(kind,DocumentMetrics(1,hard_items)).status=="warning"
    assert assess_document(kind,DocumentMetrics(1,hard_items+1)).status=="hard"
    assert profile.warning_items==warning_items and profile.hard_items==hard_items


@pytest.mark.parametrize("kind",["pptx","pdf"])
def test_size_boundaries_are_strictly_above_100_and_300_mib(kind):
    assert assess_document(kind,DocumentMetrics(100*MIB,1)).status=="normal"
    assert assess_document(kind,DocumentMetrics(100*MIB+1,1)).status=="warning"
    assert assess_document(kind,DocumentMetrics(300*MIB,1)).status=="warning"
    assert assess_document(kind,DocumentMetrics(300*MIB+1,1)).status=="hard"
    with pytest.raises(DocumentHardLimitError):
        enforce_hard_limit(kind,DocumentMetrics(300*MIB+1,1))
def test_docx_size_boundaries_have_no_unreliable_page_count_limit():
    profile=DOCUMENT_LIMITS["docx"]
    assert profile.warning_bytes==50*MIB and profile.hard_bytes==200*MIB
    assert profile.warning_items is None and profile.hard_items is None
    assert assess_document("docx",DocumentMetrics(50*MIB,999_999)).status=="normal"
    assert assess_document("docx",DocumentMetrics(50*MIB+1,0)).status=="warning"
    assert assess_document("docx",DocumentMetrics(200*MIB,0)).status=="warning"
    assert assess_document("docx",DocumentMetrics(200*MIB+1,0)).status=="hard"
