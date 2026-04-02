import asyncio
import json
import logging
import random
from collections.abc import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.agents.graph import nexus_graph
from backend.api.security import get_user_id
from backend.config import settings
from backend.evaluation.llm_judge import llm_judge_evaluate_async
from backend.evaluation.ragas_eval import run_ragas_eval_async
from backend.guardrails.input_guard import run_input_guardrails
from backend.guardrails.output_guard import run_output_guardrails
from backend.observability.cost_tracker import calculate_cost, score_cost
from backend.observability.tracing import observe

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    query: str
    max_iterations: int = 3


@router.post("/chat")
@observe(name="API: Agentic Chat (Stream)")
async def chat_agents(request: ChatRequest, user_id: str | None = Depends(get_user_id)):
    """
    Unified agentic chat endpoint that runs the LangGraph workflow.
    Streams back individual agent steps as JSON.
    """
    # 1. Input Guardrails
    pii_types = []
    current_query = request.query
    if settings.GUARDRAILS_ENABLED:
        guard_result = run_input_guardrails(request.query)
        if not guard_result.passed:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "Guardrail violation",
                    "reason": guard_result.blocked_reason,
                    "sanitized": guard_result.sanitized_content,
                },
            )
        current_query = guard_result.sanitized_content
        pii_types = guard_result.pii_detected

    async def event_generator() -> AsyncGenerator[str, None]:
        # Initialize state
        state = {
            "messages": [],
            "current_agent": "supervisor",
            "retrieved_chunks": [],
            "iteration_count": 0,
            "max_iterations": request.max_iterations,
            "validation_status": "pending",
            "hallucination_score": 0.0,
            "final_answer": "",
            "pii_detected": pii_types,
            "query": current_query,
            "user_id": user_id,
        }

        try:
            # Run graph in async loop (if configured, streaming results)
            async for step in nexus_graph.astream(state):
                # 'step' is a dict of {node_name: state_updates}
                node_name = next(iter(step.keys()))
                updates = step[node_name]

                # Filter down what to send to client
                safe_updates = {
                    "node": node_name,
                    "agent": updates.get("current_agent", ""),
                    "status": updates.get("validation_status", "working"),
                    "final_answer": updates.get("final_answer", ""),
                }

                # Output Guardrail on final answer
                if safe_updates["final_answer"]:
                    output_guard = await run_output_guardrails(
                        safe_updates["final_answer"], updates.get("retrieved_chunks", [])
                    )
                    if not output_guard.passed:
                        safe_updates["final_answer"] = output_guard.sanitized_content
                        safe_updates["status"] = "blocked"
                        safe_updates["warning"] = output_guard.blocked_reason

                yield f"data: {json.dumps(safe_updates)}\n\n"
                await asyncio.sleep(0.1)

            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/ask_agent")
@observe(name="API: Agentic Ask (Sync)")
async def ask_agent(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    user_id: str | None = Depends(get_user_id),
):
    """
    Synchronous version of the agent chat for simpler consumers.
    """
    # 1. Input Guardrails
    pii_types = []
    current_query = request.query
    if settings.GUARDRAILS_ENABLED:
        guard_result = run_input_guardrails(request.query)
        if not guard_result.passed:
            raise HTTPException(status_code=422, detail=guard_result.blocked_reason)
        current_query = guard_result.sanitized_content
        pii_types = guard_result.pii_detected

    state = {
        "messages": [],
        "current_agent": "supervisor",
        "retrieved_chunks": [],
        "iteration_count": 0,
        "max_iterations": request.max_iterations,
        "validation_status": "pending",
        "hallucination_score": 0.0,
        "final_answer": "",
        "pii_detected": pii_types,
        "query": current_query,
        "user_id": user_id,
    }

    try:
        final_state = await nexus_graph.ainvoke(state)
        answer = final_state["final_answer"]

        # 2. Output Guardrails
        if settings.GUARDRAILS_ENABLED:
            output_guard = await run_output_guardrails(
                answer, final_state.get("retrieved_chunks", [])
            )
            answer = output_guard.sanitized_content
            pii_types.extend(output_guard.pii_detected)

        # 3. Post-processing (Cost & Eval) in background
        from langfuse.decorators import langfuse_context

        trace_id = langfuse_context.get_current_trace_id()

        if trace_id:
            # Calculate costs from messages
            total_cost = 0.0
            for msg in final_state.get("messages", []):
                # LangChain messages have response_metadata
                if hasattr(msg, "response_metadata") and "token_usage" in msg.response_metadata:
                    usage = msg.response_metadata["token_usage"]
                    total_cost += calculate_cost(
                        "gpt-4o-mini",
                        usage.get("prompt_tokens", 0),
                        usage.get("completion_tokens", 0),
                    )

            # Score cost
            score_cost(trace_id, total_cost)

            # Sampling (5%) for RAGAS and Judge
            if random.random() < 0.05:
                contexts = [c["text"] for c in final_state.get("retrieved_chunks", [])]
                context_str = "\n".join(contexts)

                background_tasks.add_task(
                    run_ragas_eval_async, current_query, answer, contexts, trace_id
                )
                background_tasks.add_task(
                    llm_judge_evaluate_async, current_query, answer, context_str, trace_id
                )

        return {
            "answer": answer,
            "iterations": final_state["iteration_count"],
            "sources": len(final_state["retrieved_chunks"]),
            "guardrails": {"passed": True, "pii_detected": list(set(pii_types))},
        }
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
