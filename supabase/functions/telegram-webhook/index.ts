import { handler } from './handler.ts';
const env=(key:string)=>Deno.env.get(key)??'';
Deno.serve(handler({secret:env('TELEGRAM_WEBHOOK_SECRET'),chat:env('TELEGRAM_CHAT_ID'),
  user:env('TELEGRAM_USER_ID')||env('TELEGRAM_CHAT_ID'),bot:env('TELEGRAM_BOT_TOKEN'),
  url:env('SUPABASE_URL'),key:env('SUPABASE_SERVICE_ROLE_KEY'),githubToken:env('GITHUB_PAT'),
  repo:env('GITHUB_REPO'),ref:env('FLYMIND_WORKFLOW_REF')||'main',observatory:env('OBSERVATORY_URL')}));
