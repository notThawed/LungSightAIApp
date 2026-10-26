-- Phase 3 scheduler — NOT a migration. Run manually, and only after:
--   1. supabase/migrations/20261027000000_email_notifications.sql is applied,
--   2. the email-worker Edge Function is deployed with its secrets set,
--   3. email_preflight_checks.sql shows pg_cron, pg_net and supabase_vault available.
--
-- Replace the two <...> placeholders in the SQL Editor; never commit real values.
-- EMAIL_WORKER_SECRET must be the same value set as the Edge Function secret.

-- Extensions (alternatively enable them in Dashboard > Database > Extensions).
create extension if not exists pg_cron;
create extension if not exists pg_net;

-- Secrets for the cron job (stored encrypted in Vault, not in the job text).
select vault.create_secret('<https://PROJECT_REF.supabase.co/functions/v1/email-worker>', 'email_worker_url');
select vault.create_secret('<EMAIL_WORKER_SECRET>', 'email_worker_secret');

-- The single scheduler: one job sends queued email every minute ...
select cron.schedule(
    'lungsight-email-worker',
    '* * * * *',
    $job$
    select net.http_post(
        url := (select decrypted_secret from vault.decrypted_secrets where name = 'email_worker_url'),
        headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'x-worker-secret', (select decrypted_secret from vault.decrypted_secrets where name = 'email_worker_secret')
        ),
        body := '{}'::jsonb,
        timeout_milliseconds := 55000
    );
    $job$
);

-- ... and one job queues expiry reminders daily at 00:00 UTC (08:00 Asia/Manila).
select cron.schedule(
    'lungsight-expiry-reminders',
    '0 0 * * *',
    $job$ select public.enqueue_expiry_reminders(array[7, 3, 0]); $job$
);

-- Verify (read-only):
-- select jobname, schedule, active from cron.job where jobname like 'lungsight-%';
-- select status_code, created from net._http_response order by created desc limit 5;

-- Pause sending without removing anything:
-- update cron.job set active = false where jobname = 'lungsight-email-worker';
