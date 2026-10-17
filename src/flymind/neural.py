"""Bounded fresh-process real-connectome runner; no Canvas identifiers in child input."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from .sensory import readout

ROOT = Path(__file__).resolve().parents[2]


class SimulationFailure(Exception):
    pass


class NeuralRunner:
    def __init__(self, timeout_seconds=30, python=sys.executable):
        self.timeout_seconds, self.python = timeout_seconds, python
        self._cache = {}

    def run(self, encoding: dict) -> tuple[dict, bytes]:
        if encoding.get('version') != 'canvas-looming/v1' or encoding.get('case') not in ('weak', 'strong'):
            raise SimulationFailure('unsupported_encoding')
        key=json.dumps(encoding,sort_keys=True)
        if key in self._cache:
            result,blob=self._cache[key]
            return copy.deepcopy(result),blob
        with TemporaryDirectory(prefix='flymind-private-') as temp:
            output = Path(temp) / 'telemetry.json.gz'
            env = {k: os.environ[k] for k in ('PATH', 'SYSTEMROOT', 'TMPDIR', 'LANG') if k in os.environ}
            env.update({'PYTHONPATH': str(ROOT), 'MPLCONFIGDIR': temp, **{k: '1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS')}})
            try:
                child = subprocess.run([self.python, '-m', 'src.flymind.neural_child', '--case', encoding['case'],
                                        '--connectome', str(ROOT / 'data/neural/flywire_v783'), '--output', str(output)],
                                       cwd=ROOT, env=env, capture_output=True, timeout=self.timeout_seconds, check=True)
                summary = json.loads(child.stdout)
                if not summary.get('no_gf_direct_stimulation') or summary['model']['biological_response_validated'] is not False or summary['counts']['neurons'] != 1500:
                    raise SimulationFailure('unexpected_model')
                blob = output.read_bytes()
                result = {'status': 'complete', 'encoding': encoding, 'readout': readout(summary),
                          'activity_sha256': summary['activity_sha256'], 'source_code_sha256': summary['source_code_sha256'],
                          'telemetry_sha256': hashlib.sha256(blob).hexdigest(), 'measurements': summary['measurements'],
                          'biological_response_validated': False}
                self._cache[key]=(copy.deepcopy(result),blob)
                return result, blob
            except subprocess.TimeoutExpired:
                raise SimulationFailure('simulation_timeout') from None
            except (subprocess.CalledProcessError, OSError, ValueError, KeyError):
                raise SimulationFailure('simulation_failed') from None
