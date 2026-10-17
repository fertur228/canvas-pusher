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


REMINDER_HOURS = (24, 12, 6, 3, 1)
_VERSION = 'deadline-version:v2:'
_AUDIT = 'reminder-audit:v2:'


def reminder_band(state: dict, now: datetime) -> str | None:
    if state.get('has_submitted') or not state.get('due_at'):
        return None
    hours = (utc(state['due_at']) - utc(now)).total_seconds() / 3600
    if hours <= 0:
        return None
    return next((f'{h}h' for h in reversed(REMINDER_HOURS) if hours <= h), None)


def reminder_identity(account: str, key: str, due: str, band: str, marks: list[str]) -> str:
    # Keep v1 IDs for existing deadlines; a genuinely changed deadline gets its
    # own revision even if it later returns to a previously used timestamp.
    identity = [account, 'assignment', key, EventKind.REMINDER.value, f'{due}:{band}']
    version = next((s for s in marks if s.startswith(_VERSION)), None)
    if version:
        identity.append(version)
    return hashlib.sha256(canonical(identity).encode()).hexdigest()


def reminder_audit(marks: list[str]) -> list[dict]:
    return [json.loads(s[len(_AUDIT):]) for s in marks if s.startswith(_AUDIT)]


def consume_thresholds(state, old, now, *, created, deadline_changed, bootstrap):
    """Consume every crossed threshold atomically with the snapshot/outbox.

    Plain due:band marks remain backward compatible with v1. Additional strings
    carry version/reason metadata in the existing JSONB array (no SQL migration).
    'queued' means an outbox event, never an assertion that Telegram delivered it.
    """
    seen = [] if deadline_changed else list(old.reminders)
    if created or deadline_changed:
        seen.append(_VERSION + str(old.revision + 1))
    due = state.get('due_at')
    if not due:
        return seen, None
    hours = (utc(due) - now).total_seconds() / 3600
    band = reminder_band(state, now)
    reason = ('silent_bootstrap' if bootstrap else 'covered_by_creation' if created
              else 'covered_by_deadline_change' if deadline_changed
              else 'submitted' if state.get('has_submitted') else 'expired' if hours <= 0 else None)
    # Also respect old snapshots which stored only the nearest consumed band.
    consumed_nearer = any(f'{due}:{h}h' in seen for h in REMINDER_HOURS if band and h <= int(band[:-1]))
    emit = band if reason is None and not consumed_nearer else None
    for h in REMINDER_HOURS:
        mark = f'{due}:{h}h'
        if hours <= h and mark not in seen:
            status = reason or ('queued' if emit == f'{h}h' else 'skipped_late')
            seen.extend([mark, _AUDIT + canonical({'due_at': due, 'threshold': f'{h}h',
                                                 'status': status, 'observed_at': now.isoformat()})])
    return seen, emit


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
    seen, band = (consume_thresholds(state, old, now, created=previous is None,
                  deadline_changed='due_at' in changes, bootstrap=bootstrap)
                  if entity_type == 'assignment' else (list(old.reminders), None))
    if band:
        kinds.append(EventKind.REMINDER)
    updated = previous != state or seen != old.reminders or previous is None
    revision = old.revision + int(updated)
    priority = 0 if entity_type=='report' else 1
    if entity_type == 'assignment' and state.get('due_at') and not state.get('has_submitted'):
        hours = (utc(state['due_at']) - now).total_seconds() / 3600
        priority = 2 if hours <= 3 else 1
    events = []
    for kind in kinds if not bootstrap else []:
        identity = [account_id, entity_type, key, kind.value, revision]
        digest = (reminder_identity(account_id, key, state['due_at'], band, seen) if kind == EventKind.REMINDER
                  else hashlib.sha256(canonical(identity).encode()).hexdigest())
        events.append(CanvasEvent(event_id=digest,
                                  account_id=account_id, entity_type=entity_type, entity_key=key,
                                  kind=kind, observed_at=now.isoformat(), revision=revision,
                                  priority=priority, payload=state, changes=changes,
                                  reminder=band if kind == EventKind.REMINDER else None))
    return Snapshot(revision=revision, state=state, reminders=seen), events
