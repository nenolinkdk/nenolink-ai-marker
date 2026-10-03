"""Opt-in structured diagnostics for TEST builds.

Receipts are observational only: they are never consulted by state, routing,
rendering, or output code. Production logging is disabled by default.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any


class ReceiptLog:
    def __init__(self, enabled: bool | None = None) -> None:
        self.enabled = bool(os.getenv("NENOLINK_TEST_BUILD")) if enabled is None else enabled
        self.records: list[dict[str, Any]] = []

    def record(self, receipt: Any) -> None:
        if not self.enabled:
            return
        value = asdict(receipt) if is_dataclass(receipt) else dict(receipt)
        value["timestamp"] = datetime.now(timezone.utc).isoformat()
        value["receipt_type"] = type(receipt).__name__
        self.records.append(value)

    def json_lines(self) -> str:
        return "\n".join(json.dumps(item, default=str, sort_keys=True) for item in self.records)
