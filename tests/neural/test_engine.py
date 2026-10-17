from dataclasses import replace
import math
import numpy as np
import pytest

from src.neural.engine import simulate
from src.neural.loader import load_connectome
from src.neural.models import Parameters
from .test_loader import DATA


@pytest.mark.parametrize("change", [
    {"dt_ms": 0}, {"tau_ms": float("nan")}, {"delay_ms": 0.15}, {"duration_ms": 40},
    {"threshold_mv": -70}, {"mv_per_synapse": -1}, {"stimulus_drive_mv": float("inf")},
])
def test_invalid_parameters_fail_before_simulating(change):
    with pytest.raises(ValueError):
        replace(Parameters(), **change).validate()


def test_no_drive_no_spikes(synthetic_graph):
    result = simulate(synthetic_graph, replace(Parameters(), stimulus_drive_mv=0))
    assert result.spikes == ()
    assert result.final_voltage_mv == (-65, -65, -65)


def test_lif_matches_analytic_threshold_time(synthetic_graph):
    p = replace(Parameters(), duration_ms=40, stimulus_start_ms=0, stimulus_stop_ms=30,
                mv_per_synapse=0, sample_ms=0.1)
    result = simulate(synthetic_graph, p)
    expected = -p.tau_ms * math.log(1 - (p.threshold_mv - p.rest_mv) / p.stimulus_drive_mv)
    assert abs(result.spikes[0]["time_ms"] - expected) <= p.dt_ms
    assert all(event["root_id"] == "1" for event in result.spikes)


def test_excitation_inhibition_delay_and_count_scaling(synthetic_graph):
    p = replace(Parameters(), duration_ms=40, stimulus_start_ms=0, stimulus_stop_ms=30, sample_ms=0.1)
    result = simulate(synthetic_graph, p)
    traces = result.traces["voltage_mv"]["2"]
    times = result.traces["time_ms"]
    first_input = next(e["time_ms"] for e in result.spikes if e["root_id"] == "1")
    before = [v for t, v in zip(times, traces) if t <= first_input + p.delay_ms]
    assert np.allclose(before, p.rest_mv)
    first_arrival = first_input + p.delay_ms + p.dt_ms
    first_jump = next(v for t, v in zip(times, traces) if t >= first_arrival - 1e-8)
    assert first_jump == pytest.approx(p.rest_mv + 100 * p.mv_per_synapse)
    assert result.final_voltage_mv[1] > p.rest_mv
    assert result.final_voltage_mv[2] < p.rest_mv
    assert result.signs == {"excitatory_rows": 1, "inhibitory_rows": 1, "zero_effect_rows": 0}


def test_invalid_stimulus_id(synthetic_graph):
    with pytest.raises(ValueError, match="IDs"):
        simulate(synthetic_graph, stimulus_ids=("4",))


def test_real_simulation_reproducible_stable_and_control():
    graph = load_connectome(DATA)
    first = simulate(graph)
    second = simulate(graph)
    assert first.activity_sha256 == second.activity_sha256
    assert first.as_dict() == second.as_dict()
    assert first.stability["all_sampled_and_final_voltages_finite"]
    assert first.stability["sampled_min_mv"] > -200
    assert first.stability["sampled_max_mv"] < 100
    assert any(a["spike_count"] for a in first.activity)
    for rid in {event["root_id"] for event in first.spikes}:
        times = [e["time_ms"] for e in first.spikes if e["root_id"] == rid]
        assert all(b - a >= 2.0 - 1e-8 for a, b in zip(times, times[1:]))
    control = simulate(graph, replace(Parameters(), stimulus_drive_mv=0))
    assert control.spikes == ()
    assert control.final_voltage_mv == (-65.0,) * len(graph.neurons)
