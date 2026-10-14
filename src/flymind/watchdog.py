"""Independent scheduled health reader; no Telegram/outbox dependency or private logging."""
from datetime import datetime,timezone
import json
from .events import utc


def classify(health,now=None):
    now=now or datetime.now(timezone.utc)
    if not health or not health.get('last_attempt'):return 'failed'
    age=(now-utc(health['last_attempt'])).total_seconds()
    if age>90*60:return 'failed'
    if age>30*60:return 'delayed'
    if health.get('status')!='healthy':return 'degraded'
    if any(count for key,count in health.get('queue',{}).items() if key.endswith(('.dead','.ambiguous'))):return 'degraded'
    return 'healthy'


def main():
    from .worker import Settings
    from supabase import create_client
    s=Settings.from_env()
    if not s.enabled:print(json.dumps({'status':'disabled'}));return
    try:
        s.validate();client=create_client(s.supabase_url,s.supabase_key)
        rows=client.table('flymind_health').select('*').eq('account_id',s.account_id).limit(1).execute().data
        state=classify(rows[0] if rows else None)
    except Exception:state='failed'
    print(json.dumps({'status':state,'private_details_omitted':True}))
    raise SystemExit(0 if state=='healthy' else 2)
if __name__=='__main__':main()
