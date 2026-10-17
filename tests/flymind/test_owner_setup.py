import pytest
from src.flymind.owner_setup import validate_binding


def test_owner_provisioning_cannot_target_other_project_or_primary_chat():
    h={'SUPABASE_URL':'https://irjasmzytjeohwfpdnrl.supabase.co','SUPABASE_SERVICE_KEY':'test','SUPABASE_PUBLISHABLE_KEY':'test'}
    o={'TELEGRAM_CHAT_ID':'123','TELEGRAM_USER_ID':'123','TELEGRAM_BOT_ID':'456'}
    t={'TELEGRAM_CHAT_ID':'-789','TEST_TELEGRAM_CHAT_ID':'-789','TELEGRAM_USER_ID':'123','TELEGRAM_BOT_ID':'456'}
    validate_binding(h,o,t,'test-account')
    for changes in [{'TELEGRAM_CHAT_ID':'123','TEST_TELEGRAM_CHAT_ID':'123'}, {'TELEGRAM_USER_ID':'999'}, {'TELEGRAM_BOT_ID':'999'}, {'TEST_TELEGRAM_CHAT_ID':''}]:
        with pytest.raises(ValueError):validate_binding(h,o,t|changes,'test-account')
    with pytest.raises(ValueError):validate_binding(h|{'SUPABASE_URL':'https://other.invalid'},o,t,'test-account')
    with pytest.raises(ValueError):validate_binding(h,o,t,'')
