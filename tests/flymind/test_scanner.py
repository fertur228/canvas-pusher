import asyncio
import httpx
import pytest
from src.flymind.scanner import ReliableCanvasScanner,ScanFailure


def test_paginated_assignments_include_later_pages_and_null_submission():
    requests=[]
    def handler(request):
        requests.append(request)
        if len(requests)==1:
            return httpx.Response(200,json=[{'id':1,'name':'SYNTHETIC','submission':None}],headers={'link':'<https://canvas.invalid/api/v1/courses/2/assignments?page=2>; rel="next"'})
        return httpx.Response(200,json=[{'id':3,'submission':{'score':0,'submitted_at':'2026-10-14T00:00:00Z'}}])
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ReliableCanvasScanner('secret','https://canvas.invalid',None).fetch_course_assignments(client,{'id':2})
    rows=asyncio.run(run())
    assert [r['id'] for r in rows]==[1,3] and rows[1]['score']==0 and rows[1]['has_submitted']
    assert requests[1].headers['Authorization']=='Bearer secret'


def test_cross_origin_pagination_does_not_send_canvas_token():
    requests=[]
    def handler(request):
        requests.append(request)
        return httpx.Response(200,json=[],headers={'link':'<https://evil.invalid/api/v1/data>; rel="next"'})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await ReliableCanvasScanner('secret','https://canvas.invalid',None).pages(client,'https://canvas.invalid/api/v1/courses')
    with pytest.raises(ScanFailure):asyncio.run(run())
    assert len(requests)==1


def test_unauthorized_scan_fails_instead_of_becoming_an_empty_snapshot():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(401,json={'error':'private'}))) as client:
            await ReliableCanvasScanner('secret','https://canvas.invalid',None).pages(client,'https://canvas.invalid/api/v1/courses')
    with pytest.raises(ScanFailure,match='canvas_request_denied'):asyncio.run(run())


def test_one_failed_course_does_not_suppress_other_course_events(monkeypatch):
    scanner=ReliableCanvasScanner('secret','https://canvas.invalid',None)
    async def assignments(client,c):
        if c['id']==1:raise ScanFailure('unavailable')
        return [{'id':22,'course_id':2}]
    async def files(*a):return []
    async def announcements(*a):return []
    monkeypatch.setattr(scanner,'fetch_course_assignments',assignments)
    monkeypatch.setattr(scanner,'fetch_course_files',files)
    monkeypatch.setattr(scanner,'fetch_all_announcements',announcements)
    rows,_,_=asyncio.run(scanner.scan_all([{'id':1},{'id':2}]))
    assert rows==[{'id':22,'course_id':2}] and scanner.failures==1


def test_file_pagination_is_complete():
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(200,json=[{'id':len(calls)}],headers={'link':'<https://canvas.invalid/api/v1/courses/2/files?page=2>; rel="next"'} if len(calls)==1 else {})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ReliableCanvasScanner('secret','https://canvas.invalid',None).fetch_course_files(client,{'id':2})
    assert [x['id'] for x in asyncio.run(run())]==[1,2]


def test_rate_limit_retry_after_is_bounded_and_honored(monkeypatch):
    delays=[];calls=[]
    async def sleep(delay):delays.append(delay)
    monkeypatch.setattr('src.core.scanner.asyncio.sleep',sleep)
    def handler(request):
        calls.append(request)
        return httpx.Response(429,headers={'retry-after':'4'}) if len(calls)==1 else httpx.Response(200,json=[])
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ReliableCanvasScanner('secret','https://canvas.invalid',None).pages(client,'https://canvas.invalid/api/v1/courses')
    assert asyncio.run(run())==[] and delays==[4]


def test_rate_budget_headers_are_sanitized_finite_aggregates():
    scanner=ReliableCanvasScanner('secret','https://canvas.invalid',None)
    async def run():
        for headers in ({'x-request-cost':'2.5','x-rate-limit-remaining':'600'},
                        {'x-request-cost':'3','x-rate-limit-remaining':'590'},
                        {'x-request-cost':'nan','x-rate-limit-remaining':'-1'},
                        {'x-request-cost':'invalid','x-rate-limit-remaining':'inf'}):
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(200,json=[],headers=headers))) as client:
                await scanner.pages(client,'https://canvas.invalid/api/v1/courses')
    asyncio.run(run())
    assert scanner.rate_cost_total==5.5 and scanner.rate_remaining_min==590
