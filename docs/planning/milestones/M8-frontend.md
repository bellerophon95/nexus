# M8 — Frontend + Semantic Cache

> **Release goal:** A polished Next.js chat interface with real-time SSE streaming, citation cards, agent activity sidebar, and document upload. Semantic caching reduces repeated query latency and LLM cost.

## Deliverables

### Part A — Semantic Cache (`cache/semantic_cache.py`)

- [ ] `SemanticCache(redis_client, embed_model, similarity_threshold=0.95, ttl=86400)`
- [ ] `get(query)` — embed query, scan cached query vectors, return hit if cosine ≥ threshold
- [ ] `set(query, answer, citations)` — embed + store in Upstash Redis with TTL
- [ ] `invalidate_for_documents(doc_ids)` — flush cache entries for re-ingested docs
- [ ] Cache key format: `cache:query:{hash(query)}`
- [ ] Wire into `routes_query.py`: check cache first, store on miss
- [ ] `@observe(name="cache_lookup")` + `@observe(name="cache_store")` traced

### Part B — Next.js Frontend

#### Project Setup
- [ ] `npx create-next-app@latest frontend --typescript --tailwind --app`
- [ ] Install: `shadcn/ui`, `lucide-react`
- [ ] Configure `NEXT_PUBLIC_API_URL` env var pointing to Railway backend

#### Core Components

**`ChatInterface.tsx`**
- [ ] Message history displayed in scrollable container
- [ ] Input bar with send button + keyboard shortcut (Enter)
- [ ] SSE streaming connection via browser `EventSource`
- [ ] Renders tokens in real-time as they arrive
- [ ] Shows loading skeleton while waiting for first token
- [ ] Reconnects on connection drop

**`MessageBubble.tsx`**
- [ ] User and assistant message variants
- [ ] Renders markdown (use `react-markdown` + `remark-gfm`)
- [ ] Inline `[Source N]` citation markers are clickable → opens `CitationCard`

**`CitationCard.tsx`**
- [ ] Expandable panel showing source header + text snippet
- [ ] Displays chunk metadata (doc type, topic)
- [ ] Collapses by default, expands on click

**`AgentActivity.tsx`**
- [ ] Side panel or collapsible drawer
- [ ] Shows real-time agent steps as SSE `agent_step` events arrive
- [ ] Step list: `[icon] Researcher: searching vectors...`, `[icon] Analyst: synthesizing...`
- [ ] Fades out after answer completes

**`UploadPanel.tsx`**
- [ ] Drag-and-drop file zone (accept PDF, DOCX, HTML)
- [ ] Calls `POST /api/ingest` with `FormData`
- [ ] Progress indicator during upload
- [ ] Success state: "Document indexed — X chunks created"
- [ ] Error state with retry

**`MetricsPanel.tsx`** (optional, togglable)
- [ ] Shows quality metrics from `done` SSE event:
  - Hallucination score (color-coded: green/yellow/red)
  - Guardrail status (passed/warnings)
  - Tier used (direct / rag / agentic)
  - Response latency

#### App Pages

**`app/page.tsx`**
- [ ] Main layout: sidebar (upload + history) + main chat area
- [ ] Session ID generated per browser session (`crypto.randomUUID()`)
- [ ] Chat history stored in component state (no persistence in M8)

**`app/api/proxy/route.ts`** (optional)
- [ ] Next.js route handler as CORS proxy for SSE (if needed)

#### SSE Consumption Pattern
```typescript
const es = new EventSource(`${API_URL}/api/query?q=${encodeURIComponent(query)}`);
es.onmessage = (e) => {
  const data = JSON.parse(e.data);
  if (data.type === 'token') appendToken(data.content);
  if (data.type === 'agent_step') addAgentStep(data.tool, data.agent);
  if (data.type === 'done') { setCitations(data.citations); es.close(); }
};
```

## Design Spec

- Dark mode default (system preference toggle)
- Font: **Inter** (Google Fonts)
- Color palette: deep slate backgrounds, electric blue accents, white text
- Glassmorphism panels for citations and agent activity
- Micro-animations: typing cursor, agent step fade-in, citation card expand

## Acceptance Criteria

### Cache
- [ ] Identical query returns cached response within 50ms (vs ~2s uncached)
- [ ] Paraphrased queries with cosine ≥ 0.95 hit the cache
- [ ] Re-ingesting a document invalidates cache — next query retrieves fresh results
- [ ] Cache hit/miss visible in Langfuse trace

### Frontend
- [ ] Chat UI loads and renders correctly in Chrome, Firefox, Safari
- [ ] SSE tokens stream in real-time without buffering artifacts
- [ ] Uploading a PDF successfully ingests it (and it's queryable immediately)
- [ ] Citation cards expand/collapse correctly
- [ ] Agent activity panel populates for Tier 3 queries
- [ ] Mobile layout is usable (responsive)

## Estimated Effort: 2–3 days
