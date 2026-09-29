from datetime import datetime, timezone

from backend.supabase_client import admin_supabase


# ============================================================
# SUBSCRIPTION USAGE
# ============================================================
#
# This module is responsible for:
#
#   1. Getting the hospital's active subscription
#   2. Getting the hospital's current usage
#   3. Comparing usage against subscription limits
#   4. Checking whether an action is allowed
#
# Usage limits:
#
#   max_users
#   max_patients
#   max_xrays_per_month
#
# A NULL limit means UNLIMITED.
#
# This module does NOT create, update, or delete:
#
#   - users
#   - patients
#   - X-rays
#   - subscriptions
#
# Those operations remain in crud.py / subscription_utils.py.
# ============================================================


# ============================================================
# HELPER
# ============================================================

def _get_current_month_range():
    """
    Return the start and end timestamps for the
    current month in UTC.

    Returns:

        {
            "start": datetime,
            "end": datetime,
        }
    """

    now = datetime.now(timezone.utc)

    start = datetime(
        year=now.year,
        month=now.month,
        day=1,
        tzinfo=timezone.utc,
    )

    if now.month == 12:

        end = datetime(
            year=now.year + 1,
            month=1,
            day=1,
            tzinfo=timezone.utc,
        )

    else:

        end = datetime(
            year=now.year,
            month=now.month + 1,
            day=1,
            tzinfo=timezone.utc,
        )

    return {
        "start": start,
        "end": end,
    }


# ============================================================
# GET HOSPITAL SUBSCRIPTION
# ============================================================

def get_hospital_subscription(
    hospital_id,
):
    """
    Get the active subscription for a hospital.

    Returns the subscription together with the
    subscription plan information.

    Example:

        {
            "hospital_subscription_id": "...",
            "hospital_id": "...",
            "plan_id": 1,
            "billing_cycle": "Monthly",
            "start_date": "...",
            "end_date": "...",

            "subscription_plans": {
                "plan_id": 1,
                "plan_name": "Basic",
                "max_users": 5,
                "max_patients": 100,
                "max_xrays_per_month": 50
            }
        }

    Returns:
        dict | None
    """

    if not hospital_id:
        return None

    try:

        response = (
            admin_supabase
            .table("hospital_subscriptions")
            .select("""
                hospital_subscription_id,
                hospital_id,
                plan_id,
                billing_cycle,
                start_date,
                end_date,
                created_at,
                updated_at,

                subscription_plans (
                    plan_id,
                    plan_name,
                    description,
                    price_monthly,
                    price_yearly,
                    max_users,
                    max_patients,
                    max_xrays_per_month,
                    is_active
                )
            """)
            .eq(
                "hospital_id",
                hospital_id,
            )
            .order(
                "created_at",
                desc=True,
            )
            .limit(1)
            .execute()
        )

        rows = response.data or []

        if not rows:
            return None

        subscription = rows[0]

        # ----------------------------------------------------
        # Supabase may return the related plan as a list.
        # ----------------------------------------------------

        plan = subscription.get(
            "subscription_plans"
        )

        if isinstance(plan, list):

            plan = (
                plan[0]
                if plan
                else None
            )

        subscription["plan"] = plan

        return subscription

    except Exception as exc:

        print(
            "Failed to get hospital subscription: "
            f"{exc}"
        )

        return None


# ============================================================
# GET HOSPITAL USER COUNT
# ============================================================

def get_hospital_user_count(
    hospital_id,
):
    """
    Get the number of active users belonging
    to a hospital.

    Only active user_profiles are counted.

    Returns:
        int
    """

    if not hospital_id:
        return 0

    try:

        response = (
            admin_supabase
            .table("user_profiles")
            .select(
                "user_id",
                count="exact",
            )
            .eq(
                "hospital_id",
                hospital_id,
            )
            .eq(
                "is_active",
                True,
            )
            .execute()
        )

        return response.count or 0

    except Exception as exc:

        print(
            "Failed to get hospital user count: "
            f"{exc}"
        )

        return 0


# ============================================================
# GET HOSPITAL PATIENT COUNT
# ============================================================

def get_hospital_patient_count(
    hospital_id,
):
    """
    Get the number of patients belonging
    to a hospital.

    Returns:
        int
    """

    if not hospital_id:
        return 0

    try:

        response = (
            admin_supabase
            .table("patients")
            .select(
                "patient_id",
                count="exact",
            )
            .eq(
                "hospital_id",
                hospital_id,
            )
            .execute()
        )

        return response.count or 0

    except Exception as exc:

        print(
            "Failed to get hospital patient count: "
            f"{exc}"
        )

        return 0


