# Project NEXUS — Complete Technical Summary

> **Purpose of this document**: Provide a model without source code access the full picture of what this project demonstrates, including architecture, actual code patterns, design decisions, and production deployment details.

---

## 1. What is NEXUS?

NEXUS is a **production-deployed, multi-agent research intelligence platform** built by Vibhor Kashmira. It is a full-stack Applied AI system that:

1. **Ingests** heterogeneous documents (PDF, DOCX, HTML, JSON) through a 6-stage enrichment pipeline
2. **Builds** a semantically-rich knowledge base with hybrid dense+sparse indexes
3. **Answers** complex questions through coordinated specialist agents (Supervisor → Researcher → Analyst → Validator)
4. **Validates** every answer through LLM-based Self-RAG hallucination detection
5. **Monitors** every operation through full-stack observability with Langfuse tracing
6. **Caches** semantically similar queries via Upstash Redis for cost efficiency
7. **Guards** input/output through prompt injection detection, PII anonymization, profanity filtering, and hallucination gating

**Live deployment**: `https://project-nexus.duckdns.org` running on AWS EC2 (`t3.small`, ~$16–24/month total).

---

## 2. Technology Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.12, FastAPI, Uvicorn, Pydantic v2, pydantic-settings |
| **AI/ML** | LangChain 0.3, LangGraph 0.3, OpenAI gpt-4o-mini, Cohere rerank-english-v3.0, sentence-transformers (all-MiniLM-L6-v2 via OpenAI Embeddings API), tiktoken, spaCy |
| **Vector DB** | Qdrant Cloud (primary dense search), Supabase pgvector (fallback hybrid search) |
| **Relational DB** | Supabase PostgreSQL (chunks, documents, conversations, messages, ingestion_tasks, evaluations) |
| **Cache** | Upstash Redis (semantic similarity cache with cosine-distance matching) |
| **Guardrails** | Custom regex PII detection (EMAIL, PHONE, SSN, CREDIT_CARD, IP), BetterProfanity, regex prompt injection patterns |
| **Observability** | Langfuse (traces, spans, cost tracking via `@observe()` decorators) |
| **Evaluation** | RAGAS (faithfulness, answer_relevancy, context_precision), LLM-as-Judge (gpt-4o-mini scoring 1-5 on correctness/completeness/citations/conciseness) |
| **Frontend** | Next.js 15 (App Router), TypeScript, Tailwind CSS, Shadcn/ui, SSE streaming |
| **Infrastructure** | AWS EC2 + ECR + EIP, Terraform (IaC), Docker + Docker Compose, Caddy (reverse proxy + auto TLS) |
| **CI/CD** | GitHub Actions (lint → build → push ECR → deploy via SSM) |

---

## 3. Architecture — 5-Layer Design

### Layer 1: Document Ingestion & Enrichment Pipeline (6 stages)

The pipeline is broken into discrete, retryable stages. Each stage is traced via Langfuse `@observe()`.

**Stage 1 — Parse** (`backend/ingestion/parser.py`, 4.3 KB):
- Uses `unstructured.io` to parse PDF (hi_res strategy), DOCX, HTML, and plain text
- Extracts tables, text, and metadata from multi-format documents
- Returns `ParsedDocument(text, metadata)`

**Stage 2 — Clean** (`backend/ingestion/cleaner.py`, 1.8 KB):
- Unicode normalization (NFKC), whitespace collapse
- SimHash fingerprinting for near-duplicate detection
- Checks Supabase `documents.fingerprint` to skip near-duplicates
- Returns `CleanedDocument(text, fingerprint, is_duplicate, metadata)`

**Stage 3 — Semantic Chunk** (`backend/ingestion/chunker.py`, 8 KB):
This is the most technically sophisticated module. It implements **cosine-breakpoint semantic chunking**:

```
Algorithm:
1. Sentence segmentation via spaCy blank("en") + sentencizer (fast, no model download needed)
2. Batch-embed all sentences using OpenAI embeddings API
3. Compute cosine distances between consecutive sentence embeddings
4. Identify breakpoints where distance exceeds the 95th percentile threshold
5. Merge sentences between breakpoints into chunks
6. Enforce min_tokens=50, max_tokens=512 with hard-splits for oversized sentences
7. For massive docs (>1M chars): segments the document into manageable blocks first
```

