# CloudPilot 10-Seed Simulation Study Plan

> **Pre-Registration Status**: Written and committed prior to executing the 10-seed simulation study.

## 1. Study Objective & Protocol

This document defines the execution protocol for evaluating the pre-registered hypotheses H1, H2, and H3 established in [docs/hypotheses.md](hypotheses.md).
The protocol evaluates whether the Gradient Boosted Quantile Regressor (`GBR_q95`) configured with deterministic validation safety margins provides superior savings on the TIME split, maintains non-inferiority on the SERVICE split, and satisfies operational feasibility across multiple distinct workload realizations.

All experimental procedures are fixed in advance:
- **No retrospective tuning**: No model hyperparameter, feature set, margin grid, or generator parameter will be modified after running the study.
- **Reporting fidelity**: All empirical results—positive, negative, or mixed—will be recorded and reported exactly as produced.
- **Deviation tracking**: If a genuine bug or defect is discovered, it must be documented in `docs/deviations.md` with date, root cause, and remediation rationale. Any affected seeds must be re-executed with both original and updated results reported side-by-side.

---

## 2. Workload & Simulation Parameters

- **Random Seeds**: Seeds 1 through 10 (`seed ∈ {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}`).
- **Fleet Scale**: $N = 200$ independent microservices per seed.
- **Time Duration**: $T = 4032$ discrete 5-minute intervals ($14$ full days of cluster activity).
- **Target Pooled Violation**: $\alpha = 0.01$ ($1.0\%$ violation threshold on validation splits).
- **Execution Splits**: Each seed evaluates both partitions defined in [docs/hypotheses.md](hypotheses.md):
  1. **TIME Split**: First 60% train ($t \in [288, 2419]$), intermediate 15% validation ($t \in [2419, 3024]$), final 25% held-out test ($t \in [3024, 4032]$) across all 200 services.
  2. **SERVICE Split**: 60% train services ($120$ services), 15% validation services ($30$ services), 25% held-out test services ($50$ services) evaluated over all valid time steps ($t \in [288, 4032]$).

---

## 3. Headline Metrics & Hypothesis Evaluation Criteria

For each hypothesis, performance will be evaluated per seed and aggregated across the 10 seeds:

1. **Per-Seed Support Rate**: Count and percentage of seeds (out of 10) supporting the hypothesis under the decision rules in `docs/hypotheses.md`.
2. **Median Effect & Confidence Interval**:
   - Median treatment effect across seeds: $\text{median}(\Delta_{\text{savings}})$ in percentage points (pp).
   - Median confidence interval: $[\text{median}(CI_{\text{lower}}), \text{median}(CI_{\text{upper}})]$ across the 10 seeds.
3. **Pooled Secondary Check**:
   - A single pooled paired bootstrap resampling across all $10 \times 200 = 2{,}000$ service instances (or all held-out test services across seeds) using seed 42 and 10,000 resamples.

### Summary of Acceptance Rules:
- **H1 (TIME Split)**: Supported on a seed if $CI_{\text{lower}} > 0.0\text{ pp}$.
- **H2 (SERVICE Split)**: Supported on a seed if $CI_{\text{lower}} > -1.0\text{ pp}$ (non-inferiority margin).
- **H3 (Feasibility)**: Supported on a seed if $\text{Violation}_{\text{test, TIME}} \le 1.5\%$ AND $\text{Violation}_{\text{test, SERVICE}} \le 1.5\%$.
- An infeasible model on validation or test is strictly counted as **NOT SUPPORTED**.

---

## 4. Output Artifacts

1. `results/study_seed_<n>.json`: Detailed raw metrics, per-method test stats, and bootstrap outputs for each individual seed $n \in \{1 \dots 10\}$.
2. `results/study_summary.json`: Aggregated metrics, per-seed comparator choices, hypothesis verdicts, median effects, and pooled bootstrap outcomes. (Versioned in git).
3. `docs/results.md`: Complete human-readable Markdown report containing comprehensive tables for TIME and SERVICE splits, headline numbers, and disclaimer banners.
