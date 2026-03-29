# M7 — Observability & Evaluation

> **Release goal:** Complete Langfuse tracing across all pipeline stages, RAGAS metrics computed for every response sample, a golden dataset with 50+ Q&A pairs, and a CI regression test that blocks deploys on quality regressions.

## Deliverables

### 1. Langfuse Tracing (`observability/tracing.py`)
- [ ] Initialize `Langfuse` client with env keys
- [ ] `trace_query(query, session_id)` — start root trace per user request
- [ ] Confirm `@observe()` decorators are applied to **every** named function across all layers:
  - Ingestion: `parse_document`, `clean_document`, `semantic_chunk`, `enrich_chunk`, `embed_chunks`, `upsert_chunks`
  - Retrieval: `process_query`, `dense_search`, `sparse_search`, `cross_encoder_rerank`, `self_rag_gate`
  - Agents: `supervisor`, `researcher_agent`, `analyst_agent`, `validator_agent`, `route_query`
  - Generation: `assemble_context`, `generate_answer`
  - Guardrails: `input_guardrails`, `output_guardrails`
  - Cache: `cache_lookup`, `cache_store`

### 2. Cost Tracker (`observability/cost_tracker.py`)
- [ ] `CostTracker` class — tracks per-model token usage (prompt + completion)
- [ ] Aggregates cost per trace using `gpt-4o-mini` / `claude-haiku` pricing tables
- [ ] Pushes cost metadata to Langfuse trace via `langfuse.score(name="total_cost_usd", ...)`

### 3. Alerting (`observability/alerting.py`)
- [ ] `check_drift(metric, value, baseline, threshold)` — detects anomalies
- [ ] Fires webhook alert (Slack / Discord) when RAGAS metrics drop > 10% from baseline
- [ ] Alert on `avg_latency_ms` exceeding 10s
- [ ] Configurable via `ALERT_WEBHOOK_URL` env var (no-op if not set)

### 4. RAGAS Evaluation (`evaluation/ragas_eval.py`)
- [ ] `evaluate_response(query, answer, contexts, ground_truth?)` 
- [ ] Metrics: `faithfulness`, `answer_relevancy`, `context_precision`, (`context_recall` if ground truth provided)
- [ ] Pushes scores to Langfuse: `langfuse.score(name="ragas_faithfulness", ...)`
- [ ] Async — does not block streaming response

### 5. LLM-as-Judge (`evaluation/llm_judge.py`)
- [ ] `llm_judge_evaluate(question, answer, context)` via Claude Haiku
- [ ] Scores: Correctness, Completeness, Citation Quality, Conciseness (1–5)
- [ ] Returns `dict[str, int]`
- [ ] Used in online evaluation sampling

### 6. Golden Dataset (`evals/golden_dataset.json`)
- [ ] 50+ Q&A pairs with `question`, `ground_truth` answer, optionally `expected_sources`
- [ ] Cover all tiers: Tier 1 simple, Tier 2 factoid RAG, Tier 3 multi-hop
- [ ] Generated from the seeded document corpus (M2)
- [ ] Format: `[{"question": "...", "ground_truth": "...", "tier": "rag"}]`

### 7. Regression Runner (`evaluation/regression_runner.py`)
- [ ] `run_regression(thresholds)` — loads golden dataset, runs full NEXUS pipeline on each item
- [ ] Aggregates RAGAS scores, fails with exit code 1 if any metric < threshold
- [ ] Default thresholds: `faithfulness ≥ 0.80`, `answer_relevancy ≥ 0.75`, `context_precision ≥ 0.70`
- [ ] CLI: `python -m backend.evaluation.regression_runner --threshold-faithfulness 0.80`

### 8. Online Evaluation Sampling
- [ ] In `routes_query.py`: 5% of production requests sampled asynchronously via `asyncio.create_task()`
- [ ] Runs `evaluate_response()` in background without affecting response latency

## Tests

- [ ] `tests/evaluation/test_regression.py` — runs regression on a 10-item subset of golden dataset, asserts metrics above threshold

## Acceptance Criteria

- [ ] Every production query generates a Langfuse trace with ≥5 nested spans (router, retrieval, reranker, generation, guardrails)
- [ ] Token cost is tracked per query and visible in Langfuse as a score
- [ ] Regression runner passes on the seeded corpus with default thresholds
- [ ] Intentionally bad retrieval (mock low-quality chunks) causes regression runner to fail — regression gate works
- [ ] CI workflow (`eval-regression` job) runs on PR and posts result as a check

## CI Integration

Add to `.github/workflows/ci.yml`:
```yaml
eval-regression:
  runs-on: ubuntu-latest
  needs: lint-and-test
  steps:
    - run: poetry run python -m backend.evaluation.regression_runner \
        --threshold-faithfulness 0.80 \
        --threshold-relevancy 0.75
```

## Estimated Effort: 2–3 days
