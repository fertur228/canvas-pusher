"""Private HTML presentation: objective urgency remains independent of GF activity."""
from zoneinfo import ZoneInfo
import html
import re
from urllib.parse import urlparse
from .events import CanvasEvent, EventKind, utc


def escaped(value, limit=250):
    return html.escape(str(value)[:limit] if value is not None else '—', quote=True)


def render(event: CanvasEvent, neural: dict | None = None, *, now=None) -> str:
    p = event.payload
    labels = {EventKind.CREATED: '🆕 Новое задание!', EventKind.DEADLINE: '📅 Изменён дедлайн', EventKind.GRADE: '⭐ Новая оценка',
              EventKind.REMINDER: '⏰ Напоминание о дедлайне!', EventKind.UPDATED: '📝 Изменено задание', EventKind.SUBMISSION: '✅ Изменён статус сдачи',
              EventKind.FILE: '📎 Файл Canvas изменён', EventKind.ANNOUNCEMENT: '📢 Объявление Canvas изменено',
              EventKind.STATS:'Моя успеваемость',EventKind.HEALTH:'Еженедельный статус Canvas Pusher'}
    lines = [f'<b>{labels[event.kind]}</b>', '',
             f"📌 <b>{escaped(p.get('name') or p.get('display_name') or p.get('title'),120)}</b>",
             f"📚 {escaped(p.get('course_name'),80)}"]
    if event.entity_type == 'assignment':
        due = utc(p['due_at']).astimezone(ZoneInfo('Asia/Almaty')).strftime('%d.%m.%Y %H:%M Asia/Almaty') if p.get('due_at') else 'не установлен'
        lines.append(f'📅 Дедлайн: <b>{due}</b>')
        if event.kind == EventKind.DEADLINE:
            before = event.changes['due_at'][0]
            old_due = utc(before).astimezone(ZoneInfo('Asia/Almaty')).strftime('%d.%m.%Y %H:%M') if before else 'не установлен'
            lines.append(f'↪️ Раньше: {old_due}')
        if p.get('due_at') and not p.get('has_submitted'):
            minutes = (utc(p['due_at']) - utc(now or event.observed_at)).total_seconds() / 60
            remaining = f'{int(minutes)//60} ч {int(minutes)%60} мин' if minutes >= 1 else 'меньше минуты'
            lines.append(f'⌛ Осталось: <b>{remaining}</b>' if minutes > 0 else '⚠️ Срок уже прошёл')
            if 0 < minutes <= 180:
                lines.append('🚨 <b>Скоро дедлайн!</b>')
        lines.append('✅ Сдано' if p.get('has_submitted') else '📝 Ещё не сдано')
        if p.get('score') is not None:
            lines.append(f"⭐ Оценка: {escaped(p['score'])} / {escaped(p.get('points_possible'))}")
        if p.get('points_possible') is not None and p.get('score') is None:
            lines.append(f"💯 Возможные баллы: {escaped(p['points_possible'])}")
        url=str(p.get('html_url') or '')
        parsed=urlparse(url)
        if parsed.scheme=='https' and parsed.netloc and not parsed.username and not parsed.password and len(url)<800:
            link=f'<a href="{html.escape(url, quote=True)}">Открыть задание в Canvas</a>'
            if len(link)<1200:lines.append(link)
        if neural and neural.get('status') == 'complete':
            r = neural['readout']
            translated = {'elevated': 'повышенный', 'moderate': 'умеренный', 'minimal': 'минимальный'}[r['classification']]
            lines.extend([f'\n🧠 Экспериментальный нейронный сигнал: <b>{translated}</b>',
                          'Биологически не валидировано.'])
        elif neural:
            lines.append('\n🧠 Экспериментальная оценка недоступна')
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
