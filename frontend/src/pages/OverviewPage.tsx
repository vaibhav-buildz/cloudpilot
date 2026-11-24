import React from "react";
import { Link } from "react-router-dom";
import { DisclaimerBanner } from "../components/DisclaimerBanner";

export const OverviewPage: React.FC = () => {
  return (
    <div className="overview-page">
      <DisclaimerBanner />

      <section className="card">
        <h1 className="card-title" style={{ fontSize: "1.5rem" }}>
          CloudPilot: ML-Based CPU Allocation Research
        </h1>
        <p style={{ marginTop: "0.5rem", color: "var(--text-muted)", fontSize: "1rem" }}>
          CloudPilot is an experimental right-sizing framework exploring whether
          machine learning models can safely reduce CPU allocation overhead for
          cloud services compared to robust rolling statistical baselines.
        </p>
      </section>

      <section className="card">
        <h2 className="card-title">Methodology</h2>
        <p style={{ lineHeight: 1.6 }}>
          CPU demand is evaluated across discrete 5-minute sampling intervals under
          stringent SLA constraints (pooled violation rate target of 1% or less).
          Workloads undergo dual validation schemes: a <strong>TIME split</strong>{" "}
          (evaluating future held-out time windows on observed services) and a{" "}
          <strong>SERVICE split</strong> (evaluating completely unseen services).
          Candidate methods include fixed static reservations, rolling statistical
          heuristics (EWMA, rolling 99th percentile, rolling maximum), and
          supervised learning models (Linear Regression, Decision Tree, Random
          Forest, Gradient Boosting, and quantile regression GBR_q95). Every policy
          selects a safety margin on a validation grid; only policies meeting the
          validation target qualify as feasible comparators on the test set.
        </p>
      </section>

      <div className="grid-2">
        <div className="card">
          <h2 className="card-title">Benchmark Study Findings</h2>
          <p style={{ color: "var(--text-muted)", marginBottom: "1rem" }}>
            Review the 10-seed pre-registered study evaluating hypotheses H1
            (temporal generalization), H2 (cross-service transfer), and H3 (SLA
            safety bounds).
          </p>
          <Link to="/study" className="btn btn-primary">
            View Study Findings
          </Link>
        </div>

        <div className="card">
          <h2 className="card-title">Interactive Simulator</h2>
          <p style={{ color: "var(--text-muted)", marginBottom: "1rem" }}>
            Execute custom simulations with parameterized service counts, time
            horizons, and target violation constraints, or upload custom workload
            CSVs.
          </p>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <Link to="/simulate" className="btn btn-primary">
              Run Simulation
            </Link>
            <Link to="/upload" className="btn btn-secondary">
              Upload Workload CSV
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
