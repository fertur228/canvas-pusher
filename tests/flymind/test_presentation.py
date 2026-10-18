"""The concise lock-screen UX must not change delivery or scientific results."""
from datetime import timedelta
import pytest
from src.flymind.events import adapt, Snapshot, EventKind
from src.flymind.presentation import render
from tests.flymind.test_events import ACCOUNT, NOW, LIVE


def event(kind, **fields):
    old = Snapshot(revision=1, state={**LIVE, 'due_at': (NOW+timedelta(hours=30)).isoformat()})
    if kind == EventKind.CREATED:
        old = Snapshot()
    _, rows = adapt(ACCOUNT, 'assignment', {**LIVE, **fields}, old, NOW)
    return next(r for r in rows if r.kind == kind)


@pytest.mark.parametrize('due,points', [(None,None),(None,0),((NOW+timedelta(hours=4)).isoformat(),100)])
def test_new_assignment_compact_even_without_deadline_or_points(due, points):
    text = render(event(EventKind.CREATED, due_at=due, points_possible=points, score=None))
    assert text.startswith('<b>📌 НОВОЕ ЗАДАНИЕ!</b>')
    assert all(x in text for x in ('📝','📚','📅','💯'))
    assert len(text.splitlines()) <= 7
    assert ('не установлен' in text) == (due is None)


def test_grades_keep_zero_missing_and_course_score_separate():
    text = render(event(EventKind.GRADE, score=0, points_possible=100, course_score=0))
    assert '🔔 НОВАЯ ОЦЕНКА!' in text and '⭐ 0.0 / 100.0' in text and '📈 По курсу: 0.0%' in text
    text = render(event(EventKind.GRADE, score=25, course_score=None))
    assert '📈 По курсу: —' in text and 'None' not in text


def test_changed_deadline_and_late_reminder_use_actual_dates_and_hours():
    changed = event(EventKind.DEADLINE, due_at=(NOW+timedelta(hours=4)).isoformat())
    text = render(changed)
    assert all(x in text for x in ('ДЕДЛАЙН ИЗМЕНЁН!','🕒 Было:','✅ Стало:'))
    reminder = changed.model_copy(update={'kind':EventKind.REMINDER,'reminder':'6h'})
    text = render(reminder, now=NOW+timedelta(hours=2))
    assert 'ЧЕРЕЗ 2 ЧАСА!' in text and len(text.splitlines()) <= 5


def test_neural_success_and_failure_never_expose_science_in_notifications():
    e = event(EventKind.CREATED, name='<PRIVATE & title>', points_possible=0)
    ordinary = render(e)
    assert '&lt;PRIVATE &amp; title&gt;' in ordinary
    for result in ({'status':'complete','readout':{'classification':'elevated','gf_spikes':[3,4]}}, {'status':'failed'}):
        assert render(e,result) == ordinary
    assert e.event_id not in ordinary
