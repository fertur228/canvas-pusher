"""Opt-in real TEST chat check with persistent local idempotency. Never uses production chat."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
from .events import Snapshot,adapt
from .pipeline import Pipeline
from .store import SQLiteStore
from .telegram import TelegramDelivery


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state',type=Path,required=True);a=p.parse_args()
    token,chat=os.getenv('TELEGRAM_BOT_TOKEN'),os.getenv('TEST_TELEGRAM_CHAT_ID')
    if not token or not chat or chat==os.getenv('TELEGRAM_CHAT_ID'):
        raise SystemExit('A configured bot and separate TEST_TELEGRAM_CHAT_ID are required; no message sent')
    int(chat)
    store=SQLiteStore(a.state,'00000000-0000-0000-0000-000000000001')
    # The chat binding is local-only and persists across retries. Changing target needs a new state file.
    store.db.execute('CREATE TABLE IF NOT EXISTS test_target(chat TEXT PRIMARY KEY)')
    prior=store.db.execute('SELECT chat FROM test_target').fetchone()
    if prior and prior['chat']!=chat:raise SystemExit('State file is bound to another test chat')
    store.db.execute('INSERT OR IGNORE INTO test_target VALUES(?)',(chat,))
    pipeline=Pipeline(store,TelegramDelivery(token,chat),None,None,neural_enabled=False)
    pipeline.ingest('report',{'id':'controlled-test-v1','name':'SYNTHETIC test','message':'FlyMind: controlled TEST chat delivery. No academic data.','report_type':'health'},datetime(2026,10,14,tzinfo=timezone.utc))
    pipeline.drain_notifications()
    print(json.dumps({'jobs':store.counts(),'scope':'explicit TEST_TELEGRAM_CHAT_ID only'}));store.close()
if __name__=='__main__':main()
