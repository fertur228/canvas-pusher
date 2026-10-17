"""SYNTHETIC Canvas fixtures; biological simulation data is never invented."""
from datetime import datetime,timezone,timedelta
import pytest
from src.flymind.events import Snapshot,EventKind,adapt
from src.flymind.sensory import encode,readout
from src.flymind.presentation import render
from src.flymind.worker import Settings

ACCOUNT='00000000-0000-0000-0000-000000000001'
NOW=datetime(2026,10,14,tzinfo=timezone.utc)
LIVE={'id':10,'course_id':20,'course_name':'SYNTHETIC course','name':'<SYNTHETIC task>', 'due_at':(NOW+timedelta(hours=2)).isoformat(),'points_possible':100,'score':None,'has_submitted':False}


def test_creation_covers_current_reminder_and_is_reproducible():
    snapshot,events=adapt(ACCOUNT,'assignment',LIVE,Snapshot(),NOW)
    assert [e.kind for e in events]==[EventKind.CREATED]
    assert events==adapt(ACCOUNT,'assignment',LIVE,Snapshot(),NOW)[1]
    assert not adapt(ACCOUNT,'assignment',LIVE,snapshot,NOW+timedelta(minutes=10))[1]
    assert all(encode(e)['case']=='strong' for e in events)


def test_simultaneous_deadline_and_grade_changes_are_not_collapsed():
    old=Snapshot(revision=4,state={**LIVE,'due_at':(NOW+timedelta(hours=72)).isoformat(),'score':90})
    _,events=adapt(ACCOUNT,'assignment',{**LIVE,'score':50},old,NOW)
    assert [e.kind for e in events]==[EventKind.DEADLINE,EventKind.GRADE]
    assert len({e.event_id for e in events})==2


def test_repeated_grade_transitions_get_new_revision_ids():
    old=Snapshot(revision=1,state={**LIVE,'has_submitted':True,'score':80})
    a,ea=adapt(ACCOUNT,'assignment',{**old.state,'score':90},old,NOW)
    b,_=adapt(ACCOUNT,'assignment',{**old.state,'score':80},a,NOW)
    _,ec=adapt(ACCOUNT,'assignment',{**old.state,'score':90},b,NOW)
    assert ea[0].event_id!=ec[0].event_id


def test_reminders_recover_missed_windows_and_deduplicate_per_deadline():
    old=Snapshot(revision=1,state={**LIVE,'due_at':(NOW+timedelta(hours=72)).isoformat()})
    now=NOW+timedelta(hours=70,minutes=30)
    s,events=adapt(ACCOUNT,'assignment',old.state,old,now)
    assert events[0].reminder=='3h'
    assert not adapt(ACCOUNT,'assignment',old.state,s,now+timedelta(minutes=1))[1]
    _,one=adapt(ACCOUNT,'assignment',old.state,s,now+timedelta(minutes=40))
    assert one[0].reminder=='1h'


def test_submitted_assignment_does_not_remind():
    _,events=adapt(ACCOUNT,'assignment',{**LIVE,'has_submitted':True},Snapshot(),NOW)
    assert all(e.kind!=EventKind.REMINDER for e in events)


def test_baseline_bootstrap_is_explicit_and_silent():
    snapshot,events=adapt(ACCOUNT,'assignment',LIVE,Snapshot(),NOW,bootstrap=True)
    assert not events
    assert not adapt(ACCOUNT,'assignment',LIVE,snapshot,NOW)[1]


def test_sensor_encoder_uses_only_existing_profiles_and_stored_observation_time():
    far={**LIVE,'due_at':(NOW+timedelta(days=5)).isoformat()}
    _,events=adapt(ACCOUNT,'assignment',far,Snapshot(),NOW)
    e=events[0]
    assert encode(e)['case']=='weak'
    assert encode(e)==encode(e.model_copy())
    assert encode(e)['stimulus']['targets']==['LC4','LPLC2']
    assert encode(e)['stimulus']['direct_gf_stimulation'] is False


def test_file_events_are_delivered_but_not_sent_to_neural_engine():
    _,events=adapt(ACCOUNT,'file',{'id':10,'course_id':20,'display_name':'SYNTHETIC'},Snapshot(),NOW)
    assert encode(events[0]) is None


def test_presentation_does_not_downgrade_critical_and_escapes_private_html():
    _,events=adapt(ACCOUNT,'assignment',LIVE,Snapshot(),NOW)
    text=render(events[0],{'status':'complete','readout':{'classification':'minimal','gf_spikes':[0,0],'active_neurons':0}})
    assert 'Скоро дедлайн!' in text and 'минимальный' in text
    assert '&lt;SYNTHETIC task&gt;' in text and '<SYNTHETIC task>' not in text
    assert 'Биологически не валидировано' in text


def test_readout_thresholds_are_explicit_engineering_rules():
    r=readout({'readout':[{'spike_times_ms':[1,2,3],'latency_from_stimulus_ms':1,'peak_depolarization_mv':7},
                            {'spike_times_ms':[1,2,3,4],'latency_from_stimulus_ms':1,'peak_depolarization_mv':7}], 'active_neurons':418,'spikes':834})
    assert r['classification']=='elevated' and r['biological_response_validated'] is False
    assert 'ENGINEERING' in r['thresholds']


def test_disabled_flag_is_a_noop_even_with_missing_or_invalid_optional_config():
    Settings.from_env({'FLYMIND_MAX_NEURAL':'invalid'}).validate()
    assert not Settings.from_env({}).enabled
    with pytest.raises(ValueError):
        Settings(enabled=True).validate()


def test_naive_timestamp_rejected_instead_of_implicit_local_timezone():
    with pytest.raises(ValueError):
        adapt(ACCOUNT,'assignment',{**LIVE,'due_at':'2026-10-14T12:00:00'},Snapshot(),NOW)


def test_submission_transition_is_not_lost_and_stops_reminders():
    old=Snapshot(revision=1,state=LIVE)
    snapshot,events=adapt(ACCOUNT,'assignment',{**LIVE,'has_submitted':True},old,NOW)
    assert [e.kind for e in events]==[EventKind.SUBMISSION]
    assert '✅ Сдано' in render(events[0])
    assert encode(events[0])['case']=='weak'
    assert not adapt(ACCOUNT,'assignment',snapshot.state,snapshot,NOW)[1]


def test_activation_defaults_are_safe_and_test_chat_cannot_fallback():
    config=Settings.from_env({'FLYMIND_ENABLED':'true','TELEGRAM_CHAT_ID':'123'})
    assert config.delivery_mode=='disabled' and config.mode=='shadow'
    from dataclasses import replace
    with pytest.raises(ValueError,match='explicit_test_chat_required'):
        replace(config,delivery_mode='test').validate()
    with pytest.raises(ValueError,match='production_activation_gate_required'):
        replace(config,delivery_mode='production').validate()
