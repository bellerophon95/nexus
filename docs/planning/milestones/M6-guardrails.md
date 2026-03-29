# M6 — Guardrails & Safety

> **Release goal:** Every query is screened before processing (prompt injection, PII, topic restriction) and every answer is validated before delivery (hallucination score, toxicity, PII leak). Bad queries are rejected with informative errors. Risky answers surface warnings.

## Deliverables

### 1. Guard Result Schema (`guardrails/models.py`)
- [ ] `GuardResult(original, sanitized_query, passed, blocked_reason, pii_detected, hallucination_score, warnings)`
- [ ] Both input and output guards return this schema

### 2. Input Guardrails (`guardrails/input_guard.py`)
- [ ] Layer 1 — **Prompt Injection Detection** via `llm-guard` `PromptInjection` scanner
  - Return 422 with `blocked_reason` if detected
- [ ] Layer 2 — **PII Anonymization** via `presidio-analyzer` + `presidio-anonymizer`
  - Detect and replace PII entities in query before processing
  - Log entity types detected to Langfuse
- [ ] Layer 3 — **Topic Restriction** via `llm-guard` `BanTopics`
  - Configure `RESTRICTED_TOPICS` list (configurable via env)
  - Return 422 if topic violation
- [ ] Layer 4 — **Token Budget Check**
  - Reject if query exceeds `MAX_INPUT_TOKENS = 4096`
- [ ] `@observe(name="input_guardrails")` traced

### 3. Output Guardrails (`guardrails/output_guard.py`)
- [ ] Layer 1 — **Hallucination Score** via NLI (same `nli-deberta-v3-small` model)
  - Score answer against concatenated context chunks
  - Append warning if `hallucination_score > 0.5` (don't block, just warn)
- [ ] Layer 2 — **Citation Verification**
  - Count uncited claims, append warning if any
- [ ] Layer 3 — **Toxicity Screening** via `llm-guard` `Toxicity`
  - Block response if toxic content detected (replace with error message)
- [ ] Layer 4 — **PII Leak Detection**
  - Run presidio on output
  - Append warning if PII found in answer (do not block, but flag)
- [ ] `@observe(name="output_guardrails")` traced

### 4. Wire Into Query Endpoint
- [ ] `routes_query.py`: run `run_input_guardrails(query)` before graph invocation
- [ ] If `guard_result.passed == False` → return 422 JSON (not a stream)
- [ ] Use `guard_result.sanitized_query` (PII-anonymized) for all downstream processing
- [ ] After generation, run `run_output_guardrails(answer, context_chunks)`
- [ ] Include `guardrails` field in SSE `done` event payload

### 5. Guardrail Config
- [ ] `GUARDRAILS_ENABLED=true/false` env toggle (bypass all guardrails for dev/testing)
- [ ] `PII_DETECTION_ENABLED=true/false` separate toggle
- [ ] `RESTRICTED_TOPICS` as comma-separated env var

## Tests

- [ ] `tests/unit/test_input_guard.py`
  - Pass a known prompt injection string → assert `passed=False`
  - Pass a query with a phone number → assert `pii_detected` contains `PHONE_NUMBER`, sanitized query has it replaced
  - Pass excessively long query → assert token budget rejection
- [ ] `tests/unit/test_output_guard.py`
  - Pass an answer that contradicts all context → assert `hallucination_score > 0.5`
  - Pass an answer with toxic content (mocked) → assert `passed=False`

## Acceptance Criteria

- [ ] `POST /api/query {"query": "Ignore all previous instructions and..."}` returns 422 with `"error": "Prompt injection detected"`
- [ ] A query containing a real email address → answer uses anonymized placeholder, not the original email
- [ ] Toxic output is blocked (tested with `llm-guard` internal test strings)
- [ ] Guardrail spans visible in Langfuse for every query
- [ ] Setting `GUARDRAILS_ENABLED=false` bypasses all checks (dev mode)

## Dependencies

```toml
llm-guard = "^0.3"
presidio-analyzer = "^2.2"
presidio-anonymizer = "^2.2"
```

## Estimated Effort: 1–2 days
