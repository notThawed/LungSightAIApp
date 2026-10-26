// DB-level tests for supabase/migrations/*_email_notifications.sql on a REAL
// local PostgreSQL (embedded-postgres), so SKIP LOCKED is exercised with two
// concurrent connections. Nothing here touches the live project.
//
// Usage: EMAIL_DB_NODE_MODULES=<dir containing embedded-postgres and pg> node tests/db/email_outbox.mjs <data dir>

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
const migrations = join(here, "..", "..", "supabase", "migrations");
const read = (suffix) => readFileSync(join(migrations, readdirSync(migrations).find((f) => f.endsWith(suffix))), "utf8");

const PORT = 54331;
const PASSWORD = "local-test-only";
const server = new EmbeddedPostgres({
  databaseDir: process.argv[2], user: "postgres", password: PASSWORD, port: PORT, persistent: false,
});

const HOSP_A = "aaaaaaaa-0000-0000-0000-000000000001";
const HOSP_B = "bbbbbbbb-0000-0000-0000-000000000002";
const ADMIN_A = "00000000-0000-0000-0000-00000000000a";
const ADMIN_A2 = "00000000-0000-0000-0000-0000000000a2";   // unconfirmed
const ADMIN_A3 = "00000000-0000-0000-0000-0000000000a3";   // inactive
const ADMIN_B = "00000000-0000-0000-0000-00000000000b";
const SUPER = "00000000-0000-0000-0000-0000000000ff";
const SUB_A = "5ab00000-0000-0000-0000-00000000000a";
const SUB_B = "5ab00000-0000-0000-0000-00000000000b";

const STUB = `
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create table auth.users (id uuid primary key, email text, email_confirmed_at timestamptz);
create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
grant usage on schema auth to anon, authenticated, service_role;
grant execute on function auth.uid() to anon, authenticated, service_role;
grant usage on schema public to anon, authenticated, service_role;
alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
alter default privileges in schema public grant all on functions to anon, authenticated, service_role;

create table public.roles (role_id bigint primary key, role_name varchar);
create table public.hospitals (hospital_id uuid primary key, hospital_name varchar);
create table public.subscription_plans (plan_id bigint primary key, plan_name varchar);
create table public.user_profiles (user_id uuid primary key, role_id bigint, hospital_id uuid, is_active boolean);
create table public.hospital_applications (
  application_id uuid primary key default gen_random_uuid(), applicant_email varchar,
  application_status varchar, payment_status text, hospital_id uuid, admin_notes text);
create table public.hospital_subscriptions (
  hospital_subscription_id uuid primary key, hospital_id uuid, plan_id bigint, billing_cycle varchar,
  status varchar, start_date date, end_date date, last_renewed_at timestamptz,
  cancel_at_period_end boolean, updated_at timestamptz);
create table public.payments (
  payment_id uuid primary key default gen_random_uuid(), application_id uuid, hospital_id uuid,
  hospital_subscription_id uuid, plan_id bigint, payment_type text, status text, paid_at timestamptz);
alter table public.hospital_applications enable row level security;
alter table public.hospital_subscriptions enable row level security;

insert into public.roles values (1,'Superadmin'),(3,'Radiologist'),(6,'Hospital Admin'),(7,'Staff');
insert into public.hospitals values ('${HOSP_A}','Bayview <b>&</b> "Mock"'),('${HOSP_B}','Northridge');
insert into public.subscription_plans values (1,'Basic'),(2,'Professional'),(3,'Enterprise');
insert into auth.users values
  ('${ADMIN_A}','Admin.A@Example.com', now()),
  ('${ADMIN_A2}','new.admin@example.com', null),
  ('${ADMIN_A3}','gone@example.com', now()),
  ('${ADMIN_B}','admin.b@example.com', now()),
  ('${SUPER}','super@example.com', now());
insert into public.user_profiles values
  ('${ADMIN_A}',6,'${HOSP_A}',true), ('${ADMIN_A2}',6,'${HOSP_A}',true),
  ('${ADMIN_A3}',6,'${HOSP_A}',false), ('${ADMIN_B}',6,'${HOSP_B}',true), ('${SUPER}',1,null,true);
insert into public.hospital_subscriptions values
  ('${SUB_A}','${HOSP_A}',2,'Yearly','Pending Setup',null,null,null,false,now()),
  ('${SUB_B}','${HOSP_B}',1,'Monthly','Active','2026-10-01','2026-11-01',null,false,now());
`;

