# NEXUS System Design — v1

> Version: `v1.0.0` | Date: 2026-03-27 | Status: Approved for Implementation

---

## 1. High-Level Architecture

```mermaid
graph TB
    subgraph CLIENT["Client Layer"]
        UI["Next.js Frontend\nVercel"]
        UPLOAD["Document Upload\nDrag & Drop"]
    end

    subgraph API["API Layer — FastAPI on Railway"]
        direction TB
        HEALTH["GET /api/health"]
        INGEST_EP["POST /api/ingest"]
        QUERY_EP["POST /api/query\nSSE Stream"]
        MW["Middleware\nRate Limit · CORS · Error Handler"]
    end

    subgraph CACHE["Semantic Cache"]
        REDIS["Upstash Redis\nVector Similarity≥0.95"]
    end

    subgraph GUARD_IN["Input Guardrails"]
        INJ["Prompt Injection\nllm-guard"]
        PII_IN["PII Anonymizer\npresidio"]
        TOPIC["Topic Restriction\nBanTopics"]
        TOK["Token Budget\n≤4096 tokens"]
    end

    subgraph PIPELINE["NEXUS Query Pipeline"]
        ROUTER["Adaptive Router\nTier 1 · 2 · 3"]
        RETR["Hybrid Retrieval\nPipeline"]
        AGENTS["Agent Orchestration\nLangGraph"]
        GEN["Generation Engine\ngpt-4o-mini"]
    end

    subgraph GUARD_OUT["Output Guardrails"]
        HALLUC["Hallucination Score\nNLI ≥0.5 → warn"]
        CIT_V["Citation Verify"]
        TOX["Toxicity Filter\nllm-guard"]
        PII_OUT["PII Leak Detect\npresidio"]
    end

    subgraph OBS["Observability — Langfuse"]
        TRACE["Distributed Traces\n@observe"]
        COST["Cost Tracker\nper-model token cost"]
        EVAL["RAGAS + LLM-Judge\n5% online sampling"]
        ALERT["Drift Alerts\nWebhook"]
    end

    UI -->|Query + session_id| QUERY_EP
    UPLOAD -->|UploadFile| INGEST_EP
    QUERY_EP --> MW
    INGEST_EP --> MW
    MW --> CACHE
    CACHE -->|Cache Miss| GUARD_IN
    GUARD_IN -->|Sanitized Query| PIPELINE
    PIPELINE -->|Answer + Citations| GUARD_OUT
    GUARD_OUT -->|SSE Stream| UI
    GUARD_OUT --> CACHE
    PIPELINE -.->|@observe| OBS
    GUARD_IN -.->|@observe| OBS
    GUARD_OUT -.->|@observe| OBS
```

---

## 2. Document Ingestion Pipeline

```mermaid
flowchart LR
    subgraph INPUT["Document Sources"]
        PDF["PDF\nunstructured hi_res"]
        DOCX["DOCX\nunstructured"]
        HTML["HTML\nunstructured / BS4"]
        JSON["JSON/API\nCustom extractors"]
    end

    subgraph PIPELINE["Ingestion Pipeline — async, retryable"]
        direction TB
        PARSE["① Parse\nExtract text, tables, metadata"]
        CLEAN["② Clean\nNFKC normalize · collapse whitespace\nStrip boilerplate"]
        DEDUP{"③ Dedup Check\nSimHash fingerprint\nHamming dist < 3?"}
        SKIP["Skip duplicate\nReturn is_duplicate=true"]
        CHUNK["④ Semantic Chunk\nspaCy sentence segmentation\nCosine breakpoints @ 90th pct\nmin 100 · max 512 tokens"]
        ENRICH["⑤ Enrich\nspaCy NER · Zero-shot topics\nYAKE key phrases"]
        EMBED["⑥ Embed\nDense: all-MiniLM-L6-v2 (384d)\nSparse: BM25 token freqs"]
        UPSERT["⑦ Upsert\nQdrant + Supabase\nSaga pattern rollback"]
        INVALIDATE["⑧ Cache Invalidate\nPurge Upstash entries\nfor updated doc_ids"]
    end

    subgraph STORES["Storage"]
        QDRANT["Qdrant Cloud\nDense vectors + payload\nHNSW m=16, ef=128"]
        SUPA["Supabase PostgreSQL\nChunk text + sparse tokens\nGIN full-text index"]
        HASH_T["document_hashes table\nSimHash fingerprints"]
    end

    INPUT --> PARSE
    PARSE --> CLEAN
    CLEAN --> DEDUP
    DEDUP -->|Duplicate| SKIP
    DEDUP -->|Unique| CHUNK
    CHUNK --> ENRICH
    ENRICH --> EMBED
    EMBED --> UPSERT
    UPSERT --> QDRANT
    UPSERT --> SUPA
    UPSERT --> HASH_T
    UPSERT --> INVALIDATE
```

