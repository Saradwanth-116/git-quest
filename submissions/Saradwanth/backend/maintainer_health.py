"""Production home of Mutagent target #6's prompt (mutagent/prompts/issue_health.txt).

Implements GET /maintainer-health per design's API spec:
    {score, mislabelled[], latency_days, scanned}

mislabelled[] is the feature design calls "the differentiation nobody else
shows" — issues carrying a beginner-oriented label the model judges
inappropriate for a newcomer, given the issue's actual content.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from config import settings, load_prompt
from clients.github_client import GitHubClient
from clients.llm_client import extract_json, complete
from observability.tracer import trace

_MAX_ISSUES = 30
_VALID_VERDICTS = {"healthy", "mislabelled", "vague", "stale"}

# Coarse text heuristic for linked PRs — not a real link check.
_PR_LINK_RE = re.compile(
    r"(closes|fixes|resolves|see)\s+#\d+|pull request|PR\s*#\d+", re.IGNORECASE
)


def _parse_ts(iso_ts: str) -> datetime:
    return datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))


def _days_since(iso_ts: str) -> int:
    return max((datetime.now(timezone.utc) - _parse_ts(iso_ts)).days, 0)


def _format_issue(issue: dict) -> str:
    labels = ", ".join(issue["labels"]) or "(none)"
    body = issue["body"].strip() or "(no description provided)"
    return f"Title: {issue['title']}\nLabels: {labels}\nBody: {body}"


def _format_signals(issue: dict) -> str:
    has_linked_pr = bool(_PR_LINK_RE.search(issue["body"]))
    return (
        f"days_open: {_days_since(issue['created_at'])}\n"
        f"comment_count: {issue['comments']}\n"
        f"has_linked_pr: {str(has_linked_pr).lower()}"
    )


def get_maintainer_health(repo_url: str) -> dict:
    """Returns {score, mislabelled: [...], latency_days, scanned}.

    score: fraction of scanned issues classified healthy.
    latency_days: median days between issue creation and last update.
    """
    gh = GitHubClient(settings.GITHUB_TOKEN)
    repo = gh.get_repo(repo_url)
    issues = gh.list_issues(repo, state="open", limit=_MAX_ISSUES)

    if not issues:
        return {"score": None, "mislabelled": [], "latency_days": None, "scanned": 0}

    prompt_template = load_prompt("issue_health")
    verdicts: list[str | None] = []
    mislabelled: list[dict] = []
    update_lags: list[int] = []

    for issue in issues:
        prompt = prompt_template.format(
            issue=_format_issue(issue),
            signals=_format_signals(issue),
        )
        raw_output, latency_ms = complete(prompt, temperature=0.1)
        trace(component="issue_health", prompt=prompt, raw_output=raw_output,
              latency_ms=latency_ms, extra={"issue_number": issue["number"]})

        parsed = extract_json(raw_output)
        verdict = parsed.get("verdict") if parsed else None
        rationale = parsed.get("rationale", "") if parsed else raw_output[:200]
        if verdict not in _VALID_VERDICTS:
            verdict = None
        verdicts.append(verdict)

        if verdict == "mislabelled":
            mislabelled.append({
                "number": issue["number"],
                "title": issue["title"],
                "rationale": rationale,
            })

        update_lags.append(max(
            (_parse_ts(issue["updated_at"]) - _parse_ts(issue["created_at"])).days, 0
        ))

    scored = [v for v in verdicts if v is not None]
    score = round(sum(1 for v in scored if v == "healthy") / len(scored), 4) if scored else None
    update_lags.sort()
    latency_days = update_lags[len(update_lags) // 2] if update_lags else None

    return {
        "score": score,
        "mislabelled": mislabelled,
        "latency_days": latency_days,
        "scanned": len(issues),
    }
