"""Engineering event-to-sensory mapping. NOT a physiological Canvas sense."""
from datetime import timedelta
from .events import CanvasEvent, EventKind, utc

ENCODER_VERSION = 'canvas-looming/v1'
READOUT_VERSION = 'experimental-urgency/v1'


def encode(event: CanvasEvent) -> dict | None:
    if event.entity_type != 'assignment':
        return None
    payload = event.payload
    strong = event.priority == 2 or event.reminder in ('12h', '3h', '1h', 'overdue')
    if payload.get('due_at') and not payload.get('has_submitted'):
        strong |= utc(payload['due_at']) - utc(event.observed_at) <= timedelta(hours=24)
    if event.kind == EventKind.GRADE:
        points, score = payload.get('points_possible'), payload.get('score')
        strong |= points is not None and points > 0 and score is not None and score / points < .6
    profile = 'strong' if strong else 'weak'
    return {'version': ENCODER_VERSION, 'case': profile,
            'meaning': 'Engineering mapping to an existing recorded-protocol hypothesis, not a biological Canvas sense',
            'stimulus': {'contrast': 1.0 if strong else .35, 'radius_over_speed_ms': 20 if strong else 80,
                         'targets': ['LC4', 'LPLC2'], 'direct_gf_stimulation': False},
            'parameters_policy': 'Unchanged literature_parameters + presynaptic_shiu + exponential_current'}


def readout(summary: dict) -> dict:
    gf = [len(r['spike_times_ms']) for r in summary['readout']]
    active = summary['active_neurons']
    label = 'elevated' if sum(gf) >= 6 and active >= 400 else 'moderate' if sum(gf) >= 1 or active >= 100 else 'minimal'
    return {'version': READOUT_VERSION, 'classification': label, 'gf_spikes': gf,
            'active_neurons': active, 'population_spikes': summary['spikes'],
            'gf_first_latency_ms': [r['latency_from_stimulus_ms'] for r in summary['readout']],
            'gf_peak_model_depolarization_mv': [r['peak_depolarization_mv'] for r in summary['readout']],
            'biological_response_validated': False,
            'thresholds': 'ENGINEERING: elevated iff GF total >=6 and active cells >=400; moderate iff GF>=1 or active>=100; otherwise minimal',
            'limitation': 'Not calibrated urgency or escape behavior; generic LIF and uncalibrated recruitment; suprathreshold peaks depend on reset'}
