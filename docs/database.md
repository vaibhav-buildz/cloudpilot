# CloudPilot Database Architecture and Migration Guide

This document specifies the persistence schema, security policies, and migration procedures for the CloudPilot control plane using Supabase Postgres via PostgREST.

---

## 1. Schema Definition

The table `public.simulation_runs` persists metadata and aggregate outcomes of workload simulations conducted through `/api/simulate` and `/api/simulate/csv`.

```sql
CREATE TABLE IF NOT EXISTS public.simulation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    client_id TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('simulated', 'csv')),
    params JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    result JSONB,
    error TEXT,
    duration_ms INTEGER
);

-- Index for efficient client scoping and recency pagination
CREATE INDEX IF NOT EXISTS idx_simulation_runs_client_created_at
    ON public.simulation_runs (client_id, created_at DESC);
```

### Column Specifications

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key, `gen_random_uuid()` | Unique identifier for the simulation run. |
| `created_at` | `TIMESTAMPTZ` | Not Null, Default `now()` | Timestamp when the run was initiated and recorded. |
| `client_id` | `TEXT` | Not Null | Cryptographic SHA-256 hash prefix of the client API key. |
| `source` | `TEXT` | Check `('simulated', 'csv')` | Workload source category. |
| `params` | `JSONB` | Not Null | Run parameters (seed, services, steps, target violation). |
| `status` | `TEXT` | Check `('ok', 'error')` | Simulation completion state. |
| `result` | `JSONB` | Nullable | Full aggregate evaluation outcome and split metrics. |
| `error` | `TEXT` | Nullable | Sanitized error message if simulation failed. |
| `duration_ms` | `INTEGER` | Nullable | Wall-clock execution duration in milliseconds. |

---

## 2. Stored Data vs. Excluded Data

To uphold privacy and data minimization standards:

### What Is Stored
- Unique run UUIDs and creation timestamps.
- One-way cryptographic hash of the client's API key (`client_id`).
- High-level simulation parameters (e.g. `seed`, `n_services`, `n_steps`, `target_violation`).
- High-level CSV dimensions (e.g. `n_services`, `n_steps`, `target_violation`).
- Aggregate allocation performance metrics (savings, violations, margins, bootstrap estimates).
- Execution timing telemetry (`duration_ms`).

### What Is NOT Stored
- **Uploaded CSV contents**: Raw time series, demand values, or file bodies are **never** stored in the database.
- **Uploaded file names**: Original client file paths or names are discarded immediately upon parsing.
- **API Keys / Secrets**: Plaintext API keys and secrets are **never** persisted.
- **Client IP addresses**: Client network locations are excluded from the database table.

---

## 3. Row Level Security (RLS) & Access Model

The migration explicitly applies Row Level Security:

```sql
-- Enable Row Level Security (RLS)
ALTER TABLE public.simulation_runs ENABLE ROW LEVEL SECURITY;

-- Revoke all permissions from anon and authenticated roles
REVOKE ALL ON TABLE public.simulation_runs FROM anon, authenticated;
```

### Security Rationale
1. **Zero Public Access**: Supabase applications expose the `anon` and `authenticated` roles to web clients. Revoking all permissions on `public.simulation_runs` guarantees that even if client-side keys are compromised, unauthorized callers cannot query or manipulate simulation records.
2. **Service Role Authentication**: The CloudPilot FastAPI backend authenticates exclusively using the Supabase `service_role` key. In Postgres, the service role bypasses RLS policies by default, granting the control plane full operational access.
3. **Application-Layer Tenant Scoping**: All operations (`list_runs`, `get_run`, `delete_run`, `prune`) filter strictly by the verified `client_id`. A client cannot access or delete runs belonging to another client.
4. **Automatic Retention Pruning**: To prevent unbounded growth, the backend automatically prunes historical runs beyond the latest 50 records per client after each successful simulation.

---

## 4. How to Apply the Migration

### Supabase SQL Editor
1. Log in to the [Supabase Dashboard](https://supabase.com/dashboard) and select your project.
2. In the left-hand navigation menu, click **SQL Editor**.
3. Click **+ New query**.
4. Open [supabase/migrations/0001_simulation_runs.sql](file:///d:/GitHuh/cloudpilot/supabase/migrations/0001_simulation_runs.sql), copy its entire content, and paste it into the SQL Editor.
5. Click **Run** (or press `Ctrl+Enter` / `Cmd+Enter`).
6. Navigate to **Table Editor** > `simulation_runs` to verify that the table, index, and RLS settings have applied successfully.

### Local Development Fallback
In local development, if `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are omitted, CloudPilot seamlessly falls back to `InMemoryRunRepository`. No local database installation is required for unit tests or standard development workflows.
