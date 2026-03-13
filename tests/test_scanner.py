import pytest
from unittest.mock import MagicMock
from src.core.scanner import CanvasScanner

class MockSupabase:
    def __init__(self):
        self.table_mock = MagicMock()
        
    def table(self, name):
        return self.table_mock

def test_scanner_initialization():
    mock_canvas = MagicMock()
    mock_supabase = MockSupabase()
    
    scanner = CanvasScanner(mock_canvas, mock_supabase)
    assert scanner.canvas_client == mock_canvas
    assert scanner.supabase_client == mock_supabase

def test_scanner_fetch_course_assignments():
    mock_canvas = MagicMock()
    mock_supabase = MockSupabase()
    
    # Setup mock course and assignments
    mock_course = MagicMock()
    mock_course.id = 101
    mock_assignment = MagicMock()
    mock_assignment.id = 1
    mock_assignment.name = "Assignment 1"
    mock_assignment.due_at = "2024-01-01T00:00:00Z"
    mock_assignment.points_possible = 100
    mock_assignment.get_submission.return_value = MagicMock(score=95, submitted_at="2024-01-01T00:00:00Z")
    
    # Assignments are paginated lists, so simulate list
    mock_course.get_assignments.return_value = [mock_assignment]
    mock_canvas.get_courses.return_value = [mock_course]
    
    scanner = CanvasScanner(mock_canvas, mock_supabase)
    
    # We test the extraction logic
    assignments_data = scanner.fetch_all_assignments()
    assert len(assignments_data) == 1
    assert assignments_data[0]["id"] == 1
    assert assignments_data[0]["course_id"] == 101
    assert assignments_data[0]["score"] == 95
    assert assignments_data[0]["has_submitted"] is True
