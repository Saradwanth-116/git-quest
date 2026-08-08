"""
This module handles running a local Cross-Encoder re-ranker model.
It uses sentence-transformers, which is highly robust and avoids the memory issues of raw llama.cpp.
"""

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None

_reranker_model = None

def _get_reranker():
    global _reranker_model
    if _reranker_model is None:
        if CrossEncoder is None:
            raise ImportError("sentence-transformers is not installed. Please run `pip install sentence-transformers`.")
            
        print("Loading local bge-reranker model (this may take a moment on first boot)...")
        # Initialize the robust CrossEncoder
        # It will automatically download the required files to your local cache
        _reranker_model = CrossEncoder("BAAI/bge-reranker-base")
    return _reranker_model

def rerank_documents(query: str, documents: list[str], metadatas: list[dict], top_n: int = 5) -> tuple[list[str], list[dict]]:
    """
    Takes a list of documents and re-scores them against the query using a local Cross-Encoder.
    Returns the newly sorted top N documents and their metadata.
    """
    if not documents:
        return [], []
        
    model = _get_reranker()
    
    # CrossEncoder expects a list of pairs: [[query, doc1], [query, doc2], ...]
    pairs = [[query, doc] for doc in documents]
    
    # Predict the relevance scores
    scores = model.predict(pairs)
    
    # Sort documents and metadata by the generated score (descending)
    paired = list(zip(scores, documents, metadatas))
    paired.sort(key=lambda x: x[0], reverse=True)
    
    # Extract the top N
    top_docs = [item[1] for item in paired[:top_n]]
    top_metas = [item[2] for item in paired[:top_n]]
    
    return top_docs, top_metas
