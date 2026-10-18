"""Reproducible escape-circuit validation and sensitivity experiments, no training.

Run a fresh-process suite or an individual case. Published parameters are an
alternative hypothesis, never automatically selected to optimize GF spiking.
"""
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
import argparse
import gzip
import json
import os
import statistics
import subprocess
import sys
import time

from .experiment import export_run
from .loader import load_connectome, sha256
from .models import Parameters, literature_parameters, effective_sign
from .stimulus import Looming


CASES = (
    "legacy_raw", "legacy_presynaptic",
    "baseline", "weak", "strong", "weak_fast", "strong_slow",
    "strong_conservative_nt", "strong_raw_edge_nt", "strong_zero_synapses",
    "strong_lc4_only", "strong_lplc2_only", "strong_fine_dt", "weak_fine_dt",
)
PRIMARY = {"baseline", "weak", "strong"}
REFERENCES = [
    {"url": "https://doi.org/10.1016/j.cub.2019.01.079", "use": "LC4 velocity plus LPLC2 size contribution to GF, not drive calibration"},
    {"url": "https://doi.org/10.1242/jeb.244790", "use": "10-63 degree looms, r/v 10/20/40/80 ms; membrane response is a valid measurement"},
    {"url": "https://doi.org/10.7554/eLife.50901", "use": "cell-type transcriptomic transmitter annotations, not receptor measurements"},
    {"url": "https://doi.org/10.1038/s41586-024-07763-9", "use": "published generic LIF parameter assumptions; 0.275 mV is a free model weight"},
    {"url": "https://github.com/philshiu/Drosophila_brain_model/blob/91bdd1e7dcf193f3e7ca5a8933497fcef63b7960/model.py", "use": "exact g-decay equations and parameter semantics; our input protocol is different"},
]


def case_configuration(name: str):
    if name not in CASES:
        raise ValueError("Unknown experiment")
    if name.startswith("legacy"):
        return Parameters(), None, "voltage_jump", ("edge_prediction" if name == "legacy_raw" else "presynaptic_conservative")
    parameters = literature_parameters()
    stimulus = Looming()
    policy = "presynaptic_shiu"
    if name == "baseline":
        stimulus = replace(stimulus, contrast=0)
    if name in {"weak", "weak_fine_dt"}:
        stimulus = replace(stimulus, radius_over_speed_ms=80, contrast=0.35)
    if name == "weak_fast":
        stimulus = replace(stimulus, contrast=0.35)
    if name == "strong_slow":
        stimulus = replace(stimulus, radius_over_speed_ms=80)
    if name == "strong_conservative_nt":
        policy = "presynaptic_conservative"
    if name == "strong_raw_edge_nt":
        policy = "edge_prediction"
    if name == "strong_zero_synapses":
        parameters = replace(parameters, mv_per_synapse=0)
    if name == "strong_lc4_only":
        stimulus = replace(stimulus, enabled_types=("LC4",))
    if name == "strong_lplc2_only":
        stimulus = replace(stimulus, enabled_types=("LPLC2",))
    if name.endswith("fine_dt"):
        parameters = replace(parameters, dt_ms=0.05)
    return parameters, stimulus, "exponential_current", policy


def summarize_incoming_drive(graph, telemetry):
    """Available weighted presynaptic events, BEFORE refractory losses/filtering.

    These are g increments (or legacy v kicks), NOT a sum of biological EPSPs.
    """
    simulation = telemetry["simulation"]
    parameters = simulation["parameters"]
    counts = Counter(e["root_id"] for e in simulation["spikes"]
                     if e["time_ms"] + parameters["delay_ms"] < parameters["duration_ms"])
    cells = {n.root_id: n for n in graph.neurons}
    budgets = {}
    for target in simulation["readout_ids"]:
        channels = defaultdict(lambda: {"weighted_synapse_events": 0, "positive_increment_mv": 0.0,
                                        "negative_increment_mv": 0.0, "zero_effect_synapse_events": 0})
        for edge in graph.synapses:
            if edge.post_root_id != target:
                continue
            source = cells[edge.pre_root_id]
            kind = source.cell_type or source.hemibrain_type or "untyped"
            channel = kind if kind in {"LC4", "LPLC2"} else "other"
            events = edge.syn_count * counts[edge.pre_root_id]
            sign = effective_sign(source, edge, simulation["model"]["nt_policy"])
            channels[channel]["weighted_synapse_events"] += events
            if sign == 0:
                channels[channel]["zero_effect_synapse_events"] += events
            elif sign > 0:
                channels[channel]["positive_increment_mv"] += events * parameters["mv_per_synapse"]
            else:
                channels[channel]["negative_increment_mv"] += events * parameters["mv_per_synapse"]
        budgets[target] = dict(channels)
    return {"interpretation": "Available arrivals before refractory losses and decay; not biological EPSP sums or actual membrane depolarization",
            "targets": budgets}


