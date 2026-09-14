from backend.supabase_client import admin_supabase


# ==========================================
# CREATE USER
# ==========================================

def create_user(
    email,
    password,
    first_name,
    middle_name,
    last_name,
    birth_date,
    employee_id,
    role_id,
    sex,
    contact_number,
    address,
):
    auth_user = None

    try:
        # ------------------------------------------
        # CREATE SUPABASE AUTH ACCOUNT
        # ------------------------------------------

        auth_response = (
            admin_supabase.auth.admin.create_user(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True
                }
            )
        )

        auth_user = auth_response.user

        if not auth_user:
            raise Exception(
                "Failed to create Auth account."
            )

        user_id = auth_user.id

        # ------------------------------------------
        # CREATE USER PROFILE
        # ------------------------------------------

        profile_data = {
            "user_id": user_id,
            "employee_id": employee_id,
            "user_fname": first_name,
            "user_mname": middle_name,
            "user_lname": last_name,
            "user_birthdate": (
                birth_date.isoformat()
                if birth_date
                else None
            ),
            "user_sex": sex,
            "user_contact_number": contact_number,
            "user_address": address,
            "role_id": role_id,
            "is_active": True
        }

        profile_response = (
            admin_supabase
            .table("user_profiles")
            .insert(profile_data)
            .execute()
        )

        return {
            "success": True,
            "user_id": user_id,
            "email": email,
            "data": profile_response.data
        }

    except Exception as e:

        # ------------------------------------------
        # ROLLBACK AUTH ACCOUNT
        # ------------------------------------------

        if auth_user:

            try:
                admin_supabase.auth.admin.delete_user(
                    auth_user.id
                )

            except Exception as rollback_error:

                print(
                    "Failed to rollback Auth user:",
                    rollback_error
                )

        return {
            "success": False,
            "message": str(e)
        }


# ==========================================
# UPDATE USER
# ==========================================

def update_user(
    user_id,
    email,
    password,
    first_name,
    middle_name,
    last_name,
    birth_date,
    role_id,
    sex,
    contact_number,
    address,
):

    try:

        # ------------------------------------------
        # UPDATE AUTH ACCOUNT
        # ------------------------------------------

        auth_updates = {}

        if email:
            auth_updates["email"] = email

        if password:
            auth_updates["password"] = password

        if auth_updates:

            admin_supabase.auth.admin.update_user_by_id(
                user_id,
                auth_updates
            )

        # ------------------------------------------
        # UPDATE USER PROFILE
        # ------------------------------------------

        update_data = {
            "user_fname": first_name,
            "user_mname": middle_name,
            "user_lname": last_name,
            "user_birthdate": (
                birth_date.isoformat()
                if birth_date
                else None
            ),
            "role_id": role_id,
            "user_sex": sex,
            "user_contact_number": contact_number,
            "user_address": address
        }

        response = (
            admin_supabase
            .table("user_profiles")
            .update(update_data)
            .eq("user_id", user_id)
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


# ==========================================
# DELETE USER
# ==========================================

def delete_user(user_id):

    try:

        # ------------------------------------------
        # DELETE AUTH USER
        # ------------------------------------------

        admin_supabase.auth.admin.delete_user(
            user_id
        )

        # ------------------------------------------
        # DELETE PROFILE
        # ------------------------------------------

        (
            admin_supabase
            .table("user_profiles")
            .delete()
            .eq("user_id", user_id)
            .execute()
        )

        return {
            "success": True,
            "message": "User deleted successfully."
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }

# PATIENT MANAGEMENT


def create_patient(
    first_name,
    middle_name,
    last_name,
    suffix,
    date_of_birth,
    sex,
    contact_number,
    address,
    emergency_contact_name,
    emergency_contact_no,
    created_by=None
):
    patient_data = {
        "first_name": first_name,
        "middle_name": middle_name,
        "last_name": last_name,
        "suffix": suffix,
        "date_of_birth": date_of_birth.isoformat(),
        "sex": sex,
        "contact_number": contact_number,
        "address": address,
        "emergency_contact_name": emergency_contact_name,
        "emergency_contact_no": emergency_contact_no,
        "created_by": created_by
    }

    response = (
        admin_supabase
        .table("patients")
        .insert(patient_data)
        .execute()
    )

    return response.data

def update_patient(
    patient_id,
    first_name,
    middle_name,
    last_name,
    suffix,
    date_of_birth,
    sex,
    contact_number,
    address,
    emergency_contact_name,
    emergency_contact_no
):
    patient_data = {
        "first_name": first_name,
        "middle_name": middle_name,
        "last_name": last_name,
        "suffix": suffix,
        "date_of_birth": date_of_birth.isoformat(),
        "sex": sex,
        "contact_number": contact_number,
        "address": address,
        "emergency_contact_name": emergency_contact_name,
        "emergency_contact_no": emergency_contact_no
    }

    response = (
        admin_supabase
        .table("patients")
        .update(patient_data)
        .eq("patient_id", patient_id)
        .execute()
    )

    return response.data


def delete_patient(patient_id):
    response = (
        admin_supabase
        .table("patients")
        .delete()
        .eq("patient_id", patient_id)
        .execute()
    )

    return response.data

def create_examination(
    patient_id,
    examination_type,
    examination_date,
    clinical_notes=None,
    created_by=None
):
    examination_data = {
        "patient_id": patient_id,
        "examination_type": examination_type,
        "examination_date": examination_date.isoformat(),
        "clinical_notes": clinical_notes,
        "created_by": created_by
    }

    response = (
        admin_supabase
        .table("examinations")
        .insert(examination_data)
        .execute()
    )

    return response.data


def update_examination_clinical_notes(
    examination_id,
    clinical_notes
):
    """
    Update the clinical notes of an examination.
    """

    response = (
        admin_supabase
        .table("examinations")
        .update({
            "clinical_notes": clinical_notes
        })
        .eq(
            "examination_id",
            examination_id
        )
        .execute()
    )

    return response.data