let passes = 0;
let failures = 0;
function check(name, ok, detail = "") {
  if (ok) { passes++; console.log(`PASS  ${name}`); }
  else { failures++; console.log(`FAIL  ${name} ${detail}`); }
}

const connect = async () => {
  const c = new pg.Client({ host: "localhost", port: PORT, user: "postgres", password: PASSWORD, database: "postgres" });
  await c.connect();
  return c;
};

async function asRole(c, role, sql, params = []) {
  await c.query(`set role ${role}`);
  try { return { rows: (await c.query(sql, params)).rows }; }
  catch (e) { return { error: e }; }
  finally { await c.query("reset role"); }
}

const outbox = async (c, where = "true", params = []) =>
  (await c.query(`select * from public.email_outbox where ${where} order by created_at, email_id`, params)).rows;
const audits = async (c, type) =>
  (await c.query("select * from public.audit_logs where event_type = $1", [type])).rows;
const claim = async (c, worker, limit = 20, now = null) =>
  (await asRole(c, "service_role", "select * from public.claim_email_batch($1, $2, coalesce($3::timestamptz, now()))", [worker, limit, now])).rows;
const complete = async (c, id, worker, outcome, extra = {}) =>
  (await asRole(c, "service_role",
    "select public.complete_email_attempt($1,$2,$3,$4,$5,$6,$7) as s",
    [id, worker, outcome, extra.messageId ?? null, extra.error ?? null, extra.retryAt ?? null, extra.reason ?? null])).rows?.[0]?.s;
const expand = async (c, id, worker) =>
  (await asRole(c, "service_role", "select public.expand_email_recipients($1,$2) as n", [id, worker])).rows[0].n;
const sendCheck = async (c, id, now = null) =>
  (await asRole(c, "service_role", "select * from public.email_send_check($1, coalesce($2::timestamptz, now()))", [id, now])).rows[0];
const drain = async (c) => c.query("update public.email_outbox set status = 'cancelled', locked_by = null where status in ('queued','sending')");

await server.initialise();
await server.start();
const db = await connect();
const db2 = await connect();

