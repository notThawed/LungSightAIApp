# Proposal: apply paid plan upgrades in the PayMongo webhook

Status: **proposed, not applied.** The patch is `upgrade-payment-fix.patch` in
this folder. Apply it only after review: `git apply docs/proposals/upgrade-payment-fix.patch`.

## The bug

`create_upgrade_checkout_session()` (backend/payments.py) creates a payment
with `payment_type = 'upgrade'`, `application_id = NULL` and the target
`plan_id`, and its docstring says the upgrade is applied by the webhook.

The webhook (`supabase/functions/paymongo-webhook/index.ts`) only branches on
`payment_type === 'renewal'`. Every other paid payment takes the
application branch, which updates `hospital_applications` where
`application_id = NULL`, which matches nothing. Nothing else calls
`upgrade_subscription()`.

Result today: the hospital is charged, the payment row becomes `paid`, and the
plan never changes. Since Phase 3 this is visible as an audit event
`payment.unhandled` and in the `payments_not_applied` operations alert.

## The proposed change

1. New pure module `supabase/functions/_shared/payments/upgrade.ts` with
   `planUpgrade(payment, subscription, now)`. It mirrors the existing Python
   `upgrade_subscription()` exactly: `previous_plan_id ← plan_id`,
   `plan_id ← payment.plan_id`, `status ← 'Active'`, `last_changed_at` and
   `updated_at ← now`. `end_date` and billing fields are untouched. It refuses
   mismatched hospitals or subscriptions, cancelled subscriptions and
   already-applied upgrades.
2. A new `else if (payment_type === 'upgrade')` branch in the webhook, before
   the application branch. It reads the subscription, applies the update with
   an optimistic guard (`plan_id` must still be the value that was read), and
   writes a `subscription.upgraded` audit event, as success or failure.

Unchanged: signature verification, the `pending → paid` flip, the renewal and
application branches, HTTP responses, and prorated pricing.

## Known limitations (same as the renewal path)

* The payment is marked `paid` before the upgrade is applied. If the update
  fails, the PayMongo retry is a no-op. The failure is audited and the
  `payments_not_applied` alert reports it within the alert's 24-hour cooldown.
  A fully atomic fix would need a database function doing both writes in one
  transaction. That would be a larger payment-logic change and is not
  proposed here.
* Upgrades already paid before this fix are not back-filled automatically. A
  one-off, reviewed SQL statement per payment would be needed.

## Tests

`tests/email/upgrade_proposal.test.ts` (included in the patch), 4 tests, all
passing locally with `node --test`:

* the produced update equals `upgrade_subscription()`;
* `end_date`, `start_date`, `billing_cycle` and `last_renewed_at` are never touched;
* a repeated webhook is a no-op;
* mismatched or missing data is refused.

Not tested: the webhook branch itself against Supabase. There is no Deno
runtime here and no staging project. Deploying needs your approval.

## Also needed before applying

Add `"subscription.upgraded": ("hospital_subscription", {"payment_id": ID})`
to `backend/audit.py` `EVENTS`, so the Audit Logs page labels the event.
