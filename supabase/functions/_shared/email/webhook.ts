// Verification and parsing of provider (Resend / Svix-format) webhooks.
//
// Signed content: `${svix-id}.${svix-timestamp}.${raw body}`, HMAC-SHA256 with
// the base64 part of the "whsec_..." secret. The svix-signature header holds
// one or more space-separated "v1,<base64>" values. Timestamps outside the
// tolerance are rejected; replays inside it are rejected by the database
// (email_provider_events primary key).

export const TOLERANCE_SECONDS = 5 * 60;

export type WebhookHeaders = {
  id: string | null;
  timestamp: string | null;
  signature: string | null;
};

export type VerifyResult = { ok: true } | { ok: false; reason: string };

function base64ToBytes(value: string): Uint8Array {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function signPayload(secret: string, id: string, timestamp: string, body: string): Promise<string> {
  const keyBytes = base64ToBytes(secret.startsWith("whsec_") ? secret.slice(6) : secret);
  const key = await crypto.subtle.importKey("raw", keyBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(`${id}.${timestamp}.${body}`));
  return bytesToBase64(new Uint8Array(mac));
}

export async function verifyWebhook(
  secret: string,
  headers: WebhookHeaders,
  body: string,
  nowSeconds: number,
): Promise<VerifyResult> {
  if (!secret) return { ok: false, reason: "not_configured" };
  if (!headers.id || !headers.timestamp || !headers.signature) return { ok: false, reason: "missing_headers" };

  const timestamp = Number(headers.timestamp);
  if (!Number.isFinite(timestamp)) return { ok: false, reason: "bad_timestamp" };
  if (Math.abs(nowSeconds - timestamp) > TOLERANCE_SECONDS) return { ok: false, reason: "timestamp_out_of_range" };

  let expected: string;
  try {
    expected = await signPayload(secret, headers.id, headers.timestamp, body);
  } catch {
    return { ok: false, reason: "bad_secret" };
  }

  const candidates = headers.signature
    .split(" ")
    .map((part) => part.trim())
    .filter((part) => part.startsWith("v1,"))
    .map((part) => part.slice(3));

  return candidates.some((candidate) => constantTimeEqual(candidate, expected))
    ? { ok: true }
    : { ok: false, reason: "bad_signature" };
}

export type ProviderEvent = {
  eventId: string;
  type: string;
  messageId: string;
  bounceType: string | null;
  occurredAt: string | null;
};

const HANDLED = new Set(["email.delivered", "email.bounced", "email.complained"]);

/** Extract only the fields we store; returns null for events we ignore. */
export function parseProviderEvent(eventId: string, body: string): ProviderEvent | null {
  let payload: any;
  try {
    payload = JSON.parse(body);
  } catch {
    return null;
  }

  const type = typeof payload?.type === "string" ? payload.type : "";
  const messageId = typeof payload?.data?.email_id === "string" ? payload.data.email_id : "";

  if (!HANDLED.has(type) || !messageId || messageId.length > 128) return null;

  const bounceType = typeof payload?.data?.bounce?.type === "string" ? payload.data.bounce.type.slice(0, 20) : null;
  const createdAt = typeof payload?.created_at === "string" && !Number.isNaN(Date.parse(payload.created_at))
    ? new Date(payload.created_at).toISOString()
    : null;

  return { eventId: eventId.slice(0, 128), type, messageId, bounceType, occurredAt: createdAt };
}
