from backend.supabase_client import admin_supabase


# ============================================================
# ROLE PERMISSIONS
# Single source of truth for what each role may see/edit on
# the Profile Settings page. Add a new role here — profile.py
# picks it up automatically. No new page file needed.
# ============================================================

ROLE_PERMISSIONS = {
    "Hospital Admin": {
        "edit_personal_info": True,
        "edit_profile_picture": True,
        "edit_password": True,
        "show_hospital_info": True,
        "edit_hospital_info": True,
        "edit_preferences": True,
        "edit_system_settings": False,
    },
    "Staff": {
        "edit_personal_info": True,
        "edit_profile_picture": True,
        "edit_password": True,
        "show_hospital_info": False,
        "edit_hospital_info": False,
        "edit_preferences": True,
        "edit_system_settings": False,
    },
    "Radiologic Technologist": {
        "edit_personal_info": True,
        "edit_profile_picture": True,
        "edit_password": True,
        "show_hospital_info": False,
        "edit_hospital_info": False,
        "edit_preferences": True,
        "edit_system_settings": False,
    },
    "Radiologist": {
        "edit_personal_info": True,
        "edit_profile_picture": True,
        "edit_password": True,
        "show_hospital_info": False,
        "edit_hospital_info": False,
        "edit_preferences": True,
        "edit_system_settings": False,
    },
    "Superadmin": {
        "edit_personal_info": True,
        "edit_profile_picture": True,
        "edit_password": True,
        "show_hospital_info": False,
        "edit_hospital_info": False,
        "edit_preferences": True,
        "edit_system_settings": True,
    },
}

# Fallback for any role not listed above — safe defaults
# (can edit their own basics, nothing hospital-wide or system-wide).
DEFAULT_PERMISSIONS = {
    "edit_personal_info": True,
    "edit_profile_picture": True,
    "edit_password": True,
    "show_hospital_info": False,
    "edit_hospital_info": False,
    "edit_preferences": True,
    "edit_system_settings": False,
}


def get_role_permissions(role):
    """What this role may see/edit on the Profile Settings page."""
    return ROLE_PERMISSIONS.get(role, DEFAULT_PERMISSIONS)


# ============================================================
# ACCOUNT STATUS LABEL
# ============================================================

ACCOUNT_STATUS_LABELS = {
    "active": "Active",
    "inactive": "Inactive",
    "suspended": "Suspended",
    "pending": "Pending Activation",
}


def account_status_label(status):
    return ACCOUNT_STATUS_LABELS.get(str(status).lower(), status or "Unknown")


# ============================================================
# PERSONAL INFORMATION
# ASSUMPTION: user_profiles table has columns
# user_fname, user_mname, user_lname, birthdate, sex,
# user_contact_number, address — verify against your schema.
# ============================================================

def update_personal_information(
    user_id,
    first_name,
    middle_name,
    last_name,
    birthdate=None,
    sex=None,
    contact_number=None,
    address=None,
):
    """Update the editable personal fields on user_profiles."""

    if not user_id:
        return {"success": False, "message": "User ID is required."}

    if not first_name or not first_name.strip():
        return {"success": False, "message": "First name is required."}

    if not last_name or not last_name.strip():
        return {"success": False, "message": "Last name is required."}

    try:
        admin_supabase.table("user_profiles").update({
            "user_fname": first_name.strip(),
            "user_mname": (middle_name or "").strip(),
            "user_lname": last_name.strip(),
            "user_birthdate": birthdate.isoformat() if birthdate else None,
            "user_sex": sex,
            "user_contact_number": (contact_number or "").strip(),
            "user_address": (address or "").strip(),
        }).eq("user_id", user_id).execute()

        return {"success": True, "message": "Personal information updated successfully."}

    except Exception as e:
        return {"success": False, "message": f"Unable to update personal information: {e}"}


