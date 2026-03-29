# Milestone 10: Performance Tuning & Advanced UX

> Finalizing the system for high-scale, high-fidelity use cases with non-blocking ingestion and enhanced agent observability.

## 🎯 Outcomes
- [ ] **Async Ingestion**: Document uploads are processed in the background; UI shows progress.
- [ ] **Agent Step Visualization**: Frontend displays granular agent thought processes ("Thinking...", "Searching...").
- [ ] **Adaptive Routing Tuning**: Refined logic for Simple vs RAG vs Agentic tiers.
- [ ] **Final System Audit**: Run a full RAGAS suite on 100+ queries to confirm production stability.

## 🛠 Features

### 1. Non-Blocking Ingestion
- Use FastAPI `BackgroundTasks` for the `POST /ingest` endpoint.
- Implement a status polling endpoint `GET /ingest/status/{task_id}`.
- Update frontend to show a progress bar for document indexing.

### 2. Enhanced Agent Observability (UI)
- Update SSE stream to include `activity_log` objects.
- Frontend `AgentActivity` component now shows real-time updates as LangGraph nodes execute.

### 3. Router Calibration
- Review Langfuse traces to find "Simple" queries that should have been "RAG" (and vice versa).
- Update the `router.py` prompt/model for better 3-tier classification accuracy.

### 4. Production Smoke Test 2.0
- Expand `scripts/smoke_test.py` to include a full "Ingest -> Wait -> Query -> Verify" loop.
- Automate this in the CI/CD pipeline as a post-deploy step.

---

## 🏗 Success Criteria
- [ ] `POST /ingest` returns in <500ms (processing happens in background).
- [ ] UI displays "Researcher found 5 documents" before the answer starts.
- [ ] 0% failure rate on a 10-query smoke test suite.
