import logging
from typing import Any

from backend.database.supabase import get_supabase
from backend.ingestion.embedder import generate_dense_embedding
from backend.observability.tracing import observe
from backend.retrieval.reranker import rerank_results

logger = logging.getLogger(__name__)


@observe(name="Search Knowledge Base")
def search_knowledge_base(
    query: str, limit: int = 10, rerank: bool = True, match_threshold: float = 0.2
) -> list[dict[str, Any]]:
    """
    Performs a hybrid search (Dense + Sparse) and optionally reranks results.
    """
    try:
        # 1. Generate embedding for the query
        query_embedding = generate_dense_embedding(query)
        if not query_embedding:
            logger.error("Failed to generate query embedding.")
            return []

        # 2. Call Supabase RPC for hybrid search
        # match_count is high so we have enough candidates for reranking
        match_count = limit * 3 if rerank else limit

        response = (
            get_supabase()
            .rpc(
                "match_hybrid_chunks",
                {
                    "query_embedding": query_embedding,
                    "query_text": query,
                    "match_threshold": match_threshold,
                    "match_count": match_count,
                },
            )
            .execute()
        )

        initial_results = response.data if response.data else []
        logger.info(f"Retrieved {len(initial_results)} results from hybrid search.")

        # 3. Optional Reranking
        if rerank and initial_results:
            final_results = rerank_results(query, initial_results, top_k=limit)
            logger.info(f"Reranked results to top {len(final_results)}.")
        else:
            final_results = initial_results[:limit]

        return final_results

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []
