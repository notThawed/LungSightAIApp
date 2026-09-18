from backend.supabase_client import supabase, admin_supabase


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