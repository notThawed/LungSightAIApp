from backend.supabase_client import supabase, admin_supabase
from datetime import date, datetime, timedelta, timezone

GRACE_PERIOD_DAYS = 7
# ==========================================
# GET ALL SUBSCRIPTION PLANS
# ==========================================

def get_all_subscription_plans():

    try:

        response = (
            admin_supabase
            .table("subscription_plans")
            .select("*")
            .order("plan_id")
            .execute()
        )

        return response.data or []

    except Exception as e:

        print(
            f"Failed to fetch subscription plans: {e}"
        )

        return []


# ==========================================
# GET ACTIVE SUBSCRIPTION PLANS
# PUBLIC USE
# ==========================================

def get_active_subscription_plans():

    try:

        response = (
            supabase
            .table("subscription_plans")
            .select("*")
            .eq("is_active", True)
            .order("plan_id")
            .execute()
        )

        return response.data or []

    except Exception as e:

        print(
            f"Failed to fetch active subscription plans: {e}"
        )

        return []


# ==========================================
# CREATE SUBSCRIPTION
# ==========================================

def create_subscription(
    plan_name,
    description,
    price_monthly,
    price_yearly,
    max_users,
    max_xrays_per_month,
    max_patients,
):

    try:

        plan_data = {
            "plan_name": plan_name,
            "description": description,
            "price_monthly": price_monthly,
            "price_yearly": price_yearly,
            "max_users": max_users,
            "max_xrays_per_month": max_xrays_per_month,
            "max_patients": max_patients,
            "is_active": True
        }

        response = (
            admin_supabase
            .table("subscription_plans")
            .insert(plan_data)
            .execute()
        )

        return {
            "success": True,
            "message": "Subscription plan created successfully.",
            "data": response.data
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }


# ==========================================
# EDIT SUBSCRIPTION
# ==========================================

def edit_subscription(
    plan_id,
    plan_name,
    description,
    price_monthly,
    price_yearly,
    max_users,
    max_xrays_per_month,
    max_patients,
):

    try:

        update_data = {
            "plan_name": plan_name,
            "description": description,
            "price_monthly": price_monthly,
            "price_yearly": price_yearly,
            "max_users": max_users,
            "max_xrays_per_month": max_xrays_per_month,
            "max_patients": max_patients
        }

        response = (
            admin_supabase
            .table("subscription_plans")
            .update(update_data)
            .eq("plan_id", plan_id)
            .execute()
        )

        return {
            "success": True,
            "message": "Subscription plan updated successfully.",
            "data": response.data
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }


# ==========================================
# DEACTIVATE SUBSCRIPTION
# ==========================================

def deactivate_subscription(plan_id):

    try:

        response = (
            admin_supabase
            .table("subscription_plans")
            .update({
                "is_active": False
            })
            .eq("plan_id", plan_id)
            .execute()
        )

        return {
            "success": True,
            "message": "Subscription plan deactivated successfully.",
            "data": response.data
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }


# ==========================================
# ACTIVATE SUBSCRIPTION
# ==========================================

def activate_subscription(plan_id):

    try:

        response = (
            admin_supabase
            .table("subscription_plans")
            .update({
                "is_active": True
            })
            .eq("plan_id", plan_id)
            .execute()
        )

        return {
            "success": True,
            "message": "Subscription plan activated successfully.",
            "data": response.data
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }

def delete_subscription(plan_id):

    try:

        response = (
            admin_supabase
            .table("subscription_plans")
            .delete()
            .eq("plan_id", plan_id)
            .execute()
        )

        return {
            "success": True,
            "message": "Subscription plan deleted successfully.",
            "data": response.data
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }

def get_inactive_subscription_plans():

    response = (
        admin_supabase
        .table("subscription_plans")
        .select("*")
        .eq("is_active", False)
        .order("plan_id")
        .execute()
    )

    return response.data or []



def create_hospital_subscription(
    hospital_id,
    plan_id,
    billing_cycle,
    application_id=None
):

    try:

        # ----------------------------------------------------
        # Validate Hospital
        # ----------------------------------------------------

        if not hospital_id:

            return {
                "success": False,
                "message": "Hospital ID is required."
            }

        # ----------------------------------------------------
        # Validate Plan
        # ----------------------------------------------------

        if not plan_id:

            return {
                "success": False,
                "message": "Subscription plan is required."
            }

        # ----------------------------------------------------
        # Validate Billing Cycle
        # ----------------------------------------------------

        if billing_cycle not in [
            "Monthly",
            "Yearly"
        ]:

            return {
                "success": False,
                "message": "Invalid billing cycle."
            }

        if not application_id:
            return {
                "success": False,
                "message": "Application ID is required."
            }

        # ----------------------------------------------------
        # Check if subscription already exists
        # ----------------------------------------------------

        existing_response = (
            admin_supabase
            .table("hospital_subscriptions")
            .select("hospital_subscription_id")
            .eq(
                "hospital_id",
                hospital_id
            )
            .execute()
        )

        if existing_response.data:

            return {
                "success": False,
                "message": (
                    "A subscription already exists "
                    "for this hospital."
                )
            }

        # ----------------------------------------------------
        # Create Subscription
        # ----------------------------------------------------

        subscription_data = {

            "hospital_id":
                hospital_id,

            "plan_id":
                plan_id,

            "billing_cycle":
                billing_cycle,

            "application_id":
                application_id,

            "status":
                "Pending Setup"
        }

        response = (
            admin_supabase
            .table("hospital_subscriptions")
            .insert(subscription_data)
            .execute()
        )

        # ----------------------------------------------------
        # Check result
        # ----------------------------------------------------

        if not response.data:

            return {
                "success": False,
                "message": (
                    "Failed to create hospital subscription."
                )
            }

        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

        return {
            "success": True,
            "message": (
                "Hospital subscription created "
                "successfully."
            ),
            "subscription": response.data[0]
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }


