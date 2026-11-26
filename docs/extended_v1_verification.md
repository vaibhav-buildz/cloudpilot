# Extended-v1 final verification

The original protocol, seed selections, estimator configuration, partitions, and thresholds were retained. The scheduler now closes tasks only when their remaining work reaches an actual completion event. A prior absolute tolerance could report a completion while a fractional amount of CPU work was outstanding. This is a correction to implement the specified semantics. Measured CPU core-seconds and resident task GiB-seconds are exposed as separate scheduler diagnostics. Suspended tasks consume neither CPU nor resident memory. Tasks admitted while CPU capacity is zero continue to reserve memory.

## Seed 42 audit

The pilot re-ran offline with the original 4 services, 600 five-minute intervals, 1% target, and default estimators. It took 3.916 seconds and returned 390,774 compact JSON bytes. The raw rerun was stored locally under results/extended-v1-final-audit/extended_v1_seed_42.json. SHA-256: 069297dd38e31a72711321fa354aa14cc25fdfdb7f5ac7c7dd714054e1a97c32. The original committed pilot summary is preserved. Timings and last-bit floating-point outputs can vary between runs.

On SERVICE, service index 2 was the sole validation service and index 3 was the sole test service. Observed CPU P95 over the scored period was 20.97 cores on validation and 132.81 cores on test. Memory P95 was 14.95 GiB and 29.11 GiB respectively. GBR_q95 met the validation target with unit multipliers. On test, CPU fell short on 46 rows and memory on 17, overlapping on 12 rows. The union was 51/312 (16.35%). This single-seed service contrast is consistent with a harder test workload and limited validation coverage. It does not isolate a causal effect.

GBR_q95 completed all 312 SERVICE tasks, with zero rejected. It reached backlog six and P95 admission wait of 1,677.22 simulated seconds compared with zero admission wait and backlog for static. P95 response was 2,277.22 seconds for GBR_q95, 239.08 for rolling p99, and 163.81 for static. In a separate negative result, GB completed 266/312, with 46 unfinished including 19 rejected. The GBR_q95 resource table's memory demand-to-capacity ratio was 78.24%; resident task memory occupied 45.62% of allocated GiB-seconds. They measure different quantities.

## Offline study budget

The ten original CPU-only seeds consumed 3.51 hours in total. Two separate resources give a rough planning estimate of 7 hours for extended-v1 before accounting for hardware variability, scheduling, and output. At the full shape, one split's 748,800 rows by 14 float64 features occupy about 80 MiB of feature matrices alone. Peak memory also includes intermediate arrays, validation and test observations and traces in memory, and model fits. Exact peak memory at study scale has not been measured. The workstation had about 3.85 GiB available during preflight. The full extended study was not started in this verification session.

Run sequentially on a dedicated machine after installing backend/requirements.txt. Each completed seed has an atomic checkpoint with configuration, dependency versions, engine source hashes, runtime, and a result checksum. The checkpoint directory must support hard links, such as NTFS or ext4.

    python scripts/run_extended_study.py --full --resume --output-dir results/extended-v1-full

Re-running the command resumes only from valid matching checkpoints. The output directory is ignored by Git. No production API calls are made.
