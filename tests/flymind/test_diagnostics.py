"""Production failures must be actionable without logging academic data or credentials."""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from postgrest.exceptions import APIError

from src.flymind import worker
from src.flymind.scanner import ReliableCanvasScanner, ScanFailure
from src.flymind.store import SQLiteStore, SupabaseStore
from tests.flymind.test_events import ACCOUNT
from tests.flymind.test_pipeline import FakeDelivery, FakeRunner
from tests.flymind.test_worker import RPCClient, Scanner, settings

PRIVATE = 'SYNTHETIC_TOKEN student-name assignment-title grade=77 Authorization: private'


def records(caplog):
    return [json.loads(r.message.removeprefix('FlyMind diagnostic: '))
            for r in caplog.records if r.message.startswith('FlyMind diagnostic: ')]


@pytest.mark.parametrize('failure,stage', [
    ('courses', 'canvas.courses'),
    ('scan', 'canvas.scan'),
    ('ingest', 'snapshot.assignment'),
    ('grades', 'snapshot.grades'),
    ('verify', 'snapshot.verify'),
])
def test_worker_records_failed_stage_and_never_verifies_partial_scan(tmp_path, monkeypatch, caplog, failure, stage):
    store = SQLiteStore(tmp_path/'state.sqlite', ACCOUNT)
    calls = []

    class Client(RPCClient):
        def rpc(self, name, params):
            calls.append((name, params))
            if failure == 'verify' and name == 'flymind_sync_verified':
                raise httpx.ReadTimeout(PRIVATE)
            if failure == 'ingest' and name == 'flymind_snapshot' and params['p_kind'] == 'assignment':
                raise APIError({'code': '53300', 'message': PRIVATE, 'details': PRIVATE, 'hint': PRIVATE})
            return super().rpc(name, params)

    class Broken(Scanner):
        async def get_active_courses(self):
            if failure == 'courses':
                raise RuntimeError(PRIVATE)
            return await super().get_active_courses()

        async def scan_all(self, courses):
            if failure == 'scan':
                raise ValueError(PRIVATE)
            return await super().scan_all(courses)

    if failure == 'grades':
        def broken_grades(*args):
            raise ValueError(PRIVATE)
        monkeypatch.setattr('src.flymind.reports.save_grade_snapshot', broken_grades)
    monkeypatch.setattr(worker, 'TelegramDelivery', lambda *a: FakeDelivery())
    monkeypatch.setattr(worker, 'NeuralRunner', FakeRunner)
    result = asyncio.run(worker.run(settings(run_id='39303713768'), client_factory=lambda *a: Client(store), scanner_factory=Broken))
    assert result['errors'] == 1 and result['status'] == 'needs_attention'
    assert result['sync_status'] == 'failed' and result['last_successful_check'] is None
    assert not any(name == 'flymind_sync_verified' for name, _ in calls) or failure == 'verify'
    finish = [p for name, p in calls if name == 'flymind_heartbeat' and p['p_phase'] == 'finish'][-1]
    assert finish['p_status'] == 'degraded' and finish['p_error'].startswith(stage + ':')
    diagnostic = next(r for r in records(caplog) if r['stage'] == stage)
    assert diagnostic['run_id'] == '39303713768' and diagnostic['duration_ms'] >= 0
    assert diagnostic['error_class'] and diagnostic['category'] and diagnostic['retry_count'] == 0
    assert PRIVATE not in caplog.text
    for value in ('SYNTHETIC_TOKEN', 'student-name', 'assignment-title', 'grade=77', 'Authorization:', 'SYNTHETIC_SERVICE_SECRET'):
        assert value not in caplog.text
    store.close()


