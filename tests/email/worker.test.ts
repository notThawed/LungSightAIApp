import assert from "node:assert/strict";
import { test } from "node:test";

import type { SendOutcome } from "../../supabase/functions/_shared/email/policy.ts";
import type { EmailProvider, OutgoingEmail } from "../../supabase/functions/_shared/email/providers.ts";
import { runWorker, type CompleteInput, type EmailStore, type OutboxRow } from "../../supabase/functions/_shared/email/worker.ts";

type Row = OutboxRow & { status: string; locked_by: string | null; next: number; checkOk?: boolean; checkReason?: string };

class FakeStore implements EmailStore {
  rows = new Map<string, Row>();
  completions: CompleteInput[] = [];
  expansions: Record<string, string[]> = {};
  failCheckFor = new Set<string>();
  loseLockFor = new Set<string>();
  businessWrites = 0;

  add(row: Partial<Row> & { email_id: string }) {
    this.rows.set(row.email_id, {
      event_type: "subscription.renewed", recipient_kind: "hospital_admin", recipient_email: "admin.a@example.com",
      template_data: { end_date: "2028-01-01", hospital_name: "H" }, attempts: 0, max_attempts: 6,
      status: "queued", locked_by: null, next: 0, ...row,
    });
  }

  async claim(workerId: string, limit: number, now: string) {
    const t = Date.parse(now);
    const due = [...this.rows.values()].filter((r) => r.status === "queued" && r.next <= t).slice(0, limit);
    for (const r of due) { r.status = "sending"; r.locked_by = workerId; r.attempts += 1; }
    return due.map((r) => ({ ...r }));
  }

  async expand(emailId: string, workerId: string) {
    const parent = this.rows.get(emailId)!;
    if (parent.status !== "sending" || parent.locked_by !== workerId) return -1;
    const recipients = this.expansions[emailId] ?? [];
    recipients.forEach((email, i) => this.add({ ...parent, email_id: `${emailId}-${i}`, recipient_email: email,
      status: "queued", locked_by: null, attempts: 0 }));
    if (recipients.length) { parent.status = "expanded"; parent.locked_by = null; }
    return recipients.length;
  }

  async check(emailId: string) {
    if (this.failCheckFor.has(emailId)) throw new Error("db hiccup for victim@example.com");
    const r = this.rows.get(emailId)!;
    return { ok: r.checkOk ?? true, reason: r.checkReason ?? null };
  }

  async complete(input: CompleteInput) {
    this.completions.push(input);
    const r = this.rows.get(input.emailId)!;
    if (this.loseLockFor.has(input.emailId) || r.status !== "sending" || r.locked_by !== input.workerId) return null;
    r.locked_by = null;
    if (input.outcome === "sent") { r.status = "sent"; return "sent"; }
    if (input.outcome === "skipped") { r.status = input.reason === "suppressed" ? "suppressed" : "skipped"; return r.status; }
    if (input.outcome === "retry" && r.attempts < r.max_attempts) {
      r.status = "queued"; r.next = Date.parse(input.retryAt!); return "queued";
    }
    r.status = "failed";
    return "failed";
  }

  async enqueueAlerts() { return 0; }
}

class FakeProvider implements EmailProvider {
  readonly name = "fake";
  sent: OutgoingEmail[] = [];
  outcomes: SendOutcome[] = [];

  async send(message: OutgoingEmail): Promise<SendOutcome> {
    this.sent.push(message);
    return this.outcomes.shift() ?? { kind: "accepted", messageId: `m-${message.emailId}` };
  }
}

const CLOCK = new Date("2026-10-26T00:00:00Z");
const options = (store: FakeStore, provider: FakeProvider, extra = {}) => ({
  store, provider, workerId: "w1", appBaseUrl: "https://lungsight.example.org",
  now: () => CLOCK, random: () => 0, ...extra,
});

test("a queued email is sent once and marked sent", async () => {
  const store = new FakeStore(); const provider = new FakeProvider();
  store.add({ email_id: "e1" });

  const summary = await runWorker(options(store, provider));

  assert.equal(provider.sent.length, 1);
  assert.equal(provider.sent[0].to, "admin.a@example.com");
  assert.equal(store.rows.get("e1")!.status, "sent");
  assert.equal(summary.sent, 1);
  await runWorker(options(store, provider));
  assert.equal(provider.sent.length, 1, "a sent email is never sent again");
});

test("fan-out rows expand and the children send in the same run", async () => {
  const store = new FakeStore(); const provider = new FakeProvider();
  store.add({ email_id: "p1", recipient_email: null });
  store.expansions.p1 = ["admin.a@example.com", "admin.c@example.com"];

  const summary = await runWorker(options(store, provider));

  assert.equal(summary.expanded, 1);
  assert.deepEqual(provider.sent.map((m) => m.to).sort(), ["admin.a@example.com", "admin.c@example.com"]);
  assert.equal(store.rows.get("p1")!.status, "expanded");
});

test("no recipients yet -> retried later, nothing sent", async () => {
  const store = new FakeStore(); const provider = new FakeProvider();
  store.add({ email_id: "p2", recipient_email: null });

  await runWorker(options(store, provider));

  assert.equal(provider.sent.length, 0);
  assert.equal(store.rows.get("p2")!.status, "queued");
  assert.equal(store.rows.get("p2")!.next, CLOCK.getTime() + 30_000);
});

