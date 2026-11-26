import { useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  BookOpen,
  Check,
  ChevronDown,
  CircleCheck,
  CircleMinus,
  CircleX,
  Clock3,
  FileText,
  Layers,
  ListTree,
} from "lucide-react";
import { AllocationBarChart } from "../components/AllocationBarChart";
import study from "../data/study_summary.json";
import "./research.css";

type Split = "time" | "service";
type Policy = (typeof study.methods_summary_time)[number];
type Metric = "median_savings_pct" | "median_violation_pct" | "utilization_pct";
const titles: Record<Metric, string> = {
  median_savings_pct: "Median savings",
  median_violation_pct: "Median violation",
  utilization_pct: "Mean utilization",
};
const { config, headline } = study;
const seedCount = config.seeds.length;
const targetPercent = (100 * config.target_violation).toFixed(0);
const repository =
  "https://github.com/vaibhav-buildz/cloudpilot/blob/main/docs";

function splitResults(split: Split) {
  const hypothesis = split === "time" ? "h1" : "h2";
  return study.per_seed_breakdown.map((row) => ({
    seed: row.seed,
    effect: row[`${hypothesis}_effect_pp`],
    lower: row[`${hypothesis}_ci_lower_pp`],
    upper: row[`${hypothesis}_ci_upper_pp`],
    comparator: row[`${split}_comparator`],
    comparatorVal: row[`${split}_comp_val_viol`],
    comparatorTest: row[`${split}_comp_test_viol`],
    gbrVal: row[`${split}_gbr_val_feas`],
    gbrTest: row[`${split}_gbr_test_viol`],
    verdict: row[`${hypothesis}_verdict`],
    safety: row.h3_verdict,
  }));
}

