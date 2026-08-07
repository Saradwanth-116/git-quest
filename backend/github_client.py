"""
Thin wrapper around PyGithub. Handles all the calls out to GitHub:
- pulling repo file contents (code + docs)
- pulling open issues
- pulling merged PRs (for the optional "similar PRs" feature)
"""
from github import Github, Auth
from config import settings

# Text-like file extensions worth indexing. Skip binaries, images, lockfiles, etc.
INDEXABLE_EXTENSIONS = {
    ".md", ".mdx", ".txt", ".rst",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".rs", ".c", ".cpp", ".h",
    ".html", ".css",".json",".yml",
}

MAX_FILE_SIZE_BYTES = 200_000  # skip huge generated files


def _get_client() -> Github:
    if settings.GITHUB_TOKEN:
        return Github(auth=Auth.Token(settings.GITHUB_TOKEN))
    return Github()  # unauthenticated — works, but low rate limit


def get_rate_limit_status() -> dict:
    """
    Returns the current GitHub API rate limit status.
    """
    core = _get_client().get_rate_limit().core
    return {
        "limit": core.limit,
        "remaining": core.remaining,
        "reset": core.reset.isoformat()
    }


def parse_repo_url(repo_url: str) -> str:
    """
    Turns "https://github.com/owner/name" or "owner/name" into "owner/name".
    """
    repo_url = repo_url.strip().rstrip("/")
    if "github.com" in repo_url:
        repo_url = repo_url.split("github.com/")[-1]
    return repo_url.replace(".git", "")


def fetch_repo_files(repo_url: str) -> tuple[list[dict], int]:
    """
    Walks the default branch and returns a list of:
      {"path": "src/app.py", "content": "...", "type": "code"}
    Only text files under MAX_FILE_SIZE_BYTES with an indexable extension are returned.
    """
    client = _get_client()
    repo = client.get_repo(parse_repo_url(repo_url))

    results = []
    total_files = 0
    contents = repo.get_contents("")  # start at repo root
    stack = list(contents)

    while stack:
        item = stack.pop()
        if item.type == "dir":
            stack.extend(repo.get_contents(item.path))
            continue
            
        total_files += 1

        ext = "." + item.name.split(".")[-1] if "." in item.name else ""
        if ext not in INDEXABLE_EXTENSIONS:
            continue
        if item.size > MAX_FILE_SIZE_BYTES:
            continue

        try:
            text = item.decoded_content.decode("utf-8", errors="ignore")
        except Exception:
            continue  # skip anything that fails to decode (likely binary)

        file_type = "docs" if ext in {".md", ".mdx", ".txt", ".rst"} else "code"
        results.append({"path": item.path, "content": text, "type": file_type})

    return results, total_files


def fetch_open_issues(repo_url: str, limit: int = 50) -> list[dict]:
    """
    Returns open issues as: {"number": 12, "title": "...", "body": "...", "labels": [...]}
    Pull requests are excluded (GitHub's API lists them alongside issues).
    """
    client = _get_client()
    repo = client.get_repo(parse_repo_url(repo_url))

    issues = []
    for issue in repo.get_issues(state="open"):
        if len(issues) >= limit:
            break
        if issue.pull_request is not None:
            continue  # this "issue" is actually a PR, skip it
        issues.append({
            "number": issue.number,
            "title": issue.title,
            "body": issue.body or "",
            "labels": [label.name for label in issue.labels],
        })
    return issues


def fetch_merged_prs(repo_url: str, limit: int = 30) -> list[dict]:
    """
    Returns recently merged PRs as: {"number": 5, "title": "...", "body": "..."}
    Used only by the optional "similar past PRs" feature in PR readiness.
    """
    client = _get_client()
    repo = client.get_repo(parse_repo_url(repo_url))

    prs = []
    for pr in repo.get_pulls(state="closed", sort="updated", direction="desc"):
        if len(prs) >= limit:
            break
        if pr.merged:
            prs.append({"number": pr.number, "title": pr.title, "body": pr.body or ""})
    return prs
