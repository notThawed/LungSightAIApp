// Email worker core. Database access goes through EmailStore (Supabase RPCs
// in production, an in-memory fake in tests); sending goes through
// EmailProvider. Business state is never written here.

import { backoffDelayMs, isValidRecipient, maskEmail, sanitizeError } from "./policy.ts";
import type { EmailProvider } from "./providers.ts";
import { renderEmail, UnknownTemplateError } from "./templates.ts";

export type OutboxRow = {
  email_id: string;
  event_type: string;
  recipient_kind: string;
  recipient_email: string | null;
  template_data: Record<string, unknown>;
  attempts: number;
  max_attempts: number;
};

export type CompleteInput = {
  emailId: string;
  workerId: string;
  outcome: "sent" | "retry" | "failed" | "skipped";
  messageId?: string | null;
  error?: string | null;
  retryAt?: string | null;
  reason?: string | null;
  now: string;
};

export interface EmailStore {
  claim(workerId: string, limit: number, now: string): Promise<OutboxRow[]>;
  expand(emailId: string, workerId: string): Promise<number>;
  check(emailId: string, now: string): Promise<{ ok: boolean; reason: string | null }>;
  complete(input: CompleteInput): Promise<string | null>;
  enqueueAlerts(now: string): Promise<number>;
}

export type WorkerOptions = {
  store: EmailStore;
  provider: EmailProvider;
  workerId: string;
  appBaseUrl: string;
  now?: () => Date;
  random?: () => number;
  batchSize?: number;
  maxBatches?: number;
  redirectTo?: string | null;
  log?: (line: Record<string, unknown>) => void;
};

export type WorkerSummary = {
  claimed: number;
  expanded: number;
  sent: number;
  retried: number;
  failed: number;
  skipped: number;
  lockLost: number;
  alertsQueued: number;
};

export async function runWorker(options: WorkerOptions): Promise<WorkerSummary> {
  const now = options.now ?? (() => new Date());
  const random = options.random ?? Math.random;
  const log = options.log ?? (() => {});
  const batchSize = options.batchSize ?? 20;
  const maxBatches = options.maxBatches ?? 5;
  const redirect = options.redirectTo && isValidRecipient(options.redirectTo) ? options.redirectTo : null;

  const summary: WorkerSummary = {
    claimed: 0, expanded: 0, sent: 0, retried: 0, failed: 0, skipped: 0, lockLost: 0, alertsQueued: 0,
  };

  const finish = async (input: Omit<CompleteInput, "workerId" | "now">) => {
    const status = await options.store.complete({ ...input, workerId: options.workerId, now: now().toISOString() });
    if (status === null) summary.lockLost++;
    else if (status === "sent") summary.sent++;
    else if (status === "queued") summary.retried++;
    else if (status === "failed") summary.failed++;
    else summary.skipped++;
    return status;
  };

  try {
    summary.alertsQueued = await options.store.enqueueAlerts(now().toISOString());
  } catch (error) {
    log({ level: "error", msg: "alert scan failed", error: sanitizeError(error) });
  }

  for (let batch = 0; batch < maxBatches; batch++) {
    const rows = await options.store.claim(options.workerId, batchSize, now().toISOString());
    summary.claimed += rows.length;
    if (rows.length === 0) break;

    for (const row of rows) {
      try {
        if (!row.recipient_email && row.recipient_kind !== "applicant_receipt") {
          const recipients = await options.store.expand(row.email_id, options.workerId);
          if (recipients > 0) {
            summary.expanded++;
          } else if (recipients === 0) {
            await finish({
              emailId: row.email_id, outcome: "retry", error: "no eligible recipients yet",
              retryAt: new Date(now().getTime() + backoffDelayMs(row.attempts, random)).toISOString(),
            });
          } else {
            summary.lockLost++;
          }
          continue;
        }

        const check = await options.store.check(row.email_id, now().toISOString());
        if (!check.ok) {
          await finish({ emailId: row.email_id, outcome: "skipped", reason: check.reason ?? "ineligible" });
          continue;
        }

        if (!isValidRecipient(row.recipient_email)) {
          await finish({ emailId: row.email_id, outcome: "failed", reason: "invalid_recipient", error: "invalid recipient" });
          continue;
        }

        let rendered;
        try {
          rendered = renderEmail(row, { appBaseUrl: options.appBaseUrl, subjectPrefix: redirect ? "[TEST]" : undefined });
        } catch (error) {
          if (error instanceof UnknownTemplateError) {
            await finish({ emailId: row.email_id, outcome: "failed", reason: "unknown_template", error: error.message });
            continue;
          }
          throw error;
        }

        const outcome = await options.provider.send({
          emailId: row.email_id,
          eventType: row.event_type,
          to: redirect ?? (row.recipient_email as string),
          subject: rendered.subject,
          html: rendered.html,
          text: rendered.text,
        });

        if (outcome.kind === "accepted") {
          await finish({ emailId: row.email_id, outcome: "sent", messageId: outcome.messageId });
        } else if (outcome.kind === "transient") {
          await finish({
            emailId: row.email_id, outcome: "retry", error: outcome.error,
            retryAt: new Date(now().getTime() + backoffDelayMs(row.attempts, random)).toISOString(),
          });
        } else {
          await finish({ emailId: row.email_id, outcome: "failed", error: outcome.error, reason: outcome.reason });
        }

        log({ level: "info", email_id: row.email_id, event: row.event_type, to: maskEmail(row.recipient_email), result: outcome.kind });
      } catch (error) {
        log({ level: "error", email_id: row.email_id, error: sanitizeError(error) });
        try {
          await finish({
            emailId: row.email_id, outcome: "retry", error: sanitizeError(error),
            retryAt: new Date(now().getTime() + backoffDelayMs(row.attempts, random)).toISOString(),
          });
        } catch (inner) {
          log({ level: "error", email_id: row.email_id, error: sanitizeError(inner) });
        }
      }
    }
  }

  return summary;
}
