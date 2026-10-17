/** Private, user-JWT repository. Local TelemetrySource remains the default.
 * No service-role key, token persistence, public signed URLs or private-data bundling. */
import { assertVersion, decodeVoltage, validateExperiment } from './telemetry';
import type { Experiment, ExperimentId, Graph, LoadedExperiment, Descriptor } from './telemetry';
import { verifyBytes } from './integrity';

type EngineTrace = { readout_time_ms: number[]; readout_voltage_mv: Record<string,number[]>; time_ms: number[]; voltage_mv: Record<string,number[]> };
export type EngineExport = { schema_version: 1; manifest_sha256: string; biological_response_validated: false; activity_sha256: string; created_at_utc: string; neuron_ids: string[]; model: Experiment['model']; simulation: { parameters: Experiment['parameters']; model: Experiment['model']; stimulus: Experiment['stimulus']; stimulus_ids: string[]; spikes: {root_id:string;time_ms:number}[]; activity: Experiment['activity']; readout: Experiment['readout']; traces: EngineTrace } };
export type PrivateExperimentRow = { event_id: string; account_id: string; created_at: string; metadata: { status: string; encoding: {case: 'weak'|'strong'}; telemetry_path: string; telemetry_sha256: string; activity_sha256: string; source_code_sha256: Record<string,string>; readout: {classification:string; biological_response_validated:false} } };
export type UserAccess = { url: string; publishableKey: string; accessToken: string };

/** Lossless adapter over an existing engine export. No browser simulation. */
export function fromEngineExport(raw: EngineExport, graph: Graph, graphHash: string, row: PrivateExperimentRow): LoadedExperiment {
  if (raw.schema_version !== 1 || raw.biological_response_validated !== false || raw.manifest_sha256 !== graph.manifest_sha256 || raw.neuron_ids.length !== graph.neurons.length || raw.neuron_ids.some((id,i)=>id!==graph.neurons[i].root_id) || raw.activity_sha256!==row.metadata.activity_sha256) throw new Error('Private experiment does not match verified connectome');
  const s=raw.simulation, index=new Map(graph.neurons.map((n,i)=>[n.root_id,i]));
  const ni=(id:string)=>{const i=index.get(id);if(i===undefined)throw new Error('Unknown real neuron ID');return i;};
  const sources=[...Object.entries(s.traces.readout_voltage_mv).map(([id,values])=>({id,values,times:s.traces.readout_time_ms,phase:'before_thresholds',step:s.parameters.dt_ms})),...Object.entries(s.traces.voltage_mv).filter(([id])=>!(id in s.traces.readout_voltage_mv)).map(([id,values])=>({id,values,times:s.traces.time_ms,phase:'start',step:s.parameters.sample_ms}))];
  const binary=new ArrayBuffer(sources.reduce((n,trace)=>n+trace.values.length*8,0));const view=new DataView(binary);let offset=0;const traces:Descriptor[]=[];
  for(const trace of sources){if(trace.values.length!==trace.times.length||trace.times.some((t,i)=>Math.abs(t-Number((i*trace.step).toFixed(9)))>1e-8))throw new Error('Unsupported irregular trace timestamps');traces.push({neuron_index:ni(trace.id),length:trace.values.length,byte_offset:offset,start_ms:0,step_ms:trace.step,phase:trace.phase,signal:'recorded_simulation_voltage'});for(const value of trace.values){view.setFloat64(offset,value,true);offset+=8;}}
  const spikes=s.spikes.map(e=>[e.time_ms,ni(e.root_id)] as [number,number]).sort((a,b)=>a[0]-b[0]||a[1]-b[1]);
  const bins=Array.from({length:Math.ceil(s.parameters.duration_ms/10)},(_,i)=>[i*10,0,0,0,0] as [number,number,number,number,number]);
  for(const [t,i] of spikes){const b=bins[Math.floor(t/10)];if(!b)throw new Error('Spike outside simulation');b[1]++;const n=graph.neurons[i];const type=n.cell_type||n.hemibrain_type;const col=type==='LC4'?2:type==='LPLC2'?3:n.role==='readout'?4:0;if(col)b[col]++;}
  const e:Experiment={schema:'flymind.observatory/v1',id:row.metadata.encoding.case as ExperimentId,biological_response_validated:false,graph_sha256:graphHash,source:{path:'private-storage/'+row.metadata.telemetry_path,sha256:row.metadata.telemetry_sha256,activity_sha256:raw.activity_sha256,created_at_utc:raw.created_at_utc,source_code_sha256:row.metadata.source_code_sha256},parameters:s.parameters,model:raw.model,stimulus:s.stimulus,stimulus_indices:s.stimulus_ids.map(ni),spikes,spike_columns:['time_ms','neuron_index'],activity:s.activity,readout:s.readout,population:{bin_ms:10,bins,signal:'exact_spike_count_aggregation'},voltage:{path:'in-memory',encoding:'float64-le',sha256:row.metadata.telemetry_sha256,traces},limitations:['Private Canvas event association; event-to-drive mapping and urgency thresholds are engineering conventions, not biological validation','Generic LIF; uncalibrated sensory drive; no VNC or behavioral validation']} as Experiment;
  assertVersion(e);validateExperiment(e,graph,graphHash);return decodeVoltage(e,binary,graph);
}

