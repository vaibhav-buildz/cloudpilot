"""CSV workload parser and validator without pandas."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from itertools import pairwise
from math import isfinite

import numpy as np

from app.engine.features import MIN_WORKLOAD_SERVICES, MIN_WORKLOAD_STEPS
from app.engine.generator import WorkloadData

MAX_CSV_BYTES = 5 * 1024 * 1024  # 5 MB upload limit


def load_workload_from_csv(csv_bytes: bytes) -> WorkloadData:
    """Parse, validate, and pivot uploaded workload CSV into WorkloadData array format.

    Required columns:
    - service_id: identifier string
    - timestamp: sortable string or numeric timestamp
    - cpu_demand: numeric value >= 0
    """
    if len(csv_bytes) > MAX_CSV_BYTES:
        raise ValueError(
            f"CSV payload size ({len(csv_bytes)} bytes) exceeds the maximum allowed 5 MB limit."
        )

    try:
        text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Uploaded file must be valid UTF-8 text.") from exc

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise ValueError("Uploaded CSV is empty.") from exc

    # Normalize header column names
    col_map = {col.strip().lower(): idx for idx, col in enumerate(header)}
    required_cols = {"service_id", "timestamp", "cpu_demand"}
    missing = required_cols - set(col_map.keys())
    if missing:
        raise ValueError(
            f"CSV is missing required column(s): {', '.join(sorted(missing))}. "
            "Expected 'service_id', 'timestamp', 'cpu_demand'."
        )

    srv_idx = col_map["service_id"]
    time_idx = col_map["timestamp"]
    cpu_idx = col_map["cpu_demand"]

    service_records: dict[str, list[tuple[str, float]]] = defaultdict(list)

    for line_num, row in enumerate(reader, start=2):
        if not row:
            continue
        if len(row) <= max(srv_idx, time_idx, cpu_idx):
            raise ValueError(f"Line {line_num}: malformed row with insufficient columns.")

        service_id = row[srv_idx].strip()
        timestamp = row[time_idx].strip()
        raw_cpu = row[cpu_idx].strip()

        if not service_id:
            raise ValueError(f"Line {line_num}: 'service_id' cannot be blank.")
        if not timestamp:
            raise ValueError(f"Line {line_num}: 'timestamp' cannot be blank.")

        try:
            cpu_val = float(raw_cpu)
        except ValueError as exc:
            raise ValueError(
                f"Line {line_num}: invalid CPU demand '{raw_cpu}', expected float."
            ) from exc

        if not isfinite(cpu_val):
            raise ValueError(f"Line {line_num}: CPU demand must be finite.")
        if cpu_val < 0.0:
            raise ValueError(f"Line {line_num}: negative CPU demand {cpu_val} is prohibited.")

        service_records[service_id].append((timestamp, cpu_val))

    if not service_records:
        raise ValueError("CSV contains no valid service data rows.")

    service_ids = sorted(service_records.keys())
    n_services = len(service_ids)
    if n_services < MIN_WORKLOAD_SERVICES:
        raise ValueError(f"CSV must contain at least {MIN_WORKLOAD_SERVICES} services.")

    # Sort each service's records by timestamp
    for srv in service_ids:
        records = service_records[srv]
        records.sort(key=lambda item: item[0])
        if any(a[0] == b[0] for a, b in pairwise(records)):
            raise ValueError(
                "Duplicate timestamp within a service. Provide one row per service and interval."
            )

    # Determine step count across services
    step_counts = [len(service_records[srv]) for srv in service_ids]
    min_steps = min(step_counts)

    if min_steps < MIN_WORKLOAD_STEPS:
        raise ValueError(
            f"Service traces have {min_steps} steps. A minimum of {MIN_WORKLOAD_STEPS} steps "
            "per service is required for TIME split training after the feature warm-up."
        )

    # If traces have slight length variations, truncate all to the common minimum length
    common_steps = min_steps
    demand = np.zeros((n_services, common_steps), dtype=np.float64)

    for i, srv in enumerate(service_ids):
        values = [val for _, val in service_records[srv][:common_steps]]
        demand[i, :] = np.maximum(values, 0.01)

    # Compute static requests as 1.30x peak observed demand
    static_requests = np.max(demand, axis=1) * 1.30
    group_ids = ["uploaded" for _ in range(n_services)]
    is_hard = np.zeros(n_services, dtype=bool)

    return WorkloadData(
        demand=demand,
        static_requests=static_requests,
        service_ids=service_ids,
        group_ids=group_ids,
        is_hard=is_hard,
    )