# ============================================================
# GET HOSPITAL X-RAY COUNT
# ============================================================

def get_hospital_xray_count(
    hospital_id,
):
    """
    Get the number of X-ray images analyzed
    by a hospital during the current month.

    The monthly X-ray limit is based on X-ray images
    uploaded to the xray_images table.

    The relationship is:

        xray_images
            -> xray_requests
                -> hospital_id

    Returns:
        int
    """

    if not hospital_id:
        return 0

    try:

        month_range = (
            _get_current_month_range()
        )

        start_date = (
            month_range["start"].isoformat()
        )

        end_date = (
            month_range["end"].isoformat()
        )

        response = (
            admin_supabase
            .table("xray_images")
            .select(
                """
                image_id,
                uploaded_at,
                xray_requests!inner (
                    request_id,
                    hospital_id
                )
                """,
                count="exact",
            )
            .eq(
                "xray_requests.hospital_id",
                hospital_id,
            )
            .gte(
                "uploaded_at",
                start_date,
            )
            .lt(
                "uploaded_at",
                end_date,
            )
            .execute()
        )

        return response.count or 0

    except Exception as exc:

        print(
            "Failed to get hospital X-ray count: "
            f"{exc}"
        )

        return 0


# ============================================================
# GET HOSPITAL USAGE
# ============================================================

def get_hospital_usage(
    hospital_id,
):
    """
    Get the current usage of a hospital.

    Returns:

        {
            "users": 3,
            "patients": 25,
            "xrays": 12
        }

    X-ray usage is counted for the CURRENT MONTH.
    """

    if not hospital_id:

        return {
            "users": 0,
            "patients": 0,
            "xrays": 0,
        }

    return {
        "users": get_hospital_user_count(
            hospital_id
        ),

        "patients": get_hospital_patient_count(
            hospital_id
        ),

        "xrays": get_hospital_xray_count(
            hospital_id
        ),
    }


# ============================================================
# GET REMAINING USAGE
# ============================================================

def get_remaining_usage(
    hospital_id,
):
    """
    Compare the hospital's current usage against
    the limits of its subscription plan.

    NULL limits are treated as unlimited.

    Returns:

        {
            "users": {
                "used": 3,
                "limit": 5,
                "remaining": 2,
                "unlimited": False
            },

            "patients": {
                "used": 25,
                "limit": 100,
                "remaining": 75,
                "unlimited": False
            },

            "xrays": {
                "used": 12,
                "limit": 50,
                "remaining": 38,
                "unlimited": False
            }
        }
    """

    subscription = (
        get_hospital_subscription(
            hospital_id
        )
    )

    usage = (
        get_hospital_usage(
            hospital_id
        )
    )

    # --------------------------------------------------------
    # No subscription
    # --------------------------------------------------------

    if not subscription:

        return {
            "users": {
                "used": usage["users"],
                "limit": 0,
                "remaining": 0,
                "unlimited": False,
            },

            "patients": {
                "used": usage["patients"],
                "limit": 0,
                "remaining": 0,
                "unlimited": False,
            },

            "xrays": {
                "used": usage["xrays"],
                "limit": 0,
                "remaining": 0,
                "unlimited": False,
            },
        }

    plan = subscription.get("plan")

    if not plan:

        return {
            "users": {
                "used": usage["users"],
                "limit": 0,
                "remaining": 0,
                "unlimited": False,
            },

            "patients": {
                "used": usage["patients"],
                "limit": 0,
                "remaining": 0,
                "unlimited": False,
            },

            "xrays": {
                "used": usage["xrays"],
                "limit": 0,
                "remaining": 0,
                "unlimited": False,
            },
        }

    # --------------------------------------------------------
    # Limits
    # --------------------------------------------------------

    user_limit = plan.get(
        "max_users"
    )

    patient_limit = plan.get(
        "max_patients"
    )

    xray_limit = plan.get(
        "max_xrays_per_month"
    )

    # --------------------------------------------------------
    # Users
    # --------------------------------------------------------

    if user_limit is None:

        user_remaining = None
        user_unlimited = True

    else:

        user_remaining = max(
            int(user_limit)
            - usage["users"],
            0,
        )

        user_unlimited = False

    # --------------------------------------------------------
    # Patients
    # --------------------------------------------------------

    if patient_limit is None:

        patient_remaining = None
        patient_unlimited = True

    else:

        patient_remaining = max(
            int(patient_limit)
            - usage["patients"],
            0,
        )

        patient_unlimited = False

    # --------------------------------------------------------
    # X-rays
    # --------------------------------------------------------

    if xray_limit is None:

        xray_remaining = None
        xray_unlimited = True

    else:

        xray_remaining = max(
            int(xray_limit)
            - usage["xrays"],
            0,
        )

        xray_unlimited = False

    return {
        "users": {
            "used": usage["users"],
            "limit": user_limit,
            "remaining": user_remaining,
            "unlimited": user_unlimited,
        },

        "patients": {
            "used": usage["patients"],
            "limit": patient_limit,
            "remaining": patient_remaining,
            "unlimited": patient_unlimited,
        },

        "xrays": {
            "used": usage["xrays"],
            "limit": xray_limit,
            "remaining": xray_remaining,
            "unlimited": xray_unlimited,
        },
    }


