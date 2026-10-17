from datetime import timedelta
import hashlib
import json
from pathlib import Path
import pytest
from src.flymind.pipeline import Pipeline
from src.flymind.store import SQLiteStore,LocalTelemetryStorage,Conflict
from src.flymind.telegram import Delivery
from tests.flymind.test_events import ACCOUNT,NOW,LIVE


class FakeDelivery:
    ready=True
    def __init__(self): self.calls=[];self.responses=[]
    def deliver(self,text,message_id=None):
        self.calls.append((text,message_id))
        return self.responses.pop(0) if self.responses else Delivery('done',message_id=message_id or len(self.calls))


class FakeRunner:
    def __init__(self,fail=False):self.calls=0;self.fail=fail
    def run(self,encoding):
        self.calls+=1
        if self.fail:raise RuntimeError('SYNTHETIC failure MUST NOT appear in stored result')
        return {'status':'complete','readout':{'classification':'moderate','gf_spikes':[2,2],'active_neurons':282},'biological_response_validated':False},b'SYNTHETIC TELEMETRY FOR PLUMBING TEST'


def setup(tmp_path,runner=None):
    clock=[1000.0]
    store=SQLiteStore(tmp_path/'state.sqlite',ACCOUNT,clock=lambda:clock[0])
    delivery=FakeDelivery();runner=runner or FakeRunner()
    pipeline=Pipeline(store,delivery,runner,LocalTelemetryStorage(tmp_path/'private'),now=lambda:NOW)
    # Far from deadline to produce only one creation event.
    pipeline.ingest('assignment',{**LIVE,'due_at':(NOW+timedelta(days=5)).isoformat()},NOW)
    return store,delivery,runner,pipeline,clock


def test_primary_delivery_precedes_neural_and_enrichment_edits_same_message(tmp_path):
    store,d,r,p,clock=setup(tmp_path)
    p.drain_notifications()
    assert len(d.calls)==1 and r.calls==0
    p.drain_neural();p.drain_notifications('edit')
    assert len(d.calls)==2 and d.calls[0][1] is None and d.calls[1][1]==1
    assert d.calls[1][0] == d.calls[0][0]  # science remains private, same academic content
    assert store.counts()=={'send.done':1,'simulate.done':1,'edit.done':1}
    store.close()


def test_duplicate_event_and_job_retry_do_not_repeat_send(tmp_path):
    store,d,r,p,clock=setup(tmp_path)
    p.run_pending()
    p.ingest('assignment',{**LIVE,'due_at':(NOW+timedelta(days=5)).isoformat()},NOW)
    p.run_pending()
    assert sum(mid is None for _,mid in d.calls)==1 and r.calls==1
    store.close()


def test_state_events_and_outbox_commit_roll_back_together(tmp_path):
    store,d,r,p,clock=setup(tmp_path)
    old=store.load('assignment','20:10')
    bad=old.model_copy(update={'revision':999})
    from src.flymind.events import adapt
    snapshot,events=adapt(ACCOUNT,'assignment',{**LIVE,'score':50},old,NOW)
    events[0]=events[0].model_copy(update={'account_id':'OTHER'})
    with pytest.raises(ValueError):store.commit('assignment','20:10',old.revision,snapshot,events)
    assert store.load('assignment','20:10')==old
    with pytest.raises(Conflict):store.commit('assignment','20:10',0,bad,[])
    store.close()


def test_simulation_failure_does_not_lose_critical_delivery(tmp_path):
    store,d,r,p,clock=setup(tmp_path,FakeRunner(fail=True))
    p.ingest('assignment',LIVE,NOW)
    p.drain_notifications()
    assert any('ДЕДЛАЙН ИЗМЕНЁН!' in text for text,_ in d.calls)
    for _ in range(3):p.drain_neural();clock[0]+=1000
    p.drain_notifications('edit')
    assert all('нейрон' not in text.lower() and 'недоступна' not in text for text,_ in d.calls)
    assert store.counts().get('simulate.dead') == 2
    assert all('MUST NOT' not in (row['result'] or '') for row in store.db.execute('SELECT result FROM jobs'))
    assert store.counts().get('send.done')==2
    store.close()


def test_missing_telegram_credentials_keeps_unclaimed_pending_outbox(tmp_path):
    store,d,r,p,clock=setup(tmp_path)
    d.ready=False;p.run_pending()
    assert not d.calls and not r.calls
    assert store.counts()=={'send.pending':1,'simulate.pending':1}
    d.ready=True;p.run_pending()
    assert store.counts().get('send.done')==1
    store.close()


