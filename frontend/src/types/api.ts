export interface LimitsResponse {
  max_services: number;
  max_steps: number;
  max_csv_bytes: number;
  timeout_seconds: number;
  history_limit: number;
  extended_max_services?: number | null;
  extended_max_steps?: number | null;
}

export interface MethodMetrics {
  mae?: number | null;
  mse?: number | null;
  rmse?: number | null;
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
  traces?: HeldOutTrace[];
  comparator: string;
  comparator_is_feasible: boolean;
  methods: Record<string, MethodMetrics>;
}

export interface HeldOutTrace {
  service_index: number;
  steps: number[];
  actual: number[];
  static_capacity: number;
  methods: Record<
    string,
    { predicted: number[] | null; allocated: number[] | null }
  >;
}

export type DemandStatistics = Record<
  "mean" | "std_dev" | "min" | "max" | "median" | "p05" | "p95" | "p99",
  number
>;

export interface WorkloadAnalysis {
  statistics: DemandStatistics;
  histogram: { edges: number[]; counts: number[] };
  steps: number[];
  mean_demand: number[];
  peak_demand: number[];
  peak_step: number;
  services: Array<DemandStatistics & { service_index: number }>;
}

export interface SimulationResponse {
  mode?: "cpu-only";
  workload_analysis?: WorkloadAnalysis;
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

export type ExperimentMode = "cpu-only" | "extended-v1";

export interface TaskMetrics {
  offered: number;
  completed: number;
  completion_rate: number | null;
  unfinished: number;
  rejected: number;
  admitted_unfinished: number;
  suspended_final: number;
  never_admitted: number;
  throughput_per_second: number;
  scheduler_utilization?: {
    cpu_core_seconds: number;
    cpu_capacity_core_seconds: number;
    cpu_fraction: number | null;
    memory_gib_seconds: number;
    memory_capacity_gib_seconds: number;
    memory_fraction: number | null;
  };
  peak_backlog: number;
  final_backlog: number;
  timing_seconds: Record<
    "waiting" | "first_service" | "response" | "execution",
    {
      count: number;
      mean: number | null;
      median: number | null;
      p95: number | null;
    }
  >;
  response_distribution: { edges: number[]; counts: number[] };
  timeline: {
    elapsed_seconds: number;
    backlog: number;
    throughput_per_second: number;
  }[];
}

export interface ExtendedSplit {
  cpu: SplitComparison;
  memory: SplitComparison;
  offered_tasks: number;
  offered_tasks_sha256: string;
  policies: Record<
    string,
    {
      jointly_feasible: boolean;
      validation_joint_violation_rate: number | null;
      test_joint_violation_rate: number | null;
      tasks: TaskMetrics | null;
    }
  >;
}

export interface ExtendedResponse {
  mode: "extended-v1";
  run_id?: string;
  saved?: boolean;
  execution_time_seconds: number;
  parameters: SimulationResponse["parameters"];
  time_split: ExtendedSplit;
  service_split: ExtendedSplit;
}

export type ExperimentResult = SimulationResponse | ExtendedResponse;

export interface SavedRun {
  id: string;
  created_at: string;
  source: "simulated" | "csv";
  params: {
    n_services?: number;
    n_steps?: number;
    target_violation?: number;
    seed?: number;
    mode?: ExperimentMode;
  };
  status: "ok" | "error";
  result: ExperimentResult | null;
  duration_ms: number | null;
  error: string | null;
}
