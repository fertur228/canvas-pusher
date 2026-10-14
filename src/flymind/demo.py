"""Offline demonstration: SYNTHETIC Canvas, real FlyWire simulations, no real Telegram."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import argparse
import json
import time
import resource
import platform
from .pipeline import Pipeline
from .store import SQLiteStore,LocalTelemetryStorage
from .neural import NeuralRunner
from .telegram import Delivery


class CaptureDelivery:
    ready=True
    def __init__(self):self.messages=[];self.calls=[]
    def deliver(self,text,message_id=None):
        self.calls.append({'method':'editMessageText' if message_id else 'sendMessage','message_id':message_id,'text':text})
        if message_id is None:
            self.messages.append(text);message_id=len(self.messages)
        else:self.messages[message_id-1]=text
        return Delivery('done',message_id=message_id)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    started=time.perf_counter();cpu_started=time.process_time();children_started=resource.getrusage(resource.RUSAGE_CHILDREN)
    a.output.mkdir(parents=True,exist_ok=False)
    account='00000000-0000-0000-0000-000000000001'
    store=SQLiteStore(a.output/'outbox.sqlite',account);delivery=CaptureDelivery()
    pipeline=Pipeline(store,delivery,NeuralRunner(),LocalTelemetryStorage(a.output/'private-telemetry'))
    now=datetime(2026,10,14,tzinfo=timezone.utc)
    live={'id':1,'course_id':2,'course_name':'SYNTHETIC Canvas course','name':'SYNTHETIC task — not personal data','due_at':(now+timedelta(days=5)).isoformat(),'points_possible':100,'score':None,'has_submitted':False}
    pipeline.ingest('assignment',live,now);pipeline.run_pending()
    changed={**live,'due_at':(now+timedelta(hours=2)).isoformat(),'score':50}
    pipeline.ingest('assignment',changed,now);pipeline.run_pending()
    before=len(delivery.calls);pipeline.ingest('assignment',changed,now);pipeline.run_pending()
    assert before==len(delivery.calls)
    metadata=[json.loads(row['data']) for row in store.db.execute('SELECT data FROM experiments')]
    children=resource.getrusage(resource.RUSAGE_CHILDREN)
    measurements={'batch_wall_seconds':time.perf_counter()-started,'parent_cpu_seconds':time.process_time()-cpu_started,'children_cpu_seconds':children.ru_utime+children.ru_stime-children_started.ru_utime-children_started.ru_stime,'unique_telemetry_objects':len({m['telemetry_path'] for m in metadata}),'telemetry_bytes_on_disk':sum(p.stat().st_size for p in (a.output/'private-telemetry').rglob('*.json.gz'))}
    measurements['child_process_peak_rss_mib']=children.ru_maxrss/(1024**2 if platform.system()=='Darwin' else 1024)
    measurements['platform']=platform.platform()
    report={'measurements':measurements,'synthetic_canvas_fixture':True,'real_flywire_simulations':True,'no_external_messages_sent':True,'duplicate_poll_added_deliveries':len(delivery.calls)-before,
            'messages':delivery.messages,'delivery_attempts':delivery.calls,'jobs':store.counts(),'experiments':metadata}
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(a.output/'report.json'),'jobs':report['jobs'],'primary_messages':len(delivery.messages),'duplicate_poll_added_deliveries':report['duplicate_poll_added_deliveries'],
                      'measured_responses':[{'case':m['encoding']['case'],'readout':m['readout']} for m in metadata]},ensure_ascii=False))
    store.close()


if __name__=='__main__':main()