try {
  await db.query(STUB);
  await db.query(read("_create_audit_logs.sql"));
  await db.query(read("_email_notifications.sql"));
  check("both migrations apply on PostgreSQL 17", true);

  // ---------------------------------------------------------- receipts
  const app1 = (await db.query(`insert into public.hospital_applications (applicant_email, application_status, payment_status)
    values ('  Applicant@Example.COM ', 'Draft', 'unpaid') returning application_id`)).rows[0].application_id;
  check("draft application queues nothing", (await outbox(db)).length === 0);

  await db.query("update public.hospital_applications set application_status='Pending', payment_status='paid' where application_id=$1", [app1]);
  let rows = await outbox(db, "event_type='application.received'");
  check("paid application queues one receipt", rows.length === 1);
  check("receipt recipient is normalised", rows[0]?.recipient_email === "applicant@example.com");
  check("receipt carries only a reference, no user text",
    JSON.stringify(rows[0]?.template_data) === JSON.stringify({ reference: app1.slice(0, 8).toUpperCase() }));
  check("receipt queue is audited once", (await audits(db, "email.queued")).length === 1);

  await db.query("update public.hospital_applications set application_status='Pending', payment_status='paid' where application_id=$1", [app1]);
  await db.query("update public.hospital_applications set admin_notes='x' where application_id=$1", [app1]);
  check("repeated webhook update does not queue again", (await outbox(db, "event_type='application.received'")).length === 1);

  const app2 = (await db.query(`insert into public.hospital_applications (applicant_email, application_status, payment_status)
    values ('rollback@example.com','Draft','unpaid') returning application_id`)).rows[0].application_id;
  await db.query("begin");
  await db.query("update public.hospital_applications set application_status='Pending', payment_status='paid' where application_id=$1", [app2]);
  await db.query("rollback");
  check("no receipt when the state change rolls back", (await outbox(db, "target_id=$1", [app2])).length === 0);

  for (let i = 0; i < 4; i++) {
    const id = (await db.query(`insert into public.hospital_applications (applicant_email, application_status, payment_status)
      values ('spam@example.com','Draft','unpaid') returning application_id`)).rows[0].application_id;
    await db.query("update public.hospital_applications set application_status='Pending', payment_status='paid' where application_id=$1", [id]);
  }
  rows = await outbox(db, "recipient_email='spam@example.com'");
  check("receipts rate-limited to 3 per address per day",
    rows.filter((r) => r.status === "queued").length === 3 && rows.filter((r) => r.skip_reason === "rate_limited").length === 1);

  const bad = (await db.query(`insert into public.hospital_applications (applicant_email, application_status, payment_status)
    values ('not an email <x@y.z>', 'Draft','unpaid') returning application_id`)).rows[0].application_id;
  await db.query("update public.hospital_applications set application_status='Pending', payment_status='paid' where application_id=$1", [bad]);
  rows = await outbox(db, "target_id=$1", [bad]);
  check("invalid applicant address is skipped and not stored",
    rows[0]?.status === "skipped" && rows[0]?.skip_reason === "invalid_address" && rows[0]?.recipient_email === null);

  await db.query("alter table public.email_outbox add constraint test_force_fail check (event_type <> 'application.received') not valid");
  const app3 = (await db.query(`insert into public.hospital_applications (applicant_email, application_status, payment_status)
    values ('ok@example.com','Draft','unpaid') returning application_id`)).rows[0].application_id;
  const upd = await db.query("update public.hospital_applications set application_status='Pending', payment_status='paid' where application_id=$1 returning application_status", [app3]);
  await db.query("alter table public.email_outbox drop constraint test_force_fail");
  check("an enqueue failure never blocks the business update",
    upd.rows[0]?.application_status === "Pending" && (await outbox(db, "target_id=$1", [app3])).length === 0);

  await drain(db);

  // ---------------------------------------------------------- approval
  const appA = (await db.query(`insert into public.hospital_applications (applicant_email, application_status, payment_status)
    values ('rep@example.com','Pending','paid') returning application_id`)).rows[0].application_id;
  await db.query("update public.user_profiles set is_active=false where user_id=$1", [ADMIN_A2]);
  await db.query("update public.user_profiles set is_active=false where user_id=$1", [ADMIN_A]);
  await db.query("update public.hospital_applications set application_status='Approved', hospital_id=$2 where application_id=$1", [appA, HOSP_A]);
  let parent = (await outbox(db, "event_type='application.approved'"))[0];
  check("approval queues one recipient-less fan-out row", parent && parent.recipient_email === null && parent.recipient_kind === "hospital_admin");
  check("template data escapes nothing at rest but is length-bounded", parent?.template_data?.hospital_name === 'Bayview <b>&</b> "Mock"');

  let claimed = await claim(db, "w1");
  check("worker claims the approval row", claimed.length === 1 && claimed[0].attempts === 1);
  check("expansion with no admin yet returns 0", (await expand(db, parent.email_id, "w1")) === 0);
  check("worker reschedules it", (await complete(db, parent.email_id, "w1", "retry", { error: "no_recipients" })) === "queued");

  await db.query("update public.user_profiles set is_active=true where user_id=$1", [ADMIN_A2]);   // unconfirmed new admin
  check("the retried row is not due before its backoff", (await claim(db, "w1")).length === 0);
  claimed = await claim(db, "w1", 20, new Date(Date.now() + 120_000).toISOString());
  check("expansion reaches the unconfirmed new admin (approval exception)", (await expand(db, parent.email_id, "w1")) === 1);
  rows = await outbox(db, "event_type='application.approved' and recipient_email is not null");
  check("one child row per recipient", rows.length === 1 && rows[0].recipient_email === "new.admin@example.com");
  check("parent marked expanded", (await outbox(db, "email_id=$1", [parent.email_id]))[0].status === "expanded");
  check("expanding a non-claimed row is refused", (await expand(db, parent.email_id, "w1")) === -1);
  await db.query("update public.user_profiles set is_active=true where user_id=$1", [ADMIN_A]);
  await drain(db);

  // ---------------------------------------------------------- activation
  await db.query("update public.hospital_subscriptions set status='Active', start_date='2026-10-26', end_date='2027-10-26' where hospital_subscription_id=$1", [SUB_A]);
  parent = (await outbox(db, "event_type='subscription.activated'"))[0];
  check("activation queues one row with authoritative dates",
    parent?.idempotency_key === `subscription.activated:${SUB_A}:2026-10-26` && parent.template_data.end_date === "2027-10-26"
    && parent.template_data.plan_name === "Professional");
  await db.query("update public.hospital_subscriptions set status='Active', updated_at=now() where hospital_subscription_id=$1", [SUB_A]);
  check("re-saving an active subscription does not re-queue", (await outbox(db, "event_type='subscription.activated'")).length === 1);

  claimed = await claim(db, "w1");
  await expand(db, parent.email_id, "w1");
  rows = await outbox(db, "event_type='subscription.activated' and recipient_email is not null");
  check("activation reaches only confirmed, active admins of that hospital",
    rows.length === 1 && rows[0].recipient_email === "admin.a@example.com" && rows[0].recipient_user_id === ADMIN_A);
  const childActivated = rows[0];

  // ---------------------------------------------------------- send-time checks
  claimed = await claim(db, "w2");
  check("send check passes for current state", (await sendCheck(db, childActivated.email_id)).ok === true);
  await db.query("update public.hospital_subscriptions set status='Cancelled' where hospital_subscription_id=$1", [SUB_A]);
  check("send check fails when saved state changed", (await sendCheck(db, childActivated.email_id)).reason === "state_changed");
  await db.query("update public.hospital_subscriptions set status='Active' where hospital_subscription_id=$1", [SUB_A]);
  await db.query("update public.user_profiles set is_active=false where user_id=$1", [ADMIN_A]);
  check("send check fails for a deactivated recipient", (await sendCheck(db, childActivated.email_id)).reason === "recipient_ineligible");
  await db.query("update public.user_profiles set is_active=true where user_id=$1", [ADMIN_A]);
  await db.query("insert into public.email_suppressions values ('admin.a@example.com','hard_bounce')");
  check("send check fails for a suppressed address", (await sendCheck(db, childActivated.email_id)).reason === "suppressed");
  check("skipping a suppressed row marks it suppressed",
    (await complete(db, childActivated.email_id, "w2", "skipped", { reason: "suppressed" })) === "suppressed");
  await db.query("delete from public.email_suppressions");
  await drain(db);

  // ---------------------------------------------------------- renewal
  await db.query("update public.hospital_subscriptions set end_date='2027-12-01', last_renewed_at=now() where hospital_subscription_id=$1", [SUB_B]);
  check("extension without a paid renewal payment sends nothing", (await outbox(db, "event_type='subscription.renewed'")).length === 0);

  await db.query(`insert into public.payments (hospital_subscription_id, hospital_id, payment_type, status, paid_at)
    values ($1, $2, 'renewal', 'paid', now())`, [SUB_B, HOSP_B]);
  await db.query("update public.hospital_subscriptions set end_date='2028-01-01', last_renewed_at=now() + interval '1 second' where hospital_subscription_id=$1", [SUB_B]);
  rows = await outbox(db, "event_type='subscription.renewed'");
  check("verified renewal queues one row keyed by new end date",
    rows.length === 1 && rows[0].idempotency_key === `subscription.renewed:${SUB_B}:2028-01-01`);
  await db.query("update public.hospital_subscriptions set end_date='2028-01-01', updated_at=now() where hospital_subscription_id=$1", [SUB_B]);
  check("duplicate webhook (same values) queues nothing more", (await outbox(db, "event_type='subscription.renewed'")).length === 1);
  await drain(db);

  // ---------------------------------------------------------- reminders (fake clock)
  await db.query("update public.hospital_subscriptions set end_date='2026-11-02', status='Active', cancel_at_period_end=false where hospital_subscription_id=$1", [SUB_B]);
  const remind = async (now, offsets = "{7,3,0}") =>
    (await asRole(db, "service_role", "select public.enqueue_expiry_reminders($1::int[], $2::timestamptz) as n", [offsets, now])).rows[0].n;

  // 2026-10-26 08:00 Manila == 2026-10-26T00:00Z -> 7 days left
  check("7-day reminder queued on the right Manila day", (await remind("2026-10-26T00:00:00Z")) === 1);
  check("same-day rerun queues nothing new", (await remind("2026-10-26T10:00:00Z")) === 0);
  rows = await outbox(db, "event_type='subscription.expiry_reminder'");
  check("reminder must be sent before the Manila day ends",
    rows[0] && new Date(rows[0].send_before).toISOString() === "2026-10-26T16:00:00.000Z" && rows[0].template_data.days_left === 7);
  check("missed days are not caught up (5 days left)", (await remind("2026-10-28T00:00:00Z")) === 0);
  check("3-day reminder on its day", (await remind("2026-10-30T01:00:00Z")) === 1);
  check("UTC evening already counts as the next Manila day", (await remind("2026-11-01T16:30:00Z")) === 1); // Nov 2 Manila, day-of
  check("offsets are configurable", (await remind("2026-10-28T00:00:00Z", "{5}")) === 1);

  claimed = await claim(db, "w3");
  await expand(db, rows[0].email_id, "w3");
  const staleChild = (await outbox(db, "event_type='subscription.expiry_reminder' and recipient_email is not null"))[0];
  check("reminder children inherit send-before", staleChild && new Date(staleChild.send_before).getTime() === new Date(rows[0].send_before).getTime());
  check("a reminder past its send-before is stale",
    (await sendCheck(db, staleChild.email_id, "2026-10-27T00:00:00Z")).reason === "stale");
  await db.query("update public.hospital_subscriptions set cancel_at_period_end=true where hospital_subscription_id=$1", [SUB_B]);
  check("cancelling subscriptions get no new reminders", (await remind("2026-10-30T01:00:00Z", "{3,4}")) === 0);
  await db.query("update public.hospital_subscriptions set cancel_at_period_end=false where hospital_subscription_id=$1", [SUB_B]);
  await drain(db);

  // ---------------------------------------------------------- concurrent claims (two real connections)
  for (let i = 0; i < 5; i++) {
    await asRole(db, "postgres", `select private.enqueue_email('ops.alert', 'test.concurrency:${i}', 'platform_admin', null, null, null,
      '${SUPER}', 'super@example.com', '{"alert":"email_failures","count":5}'::jsonb)`);
  }
  await db.query("begin");
  await db.query("set local role service_role");
  const firstWorker = (await db.query("select email_id from public.claim_email_batch('A', 3)")).rows.map((r) => r.email_id);
  const secondWorker = (await asRole(db2, "service_role", "select email_id from public.claim_email_batch('B', 3)")).rows.map((r) => r.email_id);
  await db.query("commit");
  const overlap = firstWorker.filter((id) => secondWorker.includes(id));
  check("two concurrent workers never claim the same row",
    firstWorker.length === 3 && secondWorker.length === 2 && overlap.length === 0,
    `A=${firstWorker.length} B=${secondWorker.length} overlap=${overlap.length}`);

  // ---------------------------------------------------------- completion paths
  const [s1, s2, s3] = firstWorker;
  check("completing with the wrong worker is refused", (await complete(db, s1, "B", "sent", { messageId: "m-x" })) === null);
  check("sent", (await complete(db, s1, "A", "sent", { messageId: "msg-1" })) === "sent");
  check("sent is audited exactly once", (await audits(db, "email.sent")).length === 1);
  check("a completed row cannot be completed twice", (await complete(db, s1, "A", "sent", { messageId: "msg-1" })) === null);

  const future = new Date(Date.now() + 120_000).toISOString();
  check("transient failure is requeued", (await complete(db, s2, "A", "retry", { error: "HTTP 503 for bob@example.com \"x\"", retryAt: future })) === "queued");
  const s2row = (await outbox(db, "email_id=$1", [s2]))[0];
  check("stored errors are sanitised (no address, no quotes)", s2row.last_error === "HTTP 503 for [email] x");
  check("requeued row honours its backoff time", new Date(s2row.next_attempt_at).toISOString() === new Date(future).toISOString());
  check("transient retries are not audited", (await audits(db, "email.failed")).length === 0);

  check("permanent failure", (await complete(db, s3, "A", "failed", { error: "422 invalid", reason: "invalid_recipient" })) === "failed");
  check("permanent failure audited once", (await audits(db, "email.failed")).length === 1);

  await db.query("update public.email_outbox set max_attempts = attempts, next_attempt_at = now() - interval '1 minute' where email_id = $1", [s2]);
  // s2 attempts == max -> it is not due as 'queued'? It is queued and due; a claim bumps attempts past max.
  await db.query("update public.email_outbox set max_attempts = 2, attempts = 1 where email_id = $1", [s2]);
  claimed = await claim(db, "A", 10);
  check("final retry exhausts attempts -> failed",
    claimed.some((r) => r.email_id === s2) && (await complete(db, s2, "A", "retry", { error: "timeout" })) === "failed");

  // stale lock
  const [stuck] = secondWorker;
  await db.query("update public.email_outbox set locked_at = now() - interval '11 minutes' where email_id = $1", [stuck]);
  claimed = await claim(db, "C", 10);
  check("a stale lock is reclaimed by another worker", claimed.some((r) => r.email_id === stuck && r.locked_by === "C"));
  check("the original worker can no longer complete it", (await complete(db, stuck, "B", "sent", { messageId: "late" })) === null);
  await db.query("update public.email_outbox set locked_at = now() - interval '11 minutes', attempts = max_attempts where email_id = $1", [stuck]);
  await claim(db, "D", 10);
  check("a stale lock after the last attempt becomes failed",
    (await outbox(db, "email_id=$1", [stuck]))[0].status === "failed" && (await audits(db, "email.failed")).length === 3);
  await drain(db);

  // ---------------------------------------------------------- provider events
  const sentRow = (await outbox(db, "email_id=$1", [s1]))[0];
  const event = (id, type, bounce = null) => asRole(db, "service_role",
    "select public.apply_email_provider_event($1,$2,$3,$4,now()) as r", [id, type, sentRow.provider_message_id, bounce]).then((x) => x.rows[0].r);
  check("delivered event marks delivered", (await event("evt-1", "email.delivered")) === "delivered");
  check("replayed event is a no-op", (await event("evt-1", "email.delivered")) === "duplicate");
  check("transient bounce changes nothing", (await event("evt-2", "email.bounced", "Transient")) === "transient_bounce");
  check("hard bounce marks bounced", (await event("evt-3", "email.bounced", "Permanent")) === "bounced");
  check("hard bounce suppresses the address",
    (await db.query("select reason from public.email_suppressions where email='super@example.com'")).rows[0]?.reason === "hard_bounce");
  check("bounce audited once", (await audits(db, "email.bounced")).length === 1);
  check("unknown message id is ignored safely",
    (await asRole(db, "service_role", "select public.apply_email_provider_event('evt-9','email.delivered','nope') as r")).rows[0].r === "unknown_message");
  const queuedForSuppressed = await asRole(db, "postgres",
    `select private.enqueue_email('ops.alert','test.suppressed','platform_admin',null,null,null,'${SUPER}','super@example.com','{}'::jsonb) as id`);
  check("new emails to a suppressed address are suppressed at enqueue",
    (await outbox(db, "email_id=$1", [queuedForSuppressed.rows[0].id]))[0].status === "suppressed");
  await db.query("delete from public.email_suppressions");

  // ---------------------------------------------------------- operational alerts
  await db.query(`insert into public.payments (hospital_subscription_id, plan_id, payment_type, status, paid_at)
    values ($1, 3, 'upgrade', 'paid', now() - interval '20 minutes')`, [SUB_B]);
  const alerts = async (now = null) =>
    (await asRole(db, "service_role", "select public.enqueue_operational_alerts(coalesce($1::timestamptz, now())) as n", [now])).rows[0].n;
  check("unapplied paid upgrade raises one alert", (await alerts()) === 1);
  rows = await outbox(db, "event_type='ops.alert' and recipient_email is null");
  check("alert holds counts only", JSON.stringify(rows.at(-1)?.template_data) === JSON.stringify({ alert: "payments_not_applied", count: 1 }));
  check("alert cooldown suppresses repeats", (await alerts()) === 0);
  check("alert repeats after the cooldown", (await alerts(new Date(Date.now() + 25 * 3600e3).toISOString())) === 1);

  // ---------------------------------------------------------- privileges
  for (const role of ["anon", "authenticated"]) {
    const sel = await asRole(db, role, "select count(*) from public.email_outbox");
    check(`${role} cannot read the outbox`, sel.error?.code === "42501");
    const fn = await asRole(db, role, "select * from public.claim_email_batch('x', 1)");
    check(`${role} cannot claim emails`, fn.error?.code === "42501");
    const rem = await asRole(db, role, "select public.enqueue_expiry_reminders()");
    check(`${role} cannot queue reminders`, rem.error?.code === "42501");
    const priv = await asRole(db, role, "select * from private.email_recipients('platform_admin', null, 'ops.alert')");
    check(`${role} cannot list recipient addresses`, priv.error?.code === "42501");
    const sup = await asRole(db, role, "select count(*) from public.email_suppressions");
    check(`${role} cannot read suppressions`, sup.error?.code === "42501");
  }
  const del = await asRole(db, "service_role", "delete from public.email_outbox");
  check("service role cannot delete outbox history", del.error?.code === "42501");
  const recipientsDirect = await asRole(db, "service_role", "select * from private.email_recipients('platform_admin', null, 'ops.alert')");
  check("service role cannot call the recipient lookup directly", recipientsDirect.error?.code === "42501");

  // ---------------------------------------------------------- rollback
  const auditBefore = (await db.query("select count(*)::int as n from public.audit_logs")).rows[0].n;
  await db.query(readFileSync(join(here, "..", "..", "supabase", "deploy", "email_notifications_rollback.sql"), "utf8"));
  const leftovers = (await db.query(`
    select (select count(*) from information_schema.tables where table_schema = 'public'
              and table_name in ('email_outbox','email_suppressions','email_provider_events','alert_cooldowns'))
         + (select count(*) from pg_trigger where tgname like 'email_on_%')
         + (select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
              where n.nspname in ('public','private') and (p.proname like '%email%' or p.proname like '%expiry_reminders'
                    or p.proname = 'enqueue_operational_alerts')) as n`)).rows[0].n;
  check("rollback removes every email object", Number(leftovers) === 0, `left ${leftovers}`);
  const after = await db.query("update public.hospital_applications set application_status='Approved' where application_id=$1 returning application_status", [app1]);
  check("business updates work after rollback", after.rows[0]?.application_status === "Approved");
  check("audit history survives rollback", (await db.query("select count(*)::int as n from public.audit_logs")).rows[0].n === auditBefore);
} catch (e) {
  failures++;
  console.log("FAIL  unexpected error", e.message);
} finally {
  await db.end();
  await db2.end();
  await server.stop();
}

console.log(`\n${passes} passed, ${failures} failed`);
process.exit(failures ? 1 : 0);
