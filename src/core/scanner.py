"""Shared Canvas scanner: bounded concurrency, complete pagination, sanitized failures."""
import asyncio
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse
import httpx


class ScanFailure(Exception):
    pass


class AsyncCanvasScanner:
    def __init__(self, token, base_url, supabase_client):
        origin = urlparse(base_url)
        if origin.scheme != 'https' or not origin.netloc or origin.username or origin.password or origin.query or origin.fragment:
            raise ValueError('invalid_canvas_origin')
        self.headers = {'Authorization': f'Bearer {token}'}
        self.base_url = base_url.rstrip('/')
        if not self.base_url.endswith('/api/v1'):
            self.base_url += '/api/v1'
        self.supabase_client = supabase_client
        self.failures = 0
        self.request_count = 0
        self.pagination_hops = 0
        self.http_statuses = Counter()
        self.rate_cost_total = 0.0
        self.rate_remaining_min = None

    async def pages(self, client, url, params=None):
        result, visited = [], set()
        origin = urlparse(self.base_url)
        for _ in range(100):
            parsed = urlparse(url)
            if parsed.scheme != origin.scheme or parsed.netloc != origin.netloc or not parsed.path.startswith(origin.path+'/') or url in visited:
                raise ScanFailure('unsafe_or_looping_pagination')
            visited.add(url)
            for attempt in range(3):
                try:
                    self.request_count += 1
                    response = await client.get(url,headers=self.headers,params=params)
                    self.http_statuses[response.status_code] += 1
                    for header in ('x-request-cost', 'x-rate-limit-remaining'):
                        try:
                            value = float(response.headers.get(header, ''))
                        except ValueError:
                            continue
                        if not math.isfinite(value) or value < 0:
                            continue
                        if header == 'x-request-cost':
                            self.rate_cost_total += value
                        else:
                            self.rate_remaining_min = value if self.rate_remaining_min is None else min(value, self.rate_remaining_min)
                except httpx.HTTPError:
                    if attempt==2:
                        raise ScanFailure('canvas_transport_failed') from None
                    await asyncio.sleep(2**attempt)
                    continue
                if response.status_code==429 or response.status_code>=500:
                    if attempt==2:
                        raise ScanFailure('canvas_unavailable')
                    try:
                        retry_after = float(response.headers.get('retry-after', 2**attempt))
                    except ValueError:
                        retry_after = 2**attempt
                    await asyncio.sleep(min(60, max(1, retry_after)))
                    continue
                if response.status_code!=200:
                    raise ScanFailure(f'canvas_request_denied_{response.status_code}')
                break
            try:
                rows = response.json()
                if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):
                    raise ValueError()
            except ValueError:
                raise ScanFailure('invalid_canvas_response') from None
            result.extend(rows)
            next_url = response.links.get('next',{}).get('url')
            if not next_url:
                return result
            self.pagination_hops += 1
            url,params = urljoin(url,next_url),None
        raise ScanFailure('canvas_page_limit')

    async def get_active_courses(self):
        async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
            rows = await self.pages(client,self.base_url+'/users/self/courses',{'enrollment_state':'active','include[]':'total_scores','per_page':50})
            return [c for c in rows if 'id' in c]

    def safe_assignment_url(self, value):
        if not isinstance(value,str) or len(value)>1000:return False
        p,origin=urlparse(value),urlparse(self.base_url)
        return p.scheme=='https' and p.netloc==origin.netloc and not p.username and not p.password

    @staticmethod
    def is_submitted(submission):
        # A numeric score alone is NOT evidence of submission (e.g. missing work graded zero).
        return bool(submission.get('submitted_at') or submission.get('workflow_state') in ('submitted','pending_review'))

    async def fetch_course_assignments(self,client,course):
        rows = await self.pages(client,self.base_url+f"/courses/{course['id']}/assignments",{'include[]':'submission','per_page':50,'order_by':'due_at','override_assignment_dates':'true'})
        score = next((e.get('computed_current_score') for e in course.get('enrollments',[]) if e.get('type')=='student'),None)
        return [{'id':a['id'],'course_id':course['id'],'course_name':course.get('name','Unknown'), 'course_score':score,
                 'name':a.get('name','Unknown'),'due_at':a.get('due_at'),'points_possible':a.get('points_possible'),
                 'html_url':a.get('html_url') if self.safe_assignment_url(a.get('html_url')) else None,
                 'score':(a.get('submission') or {}).get('score'),'has_submitted':self.is_submitted(a.get('submission') or {})}
                for a in rows if a.get('id') and a.get('published') is not False]

    async def fetch_course_files(self,client,course):
        rows = await self.pages(client,self.base_url+f"/courses/{course['id']}/files",{'sort':'created_at','order':'desc','per_page':100})
        return [{'id':f['id'],'course_id':course['id'],'course_name':course.get('name','Unknown'),
                 'display_name':f.get('display_name'),'url':f.get('url'),'created_at':f.get('created_at'),'size':f.get('size')} for f in rows if f.get('id')]

    async def fetch_all_announcements(self,client,active_courses):
        names = {f"course_{c['id']}":c.get('name','Unknown') for c in active_courses}
        if not names:
            return []
        params = [('start_date',(datetime.now(timezone.utc)-timedelta(days=30)).isoformat())]+[('context_codes[]',k) for k in names]
        rows = await self.pages(client,self.base_url+'/announcements',params)
        return [{'id':a['id'],'context_code':a.get('context_code'),'course_name':names.get(a.get('context_code'),'Unknown'),
                 'title':a.get('title'),'message':a.get('message'),'posted_at':a.get('posted_at'),'author_name':a.get('user_name')} for a in rows if a.get('id') and a.get('published') is not False]

    async def scan_all(self, active_courses):
        async with httpx.AsyncClient(timeout=30,follow_redirects=False) as client:
            n=len(active_courses)
            tasks=[self.fetch_course_assignments(client,c) for c in active_courses]+[self.fetch_course_files(client,c) for c in active_courses]+[self.fetch_all_announcements(client,active_courses)]
            # Small bounded batches avoid Canvas's parallel-request preflight penalty.
            semaphore = asyncio.Semaphore(2)
            async def bounded(task):
                async with semaphore:
                    return await task
            results=await asyncio.gather(*(bounded(task) for task in tasks),return_exceptions=True)
            self.failures=sum(isinstance(r,BaseException) for r in results)
            assignments=[x for batch in results[:n] if isinstance(batch,list) for x in batch]
            files=[x for batch in results[n:2*n] if isinstance(batch,list) for x in batch]
            announcements=results[-1] if isinstance(results[-1],list) else []
            return assignments,files,announcements
