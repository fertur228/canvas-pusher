"""Explicit isolated real hosted Auth/RLS/Storage and headless private replay.

Never logs credentials or owner data; removes only its journaled temporary rows.
No personal Chrome profile, Telegram, Canvas mutations or production activation.
"""
import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import uuid
from datetime import datetime, timezone

import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
URL='https://irjasmzytjeohwfpdnrl.supabase.co'
JOURNAL=ROOT/'secret-flymind-release/isolated-auth-verification.json'


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isolated-hosted-test',action='store_true')
    args=parser.parse_args()
    if not args.isolated_hosted_test:raise ValueError('explicit_authorization_required')
    cfg=dotenv_values(ROOT/'.env.flymind.hosted');assert cfg['SUPABASE_URL']==URL
    service={'apikey':cfg['SUPABASE_SERVICE_KEY'],'Authorization':'Bearer '+cfg['SUPABASE_SERVICE_KEY']}
    public={'apikey':cfg['SUPABASE_PUBLISHABLE_KEY']}
    http=httpx.Client(timeout=40,follow_redirects=False)
    def request(method,path,headers=service,**kwargs):
        r=http.request(method,URL+path,headers=headers,**kwargs)
        if not r.is_success:raise RuntimeError(f'http_{r.status_code}')
        return r
    def save(state):
        JOURNAL.parent.mkdir(exist_ok=True);JOURNAL.write_text(json.dumps(state));JOURNAL.chmod(0o600)
    if JOURNAL.exists() and not json.loads(JOURNAL.read_text()).get('cleanup_verified'):
        raise ValueError('prior_isolated_test_requires_cleanup_review')
    account=str(uuid.uuid4());event=hashlib.sha256(('isolated-auth:'+account).encode()).hexdigest()
    state={'kind':'flymind-isolated-auth-v1','account':account,'event':event,'users':[],'storage_path':None,'cleanup_verified':False}
    save(state)
    report={'scope':'real hosted isolated Auth users; synthetic academic records; authentic recorded neural artifact','owner_browser_verified':False,'telegram_messages':0}
    before={table:len(request('GET','/rest/v1/'+table,params={'select':'id' if table=='flymind_accounts' else 'event_id'}).json()) for table in ('flymind_accounts','flymind_events','flymind_experiments')}
    existing=request('GET','/rest/v1/flymind_experiments',params={'select':'metadata','limit':'100'}).json()
    owner_artifact=next((r['metadata'].get('telemetry_path') for r in existing if r['metadata'].get('telemetry_path')),None)
    passwords=[];identities=[]
    try:
        for _ in range(2):
            email=f'flymind-verification-{uuid.uuid4().hex}@example.invalid';password=secrets.token_urlsafe(36)
            user=request('POST','/auth/v1/admin/users',json={'email':email,'password':password,'email_confirm':True}).json()
            state['users'].append(user['id']);save(state)
            auth=request('POST','/auth/v1/token?grant_type=password',headers=public,json={'email':email,'password':password}).json()
            token=auth['access_token'];claims=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'==='))
            assert claims['role']=='authenticated' and claims['sub']==user['id']
            identities.append(public|{'Authorization':'Bearer '+token});passwords.append((email,password))
        request('POST','/rest/v1/flymind_accounts',json={'id':account,'owner_id':state['users'][0],'telegram_chat_id':-(2**50+secrets.randbelow(2**40)),'canvas_origin':'https://synthetic-auth-test.invalid','enabled':False})
        blob=(ROOT/'data/neural/runs/escape-resumed-20261014/strong-1.json.gz').read_bytes();raw=json.loads(gzip.decompress(blob));digest=hashlib.sha256(blob).hexdigest()
        assert len(raw['neuron_ids'])==1500 and raw['biological_response_validated'] is False
        path=f'{account}/{event}/{digest}.json.gz';state['storage_path']=path;save(state)
        request('POST','/storage/v1/object/flymind-private/'+path,headers=service|{'Content-Type':'application/gzip'},content=blob)
        now=datetime.now(timezone.utc).isoformat()
        request('POST','/rest/v1/flymind_events',json={'event_id':event,'account_id':account,'priority':0,'observed_at':now,'event':{'kind':'assignment_created','observed_at':now,'payload':{'name':'SYNTHETIC AUTH VERIFICATION — not a university assignment','course_name':'ISOLATED TEST ONLY'}}})
        metadata={'status':'complete','encoding':{'case':'strong'},'telemetry_path':path,'telemetry_sha256':digest,'activity_sha256':raw['activity_sha256'],'source_code_sha256':{},'readout':{'classification':'elevated','biological_response_validated':False}}
        request('POST','/rest/v1/flymind_experiments',json={'event_id':event,'account_id':account,'metadata':metadata})
        request('POST','/rest/v1/flymind_health',json={'account_id':account,'status':'healthy','last_attempt':now,'queue':{}})
        owner,other=identities
        accounts=request('GET','/rest/v1/flymind_accounts',headers=owner,params={'select':'id,telegram_chat_id,enabled','order':'id.asc'}).json();assert [a['id'] for a in accounts]==[account]
        for table in ('flymind_events','flymind_experiments','flymind_health'):
            rows=request('GET','/rest/v1/'+table,headers=owner,params={'select':'account_id'}).json();assert len(rows)==1 and rows[0]['account_id']==account
            assert request('GET','/rest/v1/'+table,headers=other).json()==[]
            assert http.get(URL+'/rest/v1/'+table,headers=public).status_code in (401,403)
        # The temporary identity must never inherit the owner's legacy academic records.
        for table in ('canvas_state','course_grades'):
            assert request('GET','/rest/v1/'+table,headers=owner).json()==[]
        denied=http.post(URL+'/rest/v1/rpc/flymind_claim',headers=owner,json={'p_account':account,'p_stage':'send'});assert denied.status_code in (401,403,404)
        endpoint='/storage/v1/object/authenticated/flymind-private/'+path
        downloaded=request('GET',endpoint,headers=owner).content;assert hashlib.sha256(downloaded).hexdigest()==digest
        assert http.get(URL+endpoint,headers=other).status_code!=200 and http.get(URL+endpoint,headers=public).status_code!=200
        assert http.get(URL+'/storage/v1/object/public/flymind-private/'+path).status_code!=200
        if owner_artifact:
            assert http.get(URL+'/storage/v1/object/authenticated/flymind-private/'+owner_artifact,headers=owner).status_code!=200
        report.update(real_password_auth_users=2,owner_scope_verified=True,owner_private_records_hidden=True,unrelated_and_anonymous_denied=True,worker_rpc_denied=True,private_sha256_verified=True)
        output=ROOT/'secret-flymind-release/isolated-auth-browser-report.json'
        # Explicit allowlist: server credentials never enter the browser process.
        env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR','LANG','PLAYWRIGHT_CHROME_PATH')}
        env.update(FLYMIND_HOSTED_TEST='isolated-auth',FLYMIND_PREVIEW_URL='https://flymind-preview.flymind-observatory.pages.dev/',FLYMIND_TEST_EMAIL=passwords[0][0],FLYMIND_TEST_PASSWORD=passwords[0][1],FLYMIND_TEST_ACCOUNT=account,FLYMIND_EXPECTED_HASH=digest,FLYMIND_EXPECTED_SPIKES=str(len(raw['simulation']['spikes'])),FLYMIND_BROWSER_REPORT=str(output))
        subprocess.run(['node','scripts/verify-hosted-private.mjs'],cwd=ROOT/'dashboard',env=env,check=True)
        report['browser']=json.loads(output.read_text())
    finally:
        # Exact journaled namespace only. Never delete or alter pre-existing owner/test data.
        if state['storage_path']:
            request('DELETE','/storage/v1/object/flymind-private',json={'prefixes':[state['storage_path']]})
        for table in ('flymind_experiments','flymind_events','flymind_health'):
            request('DELETE','/rest/v1/'+table,params={'account_id':'eq.'+account})
        request('DELETE','/rest/v1/flymind_accounts',params={'id':'eq.'+account})
        for user in state['users']:
            request('DELETE','/auth/v1/admin/users/'+user)
            assert http.get(URL+'/auth/v1/admin/users/'+user,headers=service).status_code==404
        if state['storage_path']:
            assert http.get(URL+'/storage/v1/object/authenticated/flymind-private/'+state['storage_path'],headers=service).status_code!=200
        assert request('GET','/rest/v1/flymind_health',params={'account_id':'eq.'+account}).json()==[]
        after={table:len(request('GET','/rest/v1/'+table,params={'select':'id' if table=='flymind_accounts' else 'event_id'}).json()) for table in before}
        assert before==after
        state['cleanup_verified']=True;save(state);report['cleanup_verified']=True
        (ROOT/'docs/hosted-auth-headless-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':
    try:run()
    except Exception as error:
        print(json.dumps({'status':'failed','error_type':type(error).__name__,'private_details_omitted':True}));raise SystemExit(1) from None
