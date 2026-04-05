import logging
from typing import Any

from qdrant_client import models

from backend.database.qdrant import get_qdrant
from backend.database.supabase import get_supabase
from backend.ingestion.embedder import generate_dense_embedding
from backend.observability.tracing import observe
from backend.retrieval.audit import log_search_audit
from backend.retrieval.reranker import rerank_results

logger = logging.getLogger(__name__)


@observe(name="Search Knowledge Base")
def search_knowledge_base(
    query: str,
    user_id: str | None = None,
    limit: int = 10,
    rerank: bool = True,
    match_threshold: float = 0.2,
) -> list[dict[str, Any]]:
    """
    Performs a hybrid search (Dense + Sparse) and optionally reranks results.
    """
    # Defensive check to convert empty strings to None (prevents query shadowing)
    if user_id and not user_id.strip():
        user_id = None

    try:
        # 1. Generate embedding for the query
        query_embedding = generate_dense_embedding(query)
        if not query_embedding:
            logger.error("Failed to generate query embedding.")
            return []

        match_count = limit * 3 if rerank else limit

        client = get_qdrant()
        initial_results = []

        # 2. Call Qdrant for dense search if available
        if client:
            try:
                # Enforce is_personal=False for all anonymous/guest queries
                # For authenticated users: (user_id == MY_ID) OR (is_personal == False)
                if user_id:
                    filter_obj = models.Filter(
                        should=[
                            models.FieldCondition(
                                key="user_id", match=models.MatchValue(value=user_id)
                            ),
                            models.FieldCondition(
                                key="is_personal", match=models.MatchValue(value=False)
                            ),
                        ]
                    )
                else:
                    filter_obj = models.Filter(
                        must=[
                            models.FieldCondition(
                                key="is_personal", match=models.MatchValue(value=False)
                            )
                        ]
                    )

                logger.info(
                    f"Searching Qdrant with filter: {filter_obj} and threshold: {match_threshold}"
                )

                # Use the most modern 'query_points' if available, otherwise fallback to 'search'
                if hasattr(client, "query_points"):
                    qdrant_response = client.query_points(
                        collection_name="nexus_chunks",
                        query=query_embedding,
                        query_filter=filter_obj,
                        limit=match_count,
                        score_threshold=match_threshold,
                        with_payload=True,
                    ).points
                else:
                    qdrant_response = client.search(
                        collection_name="nexus_chunks",
                        query_vector=query_embedding,
                        query_filter=filter_obj,
                        limit=match_count,
                        score_threshold=match_threshold,
                        with_payload=True,
                    )

                for hit in qdrant_response:
                    payload = hit.payload or {}
                    initial_results.append(
                        {
                            "id": str(hit.id),
                            "text": payload.get("text"),
                            "score": float(hit.score),
                            "document_id": payload.get("document_id"),
                            "metadata": payload,
                            "title": payload.get("title", "Unknown"),
                        }
                    )

                # Perform Search Audit
                log_search_audit(query, user_id, filter_obj, len(initial_results))

                logger.info(f"Retrieved {len(initial_results)} results from Qdrant dense search.")
            except Exception as qe:
                logger.warning(f"Qdrant search failed: {qe}")

        # 3. Fallback to Supabase RPC if Qdrant yielded nothing or failed
        if not initial_results:
            logger.info("Qdrant yielded no results. Falling back to Supabase hybrid search.")
            try:
                response = (
                    get_supabase()
                    .rpc(
                        "match_hybrid_chunks",
                        {
                            "query_embedding": query_embedding,
                            "query_text": query,
                            "query_user_id": user_id,
                            "match_threshold": match_threshold,
                            "match_count": match_count,
                        },
                    )
                    .execute()
                )
                if response.data:
                    for row in response.data:
                        metadata = row.get("metadata", {})
                        row["title"] = metadata.get("title", "Unknown")
                        row["score"] = float(row.get("score") or 0.0)
                        initial_results.append(row)
                logger.info(
                    f"Retrieved {len(initial_results)} results from Supabase hybrid search (user_id: {user_id})."
                )
            except Exception as se:
                logger.error(f"Supabase RPC search failed: {se}")

        # 4. Final Processing & Scores
        if not initial_results:
            return {"chunks": [], "meta": {"hybrid_boost": False, "reranked": False}}

        hybrid_boost_triggered = False
        # Ensure similarity_score is preserved for fusion
        for hit in initial_results:
            hit["similarity_score"] = float(hit.get("score") or 0.0)

        # 5. Semantic Keyword Boost (The "mymailkeeper" fix)
        # If the query contains rare/unique tokens, we perform an exact string match
        # over the candidates to ensure high-value keywords aren't buried.
        query_parts = query.lower().split()
        for hit in initial_results:
            text = hit.get("text", "").lower()
            for part in query_parts:
                # Heuristic for rare tokens: length > 4
                if len(part) > 4 and part in text:
                    # Elevate the base score for the reranker to observe
                    hit["similarity_score"] = max(hit["similarity_score"], 0.95)
                    hybrid_boost_triggered = True

        # 6. Optional Reranking (Cross-Encoder)
        if rerank:
            final_results = rerank_results(query, initial_results, top_k=limit)
            logger.info(f"Reranked results to top {len(final_results)}.")
        else:
            final_results = initial_results[:limit]

        # Ensure every final chunk has a 'match_score' for the UI
        for chunk in final_results:
            # SHIELD BOOSTED SCORES: Use the max of rerank and similarity to ensure
            # manual keyword boosts (0.95) aren't buried by a semantic reranker.
            chunk["match_score"] = float(
                max(chunk.get("rerank_score", 0.0), chunk.get("similarity_score", 0.0))
            )

        return {
            "chunks": final_results,
            "meta": {
                "hybrid_boost": hybrid_boost_triggered,
                "reranked": rerank,
                "count": len(final_results),
            },
        }

    except Exception as e:
        logger.error(f"Error in search_knowledge_base: {e}")
        return {"chunks": [], "meta": {"hybrid_boost": False, "reranked": False}}
