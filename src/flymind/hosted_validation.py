"""Finite cloud smoke test. Explicit test-group guard; no legacy/production fallback."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import time

from .worker import Settings, run


def test_settings(env):
    if env.get('FLYMIND_TEST_CHAT_VALIDATION') != 'true':
        raise ValueError('explicit_test_run_required')
    settings = Settings.from_env(env)
    settings.validate()
    if (not settings.enabled or settings.delivery_mode != 'test'
            or settings.production_authorized or settings.mode != 'shadow'
            or not settings.chat_id.startswith('-')
            or settings.supabase_url != 'https://irjasmzytjeohwfpdnrl.supabase.co'
            or not env.get('TELEGRAM_CHAT_ID')
            or not env.get('FLYMIND_TEST_ACCOUNT_ID')
            or settings.account_id != env['FLYMIND_TEST_ACCOUNT_ID']):
        raise ValueError('isolated_test_account_required')
    return settings


async def validate(settings):
    started = time.perf_counter()
    first = await run(settings)
    second = await run(settings)
    report = {'scope':'real cloud Canvas/Supabase/Telegram test group, not production',
              'first':first,'second':second,'wall_seconds':time.perf_counter()-started,
              'repeat_created_events':second.get('events'),
              'repeat_send_done_unchanged':first.get('jobs',{}).get('send.done',0)==second.get('jobs',{}).get('send.done',0)}
    report['passed'] = (first.get('status')=='ok' and second.get('status')=='ok'
                        and second.get('events')==0 and report['repeat_send_done_unchanged'])
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        report=asyncio.run(validate(test_settings(os.environ)))
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))
    except Exception:
        raise SystemExit('Cloud test failed; private credentials and response details omitted.') from None
    raise SystemExit(0 if report['passed'] else 2)


if __name__=='__main__':main()
