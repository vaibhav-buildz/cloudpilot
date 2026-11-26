import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ExperimentModeField } from "../components/ExperimentModeField";
import { SimulationResultView } from "../components/SimulationResultView";
import { extendedMetricsCsv } from "../components/experimentExport";
import type {
  ExtendedResponse,
  ExtendedSplit,
  TaskMetrics,
} from "../types/api";

const timing = { count: 1, mean: 3, median: 3, p95: 3 };
const tasks: TaskMetrics = {
  offered: 2,
  completed: 1,
  completion_rate: 0.5,
  unfinished: 1,
  rejected: 0,
  admitted_unfinished: 1,
  suspended_final: 1,
  never_admitted: 0,
  throughput_per_second: 1 / 300,
  scheduler_utilization: {
    cpu_core_seconds: 30,
    cpu_capacity_core_seconds: 300,
    cpu_fraction: 0.1,
    memory_gib_seconds: 60,
    memory_capacity_gib_seconds: 300,
    memory_fraction: 0.2,
  },
  peak_backlog: 1,
  final_backlog: 1,
  timing_seconds: {
    waiting: timing,
    first_service: timing,
    response: timing,
    execution: timing,
  },
  response_distribution: { edges: [0, 5], counts: [1] },
  timeline: [
    { elapsed_seconds: 300, backlog: 1, throughput_per_second: 1 / 300 },
  ],
};

const metric = {
  mae: 1,
  mse: 2,
  rmse: Math.sqrt(2),
  violation_rate: 0.01,
  savings: 0.3,
  utilization: 0.4,
  wastage: 0.6,
  is_feasible: true,
  margin_value: 1,
  margin_type: "multiplicative",
};
const feasible = {
  jointly_feasible: true,
  validation_joint_violation_rate: 0,
  test_joint_violation_rate: 0.02,
  tasks,
};
const comparison = {
  comparator: "static",
  comparator_is_feasible: true,
  methods: { static: metric, GBR_q95: metric },
};
const split: ExtendedSplit = {
  cpu: comparison,
  memory: comparison,
  offered_tasks: 2,
  offered_tasks_sha256: "test",
  policies: {
    static: feasible,
    GBR_q95: { ...feasible, jointly_feasible: false, tasks: null },
  },
};
const result: ExtendedResponse = {
  mode: "extended-v1",
  execution_time_seconds: 3,
  parameters: { seed: 42, n_services: 4, n_steps: 600, target_violation: 0.01 },
  time_split: split,
  service_split: split,
};

describe("extended experiments", () => {
  it("keeps the extended option disabled until the API advertises local limits", () => {
    const limits = {
      max_services: 20,
      max_steps: 1000,
      max_csv_bytes: 1000,
      timeout_seconds: 50,
      history_limit: 50,
    };
    const onChange = vi.fn();
    const { rerender } = render(
      <ExperimentModeField
        mode="cpu-only"
        limits={limits}
        onChange={onChange}
      />,
    );
    expect(
      screen.getByRole("option", { name: /extended cpu/i }),
    ).toBeDisabled();
    rerender(
      <ExperimentModeField
        mode="cpu-only"
        limits={{
          ...limits,
          extended_max_services: 4,
          extended_max_steps: 600,
        }}
        onChange={onChange}
      />,
    );
    fireEvent.change(
      screen.getByRole("combobox", { name: /experiment mode/i }),
      { target: { value: "extended-v1" } },
    );
    expect(onChange).toHaveBeenCalledWith("extended-v1");
  });

  it("renders saved task metrics, changes resource units, and explains unavailable task results", () => {
    render(
      <MemoryRouter>
        <SimulationResultView result={result} persisted />
      </MemoryRouter>,
    );
    expect(screen.getByText(/saved to history/i)).toBeInTheDocument();
    expect(screen.getByText(/Resident task memory 20%/i)).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "Demand / capacity" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/queue and suspension backlog/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: /^MSE.*GiB/ }),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Resource"), {
      target: { value: "cpu" },
    });
    expect(
      screen.getByRole("columnheader", { name: /^MSE.*cores/ }),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Scheduling policy"), {
      target: { value: "GBR_q95" },
    });
    expect(screen.getByText(/missed joint validation/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/queue and suspension backlog/i),
    ).not.toBeInTheDocument();
  });

  it("exports separate resource units and both splits with task metrics", () => {
    const csv = extendedMetricsCsv(result);
    const rows = csv.trimEnd().split("\r\n");
    expect(rows).toHaveLength(5);
    expect(rows[0]).toContain('"memory_mse_gib_squared"');
    expect(rows[0]).toContain('"cpu_mse_cores_squared"');
    expect(rows[0]).toContain('"response_p95_seconds"');
    expect(rows[3]).toContain('"SERVICE","static"');
    expect(rows[2].split(",")).toHaveLength(rows[0].split(",").length);
  });
});
