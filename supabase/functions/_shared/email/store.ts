// EmailStore backed by the service-role Supabase client (RPCs defined in the
// email_notifications migration). Errors propagate; the worker turns them
// into retries.

import type { CompleteInput, EmailStore, OutboxRow } from "./worker.ts";

type RpcClient = {
  rpc(fn: string, args: Record<string, unknown>): PromiseLike<{ data: unknown; error: { code?: string; message?: string } | null }>;
};

async function call<T>(client: RpcClient, fn: string, args: Record<string, unknown>): Promise<T> {
  const { data, error } = await client.rpc(fn, args);
  if (error) throw new Error(`rpc ${fn} failed (${error.code ?? "unknown"})`);
  return data as T;
}

export class SupabaseEmailStore implements EmailStore {
  private readonly client: RpcClient;

  constructor(client: RpcClient) {
    this.client = client;
  }

  async claim(workerId: string, limit: number, now: string): Promise<OutboxRow[]> {
    return (await call<OutboxRow[]>(this.client, "claim_email_batch", { p_worker: workerId, p_limit: limit, p_now: now })) ?? [];
  }

  async expand(emailId: string, workerId: string): Promise<number> {
    return Number(await call<number>(this.client, "expand_email_recipients", { p_email_id: emailId, p_worker: workerId }));
  }

  async check(emailId: string, now: string): Promise<{ ok: boolean; reason: string | null }> {
    const rows = await call<{ ok: boolean; reason: string | null }[]>(this.client, "email_send_check",
      { p_email_id: emailId, p_now: now });
    return rows?.[0] ?? { ok: false, reason: "missing" };
  }

  async complete(input: CompleteInput): Promise<string | null> {
    return await call<string | null>(this.client, "complete_email_attempt", {
      p_email_id: input.emailId,
      p_worker: input.workerId,
      p_outcome: input.outcome,
      p_message_id: input.messageId ?? null,
      p_error: input.error ?? null,
      p_retry_at: input.retryAt ?? null,
      p_reason: input.reason ?? null,
      p_now: input.now,
    });
  }

  async enqueueAlerts(now: string): Promise<number> {
    return Number(await call<number>(this.client, "enqueue_operational_alerts", { p_now: now }));
  }
}