---

## 3. Hybrid Retrieval Pipeline

```mermaid
flowchart TD
    Q["User Query"]

    subgraph PROC["Query Processing"]
        EXPAND["Query Expansion\nLLM adds synonyms + related terms"]
        DECOMP["Query Decomposition\nSplit multi-part questions\nTier 3 only"]
        HYDE["HyDE Generation\nHypothetical answer → embed\nTier 3 only"]
    end

    subgraph SEARCH["Parallel Search — asyncio.gather"]
        direction LR
        DENSE["Dense Search\nQdrant ANN\ntop-50 @ cosine ≥ 0.3"]
        SPARSE["Sparse / BM25\nSupabase ts_rank_cd\ntop-50 by rank"]
    end

    subgraph FUSION["Result Fusion"]
        RRF["Reciprocal Rank Fusion\nRRF score = Σ 1÷(k+rank)\nk=60 · merge to top-20"]
        RERANK["Cross-Encoder Rerank\nms-marco-MiniLM-L-6-v2\n(query, passage) pairs → top-5"]
    end

    subgraph GATE["Self-RAG Gate"]
        NLI["NLI Model\nnli-deberta-v3-small\nP(entailment) per chunk"]
        THRESH{"Relevance ≥ 0.7?"}
        REWRITE["Rewrite Query\nvia LLM"]
        PASS["Return Validated Chunks"]
        FALLBACK["Fallback: best-effort top-3"]
    end

    Q --> EXPAND
    EXPAND --> DECOMP
    DECOMP --> HYDE
    EXPAND --> DENSE
    EXPAND --> SPARSE
    HYDE -->|hyde_vector| DENSE
    DENSE --> RRF
    SPARSE --> RRF
    RRF --> RERANK
    RERANK --> NLI
    NLI --> THRESH
    THRESH -->|Yes| PASS
    THRESH -->|No, retry < 2| REWRITE
    REWRITE --> DENSE
    THRESH -->|No, retry = 2| FALLBACK
```

---

## 4. Agent Orchestration — LangGraph StateGraph

```mermaid
stateDiagram-v2
    [*] --> Router

    Router --> Generate : tier=direct
    Router --> Retrieve : tier=rag
    Router --> Supervisor : tier=agentic

    Retrieve --> Generate

    Supervisor --> Researcher : needs evidence
    Supervisor --> Analyst : has evidence, needs synthesis
    Supervisor --> Validator : has synthesis
    Supervisor --> Generate : max_iterations reached

    Researcher --> Supervisor
    Analyst --> Supervisor

    Validator --> Generate : approved
    Validator --> Supervisor : rejected (hallucination > 30%)

    Generate --> [*]

    note right of Supervisor
        LLM decides next agent
        based on: iteration count,
        chunk count, validation status
        Hard cap: max_iterations = 3
    end note

    note right of Validator
        NLI fact-check per claim
        avg_hallucination > 0.3 → reject
        Sends feedback to Analyst
    end note
```

---