def get_hospital_subscription_details(hospital_id):
    """
    Fetches the hospital's subscription joined with its plan.

    Returns a dict:
        {
            "subscription_id": uuid,
            "plan_id": int,
            "plan_name": str,
            "description": str | None,
            "price_monthly": float | None,
            "price_yearly": float | None,
            "max_users": int | None,
            "max_patients": int | None,
            "max_xrays_per_month": int | None,
            "billing_cycle": str,
            "status": str,
            "start_date": date | None,
            "end_date": date | None,
        }

    Or None if no subscription exists for the hospital.
    """

    if not hospital_id:

        return None

    try:

        response = (
            admin_supabase
            .table("hospital_subscriptions")
            .select(
                """
                hospital_subscription_id,
                plan_id,
                billing_cycle,
                status,
                start_date,
                end_date,
                subscription_plans (
                    plan_id,
                    plan_name,
                    description,
                    price_monthly,
                    price_yearly,
                    max_users,
                    max_patients,
                    max_xrays_per_month
                )
                """
            )
            .eq(
                "hospital_id",
                hospital_id
            )
            .single()
            .execute()
        )

        row = response.data

        if not row:

            return None

        plan = row.get("subscription_plans") or {}

        return {

            "subscription_id":
                row.get("hospital_subscription_id"),

            "plan_id":
                row.get("plan_id"),

            "plan_name":
                plan.get("plan_name"),

            "description":
                plan.get("description"),

            "price_monthly":
                plan.get("price_monthly"),

            "price_yearly":
                plan.get("price_yearly"),

            "max_users":
                plan.get("max_users"),

            "max_patients":
                plan.get("max_patients"),

            "max_xrays_per_month":
                plan.get("max_xrays_per_month"),

            "billing_cycle":
                row.get("billing_cycle"),

            "status":
                row.get("status"),

            "start_date":
                row.get("start_date"),

            "end_date":
                row.get("end_date"),
        }

    except Exception as e:

        print(
            f"Error getting subscription details: {e}"
        )

        return None

def get_subscription_state(hospital_id):
    """
    Returns the current subscription state for a hospital.

    Possible return values:
      "none"           - no subscription row found
      "setup_pending"  - hospital hasn't finished the wizard yet
      "active"         - within end_date
      "grace"          - past end_date, within grace window
      "expired"        - past grace window
      "cancelled"      - manually cancelled (future use)
    """

    if not hospital_id:

        return "none"

    try:

        response = (
            admin_supabase
            .table("hospital_subscriptions")
            .select("status, start_date, end_date")
            .eq("hospital_id", hospital_id)
            .single()
            .execute()
        )

        subscription = response.data

        if not subscription:

            return "none"

        status = subscription.get("status")

        # ------------------------------------------------
        # Non-date-based statuses pass through as-is
        # ------------------------------------------------

        if status == "Pending Setup":

            return "setup_pending"

        if status == "Cancelled":

            return "cancelled"

        # ------------------------------------------------
        # Date-based states
        # ------------------------------------------------

        end_date_str = subscription.get("end_date")

        if not end_date_str:

            # No end_date means we can't compute grace/expired.
            # Treat as active (defensive).
            return "active"

        end_date = date.fromisoformat(end_date_str)

        today = date.today()

        if today <= end_date:

            return "active"

        grace_end = end_date + timedelta(days=GRACE_PERIOD_DAYS)

        if today <= grace_end:

            return "grace"

        return "expired"

    except Exception as e:

        print(f"Error getting subscription state: {e}")

        return "none"

def get_days_until_expiry(hospital_id):
    """
    Returns the number of days until the subscription's end_date.

    Possible return values:
      positive int  - days remaining before end_date
      0             - end_date is today (still active, expires tomorrow)
      negative int  - days past end_date (in grace or expired)
      None          - no subscription found, or no end_date set
    """

    if not hospital_id:

        return None

    try:

        response = (
            admin_supabase
            .table("hospital_subscriptions")
            .select("end_date")
            .eq("hospital_id", hospital_id)
            .single()
            .execute()
        )

        subscription = response.data

        if not subscription:

            return None

        end_date_str = subscription.get("end_date")

        if not end_date_str:

            return None

        end_date = date.fromisoformat(end_date_str)

        today = date.today()

        return (end_date - today).days

    except Exception as e:

        print(f"Error getting days until expiry: {e}")

        return None

