# Nexus AI — Multi-Agent Research Intelligence Platform

> A production-grade Applied AI system featuring adaptive RAG, multi-agent orchestration, hybrid retrieval, LLM-powered hallucination detection, and a zero-downtime CI/CD pipeline on AWS.

Live at **[project-nexus.duckdns.org](https://project-nexus.duckdns.org)**

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Key Features](#key-features)
3. [Tech Stack](#tech-stack)
4. [Query Pipeline (Deep Dive)](#query-pipeline-deep-dive)
5. [Ingestion Pipeline (Deep Dive)](#ingestion-pipeline-deep-dive)
6. [Guardrail System](#guardrail-system)
7. [Agent Orchestration — Radial Discovery](#agent-orchestration--radial-discovery)
8. [Observability & Evaluation](#observability--evaluation)
9. [Infrastructure & CI/CD](#infrastructure--cicd)
10. [Cost Architecture](#cost-architecture)
11. [Local Development Setup](#local-development-setup)
12. [Environment Variables Reference](#environment-variables-reference)

---

## Architecture Overview

```
┌───────────────────────────────────────────────────────┐
│  Next.js 15 Frontend (Amazon ECR → EC2)               │
│  ChatInterface · KnowledgeHub · SkillHub · Metrics    │
└───────────────────────────┬───────────────────────────┘
                            │ HTTPS / SSE
┌───────────────────────────▼───────────────────────────┐
│  Caddy Reverse Proxy (TLS termination, auto-HTTPS)    │
└───────────────────────────┬───────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────┐
│  FastAPI Backend (Amazon ECR → EC2, Python 3.12)      │
│                                                       │
│  ┌─────────────────────────────────────────────────┐  │
│  │  Query Route  (SSE Streaming)                   │  │
│  │  Input Guard → Semantic Cache → Skill Inject    │  │
│  │  → Hybrid Retrieval → Rerank → LangGraph        │  │
│  │  → LLM Generate → Self-RAG → Output Guard       │  │
│  │  → LLM Judge → SSE Stream                       │  │
│  └─────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─────────────────────────────────────────────────┐  │
│  │  Ingestion Worker (background thread)           │  │
│  │  Upload → Parse → Chunk → Embed → Upsert        │  │
│  │  → Qdrant + Supabase                            │  │
│  └─────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─────────────────────────────────────────────────┐  │
│  │  Reaper Thread  (crash recovery)                │  │
│  │  Detects orphaned chunks → recycles to pending  │  │
│  └─────────────────────────────────────────────────┘  │
└──────┬──────────┬──────────┬──────────┬───────────────┘
       │          │          │          │
  Qdrant      Supabase   Upstash    Langfuse
  (Vectors)  (Postgres)  (Redis)   (Tracing)
```

---

## Key Features

### Hybrid Retrieval with Cohere Reranking
Dense vector search (OpenAI `text-embedding-3-small`) via Qdrant is combined with BM25 sparse search via Supabase RPC. A 3-stage fallback ensures results are always returned: Qdrant → Supabase hybrid → broad shared-corpus scan. Retrieved candidates are then reranked by **Cohere Rerank API** (`rerank-english-v3.0`), ordering documents by true query relevance rather than raw cosine similarity. If the Cohere API is unavailable, the system gracefully falls back to the original vector ordering.

### LLM-Powered Self-RAG (Hallucination Gate)
Every response passes through `self_rag.py` before reaching the user. A structured prompt sent to `gpt-4o-mini` evaluates each factual claim in the answer against the retrieved context chunks, returning a JSON payload:
```json
{
  "passed": false,
  "hallucination_score": 0.72,
  "unsupported_claims": ["The fund returned 18% in Q3 2024"],
  "reasoning": "No Q3 2024 performance data is present in the context."
}
```
Responses with a hallucination score above **0.5** are blocked. Responses between **0.0–0.5** pass through with a `WARNING` badge surfaced in the UI metrics panel.

### Radial Discovery — Semantic Skill Orchestration
The `SkillOrchestrator` uses OpenAI embeddings to perform semantic vector search over a Qdrant `nexus_skills` collection at query time. Matching expert agents (Finance Analyst, Legal Consultant, etc.) are dynamically injected into the system prompt with a score threshold of **0.35**, giving the LLM a specialized persona without any rule-based routing. This is called **Radial Discovery**.

### PII & Toxicity Guardrails
- **Input**: Profanity and topic restriction checks via `better-profanity` and regex.
- **Output**: Microsoft **Presidio** (`presidio-analyzer`) detects 50+ PII entity types. High-severity types (`CREDIT_CARD`, `US_SSN`, `PASSWORD`, `IBAN_CODE`, `CRYPTO`) **block the response outright**. Lower-severity detections are surfaced as warnings.

### Semantic Caching (Upstash Redis)
Exact and near-duplicate queries are served from an Upstash Redis cache, bypassing the full retrieval and generation pipeline. Cache is invalidated per-document on ingestion completion, ensuring freshness after knowledge base updates.

### Real-Time Streaming (SSE)
Responses are streamed token-by-token via Server-Sent Events. The SSE stream delivers structured JSON events for each stage: `agent_step`, `token`, `citations`, `metrics`, and `guardrail_status` — allowing the frontend to animate the agent workflow and render citations progressively.

### Crash-Resilient Ingestion (Reaper Thread)
A dedicated `Reaper` background thread polls Supabase every 30 seconds for ingestion tasks stuck in `processing` state for more than 2 minutes. Orphaned chunks are recycled to `pending` for re-pickup, preventing silent failures caused by OOM kills or container restarts. After a single retry, unrecoverable tasks are marked `error` with a descriptive message surfaced to the user.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 15, React, TypeScript |
| **Backend** | Python 3.12, FastAPI, Uvicorn |
| **Agent Framework** | LangGraph, LangChain |
| **LLMs** | OpenAI GPT-4o / GPT-4o-mini, Anthropic Claude |
| **Embeddings** | OpenAI `text-embedding-3-small` |
| **Vector DB** | Qdrant Cloud (Managed) |
| **Relational DB** | Supabase (PostgreSQL) |
| **Cache** | Upstash Redis |
| **Reranking** | Cohere Rerank API (`rerank-english-v3.0`) |
| **PII Detection** | Microsoft Presidio |
| **Document Parsing** | Unstructured (PDF), PyPDF, spaCy |
| **Observability** | Langfuse (Tracing, Cost, Evals) |
| **Containerization** | Docker, Docker Compose |
| **Reverse Proxy** | Caddy (automatic TLS) |
| **Infrastructure** | AWS EC2 + ECR, Terraform |
| **CI/CD** | GitHub Actions |
| **Linting** | Ruff |

---

## Query Pipeline (Deep Dive)

Each query goes through the following stages. Every stage is traced in Langfuse via the `@observe` decorator.

```
User Query
    │
    ▼
[1] Input Guardrail (input_guard.py)
    • Profanity check (better-profanity)
    • Restricted topic detection
    • Returns: GuardResult(passed, blocked_reason)
    │
    ▼
[2] Semantic Cache Check (semantic_cache.py)
    • Upstash Redis — checks for near-duplicate cached response
    • Cache HIT → stream cached events directly
    • Cache MISS → continue pipeline
    │
    ▼
[3] Skill Orchestration (skill_orchestrator.py)
    • Embeds query with text-embedding-3-small
    • Queries Qdrant nexus_skills collection (threshold: 0.35)
    • Injects expert persona into LangGraph system prompt
    │
    ▼
[4] Hybrid Retrieval (searcher.py)
    • Dense: Qdrant query_points (text-embedding-3-small vectors)
    • Sparse fallback: Supabase RPC match_hybrid_chunks (BM25)
    • User isolation: filters by user_id OR is_personal=False
    │
    ▼
[5] Cohere Reranking (reranker.py)
    • Sends top 3×limit candidates to rerank-english-v3.0
    • Returns top_k results ordered by relevance_score
    • Graceful fallback to vector-score order on API failure
    │
    ▼
[6] LangGraph Agent DAG
    • Researcher node: structures initial answer from context
    • Validator node: Self-RAG hallucination check
    • Streaming token generation via generate_answer_stream()
    │
    ▼
[7] Output Guardrail (output_guard.py)
    • Presidio PII detection (blocks HIGH_SEVERITY: SSN, CC, etc.)
    • Self-RAG score enforcement (>0.5 = blocked)
    • Returns: passed | warning | blocked
    │
    ▼
[8] LLM Judge Evaluation (llm_judge.py)
    • gpt-4o-mini evaluates Faithfulness, Relevance, Completeness
    • Score 1-10 per dimension — surfaced in MetricsPanel
    • Judge failure → "Eval N/A" displayed (no silent 100% fallback)
    │
    ▼
[9] SSE Stream Response
    • Token-by-token streaming
    • Citations, agent steps, guardrail status, metrics events
```

---

## Ingestion Pipeline (Deep Dive)

Documents are processed asynchronously through a multi-stage pipeline with crash recovery.

```
File Upload (POST /api/ingest/upload)
    │
    ▼
[1] Validation & Dedup
    • MIME type validation (python-magic)
    • SimHash fingerprinting (simhash) — rejects exact duplicates
    │
    ▼
[2] Task & Chunk Creation (Supabase)
    • ingestion_tasks row created (status: pending)
    • ingestion_chunks rows created — one per chunk
    │
    ▼
[3] Background Worker (worker.py — dedicated thread)
    • Atomic chunk claim: Supabase RPC claim_ingestion_chunks
    • Prevents double-processing in multi-instance scenarios
    │
    ▼
[4] NLP Processing (ProcessPoolExecutor — isolated process)
    • PDF parsing: Unstructured + PyPDF
    • Text cleaning, sentence chunking
    • YAKE keyword extraction
    • spaCy (en_core_web_sm) entity tagging
    • OpenAI text-embedding-3-small embedding generation
    │
    ▼
[5] Upsert (upserter.py)
    • Qdrant: upsert_points to nexus_chunks collection
    • Supabase: insert chunk rows with vectors + metadata
    • Cache: invalidates Upstash Redis for affected documents
    │
    ▼
[6] Finalization
    • gpt-4o-mini generates document description/summary
    • Task marked completed (100% progress)
    │
    ▼
[Reaper Thread — parallel, every 30s]
    • Detects tasks with no heartbeat for >2 min
    • Recycles stuck chunks to pending (one retry)
    • Terminal failure → marks task as error
```

---

## Guardrail System

Nexus has a dual-layer guardrail system covering both input and output.

### Input Guardrails (`input_guard.py`)
| Check | Method | Action on Fail |
|---|---|---|
| Profanity | `better-profanity` | Block + return 400 |
| Restricted topics | Regex on `RESTRICTED_TOPICS` config | Block + return 400 |

### Output Guardrails (`output_guard.py`)
| Check | Method | Threshold | Action |
|---|---|---|---|
| Toxicity | `better-profanity` | Any match | Block response |
| High-severity PII | Presidio (`US_SSN`, `CREDIT_CARD`, `PASSWORD`, `IBAN_CODE`, `CRYPTO`) | Any match | Block response |
| Low-severity PII | Presidio (email, phone, etc.) | Any match | Warning badge |
| Hallucination | Self-RAG `gpt-4o-mini` | score > 0.5 | Block response |
| Hallucination (low) | Self-RAG `gpt-4o-mini` | score ≤ 0.5 | Warning badge |

The `TECHNICAL_WHITELIST` prevents false positives on common development terms (mock, stub, lorem, citations, etc.).

---

## Agent Orchestration — Radial Discovery

Unlike static agent routing (e.g., keyword matching or if/else chains), Nexus uses **Radial Discovery**: a semantic retrieval pattern over a dedicated `nexus_skills` Qdrant collection.

**How it works:**

1. Each Agent Skill (Financial Analyst, Legal Consultant, etc.) is stored as a vector in Qdrant — embedding of its `role`, `expertise`, and `description`.
2. At query time, the user's query is embedded and a vector search returns the top 2 matching skills (score threshold: 0.35).
3. Matching skill `content` blocks (detailed persona instructions) are injected into the LangGraph system prompt before LLM generation.
4. The LLM fully adopts the expert persona — generating responses with domain-appropriate depth and tone.

**Skill sync:** `backend/scripts/sync_skills.py` reads SKILL.md files from `_agents/skills/` and upserts them into Qdrant using deterministic UUIDs (UUID5 from `nexus.skills.<skill_id>`), enabling idempotent re-runs.

**Skill Hub UI:** The `SkillHub` component calls `GET /api/skills` to display all available agents, their expertise tags, and match scores from the last query.

---

## Observability & Evaluation

### Langfuse Tracing
All major pipeline stages are traced via the `@observe` decorator wrapping key functions:
- `Search Knowledge Base`
- `Cohere Reranking`
- `Self-RAG Validation`
- `Output Guardrails`
- `LLM Generation`

Each trace captures: latency, token counts, cost, input/output payloads, and model parameters.

### LLM-as-Judge Evaluation
After each response, an async LLM judge evaluates:
| Dimension | Scale | Description |
|---|---|---|
| **Faithfulness** | 1–10 | Is the answer grounded in retrieved context? |
| **Relevance** | 1–10 | Does the answer address the user's question? |
| **Completeness** | 1–10 | Is the answer sufficiently thorough? |

These scores are streamed back to the frontend in the final SSE event and displayed in the **MetricsPanel** component. If the judge call fails (timeout, API error), the metric is displayed as **"Eval N/A"** — not silently replaced with a perfect score.

### MetricsPanel States
| State | Display | Meaning |
|---|---|---|
| Scored | `8.5 / 10` | Normal eval result |
| General KB | `General KB` | Response from shared corpus, no personal docs |
| Eval N/A | `Eval N/A` | Judge call failed |
| Guardrail Warning | `⚠ WARNING` | Low-severity PII or hallucination detected |
| Guardrail Blocked | `🚫 BLOCKED` | Response blocked by guardrail |

---

## Infrastructure & CI/CD

### AWS Architecture
```
Internet → Route53/DuckDNS → EC2 (t3.small, 2GB RAM)
                                    │
                            Docker Compose
                         ┌──────┬──────┬──────┐
                      Backend Frontend Caddy
                      (1.5GB)  (256MB)  (TLS)
                         │
                    Amazon ECR
                  (Container Registry)
```

**Terraform** manages all AWS resources:
- `network.tf`: VPC, security groups, ingress rules (80/443/22)
- `ec2.tf`: t3.small instance, EBS volume, IAM role for ECR/SSM
- `ecr.tf`: Two ECR repositories (`nexus-backend`, `nexus-frontend`)

### GitHub Actions CI/CD (`aws-deploy.yml`)

The pipeline uses **path-based change detection** to avoid unnecessary builds:

```
Push to main
     │
     ▼
[1] Detect Changes (dorny/paths-filter)
     • backend/**  → triggers backend build
     • frontend/** → triggers frontend build
     • docs/**     → skipped entirely
     │
     ▼
[2] Lint & Verify (always runs)
     • ruff format --check backend/
     • ruff check backend/
     │
     ▼
[3] Build (parallel, conditional)
     • Docker Buildx with GitHub Actions cache
     • backend → ECR nexus-backend:latest
     • frontend → ECR nexus-frontend:latest
     │
     ▼
[4] Deploy via AWS SSM
     • No SSH required — SSM RunShellScript on EC2
     • Injects all secrets from GitHub Secrets → .env
     • docker-compose pull → up --force-recreate
     • docker system prune -af (clears old layers)
```

Deploy is gated: only fires if `validate` passes **and** all builds either succeeded or were skipped.

---

## Cost Architecture

Nexus is architected to run production AI workloads on a **t3.small (2 vCPU, 2GB RAM)** EC2 instance at ~$15/month.

### Key Cost Decisions

**Cohere Rerank API instead of local CrossEncoder**
Replacing `cross-encoder/ms-marco-MiniLM-L-6-v2` (sentence-transformers) with the Cohere Rerank API:
- Removed ~1.5GB from Docker image size
- Freed ~700MB of runtime RAM
- API cost: $1 per 1,000 rerank calls ≈ negligible for typical usage
- Enabled running on t3.small instead of t3.medium (~$15/month saving)

**LLM-as-Validator instead of local NLI model**
Using `gpt-4o-mini` for Self-RAG instead of `cross-encoder/nli-deberta-v3-small`:
- Local NLI would require ~1.5GB RAM — impossible on t3.small
- `gpt-4o-mini` at $0.15/1M tokens: 1,000 validations ≈ $0.10
- Bonus: structured JSON output with reasoning, vs. a raw float from local NLI

**Managed SaaS tiers (free)**
| Service | Plan | Monthly Cost |
|---|---|---|
| Qdrant Cloud | Free tier | $0 |
| Supabase | Free tier | $0 |
| Upstash Redis | Free tier | $0 |
| Langfuse | Cloud free tier | $0 |

**Total estimated monthly infrastructure cost: ~$15–20** (EC2 + ECR storage + data transfer)

---

## Local Development Setup

### Prerequisites
- Python 3.12+
- Node.js 18+
- Docker & Docker Compose (optional, for local prod simulation)

### 1. Clone and configure

```bash
git clone https://github.com/bellerophon95/nexus.git
cd nexus
cp .env.example .env
# Fill in your API keys in .env
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. FastAPI's interactive docs are at `http://localhost:8000/docs`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`.

### 4. Linting

```bash
pip install ruff
ruff format backend/    # Auto-format
ruff check backend/     # Lint check
```

### 5. Tests

```bash
pytest backend/tests/ -v
```

### 6. Docker (local prod simulation)

```bash
docker compose up --build
```

---

## Environment Variables Reference

Copy `.env.example` to `.env` and populate all values.

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | GPT-4o, GPT-4o-mini, embeddings |
| `ANTHROPIC_API_KEY` | Optional | Claude models (fallback LLM) |
| `COHERE_API_KEY` | ✅ | Cohere Rerank API (`rerank-english-v3.0`) |
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_ANON_KEY` | ✅ | Public anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Service key (used server-side only) |
| `QDRANT_URL` | ✅ | Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | ✅ | Qdrant Cloud API key |
| `UPSTASH_REDIS_REST_URL` | ✅ | Upstash Redis REST endpoint |
| `UPSTASH_REDIS_REST_TOKEN` | ✅ | Upstash Redis auth token |
| `LANGFUSE_PUBLIC_KEY` | Optional | Langfuse tracing (prod) |
| `LANGFUSE_SECRET_KEY` | Optional | Langfuse tracing (prod) |
| `LANGFUSE_HOST` | Optional | Default: `https://cloud.langfuse.com` |
| `ENV` | Optional | `development` or `production` |
| `GUARDRAILS_ENABLED` | Optional | Default: `true` |

> **Security note**: Never commit `.env` to version control. In production, secrets are injected via GitHub Actions → AWS SSM → EC2 `.env` file at deploy time. Rotate any key that has appeared in a chat log or commit.

---

*Built by [Vibhor Kashmira](https://github.com/bellerophon95)*
