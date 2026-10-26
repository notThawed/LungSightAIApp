-- LungSight AI — Phase 3: email notification outbox
--
-- Emails are queued by triggers in the SAME transaction as the business state
-- change, delivered by the email-worker Edge Function (service role), and
-- tracked through the email-events Edge Function (verified provider webhooks).
--
-- Guarantees:
--   * An email row can only exist after its state change committed.
--   * A failure to queue never blocks or rolls back the business update
--     (each trigger body runs in its own exception block).
--   * One row per idempotency key: repeated webhooks / reruns queue once.
--   * Clients (anon/authenticated) have no access to any table or function
--     here; Streamlit reads through the service role with server-side scoping.
--
-- Depends on 20261025000000_create_audit_logs.sql (private schema, audit_logs).

begin;

create schema if not exists private;
grant usage on schema private to service_role;

-- ============================================================
-- TABLES
-- ============================================================

create table public.email_outbox (
    email_id            uuid        primary key default gen_random_uuid(),
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    event_type          text        not null check (event_type ~ '^[a-z][a-z_]*\.[a-z][a-z_]*$'),
    idempotency_key     text        not null unique check (length(idempotency_key) <= 200),
    hospital_id         uuid,
    target_type         text        check (target_type is null or target_type ~ '^[a-z][a-z_]*$'),
    target_id           text        check (target_id is null or length(target_id) <= 128),
    recipient_kind      text        not null check (recipient_kind in ('applicant_receipt', 'hospital_admin', 'platform_admin')),
    recipient_user_id   uuid,
    recipient_email     text        check (recipient_email is null or (length(recipient_email) <= 254 and recipient_email = lower(recipient_email))),
    template_data       jsonb       not null default '{}'::jsonb
                                    check (jsonb_typeof(template_data) = 'object' and octet_length(template_data::text) <= 2048),
    status              text        not null default 'queued' check (status in (
                                        'queued', 'sending', 'sent', 'delivered', 'failed', 'bounced',
                                        'complained', 'suppressed', 'skipped', 'expanded', 'cancelled')),
    attempts            integer     not null default 0 check (attempts >= 0),
    max_attempts        integer     not null default 6 check (max_attempts between 1 and 20),
    next_attempt_at     timestamptz not null default now(),
    send_before         timestamptz,
    locked_at           timestamptz,
    locked_by           text        check (locked_by is null or length(locked_by) <= 64),
    provider_message_id text        check (provider_message_id is null or length(provider_message_id) <= 128),
    last_error          text        check (last_error is null or length(last_error) <= 300),
    skip_reason         text        check (skip_reason is null or skip_reason ~ '^[a-z_]{1,40}$'),
    sent_at             timestamptz,
    delivered_at        timestamptz
);

comment on table public.email_outbox is
    'Transactional email outbox. Written by triggers and the email worker (service role) only.';

create index email_outbox_due_idx on public.email_outbox (next_attempt_at, created_at)
    where status in ('queued', 'sending');
create index email_outbox_hospital_created_idx on public.email_outbox (hospital_id, created_at desc);
create index email_outbox_created_idx on public.email_outbox (created_at desc);
create index email_outbox_recipient_created_idx on public.email_outbox (recipient_email, created_at desc)
    where recipient_email is not null;
create unique index email_outbox_provider_message_uidx on public.email_outbox (provider_message_id)
    where provider_message_id is not null;

create table public.email_suppressions (
    email       text        primary key check (email = lower(email) and length(email) <= 254),
    reason      text        not null check (reason in ('hard_bounce', 'complaint', 'manual')),
    created_at  timestamptz not null default now()
);

create table public.email_provider_events (
    provider_event_id text        primary key check (length(provider_event_id) <= 128),
    received_at       timestamptz not null default now()
);

create table public.alert_cooldowns (
    alert_key    text        primary key check (alert_key ~ '^[a-z_]{1,40}$'),
    last_sent_at timestamptz not null
);

alter table public.email_outbox          enable row level security;
alter table public.email_suppressions    enable row level security;
alter table public.email_provider_events enable row level security;
alter table public.alert_cooldowns       enable row level security;

revoke all on table public.email_outbox, public.email_suppressions,
                    public.email_provider_events, public.alert_cooldowns
    from public, anon, authenticated, service_role;

grant select, insert, update on table public.email_outbox          to service_role;
grant select, insert         on table public.email_suppressions    to service_role;
grant select, insert         on table public.email_provider_events to service_role;
grant select, insert, update on table public.alert_cooldowns       to service_role;