test("send-time check failure skips without sending", async () => {
  const store = new FakeStore(); const provider = new FakeProvider();
  store.add({ email_id: "e2", checkOk: false, checkReason: "state_changed" });
  store.add({ email_id: "e3", checkOk: false, checkReason: "suppressed" });

  await runWorker(options(store, provider));

  assert.equal(provider.sent.length, 0);
  assert.equal(store.rows.get("e2")!.status, "skipped");
  assert.equal(store.rows.get("e3")!.status, "suppressed");
});

test("transient failure retries with backoff, then fails after max attempts", async () => {
  const store = new FakeStore(); const provider = new FakeProvider();
  store.add({ email_id: "e4", max_attempts: 2 });
  provider.outcomes = [{ kind: "transient", error: "HTTP 503" }, { kind: "transient", error: "HTTP 503" }];

  await runWorker(options(store, provider));
  assert.equal(store.rows.get("e4")!.status, "queued");
  assert.equal(store.completions.at(-1)!.retryAt, new Date(CLOCK.getTime() + 30_000).toISOString());

  await runWorker(options(store, provider, { now: () => new Date(CLOCK.getTime() + 60_000) }));
  assert.equal(store.rows.get("e4")!.status, "failed");
  assert.equal(provider.sent.length, 2);
});

test("permanent failure is not retried", async () => {
  const store = new FakeStore(); const provider = new FakeProvider();
  store.add({ email_id: "e5" });
  provider.outcomes = [{ kind: "permanent", error: "HTTP 422", reason: "invalid_request" }];

  await runWorker(options(store, provider));

  assert.equal(store.rows.get("e5")!.status, "failed");
  assert.equal(store.completions[0].reason, "invalid_request");
});

test("provider timeout leaves only an email retry (no business writes)", async () => {
  const store = new FakeStore(); const provider = new FakeProvider();
  store.add({ email_id: "e6" });
  provider.outcomes = [{ kind: "transient", error: "provider timeout" }];

  await runWorker(options(store, provider));

  assert.equal(store.rows.get("e6")!.status, "queued");
  assert.equal(store.businessWrites, 0);
  assert.deepEqual(store.completions.map((c) => c.outcome), ["retry"]);
});

test("a store error on one row does not stop the batch", async () => {
  const store = new FakeStore(); const provider = new FakeProvider();
  store.add({ email_id: "bad" });
  store.add({ email_id: "good" });
  store.failCheckFor.add("bad");
  const lines: Record<string, unknown>[] = [];

  await runWorker(options(store, provider, { log: (l: Record<string, unknown>) => lines.push(l) }));

  assert.equal(store.rows.get("bad")!.status, "queued");
  assert.equal(store.rows.get("good")!.status, "sent");
  assert.ok(!JSON.stringify(lines).includes("victim@example.com"), "errors are sanitised in logs");
});

test("losing the lock is counted and never overwrites another worker", async () => {
  const store = new FakeStore(); const provider = new FakeProvider();
  store.add({ email_id: "e7" });
  store.loseLockFor.add("e7");

  const summary = await runWorker(options(store, provider));

  assert.equal(summary.lockLost, 1);
  assert.equal(store.rows.get("e7")!.status, "sending");
});

test("unknown templates fail permanently without sending", async () => {
  const store = new FakeStore(); const provider = new FakeProvider();
  store.add({ email_id: "e8", event_type: "report.ready" });

  await runWorker(options(store, provider));

  assert.equal(provider.sent.length, 0);
  assert.equal(store.completions[0].reason, "unknown_template");
});

test("redirect mode sends every email to the test inbox with a [TEST] subject", async () => {
  const store = new FakeStore(); const provider = new FakeProvider();
  store.add({ email_id: "e9" });

  await runWorker(options(store, provider, { redirectTo: "qa@example.org" }));

  assert.equal(provider.sent[0].to, "qa@example.org");
  assert.ok(provider.sent[0].subject.startsWith("[TEST] "));
});

test("logs never contain bodies, subjects or full addresses", async () => {
  const store = new FakeStore(); const provider = new FakeProvider();
  store.add({ email_id: "e10" });
  const lines: Record<string, unknown>[] = [];

  await runWorker(options(store, provider, { log: (l: Record<string, unknown>) => lines.push(l) }));

  const logged = JSON.stringify(lines);
  assert.ok(!logged.includes("admin.a@example.com") && !logged.includes("subscription renewed") && !logged.includes("<p>"));
});

test("two workers sharing a store send each email exactly once", async () => {
  const store = new FakeStore();
  const providerA = new FakeProvider(); const providerB = new FakeProvider();
  for (let i = 0; i < 10; i++) store.add({ email_id: `c${i}` });

  await Promise.all([
    runWorker({ ...options(store, providerA), workerId: "A", batchSize: 3 }),
    runWorker({ ...options(store, providerB), workerId: "B", batchSize: 3 }),
  ]);

  const ids = [...providerA.sent, ...providerB.sent].map((m) => m.emailId).sort();
  assert.deepEqual(ids, [...store.rows.keys()].sort());
});
