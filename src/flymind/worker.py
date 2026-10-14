"""Finite scheduled worker. No live writes happen unless the feature flag is enabled."""
import argparse
import asyncio
from dataclasses import dataclass
import logging
import os
from urllib.parse import urlparse
import uuid
from .neural import NeuralRunner
from .pipeline import Pipeline
from .scanner import ReliableCanvasScanner
from .store import SupabaseStore, SupabaseTelemetryStorage
from .telegram import TelegramDelivery

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    enabled: bool = False
    neural_enabled: bool = True
    account_id: str = ''
    chat_id: str = ''
    supabase_url: str = ''
    supabase_key: str = ''
    canvas_url: str = ''
    canvas_token: str = ''
    telegram_token: str = ''
    max_neural: int = 5
    auto_report: bool = False
    run_id: str = ''
    mode: str = 'shadow'
    delivery_mode: str = 'disabled'
    test_chat_id: str = ''
    production_authorized: bool = False
    telemetry_enabled: bool = True

    @classmethod
    def from_env(cls, env=None):
        e = os.environ if env is None else env
        if e.get('FLYMIND_ENABLED','').lower()!='true':
            return cls()
        if e.get('DELIVERY_MODE')=='test' and e.get('TEST_TELEGRAM_CHAT_ID') and e.get('TEST_TELEGRAM_CHAT_ID')==e.get('TELEGRAM_CHAT_ID'):
            raise ValueError('test_chat_must_differ_from_production')
        return cls(enabled=e.get('FLYMIND_ENABLED','').lower()=='true',neural_enabled=e.get('FLYMIND_NEURAL_ENABLED','true').lower()=='true',
                   account_id=e.get('FLYMIND_ACCOUNT_ID',''),chat_id=e.get('TEST_TELEGRAM_CHAT_ID','') if e.get('DELIVERY_MODE','disabled')=='test' else e.get('TELEGRAM_CHAT_ID',''),
                   supabase_url=e.get('SUPABASE_URL',''),supabase_key=e.get('SUPABASE_SERVICE_KEY','') or e.get('SUPABASE_KEY',''),
                   canvas_url=e.get('CANVAS_API_URL',''),canvas_token=e.get('CANVAS_API_KEY',''),telegram_token=e.get('TELEGRAM_BOT_TOKEN',''),
                   max_neural=min(20,max(0,int(e.get('FLYMIND_MAX_NEURAL','5')))),
                   auto_report=e.get('IS_AUTO_REPORT','').lower()=='true',run_id=e.get('GITHUB_RUN_ID',''),
                   mode=e.get('FLYMIND_MODE','shadow'),delivery_mode=e.get('DELIVERY_MODE','disabled'),
                   test_chat_id=e.get('TEST_TELEGRAM_CHAT_ID',''),
                   production_authorized=e.get('FLYMIND_PRODUCTION_AUTHORIZED','').lower()=='true',
                   telemetry_enabled=e.get('NEURAL_TELEMETRY_ENABLED','true').lower()=='true')

    def validate(self):
        if not self.enabled:
            return
        if self.mode not in ('shadow','enrich') or self.delivery_mode not in ('disabled','test','production'):
            raise ValueError('invalid_activation_mode')
        if self.delivery_mode == 'test' and (not self.test_chat_id or self.chat_id != self.test_chat_id):
            raise ValueError('explicit_test_chat_required')
        if self.delivery_mode == 'production' and not self.production_authorized:
            raise ValueError('production_activation_gate_required')
        missing = [k for k in ('account_id','chat_id','supabase_url','supabase_key') if not getattr(self,k)]
        if missing:
            raise ValueError('missing_configuration:'+','.join(missing))
        if self.auto_report and not self.run_id:
            raise ValueError('idempotent_report_requires_GITHUB_RUN_ID')
        uuid.UUID(self.account_id)
        int(self.chat_id)
        for value in (self.supabase_url,self.canvas_url):
            if value:
                p=urlparse(value)
                if p.scheme!='https' or not p.netloc or p.username or p.password:
                    raise ValueError('invalid_service_origin')


