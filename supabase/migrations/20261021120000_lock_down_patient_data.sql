-- =====================================================================
-- LungSightAI: lock down anonymous access to patient data
-- =====================================================================
--
-- Finding (2026-10-21, read-only probe with the publishable/anon key and
-- NO login): every row and column of `patients` (17/17, incl. names, birth
-- dates, addresses, contact numbers) and `examinations` (40/40, incl.
-- complaints and diagnoses) was readable anonymously. The storage bucket
-- `consent-signatures` was public.
--
-- The publishable key is not a secret (it ships inside the mobile app), so
-- Row Level Security is the only protection for these tables.
--
-- Impact on the apps:
--   * Web (Streamlit) reads/writes with the service-role key, which BYPASSES
--     RLS -> unaffected.
--   * Mobile reads these tables only for dashboard COUNTS, as a signed-in
--     user -> keeps working through the hospital-scoped SELECT policies below.
--   * Consent signatures are displayed via signed URLs
--     (backend/fetches.py create_signed_url) -> a private bucket is fine.
--
-- HOW TO APPLY: Supabase Dashboard -> SQL Editor -> run STEP 0 first and
-- review the output, then run the whole file. It runs in one transaction.
-- =====================================================================


-- ---------------------------------------------------------------------
-- STEP 0 (review first, read-only): existing policies on these tables.
-- Policies whose `roles` include {anon} or {public} are what exposes data.
-- ---------------------------------------------------------------------
-- select tablename, policyname, roles, cmd, qual
-- from pg_policies
-- where schemaname = 'public'
--   and tablename in ('patients', 'examinations', 'follow_ups')
-- order by tablename, policyname;
--
-- select relname, relrowsecurity
-- from pg_class
-- where relname in ('patients', 'examinations', 'follow_ups');


begin;

-- ---------------------------------------------------------------------
-- 1. Helper: the signed-in user's hospital (NULL for anon / inactive users)
--    SECURITY DEFINER so policies can read user_profiles without
--    depending on (or recursing into) user_profiles' own RLS.
-- ---------------------------------------------------------------------
create or replace function public.current_user_hospital_id()
returns uuid
language sql
stable
security definer
set search_path = public
as $$
    select hospital_id
    from public.user_profiles
    where user_id = auth.uid()
      and is_active = true
    limit 1
$$;

revoke all on function public.current_user_hospital_id() from public, anon;
grant execute on function public.current_user_hospital_id() to authenticated;


-- ---------------------------------------------------------------------
-- 2. Make sure RLS is on (no-op if already enabled)
-- ---------------------------------------------------------------------
alter table public.patients     enable row level security;
alter table public.examinations enable row level security;
alter table public.follow_ups   enable row level security;


-- ---------------------------------------------------------------------
-- 3. Remove every policy on these tables that applies to anon / public.
--    (Neither app needs them: web uses the service role, mobile is
--    always signed in.)
-- ---------------------------------------------------------------------
do $$
declare
    p record;
begin
    for p in
        select tablename, policyname
        from pg_policies
        where schemaname = 'public'
          and tablename in ('patients', 'examinations', 'follow_ups')
          and (roles && array['anon', 'public']::name[])
    loop
        execute format('drop policy %I on public.%I', p.policyname, p.tablename);
        raise notice 'dropped policy % on %', p.policyname, p.tablename;
    end loop;
end
$$;


-- ---------------------------------------------------------------------
-- 4. Signed-in hospital staff may READ their own hospital's records.
--    (No INSERT/UPDATE/DELETE policies: all writes go through the web
--    server's service role.)
-- ---------------------------------------------------------------------
drop policy if exists "hospital members read patients" on public.patients;
create policy "hospital members read patients"
    on public.patients
    for select
    to authenticated
    using (hospital_id = public.current_user_hospital_id());

drop policy if exists "hospital members read examinations" on public.examinations;
create policy "hospital members read examinations"
    on public.examinations
    for select
    to authenticated
    using (
        exists (
            select 1
            from public.patients p
            where p.patient_id = examinations.patient_id
              and p.hospital_id = public.current_user_hospital_id()
        )
    );

drop policy if exists "hospital members read follow_ups" on public.follow_ups;
create policy "hospital members read follow_ups"
    on public.follow_ups
    for select
    to authenticated
    using (
        exists (
            select 1
            from public.patients p
            where p.patient_id = follow_ups.patient_id
              and p.hospital_id = public.current_user_hospital_id()
        )
    );


-- ---------------------------------------------------------------------
-- 5. Patient consent signatures must not be publicly downloadable.
-- ---------------------------------------------------------------------
update storage.buckets
set public = false
where id = 'consent-signatures';

commit;


-- ---------------------------------------------------------------------
-- VERIFY (read-only) after applying:
--   * Re-run STEP 0: only the three "hospital members read ..." policies
--     (roles = {authenticated}) should remain for SELECT.
--   * From the repo: RUN_LIVE_SECURITY_TESTS=1 pytest tests/security
--     (anonymous reads must return no rows).
-- ---------------------------------------------------------------------