def run_case(connectome: Path, output: Path, case: str):
    parameters, looming, model, policy = case_configuration(case)
    summary = export_run(connectome, output, parameters, synaptic_model=model, nt_policy=policy, looming=looming)
    opener = gzip.open if output.suffix == ".gz" else open
    with opener(output, "rt") as stream:
        telemetry = json.load(stream)
    graph = load_connectome(connectome)
    gf = {n.root_id for n in graph.neurons if n.role == "readout"}
    if gf & set(telemetry["simulation"]["stimulus_ids"]):
        raise RuntimeError("GF directly stimulated; reject experiment")
    summary.update({"case": case, "no_gf_direct_stimulation": True,
                    "incoming_drive": summarize_incoming_drive(graph, telemetry),
                    "source_code_sha256": {name: sha256(Path(__file__).with_name(name))
                                           for name in ("engine.py", "models.py", "stimulus.py", "escape.py", "experiment.py")}})
    # Separate derived metrics are exclusive-created; base telemetry is never rewritten.
    with output.with_name(output.name + ".escape.json").open("x") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return summary


def run_suite(connectome: Path, output: Path, repeats: int = 3, expanded_connectome: Path | None = None):
    if repeats < 2:
        raise ValueError("At least two repetitions required")
    output.mkdir(parents=True, exist_ok=False)
    runs = []
    env = {**os.environ, **{n: "1" for n in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")}}
    for case in CASES:
        for repeat in range(repeats if case in PRIMARY else 1):
            destination = output / f"{case}-{repeat + 1}.json.gz"
            command = [sys.executable, "-m", "src.neural.escape", "case", "--case", case,
                       "--connectome", str(connectome), "--output", str(destination)]
            start = time.perf_counter()
            result = subprocess.run(command, capture_output=True, text=True, check=True, env=env)
            summary = json.loads(result.stdout)
            summary["wall_seconds_whole_subprocess"] = time.perf_counter() - start
            runs.append(summary)
            print(json.dumps({"completed_case": case, "repeat": repeat + 1, "spikes": summary["spikes"]}), file=sys.stderr, flush=True)
    if expanded_connectome:
        for case in ("legacy_raw", "weak", "strong"):
            destination = output / f"boundary_{case}.json.gz"
            command = [sys.executable, "-m", "src.neural.escape", "case", "--case", case,
                       "--connectome", str(expanded_connectome), "--output", str(destination)]
            start = time.perf_counter()
            result = subprocess.run(command, capture_output=True, text=True, check=True, env=env)
            summary = json.loads(result.stdout)
            summary["case"] = "boundary_" + case
            summary["wall_seconds_whole_subprocess"] = time.perf_counter() - start
            runs.append(summary)
    primary = {}
    for case in sorted(PRIMARY):
        selected = [r for r in runs if r["case"] == case]
        if len({r["activity_sha256"] for r in selected}) != 1:
            raise RuntimeError("Repeated neural activity differs")
        primary[case] = {"deterministic": True, "repeats": repeats,
                         "median_cpu_seconds": statistics.median(r["measurements"]["cpu_seconds_load_import_simulation_export"] for r in selected),
                         "median_wall_seconds_whole_subprocess": statistics.median(r["wall_seconds_whole_subprocess"] for r in selected),
                         "peak_rss_mib": max(r["measurements"].get("process_lifetime_peak_rss_mib", r["measurements"]["sampled_peak_rss_mib"]) for r in selected)}
    if next(r for r in runs if r["case"] == "baseline")["spikes"]:
        raise RuntimeError("Unexpected spontaneous activity")
    if any(r["spike_times_ms"] for r in next(r for r in runs if r["case"] == "strong_zero_synapses")["readout"]):
        raise RuntimeError("GF active without synaptic drive")
    report = {"schema_version": 1, "biological_response_validated": False, "references": REFERENCES,
              "primary_benchmarks": primary, "runs": runs,
              "benchmark_method": "fresh single-thread numerical-library processes; warm OS cache; load/import/simulate/export measured; derived analysis excluded from CPU/RSS timings",
              "limitations": ["Feature-to-drive gain is assumed, not fitted to recorded LC4/LPLC2 responses",
                              "Generic published LIF parameters are not GF-specific measurements",
                              "0.275 mV is a free g-increment weight, not a measured EPSP",
                              "Cell-type transmitter evidence does not establish receptor-level polarity",
                              "No retinal receptive-field geometry, gap junctions, VNC, behavioral or physiological validation"]}
    with (output / "escape-suite.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    single = sub.add_parser("case")
    single.add_argument("--case", choices=CASES, required=True)
    single.add_argument("--connectome", type=Path, default=Path("data/neural/flywire_v783"))
    single.add_argument("--output", type=Path, required=True)
    suite = sub.add_parser("suite")
    suite.add_argument("--connectome", type=Path, default=Path("data/neural/flywire_v783"))
    suite.add_argument("--output-dir", type=Path, required=True)
    suite.add_argument("--repeats", type=int, default=3)
    suite.add_argument("--expanded-connectome", type=Path)
    args = parser.parse_args()
    if args.command == "case":
        print(json.dumps(run_case(args.connectome, args.output, args.case), sort_keys=True))
    else:
        report = run_suite(args.connectome, args.output_dir, args.repeats, args.expanded_connectome)
        print(json.dumps({"output": str(args.output_dir / "escape-suite.json"),
                          "experiments": len(report["runs"]), "primary_benchmarks": report["primary_benchmarks"]}, sort_keys=True))


if __name__ == "__main__":
    main()
