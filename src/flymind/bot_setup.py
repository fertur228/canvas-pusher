"""Local credential/bootstrap tool. Never prints tokens or HTTP exception URLs."""
import argparse
import getpass
import json
import logging
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from urllib.parse import urlparse
import httpx

COMMANDS=[{'command':k,'description':v} for k,v in [('start','Главное меню'),('menu','Открыть меню'),('deadlines','Несданные задания и сроки'),('check','Проверить Canvas сейчас'),('stats','Мои оценки'),('brain','Экспериментальная нейронная активность'),('status','Состояние системы')]]


class BotAPI:
    def __init__(self,token,client=None):
        if not token:raise ValueError('missing_bot_token')
        self.token=token;self.client=client or httpx.Client(timeout=25,follow_redirects=False)
    def call(self,method,payload=None):
        try:
            response=self.client.post(f'https://api.telegram.org/bot{self.token}/{method}',json=payload or {})
            data=response.json()
        except Exception:raise ValueError('telegram_transport_failed_private_details_omitted') from None
        if response.status_code!=200 or data.get('ok') is not True:raise ValueError('telegram_request_rejected')
        return data['result']


def write_private(path,values):
    # Exclusive creation prevents silently replacing old credentials or identity evidence.
    path=Path(path)
    if not (path.name=='.env' or path.name.startswith('.env.')):raise ValueError('private_dotenv_filename_required')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:
        for key,value in values.items():
            if '\n' in str(value) or '\r' in str(value):raise ValueError('invalid_multiline_value')
            f.write(f'{key}={json.dumps(str(value))}\n')


def discover(api,challenge,clock=time.monotonic,announce=print,owner_id=None,test_chat=False):
    me=api.call('getMe')
    if api.call('getWebhookInfo').get('url'):raise ValueError('webhook_active_stop_it_explicitly_before_polling')
    if test_chat and not owner_id:raise ValueError('owner_identity_required_first')
    announce(f'В {"отдельном тестовом групповом чате" if test_chat else "личном чате"} с новым ботом отправьте: /start {challenge}')
    deadline=clock()+120;offset=None
    while clock()<deadline:
        rows=api.call('getUpdates',{'timeout':15,'limit':100,'allowed_updates':['message'],**({'offset':offset} if offset is not None else {})})
        matches=[]
        for update in rows:
            offset=max(offset or 0,int(update['update_id'])+1)
            m=update.get('message') or {};actor=m.get('from') or {};chat=m.get('chat') or {}
            valid_chat=(chat.get('type') in ('group','supergroup') and str(actor.get('id'))==str(owner_id)) if test_chat else (chat.get('type')=='private' and str(chat.get('id'))==str(actor.get('id')))
            if m.get('text')==f'/start {challenge}' and valid_chat and not actor.get('is_bot'):
                found={'TELEGRAM_BOT_ID':str(me['id']),'TELEGRAM_CHAT_ID':str(chat['id']),'TELEGRAM_USER_ID':str(actor['id'])}
                if test_chat:found['TEST_TELEGRAM_CHAT_ID']=str(chat['id'])
                matches.append(found)
        if matches:
            if len({(m['TELEGRAM_USER_ID'],m['TELEGRAM_CHAT_ID']) for m in matches})!=1:raise ValueError('multiple_identity_candidates')
            return matches[0]
    raise ValueError('owner_start_not_received')


def configure(api,identity,webhook_url,secret,replace=False):
    import re
    p=urlparse(webhook_url)
    if p.scheme!='https' or not p.netloc or p.username or p.password or p.query or p.fragment:raise ValueError('invalid_webhook_url')
    if not re.fullmatch(r'[A-Za-z0-9_-]{32,256}',secret or ''):raise ValueError('webhook_secret_required')
    me=api.call('getMe')
    if str(me['id'])!=identity.get('TELEGRAM_BOT_ID'):raise ValueError('wrong_bot_for_identity')
    chat,user=identity.get('TELEGRAM_CHAT_ID',''),identity.get('TELEGRAM_USER_ID','')
    if not re.fullmatch(r'-?[1-9]\d*',chat) or not re.fullmatch(r'[1-9]\d*',user):raise ValueError('explicit_owner_ids_required')
    prior=api.call('getWebhookInfo').get('url')
    if prior and prior!=webhook_url and not replace:raise ValueError('different_webhook_requires_explicit_replacement')
    api.call('setMyCommands',{'commands':COMMANDS,'scope':{'type':'chat','chat_id':chat}})
    if not chat.startswith('-'):api.call('setChatMenuButton',{'chat_id':chat,'menu_button':{'type':'commands'}})
    api.call('setWebhook',{'url':webhook_url,'secret_token':secret,'allowed_updates':['message','callback_query'],'drop_pending_updates':False})
    if api.call('getWebhookInfo').get('url')!=webhook_url:raise ValueError('webhook_verification_failed')
    return {'commands_configured':True,'webhook_url_verified':True,'secret_delivery_requires_test':True}


def publish_github(repo,env,run=subprocess.run):
    import re
    if not re.fullmatch(r'[\w.-]+/[\w.-]+',repo):raise ValueError('invalid_repository')
    names=['CANVAS_API_URL','CANVAS_API_KEY','TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID','TELEGRAM_USER_ID','TEST_TELEGRAM_CHAT_ID','TELEGRAM_WEBHOOK_SECRET']
    for name in names:
        if env.get(name):
            result=run(['gh','secret','set',name,'--repo',repo],input=env[name],text=True,capture_output=True)
            if result.returncode:raise ValueError('github_secret_update_failed')
    return {'updated_secret_names':[n for n in names if env.get(n)],'production_enabled':False}


