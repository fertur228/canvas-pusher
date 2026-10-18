import asyncio
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
import json
import pytest
from src.core.scanner import AsyncCanvasScanner
from src.flymind.events import adapt,Snapshot,EventKind
from src.flymind.presentation import render
from src.flymind import bot_setup,manual_sync,worker
from src.flymind.pipeline import Pipeline
from src.flymind.store import SQLiteStore,LocalTelemetryStorage
from tests.flymind.test_events import ACCOUNT,LIVE,NOW
from tests.flymind.test_worker import RPCClient,Scanner,settings
from tests.flymind.test_pipeline import FakeDelivery,FakeRunner


def test_new_undated_assignment_title_points_link_and_repeated_scan():
    live={**LIVE,'due_at':None,'score':99,'has_submitted':False,'html_url':'https://canvas.invalid/courses/20/assignments/10?a=1&b=2'}
    snap,events=adapt(ACCOUNT,'assignment',live,Snapshot(),NOW)
    assert [e.kind for e in events]==[EventKind.CREATED]
    assert not snap.state['has_submitted']
    text=render(events[0]);assert 'не установлен' in text and 'НОВОЕ ЗАДАНИЕ!' in text and '💯 Баллы: 100.0' in text and 'Открыть задание' in text and '&amp;' in text
    assert not adapt(ACCOUNT,'assignment',live,snap,NOW+timedelta(minutes=20))[1]
    assert not adapt(ACCOUNT,'assignment',live,Snapshot(),NOW,bootstrap=True)[1]
    assert adapt(ACCOUNT,'assignment',{**live,'name':'Changed'},snap,NOW)[1][0].kind==EventKind.UPDATED


def test_submission_state_and_assignment_link_origin():
    assert not AsyncCanvasScanner.is_submitted({'score':100,'workflow_state':'graded'})
    assert AsyncCanvasScanner.is_submitted({'workflow_state':'pending_review'})
    scanner=AsyncCanvasScanner('synthetic','https://canvas.invalid',None)
    assert scanner.safe_assignment_url('https://canvas.invalid/courses/1/assignments/2')
    assert not scanner.safe_assignment_url('https://evil.invalid/assignment')
    assert not scanner.safe_assignment_url('javascript:alert(1)')


def test_expired_canvas_token_does_not_release_academic_backlog(tmp_path,monkeypatch):
    store=SQLiteStore(tmp_path/'state',ACCOUNT);client=RPCClient(store);delivery=FakeDelivery()
    Pipeline(store,delivery,None,None).ingest('assignment',LIVE,NOW)
    class Denied(Scanner):
        http_statuses={401:1}
        async def get_active_courses(self):raise RuntimeError('private token must not leak')
    monkeypatch.setattr(worker,'TelegramDelivery',lambda *a:delivery)
    result=asyncio.run(worker.run(settings(),client_factory=lambda *a:client,scanner_factory=Denied))
    assert result['sync_status']=='failed' and not delivery.calls
    assert store.counts()['send.pending']>0


def test_rotation_never_edits_old_bot_message(tmp_path):
    store=SQLiteStore(tmp_path/'state',ACCOUNT);delivery=FakeDelivery();delivery.bot_id='101'
    pipeline=Pipeline(store,delivery,FakeRunner(),LocalTelemetryStorage(tmp_path/'blobs'))
    pipeline.ingest('assignment',LIVE,NOW);pipeline.drain_notifications();sent=len(delivery.calls)
    delivery.bot_id='102';pipeline.drain_neural();pipeline.drain_notifications('edit')
    assert len(delivery.calls)==sent and store.counts().get('edit.dead',0)>0


def test_credentials_file_is_private_and_never_overwritten(tmp_path):
    p=tmp_path/'.env.identity';bot_setup.write_private(p,{'TELEGRAM_USER_ID':'123'})
    assert p.stat().st_mode&0o777==0o600
    with pytest.raises(FileExistsError):bot_setup.write_private(p,{'TELEGRAM_USER_ID':'999'})