-- No policies and no client grants: anon/authenticated are denied everything.

-- ============================================================
-- HELPERS (private)
-- ============================================================

-- Audit writes from SQL; never raises (an audit failure must not block email
-- processing or the business update that queued it).
create function private.email_audit(
    p_event_type text,
    p_outcome    text,
    p_hospital   uuid,
    p_email_id   uuid,
    p_metadata   jsonb,
    p_key        text
) returns void
language plpgsql security definer set search_path = '' as $$
begin
    insert into public.audit_logs
        (actor_user_id, hospital_id, event_type, target_type, target_id, outcome, metadata, idempotency_key)
    values
        (null, p_hospital, p_event_type, 'email', p_email_id::text, p_outcome, coalesce(p_metadata, '{}'::jsonb), p_key)
    on conflict do nothing;
exception when others then
    raise warning 'email audit write failed (%)', sqlstate;
end;
$$;

create function private.email_clean_error(p_error text) returns text
language sql immutable set search_path = '' as $$
    select nullif(left(regexp_replace(
               regexp_replace(coalesce(p_error, ''), '[^[:space:]]+@[^[:space:]]+', '[email]', 'g'),
               '[^A-Za-z0-9 _.:/\[\]()-]', '', 'g'), 300), '')
$$;

create function private.email_clean_reason(p_reason text) returns text
language sql immutable set search_path = '' as $$
    select case when p_reason ~ '^[a-z_]{1,40}$' then p_reason else 'other' end
$$;

-- Validated recipients for a kind. Hospital admins need a confirmed address,
-- except for application.approved (explicit exception: the address was
-- reviewed when the application was approved and the account was just invited).
create function private.email_recipients(p_kind text, p_hospital uuid, p_event_type text)
returns table (user_id uuid, email text)
language sql stable security definer set search_path = '' as $$
    select u.id, lower(u.email)::text
    from public.user_profiles up
    join public.roles r on r.role_id = up.role_id
    join auth.users u on u.id = up.user_id
    where up.is_active
      and u.email is not null
      and (
            (p_kind = 'hospital_admin'
             and r.role_name = 'Hospital Admin'
             and up.hospital_id = p_hospital
             and (u.email_confirmed_at is not null or p_event_type = 'application.approved'))
         or (p_kind = 'platform_admin'
             and r.role_name = 'Superadmin'
             and u.email_confirmed_at is not null)
      )
$$;

-- Insert one outbox row (no-op if the idempotency key exists). Returns the new
-- email_id, or null when the key already existed.
create function private.enqueue_email(
    p_event_type     text,
    p_key            text,
    p_kind           text,
    p_hospital       uuid,
    p_target_type    text,
    p_target_id      text,
    p_recipient_user uuid,
    p_recipient      text,
    p_data           jsonb,
    p_send_before    timestamptz default null,
    p_status         text default 'queued',
    p_skip_reason    text default null
) returns uuid
language plpgsql security definer set search_path = '' as $$
declare
    v_email  text := lower(btrim(p_recipient));
    v_status text := p_status;
    v_reason text := p_skip_reason;
    v_id     uuid;
begin
    if v_email is not null and v_status = 'queued' then
        if length(v_email) > 254 or v_email !~ '^[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$' then
            v_status := 'skipped';
            v_reason := 'invalid_address';
            v_email  := null;
        elsif exists (select 1 from public.email_suppressions s where s.email = v_email) then
            v_status := 'suppressed';
            v_reason := 'suppressed';
        end if;
    elsif v_email is not null and length(v_email) > 254 then
        v_email := null;
    end if;

    insert into public.email_outbox
        (event_type, idempotency_key, hospital_id, target_type, target_id, recipient_kind,
         recipient_user_id, recipient_email, template_data, status, skip_reason, send_before)
    values
        (p_event_type, p_key, p_hospital, p_target_type, p_target_id, p_kind,
         p_recipient_user, v_email, coalesce(p_data, '{}'::jsonb), v_status, v_reason, p_send_before)
    on conflict (idempotency_key) do nothing
    returning email_id into v_id;

    if v_id is not null and (v_email is not null or p_kind = 'applicant_receipt') then
        perform private.email_audit(
            'email.queued', 'success', p_hospital, v_id,
            jsonb_build_object('notification_event', p_event_type, 'status', v_status),
            'email.queued:' || v_id
        );
    end if;

    return v_id;
