"""Delivery with explicit uncertainty, never leaks bot-token URLs or response bodies."""
from dataclasses import dataclass
import httpx


@dataclass(frozen=True)
class Delivery:
    outcome: str
    message_id: int | None = None
    error_code: str | None = None
    retry_after: int = 0


class TelegramDelivery:
    def __init__(self, token: str | None, chat_id: str | int, client=None):
        self.token, self.chat_id = token, str(chat_id)
        self.bot_id = token.split(':',1)[0] if token and ':' in token and token.split(':',1)[0].isdigit() else None
        self.client = client or httpx.Client(timeout=10, follow_redirects=False)

    @property
    def ready(self):
        return bool(self.token and self.chat_id)

    def deliver(self, text: str, message_id: int | None = None) -> Delivery:
        if not self.ready:
            return Delivery('retry', error_code='missing_telegram_credentials', retry_after=60)
        edit = message_id is not None
        method = 'editMessageText' if edit else 'sendMessage'
        payload = {'chat_id': self.chat_id, 'text': text, 'parse_mode': 'HTML', 'link_preview_options': {'is_disabled': True}}
        payload['reply_markup']={'inline_keyboard':[[{'text':'📅 Deadlines','callback_data':'deadlines:upcoming:0'},{'text':'⚙️ System Status','callback_data':'status'}]]}
        if edit:
            payload['message_id'] = message_id
        try:
            response = self.client.post(f'https://api.telegram.org/bot{self.token}/{method}', json=payload)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
            return Delivery('retry', error_code='connect_failed', retry_after=30)
        except httpx.HTTPError:
            return Delivery('retry' if edit else 'ambiguous', error_code='transport_uncertain', retry_after=60)
        try:
            data = response.json()
        except ValueError:
            return Delivery('retry' if edit else 'ambiguous', error_code='unparseable_response', retry_after=60)
        if response.status_code == 200 and data.get('ok'):
            returned = data.get('result', {})
            mid = returned.get('message_id') if isinstance(returned, dict) else None
            if edit:
                return Delivery('done', message_id=message_id)
            if isinstance(mid, int) and mid > 0:
                return Delivery('done', message_id=mid)
            return Delivery('ambiguous', error_code='missing_message_id')
        if data.get('ok') is False:
            code = data.get('error_code', response.status_code)
            if edit and code == 400 and 'message is not modified' in str(data.get('description','')).lower():
                return Delivery('done', message_id=message_id)
            if code == 429 or code >= 500:
                delay = data.get('parameters', {}).get('retry_after', 30)
                return Delivery('retry', error_code=f'telegram_{code}', retry_after=min(86400, max(1, int(delay))))
            return Delivery('dead', error_code=f'telegram_{code}')
        return Delivery('retry' if edit else 'ambiguous', error_code='response_uncertain', retry_after=60)
