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


def test_pptx_warning_allows_continue_once(monkeypatch,tmp_path):
    calls=[]
    monkeypatch.setattr("nenolink_ai_marker.app.messagebox.askokcancel",lambda *_:calls.append(True) or True)
    app=SimpleNamespace(pptx_path=tmp_path/"large.pptx",pptx_metrics=DocumentMetrics(1,151),_pptx_warning_approved=None,translator=SimpleNamespace(text=lambda key:key))
    assert MarkerApp._confirm_pptx_limits(app)
    assert MarkerApp._confirm_pptx_limits(app)
    assert len(calls)==1


def test_pptx_hard_limit_blocks_without_continue(monkeypatch,tmp_path):
    shown=[]; continued=[]
    monkeypatch.setattr("nenolink_ai_marker.app.messagebox.showerror",lambda *args:shown.append(args))
    monkeypatch.setattr("nenolink_ai_marker.app.messagebox.askokcancel",lambda *_:continued.append(True) or True)
    app=SimpleNamespace(pptx_path=tmp_path/"too-many.pptx",pptx_metrics=DocumentMetrics(1,501),_pptx_warning_approved=None,translator=SimpleNamespace(text=lambda key:key))
    assert not MarkerApp._confirm_pptx_limits(app)
    assert shown and not continued
