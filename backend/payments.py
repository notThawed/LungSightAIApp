import os
import requests

from datetime import datetime, timezone, date
from backend.supabase_client import admin_supabase


PAYMONGO_SECRET_KEY = os.getenv("PAYMONGO_SECRET_KEY")
PAYMONGO_API_BASE   = "https://api.paymongo.com/v1"

APP_BASE_URL = os.getenv(
    "APP_BASE_URL",
    "http://localhost:8501"
)

PAYMENT_SUCCESS_URL = f"{APP_BASE_URL}/?payment=success"
PAYMENT_FAILED_URL  = f"{APP_BASE_URL}/?payment=failed"


# ============================================================
# CREATE CHECKOUT SESSION
# ============================================================

def create_checkout_session(application_id):

    try:

        # ------------------------------------------
        # 1. Fetch application
        # ------------------------------------------

        app_response = (
            admin_supabase
            .table("hospital_applications")
            .select(
                "application_id,"
                "hospital_name,"
                "selected_plan_id,"
                "billing_cycle,"
                "applicant_email,"
                "payment_status"
            )
            .eq("application_id", application_id)
            .single()
            .execute()
        )

        application = app_response.data

        if not application:
            return {
                "success": False,
                "message": "Application not found."
            }

        # ------------------------------------------
        # 2. Recompute amount server-side
        # ------------------------------------------

        plan_response = (
            admin_supabase
            .table("subscription_plans")
            .select(
                "plan_id, plan_name,"
                "price_monthly, price_yearly"
            )
            .eq(
                "plan_id",
                application["selected_plan_id"]
            )
            .single()
            .execute()
        )

        plan = plan_response.data

        if not plan:
            return {
                "success": False,
                "message": "Selected plan no longer exists."
            }

        billing_cycle = application["billing_cycle"]

        if billing_cycle == "Yearly":
            amount = float(plan["price_yearly"])
        else:
            amount = float(plan["price_monthly"])

        amount_cents = int(round(amount * 100))

        # ------------------------------------------
        # 3. Create pending payment row
        # ------------------------------------------

        payment_row = (
            admin_supabase
            .table("payments")
            .insert({
                "application_id": application_id,
                "plan_id": application["selected_plan_id"],
                "provider": "paymongo",
                "amount": amount,
                "currency": "PHP",
                "billing_cycle": billing_cycle,
                "status": "pending",
            })
            .execute()
        )

        if not payment_row.data:
            return {
                "success": False,
                "message": "Could not create payment record."
            }

        payment_id = payment_row.data[0]["payment_id"]

        # ------------------------------------------
        # 4. Create PayMongo checkout session
        # ------------------------------------------

        payload = {
            "data": {
                "attributes": {
                    "line_items": [{
                        "currency": "PHP",
                        "amount": amount_cents,
                        "name": plan["plan_name"],
                        "quantity": 1,
                        "description": (
                            f"{billing_cycle} subscription for "
                            f"{application['hospital_name']}"
                        ),
                    }],
                    "payment_method_types": [
                        "card",
                        "gcash",
                        "paymaya",
                    ],
                    "success_url": PAYMENT_SUCCESS_URL,
                    "cancel_url":  PAYMENT_FAILED_URL,
                    "description": (
                        f"LungSight {plan['plan_name']} "
                        f"({billing_cycle})"
                    ),
                    "send_email_receipt": True,
                    "metadata": {
                        "application_id": application_id,
                        "payment_id": payment_id,
                    },
                }
            }
        }

        auth = (PAYMONGO_SECRET_KEY, "")

        pm_response = requests.post(
            f"{PAYMONGO_API_BASE}/checkout_sessions",
            json=payload,
            auth=auth,
            timeout=20,
        )

        pm_response.raise_for_status()

        pm_data = pm_response.json()["data"]

        checkout_url = pm_data["attributes"]["checkout_url"]
        checkout_id  = pm_data["id"]

        # ------------------------------------------
        # 5. Save provider reference
        # ------------------------------------------

        admin_supabase.table("payments").update({
            "provider_reference": checkout_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("payment_id", payment_id).execute()

        # ------------------------------------------
        # 6. Mark application as pending payment
        # ------------------------------------------

        admin_supabase.table("hospital_applications").update({
            "payment_status": "pending",
        }).eq("application_id", application_id).execute()

        return {
            "success": True,
            "checkout_url": checkout_url,
            "payment_id": payment_id,
            "amount": amount,
            "currency": "PHP",
            "billing_cycle": billing_cycle,
        }

    except requests.HTTPError as http_err:

        return {
            "success": False,
            "message": (
                f"PayMongo error: "
                f"{http_err.response.text}"
            ),
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e),
        }


# ============================================================
# GET PAYMENT STATUS
# ============================================================

def get_payment_status(application_id):

    try:

        response = (
            admin_supabase
            .table("payments")
            .select("status, paid_at, amount, currency")
            .eq("application_id", application_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not response.data:
            return {
                "status": "none",
                "paid": False,
            }

        row = response.data[0]

        return {
            "status": row["status"],
            "paid": row["status"] == "paid",
            "paid_at": row.get("paid_at"),
            "amount": row.get("amount"),
            "currency": row.get("currency"),
        }

    except Exception as e:

        return {
            "status": "error",
            "paid": False,
            "message": str(e),
        }


def create_renewal_checkout_session(hospital_subscription_id):
    """
    Creates a PayMongo checkout session to renew an existing
    hospital subscription.

    The plan and billing cycle are taken from the subscription
    row — the user does not choose.

    Returns:
        {
            "success": True,
            "checkout_url": str,
            "payment_id": uuid,
            "amount": float,
            "currency": "PHP",
            "billing_cycle": str,
        }
        or
        {
            "success": False,
            "message": str,
        }
    """

    try:

        # ------------------------------------------
        # 1. Fetch the subscription
        # ------------------------------------------

        sub_response = (
            admin_supabase
            .table("hospital_subscriptions")
            .select(
                "hospital_subscription_id,"
                "hospital_id,"
                "plan_id,"
                "billing_cycle,"
                "status"
            )
            .eq(
                "hospital_subscription_id",
                hospital_subscription_id
            )
            .single()
            .execute()
        )

        subscription = sub_response.data

        if not subscription:

            return {
                "success": False,
                "message": "Subscription not found."
            }

        hospital_id = subscription["hospital_id"]
        plan_id     = subscription["plan_id"]
        billing_cycle = subscription["billing_cycle"]

        if billing_cycle not in ["Monthly", "Yearly"]:

            return {
                "success": False,
                "message": "Invalid billing cycle on subscription."
            }

        # ------------------------------------------
        # 2. Fetch the plan for pricing
        # ------------------------------------------

        plan_response = (
            admin_supabase
            .table("subscription_plans")
            .select(
                "plan_id, plan_name,"
                "price_monthly, price_yearly"
            )
            .eq("plan_id", plan_id)
            .single()
            .execute()
        )

        plan = plan_response.data

        if not plan:

            return {
                "success": False,
                "message": "Subscription plan not found."
            }

        if billing_cycle == "Yearly":
            amount = float(plan["price_yearly"])
        else:
            amount = float(plan["price_monthly"])

        amount_cents = int(round(amount * 100))

        # ------------------------------------------
        # 3. Insert a pending payment row
        # ------------------------------------------

        payment_row = (
            admin_supabase
            .table("payments")
            .insert({
                "application_id":          None,
                "hospital_id":             hospital_id,
                "hospital_subscription_id": hospital_subscription_id,
                "plan_id":                 plan_id,
                "provider":                "paymongo",
                "amount":                  amount,
                "currency":                "PHP",
                "billing_cycle":           billing_cycle,
                "payment_type":            "renewal",
                "status":                  "pending",
            })
            .execute()
        )

        if not payment_row.data:

            return {
                "success": False,
                "message": "Could not create payment record."
            }

        payment_id = payment_row.data[0]["payment_id"]

        # ------------------------------------------
        # 4. Create PayMongo checkout session
        # ------------------------------------------

        payload = {
            "data": {
                "attributes": {
                    "line_items": [{
                        "currency": "PHP",
                        "amount":   amount_cents,
                        "name":     f"{plan['plan_name']} — Renewal",
                        "quantity": 1,
                        "description": (
                            f"{billing_cycle} renewal of "
                            f"{plan['plan_name']} subscription"
                        ),
                    }],
                    "payment_method_types": [
                        "card",
                        "gcash",
                        "paymaya",
                    ],
                    "success_url": PAYMENT_SUCCESS_URL,
                    "cancel_url":  PAYMENT_FAILED_URL,
                    "description": (
                        f"LungSight renewal — "
                        f"{plan['plan_name']} ({billing_cycle})"
                    ),
                    "send_email_receipt": True,
                    "metadata": {
                        "hospital_subscription_id": hospital_subscription_id,
                        "payment_id":               payment_id,
                        "payment_type":             "renewal",
                    },
                }
            }
        }

        auth = (PAYMONGO_SECRET_KEY, "")

        pm_response = requests.post(
            f"{PAYMONGO_API_BASE}/checkout_sessions",
            json=payload,
            auth=auth,
            timeout=20,
        )

        pm_response.raise_for_status()

        pm_data = pm_response.json()["data"]

        checkout_url = pm_data["attributes"]["checkout_url"]
        checkout_id  = pm_data["id"]

        # ------------------------------------------
        # 5. Save the provider reference
        # ------------------------------------------

        admin_supabase.table("payments").update({
            "provider_reference": checkout_id,
            "updated_at":         datetime.now(timezone.utc).isoformat(),
        }).eq("payment_id", payment_id).execute()

        # ------------------------------------------
        # 6. Return success
        # ------------------------------------------

        return {
            "success":       True,
            "checkout_url":  checkout_url,
            "payment_id":    payment_id,
            "amount":        amount,
            "currency":      "PHP",
            "billing_cycle": billing_cycle,
        }

    except requests.HTTPError as http_err:

        return {
            "success": False,
            "message": (
                f"PayMongo error: "
                f"{http_err.response.text}"
            ),
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e),
        }


def get_renewal_status(payment_id):
    """
    Returns the current status of a renewal payment row.

    Used by the "Refresh Status" button on the renewal
    success screen.
    """

    try:

        response = (
            admin_supabase
            .table("payments")
            .select(
                "status, paid_at, amount, currency"
            )
            .eq(
                "payment_id",
                payment_id
            )
            .single()
            .execute()
        )

        row = response.data

        if not row:

            return {
                "status": "none",
                "paid":   False,
            }

        return {
            "status":   row["status"],
            "paid":     row["status"] == "paid",
            "paid_at":  row.get("paid_at"),
            "amount":   row.get("amount"),
            "currency": row.get("currency"),
        }

    except Exception as e:

        return {
            "status":  "error",
            "paid":    False,
            "message": str(e),
        }

def compute_prorated_amount(
    hospital_subscription_id,
    new_plan_id,
):
    """
    Compute the prorated charge for upgrading from the
    current plan to a new plan mid-cycle.

    Formula:

        days_left_in_cycle   = (end_date - today).days
        cycle_days           = 30 (Monthly) or 365 (Yearly)
        old_price_per_day    = old_price / cycle_days
        new_price_per_day    = new_price / cycle_days

        prorated_amount      = (new_price_per_day - old_price_per_day)
                               * days_left_in_cycle

    Returns:
        {
            "success": True,
            "amount": float,              # e.g. 208.33
            "currency": "PHP",
            "days_left": int,             # e.g. 15
            "cycle_days": int,            # 30 or 365
            "old_plan_name": str,
            "new_plan_name": str,
            "old_price": float,
            "new_price": float,
            "billing_cycle": str,
        }
        or
        {
            "success": False,
            "message": str,
        }

    Callers should only apply this when new_price > old_price.
    A downgrade never uses this function.
    """

    if not hospital_subscription_id:
        return {
            "success": False,
            "message": "Subscription ID is required.",
        }

    if not new_plan_id:
        return {
            "success": False,
            "message": "New plan ID is required.",
        }

    try:

        # ------------------------------------------
        # 1. Fetch the subscription
        # ------------------------------------------

        sub_response = (
            admin_supabase
            .table("hospital_subscriptions")
            .select(
                "hospital_subscription_id,"
                "plan_id,"
                "billing_cycle,"
                "end_date,"
                "status"
            )
            .eq(
                "hospital_subscription_id",
                hospital_subscription_id,
            )
            .single()
            .execute()
        )

        subscription = sub_response.data

        if not subscription:
            return {
                "success": False,
                "message": "Subscription not found.",
            }

        current_plan_id = subscription.get("plan_id")
        billing_cycle   = subscription.get("billing_cycle")
        end_date_str    = subscription.get("end_date")

        if current_plan_id == new_plan_id:
            return {
                "success": False,
                "message": "You are already on this plan.",
            }

        if not end_date_str:
            return {
                "success": False,
                "message": "Subscription has no end date.",
            }

        if billing_cycle not in ("Monthly", "Yearly"):
            return {
                "success": False,
                "message": (
                    f"Unsupported billing cycle: "
                    f"{billing_cycle}"
                ),
            }

        # ------------------------------------------
        # 2. Compute days left in the cycle
        # ------------------------------------------

        end_date = date.fromisoformat(end_date_str)
        today    = date.today()

        days_left = (end_date - today).days

        if days_left <= 0:
            return {
                "success": False,
                "message": (
                    "The current billing period has already "
                    "ended. Renew first, then change plan."
                ),
            }

        cycle_days = 30 if billing_cycle == "Monthly" else 365

        # ------------------------------------------
        # 3. Fetch both plans
        # ------------------------------------------

        plans_response = (
            admin_supabase
            .table("subscription_plans")
            .select(
                "plan_id,"
                "plan_name,"
                "price_monthly,"
                "price_yearly"
            )
            .in_(
                "plan_id",
                [current_plan_id, new_plan_id],
            )
            .execute()
        )

        plans = plans_response.data or []

        current_plan = next(
            (p for p in plans if p["plan_id"] == current_plan_id),
            None,
        )
        new_plan = next(
            (p for p in plans if p["plan_id"] == new_plan_id),
            None,
        )

        if not current_plan or not new_plan:
            return {
                "success": False,
                "message": "One of the plans could not be found.",
            }

        # ------------------------------------------
        # 4. Pick the correct price for the cycle
        # ------------------------------------------

        if billing_cycle == "Yearly":
            old_price = float(current_plan.get("price_yearly") or 0)
            new_price = float(new_plan.get("price_yearly") or 0)
        else:
            old_price = float(current_plan.get("price_monthly") or 0)
            new_price = float(new_plan.get("price_monthly") or 0)

        # ------------------------------------------
        # 5. Guard against downgrades / same plan
        # ------------------------------------------

        if new_price <= old_price:
            return {
                "success": False,
                "message": (
                    "The new plan is not more expensive than "
                    "the current plan. Proration only applies "
                    "to upgrades."
                ),
            }

        # ------------------------------------------
        # 6. Compute the prorated amount
        # ------------------------------------------

        old_per_day = old_price / cycle_days
        new_per_day = new_price / cycle_days

        prorated = (new_per_day - old_per_day) * days_left

        # Never charge below 1 peso — PayMongo minimums
        prorated = round(prorated, 2)

        if prorated < 1.00:
            prorated = 1.00

        return {
            "success": True,
            "amount": prorated,
            "currency": "PHP",
            "days_left": days_left,
            "cycle_days": cycle_days,
            "old_plan_name": current_plan.get("plan_name"),
            "new_plan_name": new_plan.get("plan_name"),
            "old_price": old_price,
            "new_price": new_price,
            "billing_cycle": billing_cycle,
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e),
        }

def create_upgrade_checkout_session(
    hospital_subscription_id,
    new_plan_id,
):
    """
    Creates a PayMongo checkout session for a plan upgrade.

    Unlike renewal, this flow:
      - Compares old plan vs new plan
      - Computes the prorated difference for the remaining days
      - Charges only the difference

    The subscription plan is NOT changed here. It's changed
    by the webhook after payment succeeds (payment_type='upgrade').

    Returns:
        {
            "success": True,
            "checkout_url": str,
            "payment_id": uuid,
            "amount": float,
            "currency": "PHP",
            "new_plan_id": int,
            "old_plan_id": int,
        }
        or
        {
            "success": False,
            "message": str,
        }
    """

    try:

        # ------------------------------------------
        # 1. Compute the prorated amount
        # ------------------------------------------

        proration = compute_prorated_amount(
            hospital_subscription_id,
            new_plan_id,
        )

        if not proration.get("success"):
            return {
                "success": False,
                "message": proration.get("message", "Proration failed."),
            }

        prorated_amount = float(proration["amount"])
        currency = proration.get("currency", "PHP")
        billing_cycle = proration.get("billing_cycle")
        old_plan_name = proration.get("old_plan_name")
        new_plan_name = proration.get("new_plan_name")

        # ------------------------------------------
        # 2. Fetch the subscription for hospital_id
        # ------------------------------------------

        sub_response = (
            admin_supabase
            .table("hospital_subscriptions")
            .select("hospital_id, plan_id")
            .eq(
                "hospital_subscription_id",
                hospital_subscription_id,
            )
            .single()
            .execute()
        )

        subscription = sub_response.data

        if not subscription:
            return {
                "success": False,
                "message": "Subscription not found.",
            }

        hospital_id = subscription["hospital_id"]
        old_plan_id = subscription["plan_id"]

        # ------------------------------------------
        # 3. Insert a pending upgrade payment
        # ------------------------------------------

        amount_cents = int(round(prorated_amount * 100))

        payment_row = (
            admin_supabase
            .table("payments")
            .insert({
                "application_id":           None,
                "hospital_id":              hospital_id,
                "hospital_subscription_id": hospital_subscription_id,
                "plan_id":                  new_plan_id,
                "provider":                 "paymongo",
                "amount":                   prorated_amount,
                "currency":                 currency,
                "billing_cycle":            billing_cycle,
                "payment_type":             "upgrade",
                "status":                   "pending",
            })
            .execute()
        )

        if not payment_row.data:
            return {
                "success": False,
                "message": "Could not create payment record.",
            }

        payment_id = payment_row.data[0]["payment_id"]

        # ------------------------------------------
        # 4. Create PayMongo checkout session
        # ------------------------------------------

        payload = {
            "data": {
                "attributes": {
                    "line_items": [{
                        "currency": currency,
                        "amount":   amount_cents,
                        "name":     f"Upgrade to {new_plan_name}",
                        "quantity": 1,
                        "description": (
                            f"Prorated upgrade from {old_plan_name} "
                            f"to {new_plan_name} ({billing_cycle})"
                        ),
                    }],
                    "payment_method_types": [
                        "card",
                        "gcash",
                        "paymaya",
                    ],
                    "success_url": PAYMENT_SUCCESS_URL,
                    "cancel_url":  PAYMENT_FAILED_URL,
                    "description": (
                        f"LungSight upgrade — {old_plan_name} → "
                        f"{new_plan_name}"
                    ),
                    "send_email_receipt": True,
                    "metadata": {
                        "hospital_subscription_id": hospital_subscription_id,
                        "payment_id":               payment_id,
                        "payment_type":             "upgrade",
                        "new_plan_id":              str(new_plan_id),
                        "old_plan_id":              str(old_plan_id),
                    },
                }
            }
        }

        auth = (PAYMONGO_SECRET_KEY, "")

        pm_response = requests.post(
            f"{PAYMONGO_API_BASE}/checkout_sessions",
            json=payload,
            auth=auth,
            timeout=20,
        )

        pm_response.raise_for_status()

        pm_data = pm_response.json()["data"]

        checkout_url = pm_data["attributes"]["checkout_url"]
        checkout_id  = pm_data["id"]

        # ------------------------------------------
        # 5. Save the provider reference
        # ------------------------------------------

        admin_supabase.table("payments").update({
            "provider_reference": checkout_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("payment_id", payment_id).execute()

        # ------------------------------------------
        # 6. Return success
        # ------------------------------------------

        return {
            "success":          True,
            "checkout_url":     checkout_url,
            "payment_id":       payment_id,
            "amount":           prorated_amount,
            "currency":         currency,
            "new_plan_id":      new_plan_id,
            "old_plan_id":      old_plan_id,
            "billing_cycle":    billing_cycle,
            "old_plan_name":    old_plan_name,
            "new_plan_name":    new_plan_name,
        }

    except requests.HTTPError as http_err:

        return {
            "success": False,
            "message": f"PayMongo error: {http_err.response.text}",
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e),
        }


def get_upgrade_status(payment_id):
    """
    Returns the current status of an upgrade payment row.

    Same shape as get_renewal_status() — the "Refresh Status"
    button on the checkout screen uses whichever is appropriate.
    """

    return get_renewal_status(payment_id)