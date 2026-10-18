"""Scientific-model regression and causality checks; not biological validation."""
from dataclasses import replace
from pathlib import Path
import math
import gzip
import json
import numpy as np
import pytest

from src.neural.models import Neuron, Synapse, Parameters, effective_sign, effective_transmitter, literature_parameters
from src.neural.loader import Connectome, load_connectome, sha256
from src.neural.engine import simulate
from src.neural.stimulus import Looming
from src.neural.escape import run_case
from .test_loader import DATA


def test_nt_policy_uses_evidence_without_changing_raw_annotation():
    # SYNTHETIC conflicting annotations to test provenance precedence, not biology.
    n = Neuron("1", predicted_nt="GABA", known_nt="acetylcholine", known_nt_source="SYNTHETIC citation")
    edge = Synapse("1", "2", "SYNTHETIC", 1, "GLUT")
    assert effective_sign(n, edge, "edge_prediction") == 0
    assert effective_transmitter(n, edge, "presynaptic_conservative") == ("ACH", "literature_cell_type_annotation")
    assert effective_sign(n, edge, "presynaptic_shiu") == 1
    assert edge.nt_type == "GLUT"
    assert n.predicted_nt == "GABA"
    without_evidence = replace(n, known_nt_source="")
    assert effective_sign(without_evidence, edge, "presynaptic_conservative") == -1


def test_unknown_transmitter_remains_unknown():
    # No fallback to excitatory or to a contradictory edge annotation.
    n = Neuron("1")
    edge = Synapse("1", "2", "SYNTHETIC", 1, "ACH")
    assert effective_transmitter(n, edge, "presynaptic_shiu")[0] == "UNKNOWN"
    assert effective_sign(n, edge, "presynaptic_shiu") == 0


@pytest.mark.parametrize("change", [{"radius_over_speed_ms": 0}, {"contrast": 1.1}, {"size_width_deg": 0},
                                   {"side": "invented"}, {"enabled_types": ("DNp01",)}, {"drive_scale_mv": float("nan")}])
def test_invalid_looming_rejected(change):
    graph = load_connectome(DATA)
    with pytest.raises(ValueError):
        replace(Looming(), **change).generate(graph, 1100)


def test_looming_geometry_sampling_and_gf_guard():
    graph = load_connectome(DATA)
    stimulus = Looming()
    plan = stimulus.generate(graph, 1100)
    plan.validate(graph, 1100, .1)
    assert len(plan.neuron_ids) == 314
    assert not {n.root_id for n in graph.neurons if n.role == "readout"} & set(plan.neuron_ids)
    i = int(stimulus.start_ms)
    assert plan.angle_deg[i] == pytest.approx(10)
    assert plan.angle_deg.max() <= 63
    expected_collision = 100 + 20 / math.tan(math.radians(5))
    assert plan.metadata["collision_time_ms"] == pytest.approx(expected_collision)
    active = np.flatnonzero(plan.angle_deg > 0)
    finite_difference = np.gradient(plan.angle_deg[active], plan.times_ms[active]) * 1000
    assert np.allclose(finite_difference[2:-2], plan.angular_velocity_deg_s[active][2:-2], rtol=.002)
    assert not plan.drive_mv[0].any()
    assert not plan.drive_mv[-1].any()
    assert not replace(stimulus, contrast=0).generate(graph, 1100).drive_mv.any()
    invalid = replace(plan, neuron_ids=(next(n.root_id for n in graph.neurons if n.role == "readout"),))
    with pytest.raises(ValueError, match="never Giant Fiber"):
        invalid.validate(graph, 1100, .1)


def test_direct_gf_stimulation_rejected():
    graph = load_connectome(DATA)
    gf = tuple(n.root_id for n in graph.neurons if n.role == "readout")
    with pytest.raises(ValueError, match="forbidden"):
        simulate(graph, stimulus_ids=gf)


