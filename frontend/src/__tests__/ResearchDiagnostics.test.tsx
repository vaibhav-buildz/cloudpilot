import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { SimulationResultView } from "../components/SimulationResultView";
import { metricsCsv } from "../components/experimentExport";
import type { MethodMetrics, SimulationResponse } from "../types/api";

const model: MethodMetrics = {
  mae: 1,
  mse: 2,
  rmse: Math.sqrt(2),
  margin_value: null,
  margin_type: null,
  is_feasible: false,
  violation_rate: 0.2,
  savings: 0,
  utilization: 0,
  wastage: 0,
};
const hypothesis = {
  hypothesis: "",
  verdict: "NOT_SUPPORTED",
  estimate: 0,
  ci_lower: 0,
  ci_upper: 0,
  p_value: 1,
};
const methods = { GBR_q95: model, static: { ...model, is_feasible: true } };
const time = {
  comparator: "static",
  comparator_is_feasible: true,
  methods,
  traces: [
    {
      service_index: 0,
      steps: [450, 451],
      actual: [3, 5],
      static_capacity: 7,
      methods: {
        GBR_q95: { predicted: [4, 2], allocated: null },
        static: { predicted: null, allocated: [7, 7] },
      },
    },
    {
      service_index: 1,
      steps: [450, 451],
      actual: [5, 5],
      static_capacity: 9,
      methods: {
        GBR_q95: { predicted: [2, 1], allocated: null },
        static: { predicted: null, allocated: [9, 9] },
      },
    },
  ],
};
const result: SimulationResponse = {
  disclaimer: "",
  execution_time_seconds: 1,
  parameters: { seed: 1, n_steps: 600, n_services: 4, target_violation: 0.01 },
  time_split: { ...time, h1: hypothesis },
  service_split: {
    ...time,
    h2: hypothesis,
    traces: [{ ...time.traces[0], service_index: 3, steps: [288, 289] }],
  },
  h3: {
    hypothesis: "",
    verdict: "SUPPORTED",
    test_violation_time: 0.01,
    test_violation_service: 0.01,
    threshold: 0.015,
  },
};

describe("Research diagnostics", () => {
  it("switches service, held-out split, method and step, with infeasible allocation suppressed", () => {
    render(
      <MemoryRouter>
        <SimulationResultView result={result} />
      </MemoryRouter>,
    );
    const charts = screen.getByRole("region", { name: "Held-out traces" });
    expect(
      within(charts).getByText(/no approved allocation series/i),
    ).toBeInTheDocument();
    fireEvent.change(within(charts).getByLabelText("Service"), {
      target: { value: "1" },
    });
    fireEvent.change(within(charts).getAllByRole("slider")[0], {
      target: { value: "1" },
    });
    expect(within(charts).getAllByText("Step 451").length).toBeGreaterThan(1);
    fireEvent.change(within(charts).getByLabelText("Method"), {
      target: { value: "static" },
    });
    expect(
      within(charts).getByText(/static reservation has no prediction/i),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "SERVICE" }));
    expect(
      screen.getByRole("option", { name: "Service index 3" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "MSE (cores²)" }));
    expect(screen.getByRole("columnheader", { name: /^MSE/ })).toHaveAttribute(
      "aria-sort",
      "ascending",
    );
  });

  it("renders legacy results without traces or prediction error fields", () => {
    const { mae, mse, rmse, ...legacy } = model;
    expect([mae, mse, rmse]).toHaveLength(3);
    render(
      <MemoryRouter>
        <SimulationResultView
          result={{
            ...result,
            time_split: {
              ...result.time_split,
              traces: undefined,
              methods: { GBR_q95: legacy },
            },
          }}
        />
      </MemoryRouter>,
    );
    expect(
      screen.getByText(/held-out traces are unavailable/i),
    ).toBeInTheDocument();
    expect(
      within(
        screen.getByRole("region", { name: "TIME policy comparison" }),
      ).getAllByText("—").length,
    ).toBeGreaterThan(3);
  });

  it("exports both splits, flags diagnostics, leaves absent values blank, and escapes formula cells", () => {
    const csv = metricsCsv({
      ...result,
      time_split: {
        ...result.time_split,
        methods: { ' =HYPERLINK("url")': model },
      },
    });
    expect(csv).toContain('"TIME","\' =HYPERLINK(""url"")",false,1,2,');
    expect(csv).toContain(',0.2,,,"unmargined_diagnostic"\r\n');
    expect(csv).toContain('"SERVICE","static",true,,,,0,0.2,0,0,');
  });
});
