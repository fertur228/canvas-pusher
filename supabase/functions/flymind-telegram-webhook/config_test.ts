import {flymindConfig} from './config.ts';
import {handler} from '../telegram-webhook/handler.ts';

Deno.test('isolated FlyMind function cannot use legacy credentials or an unverified bot',async()=>{
  const legacy:Record<string,string>={TELEGRAM_BOT_TOKEN:'101:legacy',TELEGRAM_WEBHOOK_SECRET:'secret',TELEGRAM_CHAT_ID:'123',TELEGRAM_USER_ID:'123',SUPABASE_URL:'https://db.invalid',SUPABASE_SERVICE_ROLE_KEY:'synthetic'};
  const env=(values:Record<string,string>)=>(name:string)=>values[name]??'';
  let calls=0;const forbidden=(async()=>{calls++;throw new Error('unexpected IO');}) as typeof fetch;
  const request=()=>new Request('https://webhook.invalid',{method:'POST'});
  const old=flymindConfig(env(legacy));
  if((await handler(old,forbidden)(request())).status!==503)throw new Error('legacy credential fallback');
  const mismatch=flymindConfig(env({...legacy,FLYMIND_TELEGRAM_BOT_TOKEN:'102:new',FLYMIND_TELEGRAM_BOT_ID:'101',FLYMIND_TELEGRAM_WEBHOOK_SECRET:'secret',FLYMIND_TELEGRAM_CHAT_ID:'123',FLYMIND_TELEGRAM_USER_ID:'123'}));
  if((await handler(mismatch,forbidden)(request())).status!==503||calls!==0)throw new Error('unverified bot accepted');
});
