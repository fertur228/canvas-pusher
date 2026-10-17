from datetime import timedelta
from types import SimpleNamespace
import pytest
from src.flymind.watchdog import classify
from src.flymind.maintenance import cleanup
from tests.flymind.test_events import NOW,ACCOUNT


def test_watchdog_age_and_failure_states():
    h={'last_attempt':NOW.isoformat(),'status':'healthy','queue':{}}
    assert classify(h,NOW)=='healthy'
    assert classify(h,NOW+timedelta(minutes=31))=='delayed'
    assert classify(h,NOW+timedelta(minutes=91))=='failed'
    assert classify({**h,'queue':{'send.ambiguous':1}},NOW)=='degraded'
    assert classify(None,NOW)=='failed'


def test_retention_dry_run_and_scope_protection():
    path=f'{ACCOUNT}/{"a"*64}/{"b"*64}.json.gz';removed=[]
    store=SimpleNamespace(account_id=ACCOUNT,_rpc=lambda name,p:[{'path':path}] if name=='flymind_retention' else [path])
    storage=SimpleNamespace(from_=lambda name:SimpleNamespace(remove=lambda paths:removed.extend(paths)))
    assert cleanup(store,storage)['objects_removed']==0 and not removed
    assert cleanup(store,storage,apply=True)['objects_removed']==1 and removed==[path]
    store._rpc=lambda name,p:[{'path':'other/private.json.gz'}] if name=='flymind_retention' else ['other/private.json.gz']
    with pytest.raises(ValueError,match='invalid_cleanup_scope'):cleanup(store,storage,apply=True)
