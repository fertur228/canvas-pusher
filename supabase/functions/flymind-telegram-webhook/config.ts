import type {Config} from '../telegram-webhook/handler.ts';

/** Project-wide Edge secrets are shared: never fall back to the legacy bot's keys. */
export function flymindConfig(env:(name:string)=>string):Config {
  const bot=env('FLYMIND_TELEGRAM_BOT_TOKEN');
  const identityMatches=/^\d+:/.test(bot)&&env('FLYMIND_TELEGRAM_BOT_ID')===bot.split(':')[0];
  return {
    secret:identityMatches?env('FLYMIND_TELEGRAM_WEBHOOK_SECRET'):'',
    chat:env('FLYMIND_TELEGRAM_CHAT_ID'),user:env('FLYMIND_TELEGRAM_USER_ID'),bot,
    url:env('SUPABASE_URL'),key:env('SUPABASE_SERVICE_ROLE_KEY'),
    // The existing Canvas project already holds a dispatch credential server-side.
    // Reuse it in place; do not export a broader personal CLI token to Edge secrets.
    githubToken:env('FLYMIND_GITHUB_PAT')||env('GITHUB_PAT'),repo:env('FLYMIND_GITHUB_REPO'),
    ref:env('FLYMIND_WORKFLOW_REF')||'main',observatory:env('FLYMIND_OBSERVATORY_URL'),
    manualEnabled:env('FLYMIND_MANUAL_SYNC_ENABLED')==='true',
  };
}
