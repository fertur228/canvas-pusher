"""Offline CLI exporting dashboard-ready telemetry and process measurements."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import argparse
import gzip
import importlib.metadata
import json
import os
import platform
import sys
import threading
import time

import psutil

from .loader import load_connectome, sha256
from .models import Parameters


class MemoryMeter:
    """Process RSS sampling plus OS lifetime high-water mark on Unix."""
    def __init__(self):
        self.process = psutil.Process()
        self.peak = self.process.memory_info().rss
        self.done = threading.Event()
        self.thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self):
        while not self.done.wait(0.005):
            self.peak = max(self.peak, self.process.memory_info().rss)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.peak = max(self.peak, self.process.memory_info().rss)
        self.done.set()
        self.thread.join()

    def measurements(self):
        result = {"sampled_peak_rss_mib": self.peak / 2**20, "rss_sample_interval_ms": 5}
        if sys.platform != "win32":
            import resource
            high_water = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            result["process_lifetime_peak_rss_mib"] = high_water / (2**20 if sys.platform == "darwin" else 1024)
        return result


def export_run(directory: Path, output: Path, parameters: Parameters,
               stimulus_type: str = "both", side: str = "both", control: bool = False,
               *, synaptic_model: str = "voltage_jump", nt_policy: str = "edge_prediction",
               looming=None):
    summary_path = output.with_name(output.name + ".summary.json")
    if output.exists() or summary_path.exists():
        raise FileExistsError("Experiment outputs already exist; choose a new output path")
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    with MemoryMeter() as memory:
        graph = load_connectome(directory)
        from .engine import simulate
        stimulus = tuple(n.root_id for n in graph.neurons if n.role == "stimulus"
                         and (stimulus_type == "both" or stimulus_type in (n.cell_type, n.hemibrain_type))
                         and (side == "both" or n.side == side))
        if not stimulus and not control:
            raise ValueError("No sensory projection neurons match the stimulus selection")
        if control:
            parameters = replace(parameters, stimulus_drive_mv=0.0)
            if looming is not None:
                looming = replace(looming, contrast=0.0)
        plan = looming.generate(graph, parameters.duration_ms) if looming is not None else None
        result = simulate(graph, parameters, stimulus_ids=stimulus if plan is None else plan.neuron_ids,
                          synaptic_model=synaptic_model, nt_policy=nt_policy, drive_plan=plan)
        telemetry = {
            "schema_version": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "experiment": "looming_feature_drive_proxy" if plan is not None else "no_stimulus_control" if control else "rectangular_current_injection",
            "time_unit": "ms", "voltage_unit": "mV", "neuron_ids_are_strings": True,
            "biological_response_validated": False,
            "dataset": graph.manifest, "manifest_sha256": sha256(directory / "manifest.json"),
            "model": {"engine": "Brian2", "method": "exact leaky integrate-and-fire", **result.model,
                      "codegen_target": "numpy", "initial_state": "all neurons at rest; no randomness",
                      "sign_assumption": nt_policy,
                      "weights_assumption": "syn_count * mv_per_synapse * sign; fixed, no normalization",
                      "limitations": "Feature-drive/current injection into LC4/LPLC2; not calibrated visual processing, no VNC/gap junctions/learning"},
            "environment": {"python": platform.python_version(), "platform": platform.platform(),
                            "machine": platform.machine(), "cpu_logical_count": os.cpu_count(),
                            "numerical_thread_environment": {name: os.getenv(name) for name in (
                                "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")},
                            "dependencies": {n: importlib.metadata.version(n) for n in ("brian2", "numpy", "sympy", "psutil", "pyparsing", "jinja2")}},
            "neuron_ids": [n.root_id for n in graph.neurons],
            "activity_sha256": result.activity_sha256, "simulation": result.as_dict(),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation avoids accidentally overwriting prior experiments.
        opener = gzip.open if output.suffix == ".gz" else open
        with opener(output, "xt", encoding="utf-8") as stream:
            json.dump(telemetry, stream, separators=(",", ":"), sort_keys=True, allow_nan=False)
    measurements = {"wall_seconds_load_import_simulation_export": time.perf_counter() - start_wall,
                    "cpu_seconds_load_import_simulation_export": time.process_time() - start_cpu,
                    **memory.measurements()}
    summary = {"output": str(output), "counts": graph.stats, "measurements": measurements,
               "environment": telemetry["environment"],
               "activity_sha256": result.activity_sha256, "spikes": len(result.spikes),
               "active_neurons": sum(a["spike_count"] > 0 for a in result.activity),
               "model": result.model,
               "population_activity": {typ: {"neurons": sum(typ in (n.cell_type, n.hemibrain_type) for n in graph.neurons),
                   "spikes": sum(a["spike_count"] for n, a in zip(graph.neurons, result.activity) if typ in (n.cell_type, n.hemibrain_type)),
                   "active_neurons": sum(a["spike_count"] > 0 for n, a in zip(graph.neurons, result.activity) if typ in (n.cell_type, n.hemibrain_type))}
                   for typ in ("LC4", "LPLC2", "DNp01")},
               "stimulus_summary": {key: value for key, value in result.stimulus.items()
                                    if key in {"kind", "peak_drive_mv", "drive_integral_mv_ms", "parameters", "start_ms", "stop_ms", "drive_mv", "expansion_end_ms"}
                                    and (key != "drive_mv" or not isinstance(value, dict))},
               "readout": list(result.readout), "signs": result.signs,
               "telemetry_bytes": output.stat().st_size}
    with summary_path.open("x") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connectome", type=Path, default=Path("data/neural/flywire_v783"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration-ms", type=float, default=200)
    parser.add_argument("--dt-ms", type=float, default=0.1)
    parser.add_argument("--drive-mv", type=float, default=30)
    parser.add_argument("--stimulus-type", choices=["both", "LC4", "LPLC2"], default="both")
    parser.add_argument("--side", choices=["both", "left", "right"], default="both")
    parser.add_argument("--control", action="store_true")
    args = parser.parse_args()
    parameters = Parameters(duration_ms=args.duration_ms, dt_ms=args.dt_ms, stimulus_drive_mv=args.drive_mv)
    print(json.dumps(export_run(args.connectome, args.output, parameters, args.stimulus_type, args.side, args.control), sort_keys=True))


if __name__ == "__main__":
    main()