## 5. Generation + Guardrail Pipeline (Full Query Flow)

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI /query
    participant CACHE as Semantic Cache
    participant GUARD_I as Input Guardrails
    participant NEXUS as NEXUS Graph
    participant GUARD_O as Output Guardrails
    participant LF as Langfuse

    U->>API: POST /query {query, session_id}
    API->>CACHE: lookup(embed(query))
    alt Cache Hit (cosine ≥ 0.95)
        CACHE-->>API: CacheResult{answer, citations}
        API-->>U: SSE stream cached response
    else Cache Miss
        API->>GUARD_I: run_input_guardrails(query)
        alt Injection / PII / Topic / Token violation
            GUARD_I-->>API: GuardResult{passed=false, blocked_reason}
            API-->>U: 422 {error: blocked_reason}
        else Passes
            GUARD_I-->>API: GuardResult{sanitized_query}
            API->>NEXUS: astream_events(NexusState{query})
            loop SSE Streaming
                NEXUS-->>U: data: {type: token, content: ...}
                NEXUS-->>U: data: {type: agent_step, tool: ...}
            end
            NEXUS-->>API: final_state{answer, chunks, citations}
            API->>GUARD_O: run_output_guardrails(answer, chunks)
            GUARD_O-->>API: GuardResult{hallucination_score, warnings}
            API->>CACHE: set(query, answer, citations)
            API-->>U: data: {type: done, citations, guardrails}
            API->>LF: score(ragas, cost, latency) [5% sampled, async]
        end
    end
