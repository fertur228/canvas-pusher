from pathlib import Path
import re


def test_workflows_pin_actions_and_do_not_publish_private_artifacts():
    for path in Path('.github/workflows').glob('*.yml'):
        source=path.read_text()
        for action in re.findall(r'uses:\s*([^\s#]+)',source):
            assert re.search(r'@[a-f0-9]{40}$',action), (path,action)
        assert 'pull_request_target' not in source
        assert 'contents: write' not in source
    read=Path('.github/workflows/flymind-readonly-check.yml').read_text()
    assert 'SUPABASE_SERVICE_KEY' not in read and 'TELEGRAM_BOT_TOKEN' not in read
    scanner=Path('.github/workflows/check_canvas.yml').read_text()
    assert 'cancel-in-progress: false' in scanner
    assert "FLYMIND_ENABLED || 'false'" in scanner and "DELIVERY_MODE || 'disabled'" in scanner
