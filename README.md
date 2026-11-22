# CloudPilot

ML-based CPU resource allocation engine for cloud workloads.

## Overview

CloudPilot is a final-year B.Tech project focusing on intelligent CPU resource allocation for multi-service cloud workloads. It uses machine learning to predict workload demands and dynamically optimize CPU allocation to minimize throttling while maximizing host CPU utilization.

The architecture consists of:
- Backend: Python 3.11+ FastAPI service deployed on Render.
- Frontend: React + Vite web dashboard deployed on Vercel (planned).
- Storage: Supabase Postgres for workload trace and allocation logs (planned).

Note: Only CPU resources are modeled in this phase of the project.

## Project Structure

```
cloudpilot/
  .github/workflows/ci.yml    # CI pipeline for linting, testing, and secret scanning
  .env.example                # Example configuration template
  .gitignore                  # Git ignore rules
  .gitleaks.toml              # Secret detection rules
  .pre-commit-config.yaml     # Pre-commit git hooks
  render.yaml                 # Render deployment blueprint
  backend/
    app/                      # FastAPI application code
    tests/                    # Pytest test suite
    Dockerfile                # Container image definition
    pyproject.toml            # Tool configuration (Ruff, Pytest)
    requirements.txt          # Production dependencies
    requirements-dev.txt      # Development dependencies
  docs/                       # Project documentation
  frontend/                   # React + Vite dashboard
  scripts/
    make_env.py               # Local environment file generator
```

## Environment Variables

| Variable | Type | Default | Required in Production | Description |
| :--- | :--- | :--- | :--- | :--- |
| `APP_ENV` | string | `development` | Yes | Application environment (`development` or `production`). |
| `CLOUDPILOT_API_KEY` | string | None | Yes | Secret API key for authentication. Minimum 32 characters in production. |
| `DEV_AUTH_DISABLED` | boolean | `false` | No | If `true`, permits starting in development without an API key. |
| `ALLOWED_ORIGIN` | string | `http://localhost:5173` | Yes | Comma-separated list of allowed CORS origins. Wildcards are rejected in production. |
| `RATE_LIMIT_PER_MIN` | integer | `30` | No | In-memory sliding window rate limit per client per minute on `/api` routes. |
| `SIM_MAX_STEPS` | integer | `1000` | No | Maximum discrete time steps for simulation runs. |
| `SIM_MAX_SERVICES` | integer | `20` | No | Maximum concurrent services simulated. |
| `SIM_TIMEOUT_SECONDS` | integer | `60` | No | Timeout in seconds for simulation execution. |
| `SUPABASE_URL` | string | None | No | Supabase project URL (optional in initial phase). |
| `SUPABASE_SERVICE_KEY` | string | None | No | Supabase service role key (optional in initial phase). |

## Local Development Setup

### 1. Prerequisites
- Python 3.11 or Python 3.12
- Git

### 2. Generate Environment Configuration
Run the environment generator script to create a secure local `.env` file with a generated 48-character API key:

```bash
python scripts/make_env.py
```

### 3. Backend Setup
Create and activate a virtual environment, then install dependencies:

```bash
cd backend
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

pip install -r requirements-dev.txt
```

### 4. Run Tests and Linters
```bash
# Run pytest
pytest

# Run Ruff linter
ruff check .

# Check code formatting
ruff format --check .
```

### 5. Start Backend Server
```bash
uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Verify the service is running:
- Health check (public): `curl http://127.0.0.1:8000/health`
- Readiness check (public): `curl http://127.0.0.1:8000/ready`
- Protected ping:
  ```bash
  curl -H "X-API-Key: <your-key-from-.env>" http://127.0.0.1:8000/api/ping
  ```

## Current Status

- Core FastAPI backend factory with fail-closed configuration validation.
- API key authentication (`X-API-Key`) with constant-time HMAC comparison.
- In-memory sliding window rate limiting on `/api` endpoints.
- Strict CORS, payload size enforcement (1 MB max), and security headers.
- Comprehensive automated test suite and GitHub Actions CI workflow.
