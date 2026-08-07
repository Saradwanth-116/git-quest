"""
Run this with:  uvicorn main:app --reload
Then open:      http://127.0.0.1:8000/docs   (auto-generated test UI)
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from indexing import index_repo
from rag_qa import ask_question
from issue_recommendation import recommend_issue
from learning_roadmap import generate_roadmap
from pr_readiness import check_pr_readiness
from github_client import get_rate_limit_status

app = FastAPI(title="AI Open Source Mentor++")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IndexRequest(BaseModel):
    repo_url: str


class QuestionRequest(BaseModel):
    repo_url: str
    question: str


class RoadmapRequest(BaseModel):
    repo_url: str


class PRCheckRequest(BaseModel):
    diff_text: str


@app.post("/index")
def index_endpoint(req: IndexRequest):
    """Step 1: always call this first for a new repo."""
    try:
        return index_repo(req.repo_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/ask")
def ask_endpoint(req: QuestionRequest):
    """RAG Q&A — repo must already be indexed."""
    try:
        return ask_question(req.repo_url, req.question)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/recommend-issue")
def recommend_issue_endpoint(repo_url: str):
    """Issue recommendation — doesn't require indexing, just the repo URL."""
    try:
        return recommend_issue(repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/roadmap")
def roadmap_endpoint(req: RoadmapRequest):
    """Learning roadmap — doesn't require indexing either."""
    try:
        return generate_roadmap(req.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/pr-check")
def pr_check_endpoint(req: PRCheckRequest):
    """PR readiness — paste a unified diff, get a readiness report."""
    try:
        return check_pr_readiness(req.diff_text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/rate-limit")
def rate_limit_endpoint():
    """Get the current GitHub API rate limit status."""
    try:
        return get_rate_limit_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/")
def health_check():
    return {"status": "ok", "message": "AI Open Source Mentor++ is running"}
