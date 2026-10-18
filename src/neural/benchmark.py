"""Measure experiments in fresh processes; verify repeatability and zero-drive control."""
from pathlib import Path
import argparse
import json
import os
import statistics
import subprocess
import sys
import time


def benchmark(connectome: Path, output: Path, repeats: int = 3):
    if repeats < 2:
        raise ValueError("Use at least two repetitions to check deterministic activity")
    output.mkdir(parents=True, exist_ok=False)
    runs = []
    for i in range(repeats + 1):
        control = i == repeats
        destination = output / ("control.json.gz" if control else f"stimulated-{i + 1}.json.gz")
        command = [sys.executable, "-m", "src.neural.experiment", "--connectome", str(connectome),
                   "--output", str(destination)]
        if control:
            command.append("--control")
        start = time.perf_counter()
        env = {**os.environ, **{name: "1" for name in (
            "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")}}
        completed = subprocess.run(command, text=True, capture_output=True, check=True, env=env)
        summary = json.loads(completed.stdout)
        summary["wall_seconds_whole_subprocess"] = time.perf_counter() - start
        runs.append(summary)
    stimulated = runs[:-1]
    if len({r["activity_sha256"] for r in stimulated}) != 1:
        raise RuntimeError("Non-deterministic neural activity")
    if runs[-1]["spikes"] != 0:
        raise RuntimeError("Unexpected activity in zero-drive control")
    report = {
        "schema_version": 1, "method": "fresh Python process per run; numerical library threads limited to 1; no network; load/import/simulate/export included",
        "repeats": repeats, "simulated_duration_ms": 200, "runs": runs,
        "environment": stimulated[0]["environment"],
        "deterministic_activity": True, "control_has_no_spikes": True,
        "median_cpu_seconds": statistics.median(r["measurements"]["cpu_seconds_load_import_simulation_export"] for r in stimulated),
        "median_wall_seconds_whole_subprocess": statistics.median(r["wall_seconds_whole_subprocess"] for r in stimulated),
        "maximum_peak_rss_mib": max(r["measurements"].get("process_lifetime_peak_rss_mib", r["measurements"]["sampled_peak_rss_mib"]) for r in runs),
    }
    with (output / "benchmark.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connectome", type=Path, default=Path("data/neural/flywire_v783"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    report = benchmark(args.connectome, args.output_dir, args.repeats)
    print(json.dumps({key: value for key, value in report.items() if key != "runs"}, sort_keys=True))


if __name__ == "__main__":
    main()
