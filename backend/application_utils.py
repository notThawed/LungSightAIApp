from backend.supabase_client import supabase, admin_supabase
from datetime import datetime, timezone

from backend.subscription_utils import create_hospital_subscription
from backend.hospital_utils import create_hospital_admin


# ============================================================
# CREATE HOSPITAL APPLICATION
# ============================================================

def create_hospital_application(
    hospital_name,
    hospital_type,
    hospital_address,
    hospital_contact_number,
    hospital_email,
    hospital_website,
    applicant_first_name,
    applicant_middle_name,
    applicant_last_name,
    applicant_email,
    applicant_contact_number,
    applicant_position,
    selected_plan_id,
    billing_cycle,
    admin_first_name,
    admin_middle_name,
    admin_last_name,
    admin_email,
    admin_contact_number,
    agreement_accepted=False,
    application_status="Pending",   # ← NEW
    payment_status="unpaid",        # ← NEW
):
    try:

        application_data = {

            # ------------------------------------------------
            # HOSPITAL INFORMATION
            # ------------------------------------------------

            "hospital_name": hospital_name,
            "hospital_type": hospital_type,
            "hospital_address": hospital_address,
            "hospital_contact_number": hospital_contact_number,
            "hospital_email": hospital_email,
            "hospital_website": hospital_website,

            # ------------------------------------------------
            # AUTHORIZED REPRESENTATIVE
            # ------------------------------------------------

            "applicant_first_name": applicant_first_name,
            "applicant_middle_name": applicant_middle_name,
            "applicant_last_name": applicant_last_name,
            "applicant_email": applicant_email,
            "applicant_contact_number": applicant_contact_number,
            "applicant_position": applicant_position,

            # ------------------------------------------------
            # SUBSCRIPTION
            # ------------------------------------------------

            "selected_plan_id": selected_plan_id,
            "billing_cycle": billing_cycle,

            # ------------------------------------------------
            # HOSPITAL ADMINISTRATOR
            # ------------------------------------------------

            "admin_first_name": admin_first_name,
            "admin_middle_name": admin_middle_name,
            "admin_last_name": admin_last_name,
            "admin_email": admin_email,
            "admin_contact_number": admin_contact_number,

            # ------------------------------------------------
            # AGREEMENT
            # ------------------------------------------------

            "agreement_accepted": agreement_accepted,

            # Only set the timestamp when accepted
            "agreement_accepted_at": (
                datetime.now(timezone.utc).isoformat()
                if agreement_accepted
                else None
            ),

            # ------------------------------------------------
            # APPLICATION STATUS
            # ------------------------------------------------

            "application_status": application_status,
            "payment_status": payment_status,
        }

        response = (
            admin_supabase
            .table("hospital_applications")
            .insert(application_data)
            .execute()
        )

        return {
            "success": True,
            "message": "Application submitted successfully.",
            "application_id": response.data[0]["application_id"],
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e),
        }


# ============================================================
# GET ALL HOSPITAL APPLICATIONS
# ============================================================

