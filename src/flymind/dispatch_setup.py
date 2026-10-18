"""Owner terminal setup for a repository-scoped GitHub dispatch credential.

Never uses or exports the personal gh CLI credential. No workflow is dispatched.
Only the isolated FlyMind Edge secret is updated; activation flags are untouched.
"""
import getpass
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import sys

import httpx

ROOT = Path(__file__).resolve().parents[2]
PROJECT = 'irjasmzytjeohwfpdnrl'
REPO = 'fertur228/canvas-pusher'


def validate_token(token, client):
    if not token.startswith('github_pat_') or any(c.isspace() for c in token):
        raise ValueError('fine_grained_repository_token_required')
    headers = {'Authorization': 'Bearer '+token, 'Accept': 'application/vnd.github+json'}
    for path in ('actions/variables/CANVAS_WORKER_ENABLED',
                 'actions/workflows/check_canvas.yml',
                 'actions/workflows/flymind-manual-completion.yml',
                 'contents/.github/workflows/check_canvas.yml?ref=main'):
        response = client.get(f'https://api.github.com/repos/{REPO}/{path}', headers=headers)
        if response.status_code != 200:
            raise ValueError('dispatch_read_preflight_http_'+str(response.status_code))


def publish(token, run=subprocess.run):
    directory = ROOT/'secret-flymind-release'
    directory.mkdir(exist_ok=True, mode=0o700)
    path = directory/'.env.dispatch-upload'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write('FLYMIND_GITHUB_PAT='+token+'\n')
        result = run(['npx','supabase','secrets','set','--project-ref',PROJECT,'--env-file',str(path)],
                     cwd=ROOT, text=True, capture_output=True, timeout=120)
        if result.returncode:
            raise ValueError('supabase_secret_update_failed')
        result = run(['npx','supabase','secrets','list','--project-ref',PROJECT],
                     cwd=ROOT, text=True, capture_output=True, timeout=120)
        if result.returncode:
            raise ValueError('supabase_secret_verification_failed')
        rows = json.loads(result.stdout)['secrets']
        if not any(r['name']=='FLYMIND_GITHUB_PAT' and r['value']==hashlib.sha256(token.encode()).hexdigest() for r in rows):
            raise ValueError('supabase_secret_digest_mismatch')
    finally:
        path.unlink()  # Only our exclusively created temporary file.


def main():
    if not sys.stdin.isatty():
        raise SystemExit('Run this setup yourself in your terminal; never paste the token into chat.')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    try:
        if (ROOT/'supabase/.temp/project-ref').read_text().strip()!=PROJECT:
            raise ValueError('wrong_linked_project')
        print('Use a new fine-grained token for ONLY fertur228/canvas-pusher:')
        print('Actions: read/write; Variables: read; Contents: read; Metadata: read. Set an expiry.')
        token = getpass.getpass('Repository-scoped GitHub token (hidden): ').strip()
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            validate_token(token, client)
        publish(token)
        print('FlyMind dispatch secret updated and digest verified. No token printed or retained locally.')
        print('Read preflight passed. Actual workflow dispatch/completion still requires a controlled test.')
    except Exception:
        raise SystemExit('Dispatch setup incomplete; check token repository permissions and linked CLI access. No secrets printed.') from None


if __name__=='__main__':
    main()
