"""Production home of Mutagent target #5's prompt (mutagent/prompts/pr_check.txt).

The checklist fields and their formatting deliberately match mutagent/
datasets/pr_check.json exactly — field names, lowercase true/false — so
real traffic and the eval both exercise the same input distribution.
"""
from __future__ import annotations

import re

from config import load_prompt
from clients.llm_client import extract_json, complete
from observability.tracer import trace

_LARGE_DIFF_THRESHOLD = 300
_SECURITY_PATH_RE = re.compile(
    r"(auth|permission|session|crypto|secret|credential|admin|password|token)",
    re.IGNORECASE,
)
_TOUCHED_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


def _touched_files(diff_text: str) -> list[str]:
    return [m.strip() for m in _TOUCHED_FILE_RE.findall(diff_text)]


def _is_test_file(path: str) -> bool:
    return "test" in path.lower() or path.startswith("tests/") or path.startswith("spec/")


def _compute_checklist(diff_text: str) -> dict:
    files = _touched_files(diff_text)
    diff_size_lines = diff_text.count("\n")
    return {
        "has_tests": any(_is_test_file(f) for f in files),
        "touches_docs": any(f.endswith(".md") or "docs/" in f for f in files),
        "diff_size_lines": diff_size_lines,
        "is_large_diff": diff_size_lines > _LARGE_DIFF_THRESHOLD,
        "touches_security_sensitive_path": any(_SECURITY_PATH_RE.search(f) for f in files),
    }


def _format_checklist(checklist: dict) -> str:
    return "\n".join(
        f"{k}: {str(v).lower() if isinstance(v, bool) else v}"
        for k, v in checklist.items()
    )


def check_pr_readiness(diff_text: str) -> dict:
    """Returns {checklist: dict, verdict: str|None, report: str, rationale: str}.

    'report' key kept for backward compat with the existing frontend.
    """
    checklist = _compute_checklist(diff_text)

    prompt = load_prompt("pr_check").format(
        checklist=_format_checklist(checklist),
        diff=diff_text[:4000],
    )
    raw_output, latency_ms = complete(prompt, temperature=0.1)

    trace(component="pr_check", prompt=prompt, raw_output=raw_output,
          latency_ms=latency_ms, extra={"checklist": checklist})

    parsed = extract_json(raw_output)
    if parsed is None or parsed.get("verdict") not in ("ready", "needs_changes", "blocked"):
        return {
            "checklist": checklist,
            "verdict": None,
            "report": f"Could not parse a verdict: {raw_output[:200]!r}",
            "rationale": "",
        }

    return {
        "checklist": checklist,
        "verdict": parsed["verdict"],
        "report": parsed.get("rationale", ""),  # 'report' for frontend compat
        "rationale": parsed.get("rationale", ""),
    }
