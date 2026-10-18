"""Measured graph fields and explicitly assumed simulation parameters."""
from dataclasses import dataclass
import math
import re


def root_id(value: str) -> str:
    # Keep uint64 identifiers as strings throughout, including JSON for JS clients.
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*", value):
        raise ValueError(f"Invalid root ID: {value!r}")
    if int(value) >= 2**64:
        raise ValueError("Root ID exceeds uint64")
    return value


@dataclass(frozen=True)
class Neuron:
    root_id: str
    cell_type: str = ""
    hemibrain_type: str = ""
    side: str = ""
    predicted_nt: str = ""
    predicted_nt_confidence: str = ""
    known_nt: str = ""
    known_nt_source: str = ""
    role: str = "partner"

    def __post_init__(self):
        root_id(self.root_id)
        if self.role not in {"stimulus", "readout", "partner"}:
            raise ValueError("Invalid neuron role")


@dataclass(frozen=True)
class Synapse:
    pre_root_id: str
    post_root_id: str
    neuropil: str
    syn_count: int
    nt_type: str

    def __post_init__(self):
        root_id(self.pre_root_id)
        root_id(self.post_root_id)
        if type(self.syn_count) is not int or self.syn_count < 1:
            raise ValueError("Synapse count must be a positive integer")
        if not self.neuropil:
            raise ValueError("Missing neuropil")
        if self.nt_type not in {"ACH", "GABA", "GLUT", "DA", "SER", "OCT", "UNKNOWN"}:
            raise ValueError("Unrecognized transmitter annotation")


@dataclass(frozen=True)
class Parameters:
    duration_ms: float = 200.0
    dt_ms: float = 0.1
    tau_ms: float = 20.0
    rest_mv: float = -65.0
    reset_mv: float = -65.0
    threshold_mv: float = -50.0
    refractory_ms: float = 2.0
    delay_ms: float = 1.0
    mv_per_synapse: float = 0.02
    stimulus_start_ms: float = 20.0
    stimulus_stop_ms: float = 80.0
    stimulus_drive_mv: float = 30.0
    sample_ms: float = 1.0
    synaptic_tau_ms: float = 5.0

    def validate(self):
        for value in self.__dict__.values():
            if not math.isfinite(value):
                raise ValueError("Parameters must be finite")
        for name in ("duration_ms", "dt_ms", "tau_ms", "refractory_ms", "delay_ms", "sample_ms", "synaptic_tau_ms"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not self.rest_mv <= self.reset_mv < self.threshold_mv:
            raise ValueError("Require rest <= reset < threshold")
        if self.dt_ms > self.tau_ms / 10:
            raise ValueError("Time step too coarse")
        if self.mv_per_synapse < 0 or self.stimulus_drive_mv < 0:
            raise ValueError("Strength and stimulus drive must be nonnegative")
        if not 0 <= self.stimulus_start_ms < self.stimulus_stop_ms <= self.duration_ms:
            raise ValueError("Stimulus must lie within the simulation")
        for name in ("duration_ms", "refractory_ms", "delay_ms", "sample_ms", "stimulus_start_ms", "stimulus_stop_ms"):
            steps = getattr(self, name) / self.dt_ms
            if not math.isclose(steps, round(steps), abs_tol=1e-8):
                raise ValueError(f"{name} must be a multiple of dt_ms")


def synaptic_sign(nt_type: str) -> int:
    """Conservative polarity assumption, NOT a measured receptor annotation.

    ACh excitatory and GABA inhibitory. Glutamate (receptor dependent), monoamines,
    and unknown remain zero-effect; their measured connections are retained.
    """
    return {"ACH": 1, "GABA": -1}.get(nt_type, 0)


NT_POLICIES = {"edge_prediction", "presynaptic_conservative", "presynaptic_shiu"}


def effective_transmitter(neuron: Neuron, synapse: Synapse, policy: str) -> tuple[str, str]:
    """Return a MODEL interpretation, never replace a raw dataset annotation.

    known_nt is a cell-type literature annotation, not a measured receptor on this
    particular synapse. Whole-neuron predictions can disagree with edge predictions.
    """
    if policy not in NT_POLICIES:
        raise ValueError("Unknown transmitter policy")
    if policy == "edge_prediction":
        return synapse.nt_type, "raw_edge_prediction"
    mapping = {"acetylcholine": "ACH", "gaba": "GABA", "glutamate": "GLUT",
               "dopamine": "DA", "serotonin": "SER", "octopamine": "OCT"}
    if neuron.known_nt and neuron.known_nt_source and neuron.known_nt.lower() in mapping:
        return mapping[neuron.known_nt.lower()], "literature_cell_type_annotation"
    return neuron.predicted_nt or "UNKNOWN", "whole_neuron_prediction"


def effective_sign(neuron: Neuron, synapse: Synapse, policy: str) -> int:
    transmitter, _ = effective_transmitter(neuron, synapse, policy)
    if policy == "presynaptic_shiu":
        # Published model convention, explicitly not receptor-level evidence.
        return {"ACH": 1, "GABA": -1, "GLUT": -1, "DA": 1, "SER": 1, "OCT": 1}.get(transmitter, 0)
    return synaptic_sign(transmitter)


def literature_parameters(duration_ms: float = 1100.0, dt_ms: float = 0.1) -> Parameters:
    """Shiu et al. published parameterisation, NOT GF-specific calibration.

    0.275 mV is an increment to decaying g, and a free model parameter; it must
    not be applied as an instantaneous 0.275 mV membrane-potential jump.
    """
    return Parameters(duration_ms=duration_ms, dt_ms=dt_ms, rest_mv=-52, reset_mv=-52,
                      threshold_mv=-45, tau_ms=20, synaptic_tau_ms=5,
                      refractory_ms=2.2, delay_ms=1.8, mv_per_synapse=0.275,
                      stimulus_start_ms=100, stimulus_stop_ms=1000)
