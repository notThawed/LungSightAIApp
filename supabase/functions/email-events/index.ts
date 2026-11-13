// email-events — Resend delivery webhook. Verifies the Svix-format signature
// and timestamp, then hands the minimal event to apply_email_provider_event(),
// which de-duplicates replays and updates delivery / bounce / suppression.
//
// Secrets: RESEND_WEBHOOK_SECRET. SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are
// provided by the platform.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

import { parseProviderEvent, verifyWebhook } from "../_shared/email/webhook.ts";

const MAX_BODY_BYTES = 64 * 1024;

Deno.serve(async (req) => {
  if (req.method !== "POST") return new Response("method not allowed", { status: 405 });

  const body = await req.text();
  if (body.length > MAX_BODY_BYTES) return new Response("too large", { status: 413 });

  const headers = {
    id: req.headers.get("svix-id"),
    timestamp: req.headers.get("svix-timestamp"),
    signature: req.headers.get("svix-signature"),
  };

  const verified = await verifyWebhook(
    Deno.env.get("RESEND_WEBHOOK_SECRET") ?? "",
    headers,
    body,
    Math.floor(Date.now() / 1000),
  );

  if (!verified.ok) {
    console.log(JSON.stringify({ level: "warn", msg: "webhook rejected", reason: verified.reason }));
    return new Response("invalid signature", { status: 401 });
  }

  const event = parseProviderEvent(headers.id as string, body);
  if (!event) return new Response("ignored", { status: 200 });

  const client = createClient(Deno.env.get("SUPABASE_URL") ?? "", Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "", {
    auth: { persistSession: false },
  });

  const { data, error } = await client.rpc("apply_email_provider_event", {
    p_event_id: event.eventId,
    p_type: event.type,
    p_message_id: event.messageId,
    p_bounce_type: event.bounceType,
    p_occurred_at: event.occurredAt,
  });

  if (error) {
    console.log(JSON.stringify({ level: "error", msg: "event apply failed", code: error.code ?? "unknown" }));
    return new Response("retry", { status: 500 });
  }

  console.log(JSON.stringify({ level: "info", msg: "event applied", type: event.type, result: data }));
  return new Response("ok", { status: 200 });
});
