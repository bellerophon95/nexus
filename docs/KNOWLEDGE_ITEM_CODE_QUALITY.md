# Nexus Code Quality Standard: Ruff 

To prevent CI/CD failures on AWS/GitHub Actions, the following checks **MUST** be run before every push to `main`.

### 🧹 Formatting Requirement
Project Nexus uses `ruff` for both linting and formatting. 

#### Mandatory Pre-Push Command:
```bash
ruff format backend/ && ruff check --fix backend/
```

### 📋 CI/CD Gating
The GitHub Action `.github/workflows/aws-deploy.yml` will fail if:
- Any file in `backend/` would be reformatted by `ruff format --check`.
- Any critical lint errors exist.

### 🧩 Applied Fixes (2026-04-01)
- Stabilized `backend/api/routes_query.py` formatting after SSE heartbeat integration.
- Ensured long-running async loops maintain correct indentation for better readability and protocol stability.
