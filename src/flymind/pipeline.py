"""Atomic ingest, independent primary delivery, then bounded neural enrichment."""
from datetime import datetime, timezone
import time
from .events import CanvasEvent, Snapshot, adapt, entity_key
from .presentation import render
from .store import Conflict, Store


class Pipeline:
    def __init__(self, store: Store, delivery, runner, storage, *, neural_enabled=True, enrichment_enabled=True, telemetry_enabled=True):
        self.store,self.delivery,self.runner,self.storage = store,delivery,runner,storage
        self.neural_enabled = neural_enabled
        self.enrichment_enabled = enrichment_enabled
        self.telemetry_enabled = telemetry_enabled
        self.deadline = time.monotonic() + 600
        self._uploaded = {}

    def ingest(self, entity_type, live, now=None, bootstrap=False):
        now = now or datetime.now(timezone.utc)
        key = entity_key(live,entity_type)
        for _ in range(3):
            old = self.store.load(entity_type,key)
            snapshot, events = adapt(self.store.account_id,entity_type,live,old,now,bootstrap=bootstrap)
            if old == snapshot:
                return 0
            try:
                committed = self.store.commit(entity_type,key,old.revision,snapshot,events)
                if committed:
                    return len(events)
            except Conflict:
                pass
        raise Conflict('snapshot_contention')

    def drain_notifications(self, stage='send', limit=25):
        if not self.delivery.ready:
            return 0  # No claims/attempts lost when credentials are missing.
        count = 0
        for _ in range(limit):
            if time.monotonic() > self.deadline:
                break
            job = self.store.claim(stage)
            if not job:
                break
            if stage == 'edit' and not self.enrichment_enabled:
                self.store.finish(job, 'done', {'suppressed': 'shadow_mode'})
                continue
            event = CanvasEvent.model_validate(job['event'])
            if stage=='edit' and not job['message_id']:
                self.store.finish(job,'dead',{'error_code':'missing_base_message'})
                continue
            text = render(event,job['neural'] if stage=='edit' else None)
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
            self.store.finish(job,outcome,{'message_id':result.message_id,'error_code':result.error_code},delay)
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