end;
$$;

-- ============================================================
-- ENQUEUE TRIGGERS
-- ============================================================

create function private.email_on_application_change() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
    v_email  text;
    v_status text := 'queued';
    v_reason text;
begin
    begin
        -- Receipt: the application became a paid, pending application.
        -- The applicant address is untrusted input, so the receipt carries no
        -- user-supplied text and is rate limited.
        if new.application_status = 'Pending' and new.payment_status = 'paid'
           and not (old.application_status is not distinct from 'Pending'
                    and old.payment_status is not distinct from 'paid') then

            v_email := lower(btrim(new.applicant_email));

            if (select count(*) from public.email_outbox o
                where o.recipient_kind = 'applicant_receipt'
                  and o.recipient_email = v_email
                  and o.created_at > now() - interval '24 hours') >= 3
            or (select count(*) from public.email_outbox o
                where o.recipient_kind = 'applicant_receipt'
                  and o.created_at > now() - interval '1 hour') >= 50 then
                v_status := 'skipped';
                v_reason := 'rate_limited';
            end if;

            perform private.enqueue_email(
                'application.received',
                'application.received:' || new.application_id,
                'applicant_receipt', null,
                'hospital_application', new.application_id::text,
                null, v_email,
                jsonb_build_object('reference', upper(left(new.application_id::text, 8))),
                null, v_status, v_reason
            );
        end if;

        -- Approval: recipients (the new Hospital Admin) are resolved at send
        -- time, because the admin account is created after this update.
        if new.application_status = 'Approved'
           and old.application_status is distinct from 'Approved'
           and new.hospital_id is not null then
            perform private.enqueue_email(
                'application.approved',
                'application.approved:' || new.application_id,
                'hospital_admin', new.hospital_id,
                'hospital_application', new.application_id::text,
                null, null,
                jsonb_build_object(
                    'hospital_name',
                    (select left(h.hospital_name, 120) from public.hospitals h where h.hospital_id = new.hospital_id)
                )
            );
        end if;

    exception when others then
        raise warning 'email enqueue failed for application (%)', sqlstate;
    end;

    return new;
end;
$$;

create trigger email_on_application_change
    after update of application_status, payment_status on public.hospital_applications
    for each row execute function private.email_on_application_change();

create function private.email_subscription_data(p_sub public.hospital_subscriptions) returns jsonb
language sql stable security definer set search_path = '' as $$
    select jsonb_build_object(
        'hospital_name', (select left(h.hospital_name, 120) from public.hospitals h where h.hospital_id = p_sub.hospital_id),
        'plan_name',     (select left(p.plan_name, 60) from public.subscription_plans p where p.plan_id = p_sub.plan_id),
        'start_date',    p_sub.start_date,
        'end_date',      p_sub.end_date
    )
$$;

create function private.email_on_subscription_change() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
    begin
        -- Activation: setup completed (Pending Setup -> Active with a start date).
        if old.status is not distinct from 'Pending Setup'
           and new.status = 'Active'
           and new.start_date is not null then
            perform private.enqueue_email(
                'subscription.activated',
                'subscription.activated:' || new.hospital_subscription_id || ':' || new.start_date,
                'hospital_admin', new.hospital_id,
                'hospital_subscription', new.hospital_subscription_id::text,
                null, null,
                private.email_subscription_data(new)
            );
        end if;

        -- Renewal: only when the extension follows a verified (paid) renewal payment.
        if new.status = 'Active'
           and new.last_renewed_at is not null
           and new.last_renewed_at is distinct from old.last_renewed_at
           and new.end_date > coalesce(old.end_date, date '-infinity')
           and exists (
               select 1 from public.payments p
               where p.hospital_subscription_id = new.hospital_subscription_id
                 and p.payment_type = 'renewal'
                 and p.status = 'paid'
                 and (old.last_renewed_at is null or p.paid_at >= old.last_renewed_at)
           ) then
            perform private.enqueue_email(
                'subscription.renewed',
                'subscription.renewed:' || new.hospital_subscription_id || ':' || new.end_date,
                'hospital_admin', new.hospital_id,
                'hospital_subscription', new.hospital_subscription_id::text,
                null, null,
                private.email_subscription_data(new)
            );
        end if;

    exception when others then
        raise warning 'email enqueue failed for subscription (%)', sqlstate;
    end;

    return new;
