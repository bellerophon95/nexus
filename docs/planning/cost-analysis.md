# NEXUS — Detailed Cost Analysis

> Verified pricing as of March 2026. All free-tier limits validated against live sources.

---

## Infrastructure Cost Table

| Service | Role | Plan | Free Limit | Overage Cost | Est. Monthly |
|---|---|---|---|---|---|
| **Railway** | FastAPI backend + model serving | Hobby | $5 usage credit included | Pay-per-resource after $5 credit | **$5.00** |
| **Vercel** | Next.js frontend | Free (Hobby) | 100K serverless invocations/mo | $0.40 per 1M extra | **$0.00** |
| **Qdrant Cloud** | Vector DB (dense search) | Free | 1GB RAM, 4GB disk, ~1M vectors @ 384d | Paid cluster starts ~$35/mo | **$0.00** |
| **Supabase** | PostgreSQL (chunks + BM25) | Free | 500MB DB, 50K MAU | Pro plan $25/mo | **$0.00** |
| **Upstash Redis** | Semantic cache + pub/sub | Free | 500K commands/mo, 256MB | $0.20 per 100K extra commands | **$0.00** |
| **Langfuse Cloud** | Tracing + eval scores | Hobby Free | 50K usage units/mo (traces+observations+scores) | Core plan $59/mo | **$0.00** |

**Fixed infrastructure subtotal: $5.00/month**

---

## LLM Inference Cost Modeling

### Model Pricing (March 2026, verified)

| Model | Input | Output | Use case in NEXUS |
|---|---|---|---|
| `gpt-4o-mini` | $0.15 / 1M tokens | $0.60 / 1M tokens | Main query generation, query expansion, router fallback |
| `claude-haiku-4-5` | $1.00 / 1M tokens | $5.00 / 1M tokens | LLM-as-Judge evaluation (optional) |
| `claude-3-5-haiku` | $0.80 / 1M tokens | $4.00 / 1M tokens | Alternative to Haiku 4.5 (cheaper) |

> **Design choice:** We default to `gpt-4o-mini` for all pipeline calls. Claude Haiku is only used for the LLM-as-Judge evaluator, which runs on 5% of production traffic.

### Per-Query Token Budget Breakdown

Each query through the NEXUS pipeline consumes tokens across several LLM calls:

| Step | Model | Input Tokens | Output Tokens | Notes |
|---|---|---|---|---|
| Query expansion | gpt-4o-mini | ~200 | ~100 | Adds related terms to query |
| Query router (fallback) | gpt-4o-mini | ~150 | ~10 | Only on classifier failure |
| HyDE generation (Tier 3 only) | gpt-4o-mini | ~200 | ~300 | ~30% of queries |
| Supervisor decision (Tier 3) | gpt-4o-mini | ~500 | ~20 | Per agent loop iteration (avg 2x) |
| Analyst synthesis (Tier 3) | gpt-4o-mini | ~6,000 | ~600 | Context + synthesis |
| Answer generation (all tiers) | gpt-4o-mini | ~8,500 | ~500 | System prompt + 8K context + response |
| LLM-as-Judge (5% of queries) | claude-3-5-haiku | ~2,000 | ~100 | Sampled evaluation |

### Tier-Weighted Average Tokens per Query

Assuming traffic distribution: **60% Tier 1/2, 40% Tier 3**

| Traffic Segment | % | Input tokens | Output tokens |
|---|---|---|---|
| Tier 1 (direct) | 20% | 500 | 300 |
| Tier 2 (single-step RAG) | 40% | 9,000 | 600 |
| Tier 3 (agentic) | 40% | 17,000 | 1,600 |

**Weighted average per query:**
- Input: `(0.20 × 500) + (0.40 × 9,000) + (0.40 × 17,000)` = **10,500 tokens**
- Output: `(0.20 × 300) + (0.40 × 600) + (0.40 × 1,600)` = **940 tokens**

### Cost per Query (gpt-4o-mini)

```
Input:  10,500 × ($0.15 / 1,000,000) = $0.001575
Output:    940 × ($0.60 / 1,000,000) = $0.000564
                                      ──────────
Per query subtotal (before cache):    $0.002139  (~$0.0021)
```

**With 95% cache hit rate** (semantic cache is very effective for repeated/similar queries):
```
Effective per-query cost = $0.0021 × (1 - 0.95 cache hit) = $0.000107/query
+ Cache lookup cost (embedding): negligible (CPU, free on Railway compute)
```

> **Realistic cache hit rate note:** 95% is for a mature deployment. Early-stage (first month) expect 10–30% cache hit rate.

### LLM Cost at Various Query Volumes (no cache / new queries)

| Monthly Queries | Raw LLM Cost | With 40% Cache Hit | With 80% Cache Hit |
|---|---|---|---|
| 100 | $0.21 | $0.13 | $0.04 |
| 500 | $1.07 | $0.64 | $0.21 |
| 1,000 | $2.14 | $1.28 | $0.43 |
| 2,000 | $4.28 | $2.57 | $0.86 |
| 5,000 | $10.70 | $6.42 | $2.14 |

