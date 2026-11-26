import { useState } from "react";
import { Activity } from "lucide-react";
import study from "../data/study_summary.json";

type Split = "time" | "service";

export function BenchmarkChart() {
  const [split, setSplit] = useState<Split>("time");
  const [inspected, setInspected] = useState<number | null>(null);
  const [cursor, setCursor] = useState(0);
  const points = study.per_seed_breakdown.map((row) => ({
    seed: row.seed,
    model: row[`${split}_gbr_test_viol`],
    baseline: row[`${split}_comp_test_viol`],
    comparator: row[`${split}_comparator`],
  }));
  const baselineName = points.every((p) => p.comparator === "rolling_max_48")
    ? "Rolling max (48)"
    : "Selected baseline";
  const values = points.flatMap((p) => [p.model, p.baseline]);
  const low = Math.floor(Math.min(...values) * 10);
  const high = Math.max(low + 1, Math.ceil(Math.max(...values) * 10));
  const ticks = Array.from({ length: high - low + 1 }, (_, i) => high - i);
  const x = (i: number) => (i * 100) / (points.length - 1);
  const y = (value: number) => ((high - value * 10) * 100) / (high - low);
  const trace = (metric: "model" | "baseline") =>
    points.map((p, i) => `${i ? "L" : "M"}${x(i)} ${y(p[metric])}`).join(" ");
  const modelPath = trace("model");
  const point = inspected === null ? undefined : points[inspected];
  function inspect(index: number) {
    setInspected(index);
    setCursor(index);
  }

  return (
    <section
      className="benchmark-panel overview-panel"
      aria-labelledby="performance-title"
    >
      <div className="overview-panel-head">
        <div>
          <h2 id="performance-title">
            <Activity size={18} />
            Allocation performance
          </h2>
          <p>Pooled test violation rate by study seed</p>
        </div>
        <div className="split-toggle" role="group" aria-label="Benchmark split">
          {(["time", "service"] as const).map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={split === s}
              onClick={() => {
                setSplit(s);
                setInspected(null);
              }}
            >
              {s === "time" ? "Time" : "Service"}
            </button>
          ))}
        </div>
      </div>
      <div className="chart-body">
        <div className="chart-legend">
          <span>
            <i className="legend-model" />
            GBR_q95
          </span>
          <span>
            <i className="legend-base" />
            {baselineName}
          </span>
        </div>
        <div
          className="benchmark-plot"
          role="group"
          aria-label={`${split} split test violation rate chart`}
        >
          <div className="plot-axis" aria-hidden="true">
            {ticks.map((v) => (
              <span key={v} style={{ top: `${y(v / 10)}%` }}>
                {(v / 10).toFixed(1)}%
              </span>
            ))}
          </div>
          <div
            className="plot-area"
            onPointerMove={(event) => {
              const bounds = event.currentTarget.getBoundingClientRect();
              if (bounds.width)
                inspect(
                  Math.max(
                    0,
                    Math.min(
                      points.length - 1,
                      Math.round(
                        ((event.clientX - bounds.left) / bounds.width) *
                          (points.length - 1),
                      ),
                    ),
                  ),
                );
            }}
            onPointerLeave={(event) => {
              if (!event.currentTarget.contains(document.activeElement))
                setInspected(null);
            }}
          >
            <svg
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <defs>
                <linearGradient id="series-fill" x1="0" x2="0" y1="0" y2="1">
                  <stop stopColor="var(--accent)" stopOpacity=".19" />
                  <stop
                    offset="1"
                    stopColor="var(--accent)"
                    stopOpacity=".015"
                  />
                </linearGradient>
              </defs>
              {ticks.map((v) => (
                <line
                  className="plot-grid"
                  key={v}
                  x1="0"
                  x2="100"
                  y1={y(v / 10)}
                  y2={y(v / 10)}
                />
              ))}
              <path d={`${modelPath} L100 100 H0 Z`} fill="url(#series-fill)" />
              <path className="plot-base" d={trace("baseline")} fill="none" />
              <path className="plot-model" d={modelPath} fill="none" />
            </svg>
            {points.map((p, i) => (
              <span
                className="data-marker"
                key={p.seed}
                style={{ left: `${x(i)}%`, top: `${y(p.model)}%` }}
              />
            ))}
            {inspected !== null && point && (
              <>
                <i
                  className="plot-crosshair"
                  style={{ left: `${x(inspected)}%` }}
                />
                <div
                  className={`plot-tip ${x(inspected) > 53 ? "tip-left" : ""}`}
                  style={{ left: `${x(inspected)}%` }}
                >
                  <b>Seed {point.seed}</b>
                  <span>
                    GBR_q95 <strong>{point.model.toFixed(3)}%</strong>
                  </span>
                  <span>
                    {point.comparator}{" "}
                    <strong>{point.baseline.toFixed(3)}%</strong>
                  </span>
                </div>
              </>
            )}
            <input
              className="chart-scrubber"
              type="range"
              min={0}
              max={points.length - 1}
              value={cursor}
              aria-label="Inspect study seed"
              aria-valuetext={`Seed ${points[cursor].seed}. GBR_q95 ${points[cursor].model.toFixed(3)} percent. ${baselineName} ${points[cursor].baseline.toFixed(3)} percent.`}
              onFocus={() => setInspected(cursor)}
              onBlur={() => setInspected(null)}
              onChange={(event) => inspect(Number(event.target.value))}
              onKeyDown={(event) => {
                if (event.key === "Escape") setInspected(null);
              }}
            />
          </div>
          <div className="seed-axis" aria-hidden="true">
            {points.map((p, i) => (
              <span key={p.seed} style={{ left: `${x(i)}%` }}>
                {String(p.seed).padStart(2, "0")}
              </span>
            ))}
          </div>
        </div>
        <div className="plot-caption">Study seed</div>
      </div>
    </section>
  );
}
