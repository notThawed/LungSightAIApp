from datetime import (
    datetime,
    timezone,
    date,
    timedelta,
)

import os
import re

from backend.supabase_client import (
    admin_supabase,
)

from backend.fetches import (
    generate_employee_id,
)


# ============================================================
# CONFIGURATION
# ============================================================

REDIRECT_URL = os.getenv(
    "INVITE_REDIRECT_URL",
    "http://localhost:8501/app/static/redirect.html",
)


EMAIL_REGEX = re.compile(
    r"^[A-Za-z0-9._%+\-]+@"
    r"[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
)


# ============================================================
# EMAIL VALIDATION
# ============================================================

def is_valid_email(value):
    """
    Validate an email address.
    """

    if not value:
        return False

    return bool(
        EMAIL_REGEX.match(
            value.strip()
        )
    )


# ============================================================
# GET HOSPITAL BY ID
# ============================================================

def get_hospital_by_id(hospital_id):
    """
    Get one hospital by hospital_id.

    Uses the admin Supabase client so this function can
    reliably retrieve hospital information regardless of
    the current user's RLS policies.
    """

    try:

        if not hospital_id:
            return None

        response = (
            admin_supabase
            .table("hospitals")
            .select("*")
            .eq(
                "hospital_id",
                hospital_id,
            )
            .single()
            .execute()
        )

        return response.data

    except Exception as exc:

        print(
            f"Error getting hospital: {exc}"
        )

        return None


# ============================================================
# GET USER PROFILE BY ID
# ============================================================

def get_user_profile_by_id(user_id):
    """
    Get a LungSight user profile by user_id.

    This is used by the setup wizard to refresh the
    administrator's information after uploading a profile
    picture.
    """

    try:

        if not user_id:
            return None

        response = (
            admin_supabase
            .table("user_profiles")
            .select(
                """
                user_id,
                employee_id,
                user_fname,
                user_mname,
                user_lname,
                user_birthdate,
                user_sex,
                user_contact_number,
                user_address,
                role_id,
                hospital_id,
                profile_picture_url,
                is_active,
                last_login
                """
            )
            .eq(
                "user_id",
                user_id,
            )
            .single()
            .execute()
        )

        return response.data

    except Exception as exc:

        print(
            f"Error getting user profile: {exc}"
        )

        return None


# ============================================================
# UPDATE HOSPITAL INFORMATION
# ============================================================

def update_hospital_information(
    hospital_id,
    hospital_name,
    hospital_type,
    address,
    contact_number,
    email,
    website=None,
):
    """
    Update the hospital's general information.

    The hospital logo URL is intentionally handled separately
    by update_hospital_logo_url().
    """

    try:

        if not hospital_id:

            return {
                "success": False,
                "message": (
                    "Hospital ID is required."
                ),
            }

        # ----------------------------------------------------
        # Prepare data
        # ----------------------------------------------------

        hospital_data = {
            "hospital_name": (
                hospital_name.strip()
                if hospital_name
                else ""
            ),

            "hospital_type": (
                hospital_type
            ),

            "address": (
                address.strip()
                if address
                else ""
            ),

            "contact_number": (
                contact_number.strip()
                if contact_number
                else None
            ),

            "email": (
                email.strip().lower()
                if email
                else None
            ),
        }

        # ----------------------------------------------------
        # Website
        # ----------------------------------------------------

        if website is not None:

            hospital_data["website"] = (
                website.strip()
                if website
                else None
            )

        # ----------------------------------------------------
        # Update hospital
        # ----------------------------------------------------

        response = (
            admin_supabase
            .table("hospitals")
            .update(
                hospital_data
            )
            .eq(
                "hospital_id",
                hospital_id,
            )
            .execute()
        )

        if not response.data:

            return {
                "success": False,
                "message": (
                    "Hospital information could not "
                    "be updated."
                ),
            }

        return {
            "success": True,
            "message": (
                "Hospital information updated successfully."
            ),
            "hospital": response.data[0],
        }

    except Exception as exc:

        return {
            "success": False,
            "message": str(exc),
        }


# ============================================================
# UPDATE HOSPITAL LOGO URL
# ============================================================

