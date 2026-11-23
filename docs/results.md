# CloudPilot 10-Seed Simulation Study Results

> **Simulated data. Results describe the simulator, not real clouds.**

## 1. Headline Findings

- **H1 (TIME Split, Superiority)**: **MIXED/NOT_SUPPORTED** (0/10 seeds supported).  
  - Median savings advantage over Comparator: **-2.53 pp** (95% median CI: [-3.68 pp, -1.31 pp]).  
  - Secondary pooled paired bootstrap: **-2.19 pp** (95% CI: [-2.58 pp, -1.82 pp], p < 0.0001).

- **H2 (SERVICE Split, Non-Inferiority)**: **MIXED/NOT_SUPPORTED** (0/10 seeds supported within -1.0 pp margin).  
  - Median savings difference on unseen services: **-0.99 pp** (95% median CI: [-3.34 pp, +1.27 pp]).  
  - Secondary pooled paired bootstrap: **-0.93 pp** (95% CI: [-1.60 pp, -0.26 pp], p = 0.0062).

- **H3 (Operational Feasibility)**: **SUPPORTED** (10/10 seeds supported with $\le 1.5\%$ violation).  
  - Max test violation on TIME split: **1.03%**.  
  - Max test violation on SERVICE split: **1.14%**.

---

## 2. Average Performance by Allocation Policy (TIME Split)

| Policy | Category | Savings (%) | Violation (%) | Utilization (%) | Wastage (%) | Feasible Seeds |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `GBR_q95` | ML Model | 54.48% | 0.97% | 35.54% | 64.69% | 10/10 |
| `LR` | ML Model | 0.00% | 38.86% | 0.00% | 0.00% | 0/10 |
| `DT` | ML Model | 0.00% | 39.80% | 0.00% | 0.00% | 0/10 |
| `RF` | ML Model | 0.00% | 38.79% | 0.00% | 0.00% | 0/10 |
| `GB` | ML Model | 0.00% | 37.49% | 0.00% | 0.00% | 0/10 |
| `rolling_max_48` | Baseline | 56.68% | 1.08% | 37.34% | 63.13% | 10/10 |
| `rolling_p99` | Baseline | 35.95% | 0.64% | 25.26% | 74.84% | 10/10 |
| `static` | Baseline | 0.00% | 0.00% | 16.18% | 83.82% | 10/10 |
| `ewma` | Baseline | 0.00% | 39.19% | 0.00% | 0.00% | 0/10 |

---

## 3. Average Performance on Unseen Services (SERVICE Split)

| Policy | Category | Savings (%) | Violation (%) | Utilization (%) | Wastage (%) | Feasible Seeds |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `GBR_q95` | ML Model | 52.79% | 0.98% | 37.04% | 63.19% | 10/10 |
| `GB` | ML Model | 21.45% | 23.57% | 15.20% | 24.91% | 4/10 |
| `LR` | ML Model | 16.13% | 27.49% | 11.50% | 18.58% | 3/10 |
| `DT` | ML Model | 16.04% | 28.53% | 11.43% | 18.65% | 3/10 |
| `RF` | ML Model | 16.04% | 27.90% | 11.42% | 18.66% | 3/10 |
| `rolling_max_48` | Baseline | 53.74% | 0.98% | 37.79% | 62.65% | 10/10 |
| `rolling_p99` | Baseline | 37.50% | 0.97% | 27.95% | 72.19% | 10/10 |
| `ewma` | Baseline | 10.54% | 31.38% | 7.42% | 12.63% | 2/10 |
| `static` | Baseline | 0.00% | 0.00% | 17.47% | 82.53% | 10/10 |

---

## 4. Per-Seed Detailed Breakdown

| Seed | TIME Comp | H1 Verdict | H1 Effect (CI) | SERVICE Comp | H2 Verdict | H2 Effect (CI) | H3 |
| :---: | :--- | :---: | :--- | :--- | :---: | :--- | :---: |
| 1 | `rolling_max_48` | NOT_SUPPORTED | -2.80 pp [-3.96, -1.63] | `rolling_max_48` | NOT_SUPPORTED | -2.48 pp [-3.90, -0.96] | SUPPORTED |
| 2 | `rolling_max_48` | NOT_SUPPORTED | -2.88 pp [-4.09, -1.68] | `rolling_max_48` | NOT_SUPPORTED | -0.39 pp [-2.45, +1.69] | SUPPORTED |
| 3 | `rolling_max_48` | NOT_SUPPORTED | -1.43 pp [-2.63, -0.23] | `rolling_max_48` | NOT_SUPPORTED | -1.88 pp [-3.75, +0.00] | SUPPORTED |
| 4 | `rolling_max_48` | NOT_SUPPORTED | -1.35 pp [-2.57, -0.16] | `rolling_max_48` | NOT_SUPPORTED | -2.99 pp [-4.75, -1.19] | SUPPORTED |
| 5 | `rolling_max_48` | NOT_SUPPORTED | -2.11 pp [-3.34, -0.87] | `rolling_max_48` | NOT_SUPPORTED | +0.95 pp [-1.08, +3.02] | SUPPORTED |
| 6 | `rolling_max_48` | NOT_SUPPORTED | -2.68 pp [-3.87, -1.52] | `rolling_max_48` | NOT_SUPPORTED | -1.54 pp [-3.62, +0.51] | SUPPORTED |
| 7 | `rolling_max_48` | NOT_SUPPORTED | -2.54 pp [-3.77, -1.31] | `rolling_max_48` | NOT_SUPPORTED | -1.05 pp [-3.70, +1.44] | SUPPORTED |
| 8 | `rolling_max_48` | NOT_SUPPORTED | -2.54 pp [-3.63, -1.45] | `rolling_max_48` | NOT_SUPPORTED | -0.06 pp [-2.36, +2.14] | SUPPORTED |
| 9 | `rolling_max_48` | NOT_SUPPORTED | -2.51 pp [-3.73, -1.31] | `rolling_max_48` | NOT_SUPPORTED | +0.90 pp [-1.43, +2.96] | SUPPORTED |
| 10 | `rolling_max_48` | NOT_SUPPORTED | -1.10 pp [-2.32, +0.11] | `rolling_max_48` | NOT_SUPPORTED | -0.92 pp [-3.06, +1.10] | SUPPORTED |
