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
    assert "cron: '3/5 * * * *'" in scanner
    assert 'group: canvas-state-tracker' in scanner
    assert "FLYMIND_ENABLED || 'false'" in scanner and "DELIVERY_MODE || 'disabled'" in scanner
    assert "inputs.read_only == true || vars.CANVAS_WORKER_ENABLED == 'true'" in scanner
    assert 'pip install -r requirements-neural.lock' in scanner
    maintenance=Path('.github/workflows/flymind-maintenance.yml').read_text()
    assert "vars.FLYMIND_RETENTION_ENABLED == 'true'" in maintenance
    assert 'default: false' in maintenance and '--days 30 --apply' in maintenance
    for name in ('flymind-maintenance.yml','flymind-watchdog.yml'):
        source=Path('.github/workflows',name).read_text()
        assert 'TEST_TELEGRAM_CHAT_ID:' in source and 'DELIVERY_MODE:' in source
        assert 'TELEGRAM_BOT_TOKEN' not in source and 'CANVAS_API_KEY' not in source


def test_manual_workflow_cannot_fall_back_to_legacy_and_finalizer_is_trusted():
    worker=Path('.github/workflows/check_canvas.yml').read_text()
    assert 'MANUAL_REQUEST_ID:' in worker and 'src.flymind.manual_sync run' in worker
    assert 'run-name: FlyMind sync' in worker
    finalizer=Path('.github/workflows/flymind-manual-completion.yml').read_text()
    assert 'workflow_run:' in finalizer and 'types: [completed]' in finalizer
    assert 'ref: ${{ github.event.repository.default_branch }}' in finalizer
    assert 'head_repository.full_name == github.repository' in finalizer
    assert 'download-artifact' not in finalizer and 'CANVAS_API_KEY' not in finalizer
