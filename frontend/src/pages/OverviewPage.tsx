import {
  Activity,
  BookOpen,
  Check,
  Cpu,
  FlaskConical,
  Layers,
  Minus,
  Server,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { Link } from "react-router-dom";
import study from "../data/study_summary.json";
import { AllocationDiagram } from "../components/AllocationDiagram";
import { BenchmarkChart } from "../components/BenchmarkChart";
import { DisclaimerBanner } from "../components/DisclaimerBanner";
import "./overview.css";

export function OverviewPage() {
  const model = study.methods_summary_time.find((m) => m.name === "GBR_q95")!;
  const metrics = [
    {
      name: "CPU savings",
      value: model.savings_pct.toFixed(2) + "%",
      note: "GBR_q95 vs. static · time split",
      icon: Cpu,
    },
    {
      name: "Test violation rate",
      value: model.violation_pct.toFixed(2) + "%",
      note: "GBR_q95 mean · time split",
      icon: Activity,
    },
    {
      name: "Simulated services",
      value: study.config.n_services,
      note: "Per seeded workload",
      icon: Server,
    },
    {
      name: "Allocation policies",
      value: study.methods_summary_time.length,
      note: "Across " + study.config.seeds.length + " benchmark seeds",
      icon: Layers,
    },
  ];
  return (
    <div className="overview-page">
      <section className="overview-hero">
        <div>
          <small className="study-label">
            <i />
            PRE-REGISTERED BENCHMARK
          </small>
          <h1>Research overview</h1>
          <p>
            Explore CPU allocation policies, compare benchmark results, and run
            reproducible cloud workload experiments.
          </p>
          <div className="overview-actions">
            <Link className="btn btn-primary" to="/simulate">
              <FlaskConical size={16} />
              Run simulation
            </Link>
            <Link className="btn btn-secondary" to="/upload">
              <Upload size={16} />
              Upload CSV
            </Link>
          </div>
        </div>
        <AllocationDiagram />
      </section>
      <div className="overview-metrics">
        {metrics.map(({ name, value, note, icon: Icon }) => (
          <div key={name}>
            <span>
              <Icon size={15} />
              {name}
            </span>
            <strong>{value}</strong>
            <small>{note}</small>
          </div>
        ))}
      </div>
      <div className="overview-panels">
        <BenchmarkChart />
        <section className="overview-panel hypotheses">
          <div className="overview-panel-head">
            <div>
              <h2>
                <ShieldCheck size={18} />
                Hypothesis summary
              </h2>
              <p>Pre-registered study outcomes</p>
            </div>
          </div>
          {(["h1", "h2", "h3"] as const).map((key, i) => {
            const h = study.headline[key],
              supported = h.verdict === "SUPPORTED";
            return (
              <div className="hyp-row" key={key}>
                <code>{key.toUpperCase()}</code>
                <div>
                  <strong>
                    {
                      [
                        "Temporal efficiency",
                        "Cross-service transfer",
                        "Safety bound",
                      ][i]
                    }
                  </strong>
                  <small>
                    {h.support_count}/{h.total_seeds} seeds supported
                  </small>
                </div>
                <span className={supported ? "positive" : ""}>
                  {supported ? <Check size={12} /> : <Minus size={12} />}
                  {supported ? "Supported" : "Unsupported"}
                </span>
              </div>
            );
          })}
          <Link className="study-link" to="/study">
            <BookOpen size={15} />
            View study findings
          </Link>
        </section>
      </div>
      <section className="overview-method">
        <h2>Methodology</h2>
        <p>
          CloudPilot compares past-only CPU allocation policies on synthetic
          workloads sampled every five minutes. Safety margins are selected on
          validation data. Held-out time windows and unseen services measure how
          well each policy generalizes.
        </p>
      </section>
      <DisclaimerBanner />
    </div>
  );
}
