# Phase 5 performance and reliability

## Measurements

The baseline was Git commit `0070834627fc7161d8f1af3e8e0fe1aa9d0f9557`. Three sequential Seed 42 runs per shape used default estimators, a 1% violation target, and web diagnostics. The client exercised the real FastAPI route in-process with an in-memory repository. The post-change route launched and reaped a real child per request. API wall time includes admission, worker startup, encoding, in-memory persistence, and delivery to TestClient. It excludes network and Supabase latency.

The workstation was Windows 11, Intel Core i7-13620H, 16 logical processors, Python 3.12.10, NumPy 2.2.3, SciPy 1.18.1, scikit-learn 1.6.1, threadpoolctl 3.8.0, and FastAPI 0.115.8. The baseline used Random Forest's all-core setting, and each reported BLAS/OpenMP pool had a 16-thread limit. The revised web profile used one Random Forest job and one native thread. The OS sampler observed up to eight worker threads including library and process-management threads. At the maximum CPU-only shape, baseline process CPU time was 58.33 s median for 29.82 s of wall time.

- **CPU-only pilot, 4 × 600.** Median engine time went from 2.40 to 1.68 s. API latency went from 2.43 to 3.27 s. Baseline peak working set was 142.8 MiB. The revised worker peaked at 117.3 MiB and the combined sampled working set was 170.2 MiB. Compact API responses were 140,403 and 140,365 bytes.
- **CPU-only web maximum, 20 × 1,000.** Median engine time went from 29.79 to 25.74 s. API latency went from 29.82 to 27.26 s. Baseline peak working set was 152.5 MiB. The revised worker peaked at 123.7 MiB and the combined sampled working set was 176.7 MiB. Compact API responses were 291,798 and 291,797 bytes.
- **Extended-v1 pilot and default web maximum, 4 × 600.** Median engine time went from 4.831 to 3.479 s. API latency went from 4.87 to 4.99 s. Baseline peak working set was 144.3 MiB. The revised worker peaked at 118.9 MiB and the combined sampled working set was 172.1 MiB. Compact API responses were 390,845 and 390,765 bytes.

Combined memory is the greatest simultaneous sampled parent-plus-child working set in each run, then the median across repetitions. Shared pages can appear in both working sets. Worker startup and isolation add about 1.5 seconds to a request on this workstation. The API processes had median peak working sets of 53.9–56.2 MiB after separating scientific dependencies into the worker.

Separate baseline stage-timed runs measured the following. These are elapsed stage times in seconds, summed across both partitions and both resources when applicable.

- **CPU-only pilot.** Workload generation 0.001, features 0.078, fitting 2.106, inference 0.086, margin selection 0.011, rolling p99 0.053, bootstrap 0.002, diagnostic construction 0.002, JSON encoding 0.005, and in-memory persistence under 0.001.
- **CPU-only web maximum.** Workload generation 0.004, features 0.159, fitting 26.299, inference 0.224, margin selection 0.029, rolling p99 0.272, bootstrap 0.005, diagnostic construction 0.004, JSON encoding 0.011, and in-memory persistence under 0.001.
- **Extended-v1 pilot.** CPU and memory generation 0.003, features 0.124, fitting 4.477, inference 0.240, margin selection 0.022, rolling p99 0.095, task scheduling and reporting 0.022, JSON encoding 0.007, and in-memory persistence under 0.001. Extended-v1 has no bootstrap stage.

Fitting was the dominant cost. Vectorized rolling statistics calculate the same features directly in service order. The engine reuses static allocations, skips per-service accounting where the outputs do not consume it, and releases allocation arrays as soon as both resources have been evaluated. The scheduler uses a deque for memory-suspended tasks. The response reuses the worker's encoded output. Existing sampled charts and exports retain their fields and sampling policy.

## Numerical equivalence

The recursive comparison covered every field of the three web workloads above, excluding only `execution_time_seconds`, `saved`, and `run_id`. Object keys, list lengths, discrete decisions, task counts, task-arrival SHA-256 digests, and sampling indices matched exactly. The 38,896 numeric leaves compared within relative tolerance 5 × 10⁻¹² and absolute tolerance 10⁻¹⁰. The observed maximum absolute difference was 3.64 × 10⁻¹² and maximum relative difference was 8.0 × 10⁻¹⁶. The tolerance covers float64 library and Random Forest summation-order effects. The phase leaves the archived CPU-only conclusions and extended-v1 protocol intact.

CI regression tests cover the original per-step feature extractor, CPU pilot decisions and bootstrap, and extended pilot task arrivals, completion totals, and joint violation rates. The local measurement captures and full-study checkpoints are under the ignored `results/` directory.

## Runtime and persistence

- Each admitted simulation owns one child process. The API kills and reaps it before releasing the slot after deadlines, handler cancellation or a detected disconnect. Linux uses a parent-death signal and Windows watches the parent process handle. Uvicorn drains or cancels requests before lifespan cleanup. Graceful shutdown has a ten-second drain window.
- Admission defaults to one request per server process with zero queued requests. The existing visitor guard returns 429 and saturated global capacity returns 503. Both send a five-second `Retry-After`. These guarantees apply to one Uvicorn process. Additional Uvicorn workers or replicas each have their own limits.
- The 42-second hard worker deadline includes startup, CSV parsing, engine execution and JSON encoding. Save confirmation has a four-second budget and pruning has two seconds. The proxy's 55-second deadline covers upstream headers and body. The function has a 60-second limit. Render wake-up happens before backend admission and can consume the proxy deadline. See the [deployment guide](DEPLOY.md).
- The worker rejects a result larger than 2,000,000 bytes by default. The output bound is configurable up to 4,000,000 bytes. History requests select metadata only. Opening an individual run reads its complete historical result. The sampled series in exports match the charts and saved results.
- A save allocates one run UUID and retries the same insert with duplicate-ignore semantics on the existing primary key. An ambiguous result is verified by visitor and UUID. A pruning failure leaves a confirmed save intact. If the insert and verification both lose their responses, the UI indicates that the save could not be confirmed. Each deliberately submitted simulation remains a separate run. The existing Supabase schema supports this change without a migration.

## Extended rollout and offline study

Production extended execution defaults to disabled. The feature flag and independent caps are advertised through `/api/limits` only when enabled. Before enabling, verify peak memory and safe latency on the hosted instance, and verify both synthetic and aligned CSV runs through persistence and readback. Keep one Uvicorn worker and one simulation slot on the free instance. For rollback, set `ENABLE_PRODUCTION_EXTENDED_SIMULATION=false` and redeploy Render. For a full service rollback, redeploy the previous Render and Vercel revisions. Existing history remains readable.

The full offline configuration uses 200 services, 4,032 steps and Seeds 1–10. To run the first seed with the measured offline profile:

```sh
python scripts/run_extended_study.py --full --seed 1 --resume --native-threads 1 --rf-jobs 8 --output-dir results/extended-v1-phase5-full
```

Use the same command without `--seed 1` to resume the complete study. Checkpoints include the execution profile, dependency versions, source hashes, and a result checksum. Use a separate output directory for a different engine or profile. The older checkpoint format is rejected and existing files are preserved.
