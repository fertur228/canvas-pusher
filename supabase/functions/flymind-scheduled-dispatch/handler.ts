/** Cloud timer only. No Canvas/Telegram access; dispatches the existing guarded worker. */
export type Config = {
  secret: string;
  enabled: boolean;
  dryRun: boolean;
  account: string;
  url: string;
  key: string;
  pat: string;
  chat: string;
  user: string;
  bot: string;
};
const repo = "fertur228/canvas-pusher", workflow = "check_canvas.yml";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
export async function signature(secret: string, body: string) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return [
    ...new Uint8Array(
      await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(body)),
    ),
  ].map((x) => x.toString(16).padStart(2, "0")).join("");
}
function equal(a: string, b: string) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
export function handler(
  c: Config,
  request: typeof fetch = fetch,
  now: () => number = Date.now,
) {
  return async (req: Request): Promise<Response> => {
    const reply = (status: string, code = 200) =>
      Response.json({ status }, {
        status: code,
        headers: { "Cache-Control": "no-store" },
      });
    if (req.method !== "POST") return reply("method", 405);
    if (!c.enabled) return reply("disabled", 503);
    if (
      c.secret.length < 32 || !uuid.test(c.account) || !c.pat || !c.key ||
      c.url !== "https://irjasmzytjeohwfpdnrl.supabase.co" ||
      ![c.chat, c.user, c.bot].every((x) => /^\d+$/.test(x))
    ) return reply("configuration", 503);
    if (Number(req.headers.get("content-length") ?? 0) > 512) {
      return reply("body", 413);
    }
    const raw = await req.text();
    if (raw.length > 512) return reply("body", 413);
    const sig = req.headers.get("x-flymind-signature") ?? "";
    if (
      !/^[0-9a-f]{64}$/.test(sig) || !equal(sig, await signature(c.secret, raw))
    ) return reply("denied", 403);
    let body: { tick: string; time: number };
    try {
      body = JSON.parse(raw);
    } catch {
      return reply("body", 400);
    }
    if (
      !body || !uuid.test(body.tick) || !Number.isSafeInteger(body.time) ||
      Math.abs(now() / 1000 - body.time) > 90
    ) return reply("expired_or_invalid", 403);
    const db = async (path: string, method = "GET", data?: unknown) => {
      const r = await request(c.url + "/rest/v1/" + path, {
        method,
        headers: {
          apikey: c.key,
          Authorization: "Bearer " + c.key,
          "Content-Type": "application/json",
        },
        body: data === undefined ? undefined : JSON.stringify(data),
        signal: AbortSignal.timeout(10000),
      });
      if (!r.ok) throw new Error("database_unavailable");
      return r.status === 204 ? null : r.json();
    };
    const gh = async (path: string) => {
      const r = await request(
        "https://api.github.com/repos/" + repo + "/" + path,
        {
          headers: {
            Authorization: "Bearer " + c.pat,
            Accept: "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
          },
          signal: AbortSignal.timeout(10000),
        },
      );
      if (!r.ok) throw new Error("github_unavailable");
      return r.json();
    };
    let claimed = false;
    const finish = async (state: string, reason: string) => {
      await db(
        "flymind_schedule_ticks?tick=eq." + body.tick + "&state=eq.claimed",
        "PATCH",
        { state, reason },
      );
      return reply(reason);
    };
    try {
      const a = await db(
        "flymind_accounts?select=id,enabled,initialized_at,canvas_origin,telegram_chat_id,telegram_user_id,telegram_bot_id&id=eq." +
          c.account,
      );
      if (
        a.length !== 1 || !a[0].enabled || !a[0].initialized_at ||
        a[0].canvas_origin !== "https://canvas.narxoz.kz" ||
        String(a[0].telegram_chat_id) !== c.chat ||
        String(a[0].telegram_user_id) !== c.user ||
        String(a[0].telegram_bot_id) !== c.bot
      ) return reply("owner_binding", 503);
      const names = [
        "CANVAS_WORKER_ENABLED",
        "FLYMIND_ENABLED",
        "DELIVERY_MODE",
        "FLYMIND_PRODUCTION_AUTHORIZED",
        "FLYMIND_MODE",
        "FLYMIND_ACCOUNT_ID",
      ];
      const expected = [
        "true",
        "true",
        "production",
        "true",
        "shadow",
        c.account,
      ];
      const vars = await Promise.all(
        names.map((n) => gh("actions/variables/" + n)),
      );
      if (vars.some((v, i) => v.value !== expected[i])) {
        return reply("gates_closed");
      }
      const wf = await gh("actions/workflows/" + workflow);
      if (wf.state !== "active") return reply("workflow_disabled", 503);
      const code = await gh(
        "contents/.github/workflows/" + workflow + "?ref=main",
      );
      if (
        code.encoding !== "base64" ||
        !atob(code.content.replace(/\s/g, "")).includes("scheduler_tick:")
      ) return reply("workflow_not_upgraded", 503);
      claimed = await db("rpc/flymind_schedule_claim", "POST", {
        p_account: c.account,
        p_tick: body.tick,
      });
      if (!claimed) return reply("duplicate_or_recent");
      const runs =
        (await gh("actions/workflows/" + workflow + "/runs?per_page=30"))
          .workflow_runs;
      // A provider may retain a stale queued ghost. Fail closed on recent active jobs;
      // worker timeout is 15 minutes; older listings have no executing scanner proof.
      if (
        runs.some((r: { status: string; created_at: string }) =>
          now() - Date.parse(r.created_at) < 20 * 60000 &&
          r.status !== "completed"
        )
      ) return await finish("skipped", "worker_active");
      const health = await db(
        "flymind_health?select=last_attempt&account_id=eq." + c.account,
      );
      if (
        health[0]?.last_attempt &&
        now() - Date.parse(health[0].last_attempt) < 4 * 60000
      ) return await finish("skipped", "recent_scan");
      if (c.dryRun) return await finish("dry_run", "dry_run");
      // Persist uncertainty BEFORE the single POST. A crash or timeout must not retry this tick.
      await db(
        "flymind_schedule_ticks?tick=eq." + body.tick + "&state=eq.claimed",
        "PATCH",
        { state: "ambiguous", reason: "dispatch_started" },
      );
      let r: Response;
      try {
        r = await request(
          "https://api.github.com/repos/" + repo + "/actions/workflows/" +
            workflow + "/dispatches",
          {
            method: "POST",
            headers: {
              Authorization: "Bearer " + c.pat,
              Accept: "application/vnd.github+json",
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              ref: "main",
              inputs: { scheduler_tick: body.tick },
            }),
            signal: AbortSignal.timeout(15000),
          },
        );
      } catch {
        return reply("dispatch_uncertain", 502);
      }
      const state = r.status === 204
        ? "accepted"
        : r.status >= 500
        ? "ambiguous"
        : "failed";
      await db(
        "flymind_schedule_ticks?tick=eq." + body.tick + "&state=eq.ambiguous",
        "PATCH",
        { state, reason: "github_" + r.status },
      );
      return reply(state, r.status === 204 ? 202 : 502);
    } catch {
      // Never echo exception messages, headers, responses, identities or academic data.
      if (claimed) {
        try {
          await finish("failed", "preflight_unavailable");
        } catch { /* persisted claim/ambiguity still prevents replay */ }
      }
      return reply("dependency_unavailable", 503);
    }
  };
}
