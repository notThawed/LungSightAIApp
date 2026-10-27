-- LungSight AI — Phase 1: append-only audit log
--
-- Writes: trusted server code only (Streamlit backend / Edge Function via the
-- service role). Reads: Hospital Admin (own hospital) and Superadmin (all) via
-- RLS for JWT clients; the Streamlit page enforces the same scope server-side
-- because it uses the service role.

begin;

-- Helper schema; not in the Data API's exposed schemas (public, graphql_public).
create schema if not exists private;
grant usage on schema private to authenticated;

create table public.audit_logs (
    audit_log_id    uuid        primary key default gen_random_uuid(),
    created_at      timestamptz not null default now(),
    actor_user_id   uuid,
    hospital_id     uuid,
    event_type      text        not null,
    event_category  text        generated always as (split_part(event_type, '.', 1)) stored,
    target_type     text,
    target_id       text,
    outcome         text        not null,
    metadata        jsonb       not null default '{}'::jsonb,
    idempotency_key text,

    constraint audit_logs_event_type_format
        check (event_type ~ '^[a-z][a-z_]*\.[a-z][a-z_]*$' and length(event_type) <= 64),
    constraint audit_logs_target_type_format
        check (target_type is null or (target_type ~ '^[a-z][a-z_]*$' and length(target_type) <= 64)),
    constraint audit_logs_target_id_length
        check (target_id is null or length(target_id) <= 128),
    constraint audit_logs_outcome_valid
        check (outcome in ('success', 'failure', 'denied')),
    constraint audit_logs_metadata_object
        check (jsonb_typeof(metadata) = 'object' and octet_length(metadata::text) <= 4096),
    constraint audit_logs_idempotency_key_length
        check (idempotency_key is null or length(idempotency_key) <= 200)
);

-- No foreign keys on actor_user_id / hospital_id: audit rows must outlive the
-- rows they reference, and ON DELETE SET NULL would be an UPDATE that the
-- append-only trigger rejects.

comment on table public.audit_logs is
    'Append-only security/audit trail. Written only by trusted server code (service role).';

create index audit_logs_hospital_created_idx on public.audit_logs (hospital_id, created_at desc);
create index audit_logs_created_idx          on public.audit_logs (created_at desc);
create index audit_logs_actor_created_idx    on public.audit_logs (actor_user_id, created_at desc)
    where actor_user_id is not null;
create unique index audit_logs_idempotency_key_uidx on public.audit_logs (idempotency_key)
    where idempotency_key is not null;

-- Append-only enforcement
create function private.audit_logs_reject_mutation()
returns trigger language plpgsql set search_path = '' as $$
begin
    raise exception 'audit_logs is append-only' using errcode = '42501';
end;
$$;
revoke all on function private.audit_logs_reject_mutation() from public, anon, authenticated;

create trigger audit_logs_no_update_delete
    before update or delete on public.audit_logs
    for each row execute function private.audit_logs_reject_mutation();
create trigger audit_logs_no_truncate
    before truncate on public.audit_logs
    for each statement execute function private.audit_logs_reject_mutation();

-- Grants: Supabase default privileges give anon/authenticated/service_role ALL
-- on new public tables, so reset explicitly.
revoke all on table public.audit_logs from public, anon, authenticated, service_role;
grant select         on table public.audit_logs to authenticated;  -- filtered by RLS below
grant select, insert on table public.audit_logs to service_role;   -- server-side writer/reader

-- RLS helpers: SECURITY DEFINER so they can read user_profiles/roles regardless
-- of those tables' policies; fixed search_path; not executable by anon/public.
create function private.audit_log_viewer_hospital_id()
returns uuid language sql stable security definer set search_path = '' as $$
    select up.hospital_id
    from public.user_profiles up
    join public.roles r on r.role_id = up.role_id
    where up.user_id = (select auth.uid())
      and up.is_active
      and r.role_name = 'Hospital Admin'
$$;

create function private.audit_log_viewer_is_superadmin()
returns boolean language sql stable security definer set search_path = '' as $$
    select exists (
        select 1
        from public.user_profiles up
        join public.roles r on r.role_id = up.role_id
        where up.user_id = (select auth.uid())
          and up.is_active
          and r.role_name = 'Superadmin'
    )
$$;

revoke all on function private.audit_log_viewer_hospital_id()   from public, anon;
revoke all on function private.audit_log_viewer_is_superadmin() from public, anon;
grant execute on function private.audit_log_viewer_hospital_id()   to authenticated;
grant execute on function private.audit_log_viewer_is_superadmin() to authenticated;

alter table public.audit_logs enable row level security;

create policy audit_logs_select_hospital_admin on public.audit_logs
    for select to authenticated
    using (hospital_id is not null
           and hospital_id = (select private.audit_log_viewer_hospital_id()));

create policy audit_logs_select_superadmin on public.audit_logs
    for select to authenticated
    using ((select private.audit_log_viewer_is_superadmin()));

-- No INSERT/UPDATE/DELETE policies: client roles cannot write.

commit;