def update_hospital_logo_url(
    hospital_id,
    logo_url,
):
    """
    Save the public Supabase Storage URL of a hospital logo
    into hospitals.hospital_logo_url.

    This uses admin_supabase so the operation is not blocked
    by the hospitals table's RLS policies.
    """

    try:

        if not hospital_id:

            return {
                "success": False,
                "message": (
                    "Hospital ID is required."
                ),
            }

        if not logo_url:

            return {
                "success": False,
                "message": (
                    "Hospital logo URL is required."
                ),
            }

        response = (
            admin_supabase
            .table("hospitals")
            .update(
                {
                    "hospital_logo_url": logo_url,
                }
            )
            .eq(
                "hospital_id",
                hospital_id,
            )
            .execute()
        )

        if not response.data:

            return {
                "success": False,
                "message": (
                    "Hospital logo URL could not "
                    "be saved."
                ),
            }

        return {
            "success": True,
            "message": (
                "Hospital logo URL saved successfully."
            ),
            "hospital": response.data[0],
        }

    except Exception as exc:

        return {
            "success": False,
            "message": str(exc),
        }


# ============================================================
# UPDATE PROFILE PICTURE URL
# ============================================================

def update_profile_picture_url(
    user_id,
    profile_picture_url,
):
    """
    Save the public Supabase Storage URL of a user's
    profile picture into user_profiles.profile_picture_url.

    Uses admin_supabase so RLS does not prevent the setup
    wizard from saving the URL.
    """

    try:

        if not user_id:

            return {
                "success": False,
                "message": (
                    "User ID is required."
                ),
            }

        if not profile_picture_url:

            return {
                "success": False,
                "message": (
                    "Profile picture URL is required."
                ),
            }

        response = (
            admin_supabase
            .table("user_profiles")
            .update(
                {
                    "profile_picture_url":
                        profile_picture_url,
                }
            )
            .eq(
                "user_id",
                user_id,
            )
            .execute()
        )

        if not response.data:

            return {
                "success": False,
                "message": (
                    "Profile picture URL could not "
                    "be saved."
                ),
            }

        return {
            "success": True,
            "message": (
                "Profile picture URL saved successfully."
            ),
            "profile": response.data[0],
        }

    except Exception as exc:

        return {
            "success": False,
            "message": str(exc),
        }


# ============================================================
# COMPLETE HOSPITAL SETUP
# ============================================================

