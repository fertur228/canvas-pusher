import json
import sys

import pytest

from src.flymind import telegram_check
from src.flymind.telegram import Delivery
from src.flymind.worker import Settings


def configure(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'argv', ['telegram-check', '--state', str(tmp_path / 'check.sqlite')])
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'synthetic-token')
    monkeypatch.setenv('TEST_TELEGRAM_CHAT_ID', '222')
    monkeypatch.setenv('TELEGRAM_CHAT_ID', '111')


def test_scheduled_worker_rejects_primary_chat_as_test_target():
    with pytest.raises(ValueError, match='test_chat_must_differ'):
        Settings.from_env({'FLYMIND_ENABLED':'true','DELIVERY_MODE':'test',
                           'TEST_TELEGRAM_CHAT_ID':'111','TELEGRAM_CHAT_ID':'111'})


@pytest.mark.parametrize('missing', ['TELEGRAM_BOT_TOKEN', 'TEST_TELEGRAM_CHAT_ID', 'same_chat'])
def test_missing_or_production_target_never_sends(monkeypatch, tmp_path, missing):
    configure(monkeypatch, tmp_path)
    if missing == 'same_chat':
        monkeypatch.setenv('TEST_TELEGRAM_CHAT_ID', '111')
    else:
        monkeypatch.delenv(missing)
    with pytest.raises(SystemExit, match='separate TEST_TELEGRAM_CHAT_ID'):
        telegram_check.main()
    assert not (tmp_path / 'check.sqlite').exists()


def test_real_check_cli_persists_send_and_edit_ids_without_duplicates(monkeypatch, tmp_path, capsys):
    configure(monkeypatch, tmp_path)
    calls = []
    class Captured:
        ready = True
        def __init__(self, token, chat):
            assert chat == '222'
        def deliver(self, text, message_id=None):
            calls.append((text, message_id))
            return Delivery('done', message_id=message_id or 987)
    monkeypatch.setattr(telegram_check, 'TelegramDelivery', Captured)
    telegram_check.main()
    telegram_check.main()
    assert len(calls) == 2
    assert calls[0][1] is None and calls[1][1] == 987
    assert 'edit verified' in calls[1][0]
    assert json.loads(capsys.readouterr().out.splitlines()[-1])['status'] == 'verified'


def test_ambiguous_test_send_fails_gate_and_is_not_repeated(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    calls = []
    class Uncertain:
        ready = True
        def __init__(self, token, chat):pass
        def deliver(self, text, message_id=None):
            calls.append(message_id)
            return Delivery('ambiguous', error_code='timeout')
    monkeypatch.setattr(telegram_check, 'TelegramDelivery', Uncertain)
    for _ in range(2):
        with pytest.raises(SystemExit) as raised:
            telegram_check.main()
        assert raised.value.code == 2
    assert calls == [None]
