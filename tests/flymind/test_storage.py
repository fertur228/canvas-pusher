import hashlib
from types import SimpleNamespace
import pytest
from src.flymind.store import SupabaseTelemetryStorage


def test_upload_is_private_content_addressed_and_never_upserts():
    requests=[]
    class Bucket:
        def upload(self,path,blob,options):requests.append((path,blob,options))
    client=SimpleNamespace(storage=SimpleNamespace(from_=lambda name:Bucket() if name=='flymind-private' else pytest.fail('Wrong bucket')))
    path=SupabaseTelemetryStorage(client).put('00000000-0000-0000-0000-000000000001','a'*64,b'SYNTHETIC')
    assert path.endswith(hashlib.sha256(b'SYNTHETIC').hexdigest()+'.json.gz')
    assert requests[0][2]['upsert']=='false'


def test_lost_upload_ack_reuses_only_checksum_matching_content():
    class Bucket:
        def upload(self,*args):raise RuntimeError('SYNTHETIC secret MUST NOT be exposed')
        def download(self,path):return b'SYNTHETIC'
    client=SimpleNamespace(storage=SimpleNamespace(from_=lambda name:Bucket()))
    assert SupabaseTelemetryStorage(client).put('00000000-0000-0000-0000-000000000001','a'*64,b'SYNTHETIC')
    with pytest.raises(ValueError,match='storage_upload_failed'):
        SupabaseTelemetryStorage(client).put('00000000-0000-0000-0000-000000000001','a'*64,b'OTHER')


def test_oversized_and_cross_scope_paths_rejected_before_upload():
    client=SimpleNamespace(storage=None)
    store=SupabaseTelemetryStorage(client)
    for account,event,blob in [('00000000-0000-0000-0000-000000000001','../other',b'x'),('00000000-0000-0000-0000-000000000001','a'*64,b'x'*(4*1024*1024+1))]:
        with pytest.raises(ValueError):store.put(account,event,blob)
