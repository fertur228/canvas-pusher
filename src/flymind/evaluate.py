"""Offline synthetic academic scenarios and explicitly NON-BIOLOGICAL topology controls.

Original CSVs, synaptic/model parameters and recorded experiments are never changed.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import timedelta
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time

from src.neural.loader import Connectome, load_connectome, sha256
from src.neural.escape import case_configuration
from .events import Snapshot, adapt
from .sensory import encode, readout

ROOT = Path(__file__).resolve().parents[2]


def shuffled_control(graph, seed=783):
    """Directed double-edge swaps within equal count/neuropil/NT strata.

    Preserves each neuron's incoming/outgoing row counts AND contact sums, and
    each row's source/weight/annotation; rejects duplicates and newly made self edges.
    This null model does NOT preserve actual anatomy, partner identity or pathways.
    """
    rng=random.Random(seed)
    edges=list(graph.synapses)
    groups=defaultdict(list)
    key=lambda e:(e.pre_root_id,e.post_root_id,e.neuropil,e.nt_type)
    occupied={key(e) for e in edges}
    for i,e in enumerate(edges):groups[(e.syn_count,e.neuropil,e.nt_type)].append(i)
    swaps=0
    for indices in groups.values():
        if len(indices)<2:continue
        for _ in range(10*len(indices)):
            i,j=rng.sample(indices,2);a,b=edges[i],edges[j]
            if a.pre_root_id==b.pre_root_id or a.post_root_id==b.post_root_id:continue
            x,y=replace(a,post_root_id=b.post_root_id),replace(b,post_root_id=a.post_root_id)
            if x.pre_root_id==x.post_root_id or y.pre_root_id==y.post_root_id or key(x) in occupied or key(y) in occupied:continue
            occupied.remove(key(a));occupied.remove(key(b));occupied.update((key(x),key(y)));edges[i],edges[j]=x,y;swaps+=1
    manifest={**graph.manifest,'kind':'synthetic_shuffled_control','control_seed':seed,'biological_topology':False}
    control=Connectome(graph.neurons,tuple(edges),manifest).validate()
    for field in ('pre_root_id','post_root_id'):
        for weighted in (False,True):
            def counts(items):
                c=Counter()
                for e in items:c[getattr(e,field)]+=e.syn_count if weighted else 1
                return c
            assert counts(graph.synapses)==counts(control.synapses)
    return control,{'seed':seed,'accepted_swaps':swaps,'changed_rows':sum(a!=b for a,b in zip(graph.synapses,edges)),
                    'preserves':'Per-neuron directed row degree and contact strength; edge count/weight/neuropil/NT strata',
                    'not_preserved':'Actual biological partner identity, morphology, pathways; this is a synthetic null model'}


def run_one(case,control,seed):
    start=time.perf_counter();cpu=time.process_time()
    graph=load_connectome(ROOT/'data/neural/flywire_v783');loaded=time.perf_counter()
    info=None
    if control=='shuffled':graph,info=shuffled_control(graph,seed)
    params,looming,model,policy=case_configuration(case)
    if control=='zero':params=replace(params,mv_per_synapse=0)
    from src.neural.experiment import MemoryMeter
    from src.neural.engine import simulate
    imported=time.perf_counter();plan=looming.generate(graph,params.duration_ms)
    sim_start=time.perf_counter();cpu_start=time.process_time()
    with MemoryMeter() as memory:
        result=simulate(graph,params,drive_plan=plan,synaptic_model=model,nt_policy=policy)
    sim_end=time.perf_counter();simulation_cpu=time.process_time()-cpu_start
    summary={'readout':list(result.readout),'active_neurons':sum(x['spike_count']>0 for x in result.activity),'spikes':len(result.spikes)}
    raw=json.dumps(result.as_dict(),sort_keys=True,separators=(',',':')).encode()
    return {'case':case,'control':control,'shuffle':info,'biological_response_validated':False,
            'activity_sha256':result.activity_sha256,'readout':readout(summary),
            'measurements':{'dataset_load_seconds':loaded-start,'import_and_control_seconds':imported-loaded,
                            'simulation_wall_seconds':sim_end-sim_start,'simulation_cpu_seconds':simulation_cpu,
                            'total_cpu_seconds':time.process_time()-cpu,'total_wall_seconds':time.perf_counter()-start,
                            'compressed_result_bytes':len(gzip.compress(raw,mtime=0)),**memory.measurements()},
            'platform':platform.platform(),'machine':platform.machine()}


def scenarios(runs):
    from datetime import datetime,timezone
    now=datetime(2026,10,14,tzinfo=timezone.utc)
    rows=[]
    for hours in (None,120,49,48,25,24,12,3,1,0,-1):
        for submitted in (False,True):
            live={'id':len(rows)+1,'course_id':1,'name':'SYNTHETIC EVALUATION','due_at':(now+timedelta(hours=hours)).isoformat() if hours is not None else None,'has_submitted':submitted,'points_possible':100,'score':None}
            event=adapt('00000000-0000-0000-0000-000000000001','assignment',live,Snapshot(),now)[1][0]
            profile=encode(event)['case'];response=next(r for r in runs if r['case']==profile and r['control']=='real')['readout']
            expected=hours is not None and hours<=3 and not submitted
            rows.append({'synthetic_scenario':len(rows)+1,'hours_remaining':hours,'submitted':submitted,'profile':profile,
                         'engineering_critical_oracle':expected,'deterministic_critical':event.priority==2,
                         'neural_elevated':response['classification']=='elevated','neural_classification':response['classification']})
    return {'synthetic':True,'oracle':'Unsubmitted deadline <=3h, including overdue; engineered operational rule, not human-labelled ground truth',
            'scenarios':rows,'false_elevated_vs_rule':sum(r['neural_elevated'] and not r['engineering_critical_oracle'] for r in rows),
            'missed_critical_vs_rule':sum(not r['neural_elevated'] and r['engineering_critical_oracle'] for r in rows),
            'classification_differences':sum(r['neural_elevated']!=r['deterministic_critical'] for r in rows),
            'conclusion':'No predictive advantage established: neural response is downstream of a two-profile engineered encoder. Preserve deterministic operational urgency; neural readout is experimental enrichment.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);p.add_argument('--case',choices=['baseline','weak','strong','weak_fast','strong_slow']);p.add_argument('--control',choices=['real','zero','shuffled'],default='real');p.add_argument('--seed',type=int,default=783);a=p.parse_args()
    if a.case:print(json.dumps(run_one(a.case,a.control,a.seed)));return
    if not a.output or a.output.exists():raise SystemExit('Provide a new --output JSON path')
    cases=[(c,k,seed) for c in ('weak','strong') for k in ('real','zero','shuffled') for seed in ((783,784,785) if k=='shuffled' else (783,783))]+[(c,'real',783) for c in ('baseline','weak_fast','strong_slow')]
    env={**os.environ,**{k:'1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS')}}
    runs=[];begin=time.perf_counter()
    for case,control,seed in cases:
        start=time.perf_counter();r=subprocess.run([sys.executable,'-m','src.flymind.evaluate','--case',case,'--control',control,'--seed',str(seed)],capture_output=True,text=True,check=True,timeout=90,env=env)
        row=json.loads(r.stdout);row['process_wall_seconds']=time.perf_counter()-start;runs.append(row)
        print(f'{case}/{control}: {row["readout"]["gf_spikes"]}',file=sys.stderr,flush=True)
    repeats={}
    for case in ('weak','strong'):
        for control in ('real','zero'):
            selected=[r for r in runs if r['case']==case and r['control']==control]
            repeats[f'{case}/{control}']=len({r['activity_sha256'] for r in selected})==1
    report={'schema':'flymind.evaluation/v1','biological_response_validated':False,'runs':runs,'repeatability':repeats,
            'source_manifest_sha256':sha256(ROOT/'data/neural/flywire_v783/manifest.json'),'evaluation':scenarios(runs),'batch_wall_seconds':time.perf_counter()-begin,
            'limits':['Synthetic scenarios, no measured user benefit or human urgency labels','Shuffled controls are not biological connectivity','Three seeds are descriptive controls, not a powered statistical study','Peak RSS is per fresh process; startup depends on environment']}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
    if not all(repeats.values()):raise SystemExit('Repeatability failed')

if __name__=='__main__':main()
