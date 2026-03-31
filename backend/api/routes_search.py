import random
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from backend.evaluation.llm_judge import llm_judge_evaluate_async
from backend.evaluation.ragas_eval import run_ragas_eval_async
from backend.observability.tracing import observe
from backend.retrieval.generator import generate_answer
from backend.retrieval.searcher import search_knowledge_base

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    rerank: bool = True
    match_threshold: float = 0.3


class SearchResult(BaseModel):
    id: str
    document_id: str
    text: str
    header: str | None = None
    metadata: dict[str, Any]
    similarity: float
    rerank_score: float | None = None


class AskResponse(BaseModel):
    answer: str
    context: list[SearchResult]


@router.post("/search", response_model=list[SearchResult])
@observe(name="API: Search")
def search_chunks(request: SearchRequest):
    """
    Endpoint to search the ingested knowledge base using hybrid search and reranking.
    """
    try:
        results = search_knowledge_base(
            query=request.query,
            limit=request.limit,
            rerank=request.rerank,
            match_threshold=request.match_threshold,
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask", response_model=AskResponse)
@observe(name="API: Ask RAG")
def ask_question(request: SearchRequest, background_tasks: BackgroundTasks):
    """
    Unified RAG endpoint: Search -> Rerank -> Generate Answer.
    """
    try:
        # 1. Search and Rerank
        context_chunks = search_knowledge_base(
            query=request.query,
            limit=request.limit,
            rerank=request.rerank,
            match_threshold=request.match_threshold,
        )

        if not context_chunks:
            return AskResponse(
                answer="No relevant information was found in the knowledge base to answer your question.",
                context=[],
            )

        # 2. Generate Answer
        answer = generate_answer(request.query, context_chunks)

        # 3. Online Evaluation Sampling (5%)
        # We sample asynchronously using BackgroundTasks to not affect latency
        if random.random() < 0.05:
            from langfuse.decorators import langfuse_context

            trace_id = langfuse_context.get_current_trace_id()
            context_str = "\n".join([c["text"] for c in context_chunks])

            background_tasks.add_task(
                run_ragas_eval_async,
                request.query,
                answer,
                [c["text"] for c in context_chunks],
                trace_id,
            )
            background_tasks.add_task(
                llm_judge_evaluate_async, request.query, answer, context_str, trace_id
            )

        return AskResponse(answer=answer, context=context_chunks)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
