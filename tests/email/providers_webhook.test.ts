import assert from "node:assert/strict";
import { test } from "node:test";

import { createProvider, LogProvider, ResendProvider } from "../../supabase/functions/_shared/email/providers.ts";
import { parseProviderEvent, signPayload, verifyWebhook } from "../../supabase/functions/_shared/email/webhook.ts";

const MESSAGE = {
  emailId: "22222222-2222-2222-2222-222222222222",
  eventType: "subscription.renewed",
  to: "admin.a@example.com",
  subject: "LungSight: subscription renewed",
  html: "<p>secret body</p>",
  text: "secret body",
};

function fakeFetch(status: number, body: unknown, calls: unknown[] = []) {
  return async (url: string, init: Record<string, unknown>) => {
    calls.push({ url, init });
    return { status, json: async () => body, text: async () => JSON.stringify(body) };
  };
}

// ------------------------------------------------------------------ providers

test("Resend request carries the outbox id as idempotency key", async () => {
  const calls: any[] = [];
  const provider = new ResendProvider({ apiKey: "re_test_key", from: "LungSight <no-reply@example.org>" },
    fakeFetch(200, { id: "re_msg_1" }, calls));

  const outcome = await provider.send(MESSAGE);

  assert.deepEqual(outcome, { kind: "accepted", messageId: "re_msg_1" });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "https://api.resend.com/emails");
  assert.equal(calls[0].init.headers["Idempotency-Key"], MESSAGE.emailId);
  assert.equal(calls[0].init.headers.Authorization, "Bearer re_test_key");
  const body = JSON.parse(calls[0].init.body);
  assert.deepEqual(body.to, ["admin.a@example.com"]);
  assert.equal(body.subject, MESSAGE.subject);
});

test("Resend errors map to retry or permanent failure", async () => {
  assert.equal((await new ResendProvider({ apiKey: "k", from: "f@example.org" }, fakeFetch(422, { name: "validation_error" })).send(MESSAGE)).kind, "permanent");
  assert.equal((await new ResendProvider({ apiKey: "k", from: "f@example.org" }, fakeFetch(429, { name: "rate_limit_exceeded" })).send(MESSAGE)).kind, "transient");
  assert.equal((await new ResendProvider({ apiKey: "k", from: "f@example.org" }, fakeFetch(500, {})).send(MESSAGE)).kind, "transient");
});

test("a hanging provider times out as a transient failure", async () => {
  const hanging = (_url: string, init: Record<string, unknown>) => new Promise<never>((_resolve, reject) => {
    (init.signal as AbortSignal).addEventListener("abort", () => {
      const error = new Error("aborted");
      error.name = "AbortError";
      reject(error);
    });
  });
  const provider = new ResendProvider({ apiKey: "k", from: "f@example.org", timeoutMs: 30 }, hanging as any);

  assert.deepEqual(await provider.send(MESSAGE), { kind: "transient", error: "provider timeout" });
});

test("log provider never logs bodies or full addresses", async () => {
  const lines: Record<string, unknown>[] = [];
  const outcome = await new LogProvider((line) => lines.push(line)).send(MESSAGE);

  assert.deepEqual(outcome, { kind: "accepted", messageId: `log-${MESSAGE.emailId}` });
  const logged = JSON.stringify(lines);
  assert.ok(!logged.includes("secret body") && !logged.includes("admin.a@") && !logged.includes("subscription renewed"));
});

test("provider factory fails closed to log mode", () => {
  const f = fakeFetch(200, {});
  const log = () => {};
  assert.equal(createProvider({}, f, log).name, "log");
  assert.equal(createProvider({ EMAIL_PROVIDER: "resend" }, f, log).name, "log");
  assert.equal(createProvider({ EMAIL_PROVIDER: "resend", RESEND_API_KEY: "k" }, f, log).name, "log");
  assert.equal(createProvider({ EMAIL_PROVIDER: "resend", RESEND_API_KEY: "k", EMAIL_FROM: "a@example.org" }, f, log).name, "resend");
});

// ------------------------------------------------------------------ webhook

const SECRET = "whsec_" + Buffer.from("test-secret-0123456789abcdef").toString("base64");
const NOW = 1_790_000_000;

async function signed(body: string, id = "msg_evt_1", timestamp = String(NOW), secret = SECRET) {
  return { id, timestamp, signature: `v1,${await signPayload(secret, id, timestamp, body)}` };
}

test("valid signature is accepted", async () => {
  const body = JSON.stringify({ type: "email.delivered", data: { email_id: "re_1" } });
  assert.deepEqual(await verifyWebhook(SECRET, await signed(body), body, NOW), { ok: true });
});

test("tampered body, wrong secret and stale timestamp are rejected", async () => {
  const body = JSON.stringify({ type: "email.delivered", data: { email_id: "re_1" } });
  const headers = await signed(body);

  assert.equal((await verifyWebhook(SECRET, headers, body.replace("re_1", "re_2"), NOW)).ok, false);
  const otherSecret = "whsec_" + Buffer.from("another-secret").toString("base64");
  assert.equal((await verifyWebhook(otherSecret, headers, body, NOW)).ok, false);
  assert.deepEqual(await verifyWebhook(SECRET, headers, body, NOW + 301), { ok: false, reason: "timestamp_out_of_range" });
  assert.deepEqual(await verifyWebhook(SECRET, { ...headers, signature: null }, body, NOW), { ok: false, reason: "missing_headers" });
  assert.deepEqual(await verifyWebhook("", headers, body, NOW), { ok: false, reason: "not_configured" });
});

test("any one valid signature among several is accepted (secret rotation)", async () => {
  const body = "{}";
  const good = await signed(body);
  assert.equal((await verifyWebhook(SECRET, { ...good, signature: `v1,AAAA ${good.signature}` }, body, NOW)).ok, true);
});

test("events are reduced to the fields we store", () => {
  const bounce = parseProviderEvent("evt", JSON.stringify({
    type: "email.bounced", created_at: "2026-10-26T01:00:00Z",
    data: { email_id: "re_9", to: ["victim@example.com"], subject: "s", bounce: { type: "Permanent", message: "x" } },
  }));
  assert.deepEqual(bounce, { eventId: "evt", type: "email.bounced", messageId: "re_9", bounceType: "Permanent",
    occurredAt: "2026-10-26T01:00:00.000Z" });
  assert.equal(parseProviderEvent("evt", JSON.stringify({ type: "email.opened", data: { email_id: "re_9" } })), null);
  assert.equal(parseProviderEvent("evt", "not json"), null);
  assert.equal(parseProviderEvent("evt", JSON.stringify({ type: "email.delivered", data: {} })), null);
});
