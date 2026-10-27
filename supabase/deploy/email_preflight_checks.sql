-- Phase 3 preflight — READ-ONLY. Run in the Supabase SQL Editor before any
-- email deployment step and share the output.

-- 1. Extensions needed by the scheduler (installed_version null = available but not enabled).
select name, default_version, installed_version
from pg_available_extensions
where name in ('pg_cron', 'pg_net', 'supabase_vault')
order by name;

-- 2. Phase 1 dependency present (private schema + audit_logs).
select
    exists (select 1 from pg_namespace where nspname = 'private')                       as private_schema,
    exists (select 1 from information_schema.tables
            where table_schema = 'public' and table_name = 'audit_logs')                as audit_logs_table;

-- 3. Email objects must NOT exist yet (all false before the migration).
select
    exists (select 1 from information_schema.tables
            where table_schema = 'public' and table_name = 'email_outbox')              as email_outbox_exists,
    exists (select 1 from pg_proc where proname = 'claim_email_batch')                  as claim_function_exists,
    exists (select 1 from pg_trigger where tgname in
            ('email_on_application_change', 'email_on_subscription_change'))            as email_triggers_exist;

-- 4. Columns the triggers rely on (expect 10 rows).
select table_name, column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and (table_name, column_name) in (
      ('hospital_applications', 'applicant_email'),
      ('hospital_applications', 'application_status'),
      ('hospital_applications', 'payment_status'),
      ('hospital_applications', 'hospital_id'),
      ('hospital_subscriptions', 'status'),
      ('hospital_subscriptions', 'start_date'),
      ('hospital_subscriptions', 'end_date'),
      ('hospital_subscriptions', 'last_renewed_at'),
      ('hospital_subscriptions', 'cancel_at_period_end'),
      ('payments', 'paid_at'))
order by table_name, column_name;

-- 5. Existing scheduled jobs, if pg_cron is already enabled (errors harmlessly otherwise).
-- select jobid, jobname, schedule, active from cron.job order by jobid;