end;
$$;

create trigger email_on_subscription_change
    after update on public.hospital_subscriptions
    for each row execute function private.email_on_subscription_change();

-- ============================================================
-- WORKER API (service role only)
-- ============================================================

-- Claim due rows. Two workers never get the same row (FOR UPDATE SKIP LOCKED).
-- Rows stuck in 'sending' longer than the lock timeout are reclaimed; rows that
-- have used all attempts are failed instead.
create function public.claim_email_batch(
    p_worker text,
    p_limit  integer default 20,
    p_now    timestamptz default now()
) returns setof public.email_outbox
language plpgsql set search_path = '' as $$
declare
    r record;
begin
    for r in
        update public.email_outbox
           set status = 'failed', last_error = 'worker lock expired after final attempt',
               locked_at = null, locked_by = null, updated_at = p_now
         where status = 'sending'
           and locked_at < p_now - interval '10 minutes'
           and attempts >= max_attempts
        returning email_id, hospital_id, event_type, attempts, recipient_email
    loop
        if r.recipient_email is not null then
            perform private.email_audit('email.failed', 'failure', r.hospital_id, r.email_id,
                jsonb_build_object('notification_event', r.event_type, 'attempts', r.attempts, 'reason', 'lock_expired'),
                'email.failed:' || r.email_id);
        end if;
    end loop;

    return query
    with due as (
        select o.email_id
          from public.email_outbox o
         where (o.status = 'queued' and o.next_attempt_at <= p_now)
            or (o.status = 'sending' and o.locked_at < p_now - interval '10 minutes')
         order by o.next_attempt_at, o.created_at
         limit least(greatest(coalesce(p_limit, 20), 1), 100)
         for update skip locked
    )
    update public.email_outbox o
       set status = 'sending', locked_at = p_now, locked_by = left(p_worker, 64),
           attempts = o.attempts + 1, updated_at = p_now
      from due
     where o.email_id = due.email_id
    returning o.*;
end;
$$;

-- Fan a claimed recipient-less row out to one row per validated recipient.
-- Returns the number of recipients, 0 when none are eligible yet, -1 when the
-- row is not a claimed fan-out row.
create function public.expand_email_recipients(p_email_id uuid, p_worker text)
returns integer
language plpgsql security definer set search_path = '' as $$
declare
    v public.email_outbox;
    r record;
    n integer := 0;
begin
    select * into v from public.email_outbox o
     where o.email_id = p_email_id
       and o.recipient_email is null
       and o.recipient_kind in ('hospital_admin', 'platform_admin')
       and o.status = 'sending'
       and o.locked_by = p_worker
     for update;

    if not found then
        return -1;
    end if;

    for r in select * from private.email_recipients(v.recipient_kind, v.hospital_id, v.event_type) loop
        perform private.enqueue_email(
            v.event_type, v.idempotency_key || ':' || r.user_id, v.recipient_kind, v.hospital_id,
            v.target_type, v.target_id, r.user_id, r.email, v.template_data, v.send_before
        );
        n := n + 1;
    end loop;

    if n > 0 then
        update public.email_outbox
           set status = 'expanded', locked_at = null, locked_by = null, updated_at = now()
         where email_id = p_email_id;
    end if;

    return n;
end;
$$;

-- Authoritative re-check at send time: the saved business state must still
-- match what the email says, and the recipient must still be eligible.
create function public.email_send_check(p_email_id uuid, p_now timestamptz default now())
returns table (ok boolean, reason text)
language plpgsql stable security definer set search_path = '' as $$
declare
    v public.email_outbox;
