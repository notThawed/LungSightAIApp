from datetime import datetime, timezone

from backend.supabase_client import (
    admin_supabase
)

from backend.fetches import generate_employee_id


# ============================================================
# GET HOSPITAL BY ID
# ============================================================

def get_hospital_by_id(hospital_id):

    try:

        if not hospital_id:

            return None

        response = (
            admin_supabase
            .table("hospitals")
            .select("*")
            .eq(
                "hospital_id",
                hospital_id
            )
            .single()
            .execute()
        )

        return response.data

    except Exception as e:

        print(
            f"Error getting hospital: {e}"
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
    website=None
):

    try:

        if not hospital_id:

            return {
                "success": False,
                "message": "Hospital ID is required."
            }

        # ----------------------------------------------------
        # Prepare data
        # ----------------------------------------------------

        hospital_data = {

            "hospital_name":
                hospital_name.strip(),

            "hospital_type":
                hospital_type,

            "address":
                address.strip(),

            "contact_number":
                contact_number.strip()
                if contact_number
                else None,

            "email":
                email.strip().lower()
                if email
                else None,
        }

        # ----------------------------------------------------
        # Website
        #
        # Only add this if your hospitals table has a
        # website column.
        # ----------------------------------------------------

        if website is not None:

            hospital_data["website"] = (
                website.strip()
            )

        # ----------------------------------------------------
        # Update hospital
        # ----------------------------------------------------

        response = (
            admin_supabase
            .table("hospitals")
            .update(hospital_data)
            .eq(
                "hospital_id",
                hospital_id
            )
            .execute()
        )

        if not response.data:

            return {
                "success": False,
                "message": (
                    "Hospital information could not "
                    "be updated."
                )
            }

        return {
            "success": True,
            "message": (
                "Hospital information updated successfully."
            ),
            "hospital": response.data[0]
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }


# ============================================================
# COMPLETE HOSPITAL SETUP
# ============================================================

def complete_hospital_setup(hospital_id):

    try:

        if not hospital_id:

            return {
                "success": False,
                "message": "Hospital ID is required."
            }

        # ----------------------------------------------------
        # 1. Check hospital
        # ----------------------------------------------------

        hospital = get_hospital_by_id(
            hospital_id
        )

        if not hospital:

            return {
                "success": False,
                "message": "Hospital not found."
            }

        # ----------------------------------------------------
        # 2. Prevent completing setup twice
        # ----------------------------------------------------

        if hospital.get(
            "setup_completed",
            False
        ):

            return {
                "success": False,
                "message": (
                    "Hospital setup has already "
                    "been completed."
                )
            }

        # ----------------------------------------------------
        # 3. Mark setup as completed
        # ----------------------------------------------------

        completed_at = datetime.now(
            timezone.utc
        ).isoformat()

        hospital_response = (
            admin_supabase
            .table("hospitals")
            .update({

                "setup_completed":
                    True,

                "setup_completed_at":
                    completed_at,

            })
            .eq(
                "hospital_id",
                hospital_id
            )
            .execute()
        )

        if not hospital_response.data:

            return {
                "success": False,
                "message": (
                    "Hospital setup could not "
                    "be completed."
                )
            }

        # ----------------------------------------------------
        # 4. Activate hospital subscription
        # ----------------------------------------------------
        #
        # For now, this activates the Inactive subscription
        # belonging to this hospital.
        #
        # Later, we can make this more strict by identifying
        # the exact subscription created from the application.
        # ----------------------------------------------------

        subscription_response = (
            admin_supabase
            .table("hospital_subscriptions")
            .update({

                "status":
                    "Active",

                "updated_at":
                    completed_at,

            })
            .eq(
                "hospital_id",
                hospital_id
            )
            .eq(
                "status",
                "Inactive"
            )
            .execute()
        )

        # ----------------------------------------------------
        # 5. Return success
        # ----------------------------------------------------

        return {
            "success": True,
            "message": (
                "Hospital setup completed and "
                "subscription activated successfully."
            ),
            "hospital":
                hospital_response.data[0],

            "subscription":
                subscription_response.data
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }

def create_hospital_admin(
    application,
    hospital_id
):

    try:

        # ----------------------------------------------------
        # 1. Get administrator information
        # ----------------------------------------------------

        first_name = (
            application.get("admin_first_name") or ""
        ).strip()

        middle_name = (
            application.get("admin_middle_name") or ""
        ).strip()

        last_name = (
            application.get("admin_last_name") or ""
        ).strip()

        email = (
            application.get("admin_email") or ""
        ).strip().lower()

        contact_number = (
            application.get("admin_contact_number") or ""
        ).strip()

        # ----------------------------------------------------
        # 2. Validate required information
        # ----------------------------------------------------

        if not first_name:

            return {
                "success": False,
                "message": (
                    "Hospital administrator "
                    "first name is missing."
                )
            }

        if not last_name:

            return {
                "success": False,
                "message": (
                    "Hospital administrator "
                    "last name is missing."
                )
            }

        if not email:

            return {
                "success": False,
                "message": (
                    "Hospital administrator "
                    "email is missing."
                )
            }

        if not hospital_id:

            return {
                "success": False,
                "message": (
                    "Hospital ID is missing."
                )
            }

        # ----------------------------------------------------
        # 3. Create Supabase Auth user
        # ----------------------------------------------------

        auth_response = (
            admin_supabase
            .auth
            .admin
            .create_user({

                "email":
                    email,

                # Temporary password for now.
                # We can replace this with a proper
                # invitation/password setup flow later.
                "password":
                    "ChangeMe123!",

                "email_confirm":
                    True,

                "user_metadata": {

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
                }
            })
        )

        if not auth_response.user:

            return {
                "success": False,
                "message": (
                    "Failed to create Hospital "
                    "Administrator account."
                )
            }

        user_id = auth_response.user.id

        # ----------------------------------------------------
        # 4. Generate Employee ID
        # ----------------------------------------------------

        employee_id = generate_employee_id()

        if not employee_id:

            # If employee ID generation fails,
            # remove the Auth user so we don't leave
            # an incomplete account behind.

            try:

                admin_supabase.auth.admin.delete_user(
                    user_id
                )

            except Exception:

                pass

            return {
                "success": False,
                "message": (
                    "Hospital Administrator account "
                    "was created, but an Employee ID "
                    "could not be generated."
                )
            }

        # ----------------------------------------------------
        # 5. Get Hospital Admin role
        # ----------------------------------------------------

        role_response = (
            admin_supabase
            .table("roles")
            .select(
                "role_id, role_name"
            )
            .eq(
                "role_name",
                "Hospital Admin"
            )
            .single()
            .execute()
        )

        role = role_response.data

        if not role:

            # Remove Auth user because the profile
            # cannot be created without a role.

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
                )
            }

        # ----------------------------------------------------
        # 6. Create user profile
        # ----------------------------------------------------

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

            # ------------------------------------------------
            # IMPORTANT:
            #
            # If profile creation fails, remove the Auth
            # account so we don't leave an orphaned user.
            # ------------------------------------------------

            try:

                admin_supabase.auth.admin.delete_user(
                    user_id
                )

            except Exception:

                pass

            return {
                "success": False,
                "message": (
                    "Hospital Admin account was created, "
                    "but the user profile could not be created."
                )
            }

        # ----------------------------------------------------
        # 7. Success
        # ----------------------------------------------------

        return {

            "success":
                True,

            "message": (
                "Hospital Administrator account "
                "created successfully."
            ),

            "user_id":
                user_id,

            "employee_id":
                employee_id,

            "profile":
                profile_response.data[0],
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }

def is_hospital_setup_completed(hospital_id):

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
                hospital_id
            )
            .single()
            .execute()
        )

        if not response.data:
            return False

        return bool(
            response.data.get(
                "setup_completed",
                False
            )
        )

    except Exception:

        return False