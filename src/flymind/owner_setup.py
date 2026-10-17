"""Owner-run terminal provisioning; no passwords/tokens printed, stored or invented.

The human explicitly supplies their email/password locally. The administrator
provisions that identity (email_confirm=True); this is not an email-delivery test.
Only the already verified test account is bound. Production stays disabled.
"""
import getpass
import logging
from pathlib import Path
import sys

from dotenv import dotenv_values
from supabase import create_client
from .bot_setup import BotAPI, write_private

ROOT=Path(__file__).resolve().parents[2]
PROJECT='https://irjasmzytjeohwfpdnrl.supabase.co'


def validate_binding(hosted,owner,test,account):
    if (hosted.get('SUPABASE_URL')!=PROJECT or not account
            or not hosted.get('SUPABASE_PUBLISHABLE_KEY') or not hosted.get('SUPABASE_SERVICE_KEY')
            or not test.get('TEST_TELEGRAM_CHAT_ID')
            or test.get('TELEGRAM_CHAT_ID')!=test['TEST_TELEGRAM_CHAT_ID']
            or test['TELEGRAM_CHAT_ID']==owner.get('TELEGRAM_CHAT_ID')
            or not owner.get('TELEGRAM_USER_ID')
            or test.get('TELEGRAM_USER_ID')!=owner['TELEGRAM_USER_ID']
            or test.get('TELEGRAM_BOT_ID')!=owner.get('TELEGRAM_BOT_ID')):
        raise ValueError('unverified_test_owner_binding')


def main():
    if not sys.stdin.isatty():
        raise SystemExit('Run this command yourself in an interactive local terminal.')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    try:
        hosted=dotenv_values(ROOT/'.env.flymind.hosted')
        local=dotenv_values(ROOT/'.env.flymind.local')
        owner=dotenv_values(ROOT/'.env.flymind.identity')
        test=dotenv_values(ROOT/'.env.flymind.test')
        account=dotenv_values(ROOT/'.env.flymind.account-test').get('FLYMIND_ACCOUNT_ID')
        validate_binding(hosted,owner,test,account)
        if str(BotAPI(local['TELEGRAM_BOT_TOKEN']).call('getMe')['id'])!=owner['TELEGRAM_BOT_ID']:
            raise ValueError('bot_mismatch')
        admin=create_client(PROJECT,hosted['SUPABASE_SERVICE_KEY'])
        row=admin.table('flymind_accounts').select('owner_id,telegram_chat_id,telegram_user_id,telegram_bot_id,canvas_origin').eq('id',account).single().execute().data
        if any(str(row[k])!=test[k.upper()] for k in ('telegram_chat_id','telegram_user_id','telegram_bot_id')) or row['canvas_origin']!='https://canvas.narxoz.kz':
            raise ValueError('stored_binding_mismatch')
        print('Provision your own Observatory sign-in. Only the test account will be linked; production remains off.')
        email=input('Your owner email (local terminal only): ').strip()
        if '@' not in email or any(c in email for c in '\r\n'):raise ValueError('invalid_email')
        password=getpass.getpass('Your chosen password (hidden, minimum 12 characters): ')
        if len(password)<12 or password!=getpass.getpass('Confirm password (hidden): '):
            raise ValueError('password_validation_failed')
        public=create_client(PROJECT,hosted['SUPABASE_PUBLISHABLE_KEY'])
        try:
            session=public.auth.sign_in_with_password({'email':email,'password':password})
        except Exception:
            # Do not change an existing user's password. Duplicate email creation fails.
            # A lost creation response can be safely resumed by signing in next time.
            admin.auth.admin.create_user({'email':email,'password':password,'email_confirm':True,
                                         'app_metadata':{'flymind_owner_provisioning':'verified_local_telegram_identity'}})
            session=public.auth.sign_in_with_password({'email':email,'password':password})
        uid=session.user.id
        identity_path=ROOT/'.env.flymind.owner'
        saved=dotenv_values(identity_path) if identity_path.exists() else {}
        if row['owner_id'] not in (None,uid) or (saved and saved.get('SUPABASE_OWNER_ID')!=uid):
            raise ValueError('existing_owner_must_not_be_reassigned')
        if row['owner_id'] is None:
            admin.table('flymind_accounts').update({'owner_id':uid}).eq('id',account).is_('owner_id','null').execute()
        visible=public.table('flymind_accounts').select('id').eq('id',account).execute().data
        if len(visible)!=1:raise ValueError('owner_mapping_not_verified')
        experiments=public.table('flymind_experiments').select('event_id').eq('account_id',account).execute().data
        if not identity_path.exists():
            write_private(identity_path,{'SUPABASE_OWNER_ID':uid,'OWNER_EMAIL':email})
        public.auth.sign_out({'scope':'local'})
        print(f'Owner login and test-account RLS verified; accessible experiments: {len(experiments)}. Password not stored.')
        print('Open https://flymind-preview.flymind-observatory.pages.dev and sign in with the credentials you just chose.')
    except Exception:
        raise SystemExit('Owner setup incomplete. No credentials printed. Existing users/passwords were not replaced; retry with the same correct credentials.') from None


if __name__=='__main__':main()
