export interface LimitsResponse {
  max_services: number;
  max_steps: number;
  max_csv_bytes: number;
  timeout_seconds: number;
  history_limit: number;
}

export interface MethodMetrics {
  margin: number | null;
  is_feasible: boolean;
  pooled_violation: number;
  pooled_savings: number;
  mean_utilization: number;
  mean_wastage: number;
}

export interface HypothesisVerdict {
  supported: boolean;
  effect_pp: number;
  ci_lower: number;
  ci_upper: number;
  note: string;
}

export interface SplitComparison {
  comparator_name: string;
  is_gbr_feasible: boolean;
  metrics: Record<string, MethodMetrics>;
  h1: HypothesisVerdict;
  h2: HypothesisVerdict;
  h3: HypothesisVerdict;
  evaluation_rows: number;
}

export interface SimulationResponse {
  id?: string;
  workload_info: {
    n_services: number;
    n_steps: number;
    target_violation: number;
    source?: string;
  };
  time_split: SplitComparison;
  service_split?: SplitComparison;
  created_at?: string;
}

export interface RunSummary {
  id: string;
  created_at: string;
  client_id: string;
  n_services: number;
  n_steps: number;
  target_violation: number;
  time_comparator: string;
  time_h1_verdict: boolean;
  service_comparator?: string | null;
  service_h1_verdict?: boolean | null;
}

export interface RunsListResponse {
  runs: RunSummary[];
  total: number;
  limit: number;
  offset: number;
}
