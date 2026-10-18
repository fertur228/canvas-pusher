import pytest
from src.flymind.hosted_validation import test_settings as settings_for_test


def env():
    account='00000000-0000-0000-0000-000000000001'
    return {'FLYMIND_TEST_CHAT_VALIDATION':'true','FLYMIND_ENABLED':'true',
            'FLYMIND_ACCOUNT_ID':account,'FLYMIND_TEST_ACCOUNT_ID':account,
            'FLYMIND_MODE':'shadow','DELIVERY_MODE':'test',
            'TELEGRAM_CHAT_ID':'123','TEST_TELEGRAM_CHAT_ID':'-456',
            'SUPABASE_URL':'https://irjasmzytjeohwfpdnrl.supabase.co',
            'SUPABASE_SERVICE_KEY':'synthetic'}


def test_cloud_probe_is_explicit_and_scoped():
    assert settings_for_test(env()).chat_id=='-456'
    for changes in [{'FLYMIND_TEST_CHAT_VALIDATION':'false'}, {'DELIVERY_MODE':'production'},
                    {'FLYMIND_PRODUCTION_AUTHORIZED':'true'}, {'FLYMIND_MODE':'enrich'},
                    {'SUPABASE_URL':'https://other.invalid'}, {'TEST_TELEGRAM_CHAT_ID':'123'},
                    {'FLYMIND_TEST_ACCOUNT_ID':''}, {'TELEGRAM_CHAT_ID':''},
                    {'FLYMIND_TEST_ACCOUNT_ID':'00000000-0000-0000-0000-000000000002'}]:
        with pytest.raises(ValueError):settings_for_test(env()|changes)
