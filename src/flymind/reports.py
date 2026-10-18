"""Preserve scheduled health and workflow-dispatched GPA reports through the outbox."""
from datetime import datetime,timezone
import math
from src.core.gpa_engine import get_grade_point
from src.core.scanner import current_course_score
from .presentation import escaped
from .events import Snapshot
from .store import Conflict


def save_grade_snapshot(store, courses, *, now=None):
    """Account-scoped current grades; no events, no legacy writes, optimistic lock."""
    now = now or datetime.now(timezone.utc)
    rows = [{'course_id': c['id'], 'course_name': c.get('name', 'Unknown'),
             'current_score': current_course_score(c)} for c in courses]
    state = {'schema_version': 1, 'synced_at': now.isoformat(), 'rows': rows}
    for _ in range(3):
        old = store.load('report', '0:course_grades')
        try:
            if store.commit('report', '0:course_grades', old.revision,
                            Snapshot(revision=old.revision + 1, state=state), []):
                return
        except Conflict:
            pass
    raise Conflict('grade_snapshot_conflict')


def queue_reports(pipeline,courses,*,auto_report=False,run_id='',now=None):
    now=now or datetime.now(timezone.utc)
    period=now.strftime('%G-W%V')
    health_id=f'health:{period}'
    if pipeline.store.load('report','0:'+health_id).state is None:
        message='✅ Canvas проверен. Мониторинг заданий работает.\n📅 Актуальные сроки — /deadlines'
        pipeline.ingest('report',{'id':health_id,'name':'Health Check','message':message,'report_type':'health'},now)
    if not auto_report:
        return
    if not run_id:
        raise ValueError('idempotent_report_requires_run_id')
    key='stats:'+run_id
    if pipeline.store.load('report','0:'+key).state is not None:
        return
    points=0;credits=0;lines=[]
    for c in courses:
        name=c.get('name','Unknown')
        score=current_course_score(c)
        if 'practic' in name.lower():
            continue
        if score is None or score=='' or not math.isfinite(float(score)):
            lines.append(escaped(name)+': без оценки')
        else:
            weight=2 if 'физическая культура' in name.lower() else 5
            gp=get_grade_point(float(score));points+=gp*weight;credits+=weight
            lines.append(f'{escaped(name)}: {escaped(score)}% (GPA {gp})')
    estimate=f'{points/credits:.2f}' if credits else '—'
    lines.append(f'<b>Итоговый GPA (оценочный): {estimate} / 4.0</b>\nНе официальный транскрипт: предполагается 5 кредитов на курс, 2 для физкультуры.')
    pipeline.ingest('report',{'id':key,'name':'GPA','message':'\n'.join(lines),'report_type':'stats'},now)
