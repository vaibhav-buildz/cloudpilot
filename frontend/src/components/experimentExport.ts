import type {
  ExperimentResult,
  ExtendedResponse,
  MethodMetrics,
  SimulationResponse,
} from "../types/api";

function csvCell(value: string | number | boolean | null | undefined) {
  if (value == null) return "";
  if (typeof value !== "string") return String(value);
  const safe = /^[\s\uFEFF]*[=+\-@\t\r\n]/u.test(value) ? "'" + value : value;
  return '"' + safe.replaceAll('"', '""') + '"';
}

export function predictionError(
  name: string,
  method: MethodMetrics,
  metric: "mae" | "mse" | "rmse",
) {
  return name === "static" ? undefined : (method[metric] ?? undefined);
}

export function metricsCsv(result: SimulationResponse) {
  const rows = [
    [
      "split",
      "method",
      "validation_feasible",
      "mae_cores",
      "mse_cores_squared",
      "rmse_cores",
      "savings_fraction",
      "violation_fraction",
      "utilization_fraction",
      "wastage_fraction",
      "violation_basis",
    ],
  ];
  const metrics = (["TIME", "SERVICE"] as const).flatMap((split) => {
    const comparison =
      split === "TIME" ? result.time_split : result.service_split;
    return Object.entries(comparison?.methods ?? {}).map(([name, method]) => [
      split,
      name,
      method.is_feasible,
      predictionError(name, method, "mae"),
      predictionError(name, method, "mse"),
      predictionError(name, method, "rmse"),
      method.is_feasible ? method.savings : null,
      method.violation_rate,
      method.is_feasible ? method.utilization : null,
      method.is_feasible ? method.wastage : null,
      method.is_feasible ? "evaluated_allocation" : "unmargined_diagnostic",
    ]);
  });
  return (
    [...rows, ...metrics]
      .map((row) => row.map(csvCell).join(","))
      .join("\r\n") + "\r\n"
  );
}

const timingKeys = [
  "waiting",
  "first_service",
  "response",
  "execution",
] as const;
const timingStats = ["count", "mean", "median", "p95"] as const;

export function extendedMetricsCsv(result: ExtendedResponse) {
  const fields = (resource: string, unit: string) =>
    [
      "validation_feasible",
      "mae_" + unit,
      "mse_" + unit + "_squared",
      "rmse_" + unit,
      "savings_fraction",
      "violation_fraction",
      "utilization_fraction",
      "wastage_fraction",
      "violation_basis",
    ].map((field) => resource + "_" + field);
  const header = [
    "protocol",
    "split",
    "method",
    ...fields("cpu", "cores"),
    ...fields("memory", "gib"),
    "joint_validation_feasible",
    "joint_validation_violation_fraction",
    "joint_test_violation_fraction",
    "offered",
    "completed",
    "completion_fraction",
    "unfinished",
    "rejected",
    "admitted_unfinished",
    "suspended_at_end",
    "never_admitted",
    "throughput_tasks_per_second",
    "peak_backlog",
    "final_backlog",
    ...timingKeys.flatMap((key) =>
      timingStats.map(
        (stat) => key + "_" + stat + (stat === "count" ? "" : "_seconds"),
      ),
    ),
  ];
  const resourceMetrics = (m: MethodMetrics) => [
    m.is_feasible,
    m.mae,
    m.mse,
    m.rmse,
    m.is_feasible ? m.savings : null,
    m.violation_rate,
    m.is_feasible ? m.utilization : null,
    m.is_feasible ? m.wastage : null,
    m.is_feasible ? "evaluated_allocation" : "unmargined_diagnostic",
  ];
  const rows = (["TIME", "SERVICE"] as const).flatMap((key) => {
    const split = key === "TIME" ? result.time_split : result.service_split;
    return Object.entries(split.policies).map(([name, comparison]) => {
      const task = comparison.tasks;
      return [
        result.mode,
        key,
        name,
        ...resourceMetrics(split.cpu.methods[name]),
        ...resourceMetrics(split.memory.methods[name]),
        comparison.jointly_feasible,
        comparison.validation_joint_violation_rate,
        comparison.test_joint_violation_rate,
        split.offered_tasks,
        task?.completed,
        task?.completion_rate,
        task?.unfinished,
        task?.rejected,
        task?.admitted_unfinished,
        task?.suspended_final,
        task?.never_admitted,
        task?.throughput_per_second,
        task?.peak_backlog,
        task?.final_backlog,
        ...timingKeys.flatMap((metric) =>
          timingStats.map((stat) => task?.timing_seconds[metric][stat]),
        ),
      ];
    });
  });
  return (
    [header, ...rows].map((row) => row.map(csvCell).join(",")).join("\r\n") +
    "\r\n"
  );
}

export function downloadExperiment(
  result: ExperimentResult,
  format: "json" | "csv",
) {
  const output =
    format === "json"
      ? JSON.stringify(result, null, 2)
      : result.mode === "extended-v1"
        ? extendedMetricsCsv(result)
        : metricsCsv(result);
  const blob = new Blob([output], {
    type: format === "json" ? "application/json" : "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download =
    "cloudpilot-" +
    (result.run_id ?? result.mode ?? "experiment") +
    "." +
    format;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
