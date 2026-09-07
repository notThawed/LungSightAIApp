from backend.supabase_client import supabase, admin_supabase
from datetime import datetime

def get_all_users():
    response = (
        supabase.table("user_profiles")
        .select("""
            *,
            roles (
                role_name
            )
        """)
        .execute()
    )

    return response.data

def get_all_roles():
    response = (
        supabase
        .table("roles")
        .select("role_id, role_name")
        .order("role_id")
        .execute()
    )

    return response.data


def generate_employee_id():
    current_year = datetime.now().year

    response = (
        supabase
        .table("user_profiles")
        .select("employee_id")
        .like("employee_id", f"EMP-{current_year}-%")
        .order("employee_id", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        return f"EMP-{current_year}-001"

    last_id = response.data[0]["employee_id"]

    number = int(last_id.split("-")[-1]) + 1

    return f"EMP-{current_year}-{number:03d}"

def get_user(user_id):
    # -----------------------------
    # Get user profile
    # -----------------------------
    profile_response = (
        supabase
        .table("user_profiles")
        .select("""
            *,
            roles(
                role_id,
                role_name
            )
        """)
        .eq("user_id", user_id)
        .single()
        .execute()
    )

    profile = profile_response.data

    # -----------------------------
    # Get auth user (email)
    # -----------------------------
    auth_response = (
        admin_supabase
        .auth
        .admin
        .get_user_by_id(user_id)
    )

    print("AUTH RESPONSE:", auth_response)

    if auth_response.user:
        profile["email"] = auth_response.user.email
    else:
        profile["email"] = ""

    return profile