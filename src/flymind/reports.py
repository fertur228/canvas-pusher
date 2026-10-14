"""Preserve scheduled health and workflow-dispatched GPA reports through the outbox."""
from datetime import datetime,timezone
from src.core.gpa_engine import calculate_gpa,get_grade_point
from .presentation import escaped


def queue_reports(pipeline,courses,*,auto_report=False,run_id='',now=None):
    now=now or datetime.now(timezone.utc)
    period=now.strftime('%G-W%V')
    health_id=f'health:{period}'
    if pipeline.store.load('report','0:'+health_id).state is None:
        counts=pipeline.store.counts()
        message='Плановая проверка запущена. Состояния durable outbox:\n'+escaped(', '.join(f'{k}: {v}' for k,v in sorted(counts.items())),700)
        pipeline.ingest('report',{'id':health_id,'name':'Health Check','message':message,'report_type':'health'},now)
    if not auto_report:
        return
    if not run_id:
        raise ValueError('idempotent_report_requires_run_id')
    key='stats:'+run_id
    if pipeline.store.load('report','0:'+key).state is not None:
        return
    scores={};lines=[]
    for c in courses:
        name=c.get('name','Unknown')
        score=next((e.get('computed_current_score') for e in c.get('enrollments',[]) if e.get('type')=='student'),None)
        if score is None or float(score)==0:
            lines.append(escaped(name)+': без оценки')
        elif 'practic' not in name.lower():
            scores[name]=float(score)
            if 'Физическая культура' in name:
                lines.append(f'{escaped(name)}: Зачет (GPA 4.0)')
            else:
                lines.append(f'{escaped(name)}: {escaped(score)}% (GPA {get_grade_point(float(score))})')
    lines.append(f'<b>Итоговый GPA: {calculate_gpa(scores)} / 4.0</b>')
    pipeline.ingest('report',{'id':key,'name':'GPA','message':'\n'.join(lines),'report_type':'stats'},now)
