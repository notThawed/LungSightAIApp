// DB-level tests for supabase/migrations/*_mobile_hospital_scope.sql on a REAL
// local PostgreSQL (embedded-postgres). Nothing here touches the live project.
//
// Usage: EMAIL_DB_NODE_MODULES=<dir with embedded-postgres and pg> node tests/db/mobile_scope.mjs <data dir>

import { readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const modulesDir = process.env.EMAIL_DB_NODE_MODULES;
if (!modulesDir) {
  console.error("EMAIL_DB_NODE_MODULES is not set");
  process.exit(2);
}
const require = createRequire(join(modulesDir, "noop.js"));
const EmbeddedPostgres = (await import(pathToFileURL(require.resolve("embedded-postgres")).href)).default;
const pg = require("pg");

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const migrations = join(root, "supabase", "migrations");
const read = (suffix) => readFileSync(join(migrations, readdirSync(migrations).find((f) => f.endsWith(suffix))), "utf8");

const PORT = 54333;
const server = new EmbeddedPostgres({
  databaseDir: process.argv[2], user: "postgres", password: "local-test-only", port: PORT, persistent: false,
});

const HA = "aaaaaaaa-0000-0000-0000-000000000001";
const HB = "bbbbbbbb-0000-0000-0000-000000000002";
const DOC_A = "00000000-0000-0000-0000-00000000000a";
const DOC_B = "00000000-0000-0000-0000-00000000000b";
const OFF_A = "00000000-0000-0000-0000-0000000000a0";   // inactive

const STUB = `
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
grant usage on schema auth to anon, authenticated, service_role;
grant execute on function auth.uid() to anon, authenticated, service_role;
grant usage on schema public to anon, authenticated, service_role;
alter default privileges in schema public grant all on tables to anon, authenticated, service_role;

create table public.roles (role_id bigint primary key, role_name varchar);
create table public.hospitals (hospital_id uuid primary key, hospital_name varchar);
create table public.user_profiles (user_id uuid primary key, role_id bigint, hospital_id uuid, is_active boolean);
create table public.patients (
  patient_id uuid primary key, hospital_id uuid, first_name varchar, last_name varchar,
  psgc_barangay_code varchar, province varchar, city varchar, barangay varchar,
  latitude double precision, longitude double precision, location_precision varchar, created_at timestamptz default now());
create table public.examinations (
  examination_id uuid primary key default gen_random_uuid(), patient_id uuid, status varchar,
  examination_type varchar, confirmed_label text, reviewed_at timestamptz, examination_date timestamptz,
  created_at timestamptz default now());
create table public.follow_ups (follow_up_id uuid primary key default gen_random_uuid(), patient_id uuid,
  follow_up_date date, status text);
create table public.xray_requests (request_id uuid primary key default gen_random_uuid(), hospital_id uuid, status varchar);

alter table public.patients enable row level security;
alter table public.examinations enable row level security;
alter table public.hospitals enable row level security;
-- the exposure being fixed
create policy "For Coding" on public.patients for select using (true);
create policy "For Coding Select" on public.examinations for select using (true);

insert into public.roles values (3,'Radiologist');
insert into public.hospitals values ('${HA}','Hospital A'),('${HB}','Hospital B');
insert into public.user_profiles values ('${DOC_A}',3,'${HA}',true),('${DOC_B}',3,'${HB}',true),('${OFF_A}',3,'${HA}',false);

-- Hospital A patients
insert into public.patients (patient_id, hospital_id, first_name, psgc_barangay_code, province, city, barangay, latitude, longitude, location_precision) values
 ('11111111-0000-0000-0000-000000000001','${HA}','P1','0722217001','Cebu','Cebu City','Lahug',10.33,123.90,'barangay'),
 ('11111111-0000-0000-0000-000000000002','${HA}','P2',null,'Cebu','City of Cebu','Brgy. Lahug',null,null,null),
 ('11111111-0000-0000-0000-000000000003','${HA}','P3',null,'Cebu','Cebu City','Mabolo',null,null,null),
 ('11111111-0000-0000-0000-000000000004','${HA}','P4','0722217002','Cebu','Cebu City','Apas',null,null,null),
 ('11111111-0000-0000-0000-000000000005','${HA}','P5','0722217003','Cebu','Cebu City','Talamban',null,null,null),
 ('11111111-0000-0000-0000-000000000007','${HA}','P7',null,null,null,null,null,null,null);
-- Hospital B patient in the same barangay
insert into public.patients (patient_id, hospital_id, first_name, psgc_barangay_code, province, city, barangay) values
 ('22222222-0000-0000-0000-000000000006','${HB}','P6','0722217001','Cebu','Cebu City','Lahug');

insert into public.examinations (patient_id, status, examination_type, confirmed_label, reviewed_at, examination_date) values
 -- P1: confirmed Oct 5 (Manila)
 ('11111111-0000-0000-0000-000000000001','Completed','General Consult','bacterial_pneumonia','2026-10-05 02:00+00','2026-10-05 01:00+00'),
 -- P2: first confirmed Sep 30 23:30 Manila, again in Oct -> counts in September only
 ('11111111-0000-0000-0000-000000000002','Completed','General Consult','viral_pneumonia',null,'2026-09-30 15:30+00'),
 ('11111111-0000-0000-0000-000000000002','Admitted','Follow-Up Examination','viral_pneumonia','2026-10-10 02:00+00','2026-10-10 01:00+00'),
 -- P3: reviewed Oct 1 00:30 Manila (Sep 30 16:30 UTC) -> October
 ('11111111-0000-0000-0000-000000000003','Discharged','General Consult','bacterial_pneumonia','2026-09-30 16:30+00','2026-09-30 10:00+00'),
 -- P4: not eligible status
 ('11111111-0000-0000-0000-000000000004','Pending','General Consult','bacterial_pneumonia',null,'2026-10-06 01:00+00'),
 -- P5: not pneumonia
 ('11111111-0000-0000-0000-000000000005','Completed','General Consult','normal',null,'2026-10-06 01:00+00'),
 -- P7: no address -> excluded entirely
 ('11111111-0000-0000-0000-000000000007','Completed','General Consult','bacterial_pneumonia',null,'2026-10-06 01:00+00'),
 -- P6: other hospital
 ('22222222-0000-0000-0000-000000000006','Completed','General Consult','bacterial_pneumonia',null,'2026-10-07 01:00+00');

insert into public.follow_ups (patient_id, follow_up_date, status) values
 ('11111111-0000-0000-0000-000000000001','2026-11-22','Scheduled'),
 ('22222222-0000-0000-0000-000000000006','2026-11-22','Scheduled');
insert into public.xray_requests (hospital_id, status) values ('${HA}','Pending'),('${HB}','Pending');
`;

let passes = 0;
let failures = 0;
const check = (name, ok, detail = "") => {
  if (ok) { passes++; console.log(`PASS  ${name}`); } else { failures++; console.log(`FAIL  ${name} ${detail}`); }
};

const db = new pg.Client({ host: "localhost", port: PORT, user: "postgres", password: "local-test-only", database: "postgres" });

async function as(role, sub, sql, params = []) {
  await db.query("reset role");
  await db.query("select set_config('request.jwt.claim.sub', $1, false)", [sub ?? ""]);
  if (role) await db.query(`set role ${role}`);
  try { return { rows: (await db.query(sql, params)).rows }; }
  catch (e) { return { error: e }; }
  finally { await db.query("reset role"); }
}
const count = async (role, sub, table) => {
  const r = await as(role, sub, `select count(*)::int as n from public.${table}`);
  return r.error ? `error ${r.error.code}` : r.rows[0].n;
};
const cases = async (sub, year, month) => {
  const r = await as("authenticated", sub, "select * from public.hospital_barangay_cases($1, $2)", [year, month]);
  if (r.error) return { error: r.error };
  return Object.fromEntries(r.rows.map((x) => [x.barangay_key, x]));
};

await server.initialise();
await server.start();
await db.connect();

try {
  await db.query(STUB);
  check("anonymous could read patients BEFORE the migration (the exposure)", (await count("anon", "", "patients")) === 7);

  await db.query(read("_create_audit_logs.sql"));
  await db.query(read("_mobile_hospital_scope.sql"));
  check("migration applies on PostgreSQL 17", true);

  // ---- exposure closed
  for (const table of ["patients", "examinations", "follow_ups", "hospitals", "xray_requests"]) {
    check(`anonymous sees no ${table}`, (await count("anon", "", table)) === 0);
  }
  const policies = (await db.query("select policyname from pg_policies where policyname in ('For Coding','For Coding Select')")).rows;
  check("the 'For Coding' policies are gone", policies.length === 0);

  // ---- own-hospital isolation
  check("Hospital A user sees only A patients", (await count("authenticated", DOC_A, "patients")) === 6);
  check("Hospital B user sees only B patients", (await count("authenticated", DOC_B, "patients")) === 1);
  check("Hospital A user sees only A examinations", (await count("authenticated", DOC_A, "examinations")) === 7);
  check("Hospital B user sees only B examinations", (await count("authenticated", DOC_B, "examinations")) === 1);
  check("Hospital A user sees only A follow-ups", (await count("authenticated", DOC_A, "follow_ups")) === 1);
  check("Hospital A user sees only A X-ray requests", (await count("authenticated", DOC_A, "xray_requests")) === 1);
  const ownHospital = await as("authenticated", DOC_A, "select hospital_name from public.hospitals");
  check("Hospital A user can read their own hospital name (fixes 'Hospital not assigned')",
    ownHospital.rows?.length === 1 && ownHospital.rows[0].hospital_name === "Hospital A");
  const leak = await as("authenticated", DOC_A, `select count(*)::int n from public.patients where hospital_id = '${HB}'`);
  check("filtering for another hospital returns nothing", leak.rows[0].n === 0);
  check("inactive user sees nothing", (await count("authenticated", OFF_A, "patients")) === 0);
  check("signed-in user without a profile sees nothing",
    (await count("authenticated", "99999999-9999-9999-9999-999999999999", "patients")) === 0);

  // ---- read-only
  const ins = await as("authenticated", DOC_A, `insert into public.patients (patient_id, hospital_id) values (gen_random_uuid(), '${HA}')`);
  check("signed-in users cannot insert patients", ins.error?.code === "42501");
  const upd = await as("authenticated", DOC_A, "update public.patients set first_name = 'x' returning patient_id");
  check("signed-in users cannot update patients", !upd.error && upd.rows.length === 0);

  // ---- geospatial counts (same rules as Streamlit)
  const oct = await cases(DOC_A, 2026, 10);
  check("geospatial function runs for a signed-in user", !oct.error, oct.error?.message);
  check("October: Lahug counts P1 once (legacy 'Brgy. Lahug, City of Cebu' row merged into its PSGC code)",
    oct["0722217001"]?.cases === 1);
  check("October: unmatched legacy barangay keeps its own key", oct["legacy:cebu|cebu|mabolo"]?.cases === 1);
  check("Manila month boundary: 00:30 on Oct 1 Manila counts in October", oct["legacy:cebu|cebu|mabolo"]?.cases === 1);
  check("non-eligible status and non-pneumonia labels count 0", oct["0722217002"]?.cases === 0 && oct["0722217003"]?.cases === 0);
  check("patients without an address are excluded", Object.keys(oct).length === 4);
  check("verified barangay coordinates are returned", oct["0722217001"]?.latitude === 10.33 && oct["0722217001"]?.longitude === 123.9);
  check("display names prefer the PSGC-coded row", oct["0722217001"]?.barangay === "Lahug");

  const sep = await cases(DOC_A, 2026, 9);
  check("September: P2 counted in the month of its FIRST confirmation", sep["0722217001"]?.cases === 1);
  check("September: P3 (Oct 1 Manila) not counted in September", sep["legacy:cebu|cebu|mabolo"]?.cases === 0);

  const otherHospital = await cases(DOC_B, 2026, 10);
  check("Hospital B sees only its own barangay counts", Object.keys(otherHospital).length === 1 && otherHospital["0722217001"]?.cases === 1);

  const inactive = await cases(OFF_A, 2026, 10);
  check("inactive user gets no counts", Object.keys(inactive).length === 0);
  const badMonth = await cases(DOC_A, 2026, 13);
  check("invalid month returns nothing", Object.keys(badMonth).length === 0);
  const anon = await as("anon", "", "select * from public.hospital_barangay_cases(2026, 10)");
  check("anonymous cannot call the geospatial function", anon.error?.code === "42501");
  const priv = await as("anon", "", "select private.current_staff_hospital_id()");
  check("anonymous cannot call the private helper", priv.error?.code === "42501");

  const ids = await as("authenticated", DOC_A, "select * from public.hospital_barangay_cases(2026, 10)");
  check("geospatial rows contain no patient identifiers",
    ids.rows.every((r) => !Object.keys(r).some((k) => /patient|name|first|last/.test(k))));

  // ---- rollback
  await db.query(readFileSync(join(root, "supabase", "deploy", "mobile_hospital_scope_rollback.sql"), "utf8"));
  const left = (await db.query(`select count(*)::int n from pg_policies where policyname like '%own%'`)).rows[0].n;
  check("rollback removes the new policies", left === 0);
  check("rollback does not reopen anonymous access", (await count("anon", "", "patients")) === 0);
} catch (e) {
  failures++;
  console.log("FAIL  unexpected error", e.message);
} finally {
  await db.end();
  await server.stop();
}

console.log(`\n${passes} passed, ${failures} failed`);
process.exit(failures ? 1 : 0);
