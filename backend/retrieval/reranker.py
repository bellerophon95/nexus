import logging
from typing import Any

import cohere

from backend.config import settings
from backend.observability.tracing import observe

logger = logging.getLogger(__name__)

# Global lazy client
_cohere_client = None


def get_cohere_client() -> cohere.Client | None:
    """
    Lazy loader for Cohere client.
    Returns None if COHERE_API_KEY is not configured, which triggers a graceful fallback.
    """
    global _cohere_client
    if _cohere_client is None:
        if not settings.COHERE_API_KEY:
            logger.warning("COHERE_API_KEY not set — reranking will be skipped.")
            return None
        _cohere_client = cohere.Client(api_key=settings.COHERE_API_KEY)
        logger.info("Cohere rerank client initialized.")
    return _cohere_client


# Keep get_model() as a no-op stub so input_guard warmup_guardrails() doesn't break.
# Previously warmed up the SentenceTransformer CrossEncoder — now a safe no-op.
def get_model():
    """Stub retained for backwards compatibility with warmup_guardrails()."""
    return None


@observe()
def rerank_results(
    query: str, chunks: list[dict[str, Any]], top_k: int = 10
) -> list[dict[str, Any]]:
    """
    Reranks a list of retrieved chunks using Cohere Rerank API (rerank-english-v3.0).
    Falls back to original order if the API is unavailable or key is missing.
    Cost: ~$1 per 1,000 calls (significantly cheaper than running a local CrossEncoder).
    """
    if not chunks:
        return []

    client = get_cohere_client()

    # Graceful fallback: if no client (key missing or error), return top_k by original score
    if client is None:
        logger.warning("Cohere client unavailable — returning top_k by original vector score.")
        return chunks[:top_k]

    try:
        # Prepare documents for Cohere — include title for richer signal
        documents = []
        for chunk in chunks:
            title = chunk.get("title") or chunk.get("metadata", {}).get("title", "")
            text = chunk.get("text", "")
            doc = f"{title}\n{text}".strip() if title else text
            documents.append(doc)

        response = client.rerank(
            model="rerank-english-v3.0",
            query=query,
            documents=documents,
            top_n=top_k,
            return_documents=False,  # We already have the docs, just need scores
        )

        # Map Cohere's ordered results back to our chunk dicts
        reranked = []
        for result in response.results:
            chunk = chunks[result.index].copy()
            chunk["rerank_score"] = result.relevance_score
            reranked.append(chunk)

        logger.info(
            f"Cohere rerank: {len(chunks)} → top {len(reranked)} "
            f"(top score: {reranked[0]['rerank_score']:.3f})"
        )
        return reranked

    except cohere.errors.TooManyRequestsError:
        logger.warning("Cohere rate limit hit — falling back to vector score ordering.")
        return chunks[:top_k]
    except Exception as e:
        logger.error(f"Cohere rerank failed: {e} — falling back to vector score ordering.")
        return chunks[:top_k]
