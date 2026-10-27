-- LungSight AI — Phase 3 follow-up: application rejection email
--
-- Replaces two functions from 20261027000000_email_notifications.sql
-- (CREATE OR REPLACE keeps their grants; the trigger stays attached):
--   * private.email_on_application_change: queue 'application.rejected' when a
--     PAID application becomes Rejected (generic notice to the applicant
--     address, reference only, max 3 per address per day); the receipt rate
--     limit now counts receipts only.
--   * public.email_send_check: a rejection is sent only while the application
--     is still Rejected.
--
-- Requires the email-worker version that has the 'application.rejected' template.

begin;

create or replace function private.email_on_application_change() returns trigger
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
                where o.event_type = 'application.received'
                  and o.recipient_email = v_email
                  and o.created_at > now() - interval '24 hours') >= 3
            or (select count(*) from public.email_outbox o
                where o.event_type = 'application.received'
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

        -- Rejection: only for paid applications (the same address already
        -- received the receipt). Generic notice to the untrusted applicant
        -- address: reference only, no reasons, no user-supplied text.
        if new.application_status = 'Rejected'
           and old.application_status is distinct from 'Rejected'
           and new.payment_status = 'paid' then

            v_email  := lower(btrim(new.applicant_email));
            v_status := 'queued';
            v_reason := null;

            if (select count(*) from public.email_outbox o
                where o.event_type = 'application.rejected'
                  and o.recipient_email = v_email
                  and o.created_at > now() - interval '24 hours') >= 3 then
                v_status := 'skipped';
                v_reason := 'rate_limited';
            end if;

            perform private.enqueue_email(
                'application.rejected',
                'application.rejected:' || new.application_id,
                'applicant_receipt', null,
                'hospital_application', new.application_id::text,
                null, v_email,
                jsonb_build_object('reference', upper(left(new.application_id::text, 8))),
                null, v_status, v_reason
            );
        end if;

    exception when others then
        raise warning 'email enqueue failed for application (%)', sqlstate;
    end;

    return new;
end;
$$;

create or replace function public.email_send_check(p_email_id uuid, p_now timestamptz default now())
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
    elsif v.event_type = 'application.rejected' then
        if not exists (select 1 from public.hospital_applications a
                       where a.application_id::text = v.target_id and a.application_status = 'Rejected') then
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

commit;
