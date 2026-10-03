"""Opt-in structured diagnostics for TEST builds.

Receipts are observational only: they are never consulted by state, routing,
rendering, or output code. Production logging is disabled by default.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any


class ReceiptLog:
    def __init__(self, enabled: bool | None = None) -> None:
        self.enabled = bool(os.getenv("NENOLINK_TEST_BUILD")) if enabled is None else enabled
        self.records: list[dict[str, Any]] = []
        self.path = (os.getenv("NENOLINK_RECEIPT_LOG") or os.path.join(tempfile.gettempdir(), "Nenolink-AI-Marker-test-receipts.jsonl")) if self.enabled else None

    def record(self, receipt: Any) -> None:
        if not self.enabled:
            return
        value = asdict(receipt) if is_dataclass(receipt) else dict(receipt)
        value["timestamp"] = datetime.now(timezone.utc).isoformat()
        value["receipt_type"] = type(receipt).__name__
        self.records.append(value)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as stream:
                stream.write(json.dumps(value, default=str, sort_keys=True) + "\n")

    def json_lines(self) -> str:
        return "\n".join(json.dumps(item, default=str, sort_keys=True) for item in self.records)
