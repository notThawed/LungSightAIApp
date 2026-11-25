// email-worker — invoked once a minute by pg_cron (via pg_net) with the
// EMAIL_WORKER_SECRET header. Sends queued emails; never changes business data.
//
// Secrets (Edge Function secrets only): EMAIL_WORKER_SECRET, EMAIL_PROVIDER,
// RESEND_API_KEY, EMAIL_FROM, EMAIL_REPLY_TO, EMAIL_REDIRECT_TO, APP_BASE_URL.
// SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are provided by the platform.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

import { createProvider } from "../_shared/email/providers.ts";
import { SupabaseEmailStore } from "../_shared/email/store.ts";
import { runWorker } from "../_shared/email/worker.ts";
import { sanitizeError } from "../_shared/email/policy.ts";

const env = (name: string) => Deno.env.get(name) ?? "";

function secretMatches(provided: string | null, expected: string): boolean {
  if (!provided || !expected || provided.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= provided.charCodeAt(i) ^ expected.charCodeAt(i);
  return diff === 0;
}

const log = (line: Record<string, unknown>) => console.log(JSON.stringify(line));

Deno.serve(async (req) => {
  if (req.method !== "POST") return new Response("method not allowed", { status: 405 });

  if (!secretMatches(req.headers.get("x-worker-secret"), env("EMAIL_WORKER_SECRET"))) {
    return new Response("unauthorized", { status: 401 });
  }

  const client = createClient(env("SUPABASE_URL"), env("SUPABASE_SERVICE_ROLE_KEY"), {
    auth: { persistSession: false },
  });

  const provider = createProvider(
    {
      EMAIL_PROVIDER: env("EMAIL_PROVIDER"),
      RESEND_API_KEY: env("RESEND_API_KEY"),
      EMAIL_FROM: env("EMAIL_FROM"),
      EMAIL_REPLY_TO: env("EMAIL_REPLY_TO"),
    },
    fetch,
    log,
  );

  try {
    const summary = await runWorker({
      store: new SupabaseEmailStore(client),
      provider,
      workerId: `edge-${crypto.randomUUID().slice(0, 8)}`,
      appBaseUrl: env("APP_BASE_URL"),
      redirectTo: env("EMAIL_REDIRECT_TO") || null,
      log,
    });
    log({ level: "info", msg: "worker run", provider: provider.name, ...summary });
    return new Response(JSON.stringify({ ok: true, provider: provider.name, ...summary }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    log({ level: "error", msg: "worker run failed", error: sanitizeError(error) });
    return new Response(JSON.stringify({ ok: false }), { status: 500 });
  }
});
