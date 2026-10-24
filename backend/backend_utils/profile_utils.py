from backend.supabase_client import admin_supabase


# ============================================================
# ROLE PERMISSIONS
# ============================================================

ROLE_PERMISSIONS = {
    "Hospital Admin": {
        "edit_personal_info": True,
        "edit_profile_picture": True,
        "edit_password": True,
        "show_hospital_info": True,
        "edit_hospital_info": True,
        "edit_hospital_theme": True,
        "edit_preferences": True,
        "edit_system_settings": False,
    },
    "Staff": {
        "edit_personal_info": True,
        "edit_profile_picture": True,
        "edit_password": True,
        "show_hospital_info": False,
        "edit_hospital_info": False,
        "edit_hospital_theme": False,
        "edit_preferences": True,
        "edit_system_settings": False,
    },
    "Radiologic Technologist": {
        "edit_personal_info": True,
        "edit_profile_picture": True,
        "edit_password": True,
        "show_hospital_info": False,
        "edit_hospital_info": False,
        "edit_hospital_theme": False,
        "edit_preferences": True,
        "edit_system_settings": False,
    },
    "Radiologist": {
        "edit_personal_info": True,
        "edit_profile_picture": True,
        "edit_password": True,
        "show_hospital_info": False,
        "edit_hospital_info": False,
        "edit_hospital_theme": False,
        "edit_preferences": True,
        "edit_system_settings": False,
    },
    "Superadmin": {
        "edit_personal_info": True,
        "edit_profile_picture": True,
        "edit_password": True,
        "show_hospital_info": False,
        "edit_hospital_info": False,
        "edit_hospital_theme": False,
        "edit_preferences": True,
        "edit_system_settings": True,
    },
}

DEFAULT_PERMISSIONS = {
    "edit_personal_info": True,
    "edit_profile_picture": True,
    "edit_password": True,
    "show_hospital_info": False,
    "edit_hospital_info": False,
    "edit_hospital_theme": False,
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
#
# NOTE: The user_profiles table does not yet have
# notifications_enabled, date_format, or time_format columns.
# These functions return defaults / soft failures until the
# columns are added. To enable real persistence, run:
#
#   ALTER TABLE public.user_profiles
#   ADD COLUMN IF NOT EXISTS notifications_enabled boolean
#       NOT NULL DEFAULT true,
#   ADD COLUMN IF NOT EXISTS date_format text
#       NOT NULL DEFAULT 'MM/DD/YYYY',
#   ADD COLUMN IF NOT EXISTS time_format text
#       NOT NULL DEFAULT '12-hour';
#
# Then restore the DB read/write code in these two functions.
# ============================================================

DATE_FORMAT_OPTIONS = ["MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD"]
TIME_FORMAT_OPTIONS = ["12-hour", "24-hour"]


def get_user_preferences(user_id):
    """
    Return preferences.

    Preferences columns are not yet in the database,
    so defaults are always returned.
    """

    return {
        "notifications_enabled": True,
        "date_format": DATE_FORMAT_OPTIONS[0],
        "time_format": TIME_FORMAT_OPTIONS[0],
    }


def update_user_preferences(user_id, notifications_enabled, date_format, time_format):
    """
    Preferences storage is not yet enabled.

    Returns a soft failure so the UI shows a friendly
    message instead of an exception.
    """

    if not user_id:
        return {"success": False, "message": "User ID is required."}

    return {
        "success": False,
        "message": (
            "Preferences cannot be saved yet — "
            "the database columns have not been added. "
            "Contact your system administrator."
        ),
    }


# ============================================================
# PASSWORD
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