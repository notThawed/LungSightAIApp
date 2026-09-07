from backend.supabase_client import admin_supabase

def create_user(
    email,
    password,
    first_name,
    middle_name,
    last_name,
    birth_date,
    employee_id,
    role_id,
    contact_number,
    address,
):
    # Create Auth account
    auth_response = admin_supabase.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True
    })

    user = auth_response.user

    if not user:
        raise Exception("Failed to create auth account.")

    # Insert into user_profiles
    admin_supabase.table("user_profiles").insert({
        "user_id": user.id,
        "user_fname": first_name,
        "user_mname": middle_name,
        "user_lname": last_name,
        "user_birthdate": birth_date.isoformat(),
        "employee_id": employee_id,
        "role_id": role_id,
        "user_contact_number": contact_number,
        "user_address": address,
        "is_active": True
    }).execute()

def delete_user(user_id):
    admin_supabase.auth.admin.delete_user(user_id)
    admin_supabase.table("user_profiles").delete().eq("user_id", user_id).execute()


def update_user(
    user_id,
    email,
    password,
    first_name,
    middle_name,
    last_name,
    birth_date,
    role_id,
    contact_number,
    address,
):
    # ----------------------------
    # Update Auth
    # ----------------------------
    auth_updates = {
        "email": email
    }

    # Only update password if entered
    if password:
        auth_updates["password"] = password

    admin_supabase.auth.admin.update_user_by_id(
        user_id,
        auth_updates
    )

    # ----------------------------
    # Update Profile
    # ----------------------------
    admin_supabase.table("user_profiles").update({
        "user_fname": first_name,
        "user_mname": middle_name,
        "user_lname": last_name,
        "user_birthdate": birth_date.isoformat(),
        "role_id": role_id,
        "user_contact_number": contact_number,
        "user_address": address
    }).eq(
        "user_id",
        user_id
    ).execute()