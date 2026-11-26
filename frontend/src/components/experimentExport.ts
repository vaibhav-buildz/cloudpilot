import type { MethodMetrics, SimulationResponse } from "../types/api";

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
