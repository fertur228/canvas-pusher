"""Finite, resumable synthetic deadline exercise against the verified hosted test group.

Real PostgreSQL RPC/outbox, Telegram delivery and fixed FlyWire simulation. Academic
fixtures and the advancing clock are SYNTHETIC; no Canvas writes or primary sends.
The checkpoint makes re-execution safe, including a crash after Telegram success.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time

from supabase import create_client

from .bot_setup import BotAPI
from .events import Snapshot, reminder_audit
from .hosted_validation import test_settings
from .neural import NeuralRunner
from .pipeline import Pipeline
from .store import SupabaseStore, SupabaseTelemetryStorage
from .telegram import TelegramDelivery

CHECKPOINT = '0:flymind-deadline-validation-v2'
COURSE = 999999999010


def scenarios(base):
    def task(number, hours, **values):
        return {'id': COURSE+number, 'course_id': COURSE,
                'course_name': 'СИНТЕТИЧЕСКИЙ ТЕСТ — не реальный курс',
                'name': f'ТЕСТ напоминаний №{number}; учебный сценарий, время ускорено',
                'due_at': (base+timedelta(hours=hours)).isoformat() if hours is not None else None,
                'has_submitted': False, 'points_possible': 0, 'score': None, **values}
    steps = [dict(live=task(1, None), hour=0, expected=1, bootstrap=False),
             dict(live=task(2, 4), hour=0, expected=1, bootstrap=False),
             dict(live=task(2, 4), hour=1, expected=1, bootstrap=False),
             dict(live=task(3, 48), hour=0, expected=0, bootstrap=True)]
    steps += [dict(live=task(3, 48), hour=48-h, expected=1, bootstrap=False) for h in (24,12,6,3,1)]
    steps += [dict(live=task(4, 48), hour=0, expected=0, bootstrap=True),
              dict(live=task(4, 48), hour=46, expected=1, bootstrap=False),
              # Persist a queued reminder, then confirm submission BEFORE any send.
              dict(live=task(4, 48), hour=47, expected=1, bootstrap=False, defer=True),
              dict(live=task(4, 48, has_submitted=True), hour=47.1, expected=1, bootstrap=False),
              dict(live=task(2, 72), hour=3, expected=1, bootstrap=False)]
    return steps


def validate(env):
    settings = test_settings(env)  # exact project, test account, shadow + production false
    import logging
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    me = BotAPI(settings.telegram_token).call('getMe')
    client = create_client(settings.supabase_url, settings.supabase_key)
    store = SupabaseStore(client, settings.account_id, int(settings.chat_id), 'https://canvas.narxoz.kz')
    if not store._rpc('flymind_check_bot', {'p_bot':me['id']}):
        raise ValueError('database_bot_binding_mismatch')
    checkpoint = store.load('report', CHECKPOINT)
    if checkpoint.state is None:
        checkpoint = Snapshot(revision=checkpoint.revision+1, state={
            'base':datetime.now(timezone.utc).isoformat(), 'completed_steps':0})
        if not store.commit('report',CHECKPOINT,checkpoint.revision-1,checkpoint,[]):
            raise ValueError('checkpoint_conflict')
    base = datetime.fromisoformat(checkpoint.state['base'])
    clock = [base]
    pipeline = Pipeline(store,TelegramDelivery(settings.telegram_token,settings.chat_id),NeuralRunner(),
                        SupabaseTelemetryStorage(client),enrichment_enabled=False,now=lambda:clock[0])
    steps = scenarios(base)
    started = time.perf_counter()
    for index, step in enumerate(steps):
        if index < checkpoint.state['completed_steps']:
            continue
        clock[0] = base+timedelta(hours=step['hour'])
        n = pipeline.ingest('assignment',step['live'],bootstrap=step['bootstrap'])
        # 0 is allowed on resume after an ingest committed but checkpoint did not.
        if n not in (0,step['expected']):
            raise ValueError('unexpected_synthetic_event_count')
        if not step.get('defer'):
            pipeline.run_pending(20)
            if any(n for k,n in store.counts().items() if not k.endswith('.done')):
                raise ValueError('incomplete_delivery_or_neural_do_not_blindly_resend')
        # Repeat the exact observed state: no new events or reminders.
        if pipeline.ingest('assignment',step['live'],bootstrap=step['bootstrap']) != 0:
            raise ValueError('repeat_created_event')
        next_checkpoint = checkpoint.model_copy(update={'revision':checkpoint.revision+1,
            'state':{**checkpoint.state,'completed_steps':index+1}})
        if not store.commit('report',CHECKPOINT,checkpoint.revision,next_checkpoint,[]):
            raise ValueError('checkpoint_conflict')
        checkpoint = next_checkpoint
    # Assert persisted event counts, IDs and suppressed stale sends, not only no exceptions.
    all_events = client.table('flymind_events').select('event_id,event').eq('account_id',settings.account_id).execute().data
    fixtures = [r for r in all_events if r['event']['entity_key'].startswith(str(COURSE)+':')]
    jobs = client.table('flymind_jobs').select('event_id,stage,state,result').eq('account_id',settings.account_id).execute().data
    sends = [j for j in jobs if j['stage']=='send' and j['event_id'] in {e['event_id'] for e in fixtures}]
    delivered = [j for j in sends if j['state']=='done' and j.get('result',{}).get('message_id')]
    suppressed = [j for j in sends if j.get('result',{}).get('suppressed')=='submitted']
    bands = [r['event']['reminder'] for r in fixtures if r['event']['entity_key']==f'{COURSE}:{COURSE+3}']
    late = store.load('assignment', f'{COURSE}:{COURSE+4}')
    skipped = [r['threshold'] for r in reminder_audit(late.reminders) if r['status']=='skipped_late']
    if len(fixtures)!=12 or len(delivered)!=11 or len(suppressed)!=1 or set(bands)!={'24h','12h','6h','3h','1h'} or skipped!=['24h','12h','6h']:
        raise ValueError('hosted_deadline_invariant_failed')
    return {'passed':True,'scope':'verified test group only; synthetic assignments and accelerated clock',
            'real_supabase':True,'real_telegram':True,'real_flywire':True,'production_chat_used':False,
            'thresholds':['24h','12h','6h','3h','1h'],'events':len(fixtures),'delivered_message_ids':len(delivered),
            'submitted_queued_reminders_suppressed':len(suppressed),'late_skipped_thresholds':skipped,
            'duplicate_events':0,'completed_steps':len(steps),'wall_seconds':time.perf_counter()-started}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        report=validate(os.environ)
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))
    except Exception:
        raise SystemExit('Hosted deadline verification incomplete; inspect persisted test state, never blindly resend. Private details omitted.') from None


if __name__=='__main__':
    main()