def test_exponential_current_matches_analytic_single_synapse_kernel():
    # SYNTHETIC isolated two-neuron fixture, not a biological circuit.
    graph = Connectome((Neuron("1", role="stimulus"), Neuron("2", role="readout")),
                       (Synapse("1", "2", "SYNTHETIC", 1, "ACH"),),
                       {"kind": "synthetic_test_fixture"})
    p = replace(Parameters(), duration_ms=50, stimulus_start_ms=0, stimulus_stop_ms=15,
                mv_per_synapse=.275, sample_ms=.1)
    r = simulate(graph, p, synaptic_model="exponential_current")
    first = next(e["time_ms"] for e in r.spikes if e["root_id"] == "1")
    times = np.array(r.traces["readout_time_ms"])
    elapsed = np.maximum(0, times - first - p.delay_ms)
    expected = p.mv_per_synapse * p.synaptic_tau_ms / (p.tau_ms - p.synaptic_tau_ms) * (
        np.exp(-elapsed / p.tau_ms) - np.exp(-elapsed / p.synaptic_tau_ms))
    voltage = np.array(r.traces["readout_voltage_mv"]["2"]) - p.rest_mv
    assert np.allclose(voltage, expected, rtol=0, atol=1e-9)
    assert voltage.max() == pytest.approx(.04331, abs=.00002)
    assert voltage.max() < .275 / 5  # Published weight is NOT an instantaneous membrane jump.
    assert not r.readout[0]["spike_times_ms"]


def test_real_transmitter_policy_ablation_causes_gf_response_without_weight_tuning():
    graph = load_connectome(DATA)
    before = {name: sha256(DATA / name) for name in ("neurons.csv", "connections.csv", "manifest.json")}
    original = simulate(graph)
    interpreted = simulate(graph, nt_policy="presynaptic_conservative")
    assert len(original.spikes) == 988
    assert [len(gf["spike_times_ms"]) for gf in original.readout] == [0, 0]
    assert [len(gf["spike_times_ms"]) for gf in interpreted.readout] == [1, 3]
    assert original.parameters == interpreted.parameters
    assert all(gf["peak_voltage_mv"] < -50 for gf in original.readout)
    assert not set(interpreted.readout_ids) & set(interpreted.stimulus_ids)
    assert before == {name: sha256(DATA / name) for name in before}


def test_literature_profile_strong_response_control_and_repeatability():
    graph = load_connectome(DATA)
    p = literature_parameters()
    kwargs = {"nt_policy": "presynaptic_shiu", "synaptic_model": "exponential_current"}
    plan = Looming().generate(graph, p.duration_ms)
    first = simulate(graph, p, drive_plan=plan, **kwargs)
    second = simulate(graph, p, drive_plan=plan, **kwargs)
    assert first.activity_sha256 == second.activity_sha256
    assert all(gf["spike_times_ms"] for gf in first.readout)
    assert first.stability["all_sampled_and_final_voltages_finite"]
    assert -100 < first.stability["sampled_min_mv"]
    assert first.model["biological_response_validated"] is False
    baseline = simulate(graph, p, drive_plan=replace(Looming(), contrast=0).generate(graph, p.duration_ms), **kwargs)
    assert not baseline.spikes
    zero_synapses = simulate(graph, replace(p, mv_per_synapse=0), drive_plan=plan, **kwargs)
    assert zero_synapses.spikes  # sensory neurons still fire
    assert all(not gf["spike_times_ms"] and gf["peak_depolarization_mv"] == 0 for gf in zero_synapses.readout)
    finer = simulate(graph, replace(p, dt_ms=.05), drive_plan=plan, **kwargs)
    for coarse_gf, fine_gf in zip(first.readout, finer.readout):
        assert len(coarse_gf["spike_times_ms"]) == len(fine_gf["spike_times_ms"])
        # First latency converges to within one coarse integration step. Later
        # spikes can shift by >1 ms because threshold/reset events are sensitive;
        # do not assert or claim complete spike-train convergence.
        assert abs(coarse_gf["spike_times_ms"][0] - fine_gf["spike_times_ms"][0]) <= p.dt_ms + 1e-8


@pytest.mark.parametrize("filename", ["baseline.json.gz", "baseline.json"])
def test_validation_export_is_offline_and_preserves_evidence(tmp_path, monkeypatch, filename):
    import urllib.request
    def forbidden(*_, **__):
        raise AssertionError("Validation experiments must not access the network")
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    output = tmp_path / filename
    summary = run_case(DATA, output, "baseline")
    opener = gzip.open if output.suffix == ".gz" else open
    with opener(output, "rt") as stream:
        data = json.load(stream)
    assert summary["no_gf_direct_stimulation"]
    assert summary["spikes"] == 0
    assert "drive_mv" not in summary["stimulus_summary"]
    assert set(summary["stimulus_summary"]["peak_drive_mv"]) == {"LC4", "LPLC2"}
    assert data["biological_response_validated"] is False
    assert data["simulation"]["stimulus"]["biologically_calibrated"] is False
    assert len(summary["source_code_sha256"]) == 5
    assert data["simulation"]["model"]["weight_interpretation"] == "increment to decaying g, not EPSP peak"
