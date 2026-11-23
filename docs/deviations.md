# CloudPilot Study Deviations and Bug Disclosures

**Date**: 2026-11-23  
**Status**: Disclosure of v1 study implementation flaws and formal definition of corrections.

---

## 1. Summary of Discovered Issues in v1 Study

An audit of the initial 10-seed simulation study results revealed two statistical anomalies: effect sizes exceeding $+100\text{ pp}$ and multiple hypothesis outcomes displaying artificial estimates of $+0.00\text{ pp } [+0.00, +0.00]$. Investigation traced these behaviors to five distinct implementation defects (D1–D5).

All results produced in study v1 are mathematically invalid and are preserved strictly for transparency in [docs/results_v1_INVALID.md](file:///d:/GitHuh/cloudpilot/docs/results_v1_INVALID.md) and [results/v1_invalid/study_summary.json](file:///d:/GitHuh/cloudpilot/results/v1_invalid/study_summary.json).

Workload generator logic, safety margin evaluation grids, ML model hyperparameters, simulation seeds ($1 \dots 10$), service counts ($N=200$), time durations ($T=4032$), and all pre-registered hypotheses remain strictly unchanged.

---

## 2. Deviation Registry

### D1: Row-Order Mismatch Between Datasets and Baseline Allocations
- **Issue**: In `features.py`, `build_dataset()` generated test slices in time-major order ($t$ outer loop, service $s$ inner loop). In contrast, `baselines.py` and `runner.py` created 2D arrays of shape $(n_{\text{services}}, n_{\text{steps}})$ and flattened them using NumPy's default C-order, producing service-major arrays ($s$ outer loop, $t$ inner loop).
- **Consequence**: When `evaluate.py` extracted per-service observations via `mask = service_indices == srv`, the stride indexed across different services in the flattened baseline array. For small services (e.g. 5-core requests), summing allocations intended for 40-core services resulted in allocated-to-static ratios $> 11.0$, plunging per-service savings down to $-1015\%$. When averaged, this corrupted the mean per-service savings of baselines (e.g. static dropped to $-70.4\%$ instead of $0.0\%$), causing paired bootstrap differences against GBR_q95 ($+54.2\%$) to artificially exceed $+100\text{ pp}$ ($+54.2\% - (-70.4\%) = +124.6\text{ pp}$). All baseline metrics in v1 are invalid.
- **Correction**: Adopt a canonical $(n_{\text{services}}, n_{\text{steps}})$ layout across the entire engine. Align all model predictions and baseline allocations explicitly with the exact row and time indices of the target evaluation slice. Add explicit assertions in `evaluate.py` verifying that shape, ordering, and service indices match demand.

### D2: Conflation of Test Violation with Validation Feasibility
- **Issue**: `evaluate.py` computed `is_feasible = violation_rate <= target_violation` directly on the test evaluation slice.
- **Consequence**: In `hypotheses.md`, model feasibility is defined strictly on validation data: a model is feasible if and only if a safety margin on the pre-defined grid achieves pooled validation violation $\le 1.0\%$. Test violation was mistakenly used to override model feasibility, conflating model selection with operational test evaluation. Test violation is governed solely by Hypothesis 3 ($\le 1.5\%$).
- **Correction**: Model feasibility is determined exclusively during the validation phase (`val_margin is not None`). Test evaluation measures test violation and test savings without retroactively altering the model's validation feasibility status.

### D3: Zero-Vector Fallback in Paired Bootstrap
- **Issue**: When `runner.py` evaluated a model as not feasible on test rows, it executed:
  `boot = paired_bootstrap_test([0.0] * n_services, [0.0] * n_services)`
- **Consequence**: Resampling two all-zero vectors produced artificial estimates of $+0.00\text{ pp } [+0.00, +0.00]$ with $p = 1.0$, completely obscuring the true performance difference between the model and comparator.
- **Correction**: Eliminate all all-zero vector fallbacks. The paired bootstrap must always execute on the actual observations of the candidate model and the comparator. If a model fails validation feasibility, its verdict is recorded as `NOT_SUPPORTED` with the explicit reason, while faithfully reporting the empirical effect size and confidence interval.

### D4: Mismatch Between Bootstrap Statistic and Pre-Registered Savings Definition
- **Issue**: The v1 bootstrap resampled the mean of unweighted per-service savings ratios $\frac{1}{N} \sum_{i=1}^N \left(1 - \frac{\sum_t A_{i,t}}{\sum_t S_{i,t}}\right)$.
- **Consequence**: Small services with low core counts exerted equal leverage to large enterprise services, and ratios were mathematically susceptible to extreme negative distortions under misalignments. `hypotheses.md` defines fleet savings as pooled capacity:
  $$1 - \frac{\sum_{i,t} A_{i,t}}{\sum_{i,t} S_{i,t}}$$
- **Correction**: Redefine the bootstrap statistic to match the pooled definition: resample service indices with replacement; for each resample, aggregate the total allocated cores and total static cores across the resampled fleet to compute pooled savings for each method. The bootstrap effect is:
  $$\Delta = \text{Savings}_{\text{model}}^{\text{pooled}} - \text{Savings}_{\text{comparator}}^{\text{pooled}}$$
  Evaluated with 10,000 resamples at seed 42 with a 95% percentile confidence interval.

### D5: Formal Specification for Infeasible Baseline Comparators
- **Rule Clarification**: `hypotheses.md` stated that the comparator is the feasible baseline with the highest validation savings. It did not explicitly define behavior when all baseline methods fail validation feasibility ($\le 1.0\%$ violation).
- **Rule Adopted Prior to Re-run**: If no baseline method is validation-feasible, the comparator defaults to `static` (multiplicative 1.00), and the resulting H1/H2 hypothesis verdicts are reported with the explicit annotation `"vs infeasible comparator"`.

---

## 3. Side-by-Side Headline Comparison (v1 vs v2)

*(To be updated upon completion of the v2 study execution)*

| Metric / Hypothesis | Study v1 (INVALID) | Study v2 (Corrected) |
| :--- | :--- | :--- |
| **H1 Verdict (TIME)** | MIXED/NOT_SUPPORTED (8/10) | *Pending v2 run* |
| **H1 Median Effect** | +79.57 pp [+68.33, +92.80] | *Pending v2 run* |
| **H2 Verdict (SERVICE)** | MIXED/NOT_SUPPORTED (6/10) | *Pending v2 run* |
| **H2 Median Effect** | +70.84 pp [+50.52, +91.52] | *Pending v2 run* |
| **H3 Verdict (Feasibility)** | SUPPORTED (10/10) | *Pending v2 run* |
| **H3 Max Test Violation** | 1.12% | *Pending v2 run* |
