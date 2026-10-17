"""Atomic ingest, independent primary delivery, then bounded neural enrichment."""
from datetime import datetime, timezone
import time
from collections import Counter
from .events import CanvasEvent, EventKind, adapt, entity_key, reminder_band, reminder_identity, utc
from .presentation import render
from .store import Conflict, Store


class Pipeline:
    def __init__(self, store: Store, delivery, runner, storage, *, neural_enabled=True, enrichment_enabled=True, telemetry_enabled=True, now=None):
        self.store,self.delivery,self.runner,self.storage = store,delivery,runner,storage
        self.neural_enabled = neural_enabled
        self.enrichment_enabled = enrichment_enabled
        self.telemetry_enabled = telemetry_enabled
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.deadline = time.monotonic() + 600
        self._uploaded = {}
        self.event_counts = Counter()

    def ingest(self, entity_type, live, now=None, bootstrap=False):
        now = now or self.now()
        key = entity_key(live,entity_type)
        for _ in range(3):
            old = self.store.load(entity_type,key)
            snapshot, events = adapt(self.store.account_id,entity_type,live,old,now,bootstrap=bootstrap)
            if old == snapshot:
                return 0
            try:
                committed = self.store.commit(entity_type,key,old.revision,snapshot,events)
                if committed:
                    self.event_counts.update(e.kind.value for e in events)
                    return len(events)
            except Conflict:
                pass
        raise Conflict('snapshot_contention')

    def obsolete_reminder(self, event):
        if event.kind != EventKind.REMINDER:
            return None
        snapshot = self.store.load(event.entity_type, event.entity_key)
        state = snapshot.state
        if not state:
            return 'snapshot_missing'
        if state.get('has_submitted'):
            return 'submitted'
        due = state.get('due_at')
        if not due or utc(due) != utc(event.payload['due_at']):
            return 'deadline_changed'
        if reminder_identity(event.account_id, event.entity_key, utc(due).isoformat(),
                             event.reminder, snapshot.reminders) != event.event_id:
            return 'deadline_version_changed'
        if reminder_band(state, self.now()) != event.reminder:
            return 'expired_or_superseded_threshold'
        return None

    def drain_notifications(self, stage='send', limit=None, only_report=None):
        if not self.delivery.ready:
            return 0  # No claims/attempts lost when credentials are missing.
        count = 0
        # Drain primary discoveries in the discovering scan; a small edit budget
        # must not postpone assignment alerts. Wall-time/backoff still bound work.
        limit = (1000 if stage == 'send' else 25) if limit is None else limit
        for _ in range(limit):
            if time.monotonic() > self.deadline:
                break
            job = self.store.claim_report(only_report) if only_report else self.store.claim(stage)
            if not job:
                break
            if stage == 'edit' and not self.enrichment_enabled:
                self.store.finish(job, 'done', {'suppressed': 'shadow_mode'})
                continue
            event = CanvasEvent.model_validate(job['event'])
            try:
                obsolete = self.obsolete_reminder(event)
            except Exception:
                # No Telegram request was attempted. A DB outage must not send
                # a reminder whose submission/deadline status we cannot verify.
                self.store.finish(job, 'dead' if job['attempts'] >= 10 else 'retry',
                                  {'error_code': 'reminder_verification_failed'}, 60)
                continue
            if obsolete:
                self.store.finish(job, 'done', {'suppressed': obsolete})
                continue
            if stage=='edit' and not job['message_id']:
                if event.kind == EventKind.REMINDER and (job.get('neural') or {}).get('status') == 'suppressed':
                    self.store.finish(job, 'done', {'suppressed': 'primary_reminder_not_delivered'})
                    continue
                self.store.finish(job,'dead',{'error_code':'missing_base_message'})
                continue
            if stage=='edit' and getattr(self.delivery,'bot_id',None) and str(job.get('base_bot_id') or '')!=self.delivery.bot_id:
                self.store.finish(job,'dead',{'error_code':'message_belongs_to_another_or_unknown_bot'})
                continue
            text = render(event,job['neural'] if stage=='edit' else None, now=self.now())
            try:
                result = self.delivery.deliver(text,job['message_id'] if stage=='edit' else None)
            except Exception:
                self.store.finish(job,'retry' if stage=='edit' else 'ambiguous',{'error_code':'delivery_uncertain'},60)
                count += 1
                continue
            outcome = result.outcome
            if outcome=='retry' and job['attempts']>=10:
                outcome='dead'
            delay = max(result.retry_after,min(3600,30*2**min(job['attempts']-1,7)))
            # If this acknowledgement fails after Telegram accepted a send, the lease
            # will become ambiguous, never be automatically resent. Edits are safe to retry.
            self.store.finish(job,outcome,{'message_id':result.message_id,'bot_id':getattr(self.delivery,'bot_id',None),'error_code':result.error_code},delay)
            count += 1
        return count

    def drain_neural(self, limit=5):
        count = 0
        for _ in range(limit):
            if time.monotonic() > self.deadline:
                break
            job = self.store.claim('simulate')
            if not job:
                break
            if job['event']['kind'] == EventKind.REMINDER and not job['message_id']:
                self.store.finish(job, 'done', {'status': 'suppressed', 'reason': 'primary_reminder_not_delivered',
                                               'biological_response_validated': False})
                continue
            if not self.neural_enabled:
                self.store.finish(job,'dead',{'status':'disabled','biological_response_validated':False})
                continue
            try:
                result,blob = self.runner.run(job['encoding'])
                if self.telemetry_enabled:
                    import hashlib
                    digest=hashlib.sha256(blob).hexdigest()
                    path=self._uploaded.get(digest)
                    if path is None:
                        path=self.storage.put(self.store.account_id,job['event']['event_id'],blob)
                        self._uploaded[digest]=path
                    result['telemetry_path']=path
                    result['telemetry_reuse_scope']='Same fixed profile within this worker; original recorded timestamp retained'
                else:
                    result['telemetry_unavailable'] = 'disabled_by_configuration'
                self.store.finish(job,'done',result)
            except Exception:
                # No raw exception text, Canvas payload or credentials in logs/results.
                terminal = job['attempts']>=3
                self.store.finish(job,'dead' if terminal else 'retry',{'status':'failed','error_code':'neural_or_storage_failed',
                                                                     'biological_response_validated':False},60*job['attempts'])
            count += 1
        return count

    def run_pending(self, max_neural=5):
        self.drain_notifications('send')
        self.drain_neural(max_neural)
        self.drain_notifications('edit')
        return self.store.counts()
