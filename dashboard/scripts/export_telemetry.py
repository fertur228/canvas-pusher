"""Offline presentation export. Reads existing runs, never imports/runs the engine."""
import argparse
import csv
import gzip
import hashlib
import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 'flymind.observatory/v1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n')


def export(output, suite_path, graph_path, annotations_path):
    suite_path, graph_path, annotations_path = (p.resolve() for p in (suite_path, graph_path, annotations_path))
    manifest_path = graph_path / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for name, spec in manifest['files'].items():
        if digest(graph_path / name) != spec['sha256']:
            raise ValueError(f'Unverified source: {name}')
    with (graph_path / 'neurons.csv').open() as stream:
        neurons = list(csv.DictReader(stream))
    ids = [n['root_id'] for n in neurons]
    index = {rid: i for i, rid in enumerate(ids)}
    if len(index) != len(ids):
        raise ValueError('Duplicate neuron IDs')
    annotations = {}
    if annotations_path.exists():
        if digest(annotations_path) != manifest['sources']['annotations.tsv']['sha256']:
            raise ValueError('Unverified coordinate annotations')
        with annotations_path.open() as stream:
            annotations = {r['root_id']: r for r in csv.DictReader(stream, delimiter='\t') if r['root_id'] in index}
    for n in neurons:
        a = annotations.get(n['root_id'], {})
        values = [a.get(f'soma_{axis}', '') for axis in 'xyz']
        n['soma_voxel'] = [float(x) for x in values] if all(x and math.isfinite(float(x)) for x in values) else None
    with (graph_path / 'connections.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    neuropils = sorted({r['neuropil'] for r in rows})
    nts = sorted({r['nt_type'] for r in rows})
    edges = [[index[r['pre_root_id']], index[r['post_root_id']], int(r['syn_count']), neuropils.index(r['neuropil']), nts.index(r['nt_type'])] for r in rows]
    graph = {'schema': SCHEMA, 'dataset': manifest, 'manifest_sha256': digest(manifest_path),
             'neurons': neurons, 'edge_columns': ['pre_index', 'post_index', 'synapse_count', 'neuropil_index', 'raw_nt_index'],
             'edges': edges, 'neuropils': neuropils, 'raw_transmitters': nts,
             'spatial': {'soma_count': sum(n['soma_voxel'] is not None for n in neurons), 'voxel_nm': [4, 4, 40],
                         'source_sha256': digest(annotations_path) if annotations else None,
                         'source_url': manifest['sources']['annotations.tsv']['url'],
                         'column_reference': f"https://github.com/flyconnectome/flywire_annotations/blob/{manifest['annotation_commit']}/supplemental_files/Supplemental_files_columns.md",
                         'morphology_in_bundle': False,
                         'note': 'Real soma points only. Straight edges encode adjacency, not neurite paths. Missing soma are omitted in soma view.'}}
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / 'graph.json', graph)
    suite = json.loads(suite_path.read_text())
    catalog = []
    for case in ('baseline', 'weak', 'strong'):
        run = next(r for r in suite['runs'] if r['case'] == case)
        source = ROOT / run['output']
        with gzip.open(source, 'rt') as f:
            raw = json.load(f)
        sim = raw['simulation']
        if raw['neuron_ids'] != ids or raw['manifest_sha256'] != digest(manifest_path):
            raise ValueError('Experiment references a different graph')
        if raw['biological_response_validated'] is not False:
            raise ValueError('Unsupported validation claim')
        if set(sim['stimulus_ids']) & set(sim['readout_ids']):
            raise ValueError('Direct readout stimulation')
        traces = sim['traces']
        buffer = bytearray()
        descriptors = []
        all_signals = [(rid, traces['readout_time_ms'], values, 'before_thresholds') for rid, values in traces['readout_voltage_mv'].items()]
        all_signals += [(rid, traces['time_ms'], values, 'start') for rid, values in traces['voltage_mv'].items() if rid not in sim['readout_ids']]
        for rid, times, values, phase in all_signals:
            dt = sim['parameters']['dt_ms'] if phase == 'before_thresholds' else sim['parameters']['sample_ms']
            if len(times) != len(values) or any(abs(t - round(i * dt, 9)) > 1e-8 for i, t in enumerate(times)):
                raise ValueError('Irregular trace sampling needs a new encoding')
            descriptors.append({'neuron_index': index[rid], 'byte_offset': len(buffer), 'length': len(values),
                                'start_ms': 0, 'step_ms': dt, 'phase': phase, 'signal': 'recorded_simulation_voltage'})
            buffer.extend(struct.pack(f'<{len(values)}d', *values))
        binary_path = output / f'{case}.voltage.bin'
        binary_path.write_bytes(buffer)
        bins = [[i * 10, 0, 0, 0, 0] for i in range(math.ceil(sim['parameters']['duration_ms'] / 10))]
        spikes = []
        for event in sim['spikes']:
            ni, t = index[event['root_id']], event['time_ms']
            spikes.append([t, ni])
            b = bins[min(int(t // 10), len(bins) - 1)]
            b[1] += 1
            kind = neurons[ni]['cell_type'] or neurons[ni]['hemibrain_type']
            if kind in ('LC4', 'LPLC2', 'DNp01'):
                b[{'LC4': 2, 'LPLC2': 3, 'DNp01': 4}[kind]] += 1
        spikes.sort(key=lambda x: (x[0], x[1]))
        payload = {'schema': SCHEMA, 'id': case, 'biological_response_validated': False,
                   'graph_sha256': digest(output / 'graph.json'), 'source': {'path': str(source.relative_to(ROOT)), 'sha256': digest(source),
                     'activity_sha256': raw['activity_sha256'], 'created_at_utc': raw['created_at_utc'], 'source_code_sha256': run['source_code_sha256']},
                   'parameters': sim['parameters'], 'model': raw['model'], 'stimulus': sim['stimulus'],
                   'stimulus_indices': [index[rid] for rid in sim['stimulus_ids']],
                   'spikes': spikes, 'spike_columns': ['time_ms', 'neuron_index'], 'activity': sim['activity'], 'readout': sim['readout'],
                   'population': {'bin_ms': 10, 'columns': ['start_ms', 'all', 'LC4', 'LPLC2', 'GF'], 'bins': bins, 'signal': 'exact_spike_count_aggregation'},
                   'voltage': {'path': binary_path.name, 'encoding': 'float64-le', 'sha256': digest(binary_path), 'traces': descriptors},
                   'limitations': suite['limitations']}
        write_json(output / f'{case}.json', payload)
        catalog.append({'id': case, 'path': f'{case}.json', 'sha256': digest(output / f'{case}.json'),
                        'spikes': len(spikes), 'active_neurons': sum(a['spike_count'] > 0 for a in sim['activity']),
                        'gf_spikes': [len(r['spike_times_ms']) for r in sim['readout']],
                        'duration_ms': sim['parameters']['duration_ms'], 'contrast': sim['stimulus']['parameters']['contrast'],
                        'radius_over_speed_ms': sim['stimulus']['parameters']['radius_over_speed_ms']})
    files = {p.name: {'bytes': p.stat().st_size, 'gzip_bytes': len(gzip.compress(p.read_bytes(), mtime=0)), 'sha256': digest(p)} for p in sorted(output.iterdir()) if p.suffix in ('.json', '.bin') and p.name != 'catalog.json'}
    result = {'schema': SCHEMA, 'graph': {'path': 'graph.json', 'sha256': digest(output / 'graph.json')}, 'experiments': catalog,
              'biological_response_validated': False, 'units': {'time': 'ms', 'voltage': 'mV', 'soma': '4x4x40 nm voxel'},
              'source_suite': str(suite_path.relative_to(ROOT)), 'files': files}
    write_json(output / 'catalog.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=ROOT / 'dashboard/public/data')
    p.add_argument('--suite', type=Path, default=ROOT / 'data/neural/runs/escape-resumed-20261014/escape-suite.json')
    p.add_argument('--annotations', type=Path, default=ROOT / 'data/neural/cache/annotations.tsv')
    a = p.parse_args()
    result = export(a.output, a.suite, ROOT / 'data/neural/flywire_v783', a.annotations)
    print(json.dumps({'files': result['files'], 'experiments': result['experiments']}, indent=2))
