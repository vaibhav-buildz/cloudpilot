export interface LimitsResponse {
  max_services: number;
  max_steps: number;
  max_csv_bytes: number;
  timeout_seconds: number;
  history_limit: number;
}

export interface MethodMetrics {
  margin_value: number | null;
  margin_type: string | null;
  is_feasible: boolean;
  violation_rate: number;
  savings: number;
  utilization: number;
  wastage: number;
}

export interface HypothesisVerdict {
  hypothesis: string;
  verdict: string;
  estimate: number;
  ci_lower: number;
  ci_upper: number;
  p_value: number;
}

export interface SplitComparison {
  comparator: string;
  comparator_is_feasible: boolean;
  methods: Record<string, MethodMetrics>;
}

export interface SimulationResponse {
  run_id?: string;
  saved?: boolean;
  disclaimer: string;
  execution_time_seconds: number;
  parameters: {
    seed: number;
    n_services: number;
    n_steps: number;
    target_violation: number;
  };
  time_split: SplitComparison & { h1: HypothesisVerdict };
  service_split: SplitComparison & { h2: HypothesisVerdict };
  h3: {
    hypothesis: string;
    verdict: string;
    test_violation_time: number;
    test_violation_service: number;
    threshold: number;
  };
}

export interface SavedRun {
  id: string;
  created_at: string;
  source: "simulated" | "csv";
  params: {
    n_services?: number;
    n_steps?: number;
    target_violation?: number;
    seed?: number;
  };
  status: "ok" | "error";
  result: SimulationResponse | null;
  duration_ms: number | null;
  error: string | null;
}
