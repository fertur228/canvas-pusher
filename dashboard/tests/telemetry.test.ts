import { readFileSync } from 'node:fs';
import { webcrypto } from 'node:crypto';
import { describe, expect, it, vi } from 'vitest';
import { assertVersion, decodeVoltage, validateExperiment, validateGraph } from '../src/telemetry';
import type { Catalog, Experiment, LoadedExperiment } from '../src/telemetry';
import { advanceTime, aggregatePairs, displayPositions, modelSign, recentSpikes, sampleEnvelope, spikesUntil } from '../src/analysis';
import { HttpTelemetrySource } from '../src/data';
vi.stubGlobal('crypto',webcrypto);
const base=new URL('../public/data/',import.meta.url);
const json=(name:string)=>JSON.parse(readFileSync(new URL(name,base),'utf8'));
const bytes=(name:string)=>{const b=readFileSync(new URL(name,base));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength) as ArrayBuffer;};
const catalog=json('catalog.json') as Catalog;
const graph=validateGraph(json('graph.json'));
function load(id:string):LoadedExperiment {const e=validateExperiment(json(`${id}.json`),graph,catalog.graph.sha256);return decodeVoltage(e,bytes(e.voltage.path),graph);}
const strong=load('strong');
describe('real FlyWire telemetry',()=>{
 it('preserves exact counts and directed pairs',()=>{expect(graph.neurons).toHaveLength(1500);expect(graph.edges).toHaveLength(25206);const pairs=aggregatePairs(graph);expect(pairs).toHaveLength(17186);expect(pairs.reduce((s,e)=>s+e.count,0)).toBe(276399);});
 it('preserves uint64 IDs as strings',()=>{expect(graph.neurons.every(n=>typeof n.root_id==='string')).toBe(true);expect(graph.neurons.filter(n=>n.role==='readout').map(n=>n.root_id)).toEqual(['720575940622838154','720575940632499757']);});
 it('does not replace conflicting raw NT annotations with model signs',()=>{const sensory=new Set(graph.neurons.map((n,i)=>['LC4','LPLC2'].includes(n.cell_type||n.hemibrain_type)?i:-1));expect(graph.edges.some(e=>sensory.has(e[0])&&graph.raw_transmitters[e[4]]!=='ACH'&&modelSign(graph.neurons[e[0]])===1)).toBe(true);});
 it.each([['baseline',0,0,[0,0]],['weak',344,282,[2,2]],['strong',834,418,[3,4]]] as const)('matches measured %s response',(id,total,active,gf)=>{const e=load(id);expect(e.spikes.length).toBe(total);expect(e.activity.filter(a=>a.spike_count).length).toBe(active);expect(e.readout.map(r=>r.spike_times_ms.length)).toEqual(gf);expect(e.biological_response_validated).toBe(false);expect(e.stimulus_indices.every(i=>graph.neurons[i].role!=='readout')).toBe(true);});
 it('has six recorded traces, never invents others',()=>{expect(strong.signals.size).toBe(6);const ni=graph.neurons.findIndex(n=>n.role==='readout');expect(strong.signals.get(ni)!.values.length).toBe(11000);expect(strong.signals.get(ni)!.values[0]).toBe(-52);expect(strong.signals.has(0)).toBe(false);});
 it('keeps silent baseline voltage exactly at rest',()=>{for(const signal of load('baseline').signals.values())expect(signal.values.every(v=>v===-52)).toBe(true);});
 it('reconstructs bins exactly from original spike events',()=>{const expected=Array(110).fill(0);for(const [t] of strong.spikes)expected[Math.floor(t/10)]++;expect(strong.population.bins.map(b=>b[1])).toEqual(expected);});
 it('has genuine soma coverage, omits missing coordinates',()=>{expect(graph.spatial.soma_count).toBe(1497);const pos=displayPositions(graph,true);expect(pos.filter(Boolean)).toHaveLength(1497);graph.neurons.forEach((n,i)=>{if(!n.soma_voxel)expect(pos[i]).toBe(null);});});
 it('scales anatomical axes with voxel anisotropy before centering',()=>{const pos=displayPositions(graph,true);const i=0,j=1;const rawI=graph.neurons[i].soma_voxel!,rawJ=graph.neurons[j].soma_voxel!;const sx=(pos[i]![0]-pos[j]![0])/((rawI[0]-rawJ[0])*4);const sz=(pos[i]![2]-pos[j]![2])/((rawI[2]-rawJ[2])*40);expect(sx).toBeCloseTo(sz,12);});
 it('uses a deterministic non-anatomical layout',()=>{expect(displayPositions(graph,false)).toEqual(displayPositions(graph,false));expect(displayPositions(graph,false).flat().every(Number.isFinite)).toBe(true);});
 it('rejects schema changes, numeric IDs and invented edges',()=>{expect(()=>assertVersion({schema:'v999'})).toThrow();const bad=structuredClone(graph);bad.neurons[0].root_id=720575940601712649 as unknown as string;expect(()=>validateGraph(bad)).toThrow();const edge=structuredClone(graph);edge.edges[0][0]=1501;expect(()=>validateGraph(edge)).toThrow();});
 it('rejects graph mismatch, corrupt spike totals and direct GF drive',()=>{const e=json('strong.json') as Experiment;expect(()=>validateExperiment(e,graph,'wrong')).toThrow();e.activity[0].spike_count++;expect(()=>validateExperiment(e,graph,catalog.graph.sha256)).toThrow();const direct=json('strong.json') as Experiment;direct.stimulus_indices.push(graph.neurons.findIndex(n=>n.role==='readout'));expect(()=>validateExperiment(direct,graph,catalog.graph.sha256)).toThrow();});
 it('rejects truncated binary signals',()=>{expect(()=>decodeVoltage(json('strong.json'),new ArrayBuffer(8),graph)).toThrow();});
});
describe('replay and plotting',()=>{
 it('is independent of wall frame rate and clamps at boundaries',()=>{expect(advanceTime(100,1000,.1,1100)).toBe(200);expect(advanceTime(1099,1000,2,1100)).toBe(1100);expect(advanceTime(-10,0,1,1100)).toBe(0);});
 it('uses exact spike times when seeking forwards and backwards',()=>{expect(spikesUntil(strong,0)).toBe(0);expect(spikesUntil(strong,1100)).toBe(834);expect(spikesUntil(strong,280)).toBe(strong.spikes.filter(([t])=>t<=280).length);expect(recentSpikes(strong,280).size).toBeGreaterThan(0);expect(recentSpikes(strong,0).size).toBe(0);});
 it('preserves recorded extrema in downsampled voltage plots',()=>{for(const {values} of strong.signals.values()){const indices=sampleEnvelope(values,500);expect(indices.length).toBeLessThanOrEqual(502);expect(indices[0]).toBe(0);expect(indices.at(-1)).toBe(values.length-1);const retained=indices.map(i=>values[i]);expect(Math.min(...retained)).toBe(Math.min(...values));expect(Math.max(...retained)).toBe(Math.max(...values));}});
});
describe('future-compatible HTTP data source',()=>{
 const fetcher=async(input:RequestInfo|URL)=>{const path=String(input).split('/').at(-1)!;return new Response(bytes(path));};
 it('loads and checksum-verifies actual static exports',async()=>{const source=new HttpTelemetrySource('/data',fetcher);const c=await source.getCatalog();const g=await source.getGraph(c);const e=await source.getExperiment(c.experiments[2],g,c.graph.sha256);expect(e.spikes.length).toBe(834);expect(e.signals.size).toBe(6);});
 it('refuses mutated assets and HTTP failures',async()=>{const corrupt=new HttpTelemetrySource('/data',async()=>new Response('modified'));await expect(corrupt.getGraph(catalog)).rejects.toThrow('checksum');const offline=new HttpTelemetrySource('/data',async()=>new Response('',{status:404}));await expect(offline.getCatalog()).rejects.toThrow('HTTP 404');});
});