def main():
    logging.getLogger('httpx').setLevel(logging.WARNING);logging.getLogger('httpcore').setLevel(logging.WARNING)
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--env-file',type=Path,default=Path('.env.flymind.local'));p.add_argument('--identity',type=Path,default=Path('.env.flymind.identity'));p.add_argument('--test-identity',type=Path,default=Path('.env.flymind.test'))
    sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('credentials');sub.add_parser('preflight');d=sub.add_parser('discover');d.add_argument('--output',type=Path,default=Path('.env.flymind.identity'));d.add_argument('--test-chat',action='store_true')
    c=sub.add_parser('configure');c.add_argument('--webhook-url',required=True);c.add_argument('--replace-webhook',action='store_true');c.add_argument('--apply',action='store_true')
    g=sub.add_parser('publish-github');g.add_argument('--repo',default='fertur228/canvas-pusher');g.add_argument('--apply',action='store_true')
    b=sub.add_parser('bind-staging');b.add_argument('--apply',action='store_true')
    a=p.parse_args()
    try:
        from dotenv import dotenv_values,load_dotenv
        if a.action=='credentials':
            if not sys.stdin.isatty():raise ValueError('interactive_terminal_required')
            values={'CANVAS_API_URL':input('Canvas HTTPS origin: ').strip(),'CANVAS_API_KEY':getpass.getpass('New Canvas API token (hidden): '),'TELEGRAM_BOT_TOKEN':getpass.getpass('New Telegram bot token (hidden): '),'TELEGRAM_WEBHOOK_SECRET':secrets.token_urlsafe(32)}
            write_private(a.env_file,values);print('Private credential file created (0600); no credentials printed.');return
        load_dotenv(a.env_file,override=False)
        identity=dict(dotenv_values(a.identity)) if a.identity.exists() else {}
        if a.action=='preflight':
            from .live_check import check
            import asyncio
            result=asyncio.run(check());print(json.dumps(result));raise SystemExit(0 if result.get('status')=='verified' else 2)
        if a.action=='publish-github':
            if not a.apply:raise ValueError('explicit_apply_required')
            # Validate the replacement Canvas credential before publishing any secret.
            from .live_check import check
            import asyncio
            if asyncio.run(check()).get('status')!='verified':raise ValueError('canvas_preflight_failed_no_secret_changes')
            test_identity=dict(dotenv_values(a.test_identity)) if a.test_identity.exists() else {}
            test_chat=test_identity.get('TEST_TELEGRAM_CHAT_ID') or os.getenv('TEST_TELEGRAM_CHAT_ID')
            if not test_chat or test_chat==identity.get('TELEGRAM_CHAT_ID'):raise ValueError('separate_test_chat_required')
            print(json.dumps(publish_github(a.repo,{**os.environ,**identity,'TEST_TELEGRAM_CHAT_ID':test_chat})));return
        api=BotAPI(os.getenv('TELEGRAM_BOT_TOKEN'))
        if a.action=='discover':
            values=discover(api,secrets.token_urlsafe(16),owner_id=identity.get('TELEGRAM_USER_ID'),test_chat=a.test_chat);write_private(a.output,values);print('Numeric owner/bot IDs saved privately; webhook and production unchanged.')
        elif a.action=='configure':
            if not a.apply:raise ValueError('explicit_apply_required')
            print(json.dumps(configure(api,identity,a.webhook_url,os.getenv('TELEGRAM_WEBHOOK_SECRET'),a.replace_webhook)))
        elif a.action=='bind-staging':
            if not a.apply or os.getenv('FLYMIND_TARGET_ENV')!='staging':raise ValueError('explicit_staging_target_required')
            if identity.get('TEST_TELEGRAM_CHAT_ID')!=identity.get('TELEGRAM_CHAT_ID') or not identity.get('TEST_TELEGRAM_CHAT_ID'):raise ValueError('separate_test_identity_required')
            me=api.call('getMe')
            if str(me['id'])!=identity.get('TELEGRAM_BOT_ID'):raise ValueError('wrong_bot_for_identity')
            from supabase import create_client
            client=create_client(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SERVICE_KEY'])
            result=client.rpc('flymind_bind_bot',{'p_account':os.environ['FLYMIND_ACCOUNT_ID'],'p_bot':int(identity['TELEGRAM_BOT_ID']),'p_user':int(identity['TELEGRAM_USER_ID']),'p_chat':int(identity['TELEGRAM_CHAT_ID'])}).execute().data
            print(json.dumps({'staging_binding_verified':result is True,'historical_records_deleted':False}))
    except Exception as error:
        # Only fixed local validation labels, never third-party exception text or token URLs.
        allowed={'webhook_active_stop_it_explicitly_before_polling','owner_start_not_received','different_webhook_requires_explicit_replacement','canvas_preflight_failed_no_secret_changes','explicit_apply_required','explicit_staging_target_required','wrong_bot_for_identity'}
        raise SystemExit(str(error) if str(error) in allowed else 'Setup failed; verify private local configuration without sharing credentials') from None
if __name__=='__main__':main()
