"""
This is the PR check box: checklist rules (+ optional similar PRs) -> LLM synthesis -> report.
"""
from openai import OpenAI
from config import settings

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.GROQ_API_KEY, 
            base_url="https://api.groq.com/openai/v1"
        )
    return _client

SYSTEM_PROMPT = """You review a pull request diff for readiness before submission.
Given the checklist results below, write a short readiness report: what's good,
what's missing, and whether you'd recommend submitting as-is or making changes first."""


def _run_checklist(diff_text: str) -> dict:
    """
    Deterministic, rule-based checks — no LLM needed for these, so they're
    fast and never hallucinate.
    """
    lower = diff_text.lower()
    has_tests = any(line.startswith('+++ ') and 'test' in line for line in lower.splitlines())
    return {
        "has_tests": has_tests,
        "touches_docs": any(name in lower for name in ["readme", ".md", "docs/"]),
        "diff_size_lines": diff_text.count("\n"),
        "is_large_diff": diff_text.count("\n") > 300,
    }


def check_pr_readiness(diff_text: str) -> dict:
    """
    Returns: {"checklist": {...}, "report": "... LLM-written summary ..."}

    diff_text is the raw unified diff (e.g. from `git diff` or the GitHub
    compare API). Similar-PR retrieval is skipped here — it's the optional
    stretch feature from the plan; add it later by fetching github_client
    .fetch_merged_prs() and passing a few into the prompt below.
    """
    checklist = _run_checklist(diff_text)

    checklist_text = "\n".join(f"- {key}: {value}" for key, value in checklist.items())

    response = _get_client().chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Checklist results:\n{checklist_text}\n\nDiff:\n{diff_text[:4000]}"},
        ],
    )

    return {"checklist": checklist, "report": response.choices[0].message.content}
