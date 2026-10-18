"""Deterministic feature-drive proxy for a dark approaching disk; not a retina model."""
from dataclasses import asdict, dataclass
import math
import numpy as np

from .loader import Connectome


@dataclass(frozen=True)
class Looming:
    radius_over_speed_ms: float = 20.0
    contrast: float = 1.0
    start_ms: float = 100.0
    initial_angle_deg: float = 10.0
    final_angle_deg: float = 63.0
    drive_scale_mv: float = 30.0
    velocity_reference_deg_s: float = 2000.0
    size_preference_deg: float = 60.0
    size_width_deg: float = 15.0
    side: str = "both"
    enabled_types: tuple[str, ...] = ("LC4", "LPLC2")
    sample_ms: float = 1.0

    def generate(self, graph: Connectome, duration_ms: float):
        numeric = [v for v in asdict(self).values() if isinstance(v, (int, float))]
        if not all(math.isfinite(v) for v in numeric):
            raise ValueError("Stimulus values must be finite")
        if (self.radius_over_speed_ms <= 0 or self.sample_ms <= 0 or self.start_ms < 0
                or self.drive_scale_mv < 0 or self.velocity_reference_deg_s <= 0
                or self.size_width_deg <= 0 or not 0 <= self.contrast <= 1
                or not 0 < self.initial_angle_deg < self.final_angle_deg < 180):
            raise ValueError("Invalid looming geometry or drive")
        if self.side not in {"both", "left", "right"} or not set(self.enabled_types) <= {"LC4", "LPLC2"}:
            raise ValueError("Stimulus may target only annotated LC4/LPLC2")
        collision = self.start_ms + self.radius_over_speed_ms / math.tan(math.radians(self.initial_angle_deg / 2))
        end = collision - self.radius_over_speed_ms / math.tan(math.radians(self.final_angle_deg / 2))
        if end >= duration_ms:
            raise ValueError("Simulation must include the full expansion and recovery")
        times = np.arange(0, duration_ms, self.sample_ms)
        remaining = collision - times
        active = (times >= self.start_ms) & (times <= end)
        theta = np.zeros_like(times)
        velocity = np.zeros_like(times)
        theta[active] = np.degrees(2 * np.arctan(self.radius_over_speed_ms / remaining[active]))
        velocity[active] = np.degrees(2 * self.radius_over_speed_ms / (remaining[active]**2 + self.radius_over_speed_ms**2)) * 1000
        # Qualitative structure from Ache 2019: LC4 velocity and LPLC2 size.
        # Gain, Gaussian preference/width and contrast mapping are assumed, not fitted.
        drive = np.zeros((len(times), 2))
        drive[active, 0] = self.contrast * self.drive_scale_mv * velocity[active] / self.velocity_reference_deg_s
        drive[active, 1] = self.contrast * self.drive_scale_mv * np.exp(-0.5 * ((theta[active] - self.size_preference_deg) / self.size_width_deg)**2)
        if "LC4" not in self.enabled_types:
            drive[:, 0] = 0
        if "LPLC2" not in self.enabled_types:
            drive[:, 1] = 0
        ids = tuple(n.root_id for n in graph.neurons
                    if {n.cell_type, n.hemibrain_type} & set(self.enabled_types)
                    and (self.side == "both" or n.side == self.side))
        if not ids:
            raise ValueError("No annotated sensory cells match the stimulus")
        if any(n.role == "readout" for n in graph.neurons if n.root_id in ids):
            raise ValueError("Giant Fiber/readout stimulation is forbidden")
        return DrivePlan(ids, self.sample_ms, drive, times, theta, velocity,
                         {"kind": "looming_feature_drive_proxy", "parameters": asdict(self),
                          "collision_time_ms": collision, "expansion_end_ms": end,
                          "biologically_calibrated": False,
                          "references": ["https://doi.org/10.1016/j.cub.2019.01.079", "https://doi.org/10.1242/jeb.244790"]})


@dataclass(frozen=True)
class DrivePlan:
    neuron_ids: tuple[str, ...]
    sample_ms: float
    drive_mv: np.ndarray
    times_ms: np.ndarray
    angle_deg: np.ndarray
    angular_velocity_deg_s: np.ndarray
    metadata: dict

    def validate(self, graph: Connectome, duration_ms: float, dt_ms: float):
        if self.sample_ms < dt_ms or not math.isclose(self.sample_ms / dt_ms, round(self.sample_ms / dt_ms), abs_tol=1e-8):
            raise ValueError("Input sampling interval must be a multiple of engine dt")
        if self.drive_mv.shape != (len(self.times_ms), 2) or not np.isfinite(self.drive_mv).all() or (self.drive_mv < 0).any():
            raise ValueError("Invalid drive array")
        if len(self.times_ms) != math.ceil(duration_ms / self.sample_ms):
            raise ValueError("Drive must cover simulation duration")
        if not np.allclose(self.times_ms, np.arange(0, duration_ms, self.sample_ms), rtol=0, atol=1e-8):
            raise ValueError("Drive timestamps must start at zero and be uniformly sampled")
        cells = {n.root_id: n for n in graph.neurons}
        if len(set(self.neuron_ids)) != len(self.neuron_ids):
            raise ValueError("Duplicate stimulus ID")
        for rid in self.neuron_ids:
            if rid not in cells or cells[rid].role == "readout" or not {cells[rid].cell_type, cells[rid].hemibrain_type} & {"LC4", "LPLC2"}:
                raise ValueError("Drive may target only LC4/LPLC2, never Giant Fiber")

    def telemetry(self):
        return {**self.metadata, "neuron_ids": list(self.neuron_ids), "sample_ms": self.sample_ms,
                "times_ms": self.times_ms.tolist(), "angle_deg": self.angle_deg.tolist(),
                "angular_velocity_deg_s": self.angular_velocity_deg_s.tolist(),
                "drive_mv": {"LC4": self.drive_mv[:, 0].tolist(), "LPLC2": self.drive_mv[:, 1].tolist()},
                "peak_drive_mv": {kind: float(self.drive_mv[:, i].max()) for i, kind in enumerate(("LC4", "LPLC2"))},
                "drive_integral_mv_ms": {kind: float(self.drive_mv[:, i].sum() * self.sample_ms) for i, kind in enumerate(("LC4", "LPLC2"))}}
