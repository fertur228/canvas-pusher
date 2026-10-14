"""Fixed-weight Brian2 leaky integrate-and-fire simulation.

Not a validated model of escape behavior. No learning or AI services. Run concurrent
experiments in separate processes: Brian's preferences are process-global.
"""
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import os
import tempfile

# Brian2 optionally imports matplotlib. Keep its cache writable without touching
# user configuration (also works in restricted CI environments).
os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "flymind-matplotlib"))

import brian2 as b2
import numpy as np

from .loader import Connectome
from .models import Parameters, effective_sign, NT_POLICIES
from .stimulus import DrivePlan


@dataclass(frozen=True)
class Result:
    parameters: dict
    stimulus_ids: tuple[str, ...]
    readout_ids: tuple[str, ...]
    spikes: tuple[dict, ...]
    activity: tuple[dict, ...]
    readout: tuple[dict, ...]
    traces: dict
    final_voltage_mv: tuple[float, ...]
    stability: dict
    signs: dict
    model: dict
    stimulus: dict

    def as_dict(self):
        return asdict(self)

    @property
    def activity_sha256(self):
        encoded = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(encoded.encode()).hexdigest()


def simulate(graph: Connectome, parameters: Parameters = Parameters(),
             stimulus_ids: tuple[str, ...] | None = None,
             readout_ids: tuple[str, ...] | None = None,
             *, synaptic_model: str = "voltage_jump", nt_policy: str = "edge_prediction",
             drive_plan: DrivePlan | None = None) -> Result:
    graph.validate()
    parameters.validate()
    ids = tuple(n.root_id for n in graph.neurons)
    index = {rid: i for i, rid in enumerate(ids)}
    cells = {n.root_id: n for n in graph.neurons}
    if synaptic_model not in {"voltage_jump", "exponential_current"} or nt_policy not in NT_POLICIES:
        raise ValueError("Unknown simulation model or transmitter policy")
    if drive_plan is not None:
        drive_plan.validate(graph, parameters.duration_ms, parameters.dt_ms)
        if stimulus_ids is not None and stimulus_ids != drive_plan.neuron_ids:
            raise ValueError("Conflicting stimulus selections")
        stimulus_ids = drive_plan.neuron_ids
    if stimulus_ids is None:
        stimulus_ids = tuple(n.root_id for n in graph.neurons if n.role == "stimulus")
    if readout_ids is None:
        readout_ids = tuple(n.root_id for n in graph.neurons if n.role == "readout")
    for selection in (stimulus_ids, readout_ids):
        if len(set(selection)) != len(selection) or not set(selection) <= index.keys():
            raise ValueError("Stimulus/readout IDs must be unique and present in the connectome")
    if any(cells[rid].role == "readout" for rid in stimulus_ids):
        raise ValueError("Direct Giant Fiber/readout stimulation is forbidden")
    previous_target = b2.prefs.codegen.target
    b2.prefs.codegen.target = "numpy"
    try:
        clock = b2.Clock(dt=parameters.dt_ms * b2.ms)
        namespace = {"rest": parameters.rest_mv * b2.mV, "tau": parameters.tau_ms * b2.ms,
                     "threshold_voltage": parameters.threshold_mv * b2.mV,
                     "reset_voltage": parameters.reset_mv * b2.mV,
                     "tau_syn": parameters.synaptic_tau_ms * b2.ms}
        drive_equation = "drive : volt"
        if drive_plan is not None:
            namespace["stimulus_wave"] = b2.TimedArray(drive_plan.drive_mv * b2.mV, dt=drive_plan.sample_ms * b2.ms)
            drive_equation = "drive = input_mask * stimulus_wave(t, input_channel) : volt\ninput_mask : 1 (constant)\ninput_channel : integer (constant)"
        equation = "dv/dt = (rest - v + drive)/tau : volt (unless refractory)"
        reset = "v = reset_voltage"
        on_pre = "v_post += w * int(not_refractory_post)"
        if synaptic_model == "exponential_current":
            equation = "dv/dt = (rest - v + g + drive)/tau : volt (unless refractory)\ndg/dt = -g/tau_syn : volt (unless refractory)"
            reset += "; g = 0*mV"
            on_pre = "g_post += w"
        group = b2.NeuronGroup(
            len(ids), equation + "\n" + drive_equation,
            threshold="v >= threshold_voltage", reset=reset,
            refractory=parameters.refractory_ms * b2.ms, method="exact", clock=clock,
            namespace=namespace,
        )
        group.v = parameters.rest_mv * b2.mV
        if drive_plan is None:
            group.drive = 0 * b2.mV
        else:
            group.input_mask = [int(rid in set(stimulus_ids)) for rid in ids]
            group.input_channel = [int("LPLC2" in (cells[rid].cell_type, cells[rid].hemibrain_type)) for rid in ids]
        links = b2.Synapses(group, group, "w : volt (constant)",
                           on_pre=on_pre,
                           delay=parameters.delay_ms * b2.ms, clock=clock)
        # Preserve one simulation link per measured neuron-neuron-neuropil row.
        if graph.synapses:
            links.connect(i=np.array([index[s.pre_root_id] for s in graph.synapses]),
                          j=np.array([index[s.post_root_id] for s in graph.synapses]))
            links.w = np.array([s.syn_count * parameters.mv_per_synapse * effective_sign(cells[s.pre_root_id], s, nt_policy)
                                for s in graph.synapses]) * b2.mV
        else:
            links.active = False
        spike_monitor = b2.SpikeMonitor(group)
        # All neurons sampled for stability; export a compact selection of traces.
        state_monitor = b2.StateMonitor(group, "v", record=True, dt=parameters.sample_ms * b2.ms)
        network = b2.Network(group, links, spike_monitor, state_monitor)
        readout_monitor = None
        if readout_ids:
            readout_monitor = b2.StateMonitor(group, "v", record=[index[rid] for rid in readout_ids],
                                             dt=parameters.dt_ms * b2.ms, when="before_thresholds")
            network.add(readout_monitor)
        if drive_plan is not None:
            network.run(parameters.duration_ms * b2.ms, namespace={})
        else:
            if parameters.stimulus_start_ms:
                network.run(parameters.stimulus_start_ms * b2.ms, namespace={})
            if stimulus_ids:
                group.drive[[index[rid] for rid in stimulus_ids]] = parameters.stimulus_drive_mv * b2.mV
            network.run((parameters.stimulus_stop_ms - parameters.stimulus_start_ms) * b2.ms, namespace={})
            group.drive = 0 * b2.mV
            if parameters.duration_ms > parameters.stimulus_stop_ms:
                network.run((parameters.duration_ms - parameters.stimulus_stop_ms) * b2.ms, namespace={})
        final = np.asarray(group.v / b2.mV)
        sampled = np.asarray(state_monitor.v / b2.mV)
        if not np.isfinite(sampled).all() or not np.isfinite(final).all():
            raise FloatingPointError("Non-finite membrane potentials")
        events = tuple({"root_id": ids[int(i)], "time_ms": round(float(t / b2.ms), 9)}
                       for i, t in zip(spike_monitor.i, spike_monitor.t))
        by_id = {rid: [] for rid in ids}
        for event in events:
            by_id[event["root_id"]].append(event["time_ms"])
        activity = tuple({"root_id": rid, "spike_count": len(by_id[rid]),
                          "first_spike_ms": by_id[rid][0] if by_id[rid] else None,
                          "rate_hz": len(by_id[rid]) * 1000 / parameters.duration_ms}
                         for rid in ids)
        readout_voltage = np.asarray(readout_monitor.v / b2.mV) if readout_monitor is not None else None
        readout_times = np.asarray(readout_monitor.t / b2.ms) if readout_monitor is not None else None
        if readout_voltage is not None and not np.isfinite(readout_voltage).all():
            raise FloatingPointError("Non-finite readout membrane potential")
        onset = drive_plan.metadata["parameters"]["start_ms"] if drive_plan is not None else parameters.stimulus_start_ms
        readout = tuple({"root_id": rid, "spike_times_ms": by_id[rid],
                         "latency_from_stimulus_ms": (by_id[rid][0] - onset) if by_id[rid] else None,
                         "peak_voltage_mv": float(readout_voltage[i].max()),
                         "peak_depolarization_mv": float(readout_voltage[i].max() - parameters.rest_mv),
                         "peak_time_ms": round(float(readout_times[int(readout_voltage[i].argmax())]), 9),
                         "final_voltage_mv": float(final[index[rid]]),
                         "sampling_phase": "before_thresholds", "sample_ms": parameters.dt_ms}
                        for i, rid in enumerate(readout_ids))
        traced = tuple(dict.fromkeys((*readout_ids, *stimulus_ids[:4])))
        signs = Counter(effective_sign(cells[s.pre_root_id], s, nt_policy) for s in graph.synapses)
        return Result(
            parameters=asdict(parameters), stimulus_ids=stimulus_ids, readout_ids=readout_ids,
            spikes=events, activity=activity, readout=readout,
            traces={"time_ms": np.round(np.asarray(state_monitor.t / b2.ms), 9).tolist(),
                    "voltage_mv": {rid: sampled[index[rid]].tolist() for rid in traced},
                    "readout_time_ms": np.round(readout_times, 9).tolist() if readout_times is not None else [],
                    "readout_voltage_mv": {rid: readout_voltage[i].tolist() for i, rid in enumerate(readout_ids)}},
            final_voltage_mv=tuple(float(v) for v in final),
            stability={"all_sampled_and_final_voltages_finite": True,
                       "sampled_min_mv": float(min(sampled.min(), final.min())),
                       "sampled_max_mv": float(max(sampled.max(), final.max())),
                       "max_spikes_per_neuron": int(max(spike_monitor.count))},
            signs={"excitatory_rows": signs[1], "inhibitory_rows": signs[-1], "zero_effect_rows": signs[0]},
            model={"synaptic_model": synaptic_model, "nt_policy": nt_policy,
                   "weight_interpretation": "increment to decaying g, not EPSP peak" if synaptic_model == "exponential_current" else "instantaneous v increment",
                   "biological_response_validated": False},
            stimulus=drive_plan.telemetry() if drive_plan is not None else {
                "kind": "rectangular_current_injection", "start_ms": parameters.stimulus_start_ms,
                "stop_ms": parameters.stimulus_stop_ms, "drive_mv": parameters.stimulus_drive_mv,
                "neuron_ids": list(stimulus_ids)},
        )
    finally:
        b2.prefs.codegen.target = previous_target
