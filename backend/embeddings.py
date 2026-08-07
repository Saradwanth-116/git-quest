"""
Two jobs:
1. chunk_text() — splits long text into overlapping token-sized pieces
2. embed_texts() — calls Gemini to turn a list of text chunks into vectors
"""
import tiktoken
import requests
from config import settings

_encoding = tiktoken.get_encoding("cl100k_base")


def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> list[str]:
    """
    Splits text into overlapping chunks measured in tokens (not characters),
    so chunk size stays consistent regardless of language or formatting.
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP

    text = text.strip()
    if not text:
        return []
        
    tokens = _encoding.encode(text)
    if len(tokens) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(tokens):
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunks.append(_encoding.decode(chunk_tokens))
        start += chunk_size - overlap  # step forward, leaving "overlap" tokens repeated

    return chunks


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Batches texts to Gemini's embeddings REST API endpoint. Returns one vector per input text,
    in the same order.
    """
    if not texts:
        return []

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.EMBEDDING_MODEL}:batchEmbedContents?key={settings.GEMINI_API_KEY}"
    data = {
        "requests": [
            {
                "model": f"models/{settings.EMBEDDING_MODEL}",
                "content": {"parts": [{"text": text}]}
            }
            for text in texts
        ]
    }
    import time
    for attempt in range(5):
        response = requests.post(url, json=data)
        if response.status_code == 429:
            print(f"Gemini API rate limit hit. Waiting 15 seconds before retrying (Attempt {attempt + 1}/5)...")
            time.sleep(15)
            continue
            
        response.raise_for_status()
        result = response.json()
        return [item["values"] for item in result.get("embeddings", [])]
        
    response.raise_for_status()
    return []