def test_rpc_error_logs_operation_and_sqlstate_without_response_or_arguments(caplog):
    error = APIError({'code': '53300', 'message': PRIVATE, 'details': PRIVATE, 'hint': PRIVATE})

    def execute():
        raise error

    client = SimpleNamespace(rpc=lambda name, params: SimpleNamespace(execute=execute))
    with pytest.raises(APIError):
        SupabaseStore(client, ACCOUNT, 123)
    record = records(caplog)[-1]
    assert record['stage'] == 'supabase.flymind_check_account'
    assert record['category'] == 'database' and record['database_code'] == '53300'
    assert record['error_class'] == 'APIError' and record['retry_count'] == 0
    assert PRIVATE not in caplog.text and ACCOUNT not in caplog.text


def test_exhausted_canvas_timeout_retains_safe_retry_evidence(monkeypatch, caplog):
    calls, delays = [], []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout(PRIVATE, request=request)

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr('src.core.scanner.asyncio.sleep', sleep)
    scanner = ReliableCanvasScanner('SYNTHETIC_TOKEN', 'https://canvas.invalid', None)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await scanner.pages(client, 'https://canvas.invalid/api/v1/courses')

    with pytest.raises(ScanFailure) as caught:
        asyncio.run(run())
    assert len(calls) == 3 and delays == [1, 2]
    assert caught.value.retry_count == 2 and caught.value.error_class == 'ReadTimeout'
    assert caught.value.category == 'timeout' and caught.value.http_status is None
    assert [r['retry_count'] for r in records(caplog)] == [0, 1]
    assert all(r['will_retry'] for r in records(caplog))
    assert 'SYNTHETIC_TOKEN' not in caplog.text and PRIVATE not in caplog.text


def test_partial_scope_failure_logs_actual_scope_and_preserves_other_results(monkeypatch, caplog):
    scanner = ReliableCanvasScanner('secret', 'https://canvas.invalid', None)

    async def assignments(client, course):
        if course['id'] == 1:
            raise TypeError(PRIVATE)
        return [{'id': 22, 'course_id': 2}]

    async def empty(*args):
        return []

    monkeypatch.setattr(scanner, 'fetch_course_assignments', assignments)
    monkeypatch.setattr(scanner, 'fetch_course_files', empty)
    monkeypatch.setattr(scanner, 'fetch_all_announcements', empty)
    rows, _, _ = asyncio.run(scanner.scan_all([{'id': 1}, {'id': 2}]))
    assert rows == [{'id': 22, 'course_id': 2}] and scanner.failures == 1
    diagnostic = records(caplog)[-1]
    assert diagnostic['stage'] == 'canvas.assignments' and diagnostic['error_class'] == 'TypeError'
    assert PRIVATE not in caplog.text


@pytest.mark.parametrize('status,category,attempts', [(401, 'authentication', 1),
                                                    (429, 'rate_limit', 3),
                                                    (503, 'dependency_unavailable', 3)])
def test_canvas_http_failure_preserves_status_and_bounded_attempts(monkeypatch, status, category, attempts):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text=PRIVATE)

    async def sleep(delay):
        pass

    monkeypatch.setattr('src.core.scanner.asyncio.sleep', sleep)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await ReliableCanvasScanner('secret', 'https://canvas.invalid', None).pages(client, 'https://canvas.invalid/api/v1/courses')

    with pytest.raises(ScanFailure) as caught:
        asyncio.run(run())
    assert len(calls) == attempts
    assert caught.value.category == category and caught.value.http_status == status
    assert caught.value.retry_count == attempts-1 and PRIVATE not in str(caught.value)


def test_postgrest_non_json_error_retains_only_http_status(caplog):
    from time import perf_counter
    from src.core.diagnostics import log_failure
    error = APIError({'code': 503, 'message': PRIVATE, 'details': PRIVATE})
    record = log_failure('supabase.flymind_snapshot', error, perf_counter(), run_id=PRIVATE)
    assert record['http_status'] == 503 and record['category'] == 'dependency_unavailable'
    assert record['run_id'] == 'local' and 'database_code' not in record
    assert PRIVATE not in caplog.text