Key production details:
- Uses `tiktoken` (`cl100k_base`) for accurate token counting
- Single sentences >4000 chars get hard-split immediately
- Oversized semantic chunks get sentence-level sub-splitting to stay under 512 tokens
- Progress callbacks for real-time UI updates during ingestion

**Stage 4 — Enrich** (`backend/ingestion/enricher.py`, 3 KB):
- Named entity extraction (spaCy NER)
- Topic classification (zero-shot)
- Key phrase extraction (YAKE)
- Returns `EnrichedChunk` with `entities`, `topics`, `key_phrases`

**Stage 5 — Embed** (`backend/ingestion/embedder.py`, 5.4 KB):
- Dense embeddings via OpenAI `text-embedding-3-small` (1536 dimensions, quantized to 384 in Qdrant)
- Sparse tokenization for BM25 (token frequency dictionaries)
- Batch encoding for efficiency

**Stage 6 — Upsert** (`backend/ingestion/upserter.py`, 4.6 KB):
- Dual-write: Qdrant Cloud (dense vectors + metadata payload) AND Supabase (full text, metadata, sparse tokens, embeddings)
- Cache invalidation on re-ingestion
- Document lineage tracking via `document_id` foreign keys

**Background Worker Architecture** (`backend/ingestion/worker.py`, 12.4 KB):
The ingestion pipeline runs asynchronously via a dedicated background thread with a `ProcessPoolExecutor`:
- Polls `ingestion_chunks` table for pending work (via Supabase RPC `claim_ingestion_chunks` — atomic claim)
- Processes chunks in batches of 10
- Uses a separate process (via `spawn` context) for NLP-heavy work to avoid event loop conflicts
- 120-second timeout per batch, with automatic pool recreation on crash
- Progress tracking persisted to Supabase `ingestion_tasks` table for real-time UI updates
- A separate **Reaper thread** (`backend/ingestion/reaper.py`) cleans up stale/stuck tasks

---

### Layer 2: Hybrid Retrieval Pipeline

**Hybrid Search** (`backend/retrieval/searcher.py`, 7.8 KB):

```
Flow:
1. Embed query → dense vector
2. Dense search: Qdrant Cloud (query_points or search, with user_id/is_personal filter)
3. If Qdrant yields nothing → Fallback: Supabase RPC `match_hybrid_chunks`
   (combines pgvector cosine + PostgreSQL full-text ts_rank_cd + title boosting)
4. Semantic Keyword Boost ("mymailkeeper fix"):
   - For rare tokens (>4 chars) found as exact substrings in candidate text,
     score is elevated to 0.95 to prevent burial by semantic-only ranking
5. Optional Cross-Encoder Reranking via Cohere API
6. Shield boosted scores: final match_score = max(rerank_score, similarity_score)
```

**Cross-Encoder Reranking** (`backend/retrieval/reranker.py`, 3.1 KB):
- Uses **Cohere rerank-english-v3.0** API (NOT a local model — cost-optimized at ~$1/1000 calls)
- Graceful fallback: if no Cohere API key, returns top-k by original vector score
- Includes title in the reranking document for richer signal
- Handles rate limits with automatic fallback

**Self-RAG Validation** (`backend/retrieval/self_rag.py`, 3.2 KB):
- Uses **gpt-4o-mini** as a fact-checking validator (NOT a local NLI model — cost-optimized)
- Prompt asks the LLM to identify all claims in the answer and check each against retrieved context
- Returns structured JSON: `{passed, hallucination_score, unsupported_claims, reasoning}`
- Uses `response_format={"type": "json_object"}` for reliable structured output
- Defaults to FAILURE if the validation itself errors (fail-safe design)

**Supabase Hybrid Search Function** (`sql/schema.sql`):
```sql
match_hybrid_chunks(query_embedding, query_text, match_threshold, match_count):
  Returns (id, document_id, title, text, header, metadata, similarity)
  Similarity = (dense_cosine * vector_weight) + (ts_rank_cd * full_text_weight) + (title_boost)
  Title boost: exact match = 2x boost, substring match = 1x boost
```

