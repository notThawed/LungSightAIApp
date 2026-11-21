-- LungSight AI — mobile access: own-hospital read rules + geospatial counts
--
-- 1. Closes an exposure: the "For Coding" SELECT policies on patients and
--    examinations allowed role PUBLIC (including anonymous callers holding the
--    publishable key shipped in the mobile app) to read every hospital's rows.
-- 2. Signed-in, active staff may READ only their own hospital's rows in
--    hospitals, patients, examinations, follow_ups and xray_requests.
--    No insert/update/delete rights are added. The Streamlit app uses the
--    service role and is unaffected.
-- 3. public.hospital_barangay_cases(year, month): per-barangay counts of
--    first-recorded clinician-confirmed pneumonia patients for the caller's
--    hospital, using the same rules as the Streamlit geospatial page
--    (backend/geospatial_backend). Returns counts only — no patient ids.
--    SECURITY INVOKER, so the read rules above still apply.
--
-- Depends on 20261025000000_create_audit_logs.sql (private schema).

begin;

-- ============================================================
-- 1. REMOVE THE PUBLIC READ POLICIES
-- ============================================================

drop policy if exists "For Coding" on public.patients;
drop policy if exists "For Coding Select" on public.examinations;

-- ============================================================
-- 2. OWN-HOSPITAL READ ACCESS
-- ============================================================

-- Hospital of the signed-in user, or null if inactive / no hospital.
create function private.current_staff_hospital_id()
returns uuid language sql stable security definer set search_path = '' as $$
    select up.hospital_id
    from public.user_profiles up
    where up.user_id = (select auth.uid())
      and up.is_active
$$;

revoke all on function private.current_staff_hospital_id() from public, anon;
grant execute on function private.current_staff_hospital_id() to authenticated;

alter table public.hospitals      enable row level security;
alter table public.patients       enable row level security;
alter table public.examinations   enable row level security;
alter table public.follow_ups     enable row level security;
alter table public.xray_requests  enable row level security;

create policy hospitals_select_own on public.hospitals
    for select to authenticated
    using (hospital_id = (select private.current_staff_hospital_id()));

create policy patients_select_own_hospital on public.patients
    for select to authenticated
    using (hospital_id = (select private.current_staff_hospital_id()));

create policy examinations_select_own_hospital on public.examinations
    for select to authenticated
    using (exists (
        select 1 from public.patients p
        where p.patient_id = examinations.patient_id
          and p.hospital_id = (select private.current_staff_hospital_id())
    ));

create policy follow_ups_select_own_hospital on public.follow_ups
    for select to authenticated
    using (exists (
        select 1 from public.patients p
        where p.patient_id = follow_ups.patient_id
          and p.hospital_id = (select private.current_staff_hospital_id())
    ));

create policy xray_requests_select_own_hospital on public.xray_requests
    for select to authenticated
    using (hospital_id = (select private.current_staff_hospital_id()));

-- ============================================================
-- 3. GEOSPATIAL COUNTS
-- ============================================================

-- Mirrors _normalized_place() in backend/geospatial_backend/patient_location_utils.py.
create function private.geo_normalize(p_value text, p_kind text default '')
returns text language sql immutable set search_path = '' as $$
    select case
        when p_kind = 'city'     then regexp_replace(regexp_replace(s, '^city of ', ''), ' city$', '')
        when p_kind = 'barangay' then regexp_replace(s, '^(barangay|brgy)\s+', '')
        else s
    end
    from (
        select btrim(regexp_replace(
                   regexp_replace(lower(coalesce(p_value, '')), '[^[:alnum:]_[:space:]]', ' ', 'g'),
                   '\s+', ' ', 'g')) as s
    ) normalized
$$;

revoke all on function private.geo_normalize(text, text) from public, anon;
grant execute on function private.geo_normalize(text, text) to authenticated;

