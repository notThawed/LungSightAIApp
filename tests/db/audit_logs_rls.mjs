// DB-layer tests for supabase/migrations/*_create_audit_logs.sql.
//
// Runs the real migration inside PGlite (Postgres compiled to WASM) on top of
// a minimal stub of the Supabase pieces it depends on: the anon /
// authenticated / service_role roles, auth.uid(), and the verified columns of
// public.roles, public.user_profiles and public.hospitals.
//
// Usage: PGLITE_MODULE=<path to @electric-sql/pglite/dist/index.js> node tests/db/audit_logs_rls.mjs

import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const modulePath = process.env.PGLITE_MODULE;
if (!modulePath) {
  console.error("PGLITE_MODULE is not set");
  process.exit(2);
}
const { PGlite } = await import(pathToFileURL(modulePath).href);

const here = dirname(fileURLToPath(import.meta.url));
const migrationsDir = join(here, "..", "..", "supabase", "migrations");
const migrationFile = readdirSync(migrationsDir).find((f) => f.endsWith("_create_audit_logs.sql"));
const migrationSql = readFileSync(join(migrationsDir, migrationFile), "utf8");

const HOSP_A = "aaaaaaaa-0000-0000-0000-000000000001";
const HOSP_B = "bbbbbbbb-0000-0000-0000-000000000002";
const ADMIN_A = "00000000-0000-0000-0000-00000000000a";
const ADMIN_B = "00000000-0000-0000-0000-00000000000b";
const RAD_A = "00000000-0000-0000-0000-0000000000ca";
const STAFF_A = "00000000-0000-0000-0000-0000000000da";
const SUPER = "00000000-0000-0000-0000-0000000000ff";
const INACTIVE_ADMIN_A = "00000000-0000-0000-0000-0000000000ee";

const STUB = `
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;

create schema auth;
create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;
grant usage on schema auth to anon, authenticated, service_role;
grant execute on function auth.uid() to anon, authenticated, service_role;
grant usage on schema public to anon, authenticated, service_role;

-- Mimic Supabase's default privileges on new public tables.
alter default privileges in schema public grant all on tables to anon, authenticated, service_role;

create table public.roles (role_id bigint primary key, role_name varchar);
create table public.hospitals (hospital_id uuid primary key);
create table public.user_profiles (
  user_id uuid primary key, role_id bigint references public.roles,
  hospital_id uuid references public.hospitals, is_active boolean
);
alter table public.user_profiles enable row level security;
alter table public.roles enable row level security;

insert into public.roles values (1,'Superadmin'),(3,'Radiologist'),(4,'Radiologic Technologist'),(6,'Hospital Admin'),(7,'Staff');
insert into public.hospitals values ('${HOSP_A}'),('${HOSP_B}');
insert into public.user_profiles values
  ('${ADMIN_A}',6,'${HOSP_A}',true),
  ('${ADMIN_B}',6,'${HOSP_B}',true),
  ('${RAD_A}',3,'${HOSP_A}',true),
  ('${STAFF_A}',7,'${HOSP_A}',true),
  ('${SUPER}',1,null,true),
  ('${INACTIVE_ADMIN_A}',6,'${HOSP_A}',false);
`;

const db = new PGlite();
let failures = 0;
let passes = 0;

function check(name, ok, detail = "") {
  if (ok) {
    passes++;
    console.log(`PASS  ${name}`);
  } else {
    failures++;
    console.log(`FAIL  ${name} ${detail}`);
  }
}

async function as(role, sub, sql, params = []) {
  await db.exec("reset role");
  await db.query("select set_config('request.jwt.claim.sub', $1, false)", [sub ?? ""]);
  if (role) await db.exec(`set role ${role}`);
  try {
    return { rows: (await db.query(sql, params)).rows };
  } catch (e) {
    return { error: e };
  } finally {
    await db.exec("reset role");
  }
}

async function expectError(name, role, sub, sql, codes) {
  const r = await as(role, sub, sql);
  const code = r.error?.code;
  check(name, r.error && codes.includes(code), `got ${r.error ? code + " " + r.error.message : "no error"}`);
}

async function count(role, sub, where = "true") {
  const r = await as(role, sub, `select count(*)::int as n from public.audit_logs where ${where}`);
  return r.error ? `error ${r.error.code}` : r.rows[0].n;
}

await db.exec(STUB);
await db.exec(migrationSql);
check("migration applies cleanly", true);

// ---- writes by the trusted server role -----------------------------------
const ins = await as("service_role", "", `
  insert into public.audit_logs (actor_user_id, hospital_id, event_type, target_type, target_id, outcome, metadata, idempotency_key) values
   ('${ADMIN_A}', '${HOSP_A}', 'user.created', 'user_profile', '${RAD_A}', 'success', '{"role_id": 3}', null),
   ('${ADMIN_B}', '${HOSP_B}', 'patient.created', 'patient', 'p-b-1', 'success', '{}', null),
   (null, null, 'auth.login_failed', null, null, 'failure', '{"reason": "invalid_credentials"}', null),
   ('${ADMIN_A}', '${HOSP_A}', 'auth.login', 'user_profile', '${ADMIN_A}', 'success', '{}', 'auth.login:${ADMIN_A}:session-1')
  returning event_category, created_at`);