---

### Layer 3: Agent Orchestration (LangGraph)

**State Schema** (`backend/agents/state.py`):
```python
class NexusState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]  # Conversation history
    current_agent: str                                      # Routing target
    retrieved_chunks: list[dict[str, Any]]                  # Vector search results
    iteration_count: int                                    # Loop counter
    max_iterations: int                                     # Safety limit (default 3)
    validation_status: str                                  # "approved" | "rejected" | "pending"
    hallucination_score: float                              # 0.0 (faithful) to 1.0 (hallucinated)
    final_answer: str                                       # Analyst's synthesized response
    pii_detected: list[str]                                 # PII types found
    query: str                                              # User's question
    activity_log: Annotated[list[dict], operator.add]       # UI visualization feed
    user_id: str | None                                     # For scoped retrieval
    match_threshold: float                                  # Tunable retrieval threshold
    rerank: bool                                            # Toggle Cohere reranking
    search_count: int                                       # Prevents infinite search loops
    is_greeting: bool                                       # Short-circuits greetings
```

**Graph Topology** (`backend/agents/graph.py`):
```
Entry Point: supervisor
Edges:
  supervisor → {researcher, analyst, validator, END}  (conditional)
  researcher → supervisor                              (always)
  analyst → validator                                   (direct hand-off)
  validator → {supervisor, END}                         (conditional: rejected → supervisor, approved → END)
```

This creates a **reflection loop**: Validator rejects → Supervisor routes to Analyst → Analyst revises → Validator re-checks → up to 3 iterations.

**Supervisor Node** (`backend/agents/nodes.py`):
- Catches simple greetings early ({"hi", "hello", "hey", "howdy", "howdie"}) to avoid unnecessary search
- Hard stop at max_iterations OR search_count ≥ 2 to prevent infinite loops
- Uses gpt-4o-mini with a system prompt that describes available agents
- Provides context summary (query, chunk count, final answer status, iteration, search count, last validation) to help LLM decide routing
- Returns `current_agent` for graph routing + `activity_log` for UI

**Researcher Node**:
- Binds LLM to `NEXUS_TOOLS` (vector_search tool)
- Injects user_id and Tune Engine settings (match_threshold, rerank) from state into tool calls
- **Diagnostic escalation**: If search returns empty, checks:
  1. Does this user have ANY documents? → "Found your library but no high-relevance matches"
  2. Does a doc with similar name exist under a DIFFERENT user_id? → "Security Alert: Session mismatch detected"
- Reports retrieval techniques used (Hybrid-Boosted, Cohere Reranking) in activity log

