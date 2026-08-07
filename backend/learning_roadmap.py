"""
This is the Roadmap box: repo structure -> concept extraction -> sequencing -> roadmap.
"""
from openai import OpenAI
from github_client import fetch_repo_files
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

SYSTEM_PROMPT = """You create a learning roadmap for a developer who is new to this
codebase. Based on the file list and README content given, produce:
1. A short list of core concepts they need to understand first
2. An ordered list of files to read, with a one-line reason for each
Keep it concise and practical."""


def generate_roadmap(repo_url: str) -> dict:
    """
    Returns: {"roadmap": "... full text response ..."}
    Uses the README plus the overall file list — doesn't require the vector
    store, so it can run even before /index if you want a quick preview.
    """
    files = fetch_repo_files(repo_url)
    if not files:
        raise ValueError("Could not read any files from this repo.")

    readme = next((f["content"] for f in files if f["path"].lower().startswith("readme")), "")
    file_list = "\n".join(f["path"] for f in files)

    user_prompt = f"README:\n{readme[:3000]}\n\nFile list:\n{file_list[:3000]}"

    response = _get_client().chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    return {"roadmap": response.choices[0].message.content}
