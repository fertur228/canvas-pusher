import { type Config, handler, signature } from "./handler.ts";
function assert(v: unknown) {
  if (!v) throw new Error("assertion failed");
}
const account = "00000000-0000-0000-0000-000000000001",
  tick = "00000000-0000-0000-0000-000000000002";
const now = 1792425600000;
const c: Config = {
  secret: "test-only-secret-at-least-32-characters",
  enabled: true,
  dryRun: false,
  account,
  url: "https://irjasmzytjeohwfpdnrl.supabase.co",
  key: "synthetic-service",
  pat: "synthetic-pat",
  chat: "123",
  user: "123",
  bot: "456",
};
async function req(t = tick, time = now / 1000) {
  const body = JSON.stringify({ tick: t, time });
  return new Request("https://example.invalid", {
    method: "POST",
    body,
    headers: { "x-flymind-signature": await signature(c.secret, body) },
  });
}
function fixture(
  options: {
    gate?: boolean;
    owner?: boolean;
    active?: boolean;
    recent?: boolean;
    timeout?: boolean;
    dbFail?: boolean;
    http?: number;
  } = {},
) {
  let sends = 0, claimed = false, state = "";
  const calls: string[] = [];
  const request =
    (async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      calls.push(url);
      if (options.dbFail && url.includes("/rest/")) {
        return new Response(null, { status: 503 });
      }
      if (url.includes("flymind_accounts")) {
        return Response.json([{
          id: account,
          enabled: true,
          initialized_at: "2026-10-18T00:00:00Z",
          canvas_origin: "https://canvas.narxoz.kz",
          telegram_chat_id: options.owner === false ? 999 : 123,
          telegram_user_id: 123,
          telegram_bot_id: 456,
        }]);
      }
      if (url.includes("/actions/variables/")) {
        const name = url.split("/").pop()!;
        return Response.json({
          value: ({
            CANVAS_WORKER_ENABLED: options.gate === false ? "false" : "true",
            FLYMIND_ENABLED: "true",
            DELIVERY_MODE: "production",
            FLYMIND_PRODUCTION_AUTHORIZED: "true",
            FLYMIND_MODE: "shadow",
            FLYMIND_ACCOUNT_ID: account,
          } as Record<string, string>)[name],
        });
      }
      if (url.includes("/contents/")) {
        return Response.json({
          encoding: "base64",
          content: btoa("scheduler_tick:"),
        });
      }
      if (url.endsWith("/check_canvas.yml")) {
        return Response.json({ state: "active" });
      }
      if (url.includes("schedule_claim")) {
        if (claimed) return Response.json(false);
        claimed = true;
        state = "claimed";
        return Response.json(true);
      }
      if (url.includes("schedule_ticks")) {
        const next = JSON.parse(String(init?.body)).state;
        const expected = new URL(url).searchParams.get("state")?.slice(3);
        if (state === expected) state = next;
        return new Response(null, { status: 204 });
      }
      if (url.includes("/runs?")) {
        return Response.json({
          workflow_runs: options.active
            ? [{
              status: "in_progress",
              created_at: new Date(now - 1000).toISOString(),
            }]
            : [],
        });
      }
      if (url.includes("flymind_health")) {
        return Response.json([{
          last_attempt: options.recent
            ? new Date(now - 1000).toISOString()
            : null,
        }]);
      }
      if (url.endsWith("/dispatches")) {
        sends++;
        assert(state === "ambiguous");
        const b = JSON.parse(String(init?.body));
        assert(
          b.ref === "main" && b.inputs.scheduler_tick === tick &&
            !b.inputs.manual_request_id,
        );
        if (options.timeout) throw new Error("lost response");
        return new Response(null, { status: options.http ?? 204 });
      }
      throw new Error("unexpected request");
    }) as typeof fetch;
  return {
    request,
    get sends() {
      return sends;
    },
    get state() {
      return state;
    },
    calls,
  };
}
Deno.test("unauthenticated, expired, malformed and disabled timer callers perform no I/O", async () => {
  const f = fixture(), h = handler(c, f.request, () => now);
  assert(
    (await h(
      new Request("https://example.invalid", { method: "POST", body: "{}" }),
    )).status === 403,
  );
  assert((await h(await req(tick, now / 1000 - 91))).status === 403);
  assert((await h(await req("bad"))).status === 403);
  assert(
    (await handler({ ...c, enabled: false }, f.request, () => now)(await req()))
      .status === 503,
  );
  assert(f.calls.length === 0);
});
Deno.test("exact owner binding and activation gates fail closed", async () => {
  for (const options of [{ gate: false }, { owner: false }, { dbFail: true }]) {
    const f = fixture(options);
    await handler(c, f.request, () => now)(await req());
    assert(f.sends === 0);
  }
});
Deno.test("concurrent/replayed ticks dispatch exactly once with durable uncertainty before POST", async () => {
  const f = fixture(), h = handler(c, f.request, () => now);
  await Promise.all([h(await req()), h(await req())]);
  await h(await req());
  assert(f.sends === 1 && f.state === "accepted");
});
Deno.test("ambiguous network/server outcomes are never retried for the same tick", async () => {
  for (const options of [{ timeout: true }, { http: 503 }]) {
    const f = fixture(options), h = handler(c, f.request, () => now);
    await h(await req());
    await h(await req());
    assert(f.sends === 1 && f.state === "ambiguous");
  }
});
Deno.test("active worker, recent scan and dry run suppress dispatch", async () => {
  for (const options of [{ active: true }, { recent: true }, {}]) {
    const f = fixture(options);
    await handler({ ...c, dryRun: true }, f.request, () => now)(await req());
    assert(f.sends === 0 && ["skipped", "dry_run"].includes(f.state));
  }
});
Deno.test("GitHub credential denial is recorded as failed, not successful delivery", async () => {
  const f = fixture({ http: 401 });
  const r = await handler(c, f.request, () => now)(await req());
  assert(r.status === 502 && f.state === "failed" && f.sends === 1);
});