def complete_hospital_setup(hospital_id):
    """
    Complete the hospital setup process.

    This:
        1. Verifies the hospital exists.
        2. Prevents duplicate setup completion.
        3. Gets the hospital subscription.
        4. Verifies the subscription is Pending Setup.
        5. Calculates the subscription period.
        6. Marks the hospital setup as completed.
        7. Activates the hospital subscription.
    """

    try:

        if not hospital_id:

            return {
                "success": False,
                "message": (
                    "Hospital ID is required."
                ),
            }

        # ====================================================
        # 1. GET HOSPITAL
        # ====================================================

        hospital = get_hospital_by_id(
            hospital_id
        )

        if not hospital:

            return {
                "success": False,
                "message": (
                    "Hospital not found."
                ),
            }

        # ====================================================
        # 2. PREVENT DUPLICATE SETUP
        # ====================================================

        if hospital.get(
            "setup_completed",
            False,
        ):

            return {
                "success": False,
                "message": (
                    "Hospital setup has already "
                    "been completed."
                ),
            }

        # ====================================================
        # 3. GET HOSPITAL SUBSCRIPTION
        # ====================================================

        subscription_response = (
            admin_supabase
            .table("hospital_subscriptions")
            .select(
                "hospital_subscription_id, "
                "billing_cycle, "
                "status"
            )
            .eq(
                "hospital_id",
                hospital_id,
            )
            .single()
            .execute()
        )

        subscription = (
            subscription_response.data
        )

        if not subscription:

            return {
                "success": False,
                "message": (
                    "No subscription found for this "
                    "hospital. Cannot complete setup."
                ),
            }

        # ====================================================
        # 4. CHECK SUBSCRIPTION STATUS
        # ====================================================

        if subscription.get(
            "status"
        ) != "Pending Setup":

            return {
                "success": False,
                "message": (
                    "Subscription is not pending setup "
                    f"(current status: "
                    f"{subscription.get('status')})."
                ),
            }

        # ====================================================
        # 5. CALCULATE SUBSCRIPTION DATES
        # ====================================================

        billing_cycle = (
            subscription.get(
                "billing_cycle"
            )
        )

        if billing_cycle == "Yearly":

            period_days = 365

        else:

            period_days = 30

        today = date.today()

        end_date = (
            today
            + timedelta(
                days=period_days
            )
        )

        completed_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        # ====================================================
        # 6. MARK HOSPITAL SETUP COMPLETED
        # ====================================================

        hospital_response = (
            admin_supabase
            .table("hospitals")
            .update(
                {
                    "setup_completed": True,
                    "setup_completed_at": completed_at,
                }
            )
            .eq(
                "hospital_id",
                hospital_id,
            )
            .execute()
        )

        if not hospital_response.data:

            return {
                "success": False,
                "message": (
                    "Hospital setup could not "
                    "be completed."
                ),
            }

        # ====================================================
        # 7. ACTIVATE SUBSCRIPTION
        # ====================================================

        subscription_response = (
            admin_supabase
            .table("hospital_subscriptions")
            .update(
                {
                    "status": "Active",
                    "start_date": today.isoformat(),
                    "end_date": end_date.isoformat(),
                    "updated_at": completed_at,
                }
            )
            .eq(
                "hospital_id",
                hospital_id,
            )
            .eq(
                "status",
                "Pending Setup",
            )
            .execute()
        )

        if not subscription_response.data:

            return {
                "success": False,
                "message": (
                    "Hospital setup was marked as "
                    "completed, but the subscription "
                    "could not be activated."
                ),
            }

        # ====================================================
        # 8. SUCCESS
        # ====================================================

        return {
            "success": True,
            "message": (
                "Hospital setup completed and "
                "subscription activated successfully."
            ),
            "hospital":
                hospital_response.data[0],
            "subscription":
                subscription_response.data,
        }

    except Exception as exc:

        return {
            "success": False,
            "message": str(exc),
        }


# ============================================================
# CREATE HOSPITAL ADMIN
# ============================================================

