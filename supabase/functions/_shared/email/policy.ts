// Delivery policy: retry backoff, result classification, sanitisation.
// Pure functions (no Deno/Node APIs) so they run in Edge Functions and tests.

export const BASE_DELAY_MS = 60_000;
export const MAX_DELAY_MS = 6 * 60 * 60 * 1000;

/** Exponential backoff with jitter: delay * [0.5, 1.0), capped. attempt is 1-based. */
export function backoffDelayMs(attempt: number, random: () => number = Math.random): number {
  const exponent = Math.max(0, Math.min(attempt - 1, 20));
  const delay = Math.min(BASE_DELAY_MS * 2 ** exponent, MAX_DELAY_MS);
  return Math.round(delay * (0.5 + 0.5 * random()));
}

export type SendOutcome =
  | { kind: "accepted"; messageId: string }
  | { kind: "transient"; error: string }
  | { kind: "permanent"; error: string; reason: string };

/**
 * Map an HTTP status from the provider to an outcome.
 * 401/403/409 are transient on purpose: a misconfigured key or an in-flight
 * idempotent duplicate should be retried once fixed, not dropped.
 */
export function classifyHttp(status: number, messageId: string | null, detail: string): SendOutcome {
  if (status >= 200 && status < 300 && messageId) {
    return { kind: "accepted", messageId };
  }
  if (status >= 200 && status < 300) {
    return { kind: "transient", error: "accepted response without message id" };
  }
  if (status === 401 || status === 403) {
    return { kind: "transient", error: `HTTP ${status} provider authentication` };
  }
  if (status === 408 || status === 409 || status === 429 || status >= 500) {
    return { kind: "transient", error: `HTTP ${status} ${sanitizeError(detail)}`.trim() };
  }
  return {
    kind: "permanent",
    error: `HTTP ${status} ${sanitizeError(detail)}`.trim(),
    reason: status === 422 || status === 400 ? "invalid_request" : "provider_rejected",
  };
}

/** Network errors and timeouts are transient: the provider may or may not have accepted. */
export function classifyException(error: unknown): SendOutcome {
  const name = error instanceof Error ? error.name : "Error";
  return { kind: "transient", error: name === "AbortError" ? "provider timeout" : `network error ${name}` };
}

/** Strip addresses and unusual characters; cap length. Never store provider bodies verbatim. */
export function sanitizeError(value: unknown): string {
  const text = String(value ?? "")
    .replace(/\S+@\S+/g, "[email]")
    .replace(/[^A-Za-z0-9 _.:/\[\]()-]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return text.slice(0, 200);
}

/** a***@example.com — for logs and the history page. */
export function maskEmail(email: string | null | undefined): string {
  if (!email || !email.includes("@")) return "—";
  const [local, domain] = email.split("@", 2);
  return `${local.slice(0, 1)}***@${domain}`;
}

/** Header values: no CR/LF, bounded. Used for From / Reply-To / Subject. */
export function safeHeader(value: string, max = 150): string {
  return String(value ?? "").replace(/[\r\n\u0000-\u001f\u007f]+/g, " ").trim().slice(0, max);
}

export const EMAIL_PATTERN = /^[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$/;

export function isValidRecipient(email: string | null | undefined): boolean {
  return typeof email === "string" && email.length <= 254 && EMAIL_PATTERN.test(email);
}
