"""Compare the browser bundle to real immutable engine exports, without rerunning them."""
import csv
import gzip
import importlib.util
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
DASH = ROOT / 'dashboard'
spec = importlib.util.spec_from_file_location('exporter', DASH / 'scripts/export_telemetry.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExportIntegrity(unittest.TestCase):
    def test_every_neuron_and_edge_row_matches_source(self):
        g = json.loads((DASH / 'public/data/graph.json').read_text())
        with (ROOT / 'data/neural/flywire_v783/neurons.csv').open() as stream:
            original = list(csv.DictReader(stream))
        for actual, source in zip(g['neurons'], original):
            self.assertEqual({k: actual[k] for k in source}, source)
        with (ROOT / 'data/neural/flywire_v783/connections.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        decoded = [{'pre_root_id': g['neurons'][e[0]]['root_id'], 'post_root_id': g['neurons'][e[1]]['root_id'],
                    'syn_count': str(e[2]), 'neuropil': g['neuropils'][e[3]], 'nt_type': g['raw_transmitters'][e[4]]} for e in g['edges']]
        self.assertEqual(decoded, rows)

    def test_all_spikes_and_every_recorded_voltage_are_exact(self):
        g = json.loads((DASH / 'public/data/graph.json').read_text())
        for case in ('baseline', 'weak', 'strong'):
            e = json.loads((DASH / f'public/data/{case}.json').read_text())
            with gzip.open(ROOT / e['source']['path'], 'rt') as f:
                source = json.load(f)
            self.assertEqual([{'time_ms': t, 'root_id': g['neurons'][i]['root_id']} for t, i in e['spikes']], source['simulation']['spikes'])
            self.assertEqual(e['stimulus'], source['simulation']['stimulus'])
            binary = (DASH / 'public/data' / e['voltage']['path']).read_bytes()
            for d in e['voltage']['traces']:
                root_id = g['neurons'][d['neuron_index']]['root_id']
                field = 'readout_voltage_mv' if d['phase'] == 'before_thresholds' else 'voltage_mv'
                values = struct.unpack_from(f"<{d['length']}d", binary, d['byte_offset'])
                self.assertEqual(list(values), source['simulation']['traces'][field][root_id])

    def test_soma_coordinates_are_pinned_source_values(self):
        annotations = ROOT / 'data/neural/cache/annotations.tsv'
        if not annotations.exists():
            self.skipTest('Optional pinned annotation cache unavailable')
        with annotations.open() as stream:
            rows = {r['root_id']: r for r in csv.DictReader(stream, delimiter='\t')}
        g = json.loads((DASH / 'public/data/graph.json').read_text())
        self.assertEqual(g['spatial']['source_sha256'], module.digest(annotations))
        for n in g['neurons']:
            r = rows[n['root_id']]
            expected = [float(r[f'soma_{a}']) for a in 'xyz'] if all(r[f'soma_{a}'] for a in 'xyz') else None
            self.assertEqual(n['soma_voxel'], expected)

    def test_export_is_deterministic_and_leaves_sources_unchanged(self):
        source_paths = list((ROOT / 'data/neural/flywire_v783').glob('*'))
        before = {str(p): module.digest(p) for p in source_paths if p.is_file()}
        annotations = ROOT / 'data/neural/cache/annotations.tsv'
        if not annotations.exists():
            self.skipTest('Optional pinned annotation cache unavailable')
        with tempfile.TemporaryDirectory() as temp:
            module.export(Path(temp), ROOT / 'data/neural/runs/escape-resumed-20261014/escape-suite.json', ROOT / 'data/neural/flywire_v783', annotations)
            for path in (DASH / 'public/data').iterdir():
                self.assertEqual(path.read_bytes(), (Path(temp) / path.name).read_bytes(), path.name)
        self.assertEqual(before, {str(p): module.digest(p) for p in source_paths if p.is_file()})

    def test_documented_cli_accepts_a_relative_suite_path(self):
        annotations = ROOT / 'data/neural/cache/annotations.tsv'
        if not annotations.exists():
            self.skipTest('Optional pinned annotation cache unavailable')
        with tempfile.TemporaryDirectory() as temp:
            subprocess.run([sys.executable, 'scripts/export_telemetry.py', '--suite',
                            '../data/neural/runs/escape-resumed-20261014/escape-suite.json',
                            '--output', temp], cwd=DASH, check=True, capture_output=True)
            actual = json.loads((Path(temp) / 'catalog.json').read_text())
            self.assertEqual([r['spikes'] for r in actual['experiments']], [0, 344, 834])


if __name__ == '__main__':
    unittest.main()
