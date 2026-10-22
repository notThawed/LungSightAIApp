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
                subscription_plans!hospital_subscriptions_plan_fk (
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
    Returns the number of days remaining.
    During grace period, returns 0 to 7 (days left).
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

        # 1. Force the DB string into a pure date object (ignoring time)
        end_date = datetime.strptime(str(end_date_str)[:10], "%Y-%m-%d").date()
        
        # 2. Force today into a pure date object (ignoring time)
        today = date.today()

        # 3. Calculate days passed
        days_passed = (today - end_date).days

        # 4. If we are past expiration, calculate days left in grace period
        if days_passed > 0:
            days_left = GRACE_PERIOD_DAYS - days_passed
            return max(0, days_left) # Clamp to 0 if fully expired
            
        # 5. If we are before expiration, return days remaining
        return -days_passed

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

def get_hospital_subscription_row(hospital_id):
    """
    Return the raw hospital_subscriptions row for a hospital,
    including the scheduled-change / cancellation columns.

    Returns:
        dict | None
    """

    if not hospital_id:
        return None

    try:

        response = (
            admin_supabase
            .table("hospital_subscriptions")
            .select(
                "hospital_subscription_id,"
                "hospital_id,"
                "plan_id,"
                "billing_cycle,"
                "status,"
                "start_date,"
                "end_date,"
                "pending_plan_id,"
                "cancel_at_period_end,"
                "cancelled_at,"
                "previous_plan_id,"
                "last_changed_at,"
                "last_renewed_at,"
                "created_at,"
                "updated_at"
            )
            .eq("hospital_id", hospital_id)
            .limit(1)
            .execute()
        )

        rows = response.data or []

        if not rows:
            return None

        return rows[0]

    except Exception as e:

        print(
            f"Error getting hospital subscription row: {e}"
        )

        return None

def schedule_downgrade(
    hospital_subscription_id,
    new_plan_id,
):
    """
    Schedule a plan downgrade for the next billing cycle.

    Does NOT touch the current plan_id — the plan only
    changes when apply_scheduled_changes() runs after
    end_date.

    Returns:
        { "success": bool, "message": str }
    """

    if not hospital_subscription_id:

        return {
            "success": False,
            "message": "Subscription ID is required.",
        }

    if not new_plan_id:

        return {
            "success": False,
            "message": "Target plan ID is required.",
        }

    try:

        now_iso = datetime.now(timezone.utc).isoformat()

        response = (
            admin_supabase
            .table("hospital_subscriptions")
            .update({
                "pending_plan_id": new_plan_id,
                "updated_at": now_iso,
            })
            .eq(
                "hospital_subscription_id",
                hospital_subscription_id,
            )
            .execute()
        )

        if not response.data:

            return {
                "success": False,
                "message": "Could not schedule downgrade.",
            }

        return {
            "success": True,
            "message": "Downgrade scheduled for next cycle.",
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e),
        }

def undo_scheduled_downgrade(
    hospital_subscription_id,
):
    """
    Cancel a scheduled downgrade.

    Returns:
        { "success": bool, "message": str }
    """

    if not hospital_subscription_id:

        return {
            "success": False,
            "message": "Subscription ID is required.",
        }

    try:

        now_iso = datetime.now(timezone.utc).isoformat()

        response = (
            admin_supabase
            .table("hospital_subscriptions")
            .update({
                "pending_plan_id": None,
                "updated_at": now_iso,
            })
            .eq(
                "hospital_subscription_id",
                hospital_subscription_id,
            )
            .execute()
        )

        if not response.data:

            return {
                "success": False,
                "message": "Could not undo scheduled downgrade.",
            }

        return {
            "success": True,
            "message": "Scheduled downgrade cancelled.",
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e),
        }

def cancel_subscription(
    hospital_subscription_id,
):
    """
    Schedule a cancellation for the end of the current
    billing period.

    Access continues until end_date. Use
    reactivate_subscription() to undo.

    Returns:
        { "success": bool, "message": str }
    """

    if not hospital_subscription_id:

        return {
            "success": False,
            "message": "Subscription ID is required.",
        }

    try:

        now_iso = datetime.now(timezone.utc).isoformat()

        response = (
            admin_supabase
            .table("hospital_subscriptions")
            .update({
                "cancel_at_period_end": True,
                "cancelled_at": now_iso,
                "updated_at": now_iso,
            })
            .eq(
                "hospital_subscription_id",
                hospital_subscription_id,
            )
            .execute()
        )

        if not response.data:

            return {
                "success": False,
                "message": "Could not cancel subscription.",
            }

        return {
            "success": True,
            "message": (
                "Subscription will be cancelled at the end "
                "of the current billing period."
            ),
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e),
        }

def reactivate_subscription(
    hospital_subscription_id,
):
    """
    Undo a scheduled cancellation.

    Returns:
        { "success": bool, "message": str }
    """

    if not hospital_subscription_id:

        return {
            "success": False,
            "message": "Subscription ID is required.",
        }

    try:

        now_iso = datetime.now(timezone.utc).isoformat()

        response = (
            admin_supabase
            .table("hospital_subscriptions")
            .update({
                "cancel_at_period_end": False,
                "cancelled_at": None,
                "updated_at": now_iso,
            })
            .eq(
                "hospital_subscription_id",
                hospital_subscription_id,
            )
            .execute()
        )

        if not response.data:

            return {
                "success": False,
                "message": "Could not reactivate subscription.",
            }

        return {
            "success": True,
            "message": "Subscription reactivated.",
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e),
        }

