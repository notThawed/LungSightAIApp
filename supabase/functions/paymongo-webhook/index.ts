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

  // The signed payload is "<timestamp>.<rawBody>"
  const signedPayload = `${timestamp}.${rawBody}`;

  // The signature to compare: prefer "li" (live), fall back to "te" (test)
  const providedSig = parts["li"] || parts["te"];
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
// MAIN HANDLER
// ============================================================

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
  console.error("Header:", signatureHeader);
  console.error("Secret length:", PAYMONGO_WEBHOOK_SECRET.length);
  console.error("Secret prefix:", PAYMONGO_WEBHOOK_SECRET.slice(0, 12));
  console.error("Body length:", rawBody.length);
  console.error("Body preview:", rawBody.slice(0, 200));
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

  // ------------------------------------------
  // 3. Find payment row and update
  //    (idempotent — only flips from 'pending')
  // ------------------------------------------

  const { data: payment, error: updateErr } = await supabase
    .from("payments")
    .update({
      status: "paid",
      paid_at: new Date().toISOString(),
      payment_method: paymentData?.attributes?.payment_method_used ?? null,
      provider_payment_id: paymentData?.attributes?.payment_intent?.id ?? null,
      raw_payload: event,
      updated_at: new Date().toISOString(),
    })
    .eq("provider_reference", checkoutId)
    .eq("status", "pending")
    .select()
    .single();

  if (updateErr || !payment) {
    console.error("Payment not found or already processed:", updateErr);
    // Return 200 so PayMongo doesn't keep retrying — the row either
    // doesn't exist or was already handled
    return new Response("noop", { status: 200 });
  }

  const applicationId = payment.application_id;

  // ------------------------------------------
  // 4. Update application → Pending / paid
  // ------------------------------------------

  const { error: appErr } = await supabase
    .from("hospital_applications")
    .update({
      application_status: "Pending",
      payment_status: "paid",
    })
    .eq("application_id", applicationId);

  if (appErr) {
    console.error("Failed to update application:", appErr);
    // Payment is recorded; app update can be retried manually
  }

  console.log(`✅ Payment processed for application ${applicationId}`);

  return new Response("ok", { status: 200 });
});