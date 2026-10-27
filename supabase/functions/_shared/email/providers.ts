// Email providers behind one interface.
//
// LogProvider (default) sends nothing: it records metadata only (never the
// body) and returns a "log-" message id so the history shows a simulated send.
// ResendProvider calls the Resend HTTP API with the outbox email_id as the
// Idempotency-Key, so a retry after a timeout does not create a second email
// within Resend's idempotency window (24h). After that window a rare
// duplicate is possible.

import { classifyException, classifyHttp, maskEmail, safeHeader, type SendOutcome } from "./policy.ts";

export type OutgoingEmail = {
  emailId: string;
  eventType: string;
  to: string;
  subject: string;
  html: string;
  text: string;
};

export interface EmailProvider {
  readonly name: string;
  send(message: OutgoingEmail): Promise<SendOutcome>;
}

export type Logger = (line: Record<string, unknown>) => void;

export class LogProvider implements EmailProvider {
  readonly name = "log";
  private readonly log: Logger;

  constructor(log: Logger) {
    this.log = log;
  }

  async send(message: OutgoingEmail): Promise<SendOutcome> {
    this.log({
      provider: "log",
      email_id: message.emailId,
      event: message.eventType,
      to: maskEmail(message.to),
    });
    return { kind: "accepted", messageId: `log-${message.emailId}` };
  }
}

export type ResendConfig = {
  apiKey: string;
  from: string;
  replyTo?: string;
  timeoutMs?: number;
  endpoint?: string;
};

type FetchLike = (input: string, init: Record<string, unknown>) => Promise<{
  status: number;
  json(): Promise<unknown>;
  text(): Promise<string>;
}>;

export class ResendProvider implements EmailProvider {
  readonly name = "resend";
  private readonly config: ResendConfig;
  private readonly fetchImpl: FetchLike;

  constructor(config: ResendConfig, fetchImpl: FetchLike) {
    if (!config.apiKey || !config.from) throw new Error("Resend provider is not configured");
    this.config = config;
    this.fetchImpl = fetchImpl;
  }

  async send(message: OutgoingEmail): Promise<SendOutcome> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.config.timeoutMs ?? 10_000);

    const payload: Record<string, unknown> = {
      from: safeHeader(this.config.from),
      to: [message.to],
      subject: safeHeader(message.subject),
      html: message.html,
      text: message.text,
      tags: [{ name: "event", value: message.eventType.replace(/[^A-Za-z0-9_-]/g, "_") }],
    };
    if (this.config.replyTo) payload.reply_to = safeHeader(this.config.replyTo);

    try {
      const response = await this.fetchImpl(this.config.endpoint ?? "https://api.resend.com/emails", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${this.config.apiKey}`,
          "Content-Type": "application/json",
          "Idempotency-Key": message.emailId,
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      let messageId: string | null = null;
      let detail = "";

      if (response.status >= 200 && response.status < 300) {
        const body = (await response.json().catch(() => ({}))) as { id?: unknown };
        messageId = typeof body.id === "string" ? body.id : null;
      } else {
        const body = (await response.json().catch(() => ({}))) as { name?: unknown };
        detail = typeof body.name === "string" ? body.name : "";
      }

      return classifyHttp(response.status, messageId, detail);
    } catch (error) {
      return classifyException(error);
    } finally {
      clearTimeout(timer);
    }
  }
}

export type ProviderEnv = {
  EMAIL_PROVIDER?: string;
  RESEND_API_KEY?: string;
  EMAIL_FROM?: string;
  EMAIL_REPLY_TO?: string;
};

/** Anything other than an explicit, fully configured "resend" falls back to log mode. */
export function createProvider(env: ProviderEnv, fetchImpl: FetchLike, log: Logger): EmailProvider {
  if (env.EMAIL_PROVIDER === "resend" && env.RESEND_API_KEY && env.EMAIL_FROM) {
    return new ResendProvider(
      { apiKey: env.RESEND_API_KEY, from: env.EMAIL_FROM, replyTo: env.EMAIL_REPLY_TO },
      fetchImpl,
    );
  }
  return new LogProvider(log);
}
