"""Durable local test adapter and production RPC adapter with the same contract."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Protocol
import uuid
from .events import CanvasEvent, Snapshot, canonical, utc
from .sensory import encode


class Conflict(Exception):
    pass


class Store(Protocol):
    account_id: str
    def load(self, entity_type: str, key: str) -> Snapshot: ...
    def commit(self, entity_type: str, key: str, expected: int, snapshot: Snapshot, events: list[CanvasEvent]) -> bool: ...
    def claim(self, stage: str) -> dict | None: ...
    def finish(self, job: dict, outcome: str, result: dict, delay: int = 0) -> bool: ...
    def counts(self) -> dict: ...


class SQLiteStore:
    """Offline deterministic test/demo outbox. Production uses Supabase, not CI artifacts."""
    def __init__(self, path: Path, account_id: str, clock=time.time):
        self.account_id, self.clock = account_id, clock
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        os.chmod(path, 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS snapshots(account_id TEXT, kind TEXT, key TEXT, data TEXT NOT NULL, PRIMARY KEY(account_id,kind,key));
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, account_id TEXT NOT NULL, data TEXT NOT NULL, encoding TEXT);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, account_id TEXT NOT NULL,event_id TEXT NOT NULL,stage TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER DEFAULT 0, available REAL DEFAULT 0, token TEXT, lease_until REAL, result TEXT);
        CREATE TABLE IF NOT EXISTS experiments(event_id TEXT PRIMARY KEY,account_id TEXT NOT NULL,data TEXT NOT NULL);
        ''')

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def load(self, entity_type, key):
        row = self.db.execute('SELECT data FROM snapshots WHERE account_id=? AND kind=? AND key=?', (self.account_id, entity_type, key)).fetchone()
        return Snapshot.model_validate_json(row['data']) if row else Snapshot()

    def commit(self, entity_type, key, expected, snapshot, events):
        with self.transaction():
            if self.load(entity_type, key).revision != expected:
                raise Conflict('snapshot_conflict')
            if not expected <= snapshot.revision <= expected+1:
                raise ValueError('invalid_revision')
            self.db.execute('INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?)', (self.account_id, entity_type, key, snapshot.model_dump_json()))
            for event in events:
                if event.account_id != self.account_id or event.entity_key != key or event.entity_type != entity_type:
                    raise ValueError('event_scope_mismatch')
                encoding = encode(event)
                inserted = self.db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?)', (event.event_id, self.account_id, event.model_dump_json(), canonical(encoding) if encoding else None)).rowcount
                if inserted:
                    for stage in ('send', 'simulate') if encoding else ('send',):
                        self.db.execute('INSERT INTO jobs(id,account_id,event_id,stage) VALUES(?,?,?,?)', (event.event_id+':'+stage, self.account_id, event.event_id, stage))
        return True

    def claim(self, stage):
        now = self.clock()
        with self.transaction():
            self.db.execute("UPDATE jobs SET state=CASE WHEN stage='send' THEN 'ambiguous' ELSE 'pending' END, token=NULL, result=? WHERE account_id=? AND state='running' AND lease_until<?", (canonical({'error_code':'expired_lease'}), self.account_id, now))
            rows = self.db.execute("SELECT j.*,e.data AS event,e.encoding FROM jobs j JOIN events e ON e.id=j.event_id WHERE j.account_id=? AND j.stage=? AND j.state='pending' AND j.available<=?", (self.account_id, stage, now)).fetchall()
            ready = [r for r in rows if stage=='send' or self.db.execute("SELECT 1 FROM jobs WHERE id=? AND state='done'", (r['event_id']+':send',)).fetchone()]
            if not ready:
                return None
            row = sorted(ready, key=lambda r: (-json.loads(r['event'])['priority'], json.loads(r['event'])['observed_at'], r['id']))[0]
            token = str(uuid.uuid4())
            self.db.execute("UPDATE jobs SET state='running', attempts=attempts+1,token=?,lease_until=? WHERE id=?", (token, now+120, row['id']))
            experiment = self.db.execute('SELECT data FROM experiments WHERE event_id=?', (row['event_id'],)).fetchone()
            base = self.db.execute('SELECT result FROM jobs WHERE id=?', (row['event_id']+':send',)).fetchone()
            return {'id':row['id'], 'stage':stage, 'token':token, 'attempts':row['attempts']+1,
                    'event':json.loads(row['event']), 'encoding':json.loads(row['encoding']) if row['encoding'] else None,
                    'neural':json.loads(experiment['data']) if experiment else None,
                    'base_bot_id':json.loads(base['result']).get('bot_id') if base and base['result'] else None,
                    'message_id':json.loads(base['result']).get('message_id') if base and base['result'] else None}

    def finish(self, job, outcome, result, delay=0):
        if outcome not in ('done','retry','ambiguous','dead'):
            raise ValueError('invalid_outcome')
        with self.transaction():
            state = 'pending' if outcome=='retry' else outcome
            count = self.db.execute('UPDATE jobs SET state=?,result=?,available=?,token=NULL WHERE id=? AND account_id=? AND token=? AND state=\'running\'', (state, canonical(result), self.clock()+delay, job['id'],self.account_id,job['token'])).rowcount
            if not count:
                return False
            if job['stage']=='simulate' and outcome in ('done','dead'):
                self.db.execute('INSERT OR REPLACE INTO experiments VALUES(?,?,?)', (job['event']['event_id'],self.account_id,canonical(result)))
                self.db.execute("INSERT OR IGNORE INTO jobs(id,account_id,event_id,stage) VALUES(?,?,?,'edit')", (job['event']['event_id']+':edit',self.account_id,job['event']['event_id']))
            return True

    def reconcile(self, job_id, message_id=None, confirm_no_delivery=False):
        with self.transaction():
            row = self.db.execute("SELECT * FROM jobs WHERE id=? AND account_id=? AND stage='send' AND state='ambiguous'", (job_id,self.account_id)).fetchone()
            if not row or (not message_id and not confirm_no_delivery):
                raise ValueError('operator_confirmation_required')
            self.db.execute("UPDATE jobs SET state=?,result=?,available=0 WHERE id=?", ('done' if message_id else 'pending',canonical({'message_id':message_id}) if message_id else None,job_id))

    def counts(self):
        return {r['stage']+'.'+r['state']:r['n'] for r in self.db.execute('SELECT stage,state,count(*) n FROM jobs WHERE account_id=? GROUP BY stage,state', (self.account_id,))}

    def close(self):
        self.db.close()


class SupabaseStore:
    def __init__(self, client, account_id: str, chat_id: int, origin: str | None = None, *, run_id=None):
        self.client,self.account_id = client,account_id
        self.run_id = run_id
        ok = self._rpc('flymind_check_account', {'p_chat_id':chat_id,'p_origin':origin})
        if ok is not True:
            raise ValueError('account_chat_binding_invalid')

    def _rpc(self, name, values):
        from time import perf_counter
        from src.core.diagnostics import log_failure
        started = perf_counter()
        try:
            return self.client.rpc(name, {'p_account':self.account_id, **values}).execute().data
        except Exception as error:
            # RPC names are code constants; never log arguments or the response body.
            log_failure('supabase.'+name, error, started, run_id=self.run_id)
            raise

    def load(self, entity_type, key):
        data = self._rpc('flymind_snapshot', {'p_kind':entity_type,'p_key':key})
        snapshot = Snapshot.model_validate(data) if data else Snapshot()
        if data and data.get('legacy_reminder') and snapshot.state and snapshot.state.get('due_at'):
            snapshot.reminders = [utc(snapshot.state['due_at']).isoformat()+':'+data['legacy_reminder']]
        return snapshot

    def commit(self, entity_type,key,expected,snapshot,events):
        return self._rpc('flymind_commit', {'p_kind':entity_type,'p_key':key,'p_expected':expected,'p_snapshot':snapshot.model_dump(),
                                           'p_events':[{'event':e.model_dump(mode='json'),'encoding':encode(e)} for e in events]})

    def claim(self, stage):
        return self._rpc('flymind_claim', {'p_stage':stage})

    def claim_report(self, event_id):
        return self._rpc('flymind_claim_report', {'p_event':event_id})

    def finish(self, job,outcome,result,delay=0):
        return self._rpc('flymind_finish', {'p_id':job['id'],'p_token':job['token'],'p_outcome':outcome,'p_result':result,'p_delay':delay})

    def reconcile(self, job_id,message_id=None,confirm_no_delivery=False):
        return self._rpc('flymind_reconcile', {'p_id':job_id,'p_message_id':message_id,'p_confirm_no_delivery':confirm_no_delivery})

    def runtime(self, initialize=False):
        return self._rpc('flymind_runtime', {'p_initialize': initialize})

    def heartbeat(self, phase, status='running', error=None):
        return self._rpc('flymind_heartbeat', {'p_phase': phase, 'p_status': status, 'p_error': error})

    def counts(self):
        return self._rpc('flymind_counts', {})


MAX_TELEMETRY_BYTES = 4 * 1024 * 1024


def telemetry_path(account, event_id, blob):
    import re
    uuid.UUID(account)
    if not re.fullmatch(r'[a-f0-9]{64}', event_id) or not 0 < len(blob) <= MAX_TELEMETRY_BYTES:
        raise ValueError('invalid_telemetry_scope_or_size')
    return f'{account}/{event_id}/{hashlib.sha256(blob).hexdigest()}.json.gz'


class LocalTelemetryStorage:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True,exist_ok=True)
        os.chmod(root,0o700)

    def put(self, account, event_id, blob):
        name = telemetry_path(account, event_id, blob)
        path = self.root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            if path.read_bytes()!=blob:
                raise ValueError('storage_checksum_mismatch')
        else:
            with path.open('xb') as f:
                os.chmod(path,0o600)
                f.write(blob)
        return name


class SupabaseTelemetryStorage:
    BUCKET = 'flymind-private'
    def __init__(self, client):
        self.client = client

    def put(self, account,event_id,blob):
        path = telemetry_path(account, event_id, blob)
        bucket = self.client.storage.from_(self.BUCKET)
        try:
            bucket.upload(path, blob, {'content-type':'application/gzip','upsert':'false'})
        except Exception:
            # Upload may have succeeded before the response was lost. Reuse only exact bytes.
            if bucket.download(path)!=blob:
                raise ValueError('storage_upload_failed') from None
        return path
