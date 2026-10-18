"""Real LOCAL Supabase Auth/PostgREST/Storage; synthetic Canvas and captured Telegram.
Only the dedicated loopback port 55321 is accepted. Never prints credentials/data.
"""
import argparse
from datetime import datetime,timedelta,timezone
import gzip
import hashlib
import json
import logging
from pathlib import Path
import secrets
import uuid
from urllib.parse import urlparse

import httpx
from supabase import create_client
from src.flymind.neural import NeuralRunner
from src.flymind.pipeline import Pipeline
from src.flymind.store import SupabaseStore,SupabaseTelemetryStorage
from src.flymind.telegram import Delivery


def run(status):
    config=json.loads(status.read_text());url=config['API_URL'];parsed=urlparse(url)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or parsed.port!=55321:
        raise ValueError('Only dedicated local Supabase port 55321 is permitted')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    client=create_client(url,config['SERVICE_ROLE_KEY'])
    users=[]
    for _ in range(2):
        email=f'flymind-{uuid.uuid4()}@example.invalid';password=secrets.token_urlsafe(30)
        user=client.auth.admin.create_user({'email':email,'password':password,'email_confirm':True}).user
        with httpx.Client(timeout=10) as http:
            response=http.post(url+'/auth/v1/token?grant_type=password',headers={'apikey':config['ANON_KEY']},json={'email':email,'password':password})
            response.raise_for_status();token=response.json()['access_token']
        users.append((user.id,token))
    account=str(uuid.uuid4());chat=180000000000+secrets.randbelow(10000000)
    client.table('flymind_accounts').insert({'id':account,'telegram_chat_id':chat,'canvas_origin':'https://canvas.invalid','owner_id':users[0][0],'enabled':True}).execute()
    store=SupabaseStore(client,account,chat,'https://canvas.invalid')
    assert not store.runtime()['initialized'];store.runtime(initialize=True);store.heartbeat('attempt')
    class Capture:
        ready=True
        def __init__(self):self.calls=[]
        def deliver(self,text,message_id=None):
            self.calls.append(message_id)
            return Delivery('done',message_id=message_id or len(self.calls))
    delivery=Capture();pipeline=Pipeline(store,delivery,NeuralRunner(),SupabaseTelemetryStorage(client))
    now=datetime.now(timezone.utc)
    event={'id':10,'course_id':20,'course_name':'SYNTHETIC LOCAL TEST','name':'SYNTHETIC task','due_at':(now+timedelta(days=5)).isoformat(),'points_possible':100,'score':None,'has_submitted':False}
    assert pipeline.ingest('assignment',event,now)==1;pipeline.run_pending()
    event['due_at']=(now+timedelta(hours=2)).isoformat();assert pipeline.ingest('assignment',event,now)==2;pipeline.run_pending()
    calls=len(delivery.calls);assert pipeline.ingest('assignment',event,now)==0;pipeline.run_pending();assert len(delivery.calls)==calls
    rows=client.table('flymind_experiments').select('*').eq('account_id',account).execute().data
    assert len(rows)==3 and all(r['metadata']['status']=='complete' for r in rows)
    strong=[r for r in rows if r['metadata']['encoding']['case']=='strong'];assert len({r['metadata']['telemetry_path'] for r in strong})==1
    with httpx.Client(timeout=15) as http:
        def headers(token):return {'apikey':config['ANON_KEY'],'Authorization':'Bearer '+token}
        owner,other=headers(users[0][1]),headers(users[1][1]);anonymous={'apikey':config['ANON_KEY']}
        r=http.get(url+'/rest/v1/flymind_experiments',headers=owner);assert r.status_code==200 and len(r.json())==3
        r=http.get(url+'/rest/v1/flymind_experiments',headers=other);assert r.status_code==200 and r.json()==[]
        r=http.get(url+'/rest/v1/flymind_events',headers=anonymous);assert r.status_code in (401,403)
        r=http.post(url+'/rest/v1/rpc/flymind_claim',headers=owner,json={'p_account':account,'p_stage':'send'});assert r.status_code in (401,403,404)
        blobrow=strong[0];path=blobrow['metadata']['telemetry_path'];endpoint=url+'/storage/v1/object/authenticated/flymind-private/'+path
        r=http.get(endpoint,headers=owner);assert r.status_code==200
        assert hashlib.sha256(r.content).hexdigest()==blobrow['metadata']['telemetry_sha256']
        assert len(json.loads(gzip.decompress(r.content))['neuron_ids'])==1500
        assert http.get(endpoint,headers=other).status_code!=200
        assert http.get(endpoint,headers=anonymous).status_code!=200
        assert http.get(url+'/storage/v1/object/public/flymind-private/'+path).status_code!=200
        # A retained old association must not delete a shared artifact used by a newer run.
        client.table('flymind_experiments').update({'created_at':(now-timedelta(days=40)).isoformat()}).eq('event_id',strong[0]['event_id']).execute()
        expired=store._rpc('flymind_retention',{'p_days':30,'p_apply':True});assert len(expired)==1
        assert path not in store._rpc('flymind_orphans',{})
        assert http.get(endpoint,headers=owner).status_code==200
    store.heartbeat('canvas');store.heartbeat('finish','healthy')
    return {'scope':'real isolated LOCAL Supabase APIs; not hosted production','auth_users':2,'rls_owner_read':True,'rls_other_owner_denied':True,'anonymous_denied':True,'worker_rpc_denied_to_browser':True,'private_storage_hash_verified':True,'public_and_guessed_storage_denied':True,'shared_artifact_retention_safe':True,'actual_neural_runs':['weak','strong'],'events':3,'captured_primary':sum(x is None for x in delivery.calls),'captured_edits':sum(x is not None for x in delivery.calls),'duplicate_deliveries':0,'real_telegram_deliveries':0,'real_canvas_read':False,'jobs':store.counts()}


def main():
    p=argparse.ArgumentParser();p.add_argument('--status',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:report=run(a.status)
    except Exception as e:
        # Exception messages may contain URLs/tokens/academic payloads. Never display them.
        print(json.dumps({'status':'failed','exception_type':type(e).__name__}));raise SystemExit(1) from None
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
