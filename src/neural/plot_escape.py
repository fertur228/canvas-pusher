"""Export static scientific figures from recorded telemetry; never runs a simulation."""
from pathlib import Path
import argparse
import gzip
import json
import os


def plot_suite(suite_path: Path, output: Path):
    import numpy as np
    os.environ.setdefault("MPLCONFIGDIR", str(Path("data/neural/cache/matplotlib").resolve()))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    report = json.loads(suite_path.read_text())
    if output.exists():
        raise FileExistsError("Choose a new plot directory")
    cases = {}
    for case in ("baseline", "weak", "strong"):
        row = next(r for r in report["runs"] if r["case"] == case)
        with gzip.open(row["output"], "rt") as stream:
            cases[case] = json.load(stream)
    colors = {"baseline": "#6b7280", "weak": "#2263ad", "strong": "#b43c32"}
    labels = {"baseline": "No stimulus", "weak": "Weak: contrast 0.35, r/v 80 ms", "strong": "Strong: contrast 1.0, r/v 20 ms"}
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for i, rid in enumerate(cases["strong"]["simulation"]["readout_ids"]):
        ax = axes[0, i]
        for case, telemetry in cases.items():
            traces = telemetry["simulation"]["traces"]
            ax.plot(traces["readout_time_ms"], traces["readout_voltage_mv"][rid], color=colors[case], label=labels[case], lw=1.2)
        ax.axhline(-45, color="black", linestyle=":", lw=1, label="Model threshold")
        ax.set(title=f"GF {'left' if i == 0 else 'right'}: {rid}", xlabel="Simulation time (ms)", ylabel="Membrane potential before threshold (mV)")
        ax.legend(fontsize=8, loc="lower right")
        ax.grid(alpha=0.2)
    ax = axes[1, 0]
    for case in ("weak", "strong"):
        stim = cases[case]["simulation"]["stimulus"]
        for typ, style in (("LC4", "-"), ("LPLC2", "--")):
            ax.plot(stim["times_ms"], stim["drive_mv"][typ], style, color=colors[case], label=f"{case}: {typ}", lw=1.3)
    ax.set(title="Assumed visual feature drive", xlabel="Simulation time (ms)", ylabel="Voltage-equivalent external drive (mV)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.2)
    ax = axes[1, 1]
    bins = np.arange(0, 1110, 10)
    for case, telemetry in cases.items():
        times = [s["time_ms"] for s in telemetry["simulation"]["spikes"]]
        counts, _ = np.histogram(times, bins=bins)
        ax.step(bins[:-1] + 5, counts, where="mid", color=colors[case], label=labels[case], lw=1.3)
    ax.set(title="Activity of the 1,500-neuron population", xlabel="Simulation time (ms)", ylabel="Spike count per 10 ms bin")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.2)
    fig.suptitle("FlyMind Escape Circuit: model response, not biological validation", fontsize=15)
    fig.supxlabel("Source: FlyWire FAFB v783; generic Shiu-inspired LIF; deterministic feature-drive assumptions", fontsize=10)
    output.mkdir(parents=True)
    fig.savefig(output / "escape-response.png", dpi=160)
    fig.savefig(output / "escape-response.svg")
    plt.close(fig)
    # Evidence for the primary diagnosis, with original membrane parameters unchanged.
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.8), constrained_layout=True)
    for i, rid in enumerate(cases["strong"]["simulation"]["readout_ids"]):
        for case, color, label in (("legacy_raw", "#6b7280", "Raw edge NT policy"),
                                    ("legacy_presynaptic", "#2263ad", "Cell-type / presynaptic NT policy")):
            row = next(r for r in report["runs"] if r["case"] == case)
            with gzip.open(row["output"], "rt") as stream:
                telemetry = json.load(stream)
            trace = telemetry["simulation"]["traces"]
            axes[i].plot(trace["readout_time_ms"], trace["readout_voltage_mv"][rid], color=color, label=label, lw=1.2)
        axes[i].axhline(-50, color="black", linestyle=":", label="Unchanged model threshold")
        axes[i].set(title=f"GF {'left' if i == 0 else 'right'}: {rid}", xlabel="Simulation time (ms)", ylabel="Membrane potential (mV)")
        axes[i].legend(fontsize=8)
        axes[i].grid(alpha=0.2)
    fig.suptitle("NT policy ablation: identical topology, input, synaptic gain and membrane parameters", fontsize=12)
    fig.supxlabel("FlyWire FAFB v783; modeled sign interpretation changes, raw biological annotations preserved", fontsize=9)
    fig.savefig(output / "transmitter-policy.png", dpi=160)
    fig.savefig(output / "transmitter-policy.svg")
    plt.close(fig)
    return {"output": str(output), "matplotlib_version": matplotlib.__version__, "biological_response_validated": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(plot_suite(args.suite, args.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