-- Mirrors catalog_by_hospital() + first_recorded_confirmed_cases():
--   * barangay key = PSGC code, else a PSGC code inferred from coded patients
--     with the same normalized place (only when unambiguous), else a
--     "legacy:" name key;
--   * a patient counts once, in the Asia/Manila month of their EARLIEST
--     confirmation (reviewed_at, else examination_date) among Completed /
--     Admitted / Discharged examinations confirmed as bacterial or viral
--     pneumonia;
--   * every observed barangay is returned, with 0 when it has no cases.
create function public.hospital_barangay_cases(p_year integer, p_month integer)
returns table (
    barangay_key text,
    province     text,
    city         text,
    barangay     text,
    latitude     double precision,
    longitude    double precision,
    cases        integer
)
language plpgsql stable security invoker set search_path = '' as $$
#variable_conflict use_column
declare
    v_hospital uuid := private.current_staff_hospital_id();
    v_start    timestamptz;
    v_end      timestamptz;
begin
    if v_hospital is null or p_month is null or p_year is null
       or p_month not between 1 and 12 or p_year not between 2000 and 2100 then
        return;
    end if;

    v_start := make_timestamptz(p_year, p_month, 1, 0, 0, 0, 'Asia/Manila');
    v_end   := make_timestamptz(
                   case when p_month = 12 then p_year + 1 else p_year end,
                   case when p_month = 12 then 1 else p_month + 1 end,
                   1, 0, 0, 0, 'Asia/Manila');

    return query
    with pts as (
        select p.patient_id,
               nullif(btrim(coalesce(p.psgc_barangay_code::text, '')), '') as code,
               coalesce(p.province::text, '') as province,
               coalesce(p.city::text, '')     as city,
               coalesce(p.barangay::text, '') as barangay,
               p.latitude::double precision   as lat,
               p.longitude::double precision  as lng,
               p.location_precision::text     as precision,
               private.geo_normalize(p.province::text)             as prov_n,
               private.geo_normalize(p.city::text, 'city')         as city_n,
               private.geo_normalize(p.barangay::text, 'barangay') as brgy_n
        from public.patients p
        where p.hospital_id = v_hospital
    ),
    lookup as (
        select prov_n, city_n, brgy_n, min(code) as code
        from pts
        where code is not null and city_n <> '' and brgy_n <> ''
        group by prov_n, city_n, brgy_n
        having count(distinct code) = 1
    ),
    keyed as (
        select t.*,
               coalesce(t.code, l.code,
                        case when t.city_n <> '' and t.brgy_n <> ''
                             then 'legacy:' || t.prov_n || '|' || t.city_n || '|' || t.brgy_n end) as gkey
        from pts t
        left join lookup l
               on l.prov_n = t.prov_n and l.city_n = t.city_n and l.brgy_n = t.brgy_n
    ),
    catalog as (
        select k.gkey,
               (array_agg(k.province order by (k.code is not null) desc, k.patient_id))[1] as province,
               (array_agg(k.city     order by (k.code is not null) desc, k.patient_id))[1] as city,
               (array_agg(k.barangay order by (k.code is not null) desc, k.patient_id))[1] as barangay,
               (array_agg(k.lat order by k.patient_id)
                    filter (where k.precision = 'barangay' and k.lat is not null and k.lng is not null))[1] as lat,
               (array_agg(k.lng order by k.patient_id)
                    filter (where k.precision = 'barangay' and k.lat is not null and k.lng is not null))[1] as lng
        from keyed k
        where k.gkey is not null
        group by k.gkey
    ),
    first_confirmed as (
        select e.patient_id, min(coalesce(e.reviewed_at, e.examination_date)) as confirmed_at
        from public.examinations e
        join keyed k on k.patient_id = e.patient_id and k.gkey is not null
        where e.status in ('Completed', 'Admitted', 'Discharged')
          and e.confirmed_label in ('bacterial_pneumonia', 'viral_pneumonia')
          and e.examination_date < v_end
          and coalesce(e.reviewed_at, e.examination_date) < v_end
        group by e.patient_id
    ),
    counts as (
        select k.gkey, count(*)::integer as n
        from first_confirmed f
        join keyed k on k.patient_id = f.patient_id
        where f.confirmed_at >= v_start and f.confirmed_at < v_end
        group by k.gkey
    )
    select c.gkey, c.province, c.city, c.barangay, c.lat, c.lng, coalesce(n.n, 0)
    from catalog c
    left join counts n on n.gkey = c.gkey
    order by c.gkey;
end;
$$;

revoke all on function public.hospital_barangay_cases(integer, integer) from public, anon;
grant execute on function public.hospital_barangay_cases(integer, integer) to authenticated;

commit;
