from backend.supabase_client import supabase, admin_supabase

def get_all_subscription_plans():

    response = (
        admin_supabase
        .table("subscription_plans")
        .select("*")
        .order("plan_id")
        .execute()
    )

    return response.data or []

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
            supabase
            .table("subscription_plans")
            .insert(plan_data)
            .execute()
        )

        return {
            "success": True,
            "message": "Subscription plan created successfully,",
            "data": response.data
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }

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

def deactivate_subscription(
        plan_id
):
    try:
        update_data = {
            "is_active": False
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
            "data": response.data
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }

def activate_subscription(
        plan_id
):

    try:
        update_data = {
            "is_active": True
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
            "data": response.data
        }
    except Exception as e:
        return {
        "success": False,
        "message": str(e)
        }
    

