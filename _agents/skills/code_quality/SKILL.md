---
name: Nexus Pre-Push Linting Standard
description: Mandatory pre-push formatting and linting rules for the Project Nexus repository.
---

# Pre-Push Linting Standard

To maintain production stability and prevent CI/CD failures on GitHub Actions, the following standard **MUST** be applied before every `git push` command.

## 🛠 Required Environment
All linting operations must be performed within the project's virtual environment:
```bash
source .venv/bin/activate
```

## 🧹 Formatting & Linting Command
The following composite command must be executed and verified (success exit code) before any commit/push that touches the `backend/` directory:

```bash
ruff format backend/ && ruff check --fix backend/
```

## 📋 Gating Rules
1. **Never propose a push** if `ruff format --check backend/` fails.
2. **Always include** the linting result in your task updates.
3. **Check for regressions** specifically in `backend/api/routes_ingest.py` and `backend/api/routes_query.py` after complex logic changes.

## 🔍 Verification
After running the fix command, always verify the clean state:
```bash
ruff format --check backend/
```
