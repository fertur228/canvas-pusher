import pytest
from src.core.diff_engine import diff_objects, DiffType, check_reminders
from datetime import datetime, timedelta, timezone

def test_diff_new_object():
    old_state = None
    new_state = {"id": 123, "name": "Test Assignment"}
    
    result = diff_objects(old_state, new_state, "assignment")
    
    assert result is not None
    assert result.diff_type == DiffType.NEW
    assert result.changes == {}

def test_diff_updated_assignment_score():
    old_state = {"id": 123, "score": 10, "points_possible": 20, "due_at": "2024-01-01T00:00:00Z"}
    new_state = {"id": 123, "score": 18, "points_possible": 20, "due_at": "2024-01-01T00:00:00Z"}
    
    result = diff_objects(old_state, new_state, "assignment")
    
    assert result is not None
    assert result.diff_type == DiffType.UPDATED_GRADE
    assert "score" in result.changes
    assert result.changes["score"] == (10, 18)

def test_diff_updated_assignment_due_date():
    old_state = {"id": 123, "score": 10, "points_possible": 20, "due_at": "2024-01-01T00:00:00Z"}
    new_state = {"id": 123, "score": 10, "points_possible": 20, "due_at": "2024-01-02T00:00:00Z"}
    
    result = diff_objects(old_state, new_state, "assignment")
    
    assert result is not None
    assert result.diff_type == DiffType.UPDATED
    assert "due_at" in result.changes
    assert result.changes["due_at"] == ("2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z")

def test_diff_no_changes():
    old_state = {"id": 123, "score": 10}
    new_state = {"id": 123, "score": 10}
    
    result = diff_objects(old_state, new_state, "assignment")
    
    assert result is None

def test_check_reminders_2_days():
    now = datetime.now(timezone.utc)
    due_at = now + timedelta(days=2, hours=1) # slightly more than 2 days
    
    state = {
        "id": 123, 
        "due_at": due_at.isoformat(), 
        "has_submitted": False
    }
    
    # Simulate time passing, now we are exactly 2 days before
    mock_now = due_at - timedelta(days=2)
    
    reminder_type = check_reminders(state, mock_now)
    assert reminder_type == "48h"

def test_check_reminders_already_submitted():
    now = datetime.now(timezone.utc)
    due_at = now + timedelta(hours=12)
    mock_now = due_at - timedelta(hours=12)
    
    state = {
        "id": 123, 
        "due_at": due_at.isoformat(), 
        "has_submitted": True # submitted_at is not null
    }
    
    reminder_type = check_reminders(state, mock_now)
    assert reminder_type is None
