export const SCHEMA = 'flymind.observatory/v1' as const;
export type ExperimentId = 'baseline' | 'weak' | 'strong';
export type Neuron = { root_id: string; cell_type: string; hemibrain_type: string; side: string; role: string; predicted_nt: string; predicted_nt_confidence: string; known_nt: string; known_nt_source: string; soma_voxel: [number, number, number] | null };
export type EdgeRow = [number, number, number, number, number];
export type Graph = { schema: typeof SCHEMA; neurons: Neuron[]; edges: EdgeRow[]; neuropils: string[]; raw_transmitters: string[]; manifest_sha256: string; dataset: { counts: { neurons: number; connection_rows: number; directed_pairs: number; synapses: number }; license: string; license_url: string; version: string; citations: string[]; limitations: string[] }; spatial: { soma_count: number; voxel_nm: [number, number, number]; column_reference: string; source_sha256: string | null; morphology_in_bundle: false; note: string } };
export type Descriptor = { neuron_index: number; byte_offset: number; length: number; start_ms: number; step_ms: number; phase: string; signal: 'recorded_simulation_voltage' };
export type Readout = { root_id: string; spike_times_ms: number[]; latency_from_stimulus_ms: number | null; peak_depolarization_mv: number; peak_voltage_mv: number; peak_time_ms: number; sample_ms: number };
export type Experiment = { schema: typeof SCHEMA; id: ExperimentId; biological_response_validated: false; graph_sha256: string; source: { path: string; sha256: string; activity_sha256: string; created_at_utc: string; source_code_sha256: Record<string, string> }; parameters: Record<string, number>; model: { nt_policy: string; synaptic_model: string; weight_interpretation: string; [key: string]: unknown }; stimulus: { biologically_calibrated: false; parameters: { contrast: number; start_ms: number; radius_over_speed_ms: number }; expansion_end_ms: number; times_ms: number[]; angle_deg: number[]; angular_velocity_deg_s: number[]; drive_mv: { LC4: number[]; LPLC2: number[] }; peak_drive_mv: { LC4: number; LPLC2: number }; drive_integral_mv_ms: { LC4: number; LPLC2: number } }; stimulus_indices: number[]; spikes: [number, number][]; activity: { root_id: string; spike_count: number; rate_hz: number }[]; readout: Readout[]; population: { bin_ms: number; bins: [number, number, number, number, number][]; signal: string }; voltage: { path: string; encoding: 'float64-le'; sha256: string; traces: Descriptor[] }; limitations: string[] };
export type LoadedExperiment = Experiment & { signals: Map<number, { descriptor: Descriptor; values: Float64Array }> };
export type CatalogEntry = { id: ExperimentId; path: string; sha256: string; spikes: number; active_neurons: number; gf_spikes: number[]; duration_ms: number; contrast: number; radius_over_speed_ms: number };
export type Catalog = { schema: typeof SCHEMA; biological_response_validated: false; graph: { path: string; sha256: string }; experiments: CatalogEntry[]; files: Record<string, { bytes: number; gzip_bytes: number; sha256: string }> };