export class SupabaseExperimentRepository {
  constructor(private access:()=>Promise<UserAccess>,private fetcher:typeof fetch=(...args)=>fetch(...args)){}
  private async credentials(){const a=await this.access();if(!a.accessToken||!a.publishableKey||a.publishableKey.startsWith('sb_secret_')||a.accessToken.startsWith('sb_secret_'))throw new Error('Authenticated user session required');for(const token of [a.accessToken,a.publishableKey]){try{const claims=JSON.parse(atob((token.split('.')[1]||'').replace(/-/g,'+').replace(/_/g,'/')));if(claims.role==='service_role')throw new Error('Service role forbidden in browser');}catch(e){if(e instanceof Error&&e.message.includes('Service role'))throw e;}}if(!/^https:\/\//.test(a.url))throw new Error('HTTPS Supabase origin required');return a;}
  async list(accountId?:string):Promise<PrivateExperimentRow[]>{const a=await this.credentials();const r=await this.fetcher(`${a.url.replace(/\/$/,'')}/rest/v1/flymind_experiments?select=event_id,account_id,created_at,metadata&order=created_at.desc&limit=50${accountId?'&account_id=eq.'+encodeURIComponent(accountId):''}`,{headers:{apikey:a.publishableKey,Authorization:`Bearer ${a.accessToken}`},cache:'no-store'});if(!r.ok)throw new Error(`Private metadata unavailable: HTTP ${r.status}`);const rows=await r.json();if(!Array.isArray(rows)||accountId&&rows.some(row=>row.account_id!==accountId))throw new Error('Invalid private metadata');return rows;}
  async load(row:PrivateExperimentRow,graph:Graph,graphHash:string):Promise<LoadedExperiment>{
    const a=await this.credentials(),path=row.metadata.telemetry_path;
    if(row.metadata.status!=='complete'||!path||!path.startsWith(`${row.account_id}/`)||!/^[-a-f0-9/]+\.json\.gz$/.test(path))throw new Error('Private telemetry unavailable or invalid path');
    const response=await this.fetcher(`${a.url.replace(/\/$/,'')}/storage/v1/object/authenticated/flymind-private/${path}`,{headers:{apikey:a.publishableKey,Authorization:`Bearer ${a.accessToken}`},cache:'no-store'});
    if(!response.ok)throw new Error(`Private telemetry unavailable: HTTP ${response.status}`);
    const bytes=await boundedBytes(response.body,4*1024*1024);await verifyBytes(bytes,row.metadata.telemetry_sha256);
    const text=new TextDecoder().decode(await boundedBytes(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip')),32*1024*1024));
    return fromEngineExport(JSON.parse(text),graph,graphHash,row);
  }
}

export async function boundedBytes(stream:ReadableStream<Uint8Array>|null,limit:number):Promise<ArrayBuffer>{
  if(!stream)throw new Error('Missing telemetry body');
  const reader=stream.getReader(),chunks:Uint8Array[]=[];let size=0;
  try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>limit){await reader.cancel();throw new Error('Telemetry size limit exceeded');}chunks.push(value);}}finally{reader.releaseLock();}
  const result=new Uint8Array(size);let offset=0;for(const chunk of chunks){result.set(chunk,offset);offset+=chunk.length;}return result.buffer;
}
