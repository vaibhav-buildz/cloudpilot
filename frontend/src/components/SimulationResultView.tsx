import React from "react";
import { SimulationResponse } from "../types/api";
import { AllocationBarChart, AllocationBarItem } from "./AllocationBarChart";

interface Props {
  result: SimulationResponse;
}

export const SimulationResultView: React.FC<Props> = ({ result }) => {
  const timeSplit = result.time_split;
  const comparatorName = timeSplit?.comparator_name || "static";
  const gbrMetrics = timeSplit?.metrics?.["GBR_q95"];
  const compMetrics = timeSplit?.metrics?.[comparatorName];
  const staticMetrics = timeSplit?.metrics?.["static"];

  // Bar chart items: compare relative test savings / allocation proxies
  const chartItems: AllocationBarItem[] = [];
  if (staticMetrics) {
    chartItems.push({
      label: "Static Request",
      value: 100, // baseline 100%
      color: "#94a3b8",
      sublabel: `Violation: ${(staticMetrics.pooled_violation * 100).toFixed(2)}%, Util: ${(staticMetrics.mean_utilization * 100).toFixed(1)}%`,
    });
  }
  if (compMetrics && comparatorName !== "static") {
    chartItems.push({
      label: `Comparator (${comparatorName})`,
      value: Math.max(0, 100 * (1 - compMetrics.pooled_savings)),
      color: "#0284c7",
      sublabel: `Savings: ${(compMetrics.pooled_savings * 100).toFixed(1)}%, Viol: ${(compMetrics.pooled_violation * 100).toFixed(2)}%`,
    });
  }
  if (gbrMetrics) {
    chartItems.push({
      label: "ML (GBR_q95)",
      value: Math.max(0, 100 * (1 - gbrMetrics.pooled_savings)),
      color: timeSplit.is_gbr_feasible ? "#10b981" : "#ef4444",
      sublabel: `Savings: ${(gbrMetrics.pooled_savings * 100).toFixed(1)}%, Viol: ${(gbrMetrics.pooled_violation * 100).toFixed(2)}%`,
    });
  }

  const getVerdictBadge = (supported: boolean) => (
    <span className={`badge ${supported ? "badge-supported" : "badge-not-supported"}`}>
      {supported ? "SUPPORTED" : "NOT SUPPORTED"}
    </span>
  );

  return (
    <div className="simulation-result" style={{ marginTop: "1.5rem" }}>
      <div className="alert alert-info">
        <strong>Run Completed:</strong> Evaluated {result.workload_info.n_services} services
        over {result.workload_info.n_steps} intervals (target violation:{" "}
        {(result.workload_info.target_violation * 100).toFixed(2)}%).
      </div>

      <div className="alert alert-error" style={{ backgroundColor: "var(--warning-bg)", color: "var(--warning)", borderColor: "var(--warning-border)" }}>
        <strong>Simulator Note:</strong> This run used the synthetic generator and simulated evaluation. Real-world results will differ.
      </div>

      <div className="grid-3" style={{ marginTop: "1rem" }}>
        <div className="card">
          <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
            Comparator Policy
          </div>
          <div style={{ fontSize: "1.2rem", fontWeight: 700, margin: "0.25rem 0" }}>
            {comparatorName}
          </div>
          <div style={{ fontSize: "0.85rem" }}>
            GBR Feasible:{" "}
            <strong>{timeSplit?.is_gbr_feasible ? "Yes" : "No"}</strong>
          </div>
        </div>

        <div className="card">
          <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
            H1: Temporal Generalization
          </div>
          <div style={{ margin: "0.25rem 0" }}>
            {timeSplit?.h1 ? getVerdictBadge(timeSplit.h1.supported) : "N/A"}
          </div>
          <div style={{ fontSize: "0.85rem", fontFamily: "var(--font-mono)" }}>
            {timeSplit?.h1?.effect_pp.toFixed(2)} pp [
            {timeSplit?.h1?.ci_lower.toFixed(2)}, {timeSplit?.h1?.ci_upper.toFixed(2)}]
          </div>
        </div>

        <div className="card">
          <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
            H3: Safety SLA Bound
          </div>
          <div style={{ margin: "0.25rem 0" }}>
            {timeSplit?.h3 ? getVerdictBadge(timeSplit.h3.supported) : "N/A"}
          </div>
          <div style={{ fontSize: "0.85rem" }}>
            Violation:{" "}
            {gbrMetrics ? `${(gbrMetrics.pooled_violation * 100).toFixed(2)}%` : "N/A"}
          </div>
        </div>
      </div>

      {chartItems.length > 0 && (
        <AllocationBarChart
          title="Relative Allocated CPU Headroom (% of Static Baseline)"
          items={chartItems}
          unit="%"
        />
      )}

      {/* Methods Metrics Table */}
      {timeSplit?.metrics && (
        <section className="card" style={{ marginTop: "1rem" }}>
          <h3 className="card-title" style={{ fontSize: "1rem" }}>
            Test Performance Across Evaluated Policies (TIME Split)
          </h3>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Method</th>
                  <th>Feasible</th>
                  <th>Margin</th>
                  <th>Test Violation</th>
                  <th>Test Savings</th>
                  <th>Utilization</th>
                  <th>Wastage</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(timeSplit.metrics).map(([name, m]) => (
                  <tr key={name}>
                    <td style={{ fontWeight: name === "GBR_q95" || name === comparatorName ? 600 : 400 }}>
                      {name} {name === comparatorName ? "(Comparator)" : ""}
                    </td>
                    <td>{m.is_feasible ? "Yes" : "No"}</td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>
                      {m.margin !== null ? m.margin.toFixed(3) : "None"}
                    </td>
                    <td>{(m.pooled_violation * 100).toFixed(2)}%</td>
                    <td>{(m.pooled_savings * 100).toFixed(1)}%</td>
                    <td>{(m.mean_utilization * 100).toFixed(1)}%</td>
                    <td>{(m.mean_wastage * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
};
