"""Existing async scanner regression tests; legacy tests targeted a removed class."""
import asyncio
import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.core.scanner import AsyncCanvasScanner, ScanFailure


def test_scanner_initialization():
    supabase = MagicMock()
    scanner = AsyncCanvasScanner("test-token", "https://canvas.invalid/", supabase)
    assert scanner.base_url == "https://canvas.invalid/api/v1"
    assert scanner.headers == {"Authorization": "Bearer test-token"}
    assert scanner.supabase_client is supabase


def test_scanner_fetch_course_assignments():
    scanner = AsyncCanvasScanner("test-token", "https://canvas.invalid", MagicMock())
    course = {"id": 101, "name": "Course", "enrollments": [
        {"type": "student", "computed_current_score": 93}]}
    response = MagicMock(status_code=200)
    response.links = {}
    response.json.return_value = [{"id": 1, "name": "Assignment 1", "points_possible": 100,
                                   "submission": {"score": 95, "submitted_at": "2024-01-01T00:00:00Z"}}]
    client = MagicMock(get=AsyncMock(return_value=response))
    assignments = asyncio.run(scanner.fetch_course_assignments(client, course))
    assert assignments == [{"id": 1, "course_id": 101, "course_name": "Course", "course_score": 93,
                            "name": "Assignment 1", "due_at": None, "points_possible": 100,
                            "score": 95, "has_submitted": True}]
    assert client.get.call_args.args == ("https://canvas.invalid/api/v1/courses/101/assignments",)


def test_scanner_failed_assignment_request():
    scanner = AsyncCanvasScanner("test-token", "https://canvas.invalid", MagicMock())
    client = MagicMock(get=AsyncMock(side_effect=httpx.ConnectError("offline")))
    # A failed fetch is not an empty authoritative course.
    with pytest.raises(ScanFailure, match="canvas_transport_failed"):
        asyncio.run(scanner.fetch_course_assignments(client, {"id": 1}))


def test_scanner_parallel_results_are_associated_with_courses():
    scanner = AsyncCanvasScanner("test-token", "https://canvas.invalid", MagicMock())
    scanner.fetch_course_assignments = AsyncMock(side_effect=[[{"id": 11}], [{"id": 22}]])
    scanner.fetch_course_files = AsyncMock(side_effect=[[{"id": 33}], []])
    scanner.fetch_all_announcements = AsyncMock(return_value=[{"id": 44}])
    with patch("src.core.scanner.httpx.AsyncClient") as client:
        client.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = asyncio.run(scanner.scan_all([{"id": 1}, {"id": 2}]))
    assert result == ([{"id": 11}, {"id": 22}], [{"id": 33}], [{"id": 44}])
