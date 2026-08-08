"""Production home of Mutagent target #1's prompt (mutagent/prompts/issue_rec.txt).

Formats repo_context in the exact shape mutagent/datasets/issue_rec.json uses
("Issue #N: 'title' [labels]", no body text) — real traffic and the eval both
exercise the identical input distribution.
"""
from __future__ import annotations

from config import settings, load_prompt
from clients.github_client import GitHubClient
from clients.llm_client import extract_json, complete
from observability.tracer import trace

_MAX_ISSUES = 30


def _format_repo_context(issues: list[dict]) -> str:
    lines = []
    for issue in issues[:_MAX_ISSUES]:
        labels = ", ".join(issue["labels"])
        lines.append(f"Issue #{issue['number']}: '{issue['title']}' [{labels}]")
    return "\n".join(lines)


def recommend_issue(repo_url: str, user_profile: str = "general contributor") -> dict:
    """Returns {issue_id: int|null, title: str|null, rationale: str}.

    issue_id null is a designed, successful outcome — it means no open issue
    is an appropriate match, not that something failed.
    """
    gh = GitHubClient(settings.GITHUB_TOKEN)
    repo = gh.get_repo(repo_url)
    issues = gh.list_issues(repo, state="open", limit=_MAX_ISSUES)

    if not issues:
        return {"issue_id": None, "title": None,
                "rationale": "This repository has no open issues to recommend."}

    prompt = load_prompt("issue_rec").format(
        user_profile=user_profile,
        repo_context=_format_repo_context(issues),
    )
    raw_output, latency_ms = complete(prompt, temperature=0.1)

    trace(component="issue_rec", prompt=prompt, raw_output=raw_output,
          latency_ms=latency_ms, extra={"repo_url": repo_url})

    parsed = extract_json(raw_output)
    if parsed is None or "issue_id" not in parsed:
        return {"issue_id": None, "title": None,
                "rationale": f"Could not parse a recommendation: {raw_output[:200]!r}"}

    issue_id = parsed.get("issue_id")
    rationale = parsed.get("rationale", "")
    title = next((i["title"] for i in issues if i["number"] == issue_id), None)

    # Ground the id against what was actually shown — a hallucination prevention check.
    if issue_id is not None and title is None:
        return {"issue_id": None, "title": None,
                "rationale": f"Model referenced issue #{issue_id}, which is not "
                             f"in the current open issues list; treating as no match."}

    return {"issue_id": issue_id, "title": title, "rationale": rationale}
