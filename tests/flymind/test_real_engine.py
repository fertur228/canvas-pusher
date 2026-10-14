"""SYNTHETIC Canvas events, REAL verified FlyWire network and actual simulation."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import pytest
from src.flymind.neural import NeuralRunner,SimulationFailure,ROOT
from src.flymind.sensory import encode
from src.flymind.events import Snapshot,adapt
from tests.flymind.test_events import ACCOUNT,NOW,LIVE
from datetime import timedelta


def test_real_fixed_engine_responses_match_previous_experiments_and_sources(monkeypatch):
    monkeypatch.setenv('CANVAS_API_KEY','SYNTHETIC SECRET MUST NOT ENTER CHILD')
    baseline=json.loads((ROOT/'docs/neural-escape-results.json').read_text())
    hashes={name:hashlib.sha256((ROOT/'src/neural'/name).read_bytes()).hexdigest() for name in ('engine.py','models.py','stimulus.py','escape.py','experiment.py')}
    for hours,case,count,gf in ((2,'strong',834,[3,4]),(120,'weak',344,[2,2])):
        _,events=adapt(ACCOUNT,'assignment',{**LIVE,'due_at':(NOW+timedelta(hours=hours)).isoformat()},Snapshot(),NOW)
        encoding=encode(events[0])
        assert encoding['case']==case
        result,blob=NeuralRunner().run(encoding)
        raw=json.loads(gzip.decompress(blob))
        assert result['readout']['population_spikes']==count
        assert result['readout']['gf_spikes']==gf
        expected=next(r for r in baseline['runs'] if r['case']==case)
        assert expected['spikes']==count
        # Native x86 libm differs from ARM by <=3.64e-12 in the measured probe.
        # A raw float hash is not a cross-platform numerical equivalence test.
        # Keep exact discrete/parameter/spike assertions and verify every float.
        from scripts.check_platform_reproducibility import compare
        with gzip.open(ROOT/f'data/neural/runs/escape-resumed-20261014/{case}-1.json.gz','rt') as f:
            reference=json.load(f)
        assert raw['simulation']['parameters']==reference['simulation']['parameters']
        assert raw['simulation']['spikes']==reference['simulation']['spikes']
        delta=compare(reference['simulation'],raw['simulation'])
        assert not delta['discrete_mismatches']
        assert delta['max_absolute_difference']<=1e-10
        repeated,_=NeuralRunner().run(encoding)  # Fresh process, not profile cache.
        assert result['activity_sha256']==repeated['activity_sha256']
        assert result['source_code_sha256']==hashes
        assert b'SYNTHETIC SECRET' not in gzip.decompress(blob)
        assert not set(raw['simulation']['stimulus_ids'])&set(raw['simulation']['readout_ids'])
        assert len(raw['neuron_ids'])==1500
        assert raw['biological_response_validated'] is False


def test_timeout_and_missing_interpreter_fail_safely(monkeypatch):
    def timeout(*args,**kwargs):
        assert 'CANVAS_API_KEY' not in kwargs['env']
        assert 'SUPABASE_SERVICE_KEY' not in kwargs['env']
        raise subprocess.TimeoutExpired(args[0],1)
    monkeypatch.setattr(subprocess,'run',timeout)
    with pytest.raises(SimulationFailure,match='timeout'):
        NeuralRunner().run({'version':'canvas-looming/v1','case':'strong'})
