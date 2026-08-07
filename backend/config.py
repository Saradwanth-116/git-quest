"""
Loads settings from your .env file into one place so every other file
can just do: from config import settings
"""
import os

# Disable ChromaDB telemetry globally before anything is imported
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from dotenv import load_dotenv

load_dotenv()  # reads the ".env" file in this folder and loads it into the environment


class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")

    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

    TOP_K: int = int(os.getenv("TOP_K", "25"))
    RERANK_TOP_K: int = int(os.getenv("RERANK_TOP_K", "5"))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))


settings = Settings()

# Warn if the required key is missing, but don't crash — lets the server start
# so the frontend can at least connect.
if not settings.OPENAI_API_KEY:
    import warnings
    warnings.warn("OPENAI_API_KEY is not set. Copy .env.example to .env and add your key.")
