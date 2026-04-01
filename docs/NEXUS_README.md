# Project NEXUS — Multi-Agent Research Intelligence Platform

> A production-ready Applied AI system featuring adaptive RAG, multi-agent orchestration, hybrid retrieval with cross-encoder reranking, Self-RAG validation, guardrails, RAGAS evaluations, full observability, and semantic caching — deployed on a zero-to-low-cost serverless stack.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Overview](#2-architecture-overview)
3. [Project Structure](#3-project-structure)
4. [Environment & Configuration](#4-environment--configuration)
5. [Layer 1 — Document Ingestion & Enrichment Pipeline](#5-layer-1--document-ingestion--enrichment-pipeline)
6. [Layer 2 — Hybrid Retrieval Pipeline](#6-layer-2--hybrid-retrieval-pipeline)
7. [Layer 3 — Agent Orchestration (LangGraph)](#7-layer-3--agent-orchestration-langgraph)
8. [Layer 4 — Generation + Guardrails](#8-layer-4--generation--guardrails)
9. [Layer 5 — Observability & Evaluation](#9-layer-5--observability--evaluation)
10. [Semantic Caching Layer](#10-semantic-caching-layer)
11. [API Layer (FastAPI)](#11-api-layer-fastapi)
12. [Frontend (Next.js)](#12-frontend-nextjs)
13. [Deployment & Infrastructure](#13-deployment--infrastructure)
14. [CI/CD Pipeline](#14-cicd-pipeline)
15. [Cost Breakdown](#15-cost-breakdown)
16. [Implementation Order](#16-implementation-order)
17. [Testing Strategy](#17-testing-strategy)
18. [Future Roadmap](#18-future-roadmap)

---

## 1. Project Overview

### What It Does

NEXUS is a domain-agnostic research intelligence platform that:

1. **Ingests** heterogeneous documents (PDF, DOCX, HTML, JSON) through an enrichment pipeline
2. **Builds** a semantically-rich knowledge base with hybrid dense+sparse indexes
3. **Answers** complex multi-hop questions through coordinated specialist agents
4. **Validates** every answer through Self-RAG relevance gating and hallucination detection
5. **Monitors** every operation through full-stack observability with Langfuse

### Key Techniques Demonstrated

| Technique | Implementation | Status |
|---|---|---|
| Multi-Agent Orchestration | LangGraph StateGraph with Supervisor/Worker pattern | `[PHASED]` |
| Adaptive RAG | Query complexity classifier routing to 3 tiers | `[ACTIVE]` |
| Hybrid Search | Dense (MiniLM) + Sparse (Supabase RPC) + Qdrant | `[PHASED]` |
| Cross-Encoder Reranking | `ms-marco-MiniLM-L-6-v2` reranker on fused results | `[ACTIVE]` |
| Self-RAG Validation | LLM-based (gpt-4o-mini) hallucination gate | `[PHASED]` |
| Semantic Chunking | Cosine-breakpoint splitting with parent-child hierarchy | `[ACTIVE]` |
| Guardrails (Input) | PII anonymization, BetterProfanity, topic restriction | `[ACTIVE]` |
| Guardrails (Output) | LLM-as-Judge hallucination scoring, toxicity filter | `[PHASED]` |
| Evaluation Pipeline | RAGAS metrics + Langfuse observability | `[ACTIVE]` |
| Semantic Caching | Cosine-similarity cache in Upstash Redis | `[ACTIVE]` |
| Streaming | Server-Sent Events (SSE) token-by-token streaming | `[ACTIVE]` |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — INGESTION                                                │
│                                                                     │
│  [PDF/DOCX] ─→ [Web/HTML] ─→ [API/JSON]                           │
│       │              │              │                               │
│       └──────────────┼──────────────┘                               │
│                      ▼                                              │
│  ┌─────────────────────────────────────────────────┐               │
│  │  ENRICHMENT PIPELINE (async, retryable)          │               │
│  │  Parse → Clean → Semantic Chunk → Enrich →       │               │
│  │  Embed (dense+sparse) → Upsert                   │               │
│  └─────────────────────────────────────────────────┘               │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 2 — RETRIEVAL                                                │
│                                                                     │
│  User Query                                                         │
│       │                                                             │
│       ▼                                                             │
│  [Query Processor] ─→ expand / decompose / HyDE                    │
│       │                                                             │
│       ▼                                                             │
│  [Adaptive Router] ─→ classify complexity                           │
│       │                                                             │
│       ├── Tier 1: Direct LLM (simple queries)                      │
│       ├── Tier 2: Single-Step RAG (factoid lookups)                 │
│       └── Tier 3: Agentic Multi-Hop (complex reasoning)            │
│                                                                     │
│  Hybrid Retrieval (for Tier 2+3):                                   │
│    Dense (Supabase/MiniLM) + Sparse (Supabase RPC)                 │
│    Qdrant (Cloud) `[PHASED]`                                       │
│       ▼                                                             │
│    Reciprocal Rank Fusion (k=60) → top-20                          │
│       ▼                                                             │
│    Cross-Encoder Rerank `[ACTIVE]` → top-5                         │
│       ▼                                                             │
│    Self-RAG LLM Gate `[PHASED]` (gpt-4o-mini validator)            │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 3 — AGENT ORCHESTRATION (LangGraph)                          │
│                                                                     │
│  ┌──────────────┐     ┌──────────────────┐                         │
│  │  SUPERVISOR   │────▶│  RESEARCHER       │ vector_search,         │
│  │  (StateGraph) │     │                  │ web_search, sql_query   │
│  │              │────▶│  ANALYST          │ synthesis, reasoning    │
│  │  routes,     │     │                  │                         │
│  │  delegates,  │────▶│  VALIDATOR        │ fact-check, NLI,       │
│  │  aggregates  │     │                  │ halluc. detection       │
│  └──────────────┘     └──────────────────┘                         │
│       │                        │                                    │
│       │    ┌───────────────────┘                                    │
│       │    │  Reflection Loop: Validator → reject → Analyst (max 3) │
│       │    │                                                        │
│  [Shared State] message bus, context accumulator, checkpoints       │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 4 — GENERATION + GUARDRAILS                                  │
│                                                                     │
│  [Input Guardrails] ─→ [Generation Engine] ─→ [Output Guardrails]  │
│   • Prompt injection     • Context assembly     • Halluc. score    │
│   • PII anonymize        • Citation prompting   • Citation verify  │
│   • Topic restriction    • SSE streaming        • Toxicity filter  │
│   • Token budget         • GPT-4o-mini/Haiku    • PII leak detect  │
│                                                                     │
│                     [Semantic Cache] ◄── check before pipeline      │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 5 — OBSERVABILITY + EVALS                                    │
│                                                                     │
│  Langfuse: traces | cost tracking | latency budgets | RAGAS evals  │
│            LLM-as-Judge | drift alerts | dashboards                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Project Structure

```
nexus/
├── README.md
├── pyproject.toml                    # Python deps (Poetry or uv)
├── Dockerfile
├── docker-compose.yml                # Local development
├── .env.example
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Lint + test + RAGAS regression
│       └── deploy.yml                # Deploy to AWS (ECR + ECS/EC2)
│
├── backend/
│   ├── main.py                       # FastAPI app entrypoint
│   ├── config.py                     # Settings via pydantic-settings
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── parser.py                 # Document parsing (unstructured.io)
│   │   ├── cleaner.py                # Text normalization, dedup (SimHash)
│   │   ├── chunker.py                # Semantic chunking engine
│   │   ├── enricher.py               # Entity extraction, topic classification
│   │   ├── embedder.py               # Dense + sparse embedding
│   │   ├── upserter.py               # Qdrant + Supabase upsert
│   │   └── pipeline.py               # Orchestrates full ingestion pipeline
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── query_processor.py        # Query expansion, decomposition, HyDE
│   │   ├── dense_search.py           # Qdrant vector search
│   │   ├── sparse_search.py          # BM25 search
│   │   ├── fusion.py                 # Reciprocal Rank Fusion
│   │   ├── reranker.py               # Cross-encoder reranking
│   │   ├── self_rag_gate.py          # Relevance gating + re-retrieval
│   │   └── pipeline.py               # Orchestrates full retrieval
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── state.py                  # Pydantic state schema (NexusState)
│   │   ├── router.py                 # Adaptive query complexity classifier
│   │   ├── supervisor.py             # Supervisor agent node
│   │   ├── researcher.py             # Researcher agent node
│   │   ├── analyst.py                # Analyst agent node
│   │   ├── validator.py              # Validator agent node
│   │   ├── tools.py                  # Tool definitions (search, sql, calc)
│   │   └── graph.py                  # LangGraph StateGraph compilation
│   │
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── context_assembler.py      # Assemble ≤8K token context window
│   │   ├── prompt_templates.py       # System + user prompt templates
│   │   ├── generator.py              # LLM call with streaming
│   │   └── citation_linker.py        # Map claims to source chunks
│   │
│   ├── guardrails/
│   │   ├── __init__.py
│   │   ├── input_guard.py            # Prompt injection + PII + topic filter
│   │   ├── output_guard.py           # Hallucination + toxicity + PII leak
│   │   └── models.py                 # Guard result schemas
│   │
│   ├── cache/
│   │   ├── __init__.py
│   │   └── semantic_cache.py         # Upstash Redis semantic cache
│   │
│   ├── observability/
│   │   ├── __init__.py
│   │   ├── tracing.py                # Langfuse @observe() wrappers
│   │   ├── cost_tracker.py           # Per-model token cost aggregation
│   │   └── alerting.py               # Webhook alerts on drift/anomaly
│   │
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── ragas_eval.py             # RAGAS metric computation
│   │   ├── llm_judge.py              # LLM-as-Judge scoring
│   │   ├── golden_dataset.json       # 200+ labeled Q&A pairs
│   │   └── regression_runner.py      # CI/CD regression test runner
│   │
│   └── api/
│       ├── __init__.py
│       ├── routes_query.py           # POST /query — main query endpoint
│       ├── routes_ingest.py          # POST /ingest — document upload
│       ├── routes_health.py          # GET /health — healthcheck
│       └── middleware.py             # Rate limiting, CORS, error handling
│
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                  # Main chat interface
│   │   ├── api/
│   │   │   └── proxy/route.ts        # Optional SSE proxy for CORS
│   │   └── components/
│   │       ├── ChatInterface.tsx      # Chat UI with streaming
│   │       ├── MessageBubble.tsx      # Message with citations
│   │       ├── CitationCard.tsx       # Expandable source reference
│   │       ├── UploadPanel.tsx        # Document upload drag-and-drop
│   │       ├── AgentActivity.tsx      # Real-time agent step display
│   │       └── MetricsPanel.tsx       # Response quality metrics
│   └── public/
│
├── evals/
│   ├── golden_dataset.json           # Ground truth Q&A pairs
│   ├── run_ragas.py                  # Standalone RAGAS evaluation script
│   └── results/                      # Historical eval results
│
└── scripts/
    ├── seed_documents.py             # Seed initial document corpus
    ├── build_bm25_index.py           # Build/rebuild BM25 sparse index
    └── export_traces.py              # Export Langfuse traces for analysis
```

---

## 4. Environment & Configuration

### `.env.example`

```env
# ── LLM Providers ──
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=gpt-4o-mini                # or claude-haiku-4-5-20251001
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=2048

# ── Vector Database (Qdrant Cloud) ──
QDRANT_URL=https://xxx.qdrant.io
QDRANT_API_KEY=...
QDRANT_COLLECTION=nexus_chunks

# ── PostgreSQL (Supabase) ──
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
DATABASE_URL=postgresql://postgres:...@db.xxx.supabase.co:5432/postgres

# ── Redis (Upstash) ──
UPSTASH_REDIS_URL=https://xxx.upstash.io
UPSTASH_REDIS_TOKEN=...

# ── Observability (Langfuse) ──
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

# ── Embedding Models ──
EMBEDDING_MODEL=all-MiniLM-L6-v2     # sentence-transformers
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2

# ── Guardrails ──
GUARDRAILS_ENABLED=true
PII_DETECTION_ENABLED=true
MAX_INPUT_TOKENS=4096

# ── Cache ──
SEMANTIC_CACHE_ENABLED=true
CACHE_SIMILARITY_THRESHOLD=0.95
CACHE_TTL_SECONDS=86400

# ── App ──
APP_ENV=production
LOG_LEVEL=INFO
CORS_ORIGINS=https://nexus.yourdomain.com
```

### `config.py`

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # LLM
    openai_api_key: str
    anthropic_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048

    # Qdrant
    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection: str = "nexus_chunks"

    # Supabase
    supabase_url: str
    supabase_key: str
    database_url: str

    # Upstash
    upstash_redis_url: str
    upstash_redis_token: str

    # Langfuse
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_host: str = "https://cloud.langfuse.com"

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Guardrails
    guardrails_enabled: bool = True
    pii_detection_enabled: bool = True
    max_input_tokens: int = 4096

    # Cache
    semantic_cache_enabled: bool = True
    cache_similarity_threshold: float = 0.95
    cache_ttl_seconds: int = 86400

    # App
    app_env: str = "production"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

---

## 5. Layer 1 — Document Ingestion & Enrichment Pipeline

### Pipeline Stages

Each stage is a discrete, retryable unit of work. Failures in one stage do not corrupt prior stages.

#### Stage 1: Parse (`ingestion/parser.py`)

```python
"""
Parse heterogeneous documents into normalized text + metadata.

Supported formats:
- PDF: unstructured.io partition_pdf with hi_res strategy
- DOCX: unstructured.io partition_docx
- HTML: unstructured.io partition_html (or BeautifulSoup fallback)
- JSON/API: Custom extractors per source schema

Output: ParsedDocument(text, metadata, tables, images_desc)
"""

from unstructured.partition.pdf import partition_pdf
from unstructured.partition.docx import partition_docx
from unstructured.partition.html import partition_html
from langfuse import observe

@observe(name="parse_document")
async def parse_document(file_path: str, file_type: str) -> ParsedDocument:
    match file_type:
        case "pdf":
            elements = partition_pdf(file_path, strategy="hi_res")
        case "docx":
            elements = partition_docx(file_path)
        case "html":
            elements = partition_html(file_path)
        case _:
            raise UnsupportedFormatError(file_type)

    text = "\n\n".join([el.text for el in elements if el.text])
    tables = [el for el in elements if el.category == "Table"]
    metadata = extract_metadata(file_path, elements)

    return ParsedDocument(
        text=text,
        tables=tables,
        metadata=metadata,
        source_path=file_path,
    )
```

**Dependencies:** `pip install unstructured[all-docs]`

#### Stage 2: Clean (`ingestion/cleaner.py`)

```python
"""
Normalize text and deduplicate documents.

Steps:
1. Unicode normalization (NFKC)
2. Whitespace collapse
3. Remove headers/footers/page numbers (regex patterns)
4. SimHash fingerprint for near-duplicate detection
5. Skip if fingerprint exists in Supabase document_hashes table

Output: CleanedDocument(text, fingerprint, is_duplicate)
"""

import simhash
from langfuse import observe

@observe(name="clean_document")
async def clean_document(doc: ParsedDocument) -> CleanedDocument:
    text = normalize_unicode(doc.text)
    text = collapse_whitespace(text)
    text = remove_boilerplate(text)

    fingerprint = simhash.Simhash(text).value

    is_duplicate = await check_duplicate(fingerprint, threshold=3)
    if is_duplicate:
        logger.info(f"Near-duplicate detected: {doc.source_path}")

    return CleanedDocument(
        text=text,
        fingerprint=fingerprint,
        is_duplicate=is_duplicate,
        metadata=doc.metadata,
    )
```

**Dependencies:** `pip install simhash-pysimhash`

#### Stage 3: Semantic Chunking (`ingestion/chunker.py`)

This is the most critical stage. Chunking quality constrains retrieval accuracy more than embedding model choice.

```python
"""
Semantic chunking using cosine-distance breakpoints.

Algorithm:
1. Split document into sentences (spaCy sentence segmenter)
2. Embed each sentence with the embedding model
3. Compute cosine distances between consecutive sentence embeddings
4. Identify breakpoints where distance exceeds a percentile threshold
5. Merge sentences between breakpoints into chunks
6. Enforce min_chunk_tokens (100) and max_chunk_tokens (512) constraints
7. Attach parent document reference + context header to each chunk

Special handling:
- Tables: Detected and kept intact as single chunks
- Lists: Grouped with their header sentence
- Code blocks: Preserved as atomic units

Output: list[Chunk] with parent_id, header, text, token_count
"""

from sentence_transformers import SentenceTransformer
from langfuse import observe
import numpy as np

class SemanticChunker:
    def __init__(
        self,
        embed_model: SentenceTransformer,
        breakpoint_percentile: float = 90,  # split at top 10% distance valleys
        min_chunk_tokens: int = 100,
        max_chunk_tokens: int = 512,
    ):
        self.embed_model = embed_model
        self.breakpoint_percentile = breakpoint_percentile
        self.min_tokens = min_chunk_tokens
        self.max_tokens = max_chunk_tokens

    @observe(name="semantic_chunk")
    def chunk(self, document: CleanedDocument) -> list[Chunk]:
        # 1. Sentence segmentation
        sentences = self.segment_sentences(document.text)

        # 2. Embed all sentences (batched)
        embeddings = self.embed_model.encode(
            sentences, batch_size=64, show_progress_bar=False
        )

        # 3. Cosine distances between consecutive sentences
        distances = np.array([
            1 - np.dot(embeddings[i], embeddings[i + 1])
            / (np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[i + 1]))
            for i in range(len(embeddings) - 1)
        ])

        # 4. Breakpoints at percentile threshold
        threshold = np.percentile(distances, self.breakpoint_percentile)
        breakpoints = distances > threshold

        # 5. Merge sentences between breakpoints
        chunks = self.merge_at_breakpoints(sentences, breakpoints)

        # 6. Enforce size constraints
        chunks = self.enforce_size_limits(chunks)

        # 7. Attach metadata
        return [
            Chunk(
                text=c,
                parent_id=document.metadata.doc_id,
                header=document.metadata.title,
                token_count=count_tokens(c),
            )
            for c in chunks
        ]

    def segment_sentences(self, text: str) -> list[str]:
        """Use spaCy for sentence segmentation with special handling."""
        # Detect tables and code blocks first — keep them atomic
        segments = []
        for block in split_special_blocks(text):
            if block.is_table or block.is_code:
                segments.append(block.text)
            else:
                segments.extend(spacy_sentencize(block.text))
        return segments

    def merge_at_breakpoints(
        self, sentences: list[str], breakpoints: np.ndarray
    ) -> list[str]:
        chunks = []
        current = [sentences[0]]
        for i, is_break in enumerate(breakpoints):
            if is_break:
                chunks.append(" ".join(current))
                current = [sentences[i + 1]]
            else:
                current.append(sentences[i + 1])
        if current:
            chunks.append(" ".join(current))
        return chunks

    def enforce_size_limits(self, chunks: list[str]) -> list[str]:
        """Merge undersized chunks, split oversized ones."""
        result = []
        buffer = ""
        for chunk in chunks:
            tokens = count_tokens(chunk)
            if tokens < self.min_tokens:
                buffer += " " + chunk
            else:
                if buffer:
                    result.append(buffer.strip())
                    buffer = ""
                if tokens > self.max_tokens:
                    result.extend(self.split_oversized(chunk))
                else:
                    result.append(chunk)
        if buffer:
            result.append(buffer.strip())
        return result
```

**Dependencies:** `pip install sentence-transformers spacy` + `python -m spacy download en_core_web_sm`

#### Stage 4: Enrich (`ingestion/enricher.py`)

```python
"""
Extract structured metadata from chunks.

Extractions:
1. Named entities (spaCy NER): PERSON, ORG, DATE, MONEY, etc.
2. Topic classification: Zero-shot classifier assigns topic labels
3. Document type: research_paper | legal | technical | general
4. Key phrases: TF-IDF or YAKE keyword extraction

Output: EnrichedChunk with entities, topics, doc_type, key_phrases
"""

@observe(name="enrich_chunk")
async def enrich_chunk(chunk: Chunk) -> EnrichedChunk:
    entities = extract_entities(chunk.text)       # spaCy NER
    topics = classify_topic(chunk.text)           # zero-shot-classification
    key_phrases = extract_key_phrases(chunk.text) # YAKE

    return EnrichedChunk(
        **chunk.dict(),
        entities=entities,
        topics=topics,
        key_phrases=key_phrases,
    )
```

#### Stage 5: Embed (`ingestion/embedder.py`)

```python
"""
Generate dense and sparse representations for each chunk.

Dense: sentence-transformers all-MiniLM-L6-v2 (384 dimensions)
  - Fast, good quality, runs on CPU
  - Batch encoding for efficiency

Sparse: BM25 token frequencies
  - Tokenize with same analyzer as query-time BM25
  - Store token frequencies in Supabase for query-time BM25

Output: EmbeddedChunk with dense_vector (384d) and sparse_tokens (dict)
"""

@observe(name="embed_chunks")
async def embed_chunks(chunks: list[EnrichedChunk]) -> list[EmbeddedChunk]:
    texts = [c.text for c in chunks]

    # Dense embeddings (batched)
    dense_vectors = embed_model.encode(texts, batch_size=64)

    # Sparse tokenization for BM25
    sparse_tokens = [tokenize_for_bm25(t) for t in texts]

    return [
        EmbeddedChunk(
            **chunk.dict(),
            dense_vector=dense_vectors[i].tolist(),
            sparse_tokens=sparse_tokens[i],
        )
        for i, chunk in enumerate(chunks)
    ]
```

#### Stage 6: Upsert (`ingestion/upserter.py`)

```python
"""
Write embedded chunks to vector DB and metadata store.

Qdrant: Dense vectors + metadata payload (for filtered search)
Supabase: Full chunk text, metadata, sparse tokens, document lineage

Operations:
1. Upsert to Qdrant collection with HNSW index
2. Insert into Supabase chunks table
3. Update document_hashes table (for dedup)
4. Invalidate semantic cache entries for affected documents

Both operations must succeed (basic saga pattern with rollback on failure).
"""

@observe(name="upsert_chunks")
async def upsert_chunks(chunks: list[EmbeddedChunk]) -> UpsertResult:
    # Qdrant upsert
    qdrant_points = [
        PointStruct(
            id=chunk.chunk_id,
            vector=chunk.dense_vector,
            payload={
                "text": chunk.text,
                "parent_id": chunk.parent_id,
                "header": chunk.header,
                "topics": chunk.topics,
                "entities": [e.text for e in chunk.entities],
                "doc_type": chunk.doc_type,
                "created_at": chunk.created_at.isoformat(),
            },
        )
        for chunk in chunks
    ]
    await qdrant_client.upsert(collection=COLLECTION, points=qdrant_points)

    # Supabase insert
    rows = [chunk_to_row(c) for c in chunks]
    await supabase.table("chunks").upsert(rows).execute()

    # Invalidate cache
    await invalidate_cache_for_documents(
        doc_ids=list(set(c.parent_id for c in chunks))
    )

    return UpsertResult(count=len(chunks), status="success")
```

### Qdrant Collection Setup

```python
from qdrant_client.models import VectorParams, Distance

await qdrant_client.create_collection(
    collection_name="nexus_chunks",
    vectors_config=VectorParams(
        size=384,                    # all-MiniLM-L6-v2 dimension
        distance=Distance.COSINE,
    ),
    hnsw_config=HnswConfigDiff(
        m=16,                        # HNSW graph connections
        ef_construct=128,            # Build-time search breadth
    ),
    optimizers_config=OptimizersConfigDiff(
        indexing_threshold=10000,    # Index after 10K vectors
    ),
)
```

### Supabase Schema

```sql
-- Document metadata
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    source_path TEXT,
    doc_type TEXT,
    fingerprint BIGINT UNIQUE,       -- SimHash for dedup
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Chunk storage (for BM25 + metadata)
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    header TEXT,
    token_count INTEGER,
    entities JSONB DEFAULT '[]',
    topics TEXT[] DEFAULT '{}',
    key_phrases TEXT[] DEFAULT '{}',
    sparse_tokens JSONB DEFAULT '{}', -- {token: frequency} for BM25
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for BM25 full-text search
CREATE INDEX idx_chunks_text_search ON chunks USING gin(to_tsvector('english', text));

-- Index for metadata filtering
CREATE INDEX idx_chunks_topics ON chunks USING gin(topics);
CREATE INDEX idx_chunks_document_id ON chunks(document_id);
```

---

## 6. Layer 2 — Hybrid Retrieval Pipeline

### Query Processing (`retrieval/query_processor.py`)

```python
"""
Transform user queries for optimal retrieval.

Techniques (applied conditionally):
1. Query Expansion: Add synonyms/related terms via LLM
2. Query Decomposition: Split multi-part questions into sub-queries
3. HyDE (Hypothetical Document Embeddings):
   - Generate a hypothetical answer, embed it, use that vector for search
   - Bridges the query-document semantic gap
   - Only used for Tier 3 (agentic) queries due to latency cost

Output: ProcessedQuery with original, expanded, sub_queries, hyde_vector
"""

@observe(name="process_query")
async def process_query(
    query: str, tier: str
) -> ProcessedQuery:
    expanded = await expand_query(query)  # LLM adds related terms

    sub_queries = None
    hyde_vector = None

    if tier == "agentic":
        sub_queries = await decompose_query(query)
        hypothetical_answer = await generate_hyde(query)
        hyde_vector = embed_model.encode(hypothetical_answer)

    return ProcessedQuery(
        original=query,
        expanded=expanded,
        sub_queries=sub_queries,
        hyde_vector=hyde_vector,
    )
```

### Dense Search (`retrieval/dense_search.py`)

```python
@observe(name="dense_search")
async def dense_search(
    query_vector: list[float],
    filters: MetadataFilters | None = None,
    top_k: int = 50,
) -> list[SearchResult]:
    query_filter = build_qdrant_filter(filters) if filters else None

    results = await qdrant_client.search(
        collection_name="nexus_chunks",
        query_vector=query_vector,
        query_filter=query_filter,
        limit=top_k,
        score_threshold=0.3,  # minimum relevance floor
    )

    return [
        SearchResult(
            chunk_id=r.id,
            text=r.payload["text"],
            score=r.score,
            metadata=r.payload,
        )
        for r in results
    ]
```

### Sparse Search / BM25 (`retrieval/sparse_search.py`)

```python
"""
BM25 keyword search on the Supabase chunks table.

Two implementation options:
  A) PostgreSQL full-text search (ts_rank) — simpler, no extra deps
  B) rank_bm25 in-memory — more accurate BM25 scoring

We use option A for simplicity + managed infrastructure:
"""

@observe(name="sparse_search")
async def sparse_search(
    query: str,
    filters: MetadataFilters | None = None,
    top_k: int = 50,
) -> list[SearchResult]:
    filter_clause = build_sql_filter(filters) if filters else "TRUE"

    result = await supabase.rpc(
        "bm25_search",
        {
            "search_query": query,
            "filter_clause": filter_clause,
            "result_limit": top_k,
        },
    ).execute()

    return [
        SearchResult(
            chunk_id=r["id"],
            text=r["text"],
            score=r["rank"],
            metadata=r,
        )
        for r in result.data
    ]
```

Supabase SQL function:

```sql
CREATE OR REPLACE FUNCTION bm25_search(
    search_query TEXT,
    filter_clause TEXT DEFAULT 'TRUE',
    result_limit INTEGER DEFAULT 50
)
RETURNS TABLE(id UUID, text TEXT, rank REAL) AS $$
BEGIN
    RETURN QUERY EXECUTE format(
        'SELECT id, text, ts_rank_cd(to_tsvector(''english'', text), plainto_tsquery(''english'', $1)) as rank
         FROM chunks
         WHERE to_tsvector(''english'', text) @@ plainto_tsquery(''english'', $1)
         AND %s
         ORDER BY rank DESC
         LIMIT $2',
        filter_clause
    ) USING search_query, result_limit;
END;
$$ LANGUAGE plpgsql;
```

### Reciprocal Rank Fusion (`retrieval/fusion.py`)

```python
"""
Merge dense and sparse results via Reciprocal Rank Fusion (RRF).

RRF formula: score(d) = Σ 1 / (k + rank_i(d))
  where k=60 (standard constant), rank_i is the rank in result set i.

RRF is preferred over linear combination because:
- No need to normalize scores across different retrieval methods
- Robust to score distribution differences between dense and sparse
- Simple, well-studied, competitive with learned fusion methods
"""

def reciprocal_rank_fusion(
    result_sets: list[list[SearchResult]],
    k: int = 60,
    top_n: int = 20,
) -> list[SearchResult]:
    scores: dict[str, float] = {}
    result_map: dict[str, SearchResult] = {}

    for results in result_sets:
        for rank, result in enumerate(results):
            chunk_id = result.chunk_id
            scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank + 1)
            if chunk_id not in result_map:
                result_map[chunk_id] = result

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)[:top_n]

    return [
        SearchResult(
            **result_map[cid].dict(),
            score=scores[cid],  # overwrite with RRF score
        )
        for cid in sorted_ids
    ]
```

### Cross-Encoder Reranking (`retrieval/reranker.py`)

```python
"""
Rerank fused results using a cross-encoder model.

Cross-encoders score (query, passage) pairs jointly — much more accurate
than bi-encoder cosine similarity but too slow for first-stage retrieval.
We apply it only to the top-20 fused results.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2
  - Trained on MS MARCO passage ranking
  - 22M parameters — fast inference on CPU
  - Returns relevance score [0, 1]
"""

from sentence_transformers import CrossEncoder

class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(model_name)

    @observe(name="cross_encoder_rerank")
    def rerank(
        self, query: str, results: list[SearchResult], top_k: int = 5
    ) -> list[SearchResult]:
        pairs = [(query, r.text) for r in results]
        scores = self.model.predict(pairs)

        for i, result in enumerate(results):
            result.rerank_score = float(scores[i])

        reranked = sorted(results, key=lambda x: x.rerank_score, reverse=True)
        return reranked[:top_k]
```

### Self-RAG Relevance Gate (`retrieval/self_rag_gate.py`)

```python
"""
Self-RAG: Validate that retrieved context is actually relevant before generation.

Uses an NLI (Natural Language Inference) model to check entailment between
the query and each retrieved chunk. If no chunk passes the relevance threshold,
we rewrite the query and re-retrieve (max 2 retries).

This prevents the LLM from generating answers grounded on irrelevant context —
the primary source of hallucination in RAG systems.

Model: cross-encoder/nli-deberta-v3-small
  - 3 classes: entailment, neutral, contradiction
  - We use P(entailment) as the relevance score
"""

class SelfRAGGate:
    def __init__(self, threshold: float = 0.7, max_retries: int = 2):
        self.nli_model = CrossEncoder("cross-encoder/nli-deberta-v3-small")
        self.threshold = threshold
        self.max_retries = max_retries

    @observe(name="self_rag_gate")
    async def validate_and_filter(
        self,
        query: str,
        chunks: list[SearchResult],
        retry_count: int = 0,
    ) -> list[SearchResult]:
        pairs = [(query, c.text) for c in chunks]
        scores = self.nli_model.predict(pairs)

        relevant = []
        for i, chunk in enumerate(chunks):
            # NLI output: [contradiction, neutral, entailment]
            entailment_score = float(scores[i][2])
            chunk.relevance_score = entailment_score
            if entailment_score >= self.threshold:
                relevant.append(chunk)

        if not relevant and retry_count < self.max_retries:
            rewritten_query = await rewrite_query_for_retrieval(query)
            new_chunks = await hybrid_retrieve(rewritten_query)
            return await self.validate_and_filter(
                rewritten_query, new_chunks, retry_count + 1
            )

        return relevant if relevant else chunks[:3]  # fallback: best effort
```

### Full Retrieval Pipeline (`retrieval/pipeline.py`)

```python
@observe(name="retrieval_pipeline")
async def retrieval_pipeline(
    query: str,
    filters: MetadataFilters | None = None,
) -> RetrievalResult:
    # 1. Embed query
    query_vector = embed_model.encode(query).tolist()

    # 2. Parallel dense + sparse search
    dense_results, sparse_results = await asyncio.gather(
        dense_search(query_vector, filters, top_k=50),
        sparse_search(query, filters, top_k=50),
    )

    # 3. Reciprocal Rank Fusion
    fused = reciprocal_rank_fusion(
        [dense_results, sparse_results], k=60, top_n=20
    )

    # 4. Cross-encoder reranking
    reranked = reranker.rerank(query, fused, top_k=5)

    # 5. Self-RAG relevance gate
    validated = await self_rag_gate.validate_and_filter(query, reranked)

    return RetrievalResult(
        chunks=validated,
        dense_count=len(dense_results),
        sparse_count=len(sparse_results),
        fused_count=len(fused),
    )
```

---

## 7. Layer 3 — Agent Orchestration (LangGraph)

### State Schema (`agents/state.py`)

```python
from typing import Annotated, Literal
from pydantic import BaseModel, Field
from langgraph.graph import add_messages

class AgentMessage(BaseModel):
    sender: str
    content: str
    confidence: float = 1.0
    citations: list[str] = []
    tool_calls: list[dict] = []

class NexusState(BaseModel):
    """Shared state for the LangGraph agent system."""

    # User query
    query: str
    query_tier: Literal["direct", "rag", "agentic"] = "rag"

    # Conversation
    messages: Annotated[list, add_messages] = []

    # Retrieved context
    retrieved_chunks: list[dict] = []
    retrieval_queries: list[str] = []

    # Agent communication
    agent_messages: list[AgentMessage] = []
    current_agent: str = ""
    iteration_count: int = 0
    max_iterations: int = 3

    # Validation
    validation_status: Literal["pending", "approved", "rejected"] = "pending"
    hallucination_score: float = 0.0

    # Output
    final_answer: str = ""
    citations: list[dict] = []
```

### Adaptive Query Router (`agents/router.py`)

```python
"""
Routes queries to the appropriate processing tier.

Classification approach:
- `[PHASED]`: Fine-tuned DeBERTa-v3-small classifier (2K labeled examples)
- `[ACTIVE]`: LLM-based classification (few-shot prompt via gpt-4o-mini)
"""

@observe(name="route_query")
async def route_query(state: NexusState) -> str:
    query = state.query

    # Try LLM classification directly for cost/stability
    tier = await llm_classify_query(query)

    state.query_tier = tier

    match tier:
        case "direct":
            return "generate"
        case "rag":
            return "retrieve"
        case "agentic":
            return "supervisor"
```

### Supervisor Agent (`agents/supervisor.py`)

```python
"""
Orchestrates specialist agents.

The supervisor:
1. Analyzes the query and decides which agent(s) to invoke
2. Delegates to Researcher first (gather evidence)
3. Passes evidence to Analyst (synthesize)
4. Sends synthesis to Validator (verify)
5. If Validator rejects → sends back to Analyst with feedback (reflection loop)
6. If approved or max iterations reached → passes to generation

Delegation is via conditional edges in the LangGraph StateGraph.
"""

SUPERVISOR_SYSTEM_PROMPT = """You are a research supervisor coordinating a team of specialists.
Given a user query and the current state of research, decide the next action:

- If we need more evidence: delegate to "researcher"
- If we have enough evidence and need synthesis: delegate to "analyst"
- If we have a synthesis that needs verification: delegate to "validator"
- If validation passed or max retries reached: proceed to "generate"

Current iteration: {iteration_count}/{max_iterations}
Retrieved evidence chunks: {chunk_count}
Validation status: {validation_status}

Respond with ONLY the next agent name: researcher | analyst | validator | generate"""

@observe(name="supervisor")
async def supervisor_node(state: NexusState) -> dict:
    if state.iteration_count >= state.max_iterations:
        return {"current_agent": "generate"}

    next_agent = await llm_decide(
        SUPERVISOR_SYSTEM_PROMPT.format(
            iteration_count=state.iteration_count,
            max_iterations=state.max_iterations,
            chunk_count=len(state.retrieved_chunks),
            validation_status=state.validation_status,
        ),
        state.messages,
    )

    return {
        "current_agent": next_agent.strip(),
        "iteration_count": state.iteration_count + 1,
    }
```

### Researcher Agent (`agents/researcher.py`)

```python
"""
Gathers evidence from multiple sources.

Tools available:
- vector_search: Search the Qdrant knowledge base
- web_search: Search the internet for current information
- sql_query: Query structured data in Supabase

The researcher decides which tools to use based on the query.
For multi-hop queries, it may execute multiple search passes.
"""

RESEARCHER_TOOLS = [vector_search_tool, web_search_tool, sql_query_tool]

@observe(name="researcher_agent")
async def researcher_node(state: NexusState) -> dict:
    agent = create_react_agent(
        model=llm,
        tools=RESEARCHER_TOOLS,
        system_message=RESEARCHER_SYSTEM_PROMPT,
    )

    result = await agent.ainvoke({"messages": state.messages})

    # Extract retrieved chunks from tool call results
    new_chunks = extract_chunks_from_tool_calls(result)

    return {
        "messages": result["messages"],
        "retrieved_chunks": state.retrieved_chunks + new_chunks,
        "agent_messages": state.agent_messages + [
            AgentMessage(
                sender="researcher",
                content=result["messages"][-1].content,
                citations=[c["chunk_id"] for c in new_chunks],
            )
        ],
    }
```

### Analyst Agent (`agents/analyst.py`)

```python
"""
Synthesizes retrieved evidence into a structured analysis.

Receives: all retrieved chunks + researcher notes
Produces: structured analysis with claims, evidence mapping, confidence scores

If the Validator rejected a previous analysis, the Analyst receives
the rejection feedback and must address the specific issues raised.
"""

ANALYST_SYSTEM_PROMPT = """You are a research analyst. Synthesize the retrieved evidence
into a comprehensive answer. For EVERY claim you make:
1. Cite the specific source chunk(s) that support it
2. Rate your confidence (high/medium/low)
3. Flag any gaps where evidence is insufficient

{rejection_feedback}
"""

@observe(name="analyst_agent")
async def analyst_node(state: NexusState) -> dict:
    rejection_feedback = ""
    if state.validation_status == "rejected":
        last_validation = [m for m in state.agent_messages if m.sender == "validator"]
        if last_validation:
            rejection_feedback = f"PREVIOUS REJECTION: {last_validation[-1].content}\nAddress these issues."

    prompt = ANALYST_SYSTEM_PROMPT.format(rejection_feedback=rejection_feedback)
    # ... (invoke LLM with context)
```

### Validator Agent (`agents/validator.py`)

```python
"""
Fact-checks the analyst's synthesis against retrieved evidence.

Checks:
1. Citation verification: Does each claim trace to a retrieved chunk?
2. Entailment check: Does the cited chunk actually support the claim? (NLI model)
3. Hallucination detection: Are there claims with no supporting evidence?
4. Completeness: Does the answer address all parts of the query?

Output: validation_status (approved/rejected) + feedback for analyst
"""

@observe(name="validator_agent")
async def validator_node(state: NexusState) -> dict:
    analyst_output = state.agent_messages[-1].content
    retrieved_chunks = state.retrieved_chunks

    # gpt-4o-mini based fact check (Cost-Optimized Validation)
    claims = extract_claims(analyst_output)
    validation_result = await llm_validate_claims(claims, retrieved_chunks)
    
    avg_hallucination = validation_result.hallucination_score

    if avg_hallucination > 0.3:  # >30% hallucination risk
        return {
            "validation_status": "rejected",
            "hallucination_score": avg_hallucination,
            "agent_messages": state.agent_messages + [
                AgentMessage(
                    sender="validator",
                    content=f"Rejected: {avg_hallucination:.0%} hallucination risk. "
                            f"Unsupported claims: {[c.text for c in claims if c.score > 0.3]}",
                    confidence=1 - avg_hallucination,
                )
            ],
        }

    return {
        "validation_status": "approved",
        "hallucination_score": avg_hallucination,
    }
```

### Graph Compilation (`agents/graph.py`)

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

def build_nexus_graph() -> CompiledGraph:
    graph = StateGraph(NexusState)

    # Add nodes
    graph.add_node("router", route_query)
    graph.add_node("retrieve", retrieval_node)     # single-step RAG retrieval
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("validator", validator_node)
    graph.add_node("generate", generation_node)

    # Entry point
    graph.set_entry_point("router")

    # Router → tier-based routing
    graph.add_conditional_edges("router", lambda s: s.query_tier, {
        "direct": "generate",
        "rag": "retrieve",
        "agentic": "supervisor",
    })

    # Single-step RAG → generate
    graph.add_edge("retrieve", "generate")

    # Supervisor → delegate to agent
    graph.add_conditional_edges("supervisor", lambda s: s.current_agent, {
        "researcher": "researcher",
        "analyst": "analyst",
        "validator": "validator",
        "generate": "generate",
    })

    # Agents → back to supervisor
    graph.add_edge("researcher", "supervisor")
    graph.add_edge("analyst", "supervisor")

    # Validator → conditional (reflection loop)
    graph.add_conditional_edges("validator", lambda s: s.validation_status, {
        "approved": "generate",
        "rejected": "supervisor",  # supervisor will route to analyst
    })

    # Generate → END
    graph.add_edge("generate", END)

    # Compile with persistence
    checkpointer = SqliteSaver.from_conn_string("nexus_checkpoints.db")
    return graph.compile(checkpointer=checkpointer)


# Singleton
nexus_graph = build_nexus_graph()
```

---

## 8. Layer 4 — Generation + Guardrails

### Input Guardrails (`guardrails/input_guard.py`)

```python
"""
Multi-layer input security screening.

Runs BEFORE any retrieval or LLM call.
All guardrail invocations are traced in Langfuse.
"""

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from llm_guard.input_scanners import PromptInjection, BanTopics
from langfuse import observe

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

@observe(name="input_guardrails")
async def run_input_guardrails(query: str) -> GuardResult:
    results = GuardResult(original=query, passed=True)

    # 1. Prompt injection detection
    injection_scanner = PromptInjection()
    sanitized, is_valid, risk_score = injection_scanner.scan("", query)
    if not is_valid:
        results.passed = False
        results.blocked_reason = f"Prompt injection detected (risk: {risk_score:.2f})"
        return results

    # 2. PII anonymization
    if settings.pii_detection_enabled:
        pii_results = analyzer.analyze(text=query, language="en")
        if pii_results:
            anonymized = anonymizer.anonymize(text=query, analyzer_results=pii_results)
            results.sanitized_query = anonymized.text
            results.pii_detected = [r.entity_type for r in pii_results]

    # 3. Topic restriction
    topic_scanner = BanTopics(topics=RESTRICTED_TOPICS)
    _, is_valid, _ = topic_scanner.scan("", query)
    if not is_valid:
        results.passed = False
        results.blocked_reason = "Query touches restricted topic"
        return results

    # 4. Token budget
    token_count = count_tokens(query)
    if token_count > settings.max_input_tokens:
        results.passed = False
        results.blocked_reason = f"Input exceeds {settings.max_input_tokens} token limit"

    return results
```

**Dependencies:** `pip install presidio-analyzer presidio-anonymizer llm-guard`

### Output Guardrails (`guardrails/output_guard.py`)

```python
"""
Post-generation safety checks.

Runs AFTER LLM generation, BEFORE returning to user.
"""

@observe(name="output_guardrails")
async def run_output_guardrails(
    answer: str, context_chunks: list[dict]
) -> GuardResult:
    results = GuardResult(original=answer, passed=True)

    # 1. Hallucination score (NLI entailment)
    context_text = " ".join([c["text"] for c in context_chunks])
    nli_scores = nli_model.predict([(answer, context_text)])
    hallucination_score = 1 - float(nli_scores[0][2])  # 1 - entailment
    results.hallucination_score = hallucination_score

    if hallucination_score > 0.5:
        results.warnings.append(
            f"High hallucination risk: {hallucination_score:.0%}"
        )

    # 2. Citation verification
    claims = extract_claims(answer)
    uncited = [c for c in claims if not c.has_citation]
    if uncited:
        results.warnings.append(f"{len(uncited)} uncited claims detected")

    # 3. Toxicity screening
    toxicity_scanner = Toxicity()
    _, is_valid, score = toxicity_scanner.scan("", answer)
    if not is_valid:
        results.passed = False
        results.blocked_reason = f"Toxic content detected (score: {score:.2f})"

    # 4. PII leak detection
    pii_results = analyzer.analyze(text=answer, language="en")
    if pii_results:
        results.warnings.append(
            f"PII detected in output: {[r.entity_type for r in pii_results]}"
        )

    return results
```

### Context Assembly (`generation/context_assembler.py`)

```python
"""
Assemble retrieved chunks into a context window for the LLM.

Rules:
- Max context: 8K tokens (shorter contexts produce better answers)
- Order: Most relevant first (by rerank score)
- Include chunk headers for document context
- Add source citation markers: [1], [2], etc.
"""

@observe(name="assemble_context")
def assemble_context(chunks: list[SearchResult], max_tokens: int = 8000) -> str:
    context_parts = []
    total_tokens = 0

    for i, chunk in enumerate(chunks):
        header = f"[Source {i+1}: {chunk.metadata.get('header', 'Unknown')}]"
        chunk_text = f"{header}\n{chunk.text}"
        chunk_tokens = count_tokens(chunk_text)

        if total_tokens + chunk_tokens > max_tokens:
            break

        context_parts.append(chunk_text)
        total_tokens += chunk_tokens

    return "\n\n---\n\n".join(context_parts)
```

### Generation with Streaming (`generation/generator.py`)

```python
"""
LLM generation with citation-grounded prompting and SSE streaming.
"""

SYSTEM_PROMPT = """You are a research assistant that provides accurate, well-cited answers.

RULES:
1. Base your answer ONLY on the provided context
2. Cite sources using [Source N] markers for EVERY claim
3. If the context doesn't contain enough information, say so explicitly
4. Never fabricate information not present in the sources
5. Be concise but thorough

CONTEXT:
{context}
"""

@observe(name="generate_answer")
async def generate_answer(
    query: str,
    context: str,
    stream: bool = True,
) -> AsyncGenerator[str, None]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
        {"role": "user", "content": query},
    ]

    if stream:
        async for chunk in llm.astream(messages):
            yield chunk.content
    else:
        response = await llm.ainvoke(messages)
        yield response.content
```

---

## 9. Layer 5 — Observability & Evaluation

### Langfuse Tracing (`observability/tracing.py`)

```python
"""
Initialize Langfuse and provide tracing utilities.

The @observe() decorator from langfuse automatically:
- Creates spans for each function call
- Records input/output
- Tracks token usage and cost
- Builds a hierarchical trace tree

No manual span management needed — just decorate functions.
"""

from langfuse import Langfuse
from langfuse.decorators import observe

# Initialize Langfuse client
langfuse = Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host,
)

# Custom trace metadata helper
def trace_query(query: str, session_id: str):
    """Start a new trace for a user query."""
    return langfuse.trace(
        name="nexus_query",
        input={"query": query},
        session_id=session_id,
        metadata={"app_version": APP_VERSION},
    )
```

### RAGAS Evaluation (`evaluation/ragas_eval.py`)

```python
"""
Evaluate RAG quality using RAGAS metrics.

Metrics:
- Faithfulness: Is the answer grounded in the retrieved context?
- Answer Relevancy: Is the answer relevant to the question?
- Context Precision: Are the retrieved chunks relevant?
- Context Recall: Did we retrieve all necessary information?

Three evaluation modes:
1. Offline: Run on golden dataset in CI/CD (blocks deploy on regression)
2. Online: Sample 5% of production queries
3. Human: Langfuse annotation queue for expert review
"""

from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from datasets import Dataset

@observe(name="ragas_evaluation")
async def evaluate_response(
    query: str,
    answer: str,
    contexts: list[str],
    ground_truth: str | None = None,
) -> dict[str, float]:
    data = {
        "question": [query],
        "answer": [answer],
        "contexts": [contexts],
    }
    if ground_truth:
        data["ground_truth"] = [ground_truth]

    dataset = Dataset.from_dict(data)

    metrics = [faithfulness, answer_relevancy, context_precision]
    if ground_truth:
        metrics.append(context_recall)

    result = evaluate(dataset=dataset, metrics=metrics)

    scores = {
        "faithfulness": result["faithfulness"],
        "answer_relevancy": result["answer_relevancy"],
        "context_precision": result["context_precision"],
    }
    if ground_truth:
        scores["context_recall"] = result["context_recall"]

    # Push scores to Langfuse as evaluation scores
    langfuse.score(
        trace_id=get_current_trace_id(),
        name="ragas_faithfulness",
        value=scores["faithfulness"],
    )

    return scores
```

### LLM-as-Judge (`evaluation/llm_judge.py`)

```python
"""
Use Claude Haiku as an evaluator for answer quality.

Scoring rubric (1-5):
- Correctness: factual accuracy relative to sources
- Completeness: covers all aspects of the question
- Citation quality: claims properly attributed
- Conciseness: no unnecessary verbosity
"""

JUDGE_PROMPT = """Rate this answer on a 1-5 scale for each criterion.

Question: {question}
Answer: {answer}
Source Context: {context}

Criteria:
1. Correctness (1=wrong, 5=perfectly accurate)
2. Completeness (1=incomplete, 5=thorough)
3. Citation Quality (1=no citations, 5=every claim cited)
4. Conciseness (1=verbose, 5=appropriately concise)

Respond ONLY with JSON: {{"correctness": N, "completeness": N, "citations": N, "conciseness": N}}"""

@observe(name="llm_judge")
async def llm_judge_evaluate(
    question: str, answer: str, context: str
) -> dict[str, int]:
    response = await judge_llm.ainvoke(
        JUDGE_PROMPT.format(question=question, answer=answer, context=context)
    )
    return json.loads(response.content)
```

### Regression Runner (`evaluation/regression_runner.py`)

```python
"""
CI/CD regression testing on golden dataset.

Loads golden_dataset.json (200+ Q&A pairs with ground truth),
runs the full NEXUS pipeline on each, computes RAGAS metrics,
and fails the build if any metric drops below threshold.

Usage in CI:
    python -m backend.evaluation.regression_runner --threshold-faithfulness 0.80
"""

import argparse
import json
import sys

THRESHOLDS = {
    "faithfulness": 0.80,
    "answer_relevancy": 0.75,
    "context_precision": 0.70,
    "context_recall": 0.70,
}

async def run_regression():
    with open("evals/golden_dataset.json") as f:
        golden = json.load(f)

    results = []
    for item in golden:
        # Run full pipeline
        response = await nexus_graph.ainvoke(
            NexusState(query=item["question"])
        )

        # Evaluate
        scores = await evaluate_response(
            query=item["question"],
            answer=response["final_answer"],
            contexts=[c["text"] for c in response["retrieved_chunks"]],
            ground_truth=item["ground_truth"],
        )
        results.append(scores)

    # Aggregate
    avg_scores = {
        metric: sum(r[metric] for r in results) / len(results)
        for metric in THRESHOLDS
    }

    # Check thresholds
    failures = []
    for metric, threshold in THRESHOLDS.items():
        if avg_scores[metric] < threshold:
            failures.append(
                f"{metric}: {avg_scores[metric]:.3f} < {threshold}"
            )

    if failures:
        print(f"REGRESSION DETECTED:\n" + "\n".join(failures))
        sys.exit(1)

    print(f"All metrics passed: {avg_scores}")
```

---

## 10. Semantic Caching Layer

### `cache/semantic_cache.py`

```python
"""
Semantic cache using Upstash Redis.

Instead of exact-match caching, we embed the query and compare against
cached query embeddings. If cosine similarity > 0.95, return cached response.

This handles paraphrased queries that have the same intent:
- "What is the capital of France?" ≈ "France's capital city?"
- Both return the same cached response

Cache invalidation:
- TTL-based (24h default)
- Event-based: purge on document re-ingestion via pub/sub
"""

from upstash_redis import Redis
import numpy as np
import json

class SemanticCache:
    def __init__(
        self,
        redis_client: Redis,
        embed_model,
        similarity_threshold: float = 0.95,
        ttl: int = 86400,
    ):
        self.redis = redis_client
        self.embed_model = embed_model
        self.threshold = similarity_threshold
        self.ttl = ttl

    @observe(name="cache_lookup")
    async def get(self, query: str) -> CacheResult | None:
        query_vector = self.embed_model.encode(query)

        # Get all cached query vectors (in production, use a vector index)
        cached_keys = await self.redis.keys("cache:query:*")

        for key in cached_keys:
            cached_data = await self.redis.get(key)
            if not cached_data:
                continue
            cached = json.loads(cached_data)
            cached_vector = np.array(cached["query_vector"])

            similarity = np.dot(query_vector, cached_vector) / (
                np.linalg.norm(query_vector) * np.linalg.norm(cached_vector)
            )

            if similarity >= self.threshold:
                return CacheResult(
                    answer=cached["answer"],
                    citations=cached["citations"],
                    cache_hit=True,
                    similarity=float(similarity),
                )

        return None

    @observe(name="cache_store")
    async def set(self, query: str, answer: str, citations: list[dict]):
        query_vector = self.embed_model.encode(query).tolist()
        cache_key = f"cache:query:{hash(query)}"

        await self.redis.set(
            cache_key,
            json.dumps({
                "query": query,
                "query_vector": query_vector,
                "answer": answer,
                "citations": citations,
            }),
            ex=self.ttl,
        )

    async def invalidate_for_documents(self, doc_ids: list[str]):
        """Purge cache entries that reference re-ingested documents."""
        # In production, maintain a reverse index: doc_id → cache_keys
        # For simplicity, flush all on re-ingestion
        await self.redis.flushdb()
```

---

## 11. API Layer (FastAPI)

### Main App (`main.py`)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load models, init connections
    load_embedding_model()
    load_reranker_model()
    load_nli_model()
    init_qdrant_client()
    init_supabase_client()
    init_redis_client()
    init_langfuse()
    yield
    # Shutdown: flush traces
    langfuse.flush()

app = FastAPI(
    title="NEXUS API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query_router, prefix="/api")
app.include_router(ingest_router, prefix="/api")
app.include_router(health_router, prefix="/api")
```

### Query Endpoint (`api/routes_query.py`)

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

@router.post("/query")
async def query_endpoint(request: QueryRequest) -> StreamingResponse:
    """
    Main query endpoint. Returns SSE stream.

    Flow:
    1. Check semantic cache
    2. Run input guardrails
    3. Execute NEXUS graph (router → retrieval → agents → generation)
    4. Run output guardrails
    5. Stream response via SSE
    6. Store in cache
    7. Sample for evaluation (5%)
    """
    # 1. Cache check
    if settings.semantic_cache_enabled:
        cached = await semantic_cache.get(request.query)
        if cached:
            return StreamingResponse(
                stream_cached_response(cached),
                media_type="text/event-stream",
            )

    # 2. Input guardrails
    guard_result = await run_input_guardrails(request.query)
    if not guard_result.passed:
        return JSONResponse(
            status_code=422,
            content={"error": guard_result.blocked_reason},
        )

    query = guard_result.sanitized_query or request.query

    # 3. Execute graph
    async def event_stream():
        state = NexusState(query=query)
        async for event in nexus_graph.astream_events(state):
            if event["event"] == "on_chat_model_stream":
                yield f"data: {json.dumps({'type': 'token', 'content': event['data']['chunk'].content})}\n\n"
            elif event["event"] == "on_tool_start":
                yield f"data: {json.dumps({'type': 'agent_step', 'tool': event['name']})}\n\n"

        # 4. Output guardrails
        final_state = await nexus_graph.ainvoke(state)
        output_guard = await run_output_guardrails(
            final_state["final_answer"],
            final_state["retrieved_chunks"],
        )

        # 5. Cache store
        if settings.semantic_cache_enabled:
            await semantic_cache.set(
                query, final_state["final_answer"], final_state["citations"]
            )

        # 6. Sample evaluation (5%)
        if random.random() < 0.05:
            asyncio.create_task(
                evaluate_response(query, final_state["final_answer"],
                    [c["text"] for c in final_state["retrieved_chunks"]])
            )

        yield f"data: {json.dumps({'type': 'done', 'citations': final_state['citations'], 'guardrails': output_guard.dict()})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

### Ingest Endpoint (`api/routes_ingest.py`)

```python
@router.post("/ingest")
async def ingest_endpoint(file: UploadFile) -> IngestResponse:
    """Upload and process a document through the enrichment pipeline."""
    file_path = await save_upload(file)
    result = await ingestion_pipeline(file_path, file.content_type)

    return IngestResponse(
        document_id=result.document_id,
        chunks_created=result.chunk_count,
        status="success",
    )
```

---

## 12. Frontend (Next.js)

### Key Components

**`ChatInterface.tsx`** — Main chat UI with:
- SSE streaming display (token-by-token)
- Agent activity sidebar (shows which agent is working)
- Citation cards (expandable source references)
- Document upload panel (drag-and-drop)
- Quality metrics display (optional, togglable)

**Tech stack:**
- Next.js 15 (App Router)
- Tailwind CSS
- `EventSource` for SSE streaming
- Shadcn/ui components

**SSE consumption pattern:**

```typescript
const eventSource = new EventSource(`/api/query?q=${encodeURIComponent(query)}`);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  switch (data.type) {
    case 'token':
      setAnswer(prev => prev + data.content);
      break;
    case 'agent_step':
      setAgentSteps(prev => [...prev, data.tool]);
      break;
    case 'done':
      setCitations(data.citations);
      setGuardrails(data.guardrails);
      eventSource.close();
      break;
  }
};
```

---

## 13. Deployment & Infrastructure

Nexus uses **Terraform** to manage its AWS-based production environment, ensuring that the infrastructure is version-controlled and reproducible.

### Infrastructure Provisioning (Terraform)

The infrastructure is defined in the `terraform/` directory and consists of:
- **Compute**: An EC2 instance (defaulting to `t3a.medium`) running Ubuntu 22.04 LTS.
- **Networking**: A custom VPC with a public subnet, internet gateway, and a static Elastic IP (EIP).
- **Security**: IAM roles for ECR access and SSM management, plus a dedicated security group allowing ports 80/443.
- **Container Registry**: Amazon ECR repositories for the `nexus-backend` and `nexus-frontend` images.

#### Provisioning Steps

1. **Initialize Terraform**:
   ```bash
   cd terraform
   terraform init
   ```

2. **Configure Variables**:
   Update `terraform/variables.tf` or create a `terraform.tfvars` file to specify your `aws_region`, `ami_id`, and `instance_type`.

3. **Plan and Apply**:
   ```bash
   terraform plan
   terraform apply
   ```

4. **Retrieve Outputs**:
   After completion, Terraform will output the `public_ip` and `ecr_repository_urls` needed for the CI/CD pipeline.

### Containerization (Docker)

Both the backend and frontend are containerized and pushed to Amazon ECR. 

**Backend Docker Highlights**:
- Multi-stage builds for minimal image size.
- Pre-downloads essential NLTK/spaCy models to ensure fast startup on EC2.
- Environment-aware configuration via `.env` files.

**Frontend Docker Highlights**:
- Standalone Next.js build for production performance.
- Reverse-proxied via Caddy on the host machine.

---

## 14. CI/CD Pipeline

### `.github/workflows/ci.yml`

```yaml
name: CI — Lint + Test + Eval Regression

on:
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install poetry && poetry install
      - run: poetry run ruff check backend/
      - run: poetry run pytest backend/tests/ -v

  eval-regression:
    runs-on: ubuntu-latest
    needs: lint-and-test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install poetry && poetry install
      - name: Run RAGAS regression
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          QDRANT_URL: ${{ secrets.QDRANT_URL }}
          QDRANT_API_KEY: ${{ secrets.QDRANT_API_KEY }}
        run: |
          poetry run python -m backend.evaluation.regression_runner \
            --threshold-faithfulness 0.80 \
            --threshold-relevancy 0.75
```

---

## 15. Cost Breakdown

| Service | Role | Tier / Instance | Monthly Cost (Est.) |
|---|---|---|---|
| AWS (EC2) | Backend + Frontend | `t3.small` (2 vCPU, 2GB RAM) | $12 – $15 |
| AWS (EBS/EIP) | Block Storage + Static IP | 24GB GP3 + EIP | $2 – $4 |
| Qdrant Cloud | Vector Database | Free Tier (1GB) | $0 |
| Supabase | PostgreSQL + Metadata | Free Tier (500MB) | $0 |
| Upstash Redis | Semantic Cache | Free Tier (10K/day) | $0 |
| OpenAI | Self-RAG + Foundation | `gpt-4o-mini` (Tokens) | $2 – $5 |
| **Total** | | | **$16 – $24** |

> [!TIP]
> The move to **LLM-as-a-Validator** (Self-RAG) reduced our fixed infrastructure requirements by 1.5GB RAM, allowing us to stay on the AWS `t3.small` tier instead of `t3.medium`.

---

## 16. Implementation Order

Build in this order. Each phase produces a working, testable system.

### Phase 1: Foundation (Days 1–3)
1. Project scaffolding (pyproject.toml, Dockerfile, .env)
2. `config.py` with pydantic-settings
3. FastAPI app with `/health` endpoint
4. Deploy skeleton to Railway
5. Qdrant Cloud collection setup
6. Supabase schema migration

### Phase 2: Ingestion Pipeline (Days 4–6)
1. `parser.py` — document parsing with unstructured
2. `cleaner.py` — normalization + dedup
3. `chunker.py` — semantic chunking engine (**most critical**)
4. `embedder.py` — dense + sparse embedding
5. `upserter.py` — Qdrant + Supabase writes
6. `pipeline.py` — orchestrate full ingestion
7. `/ingest` API endpoint
8. Seed 20-50 documents for testing

### Phase 3: Retrieval Pipeline (Days 7–9)
1. `dense_search.py` — Qdrant vector search
2. `sparse_search.py` — BM25 via Supabase
3. `fusion.py` — Reciprocal Rank Fusion
4. `reranker.py` — cross-encoder reranking
5. `self_rag_gate.py` — relevance gating
6. `pipeline.py` — full retrieval pipeline
7. Unit tests with known-good queries

### Phase 4: Basic RAG (Days 10–11)
1. `context_assembler.py` — context window assembly
2. `prompt_templates.py` — system prompts
3. `generator.py` — LLM generation with streaming
4. `/query` endpoint (Tier 2 only — single-step RAG)
5. Test end-to-end: ingest → query → answer

### Phase 5: Agent Orchestration (Days 12–15)
1. `state.py` — NexusState Pydantic schema
2. `router.py` — query complexity classifier
3. `supervisor.py` — supervisor agent
4. `researcher.py` — researcher agent with tools
5. `analyst.py` — analyst agent
6. `validator.py` — validator agent with NLI
7. `graph.py` — LangGraph compilation
8. Wire agents into `/query` endpoint

### Phase 6: Guardrails (Days 16–17)
1. `input_guard.py` — PII, injection, topic filter
2. `output_guard.py` — hallucination, toxicity, PII leak
3. Wire into `/query` pipeline

### Phase 7: Observability & Evals (Days 18–20)
1. Langfuse initialization + `@observe()` decorators everywhere
2. `ragas_eval.py` — RAGAS metric computation
3. `llm_judge.py` — LLM-as-Judge scoring
4. Build `golden_dataset.json` (50+ Q&A pairs minimum)
5. `regression_runner.py` — CI/CD regression tests
6. Online evaluation sampling (5%)

### Phase 8: Caching + Polish (Days 21–23)
1. `semantic_cache.py` — Upstash Redis cache
2. Frontend: Next.js chat interface with streaming
3. Frontend: citation cards, agent activity display
4. Frontend: document upload panel

### Phase 9: CI/CD + Deploy (Days 24–25)
1. GitHub Actions CI (lint + test + eval regression)
2. Deploy pipeline to Railway + Vercel
3. End-to-end smoke tests
4. Portfolio page update

---

## 17. Testing Strategy

```
backend/tests/
├── unit/
│   ├── test_chunker.py             # Semantic chunking edge cases
│   ├── test_fusion.py              # RRF correctness
│   ├── test_reranker.py            # Reranking order validation
│   ├── test_self_rag_gate.py       # Relevance threshold behavior
│   ├── test_router.py              # Query classification
│   ├── test_input_guard.py         # PII detection, injection blocking
│   ├── test_output_guard.py        # Hallucination scoring
│   └── test_semantic_cache.py      # Cache hit/miss/invalidation
│
├── integration/
│   ├── test_ingestion_pipeline.py  # End-to-end document processing
│   ├── test_retrieval_pipeline.py  # Dense + sparse + rerank
│   ├── test_agent_graph.py         # LangGraph execution paths
│   └── test_query_endpoint.py      # Full API flow
│
└── evaluation/
    ├── golden_dataset.json          # Ground truth Q&A pairs
    └── test_regression.py           # RAGAS metric thresholds
```

---

## 18. Future Roadmap

1. **GraphRAG** — Neo4j knowledge graph for entity-relationship reasoning
2. **Fine-Tuned Embeddings** — LoRA on sentence-transformers for domain specificity
3. **Multimodal RAG** — Image/chart processing via ColPali late interaction
4. **A/B Prompt Testing** — Langfuse prompt versioning with metric comparison
5. **MCP Server** — Expose NEXUS as a Model Context Protocol tool
6. **User Feedback Loop** — Thumbs up/down → golden dataset → continuous improvement

---

## Dependencies Summary

```toml
[tool.poetry.dependencies]
python = "^3.12"
fastapi = "^0.115"
uvicorn = {extras = ["standard"], version = "^0.34"}
pydantic = "^2.10"
pydantic-settings = "^2.7"

# AI/ML
langchain = "^0.3"
langgraph = "^0.3"
langchain-openai = "^0.3"
langchain-anthropic = "^0.3"
sentence-transformers = "^3.4"
ragas = "^0.2"

# Retrieval
qdrant-client = "^1.12"
rank-bm25 = "^0.2"

# Data processing
unstructured = {extras = ["all-docs"], version = "^0.16"}
spacy = "^3.8"

# Guardrails
llm-guard = "^0.3"
presidio-analyzer = "^2.2"
presidio-anonymizer = "^2.2"

# Observability
langfuse = "^2.55"

# Infrastructure
upstash-redis = "^1.2"
supabase = "^2.13"

# Utilities
simhash-pysimhash = "^0.3"
python-multipart = "^0.0.18"
httpx = "^0.28"
```

---

*Project NEXUS — Built by Vibhor Kashmira · 2026*
