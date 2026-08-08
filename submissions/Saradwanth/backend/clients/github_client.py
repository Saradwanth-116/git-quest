from __future__ import annotations
import base64
from github import Github, GithubException
from github.Repository import Repository
from config import settings


class GitHubClient:
    """TEMPPP-compatible class-based GitHub client."""

    def __init__(self, token: str):
        self._gh = Github(token)

    def get_repo(self, repo_url: str) -> Repository:
        slug = repo_url.rstrip("/").split("github.com/")[-1].removesuffix(".git")
        return self._gh.get_repo(slug)

    def list_files(self, repo: Repository, branch: str = "main") -> list[dict]:
        """Recursively list all files, returning dicts with path and size."""
        results: list[dict] = []
        stack = [""]
        while stack:
            path = stack.pop()
            try:
                items = repo.get_contents(path, ref=branch)
            except GithubException:
                continue
            if not isinstance(items, list):
                items = [items]
            for item in items:
                if item.type == "dir":
                    stack.append(item.path)
                else:
                    results.append({"path": item.path, "sha": item.sha, "size": item.size})
        return results

    def get_file(self, repo: Repository, path: str, branch: str = "main") -> str:
        content = repo.get_contents(path, ref=branch)
        return base64.b64decode(content.content).decode("utf-8", errors="replace")

    def list_issues(self, repo: Repository, state: str = "open", limit: int = 200) -> list[dict]:
        issues = []
        for issue in repo.get_issues(state=state):
            if issue.pull_request:
                continue
            issues.append({
                "number": issue.number,
                "title": issue.title,
                "body": (issue.body or "")[:800],
                "labels": [label.name for label in issue.labels],
                "created_at": issue.created_at.isoformat(),
                "updated_at": issue.updated_at.isoformat(),
                "comments": issue.comments,
                "author": issue.user.login if issue.user else None,
            })
            if len(issues) >= limit:
                break
        return issues

    def repo_stats(self, repo: Repository) -> dict:
        """Lightweight stats for the roadmap and maintainer panel."""
        return {
            "full_name": repo.full_name,
            "description": repo.description or "",
            "stars": repo.stargazers_count,
            "forks": repo.forks_count,
            "open_issues": repo.open_issues_count,
            "language": repo.language,
            "topics": repo.get_topics(),
        }
