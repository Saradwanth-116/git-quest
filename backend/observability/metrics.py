from __future__ import annotations
import json
from pathlib import Path
from config import REPORTS_DIR, TRACES_DIR

# Ordered list of all Mutagent targets so the dashboard shows a consistent layout
TARGETS = [
    {"id": "issue_rec",    "name": "Issue Recommendation",  "priority": "critical"},
    {"id": "council",      "name": "AI-Council Gate",        "priority": "critical"},
    {"id": "graph_query",  "name": "Graph Query Generation", "priority": "high"},
    {"id": "router",       "name": "Retrieval Router",       "priority": "medium"},
    {"id": "pr_check",     "name": "PR Readiness",           "priority": "medium"},
    {"id": "issue_health", "name": "Issue Health Scoring",   "priority": "stretch"},
]


def _load_delta(target_id: str) -> dict | None:
    path = REPORTS_DIR / f"{target_id}.delta.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _trace_count(target_id: str) -> int:
    path = TRACES_DIR / f"{target_id}.jsonl"
    if not path.exists():
        return 0
    try:
        return sum(1 for _ in path.open(encoding="utf-8"))
    except Exception:
        return 0


def get_metrics() -> dict:
    """Return the self-improvement dashboard payload for GET /metrics.

    Target graph_query writes a differently-shaped report — Node F1
    against executable ground truth — so its entry branches on the report's
    actual shape rather than silently showing null scores.
    """
    targets_out = []
    for t in TARGETS:
        delta = _load_delta(t["id"])
        entry: dict = {
            "id": t["id"],
            "name": t["name"],
            "priority": t["priority"],
            "trace_count": _trace_count(t["id"]),
            "has_report": delta is not None,
        }
        if delta:
            if "mean_f1" in delta:
                entry["metric"] = "node_f1"
                entry["mean_f1"] = delta.get("mean_f1")
                entry["by_op"] = delta.get("by_op")
                entry["optimized"] = False
            else:
                entry["metric"] = "severity_gated_pass_rate"
                entry["baseline_score"] = delta.get("baseline_score")
                entry["optimized_score"] = delta.get("optimized_score")
                entry["delta"] = delta.get("delta")
                entry["generations"] = delta.get("generations")
                entry["optimized"] = bool(delta.get("generations"))
        targets_out.append(entry)

    return {"targets": targets_out}