def get_subscription_context(hospital_id):
    """
    Bundles everything the subscription gate needs into one dict.

    Returns:
        {
            "hospital_id":   uuid,
            "state":         "active" | "grace" | "expired" |
                             "setup_pending" | "cancelled" | "none",
            "days_left":     int | None,
            "hospital_name": str | None,
            "plan_name":     str | None,
            "end_date":      str | None,
        }

    Never returns None. Falls back to a safe dict on error.
    """

    context = {
        "hospital_id":     hospital_id,
        "state":           "none",
        "days_left":       None,
        "hospital_name":   None,
        "plan_name":       None,
        "end_date":        None,
        "subscription_id": None,
        "billing_cycle":   None,
        "amount":          None,
    }

    if not hospital_id:

        return context

    try:

        # ----------------------------------------------------
        # State + days_left (reuse Phase 1 + 2 helpers)
        # ----------------------------------------------------

        context["state"] = get_subscription_state(hospital_id)

        context["days_left"] = get_days_until_expiry(hospital_id)

        # ----------------------------------------------------
        # Hospital name
        # ----------------------------------------------------

        hospital_response = (
            admin_supabase
            .table("hospitals")
            .select("hospital_name")
            .eq("hospital_id", hospital_id)
            .single()
            .execute()
        )

        if hospital_response.data:

            context["hospital_name"] = (
                hospital_response.data.get("hospital_name")
            )

        # ----------------------------------------------------
        # Plan name + end_date
        # ----------------------------------------------------

        details = get_hospital_subscription_details(hospital_id)

        if details:

            context["plan_name"] = details.get("plan_name")

            context["subscription_id"] = details.get("subscription_id")

            context["billing_cycle"] = details.get("billing_cycle")

            end_date = details.get("end_date")

            if end_date:

                context["end_date"] = str(end_date)

            # Compute the amount based on billing cycle
            billing_cycle = details.get("billing_cycle")

            if billing_cycle == "Yearly":

                context["amount"] = float(
                    details.get("price_yearly") or 0
                )

            else:

                context["amount"] = float(
                    details.get("price_monthly") or 0
                )

        return context

    except Exception as e:

        print(f"Error getting subscription context: {e}")

        return context

CYCLE_DAYS = {
    "Monthly": 30,
    "Yearly":  365,
}


def extend_subscription(hospital_subscription_id):
    """
    Extends a hospital subscription by one billing cycle
    after a successful renewal payment.

    Rules:
        - If end_date is in the future (or today)  -> end_date + cycle_days
        - If end_date is in the past               -> today + cycle_days
        - If end_date is null                      -> today + cycle_days

    Also sets:
        - status = 'Active'
        - last_renewed_at = now()
    """

    try:

        if not hospital_subscription_id:

            return {
                "success": False,
                "message": "Subscription ID is required."
            }

        # ------------------------------------------------
        # 1. Fetch the subscription
        # ------------------------------------------------

        sub_response = (
            admin_supabase
            .table("hospital_subscriptions")
            .select(
                "hospital_subscription_id,"
                "hospital_id,"
                "billing_cycle,"
                "end_date,"
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

        # ------------------------------------------------
        # 2. Determine the billing cycle
        # ------------------------------------------------

        billing_cycle = subscription.get("billing_cycle")

        cycle_days = CYCLE_DAYS.get(billing_cycle)

        if not cycle_days:

            return {
                "success": False,
                "message": (
                    f"Unknown billing cycle: {billing_cycle}"
                )
            }

        # ------------------------------------------------
        # 3. Compute the new end_date
        # ------------------------------------------------

        today = date.today()

        old_end_date_str = subscription.get("end_date")

        if old_end_date_str:

            old_end_date = date.fromisoformat(old_end_date_str)

        else:

            old_end_date = None

        if old_end_date and old_end_date >= today:

            base_date = old_end_date

        else:

            base_date = today

        new_end_date = base_date + timedelta(days=cycle_days)

        # ------------------------------------------------
        # 4. Update the subscription
        # ------------------------------------------------

        now_iso = datetime.now(timezone.utc).isoformat()

        update_response = (
            admin_supabase
            .table("hospital_subscriptions")
            .update({
                "end_date":        new_end_date.isoformat(),
                "status":          "Active",
                "last_renewed_at": now_iso,
                "updated_at":      now_iso,
            })
            .eq(
                "hospital_subscription_id",
                hospital_subscription_id
            )
            .execute()
        )

        if not update_response.data:

            return {
                "success": False,
                "message": "Failed to update subscription."
            }

        return {
            "success": True,
            "old_end_date": (
                old_end_date.isoformat() if old_end_date else None
            ),
            "new_end_date": new_end_date.isoformat(),
            "subscription": update_response.data[0],
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e),
        }