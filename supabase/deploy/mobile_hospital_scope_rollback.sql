-- Rollback for 20261122000000_mobile_hospital_scope.sql.
--
-- Removes the own-hospital read policies and the geospatial function. It does
-- NOT recreate the old "For Coding" policies: those let anonymous callers read
-- every hospital's patients and examinations. After this rollback, signed-in
-- mobile users can no longer read these tables (the Streamlit app is unaffected).

begin;

drop function if exists public.hospital_barangay_cases(integer, integer);
drop function if exists private.geo_normalize(text, text);

drop policy if exists hospitals_select_own on public.hospitals;
drop policy if exists patients_select_own_hospital on public.patients;
drop policy if exists examinations_select_own_hospital on public.examinations;
drop policy if exists follow_ups_select_own_hospital on public.follow_ups;
drop policy if exists xray_requests_select_own_hospital on public.xray_requests;

drop function if exists private.current_staff_hospital_id();

commit;
