# CloudPilot Deployment Guide

This guide covers deploying CloudPilot across three services:
- **Database**: Supabase Postgres (project ref `plpmitudxbrpxxfwedzg`)
- **Backend**: FastAPI on Render (`render.yaml` Blueprint)
- **Frontend & Serverless Proxy**: React + Vite + Vercel Function (`frontend/`)

---

## Environment Variables

All variable names match [backend/app/config.py](../backend/app/config.py) and [frontend/api/[...path].ts](../frontend/api/%5B...path%5D.ts).

| Name | Where Set | Secret | Notes |
| :--- | :--- | :--- | :--- |
| `APP_ENV` | Render / Local | No | Set to `production` on Render (`development` locally). |
| `CLOUDPILOT_API_KEY` | Render / Vercel / Local | Yes | Shared secret (>= 32 chars in production). Never put in `VITE_*`. |
| `DEV_AUTH_DISABLED` | Local only | No | Keep `false` (default) in production. |
| `ALLOWED_ORIGIN` | Render / Local | No | Exact Vercel origin URL in production (no `*`). |
| `RATE_LIMIT_PER_MIN` | Render / Local | No | Per-client sliding window limit (default `30`). |
| `GLOBAL_SIM_PER_MIN` | Render / Local | No | Global `/api/simulate*` cap across all clients (default `20`). |
| `SIM_MAX_STEPS` | Render / Local | No | Max time steps per simulation (default `1000`). |
| `SIM_MAX_SERVICES` | Render / Local | No | Max services per simulation (default `20`). |
| `SIM_TIMEOUT_SECONDS` | Render / Local | No | Worker startup, CSV parsing, engine, and encoding budget. Defaults to `42` seconds and is capped at `42` in production. |
| `SIM_MAX_CONCURRENT` | Render / Local | No | Simultaneous simulation requests per Uvicorn process (default `1`). Excess requests receive a busy response immediately. |
| `SIM_RF_JOBS`, `SIM_NATIVE_THREADS` | Render / Local | No | Random Forest jobs and BLAS/OpenMP threads per web worker (both default to `1`). |
| `ENABLE_PRODUCTION_EXTENDED_SIMULATION` | Render | No | Extended-v1 API opt-in. Keep this `false` until hosted verification passes. |
| `SIM_EXTENDED_MAX_SERVICES`, `SIM_EXTENDED_MAX_STEPS` | Render / Local | No | Independent extended caps (default `4` services and `600` steps). Local opt-in uses `ENABLE_EXTENDED_SIMULATION`. |
| `SUPABASE_URL` | Render / Local | No | `https://<project-ref>.supabase.co` (HTTPS required in production). |
| `SUPABASE_SERVICE_KEY` | Render / Local | Yes | Supabase service role / secret key for PostgREST. |
| `BACKEND_URL` | Vercel / Local | No | Render backend base URL (`https://...`), used server-side by proxy. |

---

## Ordered Deployment Steps

### 1. Push Code to GitHub
Push `main` to `vaibhav-buildz/cloudpilot` and confirm all CI jobs (Backend, Frontend, Gitleaks) are green.

### 2. Verify Supabase Schema
Confirm [supabase/migrations/0001_simulation_runs.sql](../supabase/migrations/0001_simulation_runs.sql) is applied on project `plpmitudxbrpxxfwedzg` with RLS enabled and `anon`/`authenticated` revoked. Keep `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` ready.

### 3. Deploy Backend on Render (Blueprint)
1. In the Render dashboard, choose **New + -> Blueprint** and connect `vaibhav-buildz/cloudpilot`.
2. Render reads [render.yaml](../render.yaml) and creates `cloudpilot-backend` using `backend/Dockerfile`.
3. Fill in the four `sync: false` variables:
   - `CLOUDPILOT_API_KEY`: generate a random string of at least 32 characters.
   - `SUPABASE_URL`: your Supabase project HTTPS URL.
   - `SUPABASE_SERVICE_KEY`: your Supabase service/secret key.
   - `ALLOWED_ORIGIN`: temporary placeholder (e.g. `https://placeholder.invalid`) until Vercel gives you the frontend URL.
4. Wait for the first deploy to finish and copy the Render service URL (`https://<service>.onrender.com`).

### 4. Deploy Frontend & Proxy on Vercel
1. In the Vercel dashboard, import `vaibhav-buildz/cloudpilot`.
2. Set **Root Directory** to `frontend` and **Framework Preset** to `Vite`.
3. Add server-side Environment Variables (do **not** prefix with `VITE_`):
   - `BACKEND_URL`: your Render service URL from Step 3 (no trailing slash).
   - `CLOUDPILOT_API_KEY`: the exact same key set on Render.
4. Deploy and copy the production Vercel URL (`https://<project>.vercel.app`).

### 5. Set `ALLOWED_ORIGIN` on Render & Redeploy
1. Return to Render -> `cloudpilot-backend` -> **Environment**.
2. Update `ALLOWED_ORIGIN` to the exact Vercel URL from Step 4 (e.g. `https://cloudpilot.vercel.app`, no trailing slash).
3. Trigger a manual redeploy (or save changes to trigger restart) so the CORS middleware picks up the Vercel origin.

### 6. Run End-to-End Smoke Test
From your local repo root, export `BACKEND_URL`, `FRONTEND_URL`, and `CLOUDPILOT_API_KEY` in your shell and run:

```bash
python scripts/smoke_test.py
```

All 6 checks (`health`, `ready`, `auth_required`, `proxy_simulate_and_readback`, `cors_preflight`, `simulation_caps`) must print `PASS`.

---

## Render Free-Tier Cold Starts & Proxy Timeout Behavior

- Render documents a roughly one-minute wake-up after idle spin-down. Warm the backend with `GET /health` before running the production smoke scripts. [Render free services](https://render.com/docs/free)
- The backend allows 42 seconds for the worker, four seconds for save confirmation, and two seconds for pruning. The proxy covers the complete upstream response for 55 seconds, leaving about seven seconds for transport and backend response handling. Vercel allows the function 60 seconds total. [Vercel proxy](../frontend/api/%5B...path%5D.ts)
- Customers can retry after the backend wakes or a busy slot clears. The proxy aborts the upstream request on disconnect and leaves retries to the client. For rollout and rollback details, see [Phase 5 verification](phase5.md).
