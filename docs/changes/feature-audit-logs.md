# Change record: `feature/audit-logs` → `main`

Prepared 2026-10-27. Base: `origin/main` at `01d4d29` ("Update login page styling and authentication UI").

## 1. Summary

This branch adds three features to LungSight and two small security fixes:

| Area | What it adds |
|---|---|
| **Audit logs** (Phase 1) | Append-only `audit_logs` table and one audit service (`backend/audit.py`). Events are recorded across auth, users, patients, examinations, inpatient care, X-ray, AI, review, applications, hospitals, subscriptions and exports. Includes an Audit Logs page for Hospital Admin (own hospital) and Superadmin (all hospitals), with filters, paging and CSV export. |
| **Hospital Reports** (Phase 2) | Weekly, monthly or custom reports (Asia/Manila days) on screening activity, AI-flagged outcomes, physician review and operations, plus a System activity section from the audit log. One calculation layer feeds the page, the PDF (reportlab) and the Excel export (xlsxwriter). |
| **Email notifications** (Phase 3) | A database outbox filled by triggers in the same transaction as the state change, and a Supabase Edge Function worker using Resend. Covers delivery tracking from verified webhooks, suppression, retries, operational alerts and an Email Notifications history page. Emails: application received, approved and rejected; subscription activated and renewed; expiry reminders (7, 3 and 0 days); operations alerts. All use a branded HTML and plain-text design. |
| Security fixes | The PayMongo webhook no longer logs part of its secret or the request body. The inpatient ward list is now limited to the physician's own hospital (it previously listed every hospital's admitted patients). |
| Proposal only | `docs/proposals/upgrade-payment-fix.*`: a reviewed fix for paid plan upgrades never being applied. **Not applied.** |

## 2. Sync details (this task)

* `git fetch origin`, then `git merge origin/main` → **"Already up to date."** The branch was 0 commits behind `origin/main`.
* **No merge commit was created and there were no conflicts.**
* Local `main` equals `origin/main`. `main` was never modified or pushed.

## 3. Commits

| Commit | When | Content |
|---|---|---|
| `9583367` | earlier feature work | Phase 1: audit logs |
| `2a9a47f` | earlier feature work | Webhook: stop logging secret prefix and request body |
| `a93b9fa` | earlier feature work | Inpatient ward list scoped to the physician's hospital |
| `0d74b25` | earlier feature work | Phase 2: Hospital Reports |
| `1d873a3` | earlier feature work | Phase 3: email outbox, worker, history |
| `254fec6` | earlier feature work | Paid-upgrade fix **proposal** (documents only) |
| `0a06d52` | earlier feature work | Application rejection email |
| `7550a38` | earlier feature work | Branded email design |
| `2fa1cbb` | **this task** | Unused-import cleanup |
| (this file) | **this task** | Change record |

## 4. Files

### Added
* **Audit:** `backend/audit.py`, `streamlit_app/pages/audit_logs.py`, `supabase/migrations/20261025000000_create_audit_logs.sql`.
* **Reports:** `backend/reports/` (`periods.py`, `calculations.py`, `data.py`, `service.py`, `pdf.py`, `excel.py`, `__init__.py`), `streamlit_app/pages/hospital_reports.py`.
* **Email:**
  * `backend/notifications.py` and `streamlit_app/pages/notification_history.py`;
  * the shared modules `supabase/functions/_shared/email/` (`policy.ts`, `providers.ts`, `templates.ts`, `webhook.ts`, `worker.ts`, `store.ts`);
  * the Edge Functions `supabase/functions/email-worker/index.ts` and `supabase/functions/email-events/index.ts`;
  * the migrations `supabase/migrations/20261027000000_email_notifications.sql` and `20261028000000_email_rejection.sql`;
  * the deploy helpers `supabase/deploy/email_preflight_checks.sql`, `email_scheduler.sql` and `email_notifications_rollback.sql`. These are not migrations and are run by hand.
* **Proposal:** `docs/proposals/upgrade-payment-fix.md` and `.patch`.
* **Tests:**
  * pytest: `tests/test_audit*.py`, `test_report_*.py`, `test_notifications.py`, `test_email_node.py`, `test_no_secrets.py`;
  * database tests: `tests/db/audit_logs_rls.mjs` (PGlite) and `tests/db/email_outbox.mjs` (real PostgreSQL 17);
  * Node tests for the Edge Function code: `tests/email/*.test.ts`.