**Analyst Node**:
- Uses **structured output** (`llm.with_structured_output(AnalystResponse)`) to get both `reasoning` (internal) and `answer` (user-facing)
- Sorts retrieved chunks by score; includes source path and relevance score in context
- Strict grounding prompt: "You MUST ONLY use the provided Context. Do NOT use outside knowledge."
- Helpfulness rule for partial matches (e.g., entity found as email domain → report what's known)
- If validation was previously rejected, includes rejection feedback in prompt for revision
- Fallback to standard invoke if structured output fails

**Validator Node**:
- Delegates to `check_hallucination()` (Self-RAG) which uses gpt-4o-mini to check claim-by-claim faithfulness
- If hallucination_score > threshold → rejects and routes back to supervisor with unsupported claims listed
- Returns `activity_log` with faithfulness percentage for the UI

---

### Layer 4: Generation + Guardrails

**Input Guardrails** (`backend/guardrails/input_guard.py`, 3.8 KB):
Runs BEFORE any retrieval or LLM call. Three checks:

1. **Profanity** — BetterProfanity library with a technical whitelist (dummy, mock, stub, lorem, ipsum, test, demo)
2. **Prompt Injection** — 7 regex patterns: "ignore previous instructions", "system override", "new instructions:", "you are now a", "forget everything you know", "reveal your system prompt", "disregard constraints"
3. **PII Detection & Redaction** — Custom regex (NOT Presidio, to avoid ~500MB RAM overhead):
   - EMAIL_ADDRESS → `<EMAIL>`
   - PHONE_NUMBER → `<PHONE>`
   - US_SSN → `<SSN>`
   - CREDIT_CARD → `<CREDIT_CARD>`
   - IP_ADDRESS → `<IP>`

**Output Guardrails** (`backend/guardrails/output_guard.py`, 4.8 KB):
Runs AFTER LLM generation, BEFORE returning to user. Three checks:

1. **Profanity/Toxicity** — Same BetterProfanity with expanded whitelist (answer, sources, citations, references, context, synthetic, testing, development)
2. **Self-RAG Hallucination Detection** — Calls `check_hallucination(answer, context_chunks)`. Blocks if hallucination_score > 0.5
3. **PII Leak Detection** — Same regex PII filter on the output. Blocks if high-severity PII found (CREDIT_CARD, US_SSN, PASSWORD, CRYPTO, IBAN_CODE)

**GuardResult Schema**:
```python
class GuardResult(BaseModel):
    passed: bool
    sanitized_content: str
    blocked_reason: str | None = None
    pii_detected: list[str] = []
    warnings: list[str] = []
    metadata: dict = {}
```

---

### Layer 5: Observability & Evaluation

**Langfuse Tracing** (`backend/observability/tracing.py`):
- Every significant function is decorated with `@observe()` from the Langfuse SDK
- Automatically creates hierarchical trace trees: spans for each function call, recording input/output, token usage, and cost
- Initialized at app startup via `init_tracing()`

**Evaluation Manager** (`backend/evaluation/eval_manager.py`, 7.9 KB):
Orchestrates dual evaluation strategies as a FastAPI BackgroundTask:

1. **LLM-as-Judge** (100% of queries): gpt-4o-mini scores 1-5 on faithfulness, relevance, correctness, conciseness. Results are scaled to 0.0-1.0 for the UI (e.g., faithfulness 5/5 → hallucinationScore 0.0).
2. **RAGAS** (10% sampling): context_precision, answer_relevancy, faithfulness via the RAGAS library. Only sampled queries hit this expensive path.

**Alerting**: Threshold violations (e.g., judge_faithfulness < 0.7) trigger `save_evaluation_alert()` entries in the database.

**Regression Runner** (`backend/evaluation/regression_runner.py`, 5.4 KB):
- Runs against a golden dataset in CI/CD
- Fails the build if any RAGAS metric drops below threshold (faithfulness: 0.80, relevancy: 0.75, context_precision: 0.70, context_recall: 0.70)

---

## 4. API Layer (FastAPI)

**Main App** (`backend/main.py`):
- FastAPI with `lifespan` context manager for startup/shutdown
- Startup: validates config, starts background ingestion worker thread + reaper thread, initializes Langfuse tracing
- Shutdown: shuts down NLP ProcessPoolExecutor
- CORS configured for production domain (`project-nexus.duckdns.org`) + localhost + legacy Render support

**10 API Route Groups**:
| Route | Prefix | Description |
|---|---|---|
| Health | `/api/health` | Healthcheck |
| Ingestion | `/api/ingest` | Document upload + async processing |
| Search | `/api/search` | Direct vector search |
| Agents | `/api/agents` | Agent graph invocation |
| Streaming | `/api/streaming` | Main SSE query endpoint |
| Documents | `/api/documents` | Document library management |
| History | `/api/history` | Conversation history |
| Tasks | `/api/tasks` | Ingestion task status |
| Skills | `/api/skills` | Skill registry management |
| Evaluation | `/api/evaluation` | Manual eval triggers, golden dataset management |

**Main Query Endpoint** (`GET /api/streaming/query`):
Full SSE streaming flow:
```
1. Warm SSE connection (flush proxy buffers)
2. Run input guardrails (profanity → injection → PII) in thread
3. Check semantic cache (cosine similarity ≥ 0.85 = cache hit)
4. If cache miss → Execute LangGraph agentic flow:
   - Stream agent_step events for each node (supervisor, researcher, analyst, validator)
   - Stream activity events with status + rationale for UI sidebar
   - Stream token events (simulated word-by-word streaming from analyst's final_answer)
   - Stream citation events as chunks are retrieved
5. Compute final metrics (latency, hallucination score, relevance, tier, tokens)
6. Persist assistant message to Supabase conversations/messages
7. Fire-and-forget background evaluation (LLM-Judge 100%, RAGAS 10%)
8. Store in semantic cache for future queries
9. Send "done" event with citations and conversation_id
```

**SSE Event Types**:
- `agent_step` — Agent/tool activity with rationale
- `activity` — Node status update for UI sidebar
- `tokens` — Incremental text content
- `citations` — Retrieved source chunks
- `metrics` — Latency, hallucination score, relevance, guardrail status, tier, token count, cost
- `done` — Final event with citations + conversation_id + message_id
- `error` — Error details

**Security**: Shadow auth via `X-Nexus-Access-Tier` header, user_id from session, rate limiting (20 req/min).

---

## 5. Semantic Caching

**Implementation** (`backend/cache/semantic_cache.py`, 7.8 KB):
- Uses Upstash Redis (serverless Redis)
- Stores query embedding alongside cached answer
- On lookup: embeds new query, scans all `cache:query:*` keys, computes cosine similarity
- Cache hit threshold: **0.85** (handles paraphrased queries with same intent)
- TTL: 24 hours (86400 seconds)
- Invalidation: on document re-ingestion, scans for cache entries referencing affected `doc_ids` and deletes them
- Kill switch: `CACHE_ENABLED=false` env var disables Redis entirely
- Connection test on initialization with a 10-second TTL probe key

---

## 6. Frontend (Next.js 15)

**13 Components** in `frontend/src/components/`:
| Component | Size | Purpose |
|---|---|---|
| `ChatInterface.tsx` | 25 KB | Main chat UI with SSE streaming, agent steps, citations |
| `MessageBubble.tsx` | 25 KB | Rich message rendering with markdown, citations, metrics |
| `DocumentLibrary.tsx` | 20 KB | Document management and upload interface |
| `NotificationDrawer.tsx` | 10 KB | Notification system |
| `UploadPanel.tsx` | 10 KB | Drag-and-drop document upload with progress tracking |
| `KnowledgeHub.tsx` | 9.3 KB | Knowledge base exploration |
| `SkillHub.tsx` | 9 KB | Skill/agent management interface |
| `ChatDashboard.tsx` | 8.8 KB | Dashboard/analytics view |
| `Sidebar.tsx` | 7.5 KB | Navigation sidebar |
| `SidebarHistory.tsx` | 6.3 KB | Conversation history sidebar |
| `MetricsPanel.tsx` | 6.2 KB | Real-time quality metrics display |
| `AgentActivity.tsx` | 3.9 KB | Real-time agent step visualization |
| `CitationCard.tsx` | 2.9 KB | Expandable source reference cards |

**Tech**: Next.js 15, App Router, Tailwind CSS, Shadcn/ui, EventSource for SSE.

---

## 7. Database Schema (Supabase PostgreSQL)

```sql
-- Core tables
documents (id, title, source_path, doc_type, fingerprint, chunk_count, user_id, is_personal, description, filename, created_at, updated_at)
chunks (id, document_id, text, header, token_count, entities, topics, key_phrases, sparse_tokens, embedding vector(384), user_id, is_personal, created_at)
conversations (id, title, user_id, created_at, updated_at)
messages (id, conversation_id, role, content, citations, metrics, trace_id, feedback, agent_steps, created_at)
ingestion_tasks (id, status, progress, filename, message, document_id, chunk_count, user_id, metadata, is_personal, created_at, updated_at)
ingestion_chunks (id, task_id, content, metadata, status, claimed_at, created_at)
evaluation_logs (message_id, evaluator, scores, reasoning)
evaluation_alerts (message_id, metric_name, value, threshold, comment)

-- Indexes
HNSW index on chunks.embedding (vector_cosine_ops)
GIN index on chunks.text (full-text search)
GIN index on chunks.topics
B-tree index on chunks.document_id
B-tree index on ingestion_tasks.status

-- Key RPC functions
match_hybrid_chunks — Hybrid dense+sparse+title-boost search
claim_ingestion_chunks — Atomic batch claim for worker
```

---

## 8. Deployment & Infrastructure

**Terraform** (`terraform/` — 5 config files):
- EC2 instance (default `t3a.medium`, Ubuntu 22.04)
- Custom VPC with public subnet + internet gateway + Elastic IP
- IAM roles for ECR access and SSM management
- Security group: ports 80/443
- Amazon ECR repositories for `nexus-backend` and `nexus-frontend`

**Docker Compose Production** (`docker-compose.prod.yml`):
```
3 services:
  backend:  ECR image, 1.5GB memory limit, 768MB reservation, port 8000
  frontend: ECR image, 256MB memory limit, port 3000
  caddy:    caddy:2-alpine, ports 80/443, auto-TLS via Let's Encrypt
```

**Caddy Reverse Proxy** (`Caddyfile`):
- Routes `/api*` → backend:8000 (with `flush_interval -1` for SSE streaming)
- Routes everything else → frontend:3000
- Auto-TLS via ACME for the production domain

**CI/CD** (`.github/workflows/aws-deploy.yml`):
```
Trigger: push to main OR manual workflow_dispatch
Jobs:
  1. validate: Python 3.12, Ruff format + lint checks
  2. build-backend: Docker Buildx → push to ECR (latest + SHA tag)
  3. build-frontend: Docker Buildx → push to ECR (latest + SHA tag)
  4. deploy: SSM send-command to EC2 → pull images → docker-compose up
```

The deployment encodes `docker-compose.prod.yml`, `Caddyfile`, and `.env` as base64, sends them to EC2 via SSM `AWS-RunShellScript`, and does a rolling restart.

---

## 9. Skills System

A plugin-like system (`backend/skills/`) with a JSON registry and per-skill directories:

**Registered Skills**:
1. **Synthetic Research Agent** — Deep academic/web research for grounding complex queries
2. **Senior Financial Consultant** — Balance sheet analysis, cash flow forecasting, equity research

Each skill has a `metadata` block with `name`, `description`, `role`, `expertise`, `category`, and a `content` system prompt.

---

## 10. Key Techniques Demonstrated (Summary Table)

| Technique | Implementation Detail | Status |
|---|---|---|
| **Multi-Agent Orchestration** | LangGraph StateGraph with Supervisor → Researcher → Analyst → Validator pattern, reflection loop | ✅ Active |
| **Adaptive RAG** | Query tier routing (direct/rag/agentic) via supervisor heuristics | ✅ Active |
| **Hybrid Search** | Qdrant dense (cosine) + Supabase pgvector fallback + PostgreSQL full-text ts_rank_cd | ✅ Active |
| **Semantic Keyword Boost** | Exact substring matching for rare tokens elevates score to 0.95 | ✅ Active |
| **Cross-Encoder Reranking** | Cohere rerank-english-v3.0 API (not local model — cost-optimized) | ✅ Active |
| **Self-RAG Validation** | gpt-4o-mini as claim-by-claim fact-checker with structured JSON output | ✅ Active |
| **Semantic Chunking** | Cosine-breakpoint splitting with sentence embeddings, min/max token enforcement | ✅ Active |
| **Input Guardrails** | Profanity (BetterProfanity), Injection (7 regex patterns), PII (5 regex patterns + redaction) | ✅ Active |
| **Output Guardrails** | Self-RAG hallucination gating (>50% blocks), toxicity filter, PII leak detection | ✅ Active |
| **Evaluation Pipeline** | Dual: LLM-as-Judge (100% queries) + RAGAS (10% sampling), threshold alerting | ✅ Active |
| **Semantic Caching** | Upstash Redis with cosine-similarity matching (≥0.85), TTL + doc-aware invalidation | ✅ Active |
| **SSE Streaming** | Token-by-token streaming with agent activity feed, heartbeats, and structured event types | ✅ Active |
| **Background Ingestion** | Dedicated thread + ProcessPoolExecutor with atomic claim, timeouts, pool recovery | ✅ Active |
| **Multi-Turn Conversations** | Conversation persistence in Supabase, history injection into agent state | ✅ Active |
| **Structured LLM Output** | Pydantic-based `with_structured_output()` for analyst reasoning/answer separation | ✅ Active |
| **Infrastructure as Code** | Terraform for AWS EC2/VPC/ECR/IAM/EIP provisioning | ✅ Active |
| **CI/CD** | GitHub Actions: lint → Docker build → ECR push → SSM deploy to EC2 | ✅ Active |
| **Observability** | Langfuse `@observe()` on every pipeline function — full trace trees with cost tracking | ✅ Active |
| **Session-Scoped Retrieval** | `user_id` + `is_personal` filtering ensures document isolation between users | ✅ Active |

---

## 11. Cost Architecture

| Service | Role | Tier | Monthly Cost |
|---|---|---|---|
| AWS EC2 | Backend + Frontend | t3.small (2 vCPU, 2GB) | $12–15 |
| AWS EBS/EIP | Storage + Static IP | 24GB GP3 + EIP | $2–4 |
| Qdrant Cloud | Vector Database | Free Tier (1GB) | $0 |
| Supabase | PostgreSQL + Metadata | Free Tier (500MB) | $0 |
| Upstash Redis | Semantic Cache | Free Tier (10K/day) | $0 |
| OpenAI | Self-RAG + Generation | gpt-4o-mini | $2–5 |
| Cohere | Cross-encoder Reranking | rerank-english-v3.0 | <$1 |
| **Total** | | | **$16–24** |

Key cost optimization: Using gpt-4o-mini for Self-RAG validation (instead of a local NLI model) reduced fixed infrastructure by ~1.5GB RAM, keeping the system on t3.small instead of t3.medium.

---

## 12. Production Hardening Details

1. **Infinite Loop Prevention**: `max_iterations=3` + `search_count≥2` hard stops in supervisor
2. **ProcessPoolExecutor Recovery**: If NLP child process crashes (OOM), pool is automatically recreated
3. **Timeout Protection**: 120s timeout per ingestion batch
4. **Fail-Safe Self-RAG**: If validation itself errors, defaults to FAILURE (never passes silently)
5. **SSE Connection Stability**: Warming comments, 5-second heartbeats, `flush_interval -1` in Caddy
6. **Graceful Degradation**: Cohere unavailable → falls back to vector score ordering; Qdrant down → falls back to Supabase hybrid search
7. **Session Mismatch Detection**: If user queries a document that exists under a different user_id, warns about Incognito/session issues
8. **Atomic Task Claiming**: Supabase RPC `claim_ingestion_chunks` prevents double-processing
9. **Retry Logic**: Task status updates retried up to 3 times
10. **Proxy Buffer Flushing**: `X-Accel-Buffering: no` header + Caddy `flush_interval -1` for reliable SSE

---

## 13. File Count & Codebase Size

| Directory | Files | Purpose |
|---|---|---|
| `backend/agents/` | 5 files | Graph, nodes, state, tools, skill_orchestrator |
| `backend/ingestion/` | 10 files | Parser, cleaner, chunker, enricher, embedder, upserter, pipeline, worker, reaper, summarizer |
| `backend/retrieval/` | 5 files | Searcher, reranker, self_rag, generator, audit |
| `backend/guardrails/` | 3 files | Input guard, output guard, models |
| `backend/api/` | 12 files | Routes (query, ingest, health, search, agents, documents, history, tasks, skills, eval), middleware, security |
| `backend/cache/` | 1 file | Semantic cache |
| `backend/observability/` | 1 file | Langfuse tracing |
| `backend/evaluation/` | 4 files | RAGAS eval, LLM judge, regression runner, eval manager |
| `backend/skills/` | 2 dirs + registry | Financial analyst, researcher skills |
| `frontend/src/components/` | 13 files | Full UI component library |
| `terraform/` | 5 .tf files | IaC for AWS |
| `sql/` | 2 files | Schema + ingestion queue |
| `.github/workflows/` | 2 files | CI/CD pipelines |
| Root | Config files | Dockerfile, docker-compose, Caddyfile, pyproject.toml |

**Total**: ~60+ source files across backend, frontend, infrastructure, and CI/CD.
