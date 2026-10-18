"""Private HTML presentation: objective urgency remains independent of GF activity."""
from zoneinfo import ZoneInfo
import html
import re
import math
from urllib.parse import urlparse
from .events import CanvasEvent, EventKind, utc


def escaped(value, limit=250):
    return html.escape(str(value)[:limit] if value is not None else '—', quote=True)


def render(event: CanvasEvent, neural: dict | None = None, *, now=None) -> str:
    p = event.payload
    labels = {EventKind.CREATED: '📌 НОВОЕ ЗАДАНИЕ!', EventKind.DEADLINE: '📅 ДЕДЛАЙН ИЗМЕНЁН!',
              EventKind.GRADE: '🔔 НОВАЯ ОЦЕНКА!', EventKind.REMINDER: '⏰ ДЕДЛАЙН СКОРО!',
              EventKind.UPDATED: '📝 ЗАДАНИЕ ИЗМЕНЕНО', EventKind.SUBMISSION: '✅ СТАТУС СДАЧИ ИЗМЕНЁН',
              EventKind.FILE: '📎 Файл Canvas изменён', EventKind.ANNOUNCEMENT: '📢 Объявление Canvas изменено',
              EventKind.STATS: 'Моя успеваемость', EventKind.HEALTH: 'Еженедельный статус Canvas Pusher'}
    minutes = ((utc(p['due_at']) - utc(now or event.observed_at)).total_seconds() / 60
               if p.get('due_at') else None)
    heading = labels[event.kind]
    if event.kind == EventKind.REMINDER and minutes is not None and minutes > 0:
        hours = max(1, math.ceil(minutes / 60))
        word = 'ЧАС' if hours % 10 == 1 and hours % 100 != 11 else 'ЧАСА' if hours % 10 in (2, 3, 4) and hours % 100 not in (12, 13, 14) else 'ЧАСОВ'
        heading = f'⏰ ДЕДЛАЙН ЧЕРЕЗ {hours} {word}!'
    title = f"📝 <b>{escaped(p.get('name') or p.get('display_name') or p.get('title'),120)}</b>"
    course = f"📚 {escaped(p.get('course_name'),80)}"
    lines = [f'<b>{heading}</b>', course, title] if event.kind == EventKind.GRADE else [f'<b>{heading}</b>', title, course]
    if event.entity_type == 'assignment':
        def date(value):
            return utc(value).astimezone(ZoneInfo('Asia/Almaty')).strftime('%d.%m.%Y %H:%M Asia/Almaty') if value else 'не установлен'
        if event.kind == EventKind.DEADLINE:
            lines.extend([f"🕒 Было: {date(event.changes['due_at'][0])}", f"✅ Стало: <b>{date(p.get('due_at'))}</b>"])
        elif event.kind == EventKind.GRADE:
            lines.extend([f"⭐ {escaped(p.get('score'))} / {escaped(p.get('points_possible'))}",
                          f"📈 По курсу: {escaped(p.get('course_score'))}{'%' if p.get('course_score') is not None else ''}"])
        else:
            lines.append(f"📅 Дедлайн: <b>{date(p.get('due_at'))}</b>")
            if event.kind != EventKind.REMINDER:
                if minutes is not None and not p.get('has_submitted'):
                    remaining = f'{int(minutes)//60} ч {int(minutes)%60} мин' if minutes >= 1 else 'меньше минуты'
                    lines.append(f'⏳ Осталось: <b>{remaining}</b>' if minutes > 0 else '⚠️ Срок уже прошёл')
                if event.kind == EventKind.SUBMISSION:
                    lines.append('✅ Сдано' if p.get('has_submitted') else '📝 Ещё не сдано')
                else:
                    lines.append(f"💯 Баллы: {escaped(p.get('points_possible'))}")
        url = str(p.get('html_url') or '')
        parsed = urlparse(url)
        if parsed.scheme == 'https' and parsed.netloc and not parsed.username and not parsed.password and len(url) < 800:
            link = f'<a href="{html.escape(url, quote=True)}">Открыть задание в Canvas</a>'
            if len(link) < 1200:
                lines.append(link)
        # Keep the optional argument for persisted jobs/API compatibility. Scientific
        # results and failure details remain in Observatory and /brain, never alerts.
    elif event.entity_type == 'file':
        url = str(p.get('url') or '')
        if urlparse(url).scheme == 'https':
            lines.append(f'<a href="{html.escape(url, quote=True)}">Открыть файл</a>')
    elif event.entity_type=='report':
        # Internal formatter escapes all Canvas names before producing this HTML.
        lines=[p.get('message') or 'Нет данных']
    else:
        lines.append(escaped(re.sub('<[^>]+>', '', p.get('message') or ''), 600))
    return '\n'.join(lines)
