import httpx
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import asyncio

logger = logging.getLogger(__name__)

class AsyncCanvasScanner:
    def __init__(self, token: str, base_url: str, supabase_client):
        self.headers = {"Authorization": f"Bearer {token}"}
        # canvasapi base url used to be https://url.com, we need /api/v1
        self.base_url = f"{base_url.rstrip('/')}/api/v1"
        self.supabase_client = supabase_client

    async def get_active_courses(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{self.base_url}/users/self/courses"
            params = {"enrollment_state": "active", "include[]": "total_scores", "per_page": 50}
            response = await client.get(url, headers=self.headers, params=params)
            if response.status_code == 200:
                courses = response.json()
                return [c for c in courses if 'id' in c]
            else:
                logger.error(f"Failed to fetch active courses: {response.text}")
            return []

    async def fetch_course_assignments(self, client: httpx.AsyncClient, course: Dict[str, Any]) -> List[Dict[str, Any]]:
        course_score = None
        for enr in course.get("enrollments", []):
            if enr.get("type") == "student":
                course_score = enr.get("computed_current_score")
                if course_score is not None:
                    break
        
        url = f"{self.base_url}/courses/{course['id']}/assignments"
        # We limit the data heavily to improve performance
        params = {"include[]": "submission", "per_page": 50, "order_by": "due_at"}
        
        try:
            response = await client.get(url, headers=self.headers, params=params)
        except Exception as e:
            logger.error(f"Failed HTTP assignment request for course {course.get('id')}: {e}")
            return []

        assignments_data = []
        if response.status_code == 200:
            for assignment in response.json():
                submission = assignment.get('submission', {})
                score = submission.get('score')
                submitted_at = submission.get('submitted_at')
                
                assignments_data.append({
                    "id": assignment.get('id'),
                    "course_id": course.get('id'),
                    "course_name": course.get('name', 'Unknown Course'),
                    "course_score": course_score,
                    "name": assignment.get('name', 'Unknown'),
                    "due_at": assignment.get('due_at'),
                    "points_possible": assignment.get('points_possible'),
                    "score": score,
                    "has_submitted": submitted_at is not None
                })
        return assignments_data

    async def fetch_course_files(self, client: httpx.AsyncClient, course: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/courses/{course['id']}/files"
        # Sort by created_at desc to only get the newest files
        params = {"sort": "created_at", "order": "desc", "per_page": 10}
        
        try:
            response = await client.get(url, headers=self.headers, params=params)
        except Exception as e:
            return []
            
        files_data = []
        if response.status_code == 200:
            for f in response.json():
                files_data.append({
                    "id": f.get('id'),
                    "course_id": course.get('id'),
                    "course_name": course.get('name', 'Unknown Course'),
                    "display_name": f.get('display_name', 'Unknown'),
                    "url": f.get('url'),
                    "created_at": f.get('created_at'),
                    "size": f.get('size')
                })
        return files_data

    async def fetch_all_announcements(self, client: httpx.AsyncClient, active_courses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        course_map = {f"course_{c['id']}": c.get('name', 'Unknown Course') for c in active_courses}
        course_ids = list(course_map.keys())
        
        if not course_ids:
            return []
            
        url = f"{self.base_url}/announcements"
        start_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        
        announcements_data = []
        params = [("start_date", start_date)]
        for cid in course_ids:
            params.append(("context_codes[]", cid))
            
        try:
            response = await client.get(url, headers=self.headers, params=params)
        except Exception as e:
            return []
            
        if response.status_code == 200:
            for ann in response.json():
                announcements_data.append({
                    "id": ann.get('id'),
                    "context_code": ann.get('context_code'),
                    "course_name": course_map.get(ann.get('context_code'), 'Unknown Course'),
                    "title": ann.get('title', 'Unknown'),
                    "message": ann.get('message', ''),
                    "posted_at": ann.get('posted_at'),
                    "author_name": ann.get('user_name', 'System')
                })
        return announcements_data
        
    async def scan_all(self, active_courses: List[Dict[str, Any]]) -> tuple:
        """Executes all API requests completely in parallel returning aggregated chunks"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            assignments_tasks = [self.fetch_course_assignments(client, c) for c in active_courses]
            files_tasks = [self.fetch_course_files(client, c) for c in active_courses]
            announcements_task = self.fetch_all_announcements(client, active_courses)
            
            results = await asyncio.gather(*assignments_tasks, *files_tasks, announcements_task)
            
            num_courses = len(active_courses)
            assignments_results = results[:num_courses]
            files_results = results[num_courses:2*num_courses]
            announcements_result = results[-1]
            
            all_assignments = []
            for a in assignments_results:
                all_assignments.extend(a)
                
            all_files = []
            for f in files_results:
                all_files.extend(f)
                
            return all_assignments, all_files, announcements_result
