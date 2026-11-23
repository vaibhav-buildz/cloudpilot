# CloudPilot 10-Seed Simulation Study Results

> **Simulated data. Results describe the simulator, not real clouds.**

## 1. Headline Findings

- **H1 (TIME Split, Superiority)**: **MIXED/NOT_SUPPORTED** (8/10 seeds supported).  
  - Median savings advantage over Comparator: **+79.57 pp** (95% median CI: [+68.33 pp, +92.80 pp]).  
  - Secondary pooled paired bootstrap: **+95.20 pp** (95% CI: [+89.87 pp, +100.67 pp], p = 0.0000).

- **H2 (SERVICE Split, Non-Inferiority)**: **MIXED/NOT_SUPPORTED** (6/10 seeds supported within -1.0 pp margin).  
  - Median savings difference on unseen services: **+70.84 pp** (95% median CI: [+50.52 pp, +91.52 pp]).  
  - Secondary pooled paired bootstrap: **+80.62 pp** (95% CI: [+72.97 pp, +88.65 pp], p = 0.0000).

- **H3 (Operational Feasibility)**: **SUPPORTED** (10/10 seeds supported with $\le 1.5\%$ violation).  
  - Max test violation on TIME split: **1.00%**.  
  - Max test violation on SERVICE split: **1.12%**.

---

## 2. Average Performance by Allocation Policy (TIME Split)

| Policy | Category | Savings (%) | Violation (%) | Utilization (%) | Wastage (%) | Feasible Seeds |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `GBR_q95` | ML Model | 54.36% | 0.96% | 35.44% | 64.79% | 8/10 |
| `rolling_p99` | Baseline | 6.14% | 4.35% | 10.74% | 49.35% | 6/10 |
| `LR` | ML Model | 0.00% | 38.85% | 0.00% | 0.00% | 0/10 |
| `DT` | ML Model | 0.00% | 39.83% | 0.00% | 0.00% | 0/10 |
| `RF` | ML Model | 0.00% | 38.87% | 0.00% | 0.00% | 0/10 |
| `GB` | ML Model | 0.00% | 37.56% | 0.00% | 0.00% | 0/10 |
| `static` | Baseline | 0.00% | 4.00% | 16.18% | 84.50% | 0/10 |
| `rolling_max_48` | Baseline | 0.00% | 25.33% | 0.00% | 0.00% | 0/10 |
| `ewma` | Baseline | 0.00% | 46.72% | 0.00% | 0.00% | 0/10 |

---

## 3. Average Performance on Unseen Services (SERVICE Split)

| Policy | Category | Savings (%) | Violation (%) | Utilization (%) | Wastage (%) | Feasible Seeds |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `GBR_q95` | ML Model | 52.86% | 0.98% | 37.10% | 63.14% | 6/10 |
| `GB` | ML Model | 21.45% | 23.55% | 15.20% | 24.91% | 1/10 |
| `LR` | ML Model | 16.13% | 27.40% | 11.50% | 18.58% | 0/10 |
| `RF` | ML Model | 16.04% | 27.91% | 11.42% | 18.66% | 0/10 |
| `DT` | ML Model | 15.99% | 28.66% | 11.39% | 18.69% | 0/10 |
| `rolling_p99` | Baseline | 10.31% | 1.93% | 17.75% | 72.46% | 3/10 |
| `rolling_max_48` | Baseline | 0.00% | 25.69% | 0.00% | 0.00% | 0/10 |
| `ewma` | Baseline | 0.00% | 46.97% | 0.00% | 0.00% | 0/10 |
| `static` | Baseline | -0.00% | 4.55% | 17.47% | 83.32% | 0/10 |

---

## 4. Per-Seed Detailed Breakdown

| Seed | TIME Comp | H1 Verdict | H1 Effect (CI) | SERVICE Comp | H2 Verdict | H2 Effect (CI) | H3 |
| :---: | :--- | :---: | :--- | :--- | :---: | :--- | :---: |
| 1 | `rolling_p99` | SUPPORTED | +82.31 pp [+69.51, +96.27] | `rolling_p99` | SUPPORTED | +86.18 pp [+60.88, +114.13] | SUPPORTED |
| 2 | `static` | SUPPORTED | +119.41 pp [+98.64, +141.99] | `rolling_p99` | NOT_SUPPORTED | +0.00 pp [+0.00, +0.00] | SUPPORTED |
| 3 | `rolling_p99` | SUPPORTED | +76.84 pp [+65.77, +89.33] | `rolling_p99` | SUPPORTED | +70.90 pp [+48.52, +98.85] | SUPPORTED |
| 4 | `rolling_p99` | NOT_SUPPORTED | +0.00 pp [+0.00, +0.00] | `rolling_p99` | SUPPORTED | +79.59 pp [+55.12, +110.16] | SUPPORTED |
| 5 | `static` | SUPPORTED | +124.65 pp [+102.09, +148.68] | `rolling_p99` | NOT_SUPPORTED | +0.00 pp [+0.00, +0.00] | SUPPORTED |
| 6 | `rolling_p99` | SUPPORTED | +76.69 pp [+67.15, +87.22] | `rolling_p99` | SUPPORTED | +70.79 pp [+54.17, +89.61] | SUPPORTED |
| 7 | `static` | SUPPORTED | +125.64 pp [+102.34, +151.07] | `static` | SUPPORTED | +104.63 pp [+75.03, +138.26] | SUPPORTED |
| 8 | `static` | SUPPORTED | +116.09 pp [+96.49, +136.76] | `rolling_p99` | NOT_SUPPORTED | +0.00 pp [+0.00, +0.00] | SUPPORTED |
| 9 | `rolling_p99` | SUPPORTED | +74.03 pp [+63.42, +84.92] | `rolling_p99` | NOT_SUPPORTED | +0.00 pp [+0.00, +0.00] | SUPPORTED |
| 10 | `rolling_p99` | NOT_SUPPORTED | +0.00 pp [+0.00, +0.00] | `rolling_p99` | SUPPORTED | +71.91 pp [+52.52, +93.42] | SUPPORTED |
