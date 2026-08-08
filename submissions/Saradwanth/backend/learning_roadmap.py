"""Roadmap feature — graph-informed when the repo has been indexed.

Files many other files import are structurally central: the graph — not the
model — decides what "central" means, consistent with the product's design
thesis. Degrades explicitly, not silently, when the repo has not been indexed.
"""
from __future__ import annotations

from config import settings, load_prompt, repo_id_from_url
from clients.github_client import GitHubClient
from clients.llm_client import complete
from observability.tracer import trace
from graph.store import load_graph

_MAX_CENTRAL_FILES = 8


def _central_files(repo_url: str) -> list[str]:
    try:
        graph = load_graph(repo_id_from_url(repo_url))
    except (FileNotFoundError, Exception):
        return []
    ranked = sorted(graph.nodes, key=lambda p: graph.in_degree(p), reverse=True)
    return [p for p in ranked if graph.in_degree(p) > 0][:_MAX_CENTRAL_FILES]


def generate_roadmap(repo_url: str) -> dict:
    """Returns {roadmap: str, central_files: list[str]}.

    'roadmap' key is kept for backward compatibility with the frontend.
    """
    gh = GitHubClient(settings.GITHUB_TOKEN)
    repo = gh.get_repo(repo_url)
    stats = gh.repo_stats(repo)

    central = _central_files(repo_url)
    central_files_text = (
        "\n".join(f"- {p}" for p in central)
        if central
        else "(none yet — run /index first for a graph-informed roadmap)"
    )

    prompt = load_prompt("roadmap").format(
        repo_name=stats["full_name"],
        description=stats["description"] or "(no description provided)",
        language=stats["language"] or "unknown",
        topics=", ".join(stats["topics"]) or "none listed",
        central_files=central_files_text,
    )
    markdown, latency_ms = complete(prompt, temperature=0.3, max_tokens=1024)

    trace(component="roadmap", prompt=prompt, raw_output=markdown,
          latency_ms=latency_ms, extra={"repo_url": repo_url, "central_files": central})

    return {"roadmap": markdown, "central_files": central}
