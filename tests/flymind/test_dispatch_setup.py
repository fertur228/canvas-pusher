import hashlib
import json
from types import SimpleNamespace
import httpx
import pytest
from src.flymind import dispatch_setup


def test_dispatch_token_preflight_is_read_only_and_rejects_expired_or_broad_token():
    calls=[]
    def handler(req):
        calls.append(req)
        assert req.method=='GET' and req.url.host=='api.github.com'
        assert req.url.path.startswith('/repos/fertur228/canvas-pusher/')
        return httpx.Response(401)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError,match='fine_grained'):
            dispatch_setup.validate_token('synthetic-broad-token',client)
        assert not calls
        with pytest.raises(ValueError,match='http_401'):
            dispatch_setup.validate_token('github_pat_synthetic',client)
    assert len(calls)==1


def test_secret_upload_does_not_put_token_in_arguments_and_cleans_temporary_file(tmp_path,monkeypatch):
    monkeypatch.setattr(dispatch_setup,'ROOT',tmp_path)
    token='github_pat_synthetic';calls=[]
    def run(args,**kwargs):
        calls.append(args)
        assert token not in ' '.join(args) and kwargs['capture_output']
        if 'set' in args:
            p=tmp_path/'secret-flymind-release/.env.dispatch-upload'
            assert p.stat().st_mode & 0o777==0o600 and p.read_text()=='FLYMIND_GITHUB_PAT='+token+'\n'
            return SimpleNamespace(returncode=0,stdout='')
        return SimpleNamespace(returncode=0,stdout=json.dumps({'secrets':[{'name':'FLYMIND_GITHUB_PAT','value':hashlib.sha256(token.encode()).hexdigest()}]}))
    dispatch_setup.publish(token,run)
    assert len(calls)==2 and not (tmp_path/'secret-flymind-release/.env.dispatch-upload').exists()


def test_failed_upload_does_not_leave_token_on_disk(tmp_path,monkeypatch):
    monkeypatch.setattr(dispatch_setup,'ROOT',tmp_path)
    with pytest.raises(ValueError,match='update_failed'):
        dispatch_setup.publish('github_pat_synthetic',lambda *a,**k:SimpleNamespace(returncode=1))
    assert not (tmp_path/'secret-flymind-release/.env.dispatch-upload').exists()


def test_repository_secret_gate_detects_fine_grained_credentials():
    from scripts.check_repository import findings
    assert findings(b'github_pat_'+b'x'*60)==['github_fine_grained_token']
    assert findings(b'github_pat_synthetic')==[]