begin
    select * into v from public.email_outbox o where o.email_id = p_email_id;

    if not found then
        return query select false, 'missing'::text; return;
    end if;
    if v.recipient_email is null then
        return query select false, 'no_recipient'::text; return;
    end if;
    if exists (select 1 from public.email_suppressions s where s.email = v.recipient_email) then
        return query select false, 'suppressed'::text; return;
    end if;
    if v.send_before is not null and p_now >= v.send_before then
        return query select false, 'stale'::text; return;
    end if;
    if v.recipient_kind in ('hospital_admin', 'platform_admin')
       and not exists (select 1 from private.email_recipients(v.recipient_kind, v.hospital_id, v.event_type) e
                       where e.user_id = v.recipient_user_id and e.email = v.recipient_email) then
        return query select false, 'recipient_ineligible'::text; return;
    end if;

    if v.event_type = 'application.received' then
        if not exists (select 1 from public.hospital_applications a
                       where a.application_id::text = v.target_id and a.payment_status = 'paid') then
            return query select false, 'state_changed'::text; return;
        end if;
    elsif v.event_type = 'application.approved' then
        if not exists (select 1 from public.hospital_applications a
                       where a.application_id::text = v.target_id and a.application_status = 'Approved') then
            return query select false, 'state_changed'::text; return;
        end if;
    elsif v.event_type = 'subscription.activated' then
        if not exists (select 1 from public.hospital_subscriptions s
                       where s.hospital_subscription_id::text = v.target_id and s.status = 'Active'
                         and s.start_date::text = v.template_data ->> 'start_date') then
            return query select false, 'state_changed'::text; return;
        end if;
    elsif v.event_type = 'subscription.renewed' then
        if not exists (select 1 from public.hospital_subscriptions s
                       where s.hospital_subscription_id::text = v.target_id and s.status = 'Active'
                         and s.end_date::text = v.template_data ->> 'end_date') then
            return query select false, 'state_changed'::text; return;
        end if;
    elsif v.event_type = 'subscription.expiry_reminder' then
        if not exists (select 1 from public.hospital_subscriptions s
                       where s.hospital_subscription_id::text = v.target_id and s.status = 'Active'
                         and s.end_date::text = v.template_data ->> 'end_date'
                         and not coalesce(s.cancel_at_period_end, false)) then
            return query select false, 'state_changed'::text; return;
        end if;
    elsif v.event_type <> 'ops.alert' then
        return query select false, 'unknown_event'::text; return;
    end if;

    return query select true, null::text;
end;
$$;

-- Record the outcome of one attempt. Only the worker holding the lock can
-- complete a row; returns the new status, or null if the lock was lost.
create function public.complete_email_attempt(
    p_email_id   uuid,
    p_worker     text,
    p_outcome    text,                 -- sent | retry | failed | skipped
    p_message_id text default null,
    p_error      text default null,
    p_retry_at   timestamptz default null,
    p_reason     text default null,
    p_now        timestamptz default now()
) returns text
language plpgsql security definer set search_path = '' as $$
declare
    v public.email_outbox;
    v_status text;
    v_reason text := private.email_clean_reason(p_reason);
begin
    select * into v from public.email_outbox o
     where o.email_id = p_email_id and o.status = 'sending' and o.locked_by = p_worker
     for update;

    if not found then
        return null;
    end if;

    if p_outcome = 'sent' then
        update public.email_outbox
           set status = 'sent', sent_at = p_now, provider_message_id = left(p_message_id, 128),
               last_error = null, locked_at = null, locked_by = null, updated_at = p_now
         where email_id = p_email_id;
        perform private.email_audit('email.sent', 'success', v.hospital_id, v.email_id,
            jsonb_build_object('notification_event', v.event_type, 'attempts', v.attempts),
            'email.sent:' || v.email_id);
        return 'sent';
    end if;

    if p_outcome = 'skipped' then
        v_status := case when v_reason = 'suppressed' then 'suppressed' else 'skipped' end;
        update public.email_outbox
           set status = v_status, skip_reason = v_reason, locked_at = null, locked_by = null, updated_at = p_now
         where email_id = p_email_id;
        return v_status;
    end if;

    if p_outcome = 'retry' and v.attempts < v.max_attempts then
        update public.email_outbox
           set status = 'queued', next_attempt_at = coalesce(p_retry_at, p_now + interval '1 minute'),
               last_error = private.email_clean_error(p_error), locked_at = null, locked_by = null, updated_at = p_now
         where email_id = p_email_id;
        return 'queued';
    end if;

    -- permanent failure, or retries exhausted
    update public.email_outbox
       set status = 'failed', last_error = private.email_clean_error(p_error),
           skip_reason = case when p_outcome = 'retry' then 'retries_exhausted' else v_reason end,
           locked_at = null, locked_by = null, updated_at = p_now
     where email_id = p_email_id;

    if v.recipient_email is not null then
        perform private.email_audit('email.failed', 'failure', v.hospital_id, v.email_id,
            jsonb_build_object('notification_event', v.event_type, 'attempts', v.attempts,
                               'reason', case when p_outcome = 'retry' then 'retries_exhausted' else v_reason end),
            'email.failed:' || v.email_id);
    end if;

    return 'failed';
