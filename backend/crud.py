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
        # DEACTIVATE USER PROFILE
        # ------------------------------------------

        response = (
            admin_supabase
            .table("user_profiles")
            .update({
                "is_active": False
            })
            .eq("user_id", user_id)
            .execute()
        )

        # ------------------------------------------
        # VERIFY UPDATE
        # ------------------------------------------

        if not response.data:
            return {
                "success": False,
                "message": "User not found or could not be deactivated."
            }

        return {
            "success": True,
            "message": "User deactivated successfully."
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }

# PATIENT MANAGEMENT

def reactivate_user(user_id):

    try:

        response = (
            admin_supabase
            .table("user_profiles")
            .update({
                "is_active": True
            })
            .eq("user_id", user_id)
            .execute()
        )

        if not response.data:
            return {
                "success": False,
                "message": "User not found or could not be reactivated."
            }

        return {
            "success": True,
            "message": "User reactivated successfully."
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }

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

def create_medical_record(
    patient_id,
    record_date,
    record_type,
    facility_name,
    department=None,
    attending_physician=None,
    chief_complaint=None,
    clinical_history=None,
    diagnosis=None,
    procedure_name=None,
    findings=None,
    impression=None,
    treatment=None,
    follow_up=None,
    created_by=None
):
    try:

        data = {
            "patient_id": patient_id,
            "record_date": record_date.isoformat(),
            "record_type": record_type,
            "facility_name": facility_name,
            "department": department,
            "attending_physician": attending_physician,
            "chief_complaint": chief_complaint,
            "clinical_history": clinical_history,
            "diagnosis": diagnosis,
            "procedure_name": procedure_name,
            "findings": findings,
            "impression": impression,
            "treatment": treatment,
            "follow_up": follow_up,
            "record_status": "Completed",
            "record_source": "External",
            "created_by": created_by
        }

        response = (
            admin_supabase
            .table("medical_records")
            .insert(data)
            .execute()
        )

        if not response.data:
            return {
                "success": False,
                "message": "Medical record could not be created."
            }

        return {
            "success": True,
            "message": "Medical record created successfully.",
            "data": response.data[0]
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }

def upload_medical_record_file(
    medical_record_id,
    uploaded_file,
    image_type,
    description=None
):
    try:
        file_name = uploaded_file.name
        file_bytes = uploaded_file.getvalue()

        content_type = (
            uploaded_file.type
            or "application/octet-stream"
        )

        file_path = (
            f"{medical_record_id}/{file_name}"
        )

        # Upload file to Supabase Storage
        storage_response = (
            admin_supabase
            .storage
            .from_("external-medical-records")
            .upload(
                path=file_path,
                file=file_bytes,
                file_options={
                    "content-type": content_type
                }
            )
        )

        # Save file metadata in database
        image_data = {
            "medical_record_id": medical_record_id,
            "image_type": image_type,
            "image_url": file_path,
            "description": description
        }

        db_response = (
            admin_supabase
            .table("medical_record_images")
            .insert(image_data)
            .execute()
        )

        if not db_response.data:
            return {
                "success": False,
                "message": (
                    "File uploaded, but the "
                    "database record could not be created."
                )
            }

        return {
            "success": True,
            "message": "File uploaded successfully.",
            "data": db_response.data[0]
        }

    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }