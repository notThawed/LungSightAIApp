import assert from "node:assert/strict";
import { test } from "node:test";

import {
  backoffDelayMs, classifyException, classifyHttp, isValidRecipient, maskEmail, MAX_DELAY_MS,
  safeHeader, sanitizeError,
} from "../../supabase/functions/_shared/email/policy.ts";
import { escapeHtml, formatDate, renderEmail, safeBaseUrl, UnknownTemplateError } from "../../supabase/functions/_shared/email/templates.ts";

// ------------------------------------------------------------------ policy

test("backoff grows exponentially with bounded jitter", () => {
  assert.equal(backoffDelayMs(1, () => 0), 30_000);
  assert.equal(backoffDelayMs(1, () => 0.999999), 60_000);
  assert.equal(backoffDelayMs(3, () => 0), 120_000);
  for (let attempt = 1; attempt <= 30; attempt++) {
    const low = backoffDelayMs(attempt, () => 0);
    const high = backoffDelayMs(attempt, () => 0.999999);
    assert.ok(low <= high && high <= MAX_DELAY_MS, `attempt ${attempt}`);
  }
  assert.equal(backoffDelayMs(20, () => 1), MAX_DELAY_MS);
});

test("HTTP results are classified transient vs permanent", () => {
  assert.deepEqual(classifyHttp(200, "re_123", ""), { kind: "accepted", messageId: "re_123" });
  assert.equal(classifyHttp(200, null, "").kind, "transient");
  for (const status of [401, 403, 408, 409, 429, 500, 502, 503]) assert.equal(classifyHttp(status, null, "x").kind, "transient", String(status));
  const invalid = classifyHttp(422, null, "validation_error");
  assert.equal(invalid.kind, "permanent");
  assert.equal((invalid as { reason: string }).reason, "invalid_request");
  assert.equal(classifyHttp(404, null, "").kind, "permanent");
});

test("timeouts and network errors are transient", () => {
  const abort = new Error("aborted");
  abort.name = "AbortError";
  assert.deepEqual(classifyException(abort), { kind: "transient", error: "provider timeout" });
  assert.equal(classifyException(new TypeError("fetch failed")).kind, "transient");
});

test("errors are sanitised before storage", () => {
  const cleaned = sanitizeError('Invalid "to": victim@example.com <script>\r\nX-Header: y');
  assert.ok(!cleaned.includes("@") && !cleaned.includes("<") && !cleaned.includes("\n") && !cleaned.includes('"'));
  assert.ok(cleaned.includes("[email]"));
  assert.ok(sanitizeError("x".repeat(500)).length <= 200);
});

test("addresses are masked and validated; headers lose CR/LF", () => {
  assert.equal(maskEmail("admin.a@example.com"), "a***@example.com");
  assert.equal(maskEmail(null), "—");
  assert.equal(safeHeader("LungSight\r\nBcc: attacker@example.com"), "LungSight Bcc: attacker@example.com");
  assert.ok(isValidRecipient("a.b+c@example.co"));
  for (const bad of ["Admin@Example.com", "a@b", "x@y.z, other@example.com", "a\n@example.com", "a".repeat(250) + "@ex.com"]) {
    assert.ok(!isValidRecipient(bad), bad);
  }
});

// ------------------------------------------------------------------ templates

const BASE = { appBaseUrl: "https://lungsight.example.org/app?x=1#frag" };
const row = (event_type: string, template_data: Record<string, unknown> = {}) =>
  ({ email_id: "11111111-1111-1111-1111-111111111111", event_type, template_data });

test("every queued event type renders html and text", () => {
  const cases = [
    row("application.received", { reference: "ABCDEF12" }),
    row("application.approved", { hospital_name: "Bayview" }),
    row("subscription.activated", { hospital_name: "Bayview", plan_name: "Professional", end_date: "2027-10-26" }),
    row("subscription.renewed", { hospital_name: "Bayview", end_date: "2028-01-01" }),
    row("subscription.expiry_reminder", { hospital_name: "Bayview", end_date: "2026-11-02", days_left: 7 }),
    row("ops.alert", { alert: "payments_not_applied", count: 2 }),
  ];
  for (const c of cases) {
    const email = renderEmail(c, BASE);
    assert.ok(email.subject.startsWith("LungSight"), c.event_type);
    assert.ok(email.html.startsWith("<!doctype html>") && email.text.length > 20, c.event_type);
    assert.ok(!/<[a-z]/i.test(email.text), `${c.event_type} text is plain`);
  }
});