end;
$$;

-- Apply one verified provider webhook event. Replays are no-ops.
create function public.apply_email_provider_event(
    p_event_id    text,
    p_type        text,
    p_message_id  text,
    p_bounce_type text default null,
    p_occurred_at timestamptz default null
) returns text
language plpgsql security definer set search_path = '' as $$
declare
    v public.email_outbox;
begin
    insert into public.email_provider_events (provider_event_id) values (left(p_event_id, 128))
    on conflict do nothing;

    if not found then
        return 'duplicate';
    end if;

    select * into v from public.email_outbox o where o.provider_message_id = p_message_id for update;

    if not found then
        return 'unknown_message';
    end if;

    if p_type = 'email.delivered' then
        if v.status = 'sent' then
            update public.email_outbox
               set status = 'delivered', delivered_at = coalesce(p_occurred_at, now()), updated_at = now()
             where email_id = v.email_id;
            return 'delivered';
        end if;
        return 'ignored';
    end if;

    if p_type = 'email.bounced' then
        if lower(coalesce(p_bounce_type, '')) not in ('permanent', 'hard') then
            return 'transient_bounce';
        end if;
        update public.email_outbox set status = 'bounced', updated_at = now() where email_id = v.email_id;
        insert into public.email_suppressions (email, reason) values (v.recipient_email, 'hard_bounce')
        on conflict do nothing;
        perform private.email_audit('email.bounced', 'failure', v.hospital_id, v.email_id,
            jsonb_build_object('notification_event', v.event_type), 'email.bounced:' || v.email_id);
        return 'bounced';
    end if;

    if p_type = 'email.complained' then
        update public.email_outbox set status = 'complained', updated_at = now() where email_id = v.email_id;
        insert into public.email_suppressions (email, reason) values (v.recipient_email, 'complaint')
        on conflict do nothing;
        perform private.email_audit('email.complained', 'failure', v.hospital_id, v.email_id,
            jsonb_build_object('notification_event', v.event_type), 'email.complained:' || v.email_id);
        return 'complained';
    end if;

    return 'ignored';
end;
$$;

-- Daily reminder scan. Only the reminder whose offset matches today's
-- (Asia/Manila) days-left is queued, and it must be sent before the day ends,
-- so a missed run never sends stale reminders later.
create function public.enqueue_expiry_reminders(
    p_offsets integer[] default array[7, 3, 0],
    p_now     timestamptz default now()
) returns integer
language plpgsql security definer set search_path = '' as $$
declare
    v_today  date := (p_now at time zone 'Asia/Manila')::date;
    v_before timestamptz := ((v_today + 1)::timestamp at time zone 'Asia/Manila');
    s        public.hospital_subscriptions;
    v_days   integer;
    n        integer := 0;
begin
    for s in
        select *
          from public.hospital_subscriptions x
         where x.status = 'Active'
           and x.end_date is not null
           and not coalesce(x.cancel_at_period_end, false)
           and (x.end_date - v_today) = any (p_offsets)
    loop
        v_days := s.end_date - v_today;

        if private.enqueue_email(
            'subscription.expiry_reminder',
            'subscription.expiry_reminder:' || s.hospital_subscription_id || ':' || s.end_date || ':' || v_days || 'd',
            'hospital_admin', s.hospital_id,
            'hospital_subscription', s.hospital_subscription_id::text,
            null, null,
            private.email_subscription_data(s) || jsonb_build_object('days_left', v_days),
            v_before
        ) is not null then
            n := n + 1;
        end if;
    end loop;

    return n;
end;
$$;

-- Operational alerts for reliably detectable conditions, with a 24-hour
-- cooldown per alert. Content is counts only.
create function public.enqueue_operational_alerts(p_now timestamptz default now())
returns integer
language plpgsql security definer set search_path = '' as $$
declare
    v_alerts jsonb := '[]'::jsonb;
    v_item   jsonb;
    v_count  integer;
    n        integer := 0;
