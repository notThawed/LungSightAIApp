import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { crypto } from "https://deno.land/std@0.168.0/crypto/mod.ts";


// ============================================================
// ENV
// ============================================================

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const PAYMONGO_WEBHOOK_SECRET = Deno.env.get("PAYMONGO_WEBHOOK_SECRET")!;


const supabase = createClient(
  SUPABASE_URL,
  SUPABASE_SERVICE_ROLE_KEY,
);


// ============================================================
// SIGNATURE VERIFICATION
// ============================================================

async function verifySignature(
  rawBody: string,
  signatureHeader: string | null,
): Promise<boolean> {

  if (!signatureHeader) return false;

  // PayMongo sends: t=<timestamp>,te=<test_sig>,li=<live_sig>
  const parts: Record<string, string> = {};
  for (const pair of signatureHeader.split(",")) {
    const [k, v] = pair.split("=");
    if (k && v) parts[k.trim()] = v.trim();
  }

  const timestamp = parts["t"];
  if (!timestamp) return false;
  const unixSeconds = Number(timestamp);
  if (!Number.isSafeInteger(unixSeconds) || Math.abs(Math.floor(Date.now() / 1000) - unixSeconds) > 300) {
    return false;
  }

  // The signed payload is "<timestamp>.<rawBody>"
  const signedPayload = `${timestamp}.${rawBody}`;

  // The signature to compare: prefer "li" (live), fall back to "te" (test)
  const webhookMode = Deno.env.get("PAYMONGO_WEBHOOK_MODE");
  if (webhookMode !== "test" && webhookMode !== "live") return false;
  const providedSig = webhookMode === "live" ? parts["li"] : parts["te"];
  if (!providedSig) return false;

  // HMAC-SHA256 the signed payload with the webhook secret
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(PAYMONGO_WEBHOOK_SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );

  const mac = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(signedPayload),
  );

  // Convert to hex
  const expectedSig = Array.from(new Uint8Array(mac))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  // Constant-time-ish comparison
  if (expectedSig.length !== providedSig.length) return false;
  let mismatch = 0;
  for (let i = 0; i < expectedSig.length; i++) {
    mismatch |= expectedSig.charCodeAt(i) ^ providedSig.charCodeAt(i);
  }
  return mismatch === 0;
}


// ============================================================
// AUDIT LOG
// ============================================================
//
// System events (no actor). Metadata holds identifiers only.
// A failed audit write never changes the webhook response.

async function recordAudit(row: {
  event_type: string;
  outcome: "success" | "failure";
  hospital_id: string | null;
  target_type: string;
  target_id: string | null;
  metadata: Record<string, string>;
  idempotency_key: string;
}): Promise<void> {

  const { error } = await supabase
    .from("audit_logs")
    .insert({ actor_user_id: null, ...row });

  if (error && error.code !== "23505") {
    console.error(`audit write failed for ${row.event_type}: ${error.code}`);
  }
}


// ============================================================
// MAIN HANDLER
// ============================================================