* **This record:** `docs/changes/feature-audit-logs.md`.

### Modified
* `backend/auth.py`, `backend/crud.py`, `backend/backend_utils/{application,hospital,subscription}_utils.py`: audit events after each committed operation.
* `streamlit_app/auth/{auth_manager,login}.py`, `screens/set_password.py`: login, logout and invite-accepted events.
* `streamlit_app/components/{sidebar,navbar}.py`, `layouts/{hospital_admin,system_admin}_layout.py`: navigation for Audit Logs, Hospital Reports and Email Notifications.
* `streamlit_app/pages/system_administrator/reports.py`: the Superadmin "Reports" item now opens Hospital Reports. It was a "coming soon" stub.
* `streamlit_app/pages/physician/{review_patient,inpatient_dashboard}.py`, `pages/radtech/analyze.py`: audit events. The inpatient page also gains the hospital-scoping fix.
* `supabase/functions/paymongo-webhook/index.ts`:
  * audit writes for renewals and application payments, and `payment.unhandled` for unhandled upgrades;
  * removed the secret and body logging;
  * **payment handling logic unchanged.**
* `supabase/config.toml`: registers `email-worker` and `email-events`. They check their own secret or signature, so `verify_jwt = false`.
* `requirements.txt`: `reportlab==4.4.4` and `xlsxwriter==3.2.9` (also fixes a missing newline after `pydicom`).

### Removed
None.

## 5. Cleanup done in this task (`2fa1cbb`)

Unused imports in files this branch already changed. Each name appeared only on its import line, and nothing else imports it through these modules.

| File | Removed |
|---|---|
| `streamlit_app/pages/radtech/analyze.py` | `get_xray_images_by_request`, `get_xray_image_url`, `get_xray_ai_result`, `get_all_patients`, `section_title`, `format_date`, `pill` |
| `streamlit_app/pages/physician/review_patient.py` | `show_rows` |
| `backend/backend_utils/application_utils.py` | unused `supabase` (kept `admin_supabase`) |
| `streamlit_app/layouts/system_admin_layout.py` | unused `import streamlit as st`; duplicate `profile` import (it was already overridden by the next line, so behaviour is unchanged) |

Left on purpose: two unused local variables in the physician review save path (`review_patient.py`). That's clinical code, and I wouldn't change it for cosmetic reasons.

## 6. Migrations

**All three are already applied to the live project.** They were run by hand in the Supabase SQL Editor, not with `supabase db push`.

| Order | File | Purpose | Live status | Requires |
|---|---|---|---|---|
| 1 | `20261025000000_create_audit_logs.sql` | `audit_logs` table, select-only access rules for Hospital Admin (own hospital) and Superadmin, append-only triggers, private helper functions | **Applied.** Verified: the table holds 105 rows; anon and client tokens are denied writes; Hospital Admin A saw only its own rows. | none |
| 2 | `20261027000000_email_notifications.sql` | `email_outbox`, `email_suppressions`, `email_provider_events`, `alert_cooldowns`; enqueue triggers; worker functions; reminders; alerts | **Applied.** Verified: all four tables are live; clients are denied; the worker processes the queue every minute. | 1; Edge Functions `email-worker` and `email-events` |
| 3 | `20261028000000_email_rejection.sql` | Replaces the application trigger and send-time check to add rejection emails | **Applied.** Verified by behaviour: a rejection notice was queued and delivered. | 2; an `email-worker` build that includes the `application.rejected` template |

**UNVERIFIED: migration history.** Supabase's `supabase_migrations.schema_migrations` table probably doesn't list these versions, and it can't be read through the API. Mark them as applied before anyone runs `supabase db push`; see section 10.

### Edge Functions and scheduler (live, outside migrations)

| Item | Live version | Built from |
|---|---|---|
| `email-worker` | v8 (2026-10-27 01:20 UTC) | `7550a38` templates |
| `email-events` | v6 | `1d873a3` |
| `paymongo-webhook` | v13 | webhook code as of `1d873a3` (unchanged since) |
| `pg_cron` jobs | `lungsight-email-worker` (every minute), `lungsight-expiry-reminders` (00:00 UTC) | `supabase/deploy/email_scheduler.sql` |

Version numbers also change when function secrets change, so a higher number doesn't necessarily mean a code change.

## 7. Tests run in this task (actual results)