def test_bootstrap_challenge_and_webhook_polling_exclusion():
    class API:
        webhook=False
        def call(self,method,payload=None):
            if method=='getMe':return {'id':101}
            if method=='getWebhookInfo':return {'url':'https://existing.invalid' if self.webhook else ''}
            return [{'update_id':1,'message':{'text':'/start','chat':{'id':999,'type':'private'},'from':{'id':999}}},
                    {'update_id':2,'message':{'text':'/start challenge','chat':{'id':123,'type':'private'},'from':{'id':123}}}]
    api=API();result=bot_setup.discover(api,'challenge',announce=lambda x:None)
    assert result=={'TELEGRAM_BOT_ID':'101','TELEGRAM_CHAT_ID':'123','TELEGRAM_USER_ID':'123'}
    api.webhook=True
    with pytest.raises(ValueError,match='webhook_active'):bot_setup.discover(api,'challenge')


def test_configures_official_commands_and_secret_without_dropping_updates():
    calls=[]
    class API:
        url=''
        def call(self,method,payload=None):
            calls.append((method,payload))
            if method=='getMe':return {'id':101}
            if method=='getWebhookInfo':return {'url':self.url}
            if method=='setWebhook':self.url=payload['url']
            return True
    identity={'TELEGRAM_BOT_ID':'101','TELEGRAM_CHAT_ID':'123','TELEGRAM_USER_ID':'123'}
    result=bot_setup.configure(API(),identity,'https://db.invalid/functions/v1/telegram-webhook','a'*40)
    assert result['webhook_url_verified']
    command_call=next(p for m,p in calls if m=='setMyCommands')
    assert {c['command'] for c in command_call['commands']}=={'start','menu','deadlines','check','stats','brain','status'}
    assert next(p for m,p in calls if m=='setWebhook')['drop_pending_updates'] is False
    assert not any(m=='getUpdates' for m,p in calls)


def test_secret_publication_uses_stdin_not_commandline():
    calls=[]
    def run(args,**kwargs):calls.append((args,kwargs));return SimpleNamespace(returncode=0)
    bot_setup.publish_github('owner/repo',{'CANVAS_API_KEY':'synthetic-private'},run)
    assert calls[0][1]['input']=='synthetic-private'
    assert 'synthetic-private' not in ' '.join(calls[0][0])


def test_manual_execution_claims_once_and_prepares_not_completes():
    calls=[];claimed=False
    def rpc(name,p):
        nonlocal claimed
        calls.append(name)
        if name=='flymind_manual_start':
            if claimed:return False
            claimed=True
        return True
    store=SimpleNamespace(_rpc=rpc)
    async def runner(s):return {'status':'ok','sync_status':'verified','errors':0}
    req='11111111-1111-1111-1111-111111111111'
    first=asyncio.run(manual_sync.execute(None,store,req,'444','feature',runner))
    second=asyncio.run(manual_sync.execute(None,store,req,'445','feature',runner))
    assert first['status']=='ok' and second['status']=='duplicate_or_expired_request'
    assert calls.count('flymind_manual_prepare')==1 and 'flymind_manual_complete' not in calls


def test_finalizer_requires_actual_trusted_workflow_completion():
    with pytest.raises(ValueError,match='untrusted'):
        manual_sync.finalize_event({'action':'requested'},None,None,None,'owner/repo')
    with pytest.raises(ValueError,match='untrusted'):
        manual_sync.finalize_event({'action':'completed','workflow_run':{'status':'completed','event':'workflow_dispatch','path':'.github/workflows/check_canvas.yml','head_repository':{'full_name':'attacker/fork'}}},None,None,None,'owner/repo')
    text=manual_sync.completion_text({'summary':{'sync_status':'verified','errors':0,'event_counts':{'assignment_created':2,'deadline_changed':1,'grade_updated':3},'last_successful_check':'2026-10-14T18:30:00+00:00'}},'success')
    assert 'завершена' in text and '23:30 Asia/Almaty' in text and 'Новых заданий: 2' in text
    assert 'ошибкой' in manual_sync.completion_text({},'failure')


