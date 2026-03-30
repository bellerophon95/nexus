from typing import List, Dict, Any
import numpy as np
from collections import Counter
import re
import logging
from backend.observability.tracing import observe

logger = logging.getLogger(__name__)

# Lazy loading of model
_model = None

def get_embedder_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Consistent model with the chunker
            _model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            logger.error(f"Failed to load embedder model: {e}")
            raise
    return _model

def generate_dense_embedding(text: str) -> List[float]:
    """
    Generates a 384-dimensional dense vector using all-MiniLM-L6-v2.
    """
    try:
        model = get_embedder_model()
        embedding = model.encode(text)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Dense embedding generation failed: {e}")
        return []

def generate_dense_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Generates dense embeddings for a batch of texts using all-MiniLM-L6-v2.
    Significantly faster than generating one by one for large document sets.
    """
    try:
        model = get_embedder_model()
        # Using a reasonable batch size for local execution
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)
        return embeddings.tolist()
    except Exception as e:
        logger.error(f"Batch dense embedding generation failed: {e}")
        return [[] for _ in texts]

def generate_sparse_tokens(text: str) -> Dict[str, int]:
    """
    Generates a sparse representation (bag-of-words) for the text.
    Used for hybrid search.
    """
    try:
        # Simple tokenization: lowercase, alphanumeric words
        words = re.findall(r'\b\w{2,}\b', text.lower())
        return dict(Counter(words))
    except Exception as e:
        logger.error(f"Sparse token generation failed: {e}")
        return {}

@observe()
def embed_chunk(text: str) -> Dict[str, Any]:
    """
    Generates both dense and sparse embeddings for a single text chunk.
    """
    dense = generate_dense_embedding(text)
    sparse = generate_sparse_tokens(text)
    
    return {
        "embedding": dense,
        "sparse_tokens": sparse
    }

def embed_chunks_batch(texts: List[str]) -> List[Dict[str, Any]]:
    """
    Generates embeddings for a list of chunks efficiently.
    """
    dense_embeddings = generate_dense_embeddings_batch(texts)
    results = []
    for i, text in enumerate(texts):
        results.append({
            "embedding": dense_embeddings[i],
            "sparse_tokens": generate_sparse_tokens(text)
        })
    return results
