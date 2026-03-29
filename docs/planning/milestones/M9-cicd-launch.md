# M9 — CI/CD & Production Launch

> **Release goal:** Automated GitHub Actions pipeline gates every PR with lint + tests + RAGAS regression. Backend auto-deploys to Railway, frontend auto-deploys to Vercel. Full end-to-end smoke test confirms production is healthy.

## Deliverables

### 1. GitHub Actions — CI (`ci.yml`)

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
        with: { python-version: "3.12" }
      - run: pip install poetry && poetry install
      - run: poetry run ruff check backend/
      - run: poetry run pytest backend/tests/ -v --timeout=60

  eval-regression:
    runs-on: ubuntu-latest
    needs: lint-and-test
    env:
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      QDRANT_URL: ${{ secrets.QDRANT_URL }}
      QDRANT_API_KEY: ${{ secrets.QDRANT_API_KEY }}
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install poetry && poetry install
      - run: poetry run python -m backend.evaluation.regression_runner
          --threshold-faithfulness 0.80
          --threshold-relevancy 0.75
```

### 2. GitHub Actions — Deploy (`deploy.yml`)

```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Trigger Railway deploy
        run: curl -X POST ${{ secrets.RAILWAY_DEPLOY_WEBHOOK }}

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: '--prod'
```

### 3. GitHub Secrets Setup
- [ ] `OPENAI_API_KEY`
- [ ] `ANTHROPIC_API_KEY`
- [ ] `QDRANT_URL` + `QDRANT_API_KEY`
- [ ] `SUPABASE_URL` + `SUPABASE_KEY`
- [ ] `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY`
- [ ] `RAILWAY_DEPLOY_WEBHOOK`
- [ ] `VERCEL_TOKEN` + `VERCEL_ORG_ID` + `VERCEL_PROJECT_ID`

### 4. Ruff Linting Config (`pyproject.toml`)

```toml
[tool.ruff]
line-length = 100
select = ["E", "F", "I", "UP"]
ignore = ["E501"]
```

### 5. Production Smoke Tests
- [ ] `scripts/smoke_test.py` — hits production Railway URL with 3 known-good queries
  - Confirms `GET /api/health` returns 200
  - Confirms `POST /api/query` returns a streaming response with citations
  - Confirms `POST /api/ingest` with a small test PDF succeeds
- [ ] Run smoke test as final CI step after Railway deploy

### 6. Railway Configuration
- [ ] `railway.json` or Railway dashboard config:
  - Build command: `pip install poetry && poetry install --no-dev`
  - Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
  - Health check: `GET /api/health`
  - Sleep on idle: enabled (Hobby plan)

### 7. Vercel Configuration
- [ ] `vercel.json` in `frontend/`:
  ```json
  { "framework": "nextjs", "buildCommand": "npm run build", "outputDirectory": ".next" }
  ```
- [ ] Env vars set in Vercel dashboard: `NEXT_PUBLIC_API_URL`

### 8. README Update
- [ ] Update root `README.md` with:
  - Live demo URL (frontend Vercel link)
  - API base URL (Railway link)
  - Architecture diagram (ASCII from NEXUS_README)
  - Quick start (clone → set env → `docker compose up`)
  - Link to `docs/planning/milestones/` for development history

## Acceptance Criteria

- [ ] Opening a PR triggers CI — both `lint-and-test` and `eval-regression` jobs run
- [ ] A broken unit test blocks the PR from merging
- [ ] A RAGAS regression (metrics below thresholds) blocks the PR from merging
- [ ] Merging to `main` auto-deploys backend to Railway and frontend to Vercel within 5 minutes
- [ ] `smoke_test.py` passes against production URLs
- [ ] Live demo accessible at `https://nexus-<hash>.vercel.app` with no console errors

## Post-Launch Validation

Run manually after M9 deploy:
```bash
# Health check
curl https://nexus-api.up.railway.app/api/health

# Query
curl -X POST https://nexus-api.up.railway.app/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is semantic chunking?", "session_id": "test-001"}'

# Check Langfuse trace appears
# Check Vercel frontend loads and streams token response
```

## Estimated Effort: 1–2 days
