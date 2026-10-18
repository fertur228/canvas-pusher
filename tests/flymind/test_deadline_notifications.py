"""Synthetic academic scenarios; real state machine, CAS transactions and outbox."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from threading import Barrier

import pytest

from src.flymind.events import EventKind, Snapshot, adapt, reminder_audit, reminder_band
from src.flymind.pipeline import Pipeline
from src.flymind.presentation import render
from src.flymind.store import SQLiteStore
from src.flymind.telegram import Delivery
from tests.flymind.test_events import ACCOUNT, LIVE, NOW
from tests.flymind.test_pipeline import FakeDelivery, FakeRunner


def task(hours=48, **values):
    return {**LIVE, 'due_at': (NOW+timedelta(hours=hours)).isoformat() if hours is not None else None, **values}


def evolve(live, old, hours=0, **kwargs):
    return adapt(ACCOUNT, 'assignment', live, old, NOW+timedelta(hours=hours), **kwargs)


@pytest.mark.parametrize('hours', [None, 120, 4, 0, -1])
@pytest.mark.parametrize('points', [None, 0, 100])
def test_assignment_appearing_after_initial_scan_always_creates_one_alert(hours, points):
    live = task(hours, points_possible=points)
    initial, historical = evolve(task(100, id=999), Snapshot(), bootstrap=True)
    assert not historical and initial.state
    snapshot, events = evolve(live, Snapshot())
    assert [e.kind for e in events] == [EventKind.CREATED]
    assert not evolve(live, snapshot, hours=.1)[1]
    assert len({e.event_id for e in events}) == 1


@pytest.mark.parametrize('threshold', [24, 12, 6, 3, 1])
def test_each_exact_threshold_persisted_once(threshold):
    live = task(48)
    snapshot, _ = evolve(live, Snapshot(), bootstrap=True)
    snapshot, events = evolve(live, snapshot, 48-threshold)
    assert [(e.kind, e.reminder) for e in events] == [(EventKind.REMINDER, f'{threshold}h')]
    assert reminder_audit(snapshot.reminders)[-1]['status'] == 'queued'
    assert not evolve(live, snapshot, 48-threshold+.01)[1]


def test_all_five_thresholds_in_sequence_and_zero_overdue_reminders():
    live = task(48)
    snapshot, _ = evolve(live, Snapshot(), bootstrap=True)
    ids = set()
    for threshold in (24, 12, 6, 3, 1):
        snapshot, events = evolve(live, snapshot, 48-threshold)
        assert len(events) == 1 and events[0].reminder == f'{threshold}h'
        ids.add(events[0].event_id)
    assert len(ids) == 5
    assert not evolve(live, snapshot, 48)[1]
    assert not evolve(live, snapshot, 49)[1]


def test_skipped_thresholds_are_audited_and_never_caught_up_as_burst():
    live = task(48)
    snapshot, _ = evolve(live, Snapshot(), bootstrap=True)
    snapshot, events = evolve(live, snapshot, 46.25)
    assert [e.reminder for e in events] == ['3h']
    assert {r['threshold']: r['status'] for r in reminder_audit(snapshot.reminders)} == {
        '24h': 'skipped_late', '12h': 'skipped_late', '6h': 'skipped_late', '3h': 'queued'}
    # A clock rollback cannot backfill previously consumed larger thresholds.
    assert not evolve(live, snapshot, 40)[1]
    snapshot, events = evolve(live, snapshot, 47.1)
    assert [e.reminder for e in events] == ['1h']


def test_four_hour_creation_covers_six_hour_band_then_three_and_one_work():
    live = task(4)
    snapshot, events = evolve(live, Snapshot())
    assert [e.kind for e in events] == [EventKind.CREATED]
    assert {r['threshold'] for r in reminder_audit(snapshot.reminders)} == {'24h', '12h', '6h'}
    assert all(r['status'] == 'covered_by_creation' for r in reminder_audit(snapshot.reminders))
    assert not evolve(live, snapshot, .5)[1]
    snapshot, events = evolve(live, snapshot, 1)
    assert [e.reminder for e in events] == ['3h']
    assert [e.reminder for e in evolve(live, snapshot, 3)[1]] == ['1h']


def test_submission_not_grade_stops_reminders():
    live = task(48, score=0)
    snapshot, _ = evolve(live, Snapshot(), bootstrap=True)
    assert [e.reminder for e in evolve(live, snapshot, 24)[1]] == ['24h']
    submitted = {**live, 'has_submitted': True}
    snapshot, events = evolve(submitted, snapshot, 23)
    assert [e.kind for e in events] == [EventKind.SUBMISSION]
    for hour in (24, 36, 42, 45, 47):
        snapshot, events = evolve(submitted, snapshot, hour)
        assert not events


def test_deadline_change_covers_current_band_and_resets_version_including_return_to_old_date():
    a, b = task(48), task(72)
    snapshot, _ = evolve(a, Snapshot(), bootstrap=True)
    snapshot, first = evolve(a, snapshot, 24)
    snapshot, changed = evolve(b, snapshot, 24)
    assert [e.kind for e in changed] == [EventKind.DEADLINE]
    snapshot, second = evolve(b, snapshot, 48)
    assert [e.reminder for e in second] == ['24h']
    # A genuine return to the old timestamp must get new reminder identities.
    snapshot, _ = evolve(a, snapshot, 25)
    snapshot, third = evolve(a, snapshot, 36)
    assert [e.reminder for e in third] == ['12h']
    assert len({first[0].event_id, second[0].event_id, third[0].event_id}) == 3
    equivalent = {**a, 'due_at': (NOW+timedelta(hours=48)).isoformat().replace('+00:00','Z')}
    assert not evolve(equivalent, snapshot, 36)[1]


def test_cycled_deadline_can_reemit_same_threshold_for_new_version():
    a, b = task(48), task(72)
    s, _ = evolve(a, Snapshot(), bootstrap=True)
    s, first = evolve(a, s, 24)
    s, _ = evolve(b, s, 24)
    # Both changed dates are >24h away, then simulated time reaches 24h again.
    s, _ = evolve(a, s, 23)
    _, second = evolve(a, s, 24)
    assert first[0].reminder == second[0].reminder == '24h'
    assert first[0].event_id != second[0].event_id


def test_bootstrap_inside_band_is_silent_but_later_threshold_still_alerts():
    live = task(4)
    snapshot, events = evolve(live, Snapshot(), bootstrap=True)
    assert not events
    assert all(r['status'] == 'silent_bootstrap' for r in reminder_audit(snapshot.reminders))
    assert not evolve(live, snapshot, .5)[1]
    assert [e.reminder for e in evolve(live, snapshot, 1)[1]] == ['3h']


def test_v1_marks_and_removed_48_hour_band_upgrade_without_repeat():
    live = task(48)
    old = Snapshot(revision=7, state=live, reminders=[live['due_at']+':12h'])
    s, events = evolve(live, old, 36)
    assert not events
    assert live['due_at']+':24h' in s.reminders
    assert [e.reminder for e in evolve(live, s, 42)[1]] == ['6h']
    old.reminders = [live['due_at']+':48h']
    assert reminder_band(live, NOW) is None
    assert [e.reminder for e in evolve(live, old, 24)[1]] == ['24h']


def make_pipeline(tmp_path):
    now = [NOW]
    store = SQLiteStore(tmp_path/'deadline.sqlite', ACCOUNT, clock=lambda: now[0].timestamp())
    delivery, runner = FakeDelivery(), FakeRunner(fail=True)
    pipeline = Pipeline(store, delivery, runner, None, now=lambda:now[0], enrichment_enabled=False)
    pipeline.ingest('assignment', task(48), bootstrap=True)
    return pipeline, store, delivery, runner, now


@pytest.mark.parametrize('change,reason', [({'has_submitted':True},'submitted'),
                                         ({'due_at':task(72)['due_at']},'deadline_changed'),
                                         ({'due_at':None},'deadline_changed')])
def test_queued_retry_cancelled_after_submission_or_deadline_change(tmp_path, change, reason):
    p, store, d, runner, now = make_pipeline(tmp_path)
    now[0] = NOW+timedelta(hours=24)
    p.ingest('assignment', task(48))
    d.responses = [Delivery('retry', error_code='telegram_429', retry_after=60)]
    p.drain_notifications()
    now[0] += timedelta(minutes=2)
    p.ingest('assignment', task(48, **change))
    p.run_pending(10)
    # Failed attempt + actual change notification, no stale reminder retry.
    assert len(d.calls) == 2
    results = [json.loads(r['result']) for r in store.db.execute("SELECT result FROM jobs WHERE stage='send'")]
    assert any(r.get('suppressed') == reason for r in results)
    assert runner.calls == 1  # only change notification's neural job
    store.close()


def test_pending_old_thresholds_coalesce_at_delivery_and_no_post_deadline_send(tmp_path):
    p, store, d, runner, now = make_pipeline(tmp_path)
    for hour in (24, 36, 42, 45):
        now[0] = NOW+timedelta(hours=hour)
        p.ingest('assignment', task(48))
    p.drain_notifications()
    assert len(d.calls) == 1 and 'ДЕДЛАЙН ЧЕРЕЗ 3 ЧАСА!' in d.calls[0][0]
    now[0] = NOW+timedelta(hours=47)
    p.ingest('assignment', task(48))
    now[0] = NOW+timedelta(hours=48)
    p.drain_notifications()
    assert len(d.calls) == 1
    store.close()


def test_temporary_failure_recovers_once_and_neural_failure_cannot_block(tmp_path):
    p, store, d, runner, now = make_pipeline(tmp_path)
    p.ingest('assignment', task(4, id=999))
    d.responses = [Delivery('retry', error_code='connect_failed', retry_after=30)]
    p.run_pending()
    assert runner.calls == 0 and store.counts()['send.pending'] == 1
    now[0] += timedelta(seconds=31)
    p.run_pending()
    assert len(d.calls) == 2 and store.counts()['send.done'] == 1
    assert runner.calls == 1 and store.counts()['simulate.pending'] == 1
    p.ingest('assignment', task(4, id=999))
    p.run_pending()
    assert len(d.calls) == 2
    store.close()


def test_overlapping_scans_retry_cas_without_duplicate_creation_or_threshold(tmp_path):
    path = tmp_path/'overlap.sqlite'
    SQLiteStore(path, ACCOUNT).close()

    def overlap(live, now):
        barrier = Barrier(2)
        def scan(_):
            store = SQLiteStore(path, ACCOUNT)
            load = store.load
            first = [True]
            def synchronized_load(*args):
                snapshot = load(*args)
                if first[0]:
                    first[0] = False
                    barrier.wait(timeout=5)
                return snapshot
            store.load = synchronized_load
            try:
                return Pipeline(store,None,None,None).ingest('assignment',live,now)
            finally:
                store.close()
        with ThreadPoolExecutor(2) as pool:
            return sorted(pool.map(scan,range(2)))

    assert overlap(task(48), NOW) == [0,1]
    assert overlap(task(48), NOW+timedelta(hours=24)) == [0,1]
    store = SQLiteStore(path,ACCOUNT)
    assert store.db.execute('SELECT count(*) FROM events').fetchone()[0] == 2
    assert store.counts()['send.pending'] == 2
    store.close()


def test_ordinary_message_has_actionable_fields_without_internal_or_scientific_debug():
    _, events = evolve(task(4, html_url='https://canvas.narxoz.kz/courses/20/assignments/10'), Snapshot())
    text = render(events[0])
    for value in ('НОВОЕ ЗАДАНИЕ!', '📌', '📝', '📚', '📅', '💯', '09:00 Asia/Almaty', '4 ч 0 мин', 'Открыть задание в Canvas', '&lt;SYNTHETIC task&gt;'):
        assert value in text
    for value in ('GF', 'Событие:', events[0].event_id[:12], 'Нейрон', 'нейрон', 'правила'):
        assert value not in text
    assert len(text) < 4096


def test_new_assignment_batch_not_postponed_by_old_25_message_budget(tmp_path):
    p, store, d, runner, now = make_pipeline(tmp_path)
    for i in range(30):
        assert p.ingest('assignment', task(None, id=1000+i)) == 1
    assert p.drain_notifications() == 30
    assert len(d.calls) == 30 and store.counts()['send.done'] == 30
    assert runner.calls == 0
    store.close()


def test_reminder_read_failure_does_not_send_unverified_cached_event(tmp_path):
    p, store, d, runner, now = make_pipeline(tmp_path)
    now[0] = NOW+timedelta(hours=24)
    p.ingest('assignment', task(48))
    load = store.load
    def unavailable(*args):
        raise RuntimeError('database unavailable')
    store.load = unavailable
    p.drain_notifications()
    assert not d.calls and store.counts()['send.pending'] == 1
    store.load = load
    now[0] += timedelta(seconds=61)
    p.drain_notifications()
    assert len(d.calls) == 1
    store.close()


def test_hosted_scenario_plan_offline_before_any_live_delivery(tmp_path):
    from src.flymind.deadline_validation import scenarios
    from src.flymind.store import LocalTelemetryStorage
    p, store, d, runner, now = make_pipeline(tmp_path)
    p.runner = FakeRunner()
    p.storage = LocalTelemetryStorage(tmp_path/'private')
    for step in scenarios(NOW):
        now[0] = NOW+timedelta(hours=step['hour'])
        assert p.ingest('assignment',step['live'],bootstrap=step['bootstrap']) == step['expected']
        if not step.get('defer'):
            p.run_pending(20)
        assert p.ingest('assignment',step['live'],bootstrap=step['bootstrap']) == 0
    assert len(d.calls) == 11
    assert all('ТЕСТ' in text and mid is None for text,mid in d.calls)
    assert store.counts() == {'send.done':12,'simulate.done':12,'edit.done':12}
    store.close()
