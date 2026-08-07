"""
This is the Issue rec box: open issues + labels -> feature extraction -> LLM ranking -> top issue.
"""
import json
from openai import OpenAI
from github_client import fetch_open_issues
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

GOOD_FIRST_LABELS = {"good first issue", "good-first-issue", "help wanted", "beginner friendly"}

SYSTEM_PROMPT = """You recommend one GitHub issue for a developer who is new to this
repository. Prefer issues labeled for beginners. Respond in JSON format with exactly
two keys: "number" (the integer issue number you recommend) and "explanation" 
(a short 2-3 sentence explanation of why it's a good starting point)."""


def _score_issue(issue: dict) -> int:
    """Simple heuristic: beginner-friendly labels score higher, no ML needed."""
    labels_lower = {label.lower() for label in issue["labels"]}
    return 2 if labels_lower & GOOD_FIRST_LABELS else 0


def recommend_issue(repo_url: str) -> dict:
    """
    Returns: {"number": 12, "title": "...", "explanation": "..."}
    Raises a ValueError if there are no open issues.
    """
    issues = fetch_open_issues(repo_url)
    if not issues:
        raise ValueError("No open issues found in this repo.")

    # Pre-sort by heuristic score so the LLM sees the most promising ones first.
    issues.sort(key=_score_issue, reverse=True)
    top_candidates = issues[:10]

    issue_list_text = "\n\n".join(
        f"#{issue['number']}: {issue['title']}\nLabels: {', '.join(issue['labels'])}\n{issue['body'][:300]}"
        for issue in top_candidates
    )

    response = _get_client().chat.completions.create(
        model=settings.LLM_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Candidate issues:\n\n{issue_list_text}"},
        ],
    )

    try:
        result = json.loads(response.choices[0].message.content)
        issue_number = result.get("number", top_candidates[0]["number"])
        explanation = result.get("explanation", "No explanation provided.")
    except Exception:
        # Fallback if LLM fails to output valid JSON
        issue_number = top_candidates[0]["number"]
        explanation = response.choices[0].message.content

    # Find the title matching the recommended issue number
    issue_title = next((issue["title"] for issue in top_candidates if issue["number"] == issue_number), top_candidates[0]["title"])

    return {
        "number": issue_number,
        "title": issue_title,
        "explanation": explanation,
    }