begin
    select count(*) into v_count
      from public.payments p
     where p.status = 'paid'
       and p.paid_at < p_now - interval '15 minutes'
       and p.paid_at > p_now - interval '30 days'
       and (
            (p.payment_type = 'renewal'
             and not exists (select 1 from public.hospital_subscriptions s
                             where s.hospital_subscription_id = p.hospital_subscription_id
                               and s.last_renewed_at >= p.paid_at))
         or (p.payment_type = 'upgrade'
             and not exists (select 1 from public.hospital_subscriptions s
                             where s.hospital_subscription_id = p.hospital_subscription_id
                               and s.plan_id = p.plan_id))
         or (p.payment_type is distinct from 'renewal' and p.payment_type is distinct from 'upgrade'
             and (p.application_id is null
                  or not exists (select 1 from public.hospital_applications a
                                 where a.application_id = p.application_id
                                   and a.application_status in ('Pending', 'Approved', 'Rejected'))))
       );
    if v_count > 0 then
        v_alerts := v_alerts || jsonb_build_object('alert', 'payments_not_applied', 'count', v_count);
    end if;

    select count(*) into v_count
      from public.email_outbox o
     where o.status = 'failed'
       and o.event_type <> 'ops.alert'
       and o.updated_at > p_now - interval '1 hour';
    if v_count >= 5 then
        v_alerts := v_alerts || jsonb_build_object('alert', 'email_failures', 'count', v_count);
    end if;

    for v_item in select * from jsonb_array_elements(v_alerts) loop
        if exists (select 1 from public.alert_cooldowns c
                   where c.alert_key = v_item ->> 'alert'
                     and c.last_sent_at > p_now - interval '24 hours') then
            continue;
        end if;

        insert into public.alert_cooldowns (alert_key, last_sent_at)
        values (v_item ->> 'alert', p_now)
        on conflict (alert_key) do update set last_sent_at = excluded.last_sent_at;

        perform private.enqueue_email(
            'ops.alert',
            'ops.alert:' || (v_item ->> 'alert') || ':' || to_char(p_now at time zone 'UTC', 'YYYYMMDDHH24MI'),
            'platform_admin', null, null, null, null, null,
            v_item
        );
        n := n + 1;
    end loop;

    return n;
end;
$$;

-- ============================================================
-- FUNCTION PRIVILEGES
-- ============================================================

revoke all on function private.email_audit(text, text, uuid, uuid, jsonb, text)                  from public, anon, authenticated;
revoke all on function private.email_clean_error(text)                                              from public, anon, authenticated;
revoke all on function private.email_clean_reason(text)                                             from public, anon, authenticated;
revoke all on function private.email_recipients(text, uuid, text)                                   from public, anon, authenticated;
revoke all on function private.enqueue_email(text, text, text, uuid, text, text, uuid, text, jsonb, timestamptz, text, text)
                                                                                                    from public, anon, authenticated;
revoke all on function private.email_on_application_change()                                        from public, anon, authenticated;
revoke all on function private.email_on_subscription_change()                                       from public, anon, authenticated;
revoke all on function private.email_subscription_data(public.hospital_subscriptions)               from public, anon, authenticated;

revoke all on function public.claim_email_batch(text, integer, timestamptz)                         from public, anon, authenticated;
revoke all on function public.expand_email_recipients(uuid, text)                                   from public, anon, authenticated;
revoke all on function public.email_send_check(uuid, timestamptz)                                   from public, anon, authenticated;
revoke all on function public.complete_email_attempt(uuid, text, text, text, text, timestamptz, text, timestamptz)
                                                                                                    from public, anon, authenticated;
revoke all on function public.apply_email_provider_event(text, text, text, text, timestamptz)       from public, anon, authenticated;
revoke all on function public.enqueue_expiry_reminders(integer[], timestamptz)                      from public, anon, authenticated;
revoke all on function public.enqueue_operational_alerts(timestamptz)                               from public, anon, authenticated;

grant execute on function private.email_audit(text, text, uuid, uuid, jsonb, text)                  to service_role;
grant execute on function private.email_clean_error(text)                                           to service_role;
grant execute on function private.email_clean_reason(text)                                          to service_role;
grant execute on function public.claim_email_batch(text, integer, timestamptz)                      to service_role;
grant execute on function public.expand_email_recipients(uuid, text)                                to service_role;
grant execute on function public.email_send_check(uuid, timestamptz)                                to service_role;
grant execute on function public.complete_email_attempt(uuid, text, text, text, text, timestamptz, text, timestamptz)
                                                                                                    to service_role;
grant execute on function public.apply_email_provider_event(text, text, text, text, timestamptz)    to service_role;
grant execute on function public.enqueue_expiry_reminders(integer[], timestamptz)                   to service_role;
grant execute on function public.enqueue_operational_alerts(timestamptz)                            to service_role;

commit;
