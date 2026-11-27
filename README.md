# CloudPilot

ML-based CPU resource allocation engine for cloud workloads.

## Overview

CloudPilot is a final-year B.Tech project focusing on intelligent CPU resource allocation for multi-service cloud workloads. It uses machine learning to predict workload demands and dynamically optimize CPU allocation to minimize throttling while maximizing host CPU utilization.

The architecture consists of:
- Backend: Python 3.11+ FastAPI service deployed on Render.
- Frontend: React + Vite web dashboard deployed on Vercel with serverless proxy. See [frontend/README.md](frontend/README.md).
- Storage: Supabase Postgres via PostgREST with Row Level Security (RLS) for simulation run history, with in-memory fallback for local development.

Note: Only CPU resources are modeled in this project. Memory (RAM) and other physical subsystems are strictly out of scope.

## Project Structure

```
cloudpilot/
  .github/workflows/ci.yml    # CI pipeline for linting, testing, and secret scanning
  .env.example                # Example configuration template
  .gitignore                  # Git ignore rules
  .gitleaks.toml              # Secret detection rules
  .pre-commit-config.yaml     # Pre-commit git hooks
  render.yaml                 # Render deployment blueprint
  docs/
    hypotheses.md             # Pre-registered hypotheses (H1-H3)
    method.md                 # Workload generation, splits, and margin selection methodology
    database.md               # Persistence schema, RLS policies, and migration instructions
  supabase/
    migrations/
      0001_simulation_runs.sql # PostgREST table schema, index, and RLS definitions
  backend/
    app/
      config.py               # Settings and fail-closed validation
      logging_setup.py        # Structured JSON logs with secret masking
      main.py                 # FastAPI application factory
      ratelimit.py            # In-memory sliding window rate limiter
      security.py             # Constant-time HMAC API key auth
      db/
        repository.py         # RunRepository interface, PostgREST & in-memory stores
      engine/
        generator.py          # Synthetic seeded workload generation
        csv_loader.py         # CSV workload parser without pandas
        features.py           # Past-only feature extraction (shift-before-rolling)
        baselines.py          # Static, rolling max, rolling p99, EWMA baselines
        models.py             # LR, DT, RF, GB, GBR_q95 models
        margins.py            # Safety margin grid application & selection
        evaluate.py           # Evaluation metrics over identical slices
        bootstrap.py          # Paired bootstrap across services
        runner.py             # Master experiment runner (TIME & SERVICE splits)
      routes/
        health.py             # /health (liveness) and /ready (readiness)
        simulate.py           # /api/simulate, /api/simulate/csv, /api/methods
        runs.py               # /api/runs (GET, GET /:id, DELETE /:id)
    tests/                    # Pytest test suite
    Dockerfile                # Container image definition
    pyproject.toml            # Tool configuration (Ruff, Pytest)
    requirements.txt          # Production dependencies (numpy, scikit-learn, etc.)
    requirements-dev.txt      # Development dependencies
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
| `SIM_TIMEOUT_SECONDS` | integer | `42` | No | Hard worker deadline in seconds, including startup and result encoding. |
| `SUPABASE_URL` | string | None | Yes | Supabase project URL (`https://` scheme required in production). |
| `SUPABASE_SERVICE_KEY` | string | None | Yes | Supabase service role API key for PostgREST control-plane access. |

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

### 6. Frontend Setup & Running Both Together
In a separate terminal, start the frontend development server:

```bash
cd frontend
npm ci
npm run dev
```

The Vite dev server runs at `http://localhost:5173` and automatically proxies all `/api/...` calls to the local backend at `http://localhost:8000`.

For full frontend documentation, testing instructions, and proxy security architecture, see [frontend/README.md](frontend/README.md).

## API Endpoints

### Health & Readiness
- `GET /health`: Liveness probe (public).
  ```bash
  curl http://127.0.0.1:8000/health
  ```
- `GET /ready`: Readiness probe (public).
  ```bash
  curl http://127.0.0.1:8000/ready
  ```

### Protected Endpoints (`X-API-Key` required)
- `GET /api/limits`: Returns operational bounds (max services, max steps, max CSV bytes, timeout).
  ```bash
  curl -H "X-API-Key: <CLOUDPILOT_API_KEY>" http://127.0.0.1:8000/api/limits
  ```
- `GET /api/ping`: Placeholder route to test authentication and rate limiting.
  ```bash
  curl -H "X-API-Key: <CLOUDPILOT_API_KEY>" http://127.0.0.1:8000/api/ping
  ```
- `GET /api/methods`: List all available baseline heuristics and ML models.
  ```bash
  curl -H "X-API-Key: <CLOUDPILOT_API_KEY>" http://127.0.0.1:8000/api/methods
  ```
- `POST /api/simulate`: Run simulation on synthetic seeded workload across TIME and SERVICE splits.
  ```bash
  curl -X POST http://127.0.0.1:8000/api/simulate \
    -H "Content-Type: application/json" \
    -H "X-API-Key: <CLOUDPILOT_API_KEY>" \
    -d '{
      "seed": 42,
      "n_services": 8,
      "n_steps": 600,
      "target_violation": 0.01
    }'
  ```
- `POST /api/simulate/csv`: Run allocation experiment on uploaded workload CSV (columns: `service_id`, `timestamp`, `cpu_demand`).
  ```bash
  curl -X POST http://127.0.0.1:8000/api/simulate/csv \
    -H "X-API-Key: <CLOUDPILOT_API_KEY>" \
    -F "file=@sample_workload.csv"
  ```
- `GET /api/runs`: List historical simulation runs for authenticated client (supports `?limit=20&offset=0`, max limit 50).
  ```bash
  curl -H "X-API-Key: <CLOUDPILOT_API_KEY>" "http://127.0.0.1:8000/api/runs?limit=10"
  ```
- `GET /api/runs/{id}`: Retrieve full details and evaluation metrics for a specific simulation run by UUID.
  ```bash
  curl -H "X-API-Key: <CLOUDPILOT_API_KEY>" http://127.0.0.1:8000/api/runs/<RUN_UUID>
  ```
- `DELETE /api/runs/{id}`: Delete a simulation run record scoped to the authenticated client.
  ```bash
  curl -X DELETE -H "X-API-Key: <CLOUDPILOT_API_KEY>" http://127.0.0.1:8000/api/runs/<RUN_UUID>
  ```

## Current Status

- Core FastAPI backend factory with fail-closed configuration validation.
- API key authentication (`X-API-Key`) with constant-time HMAC comparison.
- In-memory sliding window rate limiting on `/api` endpoints.
- PostgREST-backed persistence layer for Supabase with Row Level Security (RLS) and thread-safe in-memory fallback.
- Client run history management with automatic retention pruning (latest 50 runs per client).
- Seeded synthetic workload generator and CSV loader without pandas.
- Past-only feature extraction with shift-before-rolling logic and zero future data leakage.
- Deterministic safety margin selection on validation grids.
- Pre-registered hypotheses (H1-H3) and paired bootstrap statistical testing over services.
- Comprehensive automated test suite and GitHub Actions CI workflow.
