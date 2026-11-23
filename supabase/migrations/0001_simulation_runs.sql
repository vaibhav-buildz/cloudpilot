-- Migration: 0001_simulation_runs.sql
-- Description: Create simulation_runs table for control-plane persistence via PostgREST.

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

-- Index for efficient client scoping and pagination ordered by recency
CREATE INDEX IF NOT EXISTS idx_simulation_runs_client_created_at
    ON public.simulation_runs (client_id, created_at DESC);

-- Enable Row Level Security (RLS)
ALTER TABLE public.simulation_runs ENABLE ROW LEVEL SECURITY;

-- Revoke all permissions from anon and authenticated roles.
-- The backend uses the service role key which bypasses RLS in Supabase.
-- This ensures anon and authenticated roles have zero access even if exposed.
REVOKE ALL ON TABLE public.simulation_runs FROM anon, authenticated;
