# CloudPilot Experimental Hypotheses

> **Status**: Written and committed before running any experimental benchmark or generating empirical results.

## 1. Scope & System Boundary

CloudPilot models **CPU right-sizing only** for multi-tenant cloud workloads.
- All evaluation data is synthetically simulated using a deterministic, seeded workload generator unless a user explicitly uploads an external workload CSV.
- **No memory (RAM) claims**: Memory, disk I/O, and network bandwidth are intentionally out of scope and are not modeled.
- **Simulation Disclaimer**: All results, metrics, and conclusions describe the discrete simulation environment and mathematical models, not physical production cloud infrastructure.

---

## 2. Mathematical Definitions

1. **Interval & Time Step**:
   Time advances in discrete intervals $t$ of 5 minutes ($300$ seconds).

2. **Workload Demand**:
   $\text{demand}_i(t) \ge 0$ represents the average CPU core demand of service $i$ across time step $t$.

3. **Strict Past-Only Allocation**:
   The allocated CPU capacity $A_i(t)$ for service $i$ in time interval $t$ is decided strictly at the start of interval $t$ using only historical observations from intervals prior to $t$ ($\tau < t$). Future or contemporaneous demand ($\tau \ge t$) is never visible to allocation policies.

4. **CPU Allocation Violation**:
   A violation occurs at time $t$ for service $i$ if:
   $$\text{demand}_i(t) > A_i(t)$$
   The pooled violation rate over evaluated service-time pairs $(i, t) \in \mathcal{E}$ is:
   $$\text{Violation Rate} = \frac{\sum_{(i, t) \in \mathcal{E}} \mathbb{I}(\text{demand}_i(t) > A_i(t))}{|\mathcal{E}|}$$

5. **Target Violation Threshold**:
   The primary optimization objective is meeting a pooled validation violation rate $\le 1.0\%$ ($\alpha = 0.01$).

6. **Static Baseline & Cost Savings**:
   Every service has a designated static reservation $S_i$ corresponding to the over-provisioned request set by the workload generator. The aggregate savings of an allocation policy $A$ relative to static allocation is:
   $$\text{Savings} = 1 - \frac{\sum_{(i, t) \in \mathcal{E}} A_i(t)}{\sum_{(i, t) \in \mathcal{E}} S_i}$$

7. **Safety Margin Selection**:
   To convert point predictions or conservative estimates into reliable allocations, a safety margin is applied:
   - Additive margin: $A_i(t) = \hat{y}_i(t) + m$
   - Multiplicative margin: $A_i(t) = \hat{y}_i(t) \times m$

   The margin $m^*$ is chosen from a fixed, predetermined grid as the **smallest value whose pooled VALIDATION violation is $\le 1.0\%$**. If no value on the grid achieves validation violation $\le 1.0\%$, the method is flagged as **infeasible**. Margins are **never selected or adjusted using test split data**.

8. **Dataset Splits**:
   To assess temporal generalization and cross-service transferability:
   - **TIME Split**: Evaluates adaptation to unseen future periods on known services.
     - Train: First 60% of time intervals.
     - Validation: Intermediate 15% of time intervals (used for margin selection and baseline tuning).
     - Test: Final 25% of time intervals (held out strictly for final evaluation).
   - **SERVICE Split**: Evaluates transfer to completely unseen services.
     - Train: Random 60% of service IDs.
     - Validation: Disjoint 15% of service IDs.
     - Test: Disjoint 25% of service IDs held out entirely.

9. **Benchmark Comparator**:
   The **Comparator** is defined as the feasible baseline policy (among static, rolling maximum, rolling p99, and EWMA) that achieves the highest savings on the validation split.

10. **Statistical Hypothesis Testing**:
    - Paired bootstrap resampling across services.
    - Resampling rounds: $B = 10{,}000$ resamples with replacement.
    - Random seed: $42$.
    - Confidence intervals: 95% percentile bootstrap interval ($[2.5\text{th percentile}, 97.5\text{th percentile}]$) computed strictly on the held-out test split.

---

## 3. Pre-Registered Hypotheses

### Hypothesis 1 (H1: Temporal Efficiency under TIME Split)
On the held-out test split of the TIME partition, the Gradient Boosted Quantile Regressor (`GBR_q95`) configured with its validation-selected safety margin achieves higher savings than the Comparator baseline.
- **Formulation**: $\Delta_{\text{savings}} = \text{Savings}(\text{GBR\_q95}) - \text{Savings}(\text{Comparator}) > 0$.
- **Decision Rule**: H1 is **SUPPORTED** if and only if the lower bound of the 95% paired bootstrap confidence interval for $\Delta_{\text{savings}}$ is strictly greater than 0 ($CI_{\text{lower}} > 0$). Otherwise, H1 is **NOT SUPPORTED**.

### Hypothesis 2 (H2: Cross-Service Generalization under SERVICE Split)
On the held-out test split of the SERVICE partition (unseen services), `GBR_q95` with its validation-selected safety margin is non-inferior to the Comparator baseline within a tolerance margin of $-1.0$ percentage point ($-0.01$).
- **Formulation**: $\Delta_{\text{savings}} = \text{Savings}(\text{GBR\_q95}) - \text{Savings}(\text{Comparator}) \ge -0.01$.
- **Decision Rule**: H2 is **SUPPORTED** if and only if the lower bound of the 95% paired bootstrap confidence interval for $\Delta_{\text{savings}}$ is strictly greater than $-1.0$ percentage point ($CI_{\text{lower}} > -0.01$). Otherwise, H2 is **NOT SUPPORTED**.

### Hypothesis 3 (H3: Safety & Feasibility Constraint)
The selected `GBR_q95` configuration satisfies the operational safety constraint on the held-out test sets of **both** the TIME and SERVICE splits:
- **Decision Rule**: H3 is **SUPPORTED** if and only if:
  $$\text{Violation}_{\text{test, TIME}}(\text{GBR\_q95}) \le 1.5\% \quad \text{AND} \quad \text{Violation}_{\text{test, SERVICE}}(\text{GBR\_q95}) \le 1.5\%$$
  Otherwise, H3 is **NOT SUPPORTED**.

---

## 4. Reporting Protocol

- Every hypothesis (H1, H2, and H3) will be reported in the experiment runner output regardless of outcome.
- If `GBR_q95` fails to achieve $\le 1.0\%$ violation on the validation grid (infeasible), it is marked as infeasible and all dependent hypotheses are recorded as **NOT SUPPORTED**.
- No hypothesis will be retroactively altered, removed, or redefined based on experimental outputs.
