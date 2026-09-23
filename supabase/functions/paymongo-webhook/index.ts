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
// CONSTANTS
// ============================================================

const CYCLE_DAYS: Record<string, number> = {
  "Monthly": 30,
  "Yearly": 365,
};


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
// EXTEND SUBSCRIPTION
// ============================================================

async function extendSubscription(
  hospitalSubscriptionId: string,
  billingCycle: string,
): Promise<{ success: boolean; message: string; new_end_date?: string }> {

  try {

    // ------------------------------------------
    // 1. Validate billing cycle
    // ------------------------------------------

    const cycleDays = CYCLE_DAYS[billingCycle];

    if (!cycleDays) {
      return {
        success: false,
        message: `Unknown billing cycle: ${billingCycle}`,
      };
    }

    // ------------------------------------------
    // 2. Fetch the subscription
    // ------------------------------------------

    const { data: subscription, error: subErr } = await supabase
      .from("hospital_subscriptions")
      .select("hospital_subscription_id, end_date, billing_cycle")
      .eq("hospital_subscription_id", hospitalSubscriptionId)
      .single();

    if (subErr || !subscription) {
      return {
        success: false,
        message: `Subscription not found: ${subErr?.message ?? "no data"}`,
      };
    }

    // ------------------------------------------
    // 3. Compute the new end_date
    //    UTC-based, matching the Postgres date column
    // ------------------------------------------

    const now = new Date();
    const todayUTC = new Date(
      Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())
    );

    const oldEndDateStr = subscription.end_date;
    let baseDate: Date;

    if (oldEndDateStr) {

      // Parse "YYYY-MM-DD" as UTC midnight
      const [y, m, d] = oldEndDateStr.split("-").map(Number);
      const oldEndDate = new Date(Date.UTC(y, m - 1, d));

      // If end_date >= today (UTC) -> extend from end_date
      // Else -> extend from today
      baseDate = oldEndDate >= todayUTC ? oldEndDate : todayUTC;

    } else {

      baseDate = todayUTC;
    }

    const newEndDate = new Date(
      baseDate.getTime() + cycleDays * 24 * 60 * 60 * 1000
    );

    const newEndDateStr = newEndDate.toISOString().slice(0, 10);
    const nowISO = new Date().toISOString();

    // ------------------------------------------
    // 4. Update the subscription
    // ------------------------------------------

    const { error: updateErr } = await supabase
      .from("hospital_subscriptions")
      .update({
        end_date:        newEndDateStr,
        status:          "Active",
        last_renewed_at: nowISO,
        updated_at:      nowISO,
      })
      .eq("hospital_subscription_id", hospitalSubscriptionId);

    if (updateErr) {
      return {
        success: false,
        message: `Failed to extend subscription: ${updateErr.message}`,
      };
    }

    return {
      success: true,
      message: "Subscription extended.",
      new_end_date: newEndDateStr,
    };

  } catch (err) {

    return {
      success: false,
      message: `Exception: ${String(err)}`,
    };
  }
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
  //    (idempotent - only flips from 'pending')
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
    // Return 200 so PayMongo doesn't keep retrying - the row either
    // doesn't exist or was already handled
    return new Response("noop", { status: 200 });
  }

  // ------------------------------------------
  // 4. Branch on payment type
  // ------------------------------------------

  if (
    payment.payment_type === "renewal" &&
    payment.hospital_subscription_id
  ) {

    // ------------------------------------------
    // Renewal path
    // ------------------------------------------

    console.log(
      `Processing renewal for subscription ${payment.hospital_subscription_id}`
    );

    const extendResult = await extendSubscription(
      payment.hospital_subscription_id,
      payment.billing_cycle,
    );

    if (!extendResult.success) {
      console.error("Failed to extend subscription:", extendResult.message);
      // Return 500 so PayMongo retries the webhook
      return new Response("extension failed", { status: 500 });
    }

    console.log(`✅ Subscription extended to ${extendResult.new_end_date}`);

  } else {

    // ------------------------------------------
    // Application payment path (existing behavior)
    // ------------------------------------------

    const applicationId = payment.application_id;

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
  }

  return new Response("ok", { status: 200 });
});