| Check | Command | Result |
|---|---|---|
| Python tests, including real-PostgreSQL (`email_outbox.mjs`) and PGlite (`audit_logs_rls.mjs`) database tests | `PGLITE_MODULE=… EMAIL_DB_NODE_MODULES=… .venv/Scripts/python -m pytest tests -q` | **158 passed** |
| Edge Function modules | `node --test tests/email/*.test.ts` | **36 tests, 36 passed, 0 failed** |
| App smoke boot (Streamlit AppTest, logged out) and import of the cleaned modules | AppTest on `streamlit_app/app.py` | no exceptions |
| Lint (pyflakes and syntax) on files changed by this branch | `ruff check --select E9,F` | 2 findings: the intentionally kept unused variables in `review_patient.py`. All 13 findings were pre-existing, from code on `main`. |
| Mobile TypeScript (regression only; the branch changes **no** mobile files) | `npx tsc --noEmit` in `mobile_app/` | **9 errors, all pre-existing:** `TS2322` "Property 'role' does not exist" in 9 screen files under `mobile_app/src/app/*/`. Not caused by this branch, so not fixed. |

Not run: `flake8` (not installed), mobile `expo lint` (the branch doesn't touch mobile). The database test dependencies (`@electric-sql/pglite`, `embedded-postgres`, `pg`) were installed outside the repo; without them, those two tests are **skipped**, not failed.

## 8. Environment variables (names only)

* **Streamlit app:** no new variables. Existing: `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SECRET_KEY`, `PAYMONGO_SECRET_KEY`, `APP_BASE_URL`, and optionally `INVITE_REDIRECT_URL`.
* **Edge Function secrets (Supabase):**
  * `EMAIL_WORKER_SECRET`
  * `EMAIL_PROVIDER` (`resend`; anything else means log mode)
  * `RESEND_API_KEY`
  * `RESEND_WEBHOOK_SECRET`
  * `EMAIL_FROM`
  * `EMAIL_REPLY_TO` (optional)
  * `EMAIL_REDIRECT_TO` (staging only: sends every email to one inbox)
  * `APP_BASE_URL` (button link in emails; not set yet)
* **Vault (for `pg_cron`):** `email_worker_url`, `email_worker_secret`.

## 9. Security notes

**Changed (fixed):**
* The webhook no longer logs part of `PAYMONGO_WEBHOOK_SECRET` or request bodies.
* The inpatient ward list and the "rounds today" count were cross-hospital and are now limited to the physician's hospital.
* The Phase 1 webhook audit no longer mislabels upgrade payments as application payments.

**Deferred or unresolved (pre-existing, not changed here):**
* **Paid upgrades are never applied.** A fix is proposed but not applied. It's caught by the `payments_not_applied` operations alert and the `payment.unhandled` audit event.
* **Webhook writes aren't atomic.** If applying a renewal fails after the payment is marked paid, a PayMongo retry does nothing.
* `patients` / `examinations` select policies (`USING (true)`) and other tables with RLS enabled but no policies: UNVERIFIED. The policy catalog wasn't readable.
* Signed-in users can't read their own `hospitals` row, which affects the mobile app's hospital-name lookups.
* Streamlit login uses one shared anon client per process. The sidebar Logout doesn't call Supabase sign-out.
* The application approval flow isn't atomic: a hospital can end up approved with no admin account if the Supabase invitation times out. This happened once in testing.
* **In email redirect mode,** a bounce from the redirect inbox would suppress the *original* recipient. A fix is proposed in conversation; not implemented.
* The audit log's date filter uses UTC days, while the rest of the app uses Asia/Manila.

## 10. Manual steps for you

1. **Decide on your staged files** (`.gitignore`, `CLAUDE.md`, `backend/supabase_client.py`). They are not part of these commits.
2. **Record the migrations as applied** before any future `supabase db push`, for example `supabase migration repair --status applied 20261025000000 20261027000000 20261028000000`. This needs the database password.
3. **After merging,** redeploy the Streamlit app and install the new requirements. Make the app public in Streamlit Cloud, so invitation links and email buttons work.
4. **Before real recipients get email,** remove `EMAIL_REDIRECT_TO`, set `APP_BASE_URL`, and give the remaining Superadmin (`1***@123.com`) an address you read.
5. **Optionally,** review and apply the upgrade-payment proposal in `docs/proposals/`.
