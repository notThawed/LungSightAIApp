from backend.supabase_client import supabase, admin_supabase
from backend import audit
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

            audit.record_event(
                "subscription.created",
                "failure",
                target_hospital_id=hospital_id,
                metadata={"plan_id": plan_id, "reason": "insert_failed"},
            )

            return {
                "success": False,
                "message": (
                    "Failed to create hospital subscription."
                )
            }

        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

        audit.record_event(
            "subscription.created",
            target_id=response.data[0].get("hospital_subscription_id"),
            metadata={
                "plan_id": plan_id,
                "billing_cycle": billing_cycle,
                "status": "Pending Setup",
            },
        )

        return {
            "success": True,
            "message": (
                "Hospital subscription created "
                "successfully."
            ),
            "subscription": response.data[0]
        }

    except Exception as e:

        audit.record_event(
            "subscription.created",
            "failure",
            target_hospital_id=hospital_id,
            metadata={"plan_id": plan_id, "error_class": audit.error_class(e)},
        )

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



def _ph_today():
    """Philippine calendar date, independent of the server timezone."""
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Asia/Manila")).date()


def _subscription_state_from_row(subscription, today=None):
    """Pure state calculation; safe to test without a database connection."""
    if not subscription:
        return "none"
    status = subscription.get("status")
    if status == "Pending Setup":
        return "setup_pending"
    if status == "Cancelled":
        return "cancelled"
    # Only an explicitly Active subscription may enter the paid/grace states.
    if status != "Active":
        return "inactive"
    raw_end = subscription.get("end_date")
    if not raw_end:
        return "inactive"
    try:
        end = date.fromisoformat(str(raw_end)[:10])
    except (TypeError, ValueError):
        return "inactive"
    today = today or _ph_today()
    if today <= end:
        return "active"
    if today <= end + timedelta(days=GRACE_PERIOD_DAYS):
        return "grace"
    return "expired"


def get_subscription_state(hospital_id):
    """Return active/grace/expired only for an explicitly Active subscription."""
    if not hospital_id:
        return "none"
    try:
        response = (
            admin_supabase.table("hospital_subscriptions")
            .select("status, start_date, end_date")
            .eq("hospital_id", hospital_id)
            .single()
            .execute()
        )
        return _subscription_state_from_row(response.data)
    except Exception as e:
        print(f"Error getting subscription state: {e}")
        return "none"


def get_days_until_expiry(hospital_id):
    """Days until paid expiry, or remaining grace days (0 on last grace day)."""
    if not hospital_id:
        return None
    try:
        response = (
            admin_supabase.table("hospital_subscriptions")
            .select("status, end_date")
            .eq("hospital_id", hospital_id)
            .single()
            .execute()
        )
        subscription = response.data
        if not subscription or subscription.get("status") != "Active":
            return None
        raw_end = subscription.get("end_date")
        if not raw_end:
            return None
        end = date.fromisoformat(str(raw_end)[:10])
        today = _ph_today()
        days_passed = (today - end).days
        if days_passed > 0:
            return max(0, GRACE_PERIOD_DAYS - days_passed)
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

def schedule_downgrade(hospital_subscription_id, new_plan_id):
    """Schedule a lower-priced plan; never grant a new paid period."""
    if not hospital_subscription_id or not new_plan_id:
        return {"success": False, "message": "Subscription and target plan are required."}
    try:
        result = (admin_supabase.table("hospital_subscriptions")
                  .select("hospital_subscription_id,plan_id,status,end_date,cancel_at_period_end")
                  .eq("hospital_subscription_id", hospital_subscription_id)
                  .single().execute())
        sub = result.data
        if not sub or sub.get("status") != "Active" or not sub.get("end_date"):
            return {"success": False, "message": "Only active paid subscriptions may schedule a downgrade."}
        if sub.get("cancel_at_period_end"):
            return {"success": False, "message": "Undo the scheduled cancellation first."}
        today = datetime.now(timezone(timedelta(hours=8))).date()
        if today > date.fromisoformat(str(sub["end_date"])[:10]):
            return {"success": False, "message": "Renew the expired subscription before scheduling a downgrade."}
        plans = (admin_supabase.table("subscription_plans")
                 .select("plan_id,is_active,price_monthly,price_yearly")
                 .in_("plan_id", [sub["plan_id"], new_plan_id]).execute()).data or []
        by_id = {str(p["plan_id"]): p for p in plans}
        current, target = by_id.get(str(sub["plan_id"])), by_id.get(str(new_plan_id))
        if not current or not target or not target.get("is_active"):
            return {"success": False, "message": "Target plan is unavailable."}
        # Price is a validation aid only; plan changes must be paid before activation.
        cycle = (admin_supabase.table("hospital_subscriptions")
                 .select("billing_cycle").eq("hospital_subscription_id", hospital_subscription_id)
                 .single().execute()).data.get("billing_cycle")
        price_field = "price_yearly" if cycle == "Yearly" else "price_monthly"
        if cycle not in ("Monthly", "Yearly") or float(target[price_field]) >= float(current[price_field]):
            return {"success": False, "message": "Target must be a lower-priced plan in the same billing cycle."}
        now = datetime.now(timezone.utc).isoformat()
        updated = (admin_supabase.table("hospital_subscriptions")
                   .update({"pending_plan_id": new_plan_id, "updated_at": now})
                   .eq("hospital_subscription_id", hospital_subscription_id)
                   .eq("status", "Active").eq("plan_id", sub["plan_id"])
                   .eq("cancel_at_period_end", False).execute())
        if not updated.data:
            return {"success": False, "message": "Subscription changed; refresh and try again."}
        audit.record_event("subscription.downgrade_scheduled", target_id=hospital_subscription_id,
                           metadata={"pending_plan_id": new_plan_id})
        return {"success": True, "message": "Downgrade scheduled; activation requires a verified renewal."}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


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

            audit.record_event(
                "subscription.downgrade_undone",
                "failure",
                target_id=hospital_subscription_id,
                metadata={"reason": "not_updated"},
            )

            return {
                "success": False,
                "message": "Could not undo scheduled downgrade.",
            }

        audit.record_event(
            "subscription.downgrade_undone",
            target_id=hospital_subscription_id,
        )

        return {
            "success": True,
            "message": "Scheduled downgrade cancelled.",
        }

    except Exception as e:

        audit.record_event(
            "subscription.downgrade_undone",
            "failure",
            target_id=hospital_subscription_id,
            metadata={"error_class": audit.error_class(e)},
        )

        return {
            "success": False,
            "message": str(e),
        }

