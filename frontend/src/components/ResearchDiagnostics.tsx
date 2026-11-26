import { useState } from "react";
import type {
  DemandStatistics,
  HeldOutTrace,
  WorkloadAnalysis,
} from "../types/api";
import { AllocationBarChart } from "./AllocationBarChart";
import "./research-diagnostics.css";

type Series = { label: string; values: number[] };
const number = (value: number) =>
  value.toLocaleString(undefined, { maximumFractionDigits: 4 });

export function TraceChart({
  title,
  steps,
  series,
  unit = "CPU cores",
  stepLabel = "Step",
}: {
  title: string;
  steps: number[];
  series: Series[];
  unit?: string;
  stepLabel?: string;
}) {
  const [position, setPosition] = useState(0);
  const selected = Math.min(position, steps.length - 1);
  const samples = series.flatMap((line) => line.values);
  const min = Math.min(0, ...samples);
  const max = Math.max(0.001, ...samples);
  const x = (i: number) =>
    55 +
    (525 * (steps[i] - steps[0])) /
      Math.max(1, steps[steps.length - 1] - steps[0]);
  const y = (value: number) => 145 - (126 * (value - min)) / (max - min);
  return (
    <figure className="diag-chart">
      <figcaption>
        {title} · {unit}
      </figcaption>
      <svg viewBox="0 0 600 174" aria-hidden="true">
        {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
          const value = min + fraction * (max - min);
          return (
            <g key={fraction}>
              <line x1="55" x2="580" y1={y(value)} y2={y(value)} />
              <text
                x="50"
                y={y(value)}
                textAnchor="end"
                dominantBaseline="middle"
              >
                {number(value)}
              </text>
            </g>
          );
        })}
        {series.map((line, index) => (
          <polyline
            key={line.label}
            className={"diag-line diag-line-" + index}
            points={line.values
              .map((value, i) => x(i) + "," + y(value))
              .join(" ")}
          />
        ))}
        <line
          className="diag-cursor"
          x1={x(selected)}
          x2={x(selected)}
          y1="19"
          y2="145"
        />
        <text x="55" y="166">
          {stepLabel} {steps[0]}
        </text>
        <text x="580" y="166" textAnchor="end">
          {stepLabel} {steps.at(-1)}
        </text>
      </svg>
      <label>
        Inspect {stepLabel.toLowerCase()}{" "}
        <input
          type="range"
          min={0}
          max={steps.length - 1}
          value={selected}
          onChange={(event) => setPosition(Number(event.target.value))}
          aria-valuetext={`${stepLabel} ${steps[selected]}`}
        />
      </label>
      <ul>
        <li>
          {stepLabel} {steps[selected]}
        </li>
        {series.map((line, index) => (
          <li key={line.label} data-series={index}>
            {line.label} <strong>{number(line.values[selected])}</strong>
          </li>
        ))}
      </ul>
    </figure>
  );
}

export function HeldOutCharts({
  traces,
  unit = "CPU cores",
}: {
  traces: HeldOutTrace[];
  unit?: string;
}) {
  const [service, setService] = useState(0);
  const [method, setMethod] = useState("GBR_q95");
  const trace = traces[service];
  const values = trace.methods[method];
  const predictions = values.predicted;
  const allocation = values.allocated;
  return (
    <section className="diag-section" aria-label="Held-out traces">
      <h4>Held-out demand and capacity</h4>
      <p>
        Deterministic samples of evaluated rows. Services and steps use
        zero-based workload indices.
      </p>
      <div className="diag-controls">
        <label>
          Service{" "}
          <select
            value={service}
            onChange={(event) => setService(Number(event.target.value))}
          >
            {traces.map((item, index) => (
              <option key={item.service_index} value={index}>
                Service index {item.service_index}
              </option>
            ))}
          </select>
        </label>
        <label>
          Method{" "}
          <select
            value={method}
            onChange={(event) => setMethod(event.target.value)}
          >
            {Object.keys(trace.methods).map((key) => (
              <option key={key}>{key}</option>
            ))}
          </select>
        </label>
      </div>
      <TraceChart
        title="Actual vs. raw prediction"
        unit={unit}
        steps={trace.steps}
        series={[
          { label: "Actual demand", values: trace.actual },
          ...(predictions
            ? [{ label: "Raw prediction", values: predictions }]
            : []),
        ]}
      />
      {!predictions && <p>Static reservation has no prediction series.</p>}
      <TraceChart
        title="Demand vs. evaluated allocation"
        unit={unit}
        steps={trace.steps}
        series={[
          { label: "Actual demand", values: trace.actual },
          ...(allocation
            ? [{ label: "Allocated capacity", values: allocation }]
            : []),
          {
            label: "Static reference",
            values: trace.actual.map(() => trace.static_capacity),
          },
          ...(allocation
            ? [
                {
                  label: "Unused capacity",
                  values: allocation.map((v, i) =>
                    Math.max(0, v - trace.actual[i]),
                  ),
                },
              ]
            : []),
        ]}
      />
      {allocation ? (
        <p>
          Under-allocation at sampled steps:{" "}
          {trace.steps
            .filter((_, i) => allocation[i] < trace.actual[i])
            .join(", ") || "None"}
          .
        </p>
      ) : (
        <p>
          No approved allocation series. This method was infeasible on
          validation.
        </p>
      )}
    </section>
  );
}

const statistics: [keyof DemandStatistics, string][] = [
  ["mean", "Mean"],
  ["median", "Median"],
  ["std_dev", "Std. deviation"],
  ["min", "Minimum"],
  ["max", "Maximum"],
  ["p05", "P05"],
  ["p95", "P95"],
  ["p99", "P99"],
];

export function WorkloadDiagnostics({
  workload,
}: {
  workload: WorkloadAnalysis;
}) {
  return (
    <section className="exp-panel diag-section" aria-label="Workload analysis">
      <h3>Workload analysis</h3>
      <p>
        Descriptive statistics cover the full processed workload. Model fitting
        and validation use their original partitions. The observed peak occurred
        at step {workload.peak_step}.
      </p>
      <TraceChart
        title="Mean and peak demand across services"
        steps={workload.steps}
        series={[
          { label: "Mean demand", values: workload.mean_demand },
          { label: "Peak demand", values: workload.peak_demand },
        ]}
      />
      <AllocationBarChart
        title="CPU demand distribution · bin bounds in CPU cores"
        unit="observations"
        items={workload.histogram.counts.map((count, i) => ({
          label:
            number(workload.histogram.edges[i]) +
            "–" +
            number(workload.histogram.edges[i + 1]),
          value: count,
        }))}
      />
      <div
        className="exp-table-wrap"
        tabIndex={0}
        role="region"
        aria-label="Demand statistics"
      >
        <table className="exp-table">
          <caption>
            Demand statistics in CPU cores · population standard deviation
          </caption>
          <thead>
            <tr>
              <th scope="col">Workload</th>
              {statistics.map(([key, label]) => (
                <th scope="col" key={key}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">All services</th>
              {statistics.map(([key]) => (
                <td key={key}>{number(workload.statistics[key])}</td>
              ))}
            </tr>
            {workload.services.map((item) => (
              <tr key={item.service_index}>
                <th scope="row">Service index {item.service_index}</th>
                {statistics.map(([key]) => (
                  <td key={key}>{number(item[key])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>Service summaries show up to six services with the highest peaks.</p>
    </section>
  );
}
