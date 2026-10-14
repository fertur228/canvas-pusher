"""Shared Canvas scanner: bounded concurrency, complete pagination, sanitized failures."""
import asyncio
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
                    response = await client.get(url,headers=self.headers,params=params)
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
                    raise ScanFailure('canvas_request_denied')
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
            url,params = urljoin(url,next_url),None
        raise ScanFailure('canvas_page_limit')

    async def get_active_courses(self):
        async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
            rows = await self.pages(client,self.base_url+'/users/self/courses',{'enrollment_state':'active','include[]':'total_scores','per_page':50})
            return [c for c in rows if 'id' in c]

    async def fetch_course_assignments(self,client,course):
        rows = await self.pages(client,self.base_url+f"/courses/{course['id']}/assignments",{'include[]':'submission','per_page':50,'order_by':'due_at'})
        score = next((e.get('computed_current_score') for e in course.get('enrollments',[]) if e.get('type')=='student'),None)
        return [{'id':a['id'],'course_id':course['id'],'course_name':course.get('name','Unknown'), 'course_score':score,
                 'name':a.get('name','Unknown'),'due_at':a.get('due_at'),'points_possible':a.get('points_possible'),
                 'score':(a.get('submission') or {}).get('score'),'has_submitted':bool((a.get('submission') or {}).get('submitted_at'))}
                for a in rows if a.get('id')]

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
                 'title':a.get('title'),'message':a.get('message'),'posted_at':a.get('posted_at'),'author_name':a.get('user_name')} for a in rows if a.get('id')]

    async def scan_all(self, active_courses):
        async with httpx.AsyncClient(timeout=30,follow_redirects=False) as client:
            n=len(active_courses)
            tasks=[self.fetch_course_assignments(client,c) for c in active_courses]+[self.fetch_course_files(client,c) for c in active_courses]+[self.fetch_all_announcements(client,active_courses)]
            semaphore = asyncio.Semaphore(8)
            async def bounded(task):
                async with semaphore:
                    return await task
            results=await asyncio.gather(*(bounded(task) for task in tasks),return_exceptions=True)
            self.failures=sum(isinstance(r,BaseException) for r in results)
            assignments=[x for batch in results[:n] if isinstance(batch,list) for x in batch]
            files=[x for batch in results[n:2*n] if isinstance(batch,list) for x in batch]
            announcements=results[-1] if isinstance(results[-1],list) else []
            return assignments,files,announcements
