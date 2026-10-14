"""Typed, deterministic private Canvas event adapter; no biological inference."""
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, field_validator


def utc(value: str | datetime) -> datetime:
    d = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
    if d.tzinfo is None:
        raise ValueError('Timezone required')
    return d.astimezone(timezone.utc)


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


class EventKind(str, Enum):
    CREATED = 'assignment_created'
    DEADLINE = 'deadline_changed'
    GRADE = 'grade_updated'
    REMINDER = 'deadline_reminder'
    UPDATED = 'assignment_updated'
    SUBMISSION = 'submission_changed'
    FILE = 'file_changed'
    ANNOUNCEMENT = 'announcement_changed'
    STATS = 'stats_report'
    HEALTH = 'health_report'


class CanvasEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    schema_version: Literal[1] = 1
    event_id: str
    account_id: str
    entity_type: Literal['assignment', 'file', 'announcement', 'report']
    entity_key: str
    kind: EventKind
    observed_at: str
    revision: int
    priority: Literal[0, 1, 2]  # routine / important / critical: ENGINEERING rules
    payload: dict
    changes: dict
    reminder: str | None = None

    @field_validator('event_id')
    @classmethod
    def check_id(cls, value):
        if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Invalid event digest')
        return value

    @field_validator('observed_at')
    @classmethod
    def check_time(cls, value):
        return utc(value).isoformat()


class Snapshot(BaseModel):
    revision: int = 0
    state: dict | None = None
    reminders: list[str] = []


def normalize(live: dict, entity_type: str) -> dict:
    keys = {'assignment': ('id', 'course_id', 'course_name', 'name', 'due_at', 'points_possible', 'score', 'course_score', 'has_submitted', 'html_url'),
            'file': ('id', 'course_id', 'course_name', 'display_name', 'url', 'created_at', 'size'),
            'announcement': ('id', 'context_code', 'course_name', 'title', 'message', 'posted_at', 'author_name'),
            'report': ('id','name','message','report_type')}[entity_type]
    result = {k: live.get(k) for k in keys}
    if not result['id']:
        raise ValueError('Canvas object ID required')
    for key in ('score', 'points_possible', 'course_score'):
        if key in result and result[key] is not None:
            if isinstance(result[key], bool) or not math.isfinite(float(result[key])):
                raise ValueError('Invalid Canvas grade')
            result[key] = float(result[key])
    if entity_type == 'assignment':
        result['has_submitted'] = bool(result['has_submitted'])
        if result['due_at']:
            result['due_at'] = utc(result['due_at']).isoformat()
    return result


def entity_key(live: dict, entity_type: str) -> str:
    course = live.get('course_id') if entity_type != 'announcement' else live.get('context_code')
    return f"{course or 0}:{live['id']}"


def reminder_band(state: dict, now: datetime) -> str | None:
    if state.get('has_submitted') or not state.get('due_at'):
        return None
    hours = (utc(state['due_at']) - utc(now)).total_seconds() / 3600
    if hours < 0:
        return 'overdue'
    return next((f'{h}h' for h in (1, 3, 12, 24, 48) if hours <= h), None)


def adapt(account_id: str, entity_type: str, live: dict, old: Snapshot, now: datetime,
          *, bootstrap: bool = False) -> tuple[Snapshot, list[CanvasEvent]]:
    state = normalize(live, entity_type)
    now = utc(now)
    key = entity_key(state, entity_type)
    previous = normalize(old.state, entity_type) if old.state is not None else None
    changes = {k: [previous.get(k), v] for k, v in state.items() if previous is not None and previous.get(k) != v}
    kinds = []
    if entity_type == 'assignment':
        if previous is None:
            kinds.append(EventKind.CREATED)
        else:
            if 'due_at' in changes:
                kinds.append(EventKind.DEADLINE)
            if 'score' in changes:
                kinds.append(EventKind.GRADE)
            if 'has_submitted' in changes:
                kinds.append(EventKind.SUBMISSION)
            if any(k in changes for k in ('points_possible','name')):
                kinds.append(EventKind.UPDATED)
    elif entity_type=='report':
        if previous is None:
            kinds.append(EventKind.STATS if state['report_type']=='stats' else EventKind.HEALTH)
    else:
        tracked = ('url', 'display_name') if entity_type == 'file' else ('message', 'title')
        if previous is None or any(k in changes for k in tracked):
            kinds.append(EventKind.FILE if entity_type == 'file' else EventKind.ANNOUNCEMENT)
    seen = list(old.reminders)
    if changes.get('due_at'):
        seen = []
    band = reminder_band(state, now) if entity_type == 'assignment' else None
    mark = f"{state.get('due_at')}:{band}" if band else None
    new_reminder = bool(mark and mark not in seen)
    if new_reminder:
        seen.append(mark)
        kinds.append(EventKind.REMINDER)
    updated = previous != state or new_reminder or previous is None
    revision = old.revision + int(updated)
    priority = 0 if entity_type=='report' else 1
    if entity_type == 'assignment' and state.get('due_at') and not state.get('has_submitted'):
        hours = (utc(state['due_at']) - now).total_seconds() / 3600
        priority = 2 if hours <= 3 else 1
    events = []
    for kind in kinds if not bootstrap else []:
        identity = [account_id, entity_type, key, kind.value,
                    mark if kind == EventKind.REMINDER else revision]
        events.append(CanvasEvent(event_id=hashlib.sha256(canonical(identity).encode()).hexdigest(),
                                  account_id=account_id, entity_type=entity_type, entity_key=key,
                                  kind=kind, observed_at=now.isoformat(), revision=revision,
                                  priority=priority, payload=state, changes=changes,
                                  reminder=band if kind == EventKind.REMINDER else None))
    return Snapshot(revision=revision, state=state, reminders=seen), events