check("service_role can insert (incl. null-actor system event)", !ins.error && ins.rows.length === 4, ins.error?.message);
check("event_category is derived from event_type", ins.rows?.[0]?.event_category === "user");
check("created_at defaults to a timestamptz", ins.rows?.[0]?.created_at instanceof Date);

// ---- hospital isolation (RLS) --------------------------------------------
check("Hospital A admin sees only Hospital A rows", (await count("authenticated", ADMIN_A)) === 2);
check("Hospital A admin cannot read Hospital B rows even when filtering for them",
  (await count("authenticated", ADMIN_A, `hospital_id = '${HOSP_B}'`)) === 0);
check("Hospital A admin cannot read platform-wide (null hospital) rows",
  (await count("authenticated", ADMIN_A, "hospital_id is null")) === 0);
check("Hospital B admin sees only Hospital B rows", (await count("authenticated", ADMIN_B)) === 1);
check("Superadmin sees all rows including platform-wide", (await count("authenticated", SUPER)) === 4);
check("Radiologist sees nothing", (await count("authenticated", RAD_A)) === 0);
check("Staff sees nothing", (await count("authenticated", STAFF_A)) === 0);
check("Inactive hospital admin sees nothing", (await count("authenticated", INACTIVE_ADMIN_A)) === 0);
check("Authenticated with no matching profile sees nothing",
  (await count("authenticated", "11111111-1111-1111-1111-111111111111")) === 0);
check("Authenticated with no JWT sub sees nothing", (await count("authenticated", "")) === 0);
await expectError("anon cannot select", "anon", "", "select * from public.audit_logs", ["42501"]);

// ---- client roles cannot write --------------------------------------------
for (const role of ["anon", "authenticated"]) {
  const sub = role === "authenticated" ? ADMIN_A : "";
  await expectError(`${role} cannot insert`, role, sub,
    `insert into public.audit_logs (event_type, outcome) values ('auth.login', 'success')`, ["42501"]);
  await expectError(`${role} cannot update`, role, sub,
    `update public.audit_logs set outcome = 'failure'`, ["42501"]);
  await expectError(`${role} cannot delete`, role, sub, `delete from public.audit_logs`, ["42501"]);
}
await expectError("authenticated (superadmin) cannot update", "authenticated", SUPER,
  `update public.audit_logs set outcome = 'failure'`, ["42501"]);

// ---- append-only even for privileged roles --------------------------------
await expectError("service_role update rejected", "service_role", "",
  `update public.audit_logs set outcome = 'failure'`, ["42501"]);
await expectError("service_role delete rejected", "service_role", "",
  `delete from public.audit_logs`, ["42501"]);
await expectError("table owner update rejected by trigger", null, "",
  `update public.audit_logs set outcome = 'failure'`, ["42501"]);
await expectError("table owner delete rejected by trigger", null, "",
  `delete from public.audit_logs`, ["42501"]);
await expectError("table owner truncate rejected by trigger", null, "",
  `truncate public.audit_logs`, ["42501"]);
check("rows unchanged after mutation attempts", (await count(null, "")) === 4);

// ---- constraints ------------------------------------------------------------
await expectError("duplicate idempotency_key rejected", "service_role", "",
  `insert into public.audit_logs (event_type, outcome, idempotency_key) values ('auth.login','success','auth.login:${ADMIN_A}:session-1')`,
  ["23505"]);
const nulls = await as("service_role", "",
  `insert into public.audit_logs (event_type, outcome) values ('auth.logout','success'),('auth.logout','success') returning 1`);
check("multiple null idempotency keys allowed", !nulls.error && nulls.rows.length === 2, nulls.error?.message);
await expectError("invalid outcome rejected", "service_role", "",
  `insert into public.audit_logs (event_type, outcome) values ('auth.login','maybe')`, ["23514"]);
await expectError("malformed event_type rejected", "service_role", "",
  `insert into public.audit_logs (event_type, outcome) values ('Login Success','success')`, ["23514"]);
await expectError("non-object metadata rejected", "service_role", "",
  `insert into public.audit_logs (event_type, outcome, metadata) values ('auth.login','success','[1,2]')`, ["23514"]);
await expectError("oversized metadata rejected", "service_role", "",
  `insert into public.audit_logs (event_type, outcome, metadata) values ('auth.login','success', jsonb_build_object('x', repeat('a', 5000)))`,
  ["23514"]);

// ---- helper functions are not callable by anon ------------------------------
await expectError("anon cannot execute private helper", "anon", "",
  "select private.audit_log_viewer_is_superadmin()", ["42501"]);
await expectError("anon cannot execute trigger function directly", "anon", "",
  "select private.audit_logs_reject_mutation()", ["42501", "0A000", "42883"]);
const fnCfg = await as(null, "", `
  select p.proname, p.prosecdef, p.proconfig from pg_proc p join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'private' order by 1`);
check("private helpers have a fixed empty search_path",
  fnCfg.rows.every((r) => (r.proconfig || []).includes("search_path=\"\"")), JSON.stringify(fnCfg.rows));
const pol = await as(null, "", "select policyname, cmd from pg_policies where tablename = 'audit_logs' order by 1");
check("only SELECT policies exist", pol.rows.length === 2 && pol.rows.every((r) => r.cmd === "SELECT"), JSON.stringify(pol.rows));

console.log(`\n${passes} passed, ${failures} failed`);
process.exit(failures ? 1 : 0);