def get_all_hospital_applications():

    try:

        response = (
            admin_supabase
            .table("hospital_applications")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        return response.data or []

    except Exception:

        return []


# ============================================================
# GET APPLICATION BY ID
# ============================================================

def get_hospital_application(application_id):

    try:

        response = (
            admin_supabase
            .table("hospital_applications")
            .select("*")
            .eq("application_id", application_id)
            .single()
            .execute()
        )

        return response.data

    except Exception:

        return None

# ============================================================
# APPROVE HOSPITAL APPLICATION
# ============================================================

# ============================================================
# APPROVE HOSPITAL APPLICATION
# ============================================================

# ============================================================
# APPROVE HOSPITAL APPLICATION
# ============================================================

def approve_hospital_application(application_id):

    try:

        # ----------------------------------------------------
        # 1. Get the application
        # ----------------------------------------------------

        application = get_hospital_application(
            application_id
        )

        if not application:

            return {
                "success": False,
                "message": "Hospital application not found."
            }

        # ----------------------------------------------------
        # 2. Make sure application is still Pending
        # ----------------------------------------------------

        if application.get(
            "application_status"
        ) != "Pending":

            return {
                "success": False,
                "message": (
                    "Only Pending applications can be approved."
                )
            }

        # ----------------------------------------------------
        # 3. Get selected subscription information
        # ----------------------------------------------------

        plan_id = application.get(
            "selected_plan_id"
        )

        billing_cycle = application.get(
            "billing_cycle"
        )

        if not plan_id:

            return {
                "success": False,
                "message": (
                    "No subscription plan was selected "
                    "for this application."
                )
            }

        if billing_cycle not in [
            "Monthly",
            "Yearly"
        ]:

            return {
                "success": False,
                "message": (
                    "Invalid billing cycle in application."
                )
            }

        # ----------------------------------------------------
        # 4. Create hospital
        # ----------------------------------------------------

        hospital_data = {

            "hospital_name":
                application.get(
                    "hospital_name"
                ),

            "hospital_type":
                application.get(
                    "hospital_type"
                ),

            "address":
                application.get(
                    "hospital_address"
                ),

            "contact_number":
                application.get(
                    "hospital_contact_number"
                ),

            "email": (
                application.get(
                    "hospital_email"
                ).strip().lower()
                if application.get(
                    "hospital_email"
                )
                else None
            ),

            "is_active":
                True,

            # Hospital has not completed
            # the setup wizard yet.
            "setup_completed":
                False,

            "setup_completed_at":
                None,
        }

        hospital_response = (
            admin_supabase
            .table("hospitals")
            .insert(hospital_data)
            .execute()
        )

        if not hospital_response.data:

            return {
                "success": False,
                "message": (
                    "Failed to create hospital."
                )
            }

        # ----------------------------------------------------
        # 5. Get newly created hospital
        # ----------------------------------------------------

        hospital = hospital_response.data[0]

        hospital_id = hospital.get(
            "hospital_id"
        )

        if not hospital_id:

            return {
                "success": False,
                "message": (
                    "Hospital was created, but the "
                    "hospital ID could not be retrieved."
                )
            }

        # ----------------------------------------------------
        # 6. Link application to hospital
        # ----------------------------------------------------

        application_update = (
            admin_supabase
            .table("hospital_applications")
            .update({

                "application_status":
                    "Approved",

                "hospital_id":
                    hospital_id

            })
            .eq(
                "application_id",
                application_id
            )
            .execute()
        )

        if not application_update.data:

            return {
                "success": False,
                "message": (
                    "Hospital was created, but the "
                    "application could not be marked "
                    "as Approved."
                ),

                "hospital_id":
                    hospital_id
            }

        # ----------------------------------------------------
        # 7. Create Hospital Subscription
        # ----------------------------------------------------
        #
        # The subscription should NOT become Active yet.
        #
        # The Hospital Admin still needs to complete
        # the setup wizard.
        #
        # Your create_hospital_subscription() function
        # should therefore create it with:
        #
        # status = "Inactive"
        #
        # or your chosen setup-pending status.
        # ----------------------------------------------------

        subscription_result = (
            create_hospital_subscription(

                hospital_id=
                    hospital_id,

                plan_id=
                    plan_id,

                billing_cycle=
                    billing_cycle,

                application_id=
                    application_id
            )
        )

        # ----------------------------------------------------
        # 8. Check subscription creation
        # ----------------------------------------------------

        if not subscription_result.get(
            "success",
            False
        ):

            return {
                "success": False,
                "message": (
                    "Hospital was created and the "
                    "application was approved, but the "
                    "subscription could not be created: "
                    f"{subscription_result.get('message', 'Unknown error')}"
                ),

                "hospital_id":
                    hospital_id
            }

        # ----------------------------------------------------
        # 9. Create Hospital Administrator
        # ----------------------------------------------------
        #
        # IMPORTANT:
        #
        # Your create_hospital_admin() function expects:
        #
        #     application
        #     hospital_id
        #
        # It already extracts:
        #
        # admin_first_name
        # admin_middle_name
        # admin_last_name
        # admin_email
        # admin_contact_number
        #
        # from the application.
        # ----------------------------------------------------

        admin_result = create_hospital_admin(
            application=application,
            hospital_id=hospital_id
        )

        # ----------------------------------------------------
        # 10. Check Hospital Administrator creation
        # ----------------------------------------------------

        if not admin_result.get(
            "success",
            False
        ):

            return {
                "success": False,
                "message": (
                    "Hospital and subscription were created, "
                    "but the Hospital Administrator account "
                    "could not be created: "
                    f"{admin_result.get('message', 'Unknown error')}"
                ),

                "hospital_id":
                    hospital_id,

                "subscription":
                    subscription_result.get(
                        "subscription"
                    )
            }

        # ----------------------------------------------------
        # 11. Get created Hospital Admin user ID
        # ----------------------------------------------------

        admin_user_id = admin_result.get(
            "user_id"
        )

        # ----------------------------------------------------
        # 12. Success
        # ----------------------------------------------------

        return {

            "success":
                True,

            "message": (
                "Application approved successfully. "
                "Hospital, subscription, and Hospital "
                "Administrator account were created."
            ),

            # ------------------------------------------------
            # Hospital
            # ------------------------------------------------

            "hospital_id":
                hospital_id,

            "hospital":
                hospital,

            # ------------------------------------------------
            # Subscription
            # ------------------------------------------------

            "subscription":
                subscription_result.get(
                    "subscription"
                ),

            # ------------------------------------------------
            # Hospital Administrator
            # ------------------------------------------------

            "admin_user_id":
                admin_user_id,

            "admin":
                admin_result.get(
                    "profile"
                ),

        }

    except Exception as e:

        return {

            "success":
                False,

            "message":
                str(e)
        }


# ============================================================
# REJECT HOSPITAL APPLICATION
# ============================================================

def reject_hospital_application(application_id):

    try:

        response = (
            admin_supabase
            .table("hospital_applications")
            .update({
                "application_status": "Rejected"
            })
            .eq(
                "application_id",
                application_id
            )
            .execute()
        )

        return {
            "success": True,
            "message": "Hospital application rejected successfully.",
            "data": response.data,
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e),
        }


# ============================================================
# DELETE REJECTED APPLICATION
# ============================================================

def delete_hospital_application(application_id):

    try:

        response = (
            admin_supabase
            .table("hospital_applications")
            .delete()
            .eq(
                "application_id",
                application_id
            )
            .eq(
                "application_status",
                "Rejected"
            )
            .execute()
        )

        return {
            "success": True,
            "message": "Rejected application deleted successfully.",
            "data": response.data,
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e),
        }