def test_test_chat_discovery_requires_known_owner_and_separate_group():
    class API:
        def call(self,method,payload=None):
            if method=='getMe':return {'id':101}
            if method=='getWebhookInfo':return {'url':''}
            return [
                {'update_id':1,'message':{'text':'/start proof','chat':{'id':123,'type':'private'},'from':{'id':123}}},
                {'update_id':2,'message':{'text':'/start proof','chat':{'id':-100,'type':'supergroup'},'from':{'id':999}}},
                {'update_id':3,'message':{'text':'/start proof','chat':{'id':-100,'type':'supergroup'},'from':{'id':123}}}]
    result=bot_setup.discover(API(),'proof',owner_id='123',test_chat=True,announce=lambda _:None)
    assert result['TEST_TELEGRAM_CHAT_ID']=='-100' and result['TELEGRAM_USER_ID']=='123'
    with pytest.raises(ValueError,match='owner_identity_required'):
        bot_setup.discover(API(),'proof',test_chat=True)


def test_failed_manual_workflow_queues_one_operational_report_not_academic_backlog(monkeypatch):
    req='11111111-1111-1111-1111-111111111111'
    row={'id':req,'state':'running','workflow_ref':'feature','summary':{'sync_status':'failed','errors':1}}
    class Query:
        def __init__(self,table):self.table=table
        def select(self,*a):return self
        def eq(self,*a):return self
        def execute(self):return SimpleNamespace(data=[{'last_snapshot_success':'2026-10-14T18:30:00+00:00'}] if self.table=='flymind_health' else [row])
    client=SimpleNamespace(table=Query);calls=[];drains=[]
    def rpc(name,args):
        calls.append((name,args));row['state']='failed';return True
    store=SimpleNamespace(account_id=ACCOUNT,_rpc=rpc)
    class Pipe:
        def __init__(self,*a,**kw):pass
        def drain_notifications(self,**kw):drains.append(kw)
    monkeypatch.setattr(manual_sync,'Pipeline',Pipe)
    event={'action':'completed','workflow_run':{'id':444,'status':'completed','event':'workflow_dispatch','path':'.github/workflows/check_canvas.yml','head_repository':{'full_name':'owner/repo'},'head_branch':'feature','display_title':'FlyMind sync '+req,'conclusion':'failure'}}
    manual_sync.finalize_event(event,store,client,None,'owner/repo')
    manual_sync.finalize_event(event,store,client,None,'owner/repo')
    assert len(calls)==1 and calls[0][0]=='flymind_manual_complete'
    assert len(drains)==2 and drains[0]==drains[1] and set(drains[0])=={'only_report'}
    assert 'ошибкой' in calls[0][1]['p_event']['payload']['message']
    assert '23:30 Asia/Almaty' in calls[0][1]['p_event']['payload']['message']


def test_huge_escaped_assignment_stays_within_telegram_limit():
    _,events=adapt(ACCOUNT,'assignment',{**LIVE,'name':'&'*1000,'course_name':'&'*1000,'html_url':'https://canvas.invalid/'+ '&'*700},Snapshot(),NOW)
    assert all(len(render(e))<4096 for e in events)


@pytest.mark.parametrize('state,runs,allowed', [('active',[],False),('disabled_manually',[{'status':'in_progress'}],False),('disabled_inactivity',[{'status':'completed'}],True)])
def test_rotation_requires_disabled_idle_scanner(state,runs,allowed):
    def run(args,**kwargs):return SimpleNamespace(returncode=0,stdout=state if args[1]=='api' else json.dumps(runs))
    if allowed:bot_setup.rotation_preflight('owner/repo',run)
    else:
        with pytest.raises(ValueError,match='disable_scanner'):bot_setup.rotation_preflight('owner/repo',run)
