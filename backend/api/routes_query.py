import json
import asyncio
import logging
from fastapi import APIRouter, Query, Request, Depends
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator, Union, List, Dict, Any, Optional
from backend.api.security import rate_limit_dependency, get_user_id

from backend.cache.semantic_cache import get_semantic_cache
from backend.retrieval.searcher import search_knowledge_base
from backend.retrieval.generator import generate_answer_stream, generate_title
from backend.evaluation.llm_judge import llm_judge_evaluate_async
from backend.database.chat import create_conversation, save_message, get_messages, sync_user
from backend.guardrails.input_guard import run_input_guardrails
from backend.guardrails.output_guard import run_output_guardrails
from backend.observability.tracing import observe
import time

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/query")
async def query_streaming(
    request: Request, 
    q: str = Query(...),
    conversation_id: Optional[str] = Query(None),
    match_threshold: float = Query(0.2),
    rerank: bool = Query(True),
    user_id: Union[str, None] = Depends(get_user_id),
    _ = Depends(rate_limit_dependency)
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
        
        async def yield_agent_step(agent, tool, status):
            step = {'type': 'agent_step', 'agent': agent, 'tool': tool, 'status': status}
            captured_steps.append(step)
            return f"data: {json.dumps(step)}\n\n"

        print(f"DEBUG: event_generator starting for query: {q[:20]}")
        yield await yield_agent_step('Nexus', 'Initializing Connection', 'running')
        yield f"data: {json.dumps({'type': 'activity', 'node': 'router', 'status': 'Analyzing query intent...', 'status_type': 'running'})}\n\n"
        
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
                    "cost": 0.000
                }
                yield f"data: {json.dumps(metrics)}\n\n"
                yield f"data: {json.dumps({'type': 'token', 'content': f'⚠️ {guard_result.blocked_reason}'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'citations': []})}\n\n"
                return

            # Use sanitized content for the rest of the pipeline (PII Anonymized)
            effective_q = guard_result.sanitized_content
            yield await yield_agent_step('Nexus', 'Initializing Connection', 'completed')
            yield f"data: {json.dumps({'type': 'activity', 'node': 'router', 'status': 'Query intent analyzed.', 'status_type': 'completed'})}\n\n"

            
            # Handle Conversation Persistence
            if not current_conv_id:
                yield await yield_agent_step('Nexus', 'Initializing Thread', 'running')
                title = await generate_title(effective_q)
                current_conv_id = await create_conversation(title, user_id=user_id)
                logger.info(f"Created new conversation for user {user_id} with title '{title}': {current_conv_id}")
                yield await yield_agent_step('Nexus', 'Initializing Thread', 'completed')
            
            # Save user message (save the raw query for user history, but effective_q is used for LLM)
            user_msg_id = await save_message(
                conversation_id=current_conv_id,
                role="user",
                content=q,
                agent_steps=captured_steps.copy() # Capture setup steps for user turn
            )
            # 1. Check Semantic Cache first
            cached = await asyncio.to_thread(get_semantic_cache().get, effective_q)
            if cached:
                logger.info(f"Cache hit for query: {q[:50]}...")
                yield f"data: {json.dumps({'type': 'token', 'content': cached['answer']})}\n\n"
                
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
                    "tokens": len(cached['answer'].split()),
                    "cost": 0.000
                }
                yield f"data: {json.dumps(metrics)}\n\n"

                # Persist cached assistant message
                assistant_msg_id = await save_message(
                    conversation_id=current_conv_id,
                    role="assistant",
                    content=cached['answer'],
                    citations=cached['citations'],
                    metrics=metrics
                )

                yield f"data: {json.dumps({'type': 'done', 'citations': cached['citations'], 'conversation_id': current_conv_id, 'message_id': assistant_msg_id})}\n\n"
                return

            # 2. Cache Miss: Execute RAG Pipeline
            yield await yield_agent_step('Retriever', 'Scanning Knowledge Base', 'running')
            yield f"data: {json.dumps({'type': 'activity', 'node': 'retriever', 'status': 'Searching document vector space...', 'status_type': 'running'})}\n\n"

            # Fetch context chunks from Knowledge Base (Vector + BM25)
            try:
                context_chunks = await asyncio.to_thread(
                    search_knowledge_base, 
                    effective_q, 
                    match_threshold=match_threshold, 
                    rerank=rerank
                )
            except Exception as e:
                logger.error(f"Retriever search failed: {e}")
                context_chunks = []

            # Fetch history for multi-turn support
            history = []
            if current_conv_id:
                history = await get_messages(current_conv_id)

            
            tier = "rag"
            if not context_chunks:
                yield await yield_agent_step('Retriever', 'No specific documents found. Using General Knowledge.', 'warning')
                tier = "general"

            yield await yield_agent_step('LLM', 'Synthesizing Answer', 'running')
            yield f"data: {json.dumps({'type': 'activity', 'node': 'analyst', 'status': 'Synthesizing grounded response...', 'status_type': 'running'})}\n\n"
            
            yield await yield_agent_step('Retriever', 'Scanning Knowledge Base', 'completed')
            yield f"data: {json.dumps({'type': 'activity', 'node': 'retriever', 'status': 'Search completed.', 'status_type': 'completed'})}\n\n"
            
            # Step 2: Stream Answer Generation
            full_answer = ""
            async for token in generate_answer_stream(effective_q, context_chunks, history=history):
                # Check for client disconnect
                if await request.is_disconnected():
                    logger.info("Client disconnected during stream")
                    break
                    
                full_answer += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                # Small sleep to prevent network buffer issues and allow smooth frontend rendering
                await asyncio.sleep(0.01)

            yield await yield_agent_step('LLM', 'Synthesizing Answer', 'completed')
            yield f"data: {json.dumps({'type': 'activity', 'node': 'analyst', 'status': 'Response synthesized.', 'status_type': 'completed'})}\n\n"

            # Step 3: Format Citations for 'done' event
            citations = []
            doc_ids = []
            for i, chunk in enumerate(context_chunks):
                citations.append({
                    "id": i + 1,
                    "document_id": chunk["document_id"],
                    "title": chunk.get("title", "Unknown"),
                    "text": chunk["text"],
                    "header": chunk.get("header"),
                    "metadata": chunk.get("metadata", {})
                })
                doc_ids.append(chunk["document_id"])

            # Step 4: Post-Stream Evaluation & Metrics (Parallel)
            yield await yield_agent_step('Validator', 'Final Quality Check', 'running')
            
            # Combine context into a single string for the judge
            full_context = "\n---\n".join([c["text"] for c in citations])
            trace_id = getattr(request.state, "trace_id", "local_debug")

            # Fire off Judge and Output Guardrail concurrently
            judge_task = asyncio.create_task(llm_judge_evaluate_async(
                question=effective_q,
                answer=full_answer,
                context=full_context,
                trace_id=trace_id
            ))
            
            output_guard_task = asyncio.to_thread(run_output_guardrails, full_answer)

            # Wait for both with a reasonable timeout to prevent UI "hang"
            # If evaluation takes too long, we'll continue with partial data
            try:
                # Give it up to 3 seconds for GPT-4o-mini to respond
                judge_results, output_guard = await asyncio.gather(
                    asyncio.wait_for(judge_task, timeout=4.0),
                    asyncio.wait_for(output_guard_task, timeout=2.0)
                )
            except asyncio.TimeoutError:
                logger.warning("Post-stream evaluation timed out, continuing with partial results")
                judge_results = {}
                output_guard = None # Will fall back to raw answer
            except Exception as e:
                logger.error(f"Post-stream evaluation failed: {e}")
                judge_results = {}
                output_guard = None

            # Calculate final metrics
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # 5. Extract results with normalization (Judge gives 1-5, Frontend expects 0.0-1.0)
            # Frontend does (1 - hallucinationScore) * 100 for Faithfulness.
            # So if Faithfulness is 5/5 (best), we want hallucinationScore to be 0.0.
            # If Faithfulness is 1/5 (worst), we want hallucinationScore to be 1.0.
            
            raw_faithfulness = judge_results.get("faithfulness", 5)
            # Normalize 1-5 to 1.0-0.0 for "hallucination score" (inverted)
            hallucination_score = max(0.0, min(1.0, (5 - raw_faithfulness) / 4.0))
            
            raw_relevance = judge_results.get("relevance", 5)
            # Normalize 1-5 to 0.0-1.0 for relevance
            relevance_score = max(0.0, min(1.0, (raw_relevance - 1) / 4.0))

            # 6. Final Guardrail State
            guardrail_display_status = "passed"
            if not guard_result.passed:
                guardrail_display_status = "failed"
            elif getattr(output_guard, "passed", True) is False:
                logger.warning(f"Output blocked by guardrails: {output_guard.blocked_reason}")
                full_answer = output_guard.sanitized_content
                guardrail_display_status = "failed"
            else: # Passed, timeout, or skip
                guardrail_display_status = "passed"

            metrics = {
                "type": "metrics",
                "latency": latency_ms,
                "cache_hit": False,
                "hallucinationScore": hallucination_score if tier != "general" else None,
                "relevanceScore": relevance_score if tier != "general" else None,
                "guardrailStatus": guardrail_display_status, 
                "tier": tier,
                "tokens": len(full_answer.split()) + len(full_context.split()), 
                "cost": 0.000 
            }
            
            yield f"data: {json.dumps(metrics)}\n\n"
            yield await yield_agent_step('Validator', 'Final Quality Check', 'completed')

            # Step 5: Final 'done' event with metadata
            # WE SEND THIS LAST so the frontend doesn't close too early
            # Now including IDs for persistence and feedback
            
            # Step 6: Post-stream: save assistant message and metrics
            # We do this before 'done' so we can send the message_id back
            assistant_msg_id = await save_message(
                conversation_id=current_conv_id,
                role="assistant",
                content=full_answer,
                citations=citations,
                metrics=metrics,
                trace_id=trace_id,
                agent_steps=captured_steps # Capture all steps for assistant turn
            )

            done_payload = {
                'type': 'done', 
                'citations': citations,
                'conversation_id': current_conv_id,
                'message_id': assistant_msg_id
            }
            yield f"data: {json.dumps(done_payload)}\n\n"

            # Step 7: Post-stream: store in cache (Only if RAG successful and passed guardrails)
            if full_answer and tier == "rag" and getattr(output_guard, 'passed', True):
                await asyncio.to_thread(
                    get_semantic_cache().set, 
                    effective_q, 
                    full_answer, 
                    citations, 
                    list(set(doc_ids)),
                    metrics
                )

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
                "cost": 0.000
            }
            yield f"data: {json.dumps(metrics)}\n\n"
            yield await yield_agent_step('Validator', 'Final Quality Check', 'error')
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Critical for Nginx/proxies to not buffer the stream
        }
    )