test("user-supplied values are escaped and never reach the subject", () => {
  const evil = '<script>alert(1)</script>\r\nBcc: x@evil.test "&';
  const email = renderEmail(row("subscription.activated", { hospital_name: evil, plan_name: evil, end_date: "2027-01-01" }), BASE);
  assert.ok(!email.html.includes("<script>"));
  assert.ok(email.html.includes("&lt;script&gt;"));
  assert.equal(email.subject, "LungSight: subscription active");
  assert.ok(!email.subject.includes("\n"));
  assert.equal(escapeHtml(`"'<>&`), "&quot;&#39;&lt;&gt;&amp;");
});

test("wording never overclaims", () => {
  const received = renderEmail(row("application.received", { reference: "ABCDEF12" }), BASE).text;
  assert.ok(received.includes("does not mean the application has been approved"));
  assert.ok(!received.includes("Sign in"), "receipt has no account link");

  const approved = renderEmail(row("application.approved", { hospital_name: "H" }), BASE).text;
  assert.ok(approved.includes("becomes active only after the setup is completed"));

  const reminder = renderEmail(row("subscription.expiry_reminder", { end_date: "2026-11-02", days_left: 3 }), BASE).text;
  assert.ok(reminder.includes("in 3 days, on November 2, 2026"));
  assert.ok(!/paid|payment|₱|PHP/i.test(reminder));

  const today = renderEmail(row("subscription.expiry_reminder", { end_date: "2026-11-02", days_left: 0 }), BASE);
  assert.equal(today.subject, "LungSight: subscription ends today");

  const renewed = renderEmail(row("subscription.renewed", { end_date: "2028-01-01" }), BASE).text;
  assert.ok(!/₱|PHP|amount|card/i.test(renewed));
});

test("receipt ignores anything but a well-formed reference", () => {
  const email = renderEmail(row("application.received", { reference: "<a href=x>", hospital_name: "Injected" }), BASE);
  assert.ok(email.text.includes("Reference: —"));
  assert.ok(!email.text.includes("Injected"));
});

test("emails contain no clinical or AI wording", () => {
  for (const event of ["application.approved", "subscription.activated", "subscription.renewed", "subscription.expiry_reminder"]) {
    const text = renderEmail(row(event, { hospital_name: "H", end_date: "2027-01-01", days_left: 7 }), BASE).text.toLowerCase();
    assert.ok(!/diagnos|pneumonia|x-ray|ai result|positive/.test(text), event);
  }
});

test("links use APP_BASE_URL only, without query or fragment", () => {
  const email = renderEmail(row("subscription.activated", { end_date: "2027-01-01" }), BASE);
  assert.ok(email.text.includes("https://lungsight.example.org/app/"));
  assert.ok(!email.html.includes("x=1") && !email.html.includes("#frag"));
  assert.equal(safeBaseUrl("javascript:alert(1)"), null);
  const noLink = renderEmail(row("subscription.activated", { end_date: "2027-01-01" }), { appBaseUrl: "javascript:alert(1)" });
  assert.ok(!noLink.html.includes("href"));
});

test("dates and unknown events are handled safely", () => {
  assert.equal(formatDate("2026-11-02"), "November 2, 2026");
  assert.equal(formatDate("2026-13-01"), "—");
  assert.equal(formatDate("<b>"), "—");
  assert.throws(() => renderEmail(row("patient.created"), BASE), UnknownTemplateError);
  assert.throws(() => renderEmail(row("ops.alert", { alert: "other" }), BASE), UnknownTemplateError);
});

test("test redirect prefixes the subject", () => {
  const email = renderEmail(row("subscription.renewed", { end_date: "2028-01-01" }), { ...BASE, subjectPrefix: "[TEST]\r\n" });
  assert.equal(email.subject, "[TEST] LungSight: subscription renewed");
});