async def run(settings: Settings, *, client_factory=None, scanner_factory=ReliableCanvasScanner, bootstrap=False):
    if not settings.enabled:
        return {'status':'disabled'}
    settings.validate()
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    if client_factory is None:
        from supabase import create_client
        client_factory = create_client
    client = client_factory(settings.supabase_url,settings.supabase_key)
    parsed=urlparse(settings.canvas_url)
    origin=f'{parsed.scheme}://{parsed.netloc}' if settings.canvas_url else None
    store = SupabaseStore(client,str(uuid.UUID(settings.account_id)),int(settings.chat_id),origin)
    store.heartbeat('attempt')
    if not bootstrap and not store.runtime()['initialized']:
        store.heartbeat('finish','degraded','bootstrap_required')
        return {'status':'bootstrap_required','jobs':store.counts()}
    delivery = TelegramDelivery(settings.telegram_token if settings.delivery_mode!='disabled' else '',settings.chat_id)
    pipeline = Pipeline(store,delivery,NeuralRunner(),SupabaseTelemetryStorage(client),neural_enabled=settings.neural_enabled, enrichment_enabled=settings.mode=='enrich', telemetry_enabled=settings.telemetry_enabled)
    # Recover existing durable notifications even if Canvas is currently unavailable.
    if not bootstrap:
        pipeline.drain_notifications('send',limit=25)
    if not settings.canvas_url or not settings.canvas_token:
        pipeline.drain_notifications('edit',limit=25)
        store.heartbeat('finish','failed','missing_canvas_credentials')
        return {'status':'missing_canvas_credentials','jobs':store.counts()}
    scanner = scanner_factory(settings.canvas_token,settings.canvas_url,client)
    errors,events = 0,0
    courses = []
    try:
        courses = await scanner.get_active_courses()
        assignments,files,announcements = await scanner.scan_all(courses)
        errors += getattr(scanner,'failures',0)
        if not errors:
            store.heartbeat('canvas')
        for kind,rows in (('assignment',assignments),('file',files),('announcement',announcements)):
            for row in rows:
                try:
                    events += pipeline.ingest(kind,row,bootstrap=bootstrap)
                except Exception:
                    errors += 1
        # The existing webhook's GPA view keeps its source; no legacy notification processing here.
        grades = []
        for course in courses:
            score=next((e.get('computed_current_score') for e in course.get('enrollments',[]) if e.get('type')=='student'),None)
            grades.append({'user_id':int(settings.chat_id),'course_id':course['id'],'course_name':course.get('name','Unknown'),'current_score':score})
        if grades:
            try:
                client.table('course_grades').upsert(grades).execute()
            except Exception:
                errors += 1
    except Exception:
        errors += 1  # Sanitized: no API URL/token/title/grade in logs.
    if bootstrap:
        if not errors:
            store.runtime(initialize=True)
        store.heartbeat('finish','bootstrapped' if not errors else 'degraded','scan_or_persistence_failed' if errors else None)
        return {'status':'bootstrapped' if not errors else 'needs_attention','events':events,'errors':errors,'jobs':store.counts()}
    from .reports import queue_reports
    if not errors:
        queue_reports(pipeline,courses,auto_report=settings.auto_report,run_id=settings.run_id)
    jobs = pipeline.run_pending(settings.max_neural)
    delivery_problem = any(n for k,n in jobs.items() if k.startswith(('send.','edit.')) and not k.endswith('.done'))
    neural_problem = settings.neural_enabled and any(n for k,n in jobs.items() if k.startswith('simulate.') and k.endswith(('dead','pending')))
    healthy = not errors and delivery.ready and not delivery_problem and not neural_problem
    store.heartbeat('finish','healthy' if healthy else 'degraded',None if healthy else 'scan_delivery_or_neural_pending')
    return {'status':'ok' if healthy else 'needs_attention','events':events,'errors':errors,'jobs':jobs}


async def run_environment():
    try:
        result=await run(Settings.from_env())
    except Exception:
        logger.error('FlyMind worker failed; configuration/storage unavailable. Secrets and Canvas payload omitted.')
        return 2
    logger.info('FlyMind worker: %s',result)  # Summary contains only counts/status, no private payloads.
    return 0 if result['status'] in ('ok','disabled','bootstrapped') else 2


def main():
    from dotenv import load_dotenv
    load_dotenv()  # Local CLI only; explicit env values retain precedence. Never print them.
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bootstrap',action='store_true',help='Operator-only silent baseline of current objects before activation')
    args=p.parse_args()
    settings=Settings.from_env()
    if args.bootstrap and not settings.enabled:
        raise SystemExit('Bootstrap requires explicit FLYMIND_ENABLED=true and an enabled account')
    try:
        result=asyncio.run(run(settings,bootstrap=args.bootstrap))
        print(__import__('json').dumps(result,sort_keys=True))
        raise SystemExit(0 if result['status'] in ('ok','disabled','bootstrapped') else 2)
    except Exception:
        raise SystemExit('FlyMind worker failed; inspect configuration/storage without logging secrets') from None


if __name__=='__main__':
    main()