export function assertVersion(value: unknown): asserts value is { schema: typeof SCHEMA } {
  if (!value || typeof value !== 'object' || !('schema' in value) || value.schema !== SCHEMA) throw new Error('Unsupported telemetry schema. Expected ' + SCHEMA);
}
export function validateGraph(value: unknown): Graph {
  assertVersion(value);
  const g = value as Graph;
  if (!Array.isArray(g.neurons) || !Array.isArray(g.edges) || !Array.isArray(g.neuropils) || !Array.isArray(g.raw_transmitters) || !g.dataset?.counts || !g.spatial) throw new Error('Incomplete graph');
  const ids = new Set<string>();
  for (const n of g.neurons) {
    if (typeof n.root_id !== 'string' || !/^\d{18}$/.test(n.root_id) || ids.has(n.root_id)) throw new Error('Invalid or duplicate real neuron ID');
    ids.add(n.root_id);
    if (n.soma_voxel !== null && (!Array.isArray(n.soma_voxel) || n.soma_voxel.length !== 3 || !n.soma_voxel.every(Number.isFinite))) throw new Error('Invalid soma coordinate');
  }
  for (const e of g.edges) if (e.length !== 5 || !e.every(Number.isInteger) || e[0] < 0 || e[1] < 0 || e[0] >= ids.size || e[1] >= ids.size || e[2] <= 0 || !g.neuropils[e[3]] || !g.raw_transmitters[e[4]]) throw new Error('Invalid connectivity row');
  if (ids.size !== g.dataset.counts.neurons || g.edges.length !== g.dataset.counts.connection_rows || g.edges.reduce((s, e) => s + e[2], 0) !== g.dataset.counts.synapses) throw new Error('Graph counts do not match source manifest');
  if (g.neurons.filter(n => n.soma_voxel).length !== g.spatial.soma_count) throw new Error('Soma coverage mismatch');
  return g;
}
export function validateExperiment(value: unknown, graph: Graph, graphHash: string): Experiment {
  assertVersion(value);
  const e = value as Experiment;
  if (e.graph_sha256 !== graphHash || e.biological_response_validated !== false || e.stimulus?.biologically_calibrated !== false || e.voltage?.encoding !== 'float64-le') throw new Error('Experiment provenance or encoding mismatch');
  if (!Number.isFinite(e.parameters?.duration_ms) || e.parameters.duration_ms <= 0 || !Array.isArray(e.spikes) || !Array.isArray(e.activity) || e.activity.length !== graph.neurons.length) throw new Error('Incomplete experiment');
  const counts = new Uint32Array(graph.neurons.length);
  let last = -Infinity;
  for (const [t, i] of e.spikes) {
    if (!Number.isFinite(t) || t < 0 || t >= e.parameters.duration_ms || t < last || !Number.isInteger(i) || i < 0 || i >= counts.length) throw new Error('Invalid or unsorted spike event');
    counts[i]++; last = t;
  }
  e.activity.forEach((a, i) => { if (a.root_id !== graph.neurons[i].root_id || a.spike_count !== counts[i]) throw new Error('Activity does not match exact spike events'); });
  if (e.stimulus_indices.some(i => !graph.neurons[i] || graph.neurons[i].role === 'readout')) throw new Error('Forbidden direct GF stimulation');
  if (e.population.bins.reduce((s, b) => s + b[1], 0) !== e.spikes.length) throw new Error('Population count mismatch');
  const len = e.stimulus.times_ms.length;
  for (const arr of [e.stimulus.times_ms, e.stimulus.angle_deg, e.stimulus.angular_velocity_deg_s, e.stimulus.drive_mv.LC4, e.stimulus.drive_mv.LPLC2]) if (arr.length !== len || !arr.every(Number.isFinite)) throw new Error('Invalid stimulus samples');
  return e;
}
export function decodeVoltage(e: Experiment, buffer: ArrayBuffer, graph: Graph): LoadedExperiment {
  const signals: LoadedExperiment['signals'] = new Map();
  const view = new DataView(buffer);
  for (const d of e.voltage.traces) {
    if (!graph.neurons[d.neuron_index] || !Number.isInteger(d.length) || d.length < 1 || !Number.isInteger(d.byte_offset) || d.byte_offset < 0 || d.byte_offset + d.length * 8 > buffer.byteLength || !Number.isFinite(d.step_ms) || d.step_ms <= 0 || d.start_ms !== 0 || signals.has(d.neuron_index)) throw new Error('Invalid voltage descriptor or truncated file');
    const values = new Float64Array(d.length);
    for (let i = 0; i < d.length; i++) { values[i] = view.getFloat64(d.byte_offset + i * 8, true); if (!Number.isFinite(values[i])) throw new Error('Nonfinite recorded voltage'); }
    signals.set(d.neuron_index, { descriptor: d, values });
  }
  return { ...e, signals };
}
