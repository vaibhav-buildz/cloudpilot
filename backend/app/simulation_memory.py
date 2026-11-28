"""Small Linux memory samples for worker acceptance and recycling."""

import os
import sys
from pathlib import Path


def rss_kib(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return 0


def worker_memory(pid: int = 0) -> dict[str, int]:
    if not sys.platform.startswith("linux"):
        return {}
    api, worker = rss_kib(os.getpid()), rss_kib(pid) if pid else 0
    sample = {"api_rss_kib": api, "worker_rss_kib": worker, "combined_rss_kib": api + worker}
    for key, path in (
        ("cgroup_current_kib", "/sys/fs/cgroup/memory.current"),
        ("cgroup_peak_kib", "/sys/fs/cgroup/memory.peak"),
        ("cgroup_limit_kib", "/sys/fs/cgroup/memory.max"),
    ):
        try:
            sample[key] = int(Path(path).read_text()) // 1024
        except (OSError, ValueError):
            pass
    return sample


def sample_peak(pid: int, peaks: dict[str, int]) -> None:
    for key, value in worker_memory(pid).items():
        peaks[key] = max(peaks.get(key, 0), value)
