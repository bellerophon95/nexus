# M2 — Document Ingestion Pipeline

> **Release goal:** Upload any PDF/DOCX/HTML document via `POST /api/ingest` and have it parsed, cleaned, chunked, enriched, embedded, and stored in Qdrant + Supabase. Seed corpus ready for retrieval.

## Deliverables

### 1. Parser (`ingestion/parser.py`)
- [ ] `parse_document(file_path, file_type)` — supports PDF, DOCX, HTML, JSON
- [ ] Uses `unstructured.io` (`partition_pdf` hi_res, `partition_docx`, `partition_html`)
- [ ] Extracts tables as separate elements
- [ ] Returns `ParsedDocument(text, tables, metadata, source_path)`

### 2. Cleaner (`ingestion/cleaner.py`)
- [ ] Unicode normalization (NFKC)
- [ ] Whitespace collapse + boilerplate removal (headers, footers, page numbers)
- [ ] SimHash fingerprint generation per document
- [ ] Near-duplicate check against `document_hashes` table in Supabase (Hamming distance < 3)
- [ ] Returns `CleanedDocument(text, fingerprint, is_duplicate, metadata)`

### 3. Semantic Chunker (`ingestion/chunker.py`) ⭐ Critical
- [ ] `SemanticChunker` class using `sentence-transformers` + spaCy sentence segmenter
- [ ] Cosine-distance breakpoints at 90th percentile
- [ ] Min 100 tokens, max 512 tokens per chunk (merge/split enforcement)
- [ ] Tables and code blocks kept as atomic units
- [ ] Each `Chunk` carries `parent_id`, `header`, `text`, `token_count`

### 4. Enricher (`ingestion/enricher.py`)
- [ ] spaCy NER → extract PERSON, ORG, DATE, MONEY entities
- [ ] Zero-shot topic classification (HuggingFace pipeline, or simple heuristics v1)
- [ ] YAKE keyword extraction for `key_phrases`
- [ ] Returns `EnrichedChunk` extending `Chunk`

### 5. Embedder (`ingestion/embedder.py`)
- [ ] Dense: `all-MiniLM-L6-v2` via sentence-transformers, batched (batch_size=64)
- [ ] Sparse: BM25 tokenization → `{token: frequency}` dict stored per chunk
- [ ] Returns `EmbeddedChunk` with `dense_vector` (list[float, 384]) and `sparse_tokens` (dict)

### 6. Upserter (`ingestion/upserter.py`)
- [ ] Upsert dense vectors to Qdrant with metadata payload
- [ ] Insert chunk rows to Supabase `chunks` table
- [ ] Update `document_hashes` table for dedup
- [ ] Basic saga pattern: rollback Qdrant upsert on Supabase failure
- [ ] Returns `UpsertResult(count, status)`

### 7. Pipeline Orchestrator (`ingestion/pipeline.py`)
- [ ] Chains parse → clean → chunk → enrich → embed → upsert
- [ ] Skips duplicate documents gracefully
- [ ] Each stage wrapped in `@observe()` for Langfuse tracing
- [ ] Returns `PipelineResult(document_id, chunk_count, status)`

### 8. Ingest API Endpoint (`api/routes_ingest.py`)
- [ ] `POST /api/ingest` — accepts `UploadFile`
- [ ] Saves to temp path, detects content type
- [ ] Calls `ingestion_pipeline()`, returns `IngestResponse`

### 9. Seed Script (`scripts/seed_documents.py`)
- [ ] Seeds 20–50 documents from a test corpus (e.g. Wikipedia pages, arXiv abstracts, or user-provided docs)
- [ ] Run once after M2 to populate the knowledge base for retrieval testing

### 10. BM25 Index Script (`scripts/build_bm25_index.py`)
- [ ] Creates the `bm25_search` SQL function in Supabase (see M3)
- [ ] Can be re-run to rebuild after mass re-ingestion

## Tests

- [ ] `tests/unit/test_chunker.py` — chunk count, min/max token enforcement, table atomicity
- [ ] `tests/integration/test_ingestion_pipeline.py` — ingest a real PDF, verify Qdrant + Supabase rows

## Additional Dependencies

```toml
unstructured = {extras = ["all-docs"], version = "^0.16"}
sentence-transformers = "^3.4"
spacy = "^3.8"
simhash-pysimhash = "^0.3"
python-multipart = "^0.0.18"
langfuse = "^2.55"
```

Post-install:
```bash
python -m spacy download en_core_web_sm
```

## Acceptance Criteria

- [ ] `POST /api/ingest` with a PDF returns `{"document_id": "...", "chunks_created": N, "status": "success"}`
- [ ] Qdrant collection contains N vectors for the ingested doc
- [ ] Supabase `chunks` table has matching rows
- [ ] Uploading the same document twice → returns `is_duplicate: true`, no new vectors created
- [ ] Langfuse shows a trace with all pipeline stage spans

## Estimated Effort: 2–3 days
