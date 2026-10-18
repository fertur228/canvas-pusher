"""Explicit test-chat exercise of real Supabase, Telegram, Brian2 and private Storage.

Uses ignored local credential/identity files. Never sends to the primary chat.
Synthetic fixture identity is stable so interrupted/repeated runs do not resend it.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import time

from dotenv import dotenv_values
from supabase import create_client
from src.flymind.bot_setup import BotAPI
from src.flymind.neural import NeuralRunner
from src.flymind.pipeline import Pipeline
from src.flymind.store import SupabaseStore, SupabaseTelemetryStorage
from src.flymind.telegram import TelegramDelivery

ROOT = Path(__file__).resolve().parents[1]
PROJECT_URL = 'https://irjasmzytjeohwfpdnrl.supabase.co'
FIXTURE_ID = 999999999001
FIXTURE_KEY = f'{FIXTURE_ID}:{FIXTURE_ID}'


def run():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--send-test-messages', action='store_true')
    args = p.parse_args()
    if not args.send_test_messages:
        raise ValueError('explicit_test_send_required')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    local = dotenv_values(ROOT / '.env.flymind.local')
    hosted = dotenv_values(ROOT / '.env.flymind.hosted')
    owner = dotenv_values(ROOT / '.env.flymind.identity')
    test = dotenv_values(ROOT / '.env.flymind.test')
    account = dotenv_values(ROOT / '.env.flymind.account-test')['FLYMIND_ACCOUNT_ID']
    if (hosted.get('SUPABASE_URL') != PROJECT_URL
            or test.get('TEST_TELEGRAM_CHAT_ID') != test.get('TELEGRAM_CHAT_ID')
            or not test.get('TELEGRAM_CHAT_ID')
            or test['TELEGRAM_CHAT_ID'] == owner.get('TELEGRAM_CHAT_ID')
            or test.get('TELEGRAM_USER_ID') != owner.get('TELEGRAM_USER_ID')):
        raise ValueError('test_destination_not_verified')
    me = BotAPI(local['TELEGRAM_BOT_TOKEN']).call('getMe')
    if str(me['id']) != test.get('TELEGRAM_BOT_ID') or str(me['id']) != owner.get('TELEGRAM_BOT_ID'):
        raise ValueError('bot_identity_mismatch')
    client = create_client(hosted['SUPABASE_URL'], hosted['SUPABASE_SERVICE_KEY'])
    store = SupabaseStore(client, account, int(test['TELEGRAM_CHAT_ID']), 'https://canvas.narxoz.kz')
    if not store._rpc('flymind_check_bot', {'p_bot': me['id']}):
        raise ValueError('database_bot_binding_mismatch')
    pipeline = Pipeline(store, TelegramDelivery(local['TELEGRAM_BOT_TOKEN'], test['TELEGRAM_CHAT_ID']),
                        NeuralRunner(), SupabaseTelemetryStorage(client), enrichment_enabled=False)
    fixture = {'id': FIXTURE_ID, 'course_id': FIXTURE_ID,
               'course_name': 'СИНТЕТИЧЕСКИЙ ТЕСТ FLYMIND — не реальный курс',
               'name': 'СИНТЕТИЧЕСКИЙ ТЕСТ доставки и FlyWire — не задание университета',
               'due_at': None, 'points_possible': 100, 'score': None, 'has_submitted': False}
    started = time.perf_counter()
    evidence = {'synthetic_canvas_fixture': True, 'real_supabase': True, 'real_telegram_test_chat': True,
                'real_flywire_simulation': True, 'production_chat_used': False, 'profiles': []}

    def drain_and_verify():
        pipeline.drain_notifications('send')
        sends = client.table('flymind_jobs').select('state,result').eq('account_id', account).eq('stage', 'send').execute().data
        if any(j['state'] != 'done' or not j.get('result', {}).get('message_id') for j in sends):
            raise ValueError('delivery_requires_reconciliation_do_not_resend')
        pipeline.drain_neural(2)
        experiments = client.table('flymind_experiments').select('event_id,metadata').eq('account_id', account).execute().data
        if not experiments or any(e['metadata'].get('status') != 'complete' for e in experiments):
            raise ValueError('neural_or_storage_not_complete')
        for e in experiments:
            m = e['metadata']
            blob = client.storage.from_('flymind-private').download(m['telemetry_path'])
            if hashlib.sha256(blob).hexdigest() != m['telemetry_sha256']:
                raise ValueError('private_telemetry_hash_mismatch')
        # Only this separately verified test group gets the tested enrichment edit.
        # Initial notifications have already been delivered independently above.
        pipeline.enrichment_enabled = True
        pipeline.drain_notifications('edit')
        pipeline.enrichment_enabled = False
        return experiments

    if store.load('assignment', FIXTURE_KEY).state is None:
        pipeline.ingest('assignment', fixture, datetime.now(timezone.utc))
    drain_and_verify()
    if store.load('assignment', FIXTURE_KEY).state.get('score') is None:
        pipeline.ingest('assignment', fixture | {'score': 50}, datetime.now(timezone.utc))
    experiments = drain_and_verify()
    before = store.counts()
    if pipeline.ingest('assignment', fixture | {'score': 50}, datetime.now(timezone.utc)) != 0:
        raise ValueError('duplicate_scan_created_event')
    if pipeline.run_pending(2) != before or any(not k.endswith('.done') for k in before):
        raise ValueError('repeat_changed_queue_or_unfinished_jobs')
    for e in experiments:
        m = e['metadata']
        evidence['profiles'].append({'case': m['encoding']['case'], 'readout': m['readout'],
                                     'measurements': m['measurements'], 'telemetry_sha256': m['telemetry_sha256']})
    evidence.update(jobs=before, duplicate_scan_new_events=0,
                    real_message_ids_persisted=True, private_telemetry_hashes_match=True,
                    test_enrichment_edits_verified=True, wall_seconds=time.perf_counter()-started)
    (ROOT / 'docs/hosted-neural-test.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == '__main__':
    try:
        run()
    except Exception:
        raise SystemExit('Hosted test incomplete; inspect private state before retrying. No credentials or response bodies logged.') from None