def cancel_subscription(hospital_subscription_id):
    """Schedule cancellation; preserve paid access through end_date."""
    if not hospital_subscription_id:
        return {"success": False, "message": "Subscription ID required."}
    try:
        row = (admin_supabase.table("hospital_subscriptions")
               .select("status,end_date,cancel_at_period_end")
               .eq("hospital_subscription_id", hospital_subscription_id)
               .single().execute()).data
        if not row or row.get("status") != "Active" or not row.get("end_date"):
            return {"success": False, "message": "Only active subscriptions can schedule cancellation."}
        if row.get("cancel_at_period_end"):
            return {"success": True, "message": "Cancellation is already scheduled."}
        if datetime.now(timezone(timedelta(hours=8))).date() > date.fromisoformat(str(row["end_date"])[:10]):
            return {"success": False, "message": "Paid period has already ended."}
        now = datetime.now(timezone.utc).isoformat()
        result = (admin_supabase.table("hospital_subscriptions")
                  .update({"cancel_at_period_end": True, "cancelled_at": now,
                           "pending_plan_id": None, "updated_at": now})
                  .eq("hospital_subscription_id", hospital_subscription_id)
                  .eq("status", "Active").eq("cancel_at_period_end", False).execute())
        if not result.data:
            return {"success": False, "message": "Cancellation could not be scheduled."}
        audit.record_event("subscription.cancel_requested", target_id=hospital_subscription_id)
        return {"success": True, "message": "Cancellation scheduled for the end of the paid period."}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


def reactivate_subscription(hospital_subscription_id):
    """Undo a pending cancellation; never reactivate an expired subscription for free."""
    if not hospital_subscription_id:
        return {"success": False, "message": "Subscription ID required."}
    try:
        row = (admin_supabase.table("hospital_subscriptions")
               .select("status,end_date,cancel_at_period_end")
               .eq("hospital_subscription_id", hospital_subscription_id)
               .single().execute()).data
        if not row or row.get("status") != "Active" or not row.get("cancel_at_period_end"):
            return {"success": False, "message": "No active scheduled cancellation to undo."}
        if not row.get("end_date") or datetime.now(timezone(timedelta(hours=8))).date() > date.fromisoformat(str(row["end_date"])[:10]):
            return {"success": False, "message": "Paid period ended; verified renewal is required."}
        now = datetime.now(timezone.utc).isoformat()
        result = (admin_supabase.table("hospital_subscriptions")
                  .update({"cancel_at_period_end": False, "cancelled_at": None, "updated_at": now})
                  .eq("hospital_subscription_id", hospital_subscription_id)
                  .eq("status", "Active").eq("cancel_at_period_end", True).execute())
        if not result.data:
            return {"success": False, "message": "Cancellation could not be undone."}
        audit.record_event("subscription.reactivated", target_id=hospital_subscription_id)
        return {"success": True, "message": "Scheduled cancellation removed."}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


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
    """Apply cancellation after paid period; never activate unpaid downgrades."""
    if not hospital_id:
        return {"success": False, "action": "error", "message": "Hospital ID required."}
    try:
        row = get_hospital_subscription_row(hospital_id)
        if not row:
            return {"success": False, "action": "error", "message": "Subscription not found."}
        if row.get("status") != "Active" or not row.get("end_date"):
            return {"success": True, "action": "no_change", "message": "No active paid period."}
        end = date.fromisoformat(str(row["end_date"])[:10])
        today = datetime.now(timezone(timedelta(hours=8))).date()
        if today <= end:
            return {"success": True, "action": "no_change", "message": "Paid period has not ended."}
        if row.get("cancel_at_period_end"):
            now = datetime.now(timezone.utc).isoformat()
            response = (admin_supabase.table("hospital_subscriptions")
                        .update({"status": "Cancelled", "cancel_at_period_end": False,
                                 "updated_at": now})
                        .eq("hospital_subscription_id", row["hospital_subscription_id"])
                        .eq("status", "Active").eq("end_date", row["end_date"])
                        .eq("cancel_at_period_end", True).execute())
            if not response.data:
                return {"success": False, "action": "error", "message": "Cancellation not applied; refresh."}
            audit.record_event("subscription.cancelled", target_id=row["hospital_subscription_id"],
                               idempotency_key=f"subscription.cancelled:{row['hospital_subscription_id']}:{row['end_date']}", system=True)
            return {"success": True, "action": "cancelled", "message": "Cancelled after paid period."}
        if row.get("pending_plan_id"):
            return {"success": True, "action": "awaiting_payment",
                    "message": "Downgrade is scheduled but requires verified renewal payment. No new period granted."}
        return {"success": True, "action": "no_change", "message": "No scheduled change."}
    except Exception as exc:
        return {"success": False, "action": "error", "message": str(exc)}