# ============================================================
# CAN CREATE USER
# ============================================================

def can_create_user(
    hospital_id,
):
    """
    Check whether a hospital can create another user.

    Returns:

        {
            "allowed": True,
            "used": 3,
            "limit": 5,
            "remaining": 2,
            "message": "User limit available."
        }

    If max_users is NULL, the hospital has unlimited users.
    """

    if not hospital_id:

        return {
            "allowed": False,
            "used": 0,
            "limit": 0,
            "remaining": 0,
            "message": (
                "Hospital ID is required."
            ),
        }

    usage = get_remaining_usage(
        hospital_id
    )

    data = usage["users"]

    if data["unlimited"]:

        return {
            "allowed": True,
            "used": data["used"],
            "limit": None,
            "remaining": None,
            "message": (
                "User limit is unlimited."
            ),
        }

    allowed = (
        data["remaining"] > 0
    )

    if allowed:

        message = (
            "User limit available."
        )

    else:

        message = (
            "User limit reached. "
            "Please upgrade your subscription "
            "to create more users."
        )

    return {
        "allowed": allowed,
        "used": data["used"],
        "limit": data["limit"],
        "remaining": data["remaining"],
        "message": message,
    }


# ============================================================
# CAN REGISTER PATIENT
# ============================================================

def can_register_patient(
    hospital_id,
):
    """
    Check whether a hospital can register
    another patient.

    Returns the same structure as can_create_user().
    """

    if not hospital_id:

        return {
            "allowed": False,
            "used": 0,
            "limit": 0,
            "remaining": 0,
            "message": (
                "Hospital ID is required."
            ),
        }

    usage = get_remaining_usage(
        hospital_id
    )

    data = usage["patients"]

    if data["unlimited"]:

        return {
            "allowed": True,
            "used": data["used"],
            "limit": None,
            "remaining": None,
            "message": (
                "Patient limit is unlimited."
            ),
        }

    allowed = (
        data["remaining"] > 0
    )

    if allowed:

        message = (
            "Patient registration available."
        )

    else:

        message = (
            "Patient limit reached. "
            "Please upgrade your subscription "
            "to register more patients."
        )

    return {
        "allowed": allowed,
        "used": data["used"],
        "limit": data["limit"],
        "remaining": data["remaining"],
        "message": message,
    }


# ============================================================
# CAN ANALYZE X-RAY
# ============================================================

def can_analyze_xray(
    hospital_id,
):
    """
    Check whether a hospital can analyze
    another X-ray during the current month.

    The X-ray limit is based on:

        max_xrays_per_month

    NULL means unlimited.
    """

    if not hospital_id:

        return {
            "allowed": False,
            "used": 0,
            "limit": 0,
            "remaining": 0,
            "message": (
                "Hospital ID is required."
            ),
        }

    usage = get_remaining_usage(
        hospital_id
    )

    data = usage["xrays"]

    if data["unlimited"]:

        return {
            "allowed": True,
            "used": data["used"],
            "limit": None,
            "remaining": None,
            "message": (
                "Monthly X-ray limit is unlimited."
            ),
        }

    allowed = (
        data["remaining"] > 0
    )

    if allowed:

        message = (
            "X-ray analysis available."
        )

    else:

        message = (
            "Monthly X-ray limit reached. "
            "Please upgrade your subscription "
            "to analyze more X-rays."
        )

    return {
        "allowed": allowed,
        "used": data["used"],
        "limit": data["limit"],
        "remaining": data["remaining"],
        "message": message,
    }