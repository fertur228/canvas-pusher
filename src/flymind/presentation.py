"""Private HTML presentation: objective urgency remains independent of GF activity."""
from zoneinfo import ZoneInfo
import html
import re
from urllib.parse import urlparse
from .events import CanvasEvent, EventKind, utc


def escaped(value, limit=250):
    return html.escape(str(value)[:limit] if value is not None else '—', quote=True)


def render(event: CanvasEvent, neural: dict | None = None) -> str:
    p = event.payload
    labels = {EventKind.CREATED: 'Новое задание', EventKind.DEADLINE: 'Изменён дедлайн', EventKind.GRADE: 'Обновлена оценка',
              EventKind.REMINDER: 'Напоминание о дедлайне', EventKind.UPDATED: 'Изменено задание', EventKind.SUBMISSION: 'Изменён статус сдачи',
              EventKind.FILE: 'Файл Canvas изменён', EventKind.ANNOUNCEMENT: 'Объявление Canvas изменено',
              EventKind.STATS:'Моя успеваемость',EventKind.HEALTH:'Еженедельный статус Canvas Pusher'}
    urgency = ('обычная', 'важная', 'КРИТИЧЕСКАЯ')[event.priority]
    lines = [f'<b>{labels[event.kind]}</b>', f'Срочность Canvas (правила): <b>{urgency}</b>',
             escaped(p.get('name') or p.get('display_name') or p.get('title'),120),
             f"Дисциплина: {escaped(p.get('course_name'),80)}"]
    if event.entity_type == 'assignment':
        due = utc(p['due_at']).astimezone(ZoneInfo('Asia/Almaty')).strftime('%d.%m.%Y %H:%M Asia/Almaty') if p.get('due_at') else 'не установлен'
        lines.append(f'Дедлайн: {due}')
        lines.append('Статус: ' + ('сдано' if p.get('has_submitted') else 'не сдано'))
        if p.get('score') is not None:
            lines.append(f"Оценка: {escaped(p['score'])} / {escaped(p.get('points_possible'))}")
        if p.get('points_possible') is not None and p.get('score') is None:
            lines.append(f"Возможные баллы: {escaped(p['points_possible'])}")
        url=str(p.get('html_url') or '')
        parsed=urlparse(url)
        if parsed.scheme=='https' and parsed.netloc and not parsed.username and not parsed.password and len(url)<800:
            link=f'<a href="{html.escape(url, quote=True)}">Открыть задание в Canvas</a>'
            if len(link)<1200:lines.append(link)
        if event.reminder:
            lines.append(f'Интервал: {escaped(event.reminder)}')
        if neural and neural.get('status') == 'complete':
            r = neural['readout']
            translated = {'elevated': 'повышенный', 'moderate': 'умеренный', 'minimal': 'минимальный'}[r['classification']]
            lines.extend([f'\nЭкспериментальный нейронный сигнал: <b>{translated}</b>',
                          f"GF L/R: {r['gf_spikes'][0]}/{r['gf_spikes'][1]}; активных клеток: {r['active_neurons']}",
                          'Порог задан инженером. Биологически не валидировано.'])
        else:
            lines.append('\nНейронная оценка: ' + ('недоступна; уведомление доставлено независимо' if neural else 'ожидается; доставка не зависит от расчёта'))
    elif event.entity_type == 'file':
        url = str(p.get('url') or '')
        if urlparse(url).scheme == 'https':
            lines.append(f'<a href="{html.escape(url, quote=True)}">Открыть файл</a>')
    elif event.entity_type=='report':
        # Internal formatter escapes all Canvas names before producing this HTML.
        lines=[p.get('message') or 'Нет данных']
    else:
        lines.append(escaped(re.sub('<[^>]+>', '', p.get('message') or ''), 600))
    # A stable event reference helps an operator resolve ambiguous delivery, without exposing payloads in logs.
    lines.append(f'\nСобытие: <code>{event.event_id[:12]}</code>')
    return '\n'.join(lines)
