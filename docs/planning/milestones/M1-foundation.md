# M1 — Foundation & Infrastructure

> **Release goal:** A deployable FastAPI skeleton connected to all external services, with a working `/health` endpoint live on Railway.

## Deliverables

### 1. Project Scaffolding
- [ ] `pyproject.toml` — Poetry deps (fastapi, uvicorn, pydantic-settings, langfuse, qdrant-client, supabase, upstash-redis)
- [ ] `.env.example` — all required env vars documented
- [ ] `.gitignore` — exclude `.env`, model caches, `__pycache__`
- [ ] `Dockerfile` — production image (python:3.12-slim, system deps for unstructured + spaCy)
- [ ] `docker-compose.yml` — local dev stack

### 2. Application Config
- [ ] `backend/config.py` — `pydantic-settings` `Settings` class with all env vars
- [ ] `backend/main.py` — FastAPI app with lifespan (startup/shutdown), CORS middleware
- [ ] `backend/api/routes_health.py` — `GET /api/health` returns `{"status": "ok", "version": "..."}` 
- [ ] `backend/api/middleware.py` — rate limiting, error handler, request ID injection

### 3. External Service Provisioning
- [ ] **Qdrant Cloud** — create free cluster, create `nexus_chunks` collection (384d, COSINE, HNSW m=16)
- [ ] **Supabase** — new project, run schema migration (tables: `documents`, `chunks`, `document_hashes`)
- [ ] **Upstash Redis** — create free database
- [ ] **Langfuse Cloud** — new project, grab public/secret keys
- [ ] Populate `.env` with all real credentials

### 4. Deploy Skeleton
- [ ] Connect GitHub repo to Railway
- [ ] Set all env vars in Railway dashboard
- [ ] Confirm `GET https://nexus-api.up.railway.app/api/health` returns 200

## Acceptance Criteria

- [ ] `/api/health` returns `{"status": "ok"}` from Railway URL
- [ ] All infra services are reachable from the deployed app (verified in startup logs)
- [ ] `docker compose up` runs the app locally without errors
- [ ] `.env.example` covers every required variable

## Key Dependencies

```toml
fastapi = "^0.115"
uvicorn = {extras = ["standard"], version = "^0.34"}
pydantic = "^2.10"
pydantic-settings = "^2.7"
qdrant-client = "^1.12"
supabase = "^2.13"
upstash-redis = "^1.2"
langfuse = "^2.55"
```

## Supabase Schema (run in SQL editor)

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    source_path TEXT,
    doc_type TEXT,
    fingerprint BIGINT UNIQUE,
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    header TEXT,
    token_count INTEGER,
    entities JSONB DEFAULT '[]',
    topics TEXT[] DEFAULT '{}',
    key_phrases TEXT[] DEFAULT '{}',
    sparse_tokens JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_chunks_text_search ON chunks USING gin(to_tsvector('english', text));
CREATE INDEX idx_chunks_topics ON chunks USING gin(topics);
CREATE INDEX idx_chunks_document_id ON chunks(document_id);
```

## Estimated Effort: 1–2 days