def test_explicit_transient_failure_retries_after_persisted_backoff(tmp_path):
    store,d,r,p,clock=setup(tmp_path)
    d.responses=[Delivery('retry',error_code='telegram_429',retry_after=60)]
    p.drain_notifications();p.drain_notifications()
    assert len(d.calls)==1
    clock[0]+=61;p.drain_notifications()
    assert store.counts()['send.done']==1 and len(d.calls)==2
    store.close()


def test_crash_after_claim_is_quarantined_not_automatically_resent(tmp_path):
    store,d,r,p,clock=setup(tmp_path)
    job=store.claim('send');assert job
    store.close()
    clock[0]+=121
    recovery=SQLiteStore(tmp_path/'state.sqlite',ACCOUNT,clock=lambda:clock[0])
    assert recovery.claim('send') is None
    assert recovery.counts()['send.ambiguous']==1
    with pytest.raises(ValueError):recovery.reconcile(job['id'])
    recovery.reconcile(job['id'],message_id=1234)
    assert recovery.claim('simulate')['message_id']==1234
    recovery.close()


def test_stale_lease_ack_and_duplicate_finish_are_rejected(tmp_path):
    store,d,r,p,clock=setup(tmp_path)
    job=store.claim('send')
    assert not store.finish({**job,'token':'wrong'},'done',{'message_id':1})
    assert store.finish(job,'done',{'message_id':1})
    assert not store.finish(job,'done',{'message_id':1})
    store.close()


def test_expired_simulation_is_safe_to_recompute_and_does_not_resend_base(tmp_path):
    store,d,r,p,clock=setup(tmp_path)
    p.drain_notifications();job=store.claim('simulate');clock[0]+=121
    recovered=store.claim('simulate')
    assert recovered and recovered['token']!=job['token']
    assert not store.finish(job,'done',{})
    store.finish(recovered,'retry',{'status':'failed'},delay=0)
    p.run_pending()
    assert sum(mid is None for _,mid in d.calls)==1
    store.close()


def test_cross_account_isolation_and_atomic_duplicate_claim(tmp_path):
    store,d,r,p,clock=setup(tmp_path)
    other=SQLiteStore(tmp_path/'state.sqlite','00000000-0000-0000-0000-000000000002',clock=lambda:clock[0])
    assert not other.counts() and other.claim('send') is None
    same=SQLiteStore(tmp_path/'state.sqlite',ACCOUNT,clock=lambda:clock[0])
    assert store.claim('send') and same.claim('send') is None
    other.close();same.close();store.close()


def test_health_and_forced_stats_use_outbox_without_neural_or_duplicate_reports(tmp_path):
    from src.flymind.reports import queue_reports
    store,d,r,p,clock=setup(tmp_path)
    courses=[{'id':20,'name':'<SYNTHETIC COURSE>','enrollments':[{'type':'student','computed_current_score':95}]}]
    queue_reports(p,courses,auto_report=True,run_id='test-run-1',now=NOW)
    p.run_pending();before=len(d.calls)
    queue_reports(p,courses,auto_report=True,run_id='test-run-1',now=NOW)
    p.run_pending()
    assert len(d.calls)==before and r.calls==1
    assert any('Итоговый GPA' in text and '&lt;SYNTHETIC COURSE&gt;' in text for text,_ in d.calls)
    store.close()


def test_neural_disabled_keeps_primary_delivery_and_marks_unavailable(tmp_path):
    store,d,r,p,clock=setup(tmp_path)
    p.neural_enabled=False
    p.run_pending()
    assert sum(mid is None for _,mid in d.calls)==1 and r.calls==0
    assert store.counts()['send.done']==1
    assert any(mid==1 and text == d.calls[0][0] for text,mid in d.calls)
    result=json.loads(store.db.execute("SELECT result FROM jobs WHERE stage='simulate'").fetchone()[0])
    assert result['status']=='disabled' and result['biological_response_validated'] is False
    store.close()


def test_shadow_runs_real_interface_but_never_edits_primary(tmp_path):
    store,d,r,p,clock=setup(tmp_path)
    p.enrichment_enabled=False
    p.run_pending()
    assert r.calls==1 and len(d.calls)==1 and d.calls[0][1] is None
    assert store.counts()['edit.done']==1
    store.close()


def test_storage_failure_keeps_delivery_and_recovers(tmp_path):
    store,d,r,p,clock=setup(tmp_path)
    original=p.storage
    class Broken:
        def put(self,*args):raise RuntimeError('storage offline')
    p.storage=Broken();p.run_pending()
    assert store.counts()['send.done']==1 and store.counts()['simulate.pending']==1
    clock[0]+=61;p.storage=original;p.run_pending()
    assert sum(mid is None for _,mid in d.calls)==1 and store.counts()['simulate.done']==1
    store.close()
