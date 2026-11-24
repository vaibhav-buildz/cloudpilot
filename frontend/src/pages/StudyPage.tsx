import React from "react";
import studySummary from "../data/study_summary.json";
import { DisclaimerBanner } from "../components/DisclaimerBanner";

export const StudyPage: React.FC = () => {
  const { headline, per_seed_breakdown, methods_summary_time, methods_summary_service } =
    studySummary;

  const getVerdictBadgeClass = (verdict: string) => {
    if (verdict === "SUPPORTED") return "badge-supported";
    if (verdict === "NOT_SUPPORTED") return "badge-not-supported";
    return "badge-mixed";
  };

  return (
    <div className="study-page">
      <DisclaimerBanner />

      <section className="card">
        <h1 className="card-title" style={{ fontSize: "1.4rem" }}>
          Empirical Study Findings (10 Seeds Benchmark)
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.95rem" }}>
          Full results from 10 seeded workloads (200 services, 4,032 steps / 14 days
          per seed, 1% violation target). All numbers are loaded statically from the
          reproducible benchmark study.
        </p>
      </section>

      {/* Headline Verdicts */}
      <div className="grid-3">
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontWeight: 600 }}>H1: Time Split</span>
            <span className={`badge ${getVerdictBadgeClass(headline.h1.verdict)}`}>
              {headline.h1.verdict}
            </span>
          </div>
          <div style={{ fontSize: "1.25rem", fontWeight: 700, margin: "0.5rem 0" }}>
            {headline.h1.support_count}/{headline.h1.total_seeds} seeds
          </div>
          <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
            Median effect: {headline.h1.median_effect_pp.toFixed(2)} pp
            <br />
            95% CI: [{headline.h1.median_ci_lower_pp.toFixed(2)},{" "}
            {headline.h1.median_ci_upper_pp.toFixed(2)}] pp
          </div>
        </div>

        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontWeight: 600 }}>H2: Service Split</span>
            <span className={`badge ${getVerdictBadgeClass(headline.h2.verdict)}`}>
              {headline.h2.verdict}
            </span>
          </div>
          <div style={{ fontSize: "1.25rem", fontWeight: 700, margin: "0.5rem 0" }}>
            {headline.h2.support_count}/{headline.h2.total_seeds} seeds
          </div>
          <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
            Median effect: {headline.h2.median_effect_pp.toFixed(2)} pp
            <br />
            95% CI: [{headline.h2.median_ci_lower_pp.toFixed(2)},{" "}
            {headline.h2.median_ci_upper_pp.toFixed(2)}] pp
          </div>
        </div>

        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontWeight: 600 }}>H3: Safety Bound</span>
            <span className={`badge ${getVerdictBadgeClass(headline.h3.verdict)}`}>
              {headline.h3.verdict}
            </span>
          </div>
          <div style={{ fontSize: "1.25rem", fontWeight: 700, margin: "0.5rem 0" }}>
            {headline.h3.support_count}/{headline.h3.total_seeds} seeds
          </div>
          <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
            Max violation Time: {(headline.h3.max_test_violation_time * 100).toFixed(2)}%
            <br />
            Max violation Service: {(headline.h3.max_test_violation_service * 100).toFixed(2)}%
            <br />
            Threshold: &lt;= 1.50%
          </div>
        </div>
      </div>

      {/* Discussion of the Negative Result */}
      <section className="card">
        <h2 className="card-title">Analysis of the Negative Result</h2>
        <p style={{ lineHeight: 1.6, marginBottom: "0.75rem" }}>
          In our controlled 10-seed evaluation, <strong>H1 is not supported</strong> and{" "}
          <strong>H2 is not supported</strong>. Gradient Boosting Quantile Regression
          (GBR_q95) met the SLA safety bound across all runs (H3 supported), but it did
          not reliably outperform simple moving-window statistical heuristics (such as
          the 48-step rolling maximum or rolling 99th percentile). In both time-series
          and cross-service transfer evaluations, simple statistical baselines achieved
          comparable or superior savings without model training latency or complexity.
        </p>
        <div className="alert alert-info" style={{ marginBottom: "0.75rem" }}>
          <strong>Generator Over-Provisioning Note:</strong> Savings are relative to the
          simulator's static request, which over-provisions (static utilization about
          16%); magnitudes depend on the generator.
        </div>
        <p style={{ fontSize: "0.9rem" }}>
          For detailed discussion of early methodology bugfixes and pre-study deviations,
          consult the official{" "}
          <a
            href="https://github.com/vy979/cloudpilot/blob/main/docs/deviations.md"
            target="_blank"
            rel="noreferrer"
          >
            docs/deviations.md
          </a>{" "}
          log on GitHub.
        </p>
      </section>

      {/* Per-Seed Benchmark Table */}
      <section className="card">
        <h2 className="card-title">Per-Seed Comparison (TIME and SERVICE Splits)</h2>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Seed</th>
                <th>Time Comparator</th>
                <th>Time Comp (Val / Test Viol)</th>
                <th>Time GBR (Val / Test Viol)</th>
                <th>H1 Effect (95% CI)</th>
                <th>Service Comparator</th>
                <th>Service Comp (Val / Test Viol)</th>
                <th>Service GBR (Val / Test Viol)</th>
                <th>H2 Effect (95% CI)</th>
                <th>H3</th>
              </tr>
            </thead>
            <tbody>
              {per_seed_breakdown.map((r) => (
                <tr key={r.seed}>
                  <td style={{ fontWeight: 600 }}>{r.seed}</td>
                  <td>{r.time_comparator}</td>
                  <td>
                    {r.time_comp_val_viol} / {(r.time_comp_test_viol).toFixed(2)}%
                  </td>
                  <td>
                    {r.time_gbr_val_feas} / {(r.time_gbr_test_viol).toFixed(2)}%
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.825rem" }}>
                    {r.h1_effect_pp.toFixed(2)} pp
                    <br />
                    [{r.h1_ci_lower_pp.toFixed(2)}, {r.h1_ci_upper_pp.toFixed(2)}]
                  </td>
                  <td>{r.service_comparator}</td>
                  <td>
                    {r.service_comp_val_viol} / {(r.service_comp_test_viol).toFixed(2)}%
                  </td>
                  <td>
                    {r.service_gbr_val_feas} / {(r.service_gbr_test_viol).toFixed(2)}%
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.825rem" }}>
                    {r.h2_effect_pp.toFixed(2)} pp
                    <br />
                    [{r.h2_ci_lower_pp.toFixed(2)}, {r.h2_ci_upper_pp.toFixed(2)}]
                  </td>
                  <td>
                    <span className="badge badge-supported">{r.h3_verdict}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Median Test Metrics Tables */}
      <div className="grid-2">
        <section className="card">
          <h2 className="card-title">Median Test Metrics: TIME Split</h2>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Method</th>
                  <th>Savings</th>
                  <th>Violation</th>
                  <th>Utilization</th>
                  <th>Feasible</th>
                </tr>
              </thead>
              <tbody>
                {methods_summary_time.map((m) => (
                  <tr key={m.name}>
                    <td style={{ fontWeight: 500 }}>{m.name}</td>
                    <td>{m.median_savings_pct.toFixed(1)}%</td>
                    <td>{m.median_violation_pct.toFixed(2)}%</td>
                    <td>{m.utilization_pct.toFixed(1)}%</td>
                    <td>{m.feasible_count}/10</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="card">
          <h2 className="card-title">Median Test Metrics: SERVICE Split</h2>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Method</th>
                  <th>Savings</th>
                  <th>Violation</th>
                  <th>Utilization</th>
                  <th>Feasible</th>
                </tr>
              </thead>
              <tbody>
                {methods_summary_service.map((m) => (
                  <tr key={m.name}>
                    <td style={{ fontWeight: 500 }}>{m.name}</td>
                    <td>{m.median_savings_pct.toFixed(1)}%</td>
                    <td>{m.median_violation_pct.toFixed(2)}%</td>
                    <td>{m.utilization_pct.toFixed(1)}%</td>
                    <td>{m.feasible_count}/10</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
};
