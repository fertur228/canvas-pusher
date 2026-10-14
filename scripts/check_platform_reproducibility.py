"""Diagnose native-platform floating-point drift without changing scientific parameters."""
import argparse
from datetime import datetime,timedelta,timezone
import gzip
import json
from pathlib import Path
import platform
from src.flymind.neural import NeuralRunner
from src.flymind.events import Snapshot,adapt
from src.flymind.sensory import encode


def compare(expected,actual,path='',report=None):
    report=report if report is not None else {'different_floats':0,'max_absolute_difference':0.0,'max_difference_path':None,'discrete_mismatches':[]}
    if isinstance(expected,dict) and isinstance(actual,dict):
        if set(expected)!=set(actual):report['discrete_mismatches'].append(path+'.keys');return report
        for key in expected:compare(expected[key],actual[key],path+'.'+key,report)
    elif isinstance(expected,list) and isinstance(actual,list):
        if len(expected)!=len(actual):report['discrete_mismatches'].append(path+'.length');return report
        for i,(a,b) in enumerate(zip(expected,actual)):compare(a,b,f'{path}[{i}]',report)
    elif isinstance(expected,float) and isinstance(actual,(int,float)):
        if expected!=actual:
            delta=abs(expected-actual);report['different_floats']+=1
            if delta>report['max_absolute_difference']:report['max_absolute_difference']=delta;report['max_difference_path']=path
    elif expected!=actual:report['discrete_mismatches'].append(path)
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    now=datetime(2026,10,14,tzinfo=timezone.utc);rows=[]
    for case,hours in [('weak',120),('strong',2)]:
        _,events=adapt('00000000-0000-0000-0000-000000000001','assignment',{'id':1,'course_id':2,'due_at':(now+timedelta(hours=hours)).isoformat(),'has_submitted':False},Snapshot(),now)
        encoding=encode(events[0]);one,blob=NeuralRunner().run(encoding);two,_=NeuralRunner().run(encoding)
        with gzip.open(f'data/neural/runs/escape-resumed-20261014/{case}-1.json.gz','rt') as f:expected=json.load(f)
        actual=json.loads(gzip.decompress(blob));comparison=compare(expected['simulation'],actual['simulation'])
        rows.append({'case':case,'native_repeated_hash_equal':one['activity_sha256']==two['activity_sha256'],
                     'original_hash':expected['activity_sha256'],'native_hash':one['activity_sha256'],
                     'spikes_exactly_equal':expected['simulation']['spikes']==actual['simulation']['spikes'],**comparison})
    report={'platform':platform.platform(),'machine':platform.machine(),'runs':rows,'parameters_changed':False}
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