```

---

## 6. Data Model & Storage Architecture

```mermaid
erDiagram
    DOCUMENTS {
        uuid id PK
        text title
        text source_path
        text doc_type
        bigint fingerprint UK
        int chunk_count
        timestamptz created_at
        timestamptz updated_at
    }

    CHUNKS {
        uuid id PK
        uuid document_id FK
        text text
        text header
        int token_count
        jsonb entities
        text_array topics
        text_array key_phrases
        jsonb sparse_tokens
        timestamptz created_at
    }

    QDRANT_POINTS {
        uuid id PK
        float_array dense_vector
        text text
        uuid parent_id FK
        text header
        text_array topics
        text_array entities
        text doc_type
        timestamptz created_at
    }

    REDIS_CACHE {
        string cache_key PK
        text query
        float_array query_vector
        text answer
        jsonb citations
        int ttl_seconds
    }

    DOCUMENTS ||--o{ CHUNKS : "has many"
    CHUNKS ||--|| QDRANT_POINTS : "mirrors (same chunk_id)"
```

---

## 7. Observability & Evaluation Architecture

```mermaid
flowchart LR
    subgraph APP["NEXUS Application"]
        FN["@observe decorated\nfunctions across all layers"]
    end

    subgraph LF["Langfuse Cloud"]
        direction TB
        TRACES["Trace Tree\nroot → spans → sub-spans"]
        SCORES["Scores\nragas_faithfulness\nanswer_relevancy\ncost_usd\nlatency_ms"]
        DASH["Dashboards\nP50/P95 latency\nCost per query\nCache hit rate"]
        ANNOT["Annotation Queue\nHuman review"]
    end

    subgraph EVAL["Evaluation Pipeline"]
        ONLINE["Online Sampling\n5% of queries → RAGAS async"]
        OFFLINE["Offline Regression\nGolden dataset 50+ Q&A\nRun in CI on PR"]
        JUDGE["LLM-as-Judge\nClaude Haiku\nCorrectness · Completeness\nCitation Quality"]
    end

    subgraph CI["CI/CD Gate"]
        GH["GitHub Actions\nfail PR if metrics\nbelow thresholds"]
        THRESHOLDS["Thresholds\nFaithfulness ≥ 0.80\nRelevancy ≥ 0.75\nPrecision ≥ 0.70"]
    end

    APP -->|SDK auto-instrument| LF
    LF --> EVAL
    EVAL --> CI
    CI -->|Block merge| GH
```

---

## 8. Deployment & Infrastructure Topology

```mermaid
graph TB
    subgraph GH["GitHub Repository"]
        CODE["Source Code\nmain branch"]
        CI_WF[".github/workflows/ci.yml\nLint · Test · RAGAS regression"]
        DEPLOY_WF[".github/workflows/deploy.yml\nAuto-deploy on merge to main"]
    end

    subgraph RAILWAY["Railway (Backend)"]
        DOCKER["Docker Container\npython:3.12-slim"]
        FASTAPI["FastAPI + Uvicorn\nport $PORT"]
        MODELS["ML Models (baked in)\nall-MiniLM-L6-v2\nms-marco-MiniLM-L-6-v2\nnli-deberta-v3-small\nen_core_web_sm"]
        SLEEP["Sleep on Idle\n~5min inactivity\n→ cold start ~10s"]
    end

    subgraph VERCEL["Vercel (Frontend)"]
        NEXT["Next.js 15\nApp Router"]
        SSE_PROXY["SSE Proxy Route\n/api/proxy (CORS bridge)"]
    end

    subgraph EXTERNAL["External Managed Services"]
        QDRANT_C["Qdrant Cloud\nFree cluster\n1GB RAM · 4GB disk"]
        SUPA_C["Supabase\nFree PostgreSQL\n500MB"]
        UPSTASH_C["Upstash Redis\nFree\n500K cmd/mo"]
        LF_C["Langfuse Cloud\nFree Hobby\n50K units/mo"]
        OAI["OpenAI API\ngpt-4o-mini\n$0.15/$0.60 per 1M"]
    end

    CODE -->|PR| CI_WF
    CODE -->|merge to main| DEPLOY_WF
    DEPLOY_WF -->|webhook| RAILWAY
    DEPLOY_WF -->|vercel-action| VERCEL
    RAILWAY --> QDRANT_C
    RAILWAY --> SUPA_C
    RAILWAY --> UPSTASH_C
    RAILWAY --> LF_C
    RAILWAY --> OAI
    VERCEL -->|NEXT_PUBLIC_API_URL| RAILWAY
```

---

## 9. Component Dependency Map

```mermaid
graph LR
    subgraph LAYER1["Layer 1: Ingestion"]
        PARSER
        CLEANER
        CHUNKER
        ENRICHER
        EMBEDDER
        UPSERTER
        ING_PIPE["ingestion/pipeline.py"]
    end

    subgraph LAYER2["Layer 2: Retrieval"]
        QP["query_processor"]
        DS["dense_search"]
        SS["sparse_search"]
        FUSION["fusion (RRF)"]
        RERANKER
        SRG["self_rag_gate"]
        RET_PIPE["retrieval/pipeline.py"]
    end

    subgraph LAYER3["Layer 3: Agents"]
        STATE["state.py\nNexusState"]
        ROUTER_A["router.py"]
        SUP["supervisor"]
        RES["researcher"]
        ANA["analyst"]
        VAL["validator"]
        TOOLS_A["tools.py"]
        GRAPH["graph.py\nStateGraph"]
    end

    subgraph LAYER4["Layer 4: Generation"]
        CTX["context_assembler"]
        PROMPTS["prompt_templates"]
        GENERATOR
        CITATIONS["citation_linker"]
    end

    subgraph LAYER5["Layer 5: Cross-cutting"]
        GUARD_I2["input_guard"]
        GUARD_O2["output_guard"]
        CACHE2["semantic_cache"]
        TRACE2["tracing @observe"]
        RAGAS2["ragas_eval"]
    end

    PARSER --> CLEANER --> CHUNKER --> ENRICHER --> EMBEDDER --> UPSERTER
    UPSERTER --> QDRANT_C2[(Qdrant)]
    UPSERTER --> SUPA_C2[(Supabase)]

    QP --> DS & SS
    DS & SS --> FUSION --> RERANKER --> SRG
    SRG --> RET_PIPE

    STATE --> ROUTER_A
    ROUTER_A --> GRAPH
    RET_PIPE --> GRAPH
    SUP & RES & ANA & VAL & TOOLS_A --> GRAPH

    RET_PIPE --> CTX
    CTX --> GENERATOR
    GENERATOR --> CITATIONS

    GUARD_I2 --> GRAPH
    GRAPH --> GUARD_O2
    GUARD_O2 --> CACHE2
    TRACE2 -.->|decorates| LAYER1 & LAYER2 & LAYER3 & LAYER4
```

---

## Version History

| Version | Date | Description |
|---|---|---|
| v1.0.0 | 2026-03-27 | Initial system design — full NEXUS architecture |