def remove_profile_picture(user_id):
    """
    Remove the user's profile picture.

    This performs both operations:

        1. Delete the actual image from Supabase Storage.
        2. Clear profile_picture_url in user_profiles.

    No profile-picture history is kept.
    """

    if not user_id:
        return {
            "success": False,
            "message": "User ID is required.",
        }

    try:

        # ----------------------------------------------------
        # Delete the actual Storage object first.
        # ----------------------------------------------------

        from backend.backend_utils.storage_utils import (
            delete_profile_picture,
        )

        storage_result = delete_profile_picture(
            user_id
        )

        if not storage_result["success"]:
            return {
                "success": False,
                "message": storage_result["message"],
            }

        # ----------------------------------------------------
        # Clear the database reference.
        # ----------------------------------------------------

        admin_supabase.table(
            "user_profiles"
        ).update({
            "profile_picture_url": None,
        }).eq(
            "user_id",
            user_id,
        ).execute()

        return {
            "success": True,
            "message": "Profile picture removed.",
        }

    except Exception as e:

        return {
            "success": False,
            "message": (
                "Unable to remove profile picture: "
                f"{e}"
            ),
        }


# ============================================================
# PREFERENCES (notifications, date/time)
# ASSUMPTION: user_profiles has notifications_enabled (bool),
# date_format (text), time_format (text) columns.
# If you'd rather keep these in a separate "user_preferences"
# table, just change the table name below.
# ============================================================

DATE_FORMAT_OPTIONS = ["MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD"]
TIME_FORMAT_OPTIONS = ["12-hour", "24-hour"]


def get_user_preferences(user_id):
    """Returns {notifications_enabled, date_format, time_format} with safe defaults."""

    defaults = {
        "notifications_enabled": True,
        "date_format": DATE_FORMAT_OPTIONS[0],
        "time_format": TIME_FORMAT_OPTIONS[0],
    }

    if not user_id:
        return defaults

    try:
        response = (
            admin_supabase.table("user_profiles")
            .select("notifications_enabled, date_format, time_format")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            return defaults

        row = response.data[0]

        return {
            "notifications_enabled": row.get("notifications_enabled", True),
            "date_format": row.get("date_format") or DATE_FORMAT_OPTIONS[0],
            "time_format": row.get("time_format") or TIME_FORMAT_OPTIONS[0],
        }

    except Exception as e:
        print(f"Preferences lookup error: {e}")
        return defaults


def update_user_preferences(user_id, notifications_enabled, date_format, time_format):

    if not user_id:
        return {"success": False, "message": "User ID is required."}

    try:
        admin_supabase.table("user_profiles").update({
            "notifications_enabled": notifications_enabled,
            "date_format": date_format,
            "time_format": time_format,
        }).eq("user_id", user_id).execute()

        return {"success": True, "message": "Preferences updated."}

    except Exception as e:
        return {"success": False, "message": f"Unable to update preferences: {e}"}


# ============================================================
# PASSWORD
# ASSUMPTION: admin_supabase exposes the Supabase auth admin
# API (admin_supabase.auth.admin.update_user_by_id). If your
# backend/auth.py already wraps this differently, swap the
# body of this function to call that instead.
# ============================================================

def change_password(user_id, new_password, confirm_password):

    if not new_password or len(new_password) < 8:
        return {"success": False, "message": "Password must be at least 8 characters."}

    if new_password != confirm_password:
        return {"success": False, "message": "Passwords do not match."}

    try:
        admin_supabase.auth.admin.update_user_by_id(
            user_id,
            {"password": new_password},
        )
        return {"success": True, "message": "Password updated successfully."}

    except Exception as e:
        return {"success": False, "message": f"Unable to update password: {e}"}


# ============================================================
# LAST LOGIN
# ASSUMPTION: user_profiles has a last_login timestamp column,
# updated elsewhere (e.g. in your login flow). If it isn't
# tracked yet, this simply returns None and the UI shows "—".
# ============================================================

def get_last_login(user_id):

    if not user_id:
        return None

    try:
        response = admin_supabase.auth.admin.get_user_by_id(user_id)

        if not response or not response.user:
            return None

        return response.user.last_sign_in_at

    except Exception as e:
        print(f"Last login lookup error: {e}")
        return None