---

## Free Tier Limit Analysis

### Qdrant Cloud (384-dimensional vectors)

```
Max vectors: ~1M @ 384d (well within free tier)
Expected corpus: 1,000 docs × ~50 chunks = 50,000 vectors
Vector storage: 50,000 × 384 × 4 bytes = ~74MB  ← well under 4GB disk limit
RAM usage for HNSW index: ~50,000 × 384 × 8 bytes ≈ ~150MB ← under 1GB RAM
```
**✅ Free tier sufficient for up to ~300K chunks / ~6,000 documents**

### Supabase (PostgreSQL)

```
Chunk row size: ~2KB per row (text + metadata)
50,000 chunks × 2KB = ~100MB ← well under 500MB free limit
GIN index overhead: ~20MB additional
```
**✅ Free tier sufficient for up to ~200K chunks**

### Upstash Redis (Semantic Cache)

```
Cache operations per query: ~2–5 commands (GET keys, GET value, SET on miss)
At 1,000 queries/month: ~4,000 commands ← well under 500K/month free limit
At 10,000 queries/month: ~40,000 commands ← still under free limit
Cache entry size: ~2KB per entry (query vector + answer + citations)
At 10,000 unique queries: ~20MB ← under 256MB limit
```
**✅ Free tier sufficient for up to ~100K queries/month**

### Langfuse (Tracing Units)

```
Traces per query: 1 root trace
Spans per query: ~12-15 (router, dense_search, sparse_search, reranker, 
                          self_rag, assemble_context, generate, guardrails, cache)
Scores per query: 2-4 (RAGAS faithfulness, relevancy; LLM-judge on 5%)
Units per query: ~18 usage units
At 1,000 queries/month: ~18,000 units ← under 50K limit
At 2,700 queries/month: ~48,600 units ← approaching limit
```
**⚠️ Langfuse free tier supports ~2,500 queries/month. Beyond that, consider self-hosting (free, via Docker).**

### Railway (Compute)

```
$5 credit included in Hobby plan subscription
FastAPI + ML models (sentence-transformers, cross-encoder, NLI model):
  Expected idle RAM: ~1.5–2GB (models loaded in memory)
  Railway RAM pricing: ~$0.000231/GB/min
  Monthly idle cost: 2GB × 43,200 min/mo = $20 ← EXCEEDS $5 credit

IMPORTANT: Enable Railway "Sleep on Idle" to avoid overage:
  - Service sleeps after ~5 min inactivity
  - Cold start: ~8–15 seconds (acceptable for portfolio/dev use)
  - Active hours estimate: 4 hrs/day × 30 days = 7,200 min/mo
  - Cost at 2GB: 2GB × 7,200 min × $0.000231 = $3.33 ← within $5 credit
```
**✅ Free (within $5 credit) with Sleep on Idle enabled. Cold starts are the trade-off.**

---

## Total Monthly Cost Summary

### Scenario A: Early Stage (< 500 unique queries/month)

| Item | Cost |
|---|---|
| Railway (Hobby, sleep on idle) | $5.00 |
| All other infra (Vercel, Qdrant, Supabase, Upstash, Langfuse) | $0.00 |
| LLM inference (500 queries × $0.0021, ~20% cache hit) | $0.84 |
| **Total** | **$5.84/mo** |

### Scenario B: Active Portfolio / Demo (1,000–2,000 queries/month)

| Item | Cost |
|---|---|
| Railway (sleep on idle, ~4 active hrs/day) | $5.00 |
| LLM inference (1,500 avg queries × $0.0021, ~50% cache hit) | $1.58 |
| Langfuse (approaching free limit — monitor) | $0.00 |
| **Total** | **$6.58/mo** |

### Scenario C: High Usage (5,000 queries/month)

| Item | Cost |
|---|---|
| Railway (Hobby, may exceed $5 credit ~ +$2–3) | $7.00 |
| LLM inference (5,000 queries × $0.0021, ~70% cache hit) | $3.15 |
| Langfuse (self-host via Docker on Railway, no extra cost) | $0.00 |
| **Total** | **$10.15/mo** |

---

## Verdict

> ✅ **NEXUS comfortably fits within the $3–15/month target across all realistic usage scenarios.**

The original README estimate of **$3–15/month** is **accurate and slightly conservative** — real costs may be lower due to:
1. `gpt-4o-mini` being cheaper than expected at $0.15/1M input tokens
2. Semantic caching absorbing repeated/similar queries effectively
3. Railway's sleep-on-idle keeping compute costs inside the $5 credit

**Key risk to monitor:** Langfuse free tier caps at ~2,500 queries/month. Mitigation: self-host Langfuse on Railway once traffic exceeds this (zero additional cost, uses existing Railway plan).

**Upgrade triggers (when to graduate from free tiers):**
- **Qdrant** → upgrade when corpus exceeds ~300K chunks
- **Supabase** → upgrade when DB exceeds 400MB
- **Langfuse** → self-host when queries exceed 2,500/month
- **Railway** → upgrade to Pro ($20/mo) when always-on latency matters more than cost
