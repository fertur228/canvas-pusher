import asyncio
from types import SimpleNamespace
import pytest
from src.flymind import worker
from src.flymind.events import CanvasEvent,Snapshot
from src.flymind.store import SQLiteStore
from tests.flymind.test_pipeline import FakeDelivery,FakeRunner
from tests.flymind.test_events import ACCOUNT,LIVE,NOW


class RPCClient:
    def __init__(self,store):self.store=store;self.grades=[]
    def rpc(self,name,p):
        s=self.store
        if name=='flymind_runtime':data={'initialized':True}
        elif name=='flymind_heartbeat':data=True
        elif name=='flymind_sync_verified':data=NOW.isoformat()
        elif name=='flymind_check_account':data=p['p_chat_id']==123
        elif name=='flymind_snapshot':data=s.load(p['p_kind'],p['p_key']).model_dump()
        elif name=='flymind_commit':data=s.commit(p['p_kind'],p['p_key'],p['p_expected'],Snapshot.model_validate(p['p_snapshot']),[CanvasEvent.model_validate(x['event']) for x in p['p_events']])
        elif name=='flymind_claim':data=s.claim(p['p_stage'])
        elif name=='flymind_finish':
            row=s.db.execute('SELECT event_id,stage,attempts FROM jobs WHERE id=?',(p['p_id'],)).fetchone()
            event=s.db.execute('SELECT data FROM events WHERE id=?',(row['event_id'],)).fetchone()
            import json
            job={'id':p['p_id'],'token':p['p_token'],'stage':row['stage'],'attempts':row['attempts'],'event':json.loads(event['data'])}
            data=s.finish(job,p['p_outcome'],p['p_result'],p['p_delay'])
        elif name=='flymind_counts':data=s.counts()
        else:raise AssertionError(name)
        return SimpleNamespace(execute=lambda:SimpleNamespace(data=data))
    def table(self,name):
        assert name=='course_grades'
        def upsert(rows):self.grades.extend(rows);return SimpleNamespace(execute=lambda:None)
        return SimpleNamespace(upsert=upsert)
    @property
    def storage(self):
        class Bucket:
            blobs={}
            def upload(self,path,blob,opts):self.blobs[path]=blob
        return SimpleNamespace(from_=lambda name:Bucket())


class Scanner:
    def __init__(self,*args):pass
    async def get_active_courses(self):return [{'id':20,'name':'SYNTHETIC','enrollments':[]}]
    async def scan_all(self,courses):return [LIVE],[],[]


def settings(**changes):
    return worker.Settings(enabled=True,account_id=ACCOUNT,chat_id='123',supabase_url='https://supabase.invalid',supabase_key='SYNTHETIC_SERVICE_SECRET',canvas_url='https://canvas.invalid',canvas_token='SYNTHETIC_CANVAS_SECRET',telegram_token='SYNTHETIC_BOT_SECRET',delivery_mode='test',test_chat_id='123',mode='enrich',**changes)


def test_disabled_worker_makes_no_calls():
    assert asyncio.run(worker.run(worker.Settings(),client_factory=lambda *a:pytest.fail('No disabled calls'))) == {'status':'disabled'}


def test_flagged_worker_normal_execution_and_duplicate_poll(tmp_path,monkeypatch):
    store=SQLiteStore(tmp_path/'state.sqlite',ACCOUNT)
    client=RPCClient(store);delivery=FakeDelivery()
    monkeypatch.setattr(worker,'TelegramDelivery',lambda *a:delivery)
    monkeypatch.setattr(worker,'NeuralRunner',FakeRunner)
    first=asyncio.run(worker.run(settings(),client_factory=lambda *a:client,scanner_factory=Scanner))
    count=len(delivery.calls)
    second=asyncio.run(worker.run(settings(),client_factory=lambda *a:client,scanner_factory=Scanner))
    assert first['status']=='ok' and second['status']=='ok'
    assert len(delivery.calls)==count and client.grades
    store.close()


def test_scan_failure_still_drains_prior_notifications_and_logs_no_secrets(tmp_path,monkeypatch,caplog):
    from src.flymind.pipeline import Pipeline
    from src.flymind.store import LocalTelemetryStorage
    store=SQLiteStore(tmp_path/'state.sqlite',ACCOUNT)
    client=RPCClient(store);delivery=FakeDelivery()
    p=Pipeline(store,delivery,FakeRunner(),LocalTelemetryStorage(tmp_path/'private'))
    p.ingest('assignment',LIVE,NOW)
    class Broken(Scanner):
        async def get_active_courses(self):raise RuntimeError('SYNTHETIC_CANVAS_SECRET')
    monkeypatch.setattr(worker,'TelegramDelivery',lambda *a:delivery)
    monkeypatch.setattr(worker,'NeuralRunner',FakeRunner)
    result=asyncio.run(worker.run(settings(),client_factory=lambda *a:client,scanner_factory=Broken))
    assert result['status']=='needs_attention' and result['errors']==1 and delivery.calls
    assert 'SYNTHETIC_CANVAS_SECRET' not in caplog.text
    store.close()


def test_missing_canvas_token_recovers_outbox_without_scanning(tmp_path,monkeypatch):
    from dataclasses import replace
    store=SQLiteStore(tmp_path/'state.sqlite',ACCOUNT)
    client=RPCClient(store);delivery=FakeDelivery()
    monkeypatch.setattr(worker,'TelegramDelivery',lambda *a:delivery)
    monkeypatch.setattr(worker,'NeuralRunner',FakeRunner)
    # Initial missing-credential run must not invoke scanner or discard state.
    result=asyncio.run(worker.run(replace(settings(),canvas_token=''),client_factory=lambda *a:client,scanner_factory=lambda *a:pytest.fail('No scan')))
    assert result['status']=='missing_canvas_credentials'
    store.close()


def test_bootstrap_is_silent_even_with_pending_jobs(tmp_path,monkeypatch):
    from src.flymind.pipeline import Pipeline
    from src.flymind.store import LocalTelemetryStorage
    store=SQLiteStore(tmp_path/'state.sqlite',ACCOUNT)
    client=RPCClient(store);delivery=FakeDelivery();runner=FakeRunner()
    Pipeline(store,delivery,runner,LocalTelemetryStorage(tmp_path/'private')).ingest('assignment',LIVE,NOW)
    monkeypatch.setattr(worker,'TelegramDelivery',lambda *a:delivery)
    monkeypatch.setattr(worker,'NeuralRunner',lambda:runner)
    result=asyncio.run(worker.run(settings(),client_factory=lambda *a:client,scanner_factory=Scanner,bootstrap=True))
    assert result['status']=='bootstrapped' and not delivery.calls and runner.calls==0
    store.close()


def test_missing_bootstrap_never_scans_or_sends(tmp_path,monkeypatch):
    store=SQLiteStore(tmp_path/'state.sqlite',ACCOUNT)
    class FreshClient(RPCClient):
        def rpc(self,name,p):
            if name=='flymind_runtime':return SimpleNamespace(execute=lambda:SimpleNamespace(data={'initialized':False}))
            return super().rpc(name,p)
    result=asyncio.run(worker.run(settings(),client_factory=lambda *a:FreshClient(store),scanner_factory=lambda *a:pytest.fail('Bootstrap gate bypassed')))
    assert result['status']=='bootstrap_required' and not store.counts()
    store.close()
