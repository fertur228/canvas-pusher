import {useEffect,useMemo,useRef,useState} from 'react';
import type {Session,SupabaseClient} from '@supabase/supabase-js';
import {ownerAuth} from './auth';
import {dataSource} from './data';
import {SupabaseExperimentRepository} from './supabase';
import type {PrivateExperimentRow} from './supabase';
import App from './App';
import type {Loaded} from './App';
import type {ExperimentId,LoadedExperiment} from './telemetry';

type OwnerAccount={id:string;telegram_chat_id:number;enabled:boolean};
type Health={last_attempt:string|null;last_canvas_success:string|null;last_database_success:string|null;last_neural_success:string|null;last_telegram_success:string|null;status:string;error_code:string|null;queue:Record<string,number>};
export function healthState(health:Health|undefined,now=Date.now()) {
  if(!health?.last_attempt)return 'unknown';
  if(now-Date.parse(health.last_attempt)>90*60_000)return 'failed';
  if(now-Date.parse(health.last_attempt)>30*60_000)return 'delayed';
  return health.status;
}
export default function PrivateObservatory(){
  const [client]=useState(()=>{try{return ownerAuth();}catch{return null;}});
  const [session,setSession]=useState<Session|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{if(!client)return;const {data}=client.auth.onAuthStateChange((_event,s)=>setSession(s));return()=>data.subscription.unsubscribe();},[client]);
  if(!client)return <div className="loading-screen"><h1>Private Observatory</h1><p role="alert">Configure VITE_SUPABASE_URL and a public VITE_SUPABASE_PUBLISHABLE_KEY. Service keys are forbidden.</p></div>;
  if(session)return <PrivateWorkspace key={session.user.id} client={client} onSignOut={()=>{setSession(null);void client.auth.signOut({scope:'local'});}}/>;
  return <div className="loading-screen"><h1>FlyMind · owner sign-in</h1><p>Private Canvas records require an authorized owner account.</p><form className="auth-form" onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');const form=new FormData(e.currentTarget);try{const {error}=await client.auth.signInWithPassword({email:String(form.get('email')),password:String(form.get('password'))});if(error)setError('Sign-in failed. Check your account or try again later.');}catch{setError('Authentication unavailable. Try again later.');}finally{setBusy(false);}}}><label>Email<input type="email" name="email" autoComplete="username" required/></label><label>Password<input type="password" name="password" autoComplete="current-password" required/></label><button disabled={busy}>{busy?'Signing in…':'Sign in'}</button></form>{error&&<p role="alert">{error}</p>}<small>Session stays in memory. Reloading signs you out. No public registration.</small></div>;
}
function PrivateWorkspace({client,onSignOut}:{client:SupabaseClient;onSignOut:()=>void}){
  const [rows,setRows]=useState<PrivateExperimentRow[]>([]),[health,setHealth]=useState<Health>(),[errors,setErrors]=useState<{error_code:string;created_at:string}[]>([]),[loaded,setLoaded]=useState<Loaded>(),[selected,setSelected]=useState<PrivateExperimentRow>(),[trigger,setTrigger]=useState<{kind:string;payload:{name?:string;course_name?:string};observed_at:string}>(),[error,setError]=useState(''),[busy,setBusy]=useState(true),[storage,setStorage]=useState('not checked'),[revision,setRevision]=useState(0);
  const [accounts,setAccounts]=useState<OwnerAccount[]>([]),[accountId,setAccountId]=useState('');
  const cache=useRef(new Map<string,Loaded>()),requestId=useRef(0);
  const repository=useMemo(()=>new SupabaseExperimentRepository(async()=>{const {data}=await client.auth.getSession();if(!data.session)throw new Error('Session expired');return {url:import.meta.env.VITE_SUPABASE_URL,publishableKey:import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY,accessToken:data.session.access_token};}),[client]);
  useEffect(()=>{let active=true;void(async()=>{
    try {
      const {data,error}=await client.from('flymind_accounts').select('id,telegram_chat_id,enabled').order('created_at');
      if(error||!data?.length)throw new Error('No authorized accounts');
      if(active){setAccounts(data);setAccountId((data.find(a=>Number(a.telegram_chat_id)>0&&a.enabled)||data[0]).id);}
    }catch{if(active){setError('Private metadata unavailable. Check owner account mapping and session.');setBusy(false);}}
  })();return()=>{active=false;};},[client]);
  useEffect(()=>{
    if(!accountId)return;
    let active=true;setBusy(true);setError('');setRows([]);setHealth(undefined);setErrors([]);
    setLoaded(undefined);setSelected(undefined);setTrigger(undefined);setStorage('not checked');
    requestId.current++;cache.current.clear();
    void(async()=>{try{
      const [runs,h,e]=await Promise.all([
        repository.list(accountId),
        client.from('flymind_health').select('*').eq('account_id',accountId).limit(1),
        client.from('flymind_attempts').select('error_code,created_at').eq('account_id',accountId).not('error_code','is',null).order('created_at',{ascending:false}).limit(8)]);
      if(h.error||e.error)throw new Error('Private health unavailable; verify ownership and migrations');
      if(active){setRows(runs);setHealth(h.data?.[0]);setErrors(e.data??[]);}
    }catch{if(active)setError('Private metadata unavailable. Check your connection, owner mapping and session.');}
    finally{if(active)setBusy(false);}})();
    return()=>{active=false;requestId.current++;cache.current.clear();};
  },[repository,client,revision,accountId]);
  async function load(row:PrivateExperimentRow){if(row.account_id!==accountId)return;const id=++requestId.current;setBusy(true);setError('');setLoaded(undefined);setSelected(row);setTrigger(undefined);try{let result=cache.current.get(row.event_id);if(!result){const catalog=await dataSource.getCatalog(),graph=await dataSource.getGraph(catalog);const references=await Promise.all(catalog.experiments.map(e=>dataSource.getExperiment(e,graph,catalog.graph.sha256)));const experiment=await repository.load(row,graph,catalog.graph.sha256);const entries=catalog.experiments.map(e=>e.id!==experiment.id?e:{...e,spikes:experiment.spikes.length,active_neurons:experiment.activity.filter(n=>n.spike_count>0).length,gf_spikes:experiment.readout.map(r=>r.spike_times_ms.length),duration_ms:experiment.parameters.duration_ms,contrast:experiment.stimulus.parameters.contrast,radius_over_speed_ms:experiment.stimulus.parameters.radius_over_speed_ms});result={catalog:{...catalog,experiments:entries},graph,experiments:{...Object.fromEntries(references.map(e=>[e.id,e])),[experiment.id]:experiment} as Record<ExperimentId,LoadedExperiment>};if(cache.current.size>=3)cache.current.delete(cache.current.keys().next().value!);cache.current.set(row.event_id,result);}const event=await client.from('flymind_events').select('event').eq('event_id',row.event_id).eq('account_id',accountId).single();if(event.error)throw new Error('Trigger unavailable');if(id===requestId.current){setLoaded(result);setTrigger(event.data.event);setStorage('verified private download');}}catch{if(id===requestId.current){setError('Experiment unavailable: expired session, missing/retained artifact, or integrity check failed. Retry after checking System Health.');setStorage('unavailable');}}finally{if(id===requestId.current)setBusy(false);}}
  const stamp=(v:string|null|undefined)=>v?new Date(v).toLocaleString():'unavailable';
  return <><section className="private-panel"><div className="panel-heading"><div><h1>Private Observatory</h1><p>Authenticated owner data · deployment: {import.meta.env.VITE_DEPLOYMENT_LABEL||'local / not deployed'}</p></div><button onClick={onSignOut}>Sign out</button></div><label>Account <select aria-label="Account" value={accountId} onChange={e=>setAccountId(e.target.value)}>{accounts.map(a=><option key={a.id} value={a.id}>{Number(a.telegram_chat_id)<0?'Test group':'Private chat'} · {a.enabled?'enabled':'disabled'}</option>)}</select></label><h2>Overview & system health</h2><dl className="health-grid"><div><dt>State</dt><dd>{healthState(health)}</dd></div><div><dt>Scanner attempt</dt><dd>{stamp(health?.last_attempt)}</dd></div><div><dt>Canvas success</dt><dd>{stamp(health?.last_canvas_success)}</dd></div><div><dt>Database success</dt><dd>{stamp(health?.last_database_success)}</dd></div><div><dt>Neural success</dt><dd>{stamp(health?.last_neural_success)}</dd></div><div><dt>Telegram delivery</dt><dd>{stamp(health?.last_telegram_success)}</dd></div><div><dt>Storage</dt><dd>{storage}</dd></div><div><dt>Model</dt><dd>Fixed LIF · FAFB v783 · experimental</dd></div></dl><p>Queue: {health?Object.entries(health.queue).map(([k,n])=>`${k}: ${n}`).join(' · ')||'empty':'unavailable'}</p><p>Recent errors: {errors.map(e=>`${stamp(e.created_at)} ${e.error_code}`).join(' · ')||'none recorded'}</p><button onClick={()=>setRevision(x=>x+1)} disabled={busy}>Refresh history and health</button><h2>Experiments · latest 50</h2>{busy&&<p role="status">Loading private data…</p>}{error&&<p role="alert">{error}</p>}{!busy&&!rows.length&&!error&&<p>No experiments accessible. Check owner mapping or run the worker.</p>}<div className="run-list">{rows.map(row=><button key={row.event_id} disabled={busy} onClick={()=>void load(row)} aria-pressed={selected?.event_id===row.event_id}>{stamp(row.created_at)} · {row.metadata.encoding?.case||'unavailable'} · {row.metadata.readout?.classification||row.metadata.status}</button>)}</div>{trigger&&<p>Trigger: {trigger.kind} · {trigger.payload.course_name} · {trigger.payload.name} · {stamp(trigger.observed_at)}</p>}{loaded&&selected&&<p><strong>{selected.metadata.encoding.case}</strong> replays this private run. Other profiles are bundled research references, not runs from your Canvas account. All activity is model-recorded and biologically unvalidated.</p>}</section>{loaded&&selected&&<App key={selected.event_id} initialData={loaded} initialExperiment={selected.metadata.encoding.case} sourceLabel="Private run + local references"/>}</>;
}
