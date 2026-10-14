"""Explicit retention/recovery CLI. Dry-run is the default. No Canvas payload logging."""
import argparse
import json
import os
import re
from .store import SupabaseStore
from .worker import Settings


def cleanup(store,storage,days=30,apply=False):
    rows=store._rpc('flymind_retention',{'p_days':days,'p_apply':apply})
    orphans=store._rpc('flymind_orphans',{})
    # Only orphan candidates are safe to delete: a cached artifact may still be
    # referenced by a newer event. Detaching old references is a separate transaction.
    paths=sorted(set(orphans))
    for path in paths:
        if not re.fullmatch(re.escape(store.account_id)+r'/[a-f0-9]{64}/[a-f0-9]{64}\.json\.gz',path):
            raise ValueError('invalid_cleanup_scope')
    if apply and paths:
        for i in range(0,len(paths),100):storage.from_('flymind-private').remove(paths[i:i+100])
    return {'apply':apply,'expired_references':len(rows),'orphan_objects':len(orphans),'objects_removed':len(paths) if apply else 0}


def main():
    from dotenv import load_dotenv
    load_dotenv()
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    retention=sub.add_parser('retention');retention.add_argument('--days',type=int,default=30);retention.add_argument('--apply',action='store_true')
    retry=sub.add_parser('retry');retry.add_argument('--job',required=True)
    reconcile=sub.add_parser('reconcile');reconcile.add_argument('--job',required=True)
    evidence=reconcile.add_mutually_exclusive_group(required=True);evidence.add_argument('--message-id',type=int);evidence.add_argument('--confirmed-unsent',action='store_true')
    a=p.parse_args();s=Settings.from_env();s.validate()
    if not s.enabled:raise SystemExit('FLYMIND_ENABLED=true required')
    if a.action=='retention' and a.apply and os.getenv('FLYMIND_RETENTION_ENABLED')!='true':raise SystemExit('Explicit FLYMIND_RETENTION_ENABLED=true required for deletion')
    from supabase import create_client
    client=create_client(s.supabase_url,s.supabase_key);store=SupabaseStore(client,s.account_id,int(s.chat_id))
    try:
        if a.action=='retention':result=cleanup(store,client.storage,a.days,a.apply)
        elif a.action=='retry':result={'requeued':store._rpc('flymind_retry_dead',{'p_job':a.job})}
        else:result={'reconciled':store.reconcile(a.job,a.message_id,a.confirmed_unsent)}
        print(json.dumps(result))
    except Exception:raise SystemExit('Maintenance failed; inspect private state, no secrets logged') from None

if __name__=='__main__':main()
