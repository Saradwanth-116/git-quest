from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from config import TRACES_DIR


def trace(
    component: str,
    prompt: str,
    raw_output: str,
    latency_ms: float,
    extra: dict | None = None,
) -> None:
    """Append one trace record to mutagent/traces/<component>.jsonl.

    Raw output is stored exactly as received — malformed JSON must survive
    as evidence, not be swallowed by defensive parsing.
    """
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "component": component,
        "prompt": prompt,
        "raw_output": raw_output,
        "latency_ms": round(latency_ms, 2),
    }
    if extra:
        record.update(extra)

    dest = TRACES_DIR / f"{component}.jsonl"
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
