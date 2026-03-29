# M4 — Basic RAG + Query API

> **Release goal:** A working end-to-end Q&A system. `POST /api/query` takes a question, retrieves context, generates a cited answer, and streams it token-by-token via SSE. Tier 2 (single-step RAG) only — no agents yet.

## Deliverables

### 1. Context Assembler (`generation/context_assembler.py`)
- [ ] `assemble_context(chunks, max_tokens=8000)`
- [ ] Orders chunks by rerank score (most relevant first)
- [ ] Adds `[Source N: <header>]` citation markers before each chunk
- [ ] Respects hard token budget — stops adding chunks when limit reached
- [ ] Returns formatted context string

### 2. Prompt Templates (`generation/prompt_templates.py`)
- [ ] System prompt enforcing citation-grounded answering
- [ ] User message template
- [ ] "Context insufficient" fallback prompt variant

### 3. Generator (`generation/generator.py`)
- [ ] `generate_answer(query, context, stream=True)`
- [ ] Calls `gpt-4o-mini` (or Claude Haiku) via LangChain
- [ ] Streaming mode: yields tokens via `AsyncGenerator`
- [ ] Non-streaming mode: returns full response (for eval runs)
- [ ] `@observe()` traced

### 4. Citation Linker (`generation/citation_linker.py`)
- [ ] `link_citations(answer, chunks)` — maps `[Source N]` markers in generated answer to chunk metadata
- [ ] Returns `list[Citation(source_n, chunk_id, header, text_snippet)]`

### 5. Query Endpoint — Tier 1 + 2 (`api/routes_query.py`)
- [ ] `POST /api/query` accepting `{"query": "...", "session_id": "..."}`
- [ ] Returns `StreamingResponse` with `text/event-stream`
- [ ] SSE event types: `token`, `done`
- [ ] `done` event carries `{"citations": [...], "tier": "rag"}`
- [ ] Tier 1 (direct): skips retrieval, calls LLM directly
- [ ] Tier 2 (rag): retrieval → context assembly → generation

### 6. Adaptive Query Router (Tier Classification)
- [ ] `agents/router.py` — LLM few-shot classifier (Tier 1 / Tier 2 / Tier 3)
- [ ] Tier 1: simple factoid, conversational, no retrieval needed
- [ ] Tier 2: factoid lookups requiring document knowledge
- [ ] Tier 3: complex multi-hop (placeholder — routed to Tier 2 until M5)
- [ ] `@observe()` traced

### 7. `NexusState` Schema (`agents/state.py`)
- [ ] Pydantic `NexusState` model (needed by router even before agents)
- [ ] Fields: `query`, `query_tier`, `messages`, `retrieved_chunks`, `final_answer`, `citations`

## End-to-End Flow (M4)

```
POST /query
  → route_query() → tier assignment
  ├─ Tier 1 → generate_answer() → SSE stream
  └─ Tier 2 → retrieval_pipeline()
               → assemble_context()
               → generate_answer()
               → link_citations()
               → SSE stream
```

## Tests

- [ ] `tests/integration/test_query_endpoint.py` — POST `/api/query` with a question answerable from seeded corpus, verify answer contains `[Source 1]` citation
- [ ] Manual: verify SSE stream in curl or browser `EventSource`
- [ ] Verify Langfuse trace shows query → retrieval → generation hierarchy

## Acceptance Criteria

- [ ] `POST /api/query {"query": "What is X?"}` returns streaming SSE tokens followed by `done` event
- [ ] `done` event contains at least one citation mapped to a real chunk in Qdrant
- [ ] Tier 1 queries (e.g. "What is 2+2?") skip retrieval entirely (verifiable in Langfuse)
- [ ] Response latency (time to first token) < 3 seconds on warm instance
- [ ] System works end-to-end: ingest a document → query about it → get a cited answer

## Estimated Effort: 1–2 days
