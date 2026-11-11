-- Phase 3 rollback — removes the email outbox, triggers and functions.
-- Business tables (applications, subscriptions, payments) are untouched.
-- Audit rows already written (email.*) stay: audit_logs is append-only.
--
-- If the scheduler was created, remove it FIRST (run separately):
--   select cron.unschedule('lungsight-email-worker');
--   select cron.unschedule('lungsight-expiry-reminders');
--   delete from vault.secrets where name in ('email_worker_url', 'email_worker_secret');

begin;

drop trigger if exists email_on_application_change on public.hospital_applications;
drop trigger if exists email_on_subscription_change on public.hospital_subscriptions;

drop function if exists public.claim_email_batch(text, integer, timestamptz);
drop function if exists public.expand_email_recipients(uuid, text);
drop function if exists public.email_send_check(uuid, timestamptz);
drop function if exists public.complete_email_attempt(uuid, text, text, text, text, timestamptz, text, timestamptz);
drop function if exists public.apply_email_provider_event(text, text, text, text, timestamptz);
drop function if exists public.enqueue_expiry_reminders(integer[], timestamptz);
drop function if exists public.enqueue_operational_alerts(timestamptz);

drop function if exists private.email_on_application_change();
drop function if exists private.email_on_subscription_change();
drop function if exists private.email_subscription_data(public.hospital_subscriptions);
drop function if exists private.enqueue_email(text, text, text, uuid, text, text, uuid, text, jsonb, timestamptz, text, text);
drop function if exists private.email_recipients(text, uuid, text);
drop function if exists private.email_clean_reason(text);
drop function if exists private.email_clean_error(text);
drop function if exists private.email_audit(text, text, uuid, uuid, jsonb, text);

drop table if exists public.alert_cooldowns;
drop table if exists public.email_provider_events;
drop table if exists public.email_suppressions;
drop table if exists public.email_outbox;

commit;
