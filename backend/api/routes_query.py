import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import StreamingResponse

from backend.agents.graph import nexus_graph
from backend.agents.state import NexusState
from backend.api.security import get_user_id, rate_limit_dependency
from backend.cache.semantic_cache import get_semantic_cache
from backend.database.chat import create_conversation, get_messages, save_message, sync_user
from backend.evaluation.eval_manager import EvaluationManager
from backend.guardrails.input_guard import run_input_guardrails
from backend.retrieval.generator import generate_title

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/query")
async def query_streaming(
    request: Request,
    q: str = Query(...),
    conversation_id: str | None = Query(None),
    match_threshold: float = Query(0.2),
    rerank: bool = Query(True),
    max_iterations: int = Query(3),
    background_tasks: BackgroundTasks = None,
    user_id: str | None = Depends(get_user_id),
    _=Depends(rate_limit_dependency),
):
    """
    Main entry point for streaming queries.
    Uses SSE (Server-Sent Events) to stream tokens back to the client.
    Integrates semantic caching.
    """

    start_time = time.perf_counter()
    # Shadow Auth: Sync user registration
    access_tier = request.headers.get("X-Nexus-Access-Tier") or "visitor"
    if user_id:
        await sync_user(user_id, access_tier)

    current_conv_id = conversation_id

    async def event_generator() -> AsyncGenerator[str, None]:
        nonlocal current_conv_id
        captured_steps = []
        last_heartbeat = time.perf_counter()

        async def yield_agent_step(agent, tool, status, rationale=None):
            step = {
                "type": "agent_step",
                "agent": agent,
                "tool": tool,
                "status": status,
                "rationale": rationale,
            }
            captured_steps.append(step)
            return f"data: {json.dumps(step)}\n\n"

        async def heartbeat():
            """Yields an SSE comment to keep the connection alive."""
            nonlocal last_heartbeat
            now = time.perf_counter()
            if (
                now - last_heartbeat > 5
            ):  # Every 5 seconds of silence (Reduced from 15s for stability)
                last_heartbeat = now
                return ": heartbeat\n\n"
            return None

        # 0. Warming comment to flush proxy buffers immediately
        yield ": warming connection\n\n"
        yield await yield_agent_step("Nexus", "Initializing Connection", "running")
        yield f"data: {json.dumps({'type': 'activity', 'node': 'router', 'status': 'Analyzing query intent...', 'status_type': 'running'})}\n\n"
        last_heartbeat = time.perf_counter()

        try:
            # 1. Immediate feedback to prevent "hang" perception
            # yield f"data: {json.dumps({'type': 'agent_step', 'agent': 'Nexus', 'tool': 'Validating Input', 'status': 'running'})}\n\n"

            # 0. Input Guardrails Gate (Run in a thread to keep loop free)
            guard_result = await asyncio.to_thread(run_input_guardrails, q)

            if not guard_result.passed:
                logger.warning(f"Query blocked by input guardrails: {guard_result.blocked_reason}")
                latency_ms = (time.perf_counter() - start_time) * 1000
                metrics = {
                    "type": "metrics",
                    "latency": latency_ms,
                    "hallucinationScore": None,
                    "guardrailStatus": "failed",
                    "tier": "direct",
                    "tokens": 0,
                    "cost": 0.000,
                }
                yield f"data: {json.dumps(metrics)}\n\n"
                yield f"data: {json.dumps({'type': 'token', 'content': f'⚠️ {guard_result.blocked_reason}'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'citations': []})}\n\n"
                return

            # 1. Yield bootstrap metrics to wake up the UI metrics panel
            latency_ms = (time.perf_counter() - start_time) * 1000
            yield f"data: {json.dumps({'type': 'metrics', 'latency': latency_ms, 'tokens': 0, 'cost': 0, 'tier': 'initializing', 'cache_hit': False, 'hallucinationScore': 0.0, 'relevanceScore': 0.0, 'guardrailStatus': 'passed'})}\n\n"

            logger.info(f"Query Processed for User: {user_id}")

            # Use sanitized content for the rest of the pipeline (PII Anonymized)
            effective_q = guard_result.sanitized_content
            yield await yield_agent_step(
                "Nexus", "Initializing Connection", "completed", "Establishing SSE channel."
            )
            yield f"data: {json.dumps({'type': 'activity', 'node': 'router', 'status': 'Query intent analyzed.', 'status_type': 'completed'})}\n\n"

            # Handle Conversation Persistence
            if not current_conv_id:
                yield await yield_agent_step(
                    "Nexus", "Initializing Thread", "running", "Creating new conversation record."
                )
                title = await generate_title(effective_q)
                current_conv_id = await create_conversation(title, user_id=user_id)
                logger.info(
                    f"Created new conversation for user {user_id} with title '{title}': {current_conv_id}"
                )
                yield await yield_agent_step(
                    "Nexus", "Initializing Thread", "completed", "Thread ready."
                )

            # Save user message (save the raw query for user history, but effective_q is used for LLM)
            await save_message(
                conversation_id=current_conv_id,
                role="user",
                content=q,
                agent_steps=captured_steps.copy(),  # Capture setup steps for user turn
            )
            # 1. Check Semantic Cache first
            cached = await asyncio.to_thread(get_semantic_cache().get, effective_q)
            if cached:
                logger.info(f"Cache hit for query: {q[:50]}...")
                yield f"data: {json.dumps({'type': 'tokens', 'content': cached['answer']})}\n\n"

                # Yield cache hit metrics
                latency_ms = (time.perf_counter() - start_time) * 1000
                cached_metrics = cached.get("metrics", {})

                metrics = {
                    "type": "metrics",
                    "latency": latency_ms,
                    "cache_hit": True,
                    "hallucinationScore": cached_metrics.get("hallucinationScore", 0),
                    "relevanceScore": cached_metrics.get("relevanceScore", 1.0),
                    "guardrailStatus": "passed",
                    "tier": "direct",
                    "tokens": len(cached["answer"].split()),
                    "cost": 0.000,
                }
                yield f"data: {json.dumps(metrics)}\n\n"

                # Persist cached assistant message
                assistant_msg_id = await save_message(
                    conversation_id=current_conv_id,
                    role="assistant",
                    content=cached["answer"],
                    citations=cached["citations"],
                    metrics=metrics,
                )

                yield f"data: {json.dumps({'type': 'done', 'citations': cached['citations'], 'conversation_id': current_conv_id, 'message_id': assistant_msg_id})}\n\n"
                return

            # 2. Cache Miss: Execute Agentic LangGraph Flow
            initial_state: NexusState = {
                "messages": [],
                "query": effective_q,
                "current_agent": "supervisor",
                "retrieved_chunks": [],
                "iteration_count": 0,
                "max_iterations": max_iterations,
                "search_count": 0,
                "is_greeting": False,
                "validation_status": "pending",
                "hallucination_score": 0.0,
                "final_answer": "",
                "pii_detected": [],
                "activity_log": [],
                "user_id": user_id,
                "match_threshold": match_threshold,
                "rerank": rerank,
            }

            # Fetch history for multi-turn support and inject into state
            if current_conv_id:
                history_messages = await get_messages(current_conv_id)
                initial_state["messages"] = history_messages

            full_answer = ""
            citations = []

            # Execute graph and stream steps
            try:
                async for step in nexus_graph.astream(initial_state):
                    if await request.is_disconnected():
                        logger.info("Client disconnected during agentic flow")
                        break

                    # 'step' is a dict of {node_name: state_updates}
                    node_name = next(iter(step.keys()))
                    updates = step[node_name]

                    # Yield agent step for UI tracking
                    agent_name = node_name.capitalize()
                    status_desc = "Working..."
                    if updates.get("activity_log"):
                        status_desc = updates["activity_log"][-1].get("status", "Working...")

                    # Extract rationale if available
                    rationale = (
                        updates["activity_log"][-1].get("rationale")
                        if updates.get("activity_log")
                        else None
                    )
                    yield await yield_agent_step(agent_name, node_name, "completed", rationale)
                    yield f"data: {json.dumps({'type': 'activity', 'node': node_name, 'status': status_desc, 'status_type': 'completed', 'rationale': rationale})}\n\n"

                    # Capture tokens if analyst node yields final_answer
                    if updates.get("final_answer") and not full_answer:
                        full_answer = updates["final_answer"]
                        # Simulate token-by-token streaming for the frontend "typing" effect
                        tokens = full_answer.split(" ")
                        for i, token in enumerate(tokens):
                            # Append space to every token except the last to avoid trailing space issues
                            content = token + (" " if i < len(tokens) - 1 else "")
                            yield f"data: {json.dumps({'type': 'tokens', 'content': content})}\n\n"
                            await asyncio.sleep(0.01)

                    # Capture citations from the state if present in the final update or analyst update
                    if "retrieved_chunks" in updates:
                        # Clear and update to avoid duplicates if nodes return same chunks
                        new_citations = []
                        for i, chunk in enumerate(updates["retrieved_chunks"]):
                            new_citations.append(
                                {
                                    "id": i + 1,
                                    "document_id": chunk.get("metadata", {}).get(
                                        "document_id", f"doc_{i}"
                                    ),
                                    "title": chunk.get("metadata", {}).get("title", "Unknown"),
                                    "text": chunk.get("text", ""),
                                    "metadata": chunk.get("metadata", {}),
                                }
                            )
                        citations = new_citations
                        # Early yield of citations to the UI
                        yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"

                    last_heartbeat = time.perf_counter()
                    yield await heartbeat() or ""

            except Exception as e:
                # Catch recursion limits or graph issues
                if "recursion limit" in str(e).lower():
                    logger.error("LangGraph recursion limit reached")
                    full_answer = "I've searched extensively but couldn't find a definitive answer in your documents. Please try a more specific question."
                    yield f"data: {json.dumps({'type': 'tokens', 'content': f'\n\n{full_answer}'})}\n\n"
                else:
                    raise e

            # Final metrics calculation
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Bootstrap relevance: 1.0 if we have chunks, 0.0 if we don't (unless it's a greeting)
            bootstrap_relevance = (
                1.0 if citations else (1.0 if initial_state.get("is_greeting") else 0.0)
            )

            metrics = {
                "type": "metrics",
                "latency": latency_ms,
                "cache_hit": False,
                "hallucinationScore": initial_state.get("hallucination_score", 0.0),
                "relevanceScore": bootstrap_relevance,
                "guardrailStatus": "passed",
                "tier": "agentic",
                "tokens": len(full_answer.split()),
                "cost": 0.000,
            }
            yield f"data: {json.dumps(metrics)}\n\n"

            # Save assistant message
            assistant_msg_id = await save_message(
                conversation_id=current_conv_id,
                role="assistant",
                content=full_answer,
                citations=citations,
                metrics=metrics,
                agent_steps=captured_steps,
            )

            # Fire-and-forget deep evaluation in the background
            if background_tasks and assistant_msg_id:
                # Get context strings
                context_texts = [c.get("text", "") for c in citations]

                background_tasks.add_task(
                    EvaluationManager.run_async_eval,
                    message_id=assistant_msg_id,
                    question=effective_q,
                    answer=full_answer,
                    contexts=context_texts,
                    trace_id=initial_state.get("trace_id") or "live_stream",
                )

            yield f"data: {json.dumps({'type': 'done', 'citations': citations, 'conversation_id': current_conv_id, 'message_id': assistant_msg_id})}\n\n"

        except Exception as e:
            logger.error(f"Error in streaming query: {e}")

            # Emit error metrics to clear loading state
            latency_ms = (time.perf_counter() - start_time) * 1000
            metrics = {
                "type": "metrics",
                "latency": latency_ms,
                "hallucinationScore": None,
                "relevanceScore": None,
                "guardrailStatus": "failed",
                "tier": "rag",
                "tokens": 0,
                "cost": 0.000,
            }
            yield f"data: {json.dumps(metrics)}\n\n"
            yield await yield_agent_step("Validator", "Final Quality Check", "error")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Critical for Nginx/proxies to not buffer the stream
        },
    )
