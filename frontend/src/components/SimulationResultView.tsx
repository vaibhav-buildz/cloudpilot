import {
  ChartNoAxesColumn,
  Check,
  CircleMinus,
  Database,
  Download,
  FlaskConical,
  Timer,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import type { HypothesisVerdict, SimulationResponse } from "../types/api";
import { AllocationBarChart } from "./AllocationBarChart";
import "../pages/experiments.css";

interface Props {
  result: SimulationResponse;
  source?: string;
  persisted?: boolean;
}

const percent = (value: number) => `${(100 * value).toFixed(2)}%`;
const pp = (value: number) => (100 * value).toFixed(2);

function Verdict({ value }: { value: string }) {
  const supported = value.startsWith("SUPPORTED");
  const Icon = supported ? Check : CircleMinus;
  const reason = value.slice(
    supported ? "SUPPORTED".length : "NOT_SUPPORTED".length,
  );
  return (
    <span className="exp-verdict">
      <Icon size={14} aria-hidden="true" />
      {supported ? "Supported" : "Not supported"}
      {reason}
    </span>
  );
}

function EfficiencyFinding({
  title,
  test,
}: {
  title: string;
  test: HypothesisVerdict;
}) {
  return (
    <article>
      <h4>{title}</h4>
      <Verdict value={test.verdict} />
      <p>
        Savings difference <b>{pp(test.estimate)} pp</b>
      </p>
      <small>
        95% CI [{pp(test.ci_lower)}, {pp(test.ci_upper)}] pp
      </small>
    </article>
  );
}

function downloadResult(result: SimulationResponse) {
  const blob = new Blob([JSON.stringify(result, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `cloudpilot-${result.run_id ?? "experiment"}.json`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function SimulationResultView({ result, source, persisted }: Props) {
  const [split, setSplit] = useState<"TIME" | "SERVICE">("TIME");
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (!persisted) heading.current?.focus();
  }, [result, persisted]);

  const exportButton = (
    <button
      type="button"
      className="btn btn-secondary"
      onClick={() => downloadResult(result)}
    >
      <Download size={15} aria-hidden="true" />
      Export JSON
    </button>
  );
  if (
    !result.parameters ||
    !result.time_split?.methods ||
    !result.service_split?.methods
  ) {
    return (
      <section className="exp-panel exp-section">
        <h3>Experiment results</h3>
        <p>
          This record has incomplete split data. Its recorded fields are
          available in the export.
        </p>
        {exportButton}
      </section>
    );
  }

  const comparison =
    split === "TIME" ? result.time_split : result.service_split;
  const params = result.parameters;
  const saved = persisted ?? result.saved;
  const chartItems = Object.entries(comparison.methods)
    .filter(([, method]) => method.is_feasible)
    .sort(([, a], [, b]) => b.savings - a.savings)
    .map(([name, method]) => ({
      label: name,
      value: (1 - method.savings) * 100,
      color:
        name === "GBR_q95"
          ? "var(--accent)"
          : name === comparison.comparator
            ? "var(--text)"
            : "var(--muted)",
      sublabel: `${percent(method.savings)} savings · ${percent(method.violation_rate)} test violation`,
    }));

  return (
    <section className="exp-result" aria-label="Experiment results">
      <header className="exp-result-heading">
        <div>
          <h2 tabIndex={-1} ref={heading}>
            Experiment results
          </h2>
          <p>
            {source === "csv"
              ? "CSV workload"
              : source === "simulated"
                ? "Synthetic workload"
                : "Workload"}{" "}
            · {params.n_services} services · {params.n_steps.toLocaleString()}{" "}
            steps · {percent(params.target_violation)} target
          </p>
        </div>
        {exportButton}
      </header>
      <div className="exp-receipt">
        <span>
          <Timer size={15} aria-hidden="true" />
          Engine time <b>{result.execution_time_seconds.toFixed(2)} s</b>
        </span>
        <span>
          <Database size={15} aria-hidden="true" />
          {saved === true
            ? "Saved to history"
            : saved === false
              ? "Run completed without a history save"
              : "Save status unavailable"}
          {saved && result.run_id && !persisted && (
            <Link to={`/history/${encodeURIComponent(result.run_id)}`}>
              View run
            </Link>
          )}
        </span>
      </div>
      <div className="exp-panel">
        <header className="exp-panel-heading exp-split-heading">
          <ChartNoAxesColumn aria-hidden="true" />
          <h3>Allocation policies</h3>
          <div className="exp-split" role="group" aria-label="Result split">
            {(["TIME", "SERVICE"] as const).map((key) => (
              <button
                type="button"
                key={key}
                aria-pressed={key === split}
                onClick={() => setSplit(key)}
              >
                {key}
              </button>
            ))}
          </div>
        </header>
        <div className="exp-section">
          <p className="exp-context">
            <b>{split === "TIME" ? "Future intervals" : "Unseen services"}</b> ·
            Comparator <code>{comparison.comparator}</code>
            {!comparison.comparator_is_feasible && " (infeasible fallback)"}
          </p>
          {chartItems.length > 0 && (
            <AllocationBarChart
              title="Allocated CPU relative to static reservation"
              items={chartItems}
              unit="%"
            />
          )}
        </div>
        <div
          className="exp-table-wrap"
          tabIndex={0}
          role="region"
          aria-label={`${split} policy comparison`}
        >
          <table className="exp-table">
            <caption className="sr-only">
              Held-out {split} metrics and validation feasibility
            </caption>
            <thead>
              <tr>
                {[
                  "Policy",
                  "Validation",
                  "Margin",
                  "Violation",
                  "Savings",
                  "Utilization",
                  "Wastage",
                ].map((label) => (
                  <th key={label} scope="col">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(comparison.methods).map(([name, method]) => (
                <tr key={name}>
                  <th scope="row">{name}</th>
                  <td>{method.is_feasible ? "Feasible" : "Infeasible"}</td>
                  <td>
                    {method.margin_value == null
                      ? "—"
                      : method.margin_type === "additive"
                        ? `+${method.margin_value.toFixed(2)} pp`
                        : `×${method.margin_value.toFixed(2)}`}
                  </td>
                  <td>{percent(method.violation_rate)}</td>
                  {[method.savings, method.utilization, method.wastage].map(
                    (value, i) => (
                      <td key={i}>
                        {method.is_feasible ? percent(value) : "—"}
                      </td>
                    ),
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="exp-table-note">
          Savings, utilization and wastage are reported for validation-feasible
          policies.
        </p>
      </div>
      <section className="exp-panel">
        <header className="exp-panel-heading">
          <FlaskConical aria-hidden="true" />
          <h3>Hypothesis analysis</h3>
        </header>
        <div className="exp-hypotheses">
          {result.time_split.h1 && (
            <EfficiencyFinding
              title="H1 · Temporal efficiency"
              test={result.time_split.h1}
            />
          )}
          {result.service_split.h2 && (
            <EfficiencyFinding
              title="H2 · Cross-service transfer"
              test={result.service_split.h2}
            />
          )}
          {result.h3 && (
            <article>
              <h4>H3 · Violation bound</h4>
              <Verdict value={result.h3.verdict} />
              <p>
                TIME <b>{percent(result.h3.test_violation_time)}</b> · SERVICE{" "}
                <b>{percent(result.h3.test_violation_service)}</b>
              </p>
              <small>
                Maximum {percent(result.h3.threshold)} on each split
              </small>
            </article>
          )}
        </div>
      </section>
      {result.disclaimer && <p className="exp-note">{result.disclaimer}</p>}
    </section>
  );
}
