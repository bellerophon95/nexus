import logging
from typing import List, Dict, Any
from sentence_transformers import CrossEncoder
from backend.observability.tracing import observe

logger = logging.getLogger(__name__)

# Load the cross-encoder model eagerly
model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
logger.info(f"Loading Cross-Encoder model: {model_name}")
try:
    _model = CrossEncoder(model_name)
    logger.info("Cross-Encoder model loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load Cross-Encoder model: {e}")
    _model = None # Fallback or keep for robust handling

@observe()
def rerank_results(query: str, chunks: List[Dict[str, Any]], top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Reranks a list of retrieved chunks using a Cross-Encoder for higher precision.
    """
    if not chunks or _model is None:
        return chunks[:top_k]

    model = _model
    
    # Prepare pairs for cross-encoder (Query, [Title + Text])
    pairs = []
    for chunk in chunks:
        # If title is available from the new metadata-aware search, prepend it
        title_prefix = f"Document: {chunk.get('title', 'Unknown')}\n"
        content = f"{title_prefix}Text: {chunk['text']}"
        pairs.append([query, content])
    
    # Predict relevance scores
    scores = model.predict(pairs)
    
    # Add scores back to chunks
    for i, chunk in enumerate(chunks):
        chunk["rerank_score"] = float(scores[i])
        
    # Sort by rerank score descending
    reranked = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
    
    # Return top K
    return reranked[:top_k]
