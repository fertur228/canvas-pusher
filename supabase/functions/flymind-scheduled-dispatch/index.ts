import { handler } from "./handler.ts";
const env = (n: string) => Deno.env.get(n) ?? "";
Deno.serve(handler({
  secret: env("FLYMIND_SCHEDULE_SECRET"),
  enabled: env("FLYMIND_SCHEDULE_ENABLED") === "true",
  dryRun: env("FLYMIND_SCHEDULE_DRY_RUN") !== "false",
  account: env("FLYMIND_SCHEDULE_ACCOUNT_ID"),
  url: env("SUPABASE_URL"),
  key: env("SUPABASE_SERVICE_ROLE_KEY"),
  pat: env("FLYMIND_GITHUB_PAT"),
  chat: env("FLYMIND_TELEGRAM_CHAT_ID"),
  user: env("FLYMIND_TELEGRAM_USER_ID"),
  bot: env("FLYMIND_TELEGRAM_BOT_ID"),
}));
