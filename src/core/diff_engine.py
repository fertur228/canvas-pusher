from enum import Enum
from typing import Optional, Dict, Any, Tuple
from pydantic import BaseModel
from datetime import datetime, timezone

class DiffType(Enum):
    NEW = "NEW"
    UPDATED = "UPDATED"
    UPDATED_GRADE = "UPDATED_GRADE"
    REMINDER_DUE = "REMINDER_DUE"

class DiffResult(BaseModel):
    diff_type: DiffType
    object_type: str
    changes: Dict[str, Tuple[Any, Any]]
    reminder_type: Optional[str] = None

def diff_objects(old_state: Optional[Dict[str, Any]], new_state: Dict[str, Any], object_type: str) -> Optional[DiffResult]:
    """
    Compares two state dictionaries and returns the type of change.
    """
    if old_state is None:
        return DiffResult(diff_type=DiffType.NEW, object_type=object_type, changes={})

    changes = {}
    
    # Define which keys to track based on object_type
    keys_to_track = []
    if object_type == "assignment":
        keys_to_track = ["score", "points_possible", "due_at"]
    elif object_type == "file":
        keys_to_track = ["url", "display_name"]
    elif object_type == "announcement":
        keys_to_track = ["message", "title"]

    for key in keys_to_track:
        old_val = old_state.get(key)
        new_val = new_state.get(key)
        if old_val != new_val:
            changes[key] = (old_val, new_val)

    if changes:
        if object_type == "assignment" and "score" in changes:
            return DiffResult(diff_type=DiffType.UPDATED_GRADE, object_type=object_type, changes=changes)
        return DiffResult(diff_type=DiffType.UPDATED, object_type=object_type, changes=changes)

    return None

def check_reminders(new_state: Dict[str, Any], current_time: datetime) -> Optional[str]:
    """
    Checks if a reminder should be sent based on due_at and submission status.
    Returns the string representing the reminder type ('48h', '24h', '12h', '3h', '1h') or None.
    """
    # If the assignment is already submitted, we don't send reminders.
    if new_state.get("has_submitted", False):
        return None
        
    due_at_str = new_state.get("due_at")
    if not due_at_str:
        return None

    try:
        due_at = datetime.fromisoformat(due_at_str.replace("Z", "+00:00"))
    except ValueError:
        return None

    time_left = due_at - current_time
    hours_left = time_left.total_seconds() / 3600

    if 48 <= hours_left < 49:
        return "48h"
    elif 24 <= hours_left < 25:
        return "24h"
    elif 12 <= hours_left < 13:
        return "12h"
    elif 3 <= hours_left < 4:
        return "3h"
    elif 1 <= hours_left < 2:
        return "1h"

    return None
