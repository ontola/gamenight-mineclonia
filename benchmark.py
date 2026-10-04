"""Opt-in Windows package measurements. Requires the development psutil package."""

import csv
import platform
import statistics
import time


def summarize(path, start_us, end_us):
    with path.open(encoding="ascii") as source:
        rows = [tuple(map(int, row)) for row in csv.reader(source) if len(row) == 4]
    rows = [row for row in rows if start_us <= row[0] <= end_us and row[1] > 0]
    if len(rows) < 60:
        raise RuntimeError(f"Too few rendered frames in {path}")
    ms = sorted(row[1] / 1000 for row in rows)

    def percentile(p):
        return ms[min(len(ms) - 1, round((len(ms) - 1) * p))]

    return {
        "frames": len(ms),
        "mean_fps": 1000 / statistics.mean(ms),
        "frame_ms_p50": percentile(0.5),
        "frame_ms_p95": percentile(0.95),
        "frame_ms_p99": percentile(0.99),
        "frame_ms_max": max(ms),
        "frames_over_33ms_percent": sum(v > 33.333 for v in ms) * 100 / len(ms),
        "render_sizes": sorted({(row[2], row[3]) for row in rows}),
    }


def measure(root, controls, pump, seconds):
    import psutil

    pids = [
        int(value) for value in (root / "managed/view-pids.txt").read_text().split()
    ]
    pids.append(int((root / "managed/server.pid").read_text()))
    processes = [psutil.Process(pid) for pid in pids]

    def cpu_seconds():
        return sum(p.cpu_times().user + p.cpu_times().system for p in processes)

    cases = []
    for name, look in (("stationary", 0), ("camera_pan", 12000)):
        for pad in controls:
            pad["axes"][2] = look
        pump(
            10
        )  # fixed warmup; no image capture, world generation or launch in samples
        start_us = time.time_ns() // 1000
        started, cpu_before = time.monotonic(), cpu_seconds()
        rss = []
        while time.monotonic() - started < seconds:
            pump(min(0.5, max(0, seconds - (time.monotonic() - started))))
            rss.append(sum(p.memory_info().rss for p in processes))
        elapsed = time.monotonic() - started
        end_us = time.time_ns() // 1000
        used = cpu_seconds() - cpu_before
        pump(
            2
        )  # allow buffered timing lines to flush before reading the measured interval
        cases.append(
            {
                "scenario": name,
                "seconds": elapsed,
                "cpu_core_equivalents": used / elapsed,
                "cpu_machine_percent": used / elapsed / psutil.cpu_count() * 100,
                "combined_working_set_peak_bytes": max(rss),
                "views": [
                    summarize(root / f"managed/performance-{i}.csv", start_us, end_us)
                    for i in range(len(controls))
                ],
            }
        )
    for pad in controls:
        pad["axes"][2] = 0
    return {
        "cases": cases,
        "logical_processors": psutil.cpu_count(),
        "memory_bytes": psutil.virtual_memory().total,
        "os": platform.platform(),
        "method": "Render completion intervals include pacing and CPU/OS work; these are not GPU timings. Combined working sets may count shared pages more than once.",
        "limits": [
            "Fixed seed, short stationary and camera-pan scenes",
            "No mob-heavy or long-session stress",
            "Other desktop applications remained running",
            "Physical controller feel not measured",
        ],
    }
