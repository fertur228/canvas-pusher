from typing import List, Dict, Any

class CanvasScanner:
    def __init__(self, canvas_client, supabase_client):
        """
        Initializes the scanner with a Canvas API client and Supabase client.
        """
        self.canvas_client = canvas_client
        self.supabase_client = supabase_client

    def fetch_all_assignments(self) -> List[Dict[str, Any]]:
        """
        Fetches all assignments across active courses for the current user.
        Includes submission data to determine score and submission status.
        """
        assignments_data = []
        try:
            courses = self.canvas_client.get_courses(enrollment_state="active")
        except Exception:
            return []

        for course in courses:
            if not hasattr(course, "id"):
                continue
            
            try:
                # include=['submission'] is much faster than individual API calls
                assignments = course.get_assignments(include=['submission'])
                for assignment in assignments:
                    submission = getattr(assignment, 'submission', {})
                    score = submission.get('score')
                    submitted_at = submission.get('submitted_at')

                    assignments_data.append({
                        "id": getattr(assignment, 'id', None),
                        "course_id": getattr(course, 'id', None),
                        "course_name": getattr(course, 'name', 'Unknown Course'),
                        "name": getattr(assignment, 'name', 'Unknown'),
                        "due_at": getattr(assignment, 'due_at', None),
                        "points_possible": getattr(assignment, 'points_possible', None),
                        "score": score,
                        "has_submitted": submitted_at is not None
                    })
            except Exception:
                # E.g., course doesn"t allow fetching assignments or user forbidden
                pass
                
        return assignments_data

    def fetch_all_files(self) -> List[Dict[str, Any]]:
        """
        Fetches all files across active courses for the current user.
        """
        files_data = []
        try:
            courses = self.canvas_client.get_courses(enrollment_state="active")
        except Exception:
            return []

        for course in courses:
            if not hasattr(course, "id"):
                continue
            
            try:
                files = course.get_files()
                for f in files:
                    files_data.append({
                        "id": getattr(f, 'id', None),
                        "course_id": getattr(course, 'id', None),
                        "course_name": getattr(course, 'name', 'Unknown Course'),
                        "display_name": getattr(f, 'display_name', 'Unknown'),
                        "url": getattr(f, 'url', None),
                        "created_at": getattr(f, 'created_at', None),
                        "size": getattr(f, 'size', None)
                    })
            except Exception:
                pass
                
        return files_data

    def fetch_all_announcements(self) -> List[Dict[str, Any]]:
        """
        Fetches all announcements (discussion topics with is_announcement=True)
        across active courses for the current user.
        """
        announcements_data = []
        try:
            courses = self.canvas_client.get_courses(enrollment_state="active")
        except Exception:
            return []
            
        course_map = {}
        course_ids = []
        for course in courses:
             if hasattr(course, "id"):
                 course_ids.append(f"course_{course.id}")
                 course_map[f"course_{course.id}"] = getattr(course, 'name', 'Unknown Course')

        if not course_ids:
            return []

        # Use the global announcements endpoint which requires context_codes
        try:
            from datetime import datetime, timedelta, timezone
            start_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            announcements = self.canvas_client.get_announcements(
                context_codes=course_ids,
                start_date=start_date
            )
            for ann in announcements:
                announcements_data.append({
                    "id": getattr(ann, 'id', None),
                    "context_code": getattr(ann, 'context_code', None), # e.g. "course_123"
                    "course_name": course_map.get(getattr(ann, 'context_code', ''), 'Unknown Course'),
                    "title": getattr(ann, 'title', 'Unknown'),
                    "message": getattr(ann, 'message', ''),
                    "posted_at": getattr(ann, 'posted_at', None),
                    "author_name": getattr(ann, 'user_name', 'System')
                })
        except Exception:
            pass

        return announcements_data
