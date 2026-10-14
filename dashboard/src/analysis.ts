import type { Graph, LoadedExperiment, Neuron } from './telemetry';
export const COLORS = { LC4: '#57bba8', LPLC2: '#829df5', GF: '#edb66b', partner: '#667487', baseline: '#8590a1', weak: '#829df5', strong: '#57bba8' };
export function kind(n: Neuron) { return n.role === 'readout' ? 'GF' : (n.cell_type || n.hemibrain_type || 'untyped'); }
export function neuronColor(n: Neuron) { const k = kind(n); return k === 'LC4' ? COLORS.LC4 : k === 'LPLC2' ? COLORS.LPLC2 : k === 'GF' ? COLORS.GF : COLORS.partner; }
export function interpretedNT(n: Neuron) { const mapping: Record<string,string> = { acetylcholine: 'ACH', gaba: 'GABA', glutamate: 'GLUT', dopamine: 'DA', serotonin: 'SER', octopamine: 'OCT' }; return n.known_nt_source && mapping[n.known_nt.toLowerCase()] ? mapping[n.known_nt.toLowerCase()] : n.predicted_nt || 'UNKNOWN'; }
export function modelSign(n: Neuron) { return ({ ACH: 1, GABA: -1, GLUT: -1, DA: 1, SER: 1, OCT: 1 } as Record<string,number>)[interpretedNT(n)] || 0; }
export type Pair = { pre: number; post: number; count: number; rows: number; rawNT: Record<string, number>; neuropils: Set<string> };
export function aggregatePairs(g: Graph): Pair[] {
  const result = new Map<string, Pair>();
  for (const [pre, post, count, neuropil, nt] of g.edges) {
    const key = `${pre}:${post}`;
    const p = result.get(key) || { pre, post, count: 0, rows: 0, rawNT: {}, neuropils: new Set<string>() };
    p.count += count; p.rows++; const raw = g.raw_transmitters[nt]; p.rawNT[raw] = (p.rawNT[raw] || 0) + count; p.neuropils.add(g.neuropils[neuropil]); result.set(key, p);
  }
  return [...result.values()].sort((a,b) => b.count - a.count || a.pre - b.pre || a.post - b.post);
}
export function displayPositions(g: Graph, anatomical: boolean): ([number,number,number] | null)[] {
  if (anatomical) {
    const physical = g.neurons.map(n => n.soma_voxel?.map((x, i) => x * g.spatial.voxel_nm[i] / 1000) as [number,number,number] | undefined);
    const points = physical.filter((p): p is [number,number,number] => !!p);
    const lo = [0,1,2].map(a => Math.min(...points.map(p => p[a])));
    const hi = [0,1,2].map(a => Math.max(...points.map(p => p[a])));
    const scale = 28 / Math.max(...hi.map((h,i) => h - lo[i]));
    return physical.map(p => p ? p.map((x,i) => (x - (lo[i] + hi[i]) / 2) * scale) as [number,number,number] : null);
  }
  // Deterministic type-group layout, dimensionless. Never called anatomy.
  const groups = new Map<string,number[]>();
  g.neurons.forEach((n,i) => { const k = ['LC4','LPLC2','GF'].includes(kind(n)) ? kind(n) : 'partner'; groups.set(k, [...(groups.get(k) || []), i]); });
  const positions: [number,number,number][] = g.neurons.map(() => [0,0,0]);
  for (const [group, indices] of groups) indices.forEach((index, j) => {
    const angle = j * 2.399963229728653;
    const radius = Math.sqrt((j + .5) / indices.length) * (group === 'partner' ? 9 : 4);
    const x = group === 'LC4' || group === 'LPLC2' ? -12 : group === 'GF' ? 12 : 0;
    positions[index] = [x + (group === 'partner' ? Math.sin(j * 1.618) * 3 : 0), Math.cos(angle) * radius + (group === 'LC4' ? 5 : group === 'LPLC2' ? -5 : 0), group === 'GF' ? (j === 0 ? -3 : 3) : Math.sin(angle) * radius];
  });
  return positions;
}
export function spikesUntil(e: LoadedExperiment, time: number) {
  let lo = 0, hi = e.spikes.length;
  while (lo < hi) { const mid = (lo + hi) >>> 1; if (e.spikes[mid][0] <= time) lo = mid + 1; else hi = mid; }
  return lo;
}
export function recentSpikes(e: LoadedExperiment, time: number, windowMs = 20) { const set = new Set<number>(); for (let i = spikesUntil(e, Math.max(-1, time - windowMs)); i < spikesUntil(e,time); i++) set.add(e.spikes[i][1]); return set; }
export function advanceTime(time: number, deltaWallMs: number, speed: number, duration: number) { return Math.min(duration, Math.max(0, time + deltaWallMs * speed)); }
/** Min/max envelope retaining original sample indices. No interpolated voltages. */
export function sampleEnvelope(values: Float64Array, budget = 1000) {
  if (values.length <= budget) return Array.from(values, (_,i) => i);
  const chosen = new Set([0, values.length - 1]);
  const stride = Math.ceil(values.length / Math.floor(budget / 2));
  for (let start=0; start<values.length; start+=stride) { let lo=start, hi=start; for (let i=start+1;i<Math.min(start+stride, values.length);i++) { if (values[i]<values[lo]) lo=i; if (values[i]>values[hi]) hi=i; } chosen.add(lo); chosen.add(hi); }
  return [...chosen].sort((a,b) => a-b);
}
