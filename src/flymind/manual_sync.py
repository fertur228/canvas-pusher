"""Manual request lifecycle. Completion is emitted ONLY from workflow_run: completed."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
import re
import uuid
from .worker import Settings, run
from .store import SupabaseStore
from .events import Snapshot, adapt
from .pipeline import Pipeline
from .telegram import TelegramDelivery


def context():
    s=Settings.from_env();s.validate()
    if not s.enabled or os.getenv('CANVAS_WORKER_ENABLED')!='true' or s.delivery_mode not in ('test','production'):
        raise ValueError('manual_activation_gates_closed')
    from supabase import create_client
    client=create_client(s.supabase_url,s.supabase_key)
    store=SupabaseStore(client,s.account_id,int(s.chat_id))
    delivery=TelegramDelivery(s.telegram_token,s.chat_id)
    if not delivery.bot_id or not store._rpc('flymind_check_bot',{'p_bot':int(delivery.bot_id)}):
        raise ValueError('bot_binding_required')
    return s,client,store,delivery


def completion_text(row,conclusion):
    summary=row.get('summary') or {};counts=summary.get('event_counts') or {}
    verified=summary.get('sync_status')=='verified'
    ok=conclusion=='success' and verified
    stamp=summary.get('last_successful_check')
    from zoneinfo import ZoneInfo
    try:stamp=datetime.fromisoformat(stamp).astimezone(ZoneInfo('Asia/Almaty')).strftime('%d.%m.%Y %H:%M Asia/Almaty')
    except (TypeError,ValueError):stamp='не подтверждена; /status'
    return '\n'.join(['✅ Проверка Canvas завершена.' if ok else '⚠️ Workflow завершён с ошибкой или неполной проверкой.',
                      f'Последняя успешная проверка: {stamp}',
                      f"Новых заданий: {int(counts.get('assignment_created',0))}",
                      f"Изменений дедлайна: {int(counts.get('deadline_changed',0))}",
                      f"Обновлений оценок: {int(counts.get('grade_updated',0))}",
                      f"Ошибок: {max(0 if ok else 1,int(summary.get('errors',0)))}",
                      'Нажмите 📅 Дедлайны, чтобы открыть проверенный список.'])


async def execute(s,store,request_id,run_id,ref,runner=run):
    uuid.UUID(request_id)
    if not re.fullmatch(r'\d+',run_id):raise ValueError('invalid_run_id')
    if not store._rpc('flymind_manual_start',{'p_id':request_id,'p_run':run_id,'p_ref':ref}):
        return {'status':'duplicate_or_expired_request'}
    try:summary=await runner(s)
    except Exception:summary={'status':'failed','sync_status':'failed','errors':1}
    store._rpc('flymind_manual_prepare',{'p_id':request_id,'p_run':run_id,'p_summary':summary})
    return summary


def finalize_event(event,store,client,delivery,repo):
    r=event.get('workflow_run',{})
    if event.get('action')!='completed' or r.get('status')!='completed' or r.get('event')!='workflow_dispatch' or r.get('path')!='.github/workflows/check_canvas.yml' or r.get('head_repository',{}).get('full_name')!=repo:
        raise ValueError('untrusted_completion_context')
    match=re.fullmatch(r'FlyMind sync ([0-9a-f-]{36})',r.get('display_title',''))
    if not match:return {'status':'not_manual'}
    request_id=str(uuid.UUID(match[1]));run_id=str(r['id'])
    rows=client.table('flymind_manual_requests').select('*').eq('account_id',store.account_id).eq('id',request_id).execute().data
    if not rows or rows[0]['workflow_ref']!=r.get('head_branch'):raise ValueError('request_branch_mismatch')
    row=rows[0]
    if row['state'] in ('completed','failed'):
        # Reconcile/retry the already committed result without generating another event.
        _, prior=adapt(store.account_id,'report',{'id':request_id,'name':'Manual Canvas sync','message':'','report_type':'health'},Snapshot(),datetime.now(timezone.utc))
        Pipeline(store,delivery,None,None,neural_enabled=False).drain_notifications(only_report=prior[0].event_id)
        return {'status':'already_finalized'}
    if not (row.get('summary') or {}).get('last_successful_check'):
        health=client.table('flymind_health').select('last_snapshot_success').eq('account_id',store.account_id).execute().data
        row={**row,'summary':{**(row.get('summary') or {}),'last_successful_check':health[0].get('last_snapshot_success') if health else None}}
    text=completion_text(row,r.get('conclusion'))
    _,events=adapt(store.account_id,'report',{'id':request_id,'name':'Manual Canvas sync','message':text,'report_type':'health'},Snapshot(),datetime.now(timezone.utc))
    done=store._rpc('flymind_manual_complete',{'p_id':request_id,'p_run':run_id,'p_conclusion':r.get('conclusion') or 'unknown','p_event':events[0].model_dump(mode='json')})
    # Send only this operational result, never release academic backlog after an auth failure.
    Pipeline(store,delivery,None,None,neural_enabled=False).drain_notifications(only_report=events[0].event_id)
    return {'status':'finalized' if done else 'already_finalized'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['run','finalize']);a=p.parse_args()
    try:
        s,client,store,delivery=context()
        if a.action=='run':
            result=asyncio.run(execute(s,store,os.environ['MANUAL_REQUEST_ID'],os.environ['GITHUB_RUN_ID'],os.environ['GITHUB_REF_NAME']))
            print(json.dumps(result));raise SystemExit(0 if result.get('status') in ('ok','duplicate_or_expired_request') else 2)
        with open(os.environ['GITHUB_EVENT_PATH']) as f:event=json.load(f)
        print(json.dumps(finalize_event(event,store,client,delivery,os.environ['GITHUB_REPOSITORY'])))
    except Exception:raise SystemExit('Manual sync failed; private details omitted') from None
if __name__=='__main__':main()
