# CloudPilot Simulation & Allocation Methodology

## 1. What Is Simulated

CloudPilot simulates discrete time-series workloads of compute demand across multiple independent services running on a shared cluster.

- **Time Resolution**: 5-minute discrete intervals ($300$ seconds per step; $288$ steps per day; $2016$ steps per week).
- **CPU Resource Units**: Continuous average core utilization during the interval.
- **Component Breakdown**:
  - **Base Load**: Baseline mean core consumption ($2.0$ to $32.0$ cores per service).
  - **Seasonality**: Diurnal cycles (daily peaks/troughs) and weekly patterns (weekday vs. weekend variation).
  - **Linear Trend**: Subtle gradual drift ($-10\%$ to $+15\%$ over the simulation window).
  - **Stochastic Noise**: Uncorrelated Gaussian perturbations ($\sigma = 8\%$ of base for standard services, $25\%$ for hard services).
  - **Burst Spikes**: Sporadic transient demand surges lasting $2$ to $6$ intervals ($10$ to $30$ minutes) with $1.5\times$ to $3.5\times$ base amplitude.
  - **Regime Shifts**: In $30\%$ of the fleet ("hard" services), sudden structural level shifts ($0.65\times$ to $1.5\times$) occur at random change points.
- **Per-Service Static Request**: Set to $1.30\times$ the historical 99th percentile of demand, modeling realistic enterprise cloud over-provisioning.

---

## 2. Temporal & Service Partitions

To rigorously prevent data leakage and evaluate generalization:

1. **TIME Split (Known Services, Future Intervals)**:
   - Evaluates whether an allocator can adapt to future temporal dynamics on existing services.
   - **Train** (first 60% of steps): Model parameters fitted on past observations ($t \ge 288$ to accommodate lag features).
   - **Validation** (next 15% of steps): Safety margins selected and baseline hyperparameters tuned.
   - **Test** (final 25% of steps): Held out strictly for final evaluation and paired bootstrap inference.

2. **SERVICE Split (Unseen Services)**:
   - Evaluates cross-service transferability to newly deployed microservices.
   - **Train** (60% of services): Models trained across all available historical intervals.
   - **Validation** (15% of services): Disjoint fleet partition used for margin selection.
   - **Test** (25% of services): Completely held-out fleet partition evaluated without fine-tuning.

---

## 3. Shift-Before-Rolling & Zero-Leakage Guarantee

All feature transformations and baseline heuristics strictly observe temporal causality:
- For any time step $t$, the allocation decision $A_i(t)$ is established at the onset of $t$ using **only** observations strictly prior to $t$ ($\tau < t$).
- Rolling statistics (mean, max, std over 12 and 48 steps) and lag vectors ($1, 2, 3, 6, 12, 288$) use an exclusive upper slice $[t - w : t]$, ensuring index $t$ or later is never accessed.
- Backward-filling or forward-looking interpolation is strictly prohibited.

---

## 4. Deterministic Safety Margin Selection

Raw regression predictions are prone to under-allocation during sudden demand surges. To enforce a bounded violation rate ($\le 1.0\%$):
- A safety margin grid is evaluated on the **validation partition only**:
  - Multiplicative factors: $1.00$ to $1.60$ in steps of $0.01$.
  - Additive offsets: $0.0$ to $30.0$ percentage points in steps of $0.5$ pp.
- The algorithm deterministically selects the **smallest margin** achieving pooled validation violation $\le 1.0\%$.
- If no grid value achieves $\le 1.0\%$ violation, the configuration is marked **infeasible**.
- Test data is never used to calibrate, adjust, or select margins.

---

## 5. Limitations & Boundary Scope

- **CPU Right-Sizing Only**: Memory (RAM), ephemeral storage, network bandwidth, and IOPS are intentionally not modeled.
- **No Memory Claims**: Allocations and savings figures apply solely to CPU core provisioning. Memory allocation dynamics follow fundamentally different saturation curves and remain out of scope.
- **Discrete Simulator**: Results describe mathematical simulations and trace replays, not physical server hypervisors or container orchestrator kernel scheduling.
