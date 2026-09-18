import os
import requests

from datetime import datetime, timezone
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