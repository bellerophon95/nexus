# M3 — Hybrid Retrieval Pipeline

> **Release goal:** Given any text query, return the top-5 most relevant chunks using dense vector search + BM25 keyword search, fused via RRF, reranked by a cross-encoder, and validated by a Self-RAG relevance gate.

## Deliverables

### 1. Supabase BM25 Function
- [ ] Deploy `bm25_search` SQL function to Supabase:
  ```sql
  CREATE OR REPLACE FUNCTION bm25_search(
      search_query TEXT,
      filter_clause TEXT DEFAULT 'TRUE',
      result_limit INTEGER DEFAULT 50
  ) RETURNS TABLE(id UUID, text TEXT, rank REAL) ...
  ```
- [ ] Verify with manual `SELECT` in Supabase SQL editor

### 2. Dense Search (`retrieval/dense_search.py`)
- [ ] `dense_search(query_vector, filters, top_k=50)` 
- [ ] Qdrant `search()` with `score_threshold=0.3`
- [ ] Supports optional `MetadataFilters` (topic, doc_type)
- [ ] Returns `list[SearchResult]`

### 3. Sparse / BM25 Search (`retrieval/sparse_search.py`)
- [ ] `sparse_search(query, filters, top_k=50)`
- [ ] Calls Supabase `bm25_search` RPC
- [ ] Returns `list[SearchResult]` with `rank` as score

### 4. Reciprocal Rank Fusion (`retrieval/fusion.py`)
- [ ] `reciprocal_rank_fusion(result_sets, k=60, top_n=20)`
- [ ] Merges any number of ranked lists
- [ ] Returns deduplicated, RRF-scored `list[SearchResult]`

### 5. Cross-Encoder Reranker (`retrieval/reranker.py`)
- [ ] `Reranker` class, loads `cross-encoder/ms-marco-MiniLM-L-6-v2`
- [ ] `rerank(query, results, top_k=5)` — scores (query, chunk) pairs jointly
- [ ] Returns top-k by `rerank_score`

### 6. Self-RAG Relevance Gate (`retrieval/self_rag_gate.py`)
- [ ] `SelfRAGGate(threshold=0.7, max_retries=2)`
- [ ] Uses `cross-encoder/nli-deberta-v3-small` — P(entailment) as relevance score
- [ ] If no chunk passes threshold: rewrites query via LLM and re-retrieves (max 2 retries)
- [ ] Fallback: return best-effort top-3 if still no match

### 7. Query Processor (`retrieval/query_processor.py`)
- [ ] `process_query(query, tier)` — query expansion via LLM (always)
- [ ] HyDE (Hypothetical Document Embedding) — for `tier=agentic` only
- [ ] Query decomposition into sub-queries — for `tier=agentic` only
- [ ] Returns `ProcessedQuery(original, expanded, sub_queries, hyde_vector)`

### 8. Full Retrieval Pipeline (`retrieval/pipeline.py`)
- [ ] `retrieval_pipeline(query, filters)` — chains all steps
- [ ] Dense + sparse search run in parallel (`asyncio.gather`)
- [ ] Returns `RetrievalResult(chunks, dense_count, sparse_count, fused_count)`

## Tests

- [ ] `tests/unit/test_fusion.py` — RRF score correctness, deduplication
- [ ] `tests/unit/test_reranker.py` — reranking order validation with known pairs
- [ ] `tests/unit/test_self_rag_gate.py` — relevance above/below threshold, retry behavior
- [ ] `tests/integration/test_retrieval_pipeline.py` — query against seeded corpus, verify top chunk relevance manually

## Acceptance Criteria

- [ ] `retrieval_pipeline("what is X")` returns ≤5 chunks, sorted by relevance
- [ ] Running on seeded corpus: top result is visually relevant to the query for at least 80% of test queries
- [ ] Dense and sparse searches complete in parallel (verify via Langfuse trace timing)
- [ ] Self-RAG gate triggers at least once during testing when a clearly off-topic query is used
- [ ] All retrieval stages visible as spans in Langfuse

## Estimated Effort: 2–3 days