def upgrade_subscription(
    hospital_subscription_id,
    new_plan_id,
):
    """
    Apply an immediate plan upgrade.

    Called from the webhook after a successful upgrade
    payment. Also used by apply_scheduled_changes() when
    it applies a pending upgrade (if any).

    What it does:
      - previous_plan_id  <- current plan_id
      - plan_id           <- new_plan_id
      - status            <- "Active"
      - last_changed_at   <- now
      - updated_at        <- now

    Note: end_date is NOT modified. The user keeps their
    current billing cycle end date.

    Returns:
        { "success": bool, "message": str, "subscription": dict }
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

        # ------------------------------------------------
        # 1. Fetch current subscription
        # ------------------------------------------------

        current = (
            admin_supabase
            .table("hospital_subscriptions")
            .select("plan_id, status")
            .eq(
                "hospital_subscription_id",
                hospital_subscription_id,
            )
            .single()
            .execute()
        )

        if not current.data:

            return {
                "success": False,
                "message": "Subscription not found.",
            }

        old_plan_id = current.data.get("plan_id")

        # ------------------------------------------------
        # 2. Apply the upgrade
        # ------------------------------------------------

        now_iso = datetime.now(timezone.utc).isoformat()

        response = (
            admin_supabase
            .table("hospital_subscriptions")
            .update({
                "previous_plan_id": old_plan_id,
                "plan_id": new_plan_id,
                "status": "Active",
                "last_changed_at": now_iso,
                "updated_at": now_iso,
            })
            .eq(
                "hospital_subscription_id",
                hospital_subscription_id,
            )
            .execute()
        )

        if not response.data:

            return {
                "success": False,
                "message": "Could not apply upgrade.",
            }

        return {
            "success": True,
            "message": "Plan upgraded successfully.",
            "subscription": response.data[0],
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e),
        }

def apply_scheduled_changes(hospital_id):
    """
    Apply any pending scheduled changes for a hospital.

    Called on page load (in subscription_settings.py).

    Handles three scenarios at end_date:

      1. cancel_at_period_end = TRUE
            -> status = "Cancelled"
            -> The gate picks this up next and blocks access.

      2. pending_plan_id is set (downgrade)
            -> plan_id = pending_plan_id
            -> pending_plan_id = NULL
            -> previous_plan_id = old plan_id
            -> status stays "Active" (no payment required)
            -> end_date extended by one cycle so the new plan
               immediately has a billing period

      3. Neither
            -> No change. Return "no_change".

    Returns:
        {
            "success": bool,
            "action":  "cancelled" | "downgraded" | "no_change" | "error",
            "message": str,
        }
    """

    if not hospital_id:

        return {
            "success": False,
            "action": "error",
            "message": "Hospital ID is required.",
        }

    try:

        # ------------------------------------------------
        # 1. Fetch the subscription row
        # ------------------------------------------------

        row = get_hospital_subscription_row(hospital_id)

        if not row:

            return {
                "success": False,
                "action": "error",
                "message": "Subscription not found.",
            }

        # ------------------------------------------------
        # 2. Not at end_date yet? Do nothing.
        # ------------------------------------------------

        end_date_str = row.get("end_date")

        if not end_date_str:

            return {
                "success": True,
                "action": "no_change",
                "message": "No end date set.",
            }

        end_date = date.fromisoformat(end_date_str)
        today = date.today()

        # Scheduled changes only apply AFTER the end_date
        # (not on the last day).
        if today <= end_date:

            return {
                "success": True,
                "action": "no_change",
                "message": "No scheduled change due yet.",
            }

        sub_id = row.get("hospital_subscription_id")

        # ------------------------------------------------
        # 3. Cancellation takes priority over downgrade
        # ------------------------------------------------

        if row.get("cancel_at_period_end"):

            response = (
                admin_supabase
                .table("hospital_subscriptions")
                .update({
                    "status": "Cancelled",
                    "cancel_at_period_end": False,
                    "updated_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                })
                .eq(
                    "hospital_subscription_id",
                    sub_id,
                )
                .execute()
            )

            if not response.data:

                return {
                    "success": False,
                    "action": "error",
                    "message": "Could not cancel subscription.",
                }

            return {
                "success": True,
                "action": "cancelled",
                "message": "Subscription cancelled at period end.",
            }

        # ------------------------------------------------
        # 4. Pending downgrade
        # ------------------------------------------------

        pending_plan_id = row.get("pending_plan_id")

        if pending_plan_id:

            old_plan_id = row.get("plan_id")
            billing_cycle = row.get("billing_cycle")
            cycle_days = CYCLE_DAYS.get(billing_cycle, 30)

            # Start the new plan fresh — extend end_date from
            # today by one cycle
            new_end_date = (
                today + timedelta(days=cycle_days)
            )

            now_iso = datetime.now(
                timezone.utc
            ).isoformat()

            response = (
                admin_supabase
                .table("hospital_subscriptions")
                .update({
                    "previous_plan_id": old_plan_id,
                    "plan_id": pending_plan_id,
                    "pending_plan_id": None,
                    "status": "Active",
                    "start_date": today.isoformat(),
                    "end_date": new_end_date.isoformat(),
                    "last_changed_at": now_iso,
                    "updated_at": now_iso,
                })
                .eq(
                    "hospital_subscription_id",
                    sub_id,
                )
                .execute()
            )

            if not response.data:

                return {
                    "success": False,
                    "action": "error",
                    "message": "Could not apply downgrade.",
                }

            return {
                "success": True,
                "action": "downgraded",
                "message": (
                    f"Downgraded to plan "
                    f"{pending_plan_id}."
                ),
            }

        # ------------------------------------------------
        # 5. Nothing scheduled
        # ------------------------------------------------

        return {
            "success": True,
            "action": "no_change",
            "message": "No scheduled change.",
        }

    except Exception as e:

        return {
            "success": False,
            "action": "error",
            "message": str(e),
        }