import httpx
import pytest
from src.flymind.telegram import TelegramDelivery


def delivery(handler):
    client=httpx.Client(transport=httpx.MockTransport(handler))
    return TelegramDelivery('SYNTHETIC_TOKEN_DO_NOT_LOG','123',client)


def test_send_success_has_message_id_and_edit_uses_same_id():
    requests=[]
    def handler(req):
        requests.append(req)
        return httpx.Response(200,json={'ok':True,'result':{'message_id':45}})
    bot=delivery(handler)
    assert bot.deliver('test').message_id==45
    assert bot.deliver('edit',45).outcome=='done'
    assert requests[1].url.path.endswith('/editMessageText')


def test_lost_response_is_ambiguous_for_send_but_edit_can_retry():
    bot=delivery(lambda req:(_ for _ in ()).throw(httpx.ReadTimeout('SYNTHETIC_TOKEN_DO_NOT_LOG',request=req)))
    assert bot.deliver('test').outcome=='ambiguous'
    assert bot.deliver('edit',45).outcome=='retry'


def test_pre_connection_failure_can_retry_without_duplicate():
    bot=delivery(lambda req:(_ for _ in ()).throw(httpx.ConnectError('secret',request=req)))
    assert bot.deliver('test').outcome=='retry'


@pytest.mark.parametrize('status,body,outcome',[(429,{'ok':False,'error_code':429,'parameters':{'retry_after':120}},'retry'),
                                              (500,{'ok':False,'error_code':500},'retry'),
                                              (403,{'ok':False,'error_code':403},'dead'),
                                              (200,{'ok':True,'result':{}},'ambiguous')])
def test_known_api_results(status,body,outcome):
    bot=delivery(lambda req:httpx.Response(status,json=body))
    r=bot.deliver('test')
    assert r.outcome==outcome
    if status==429:assert r.retry_after==120


def test_idempotent_edit_not_modified_is_success():
    bot=delivery(lambda req:httpx.Response(400,json={'ok':False,'error_code':400,'description':'Bad Request: message is not modified'}))
    assert bot.deliver('test',45).outcome=='done'


def test_unstructured_gateway_error_has_unknown_send_outcome():
    bot=delivery(lambda req:httpx.Response(502,text='secret gateway body'))
    assert bot.deliver('test').outcome=='ambiguous'


def test_missing_credentials_does_not_make_network_request():
    bot=TelegramDelivery('',123,httpx.Client(transport=httpx.MockTransport(lambda req:pytest.fail('Unexpected network'))))
    assert not bot.ready and bot.deliver('test').error_code=='missing_telegram_credentials'