def create_hospital_admin(
    application,
    hospital_id,
):
    """
    Create a Hospital Administrator Auth account and
    corresponding user_profiles record.
    """

    try:

        # ====================================================
        # 1. GET ADMINISTRATOR INFORMATION
        # ====================================================

        first_name = (
            application.get(
                "admin_first_name"
            )
            or ""
        ).strip()

        middle_name = (
            application.get(
                "admin_middle_name"
            )
            or ""
        ).strip()

        last_name = (
            application.get(
                "admin_last_name"
            )
            or ""
        ).strip()

        email = (
            application.get(
                "admin_email"
            )
            or ""
        ).strip().lower()

        contact_number = (
            application.get(
                "admin_contact_number"
            )
            or ""
        ).strip()

        # ====================================================
        # 2. VALIDATE
        # ====================================================

        if not first_name:

            return {
                "success": False,
                "message": (
                    "Hospital administrator "
                    "first name is missing."
                ),
            }

        if not last_name:

            return {
                "success": False,
                "message": (
                    "Hospital administrator "
                    "last name is missing."
                ),
            }

        if not email:

            return {
                "success": False,
                "message": (
                    "Hospital administrator "
                    "email is missing."
                ),
            }

        if not is_valid_email(email):

            return {
                "success": False,
                "message": (
                    "Hospital administrator "
                    "email is not a valid email address."
                ),
            }

        if not hospital_id:

            return {
                "success": False,
                "message": (
                    "Hospital ID is missing."
                ),
            }

        # ====================================================
        # 3. SEND SUPABASE INVITATION
        # ====================================================

        invite_response = (
            admin_supabase
            .auth
            .admin
            .invite_user_by_email(
                email,
                options={
                    "redirect_to": REDIRECT_URL,
                    "data": {
                        "first_name":
                            first_name,
                        "middle_name":
                            middle_name,
                        "last_name":
                            last_name,
                        "role":
                            "Hospital Admin",
                        "hospital_id":
                            hospital_id,
                    },
                },
            )
        )

        if not invite_response.user:

            return {
                "success": False,
                "message": (
                    "Failed to send Hospital "
                    "Administrator invitation email."
                ),
            }

        user_id = (
            invite_response.user.id
        )

        # ====================================================
        # 4. GENERATE EMPLOYEE ID
        # ====================================================

        employee_id = (
            generate_employee_id()
        )

        if not employee_id:

            try:

                admin_supabase.auth.admin.delete_user(
                    user_id
                )

            except Exception:
                pass

            return {
                "success": False,
                "message": (
                    "Hospital Administrator invitation "
                    "was sent, but an Employee ID "
                    "could not be generated."
                ),
            }

        # ====================================================
        # 5. GET HOSPITAL ADMIN ROLE
        # ====================================================

        role_response = (
            admin_supabase
            .table("roles")
            .select(
                "role_id, role_name"
            )
            .eq(
                "role_name",
                "Hospital Admin",
            )
            .single()
            .execute()
        )

        role = role_response.data

        if not role:

            try:

                admin_supabase.auth.admin.delete_user(
                    user_id
                )

            except Exception:
                pass

            return {
                "success": False,
                "message": (
                    "Hospital Admin role "
                    "was not found."
                ),
            }

        # ====================================================
        # 6. CREATE USER PROFILE
        # ====================================================

        profile_data = {
            "user_id":
                user_id,

            "employee_id":
                employee_id,

            "user_fname":
                first_name,

            "user_mname":
                middle_name or None,

            "user_lname":
                last_name,

            "role_id":
                role["role_id"],

            "hospital_id":
                hospital_id,

            "user_contact_number":
                contact_number or None,

            "is_active":
                True,
        }

        profile_response = (
            admin_supabase
            .table("user_profiles")
            .insert(
                profile_data
            )
            .execute()
        )

        if not profile_response.data:

            try:

                admin_supabase.auth.admin.delete_user(
                    user_id
                )

            except Exception:
                pass

            return {
                "success": False,
                "message": (
                    "Hospital Admin invitation was sent, "
                    "but the user profile could not be created. "
                    "The invite has been rolled back — "
                    "you can retry."
                ),
            }

        # ====================================================
        # 7. SUCCESS
        # ====================================================

        return {
            "success": True,
            "message": (
                "Hospital Administrator invitation "
                f"sent to {email}."
            ),
            "user_id":
                user_id,
            "employee_id":
                employee_id,
            "profile":
                profile_response.data[0],
        }

    except Exception as exc:

        message = str(exc)

        if (
            "already been registered"
            in message
            or "already exists"
            in message
        ):

            message = (
                "A user with this email already exists."
            )

        return {
            "success": False,
            "message": message,
        }


# ============================================================
# CHECK HOSPITAL SETUP STATUS
# ============================================================

def is_hospital_setup_completed(
    hospital_id,
):
    """
    Return True when the hospital has completed setup.
    """

    try:

        if not hospital_id:
            return False

        response = (
            admin_supabase
            .table("hospitals")
            .select(
                "setup_completed"
            )
            .eq(
                "hospital_id",
                hospital_id,
            )
            .single()
            .execute()
        )

        if not response.data:
            return False

        return bool(
            response.data.get(
                "setup_completed",
                False,
            )
        )

    except Exception:

        return False

def is_hospital_active(hospital_id):
    """
    Check whether a hospital is currently active.
    """

    if not hospital_id:
        return True

    try:

        response = (
            admin_supabase
            .table("hospitals")
            .select("is_active")
            .eq(
                "hospital_id",
                hospital_id
            )
            .limit(1)
            .execute()
        )

        rows = response.data or []

        if not rows:
            return False

        return bool(
            rows[0].get("is_active", False)
        )

    except Exception as e:

        print(
            "HOSPITAL STATUS CHECK ERROR:",
            repr(e)
        )

        # Fail closed.
        # If we cannot verify the hospital,
        # do not allow access.
        return False