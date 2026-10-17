"""Controlled HTTP updates to the deployed webhook, with real test-chat delivery.

This is NOT evidence of pressing buttons in the Telegram client. It exercises
real Supabase reads, Telegram sends/edits and durable bot-scoped update claims.
Private fixture IDs persist, so repeating this probe never blindly resends them.
"""
import argparse
import json
import logging
import os
from pathlib import Path
import secrets

import httpx
from dotenv import dotenv_values
from supabase import create_client
from src.flymind.bot_setup import BotAPI

ROOT = Path(__file__).resolve().parents[1]


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--send-test-messages', action='store_true')
    args = parser.parse_args()
    if not args.send_test_messages:
        raise ValueError('explicit_test_send_required')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    local = dotenv_values(ROOT / '.env.flymind.local')
    hosted = dotenv_values(ROOT / '.env.flymind.hosted')
    owner = dotenv_values(ROOT / '.env.flymind.identity')
    test = dotenv_values(ROOT / '.env.flymind.test')
    account = dotenv_values(ROOT / '.env.flymind.account-test')['FLYMIND_ACCOUNT_ID']
    if (hosted['SUPABASE_URL'] != 'https://irjasmzytjeohwfpdnrl.supabase.co'
            or test.get('TELEGRAM_CHAT_ID') != test.get('TEST_TELEGRAM_CHAT_ID')
            or test['TELEGRAM_CHAT_ID'] == owner['TELEGRAM_CHAT_ID']
            or test['TELEGRAM_USER_ID'] != owner['TELEGRAM_USER_ID']):
        raise ValueError('wrong_test_destination')
    bot = BotAPI(local['TELEGRAM_BOT_TOKEN'])
    if str(bot.call('getMe')['id']) != test['TELEGRAM_BOT_ID']:
        raise ValueError('wrong_bot')
    db = create_client(hosted['SUPABASE_URL'], hosted['SUPABASE_SERVICE_KEY'])
    fixture_path = ROOT / 'secret-flymind-release/webhook-probe.json'
    if not fixture_path.exists():
        # Telegram update IDs are far below this reserved, safe-integer test range.
        fixture = {'first_update': 2**50 + secrets.randbelow(2**40)}
        fixture_path.write_text(json.dumps(fixture)); fixture_path.chmod(0o600)
    fixture = json.loads(fixture_path.read_text())
    url = hosted['SUPABASE_URL'] + '/functions/v1/flymind-telegram-webhook'
    client = httpx.Client(timeout=50, follow_redirects=False)
    headers = {'X-Telegram-Bot-Api-Secret-Token': local['TELEGRAM_WEBHOOK_SECRET']}
    def body(index, command):
        return {'update_id': fixture['first_update'] + index,
                'message': {'chat': {'id': int(test['TELEGRAM_CHAT_ID'])},
                            'from': {'id': int(test['TELEGRAM_USER_ID'])}, 'text': command}}
    results = {}
    for index, command in enumerate(['/start', '/menu', '/deadlines', '/stats', '/status', '/brain', '/check']):
        payload = body(index, command)
        response = client.post(url, headers=headers, json=payload)
        assert response.status_code == 200
        row = db.table('flymind_webhook_updates').select('status').eq('bot_id', test['TELEGRAM_BOT_ID']).eq('update_id', payload['update_id']).single().execute().data
        assert row['status'] == ('claimed' if command == '/check' else 'done')
        again = client.post(url, headers=headers, json=payload)
        assert again.status_code == 200 and again.text == 'Already handled or account disabled'
        results[command] = {'status': row['status'], 'repeat_suppressed': True}
    # Actual editMessageText on a separately created, clearly labeled test message.
    if 'message_id' not in fixture:
        fixture['message_id'] = bot.call('sendMessage', {'chat_id': test['TELEGRAM_CHAT_ID'], 'text': 'ТЕСТ FLYMIND: проверка переключения сохранённых дедлайнов.'})['message_id']
        fixture_path.write_text(json.dumps(fixture)); fixture_path.chmod(0o600)
    for index, view in enumerate(['upcoming', 'overdue', 'today', 'week', 'month', 'all', 'undated'], start=20):
        payload = {'update_id': fixture['first_update']+index,
                   'callback_query': {'id': 'synthetic-callback-'+str(index), 'data': f'deadlines:{view}:0',
                                      'from': {'id': int(test['TELEGRAM_USER_ID'])},
                                      'message': {'chat': {'id': int(test['TELEGRAM_CHAT_ID'])}, 'message_id': fixture['message_id']}}}
        response = client.post(url, headers=headers, json=payload)
        assert response.status_code == 200
        row = db.table('flymind_webhook_updates').select('status').eq('bot_id', test['TELEGRAM_BOT_ID']).eq('update_id', payload['update_id']).single().execute().data
        assert row['status'] == 'done'
        results['deadlines:'+view] = 'real_edit_completed'
    invalid = body(100, '/deadlines')
    assert client.post(url, json=invalid).status_code == 403
    assert client.post(url, headers={'X-Telegram-Bot-Api-Secret-Token':'invalid-test'}, json=invalid).status_code == 403
    invalid['message']['from']['id'] = 1
    assert client.post(url, headers=headers, json=invalid).status_code == 403
    invalid['message']['from']['id'] = int(test['TELEGRAM_USER_ID'])
    invalid['message']['chat']['id'] = 1
    assert client.post(url, headers=headers, json=invalid).status_code == 403
    # Disabled manual gate must not create a fake success or dispatch anything.
    requests = db.table('flymind_manual_requests').select('id').eq('account_id', account).execute().data
    assert not requests
    report = {'transport':'controlled HTTP updates, real deployed function and Telegram Bot API',
              'telegram_client_buttons_tested':False, 'primary_chat_used':False,
              'commands':results, 'negative_identity_and_secret_checks':4,
              'manual_dispatch_disabled_accurately':True}
    (ROOT / 'docs/hosted-webhook-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':
    try:
        run()
    except Exception:
        raise SystemExit('Hosted webhook probe incomplete; inspect private claim state before retry. No response bodies or credentials logged.') from None