function verdictLabel(verdict: string) {
  const words = verdict.toLowerCase().replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function ConfidencePlot({
  split,
  rows,
}: {
  split: Split;
  rows: ReturnType<typeof splitResults>;
}) {
  const [selectedSeed, setSelectedSeed] = useState(rows[0].seed);
  const [hoverSeed, setHoverSeed] = useState<number | null>(null);
  const active =
    rows.find((r) => r.seed === (hoverSeed ?? selectedSeed)) ?? rows[0];
  const summary = split === "time" ? headline.h1 : headline.h2;
  const threshold = split === "time" ? 0 : -1;
  const min = Math.floor(Math.min(threshold, ...rows.map((r) => r.lower)));
  const max = Math.ceil(Math.max(0, ...rows.map((r) => r.upper)));
  const position = (n: number) => (100 * (n - min)) / (max - min || 1);
  const tickStep = Math.max(1, Math.ceil((max - min) / 6));
  const ticks = Array.from(
    { length: Math.floor((max - min) / tickStep) + 1 },
    (_, i) => min + i * tickStep,
  );

  return (
    <section className="research-panel research-confidence">
      <div className="research-confidence-copy">
        <h2>Savings difference</h2>
        <p>
          GBR_q95 savings minus the comparator’s savings on held-out workloads,
          in percentage points.
        </p>
        <div className="research-effect">
          <span>Median effect</span>
          <strong>
            {summary.median_effect_pp.toFixed(2)} <small>pp</small>
          </strong>
        </div>
        <p>
          Median interval endpoints{" "}
          <span className="research-mono">
            [{summary.median_ci_lower_pp.toFixed(2)},{" "}
            {summary.median_ci_upper_pp.toFixed(2)}] pp
          </span>
        </p>
        <p>
          The lower bound must exceed <strong>{threshold} pp</strong> to support{" "}
          {split === "time" ? "H1" : "H2"} on a seed.
        </p>
      </div>
      <figure
        className="research-forest"
        aria-label="95% confidence intervals by seed"
      >
        <figcaption>95% confidence intervals by seed</figcaption>
        <div className="research-forest-axis" aria-hidden="true">
          <span>Seed</span>
          <div>
            {ticks.map((t) => (
              <span key={t} style={{ left: `${position(t)}%` }}>
                {t}
              </span>
            ))}
          </div>
        </div>
        <div onMouseLeave={() => setHoverSeed(null)}>
          {rows.map((r) => (
            <button
              type="button"
              key={r.seed}
              className="research-forest-row"
              aria-label={`Seed ${r.seed}, effect ${r.effect.toFixed(2)} pp, 95% interval ${r.lower.toFixed(2)} to ${r.upper.toFixed(2)} pp`}
              aria-pressed={selectedSeed === r.seed}
              data-active={active.seed === r.seed}
              onMouseEnter={() => setHoverSeed(r.seed)}
              onFocus={() => setHoverSeed(null)}
              onClick={() => setSelectedSeed(r.seed)}
            >
              <span>{String(r.seed).padStart(2, "0")}</span>
              <span className="research-forest-track" aria-hidden="true">
                <i
                  className="research-threshold"
                  style={{ left: `${position(threshold)}%` }}
                />
                <i
                  className="research-interval"
                  style={{
                    left: `${position(r.lower)}%`,
                    width: `${position(r.upper) - position(r.lower)}%`,
                  }}
                />
                <i
                  className="research-dot"
                  style={{ left: `${position(r.effect)}%` }}
                />
              </span>
            </button>
          ))}
        </div>
        <div className="research-forest-readout">
          <span>Seed {active.seed}</span>
          <strong>{active.effect.toFixed(2)} pp</strong>
          <span>
            95% CI [{active.lower.toFixed(2)}, {active.upper.toFixed(2)}]
          </span>
        </div>
      </figure>
    </section>
  );
}

const columns = [
  ["name", "Policy"],
  ["median_savings_pct", "Median savings"],
  ["median_violation_pct", "Median violation"],
  ["utilization_pct", "Mean utilization"],
  ["wastage_pct", "Mean wastage"],
  ["feasible_count", "Feasible seeds"],
] as const;
type SortKey = (typeof columns)[number][0];

function PolicyTable({
  policies,
  split,
}: {
  policies: Policy[];
  split: Split;
}) {
  const [sort, setSort] = useState<{ key: SortKey; ascending: boolean }>({
    key: "median_savings_pct",
    ascending: false,
  });
  const sorted = [...policies].sort((a, b) => {
    const key = sort.key;
    const order =
      key === "name" ? a.name.localeCompare(b.name) : a[key] - b[key];
    return (sort.ascending ? order : -order) || a.name.localeCompare(b.name);
  });
  return (
    <section className="research-panel">
      <div className="research-panel-head">
        <div>
          <h2>Policy comparison</h2>
          <p>
            Test metrics across {seedCount} seeds. Feasibility uses the{" "}
            {targetPercent}% validation target.
          </p>
        </div>
        <span className="research-count">{policies.length} policies</span>
      </div>
      <div
        className="research-scroll"
        tabIndex={0}
        role="region"
        aria-label="Scrollable policy metrics"
      >
        <table
          className="research-table"
          aria-label={`Policy comparison for ${split} split`}
        >
          <thead>
            <tr>
              {columns.map(([key, label]) => {
                const selected = key === sort.key;
                const SortIcon = selected
                  ? sort.ascending
                    ? ArrowUp
                    : ArrowDown
                  : ArrowUpDown;
                return (
                  <th
                    key={key}
                    scope="col"
                    aria-sort={
                      selected
                        ? sort.ascending
                          ? "ascending"
                          : "descending"
                        : undefined
                    }
                  >
                    <button
                      type="button"
                      onClick={() =>
                        setSort({
                          key,
                          ascending: selected
                            ? !sort.ascending
                            : key === "name" || key === "median_violation_pct",
                        })
                      }
                    >
                      {label}
                      <SortIcon size={13} aria-hidden="true" />
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.map((policy) => {
              const Feasibility =
                policy.feasible_count === seedCount
                  ? CircleCheck
                  : policy.feasible_count === 0
                    ? CircleX
                    : CircleMinus;
              return (
                <tr key={policy.name}>
                  <th scope="row">
                    <span>{policy.name}</span>
                    <small>{policy.category}</small>
                  </th>
                  <td>{policy.median_savings_pct.toFixed(2)}%</td>
                  <td>{policy.median_violation_pct.toFixed(2)}%</td>
                  <td>{policy.utilization_pct.toFixed(2)}%</td>
                  <td>{policy.wastage_pct.toFixed(2)}%</td>
                  <td>
                    <span className="research-feasibility">
                      <Feasibility size={14} aria-hidden="true" />
                      {policy.feasible_count}/{seedCount}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="research-footnote">
        The benchmark assigns zero savings, utilization, and wastage to
        validation-infeasible runs when computing these aggregates.
      </p>
    </section>
  );
}

export function StudyPage() {
  const [split, setSplit] = useState<Split>("time");
  const [metric, setMetric] = useState<Metric>("median_savings_pct");
  const policies =
    split === "time"
      ? study.methods_summary_time
      : study.methods_summary_service;
  const rows = splitResults(split);
  const chartItems = policies
    .filter((m) => m.feasible_count === seedCount)
    .sort((a, b) => b[metric] - a[metric])
    .map((m) => ({
      label: m.name,
      value: m[metric],
      color: m.name === "GBR_q95" ? "var(--accent)" : "var(--muted)",
      sublabel: `${m.category} · Mean savings ${m.savings_pct.toFixed(2)}% · Mean test violation ${m.violation_pct.toFixed(2)}% · Feasible on ${m.feasible_count}/${seedCount} seeds`,
    }));
  const hypotheses = [
    {
      key: "H1",
      name: "Time split",
      data: headline.h1,
      detail: "Higher savings on future intervals",
    },
    {
      key: "H2",
      name: "Service split",
      data: headline.h2,
      detail: "Non-inferiority on unseen services",
    },
    {
      key: "H3",
      name: "Safety bound",
      data: headline.h3,
      detail: `Test violation ≤ ${(100 * headline.h3.threshold).toFixed(1)}% on both splits`,
    },
  ];

  return (
    <div className="research-page">
      <header className="research-header">
        <div>
          <h1>Research study</h1>
          <p>
            Compare CPU allocation policies across {seedCount} seeded workloads,
            each with {config.n_services} services and{" "}
            {config.n_steps.toLocaleString("en-US")} simulated intervals.
          </p>
        </div>
        <div
          className="research-switch"
          role="group"
          aria-label="Benchmark split"
        >
          <button
            type="button"
            aria-pressed={split === "time"}
            onClick={() => setSplit("time")}
          >
            <Clock3 size={15} aria-hidden="true" />
            TIME
          </button>
          <button
            type="button"
            aria-pressed={split === "service"}
            onClick={() => setSplit("service")}
          >
            <Layers size={15} aria-hidden="true" />
            SERVICE
          </button>
        </div>
      </header>

      <div className="research-top-grid">
        <section className="research-panel research-performance">
          <div className="research-panel-head">
            <div>
              <h2>Policy performance</h2>
              <p>
                {split === "time"
                  ? "Future intervals on known services"
                  : "Held-out services"}{" "}
                · Policies feasible on every seed
              </p>
            </div>
            <label className="research-select">
              <span className="research-sr">Performance metric</span>
              <select
                value={metric}
                onChange={(event) => setMetric(event.target.value as Metric)}
              >
                {Object.entries(titles).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
              <ChevronDown size={14} aria-hidden="true" />
            </label>
          </div>
          <AllocationBarChart
            key={`${split}-${metric}`}
            title={`${titles[metric]} by policy on the ${split} split`}
            unit="%"
            items={chartItems}
          />
          <div className="research-legend">
            <span>GBR_q95</span>
            <span>Baselines</span>
          </div>
        </section>
        <section className="research-panel research-verdicts">
          <div className="research-panel-head">
            <h2>Hypothesis verdicts</h2>
          </div>
          {hypotheses.map(({ key, name, data, detail }) => (
            <div key={key} className="research-verdict">
              <div className="research-verdict-main">
                <h3>
                  <span>{key}</span> {name}
                </h3>
                <span className="research-status">
                  {data.verdict === "SUPPORTED" && (
                    <Check size={12} aria-hidden="true" />
                  )}
                  {verdictLabel(data.verdict)}
                </span>
              </div>
              <p>
                {detail} · {data.support_count}/{data.total_seeds} seeds
                supported
              </p>
            </div>
          ))}
        </section>
      </div>

      <ConfidencePlot split={split} rows={rows} />
      <PolicyTable policies={policies} split={split} />

      <details className="research-disclosure research-panel">
        <summary>
          <ListTree size={17} aria-hidden="true" />
          <h2>Per-seed comparison</h2>
          <ChevronDown size={16} aria-hidden="true" />
        </summary>
        <div
          className="research-scroll"
          role="region"
          tabIndex={0}
          aria-label="Scrollable per-seed results"
        >
          <table
            className="research-table"
            aria-label={`Per-seed results for ${split} split`}
          >
            <thead>
              <tr>
                <th>Seed</th>
                <th>Comparator</th>
                <th>
                  Comparator violation
                  <br />
                  Validation / Test
                </th>
                <th>
                  GBR_q95 violation
                  <br />
                  Validation / Test
                </th>
                <th>Effect and 95% CI (pp)</th>
                <th>{split === "time" ? "H1" : "H2"}</th>
                <th>H3</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.seed}>
                  <th scope="row">{r.seed}</th>
                  <td>{r.comparator}</td>
                  <td>
                    {r.comparatorVal} / {r.comparatorTest.toFixed(2)}%
                  </td>
                  <td>
                    {r.gbrVal} / {r.gbrTest.toFixed(2)}%
                  </td>
                  <td>
                    {r.effect.toFixed(2)} [{r.lower.toFixed(2)},{" "}
                    {r.upper.toFixed(2)}]
                  </td>
                  <td>{verdictLabel(r.verdict)}</td>
                  <td>{verdictLabel(r.safety)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <details className="research-disclosure research-panel">
        <summary>
          <BookOpen size={17} aria-hidden="true" />
          <h2>Methodology and interpretation</h2>
          <ChevronDown size={16} aria-hidden="true" />
        </summary>
        <div className="research-method">
          <h3>Study design</h3>
          <p>
            Each seed generates {config.n_steps.toLocaleString("en-US")}{" "}
            five-minute intervals per service. The TIME split partitions
            intervals chronologically. The SERVICE split holds out service IDs.
            Each uses 60% for training, 15% for validation, and 25% for testing.
          </p>
          <p>
            The comparator is the baseline with the highest validation savings
            among those meeting the {targetPercent}% validation violation
            target. Each interval estimate uses 10,000 paired bootstrap
            resamples across held-out services.
          </p>
          <h3>Analysis of the negative result</h3>
          <p>
            In this {seedCount}-seed evaluation, the rolling maximum saved more
            CPU than GBR_q95 on the median seed in both splits. Neither H1 nor
            H2 met its decision rule on any seed. GBR_q95 met H3 on every seed,
            with maximum test violations of{" "}
            {(100 * headline.h3.max_test_violation_time).toFixed(2)}% on TIME
            and {(100 * headline.h3.max_test_violation_service).toFixed(2)}% on
            SERVICE.
          </p>
          <h3>Generator over-provisioning</h3>
          <p>
            Savings are relative to the simulator’s static request. Its mean
            TIME-split utilization is{" "}
            {study.methods_summary_time
              .find((m) => m.name === "static")
              ?.utilization_pct.toFixed(2)}
            %. The magnitude of savings depends on the synthetic workload
            generator.
          </p>
          <div className="research-docs">
            <a
              href={`${repository}/method.md`}
              target="_blank"
              rel="noreferrer"
            >
              <FileText size={15} aria-hidden="true" />
              Full methodology
            </a>
            <a
              href={`${repository}/deviations.md`}
              target="_blank"
              rel="noreferrer"
            >
              <FileText size={15} aria-hidden="true" />
              Study deviations
            </a>
          </div>
        </div>
      </details>
    </div>
  );
}