// Phase 2E: independently verify the paid checkout with PayMongo.
// Fail closed if PayMongo's checkout response does not expose payment evidence.
async function verifyPayMongoCheckout(checkoutId: string, expectedAmount: unknown, expectedCurrency: unknown, expectedPaymentId: string): Promise<boolean> {
  const key = Deno.env.get("PAYMONGO_SECRET_KEY");
  const mode = Deno.env.get("PAYMONGO_WEBHOOK_MODE");
  if (!key || (mode !== "test" && mode !== "live")) return false;
  if (mode === "test" && !key.startsWith("sk_test_")) return false;
  if (mode === "live" && !key.startsWith("sk_live_")) return false;
  if (!/^cs_[A-Za-z0-9_-]+$/.test(checkoutId)) return false;

  const amount = Number(expectedAmount);
  if (!Number.isFinite(amount) || amount <= 0 || !Number.isInteger(Math.round(amount * 100))) return false;
  if (String(expectedCurrency).toUpperCase() !== "PHP") return false;

  const auth = btoa(`${key}:`);
  const response = await fetch(`https://api.paymongo.com/v1/checkout_sessions/${encodeURIComponent(checkoutId)}`, {
    method: "GET",
    headers: { Authorization: `Basic ${auth}`, Accept: "application/json" },
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) return false;
  const doc = await response.json();
  if (doc?.data?.id !== checkoutId) return false;
  const attrs = doc?.data?.attributes;
  if (!attrs || typeof attrs !== "object") return false;
  const metadata = attrs.metadata;
  if (!metadata || String(metadata.payment_id) !== expectedPaymentId) return false;

  // PayMongo's checkout session may include payment resources. Require one
  // unambiguously paid payment whose amount is expressed in centavos.
  const payments = attrs.payments;
  if (!Array.isArray(payments) || payments.length !== 1) return false;
  const payment = payments[0];
  const paid = payment?.attributes ?? payment;
  if (paid?.status !== "paid") return false;
  if (String(paid.currency).toUpperCase() !== "PHP") return false;
  if (!Number.isSafeInteger(paid.amount)) return false;
  return paid.amount === Math.round(amount * 100);
}

serve(async (req) => {

  // Only accept POST
  if (req.method !== "POST") {
    return new Response("method not allowed", { status: 405 });
  }

  const rawBody = await req.text();
  const signatureHeader = req.headers.get("paymongo-signature");

  // ------------------------------------------
  // 1. Verify signature
  // ------------------------------------------

  const valid = await verifySignature(rawBody, signatureHeader);

  if (!valid) {
    console.error("=== SIGNATURE MISMATCH ===");
    return new Response("invalid signature", { status: 401 });
  }

  // ------------------------------------------
  // 2. Parse the event
  // ------------------------------------------

  let event: any;
  try {
    event = JSON.parse(rawBody);
  } catch {
    return new Response("bad json", { status: 400 });
  }

  const eventType = event?.data?.attributes?.type;
  const paymentData = event?.data?.attributes?.data;

  // We only care about paid events for now
  if (eventType !== "checkout_session.payment.paid") {
    console.log(`Ignoring event type: ${eventType}`);
    return new Response("ignored", { status: 200 });
  }

  const checkoutId = paymentData?.id;
  if (!checkoutId) {
    console.error("No checkout id in payload");
    return new Response("missing checkout id", { status: 400 });
  }

  console.log(`Processing paid event for checkout: ${checkoutId}`);

  // Phase 2E: paid renewal/upgrade is finalized atomically in Postgres.
  // A paid payment row must NEVER be committed before its subscription change.
  const { data: classified, error: classifyError } = await supabase
    .from("payments")
    .select("payment_type,payment_id,amount,currency")
    .eq("provider_reference", checkoutId)
    .maybeSingle();

  if (classifyError) {
    console.error("Payment lookup failed:", classifyError.code);
    return new Response("payment lookup failed", { status: 500 });
  }
  if (!classified) {
    // Unknown checkout: retry in case payment row is not yet committed.
    return new Response("unknown checkout", { status: 500 });
  }

  // Independent provider verification applies to ALL payment types.
  // Do not mark a payment paid or update a subscription/application on failure.
  let verified = false;
  try {
    verified = await verifyPayMongoCheckout(
      checkoutId, classified.amount, classified.currency, String(classified.payment_id),
    );
  } catch (err) {
    console.error("PayMongo checkout verification unavailable", err instanceof Error ? err.name : "unknown");
  }
  if (!verified) {
    console.error("PayMongo checkout verification failed for checkout", checkoutId);
    return new Response("provider verification failed", { status: 500 });
  }

  if (classified.payment_type === "renewal" || classified.payment_type === "upgrade") {
    const { data: result, error: finalizeError } = await supabase.rpc(
      "ls_finalize_subscription_payment_v2",
      {
        p_checkout_id: checkoutId,
        p_payload: event,
        p_payment_method: paymentData?.attributes?.payment_method_used ?? null,
        p_provider_payment_id: paymentData?.attributes?.payment_intent?.id ?? null,
      },
    );
    if (finalizeError) {
      console.error("Atomic subscription payment failed:", finalizeError.code);
      return new Response("finalization failed", { status: 500 });
    }
    if (!result || result.success !== true) {
      console.error("Atomic payment requires reconciliation or failed", result);
      return new Response("manual reconciliation required", { status: 500 });
    }
    console.log("Atomic subscription payment completed");
    return new Response("ok", { status: 200 });
  }

  if (classified.payment_type !== "application") {
    console.error("Unknown payment type:", classified.payment_type);
    return new Response("unsupported payment type", { status: 500 });
  }

  // Phase 2E: atomic application payment finalization.
  // Provider verification above MUST have succeeded before calling this RPC.
  const { data: result, error: finalizeError } = await supabase.rpc(
    "ls_finalize_application_payment_v1",
    {
      p_checkout_id: checkoutId,
      p_payload: event,
      p_payment_method: paymentData?.attributes?.payment_method_used ?? null,
      p_provider_payment_id: paymentData?.attributes?.payment_intent?.id ?? null,
    },
  );
  if (finalizeError) {
    console.error("Atomic application payment failed:", finalizeError.code);
    return new Response("application finalization failed", { status: 500 });
  }
  if (!result || result.success !== true) {
    console.error("Application payment needs reconciliation:", result);
    return new Response("manual reconciliation required", { status: 500 });
  }
  // Preserve application payment audit behavior. Failure does not undo a
  // committed payment; the existing audit helper handles duplicate keys.
  const { data: applicationPayment, error: applicationLookupError } = await supabase
    .from("payments")
    .select("application_id,hospital_id,payment_id")
    .eq("provider_reference", checkoutId)
    .single();
  if (!applicationLookupError && applicationPayment?.application_id) {
    await recordAudit({
      event_type: "hospital_application.payment_received",
      outcome: "success",
      hospital_id: applicationPayment.hospital_id ?? null,
      target_type: "hospital_application",
      target_id: applicationPayment.application_id,
      metadata: { payment_id: applicationPayment.payment_id },
      idempotency_key: `hospital_application.payment_received:payment:${applicationPayment.payment_id}`,
    });
  }
  return new Response("ok", { status: 200 });
});