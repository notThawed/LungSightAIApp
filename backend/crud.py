from backend.supabase_client import admin_supabase


# ==========================================
# CREATE USER
# ==========================================

def create_user(
    email,
    first_name,
    middle_name,
    last_name,
    birth_date,
    employee_id,
    role_id,
    sex,
    contact_number,
    address,
    hospital_id,
):
    try:
        # ------------------------------------------
        # 1. SEND INVITE VIA SUPABASE
        # ------------------------------------------

        invite_response = admin_supabase.auth.admin.invite_user_by_email(
            email,
            options={
                "redirect_to": "http://localhost:8501/app/static/redirect.html",
                "data": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "employee_id": employee_id,
                },
            },
        )

        if not invite_response.user:
            return {
                "success": False,
                "message": "Failed to send invitation email.",
            }

        user_id = invite_response.user.id

        # ------------------------------------------
        # 2. INSERT USER_PROFILES ROW
        # ------------------------------------------

        profile_data = {
            "user_id": user_id,
            "user_fname": first_name,
            "user_mname": middle_name,
            "user_lname": last_name,
            "user_birthdate": (
                birth_date.isoformat()
                if birth_date else None
            ),
            "employee_id": employee_id,
            "role_id": role_id,
            "user_sex": sex,
            "user_contact_number": contact_number,
            "user_address": address,
            "hospital_id": hospital_id,
            "is_active": True,
        }

        admin_supabase.table("user_profiles").insert(
            profile_data
        ).execute()

        return {
            "success": True,
            "message": f"Invitation sent to {email}",
        }

    except Exception as e:
        return {
            "success": False,
            "message": str(e),
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
    hospital_id = None,
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
            "user_address": address,
            "hospital_id": hospital_id,
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
    civil_status=None,
    occupation=None,
    nationality=None,
    religion=None,
    contact_number=None,
    address=None,
    emergency_contact_name=None,
    emergency_contact_no=None,
    created_by=None,
    hospital_id=None,          # ← NEW
):
    patient_data = {
        "first_name": first_name,
        "middle_name": middle_name,
        "last_name": last_name,
        "suffix": suffix,
        "date_of_birth": date_of_birth.isoformat(),
        "sex": sex,
        "civil_status": civil_status,
        "occupation": occupation,
        "nationality": nationality,
        "religion": religion,
        "contact_number": contact_number,
        "address": address,
        "emergency_contact_name": emergency_contact_name,
        "emergency_contact_no": emergency_contact_no,
        "created_by": created_by,
        "hospital_id": hospital_id,          # ← NEW
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
    civil_status=None,
    occupation=None,
    nationality=None,
    religion=None,
    contact_number=None,
    address=None,
    emergency_contact_name=None,
    emergency_contact_no=None,
    hospital_id=None,          # ← NEW
):
    patient_data = {
        "first_name": first_name,
        "middle_name": middle_name,
        "last_name": last_name,
        "suffix": suffix,
        "date_of_birth": date_of_birth.isoformat(),
        "sex": sex,
        "civil_status": civil_status,
        "occupation": occupation,
        "nationality": nationality,
        "religion": religion,
        "contact_number": contact_number,
        "address": address,
        "emergency_contact_name": emergency_contact_name,
        "emergency_contact_no": emergency_contact_no,
        "hospital_id": hospital_id,          # ← NEW
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
    created_by=None,
    # consent
    consent_given=False,
    consent_signed_by_name=None,
    consent_signed_by_type=None,
    consent_guardian_name=None,
    consent_guardian_relation=None,
    consent_witnessed_by=None,
    # vitals (nurse)
    bp_systolic=None,
    bp_diastolic=None,
    temperature=None,
):
    from datetime import datetime, timezone

    # ------------------------------------------
    # 1. INSERT THE EXAMINATION
    # ------------------------------------------

    examination_data = {
        "patient_id": patient_id,
        "examination_type": examination_type,
        "examination_date": examination_date.isoformat(),
        "created_by": created_by,
        "status": "Pending",
        "time_in": datetime.now(timezone.utc).isoformat(),
    }

    exam_response = (
        admin_supabase
        .table("examinations")
        .insert(examination_data)
        .execute()
    )

    if not exam_response.data:
        return None

    examination = exam_response.data[0]
    examination_id = examination["examination_id"]

    # ------------------------------------------
    # 2. INSERT CONSENT (if given)
    # ------------------------------------------

    if consent_given:

        consent_data = {
            "examination_id": examination_id,
            "consent_type": "Treatment",
            "given": True,
            "signed_by_name": consent_signed_by_name,
            "signed_by_type": consent_signed_by_type,
            "guardian_name": consent_guardian_name,
            "guardian_relation": consent_guardian_relation,
            "signed_at": datetime.now(timezone.utc).isoformat(),
            "witnessed_by": consent_witnessed_by,
        }

        admin_supabase.table("examination_consents").insert(consent_data).execute()

    # ------------------------------------------
    # 3. INSERT VITALS (if any value given)
    # ------------------------------------------

    if any([bp_systolic, bp_diastolic, temperature]):

        vitals_data = {
            "examination_id": examination_id,
            "bp_systolic": bp_systolic,
            "bp_diastolic": bp_diastolic,
            "temperature": temperature,
            "recorded_by": created_by,
            "recorded_by_role": "nurse",
        }

        admin_supabase.table("examination_vitals").insert(vitals_data).execute()

    return [examination]


def update_examination(examination_id, **fields):
    """
    Update any examination fields.
    Automatically handles timestamps and returns the updated row.
    """

    from datetime import datetime, timezone

    # Auto-fill time_of_discharge when status becomes Completed
    if fields.get("status") == "Completed":
        if "time_of_discharge" not in fields:
            fields["time_of_discharge"] = datetime.now(timezone.utc).isoformat()
        if "reviewed_at" not in fields:
            fields["reviewed_at"] = datetime.now(timezone.utc).isoformat()

    fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    response = (
        admin_supabase
        .table("examinations")
        .update(fields)
        .eq("examination_id", examination_id)
        .execute()
    )

    return response.data

def add_examination_vitals(
    examination_id,
    recorded_by,
    recorded_by_role,       # 'nurse' or 'doctor'
    bp_systolic=None,
    bp_diastolic=None,
    temperature=None,
    pulse_rate=None,
    respiratory_rate=None,
    weight_kg=None,
    height_cm=None,
    spo2=None,
    heart_rate=None,
    bmi=None,
):
    """Insert one row of vitals for an examination."""

    vitals_data = {
        "examination_id": examination_id,
        "recorded_by": recorded_by,
        "recorded_by_role": recorded_by_role,
        "bp_systolic": bp_systolic,
        "bp_diastolic": bp_diastolic,
        "temperature": temperature,
        "pulse_rate": pulse_rate,
        "respiratory_rate": respiratory_rate,
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "spo2": spo2,
        "heart_rate": heart_rate,
        "bmi": bmi,
    }

    response = (
        admin_supabase
        .table("examination_vitals")
        .insert(vitals_data)
        .execute()
    )

    return response.data

def update_examination_vitals(vitals_id, **fields):
    """Update a specific vitals row."""

    response = (
        admin_supabase
        .table("examination_vitals")
        .update(fields)
        .eq("vitals_id", vitals_id)
        .execute()
    )

    return response.data

def update_examination_consent(consent_id, **fields):
    """Update a consent row."""

    response = (
        admin_supabase
        .table("examination_consents")
        .update(fields)
        .eq("consent_id", consent_id)
        .execute()
    )

    return response.data

def cancel_examination(examination_id):
    """Soft-cancel an examination (keeps data for audit)."""
    from datetime import datetime, timezone

    response = (
        admin_supabase
        .table("examinations")
        .update({
            "status": "Cancelled",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("examination_id", examination_id)
        .execute()
    )

    return response.data


def delete_examination(examination_id):
    """Hard-delete an examination (superadmin only).
    Cascades delete consent + vitals rows via FK ON DELETE CASCADE."""

    response = (
        admin_supabase
        .table("examinations")
        .delete()
        .eq("examination_id", examination_id)
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

def create_hospital(
    hospital_name,
    address,
    hospital_code=None,
    contact_number=None,
    email=None,
    created_by=None
):
    hospital_data = {
        "hospital_name":  hospital_name,
        "hospital_code":  hospital_code,
        "address":        address,
        "contact_number": contact_number,
        "email":          email,
    }

    response = (
        admin_supabase
        .table("hospitals")
        .insert(hospital_data)
        .execute()
    )

    return response.data

def update_hospital(
    hospital_id,
    hospital_name,
    address,
    hospital_code=None,
    contact_number=None,
    email=None
):
    hospital_data = {
        "hospital_name":  hospital_name,
        "hospital_code":  hospital_code,
        "address":        address,
        "contact_number": contact_number,
        "email":          email,
    }

    response = (
        admin_supabase
        .table("hospitals")
        .update(hospital_data)
        .eq("hospital_id", hospital_id)
        .execute()
    )

    return response.data

def deactivate_hospital(hospital_id):
    response = (
        admin_supabase
        .table("hospitals")
        .update({"is_active": False})
        .eq("hospital_id", hospital_id)
        .execute()
    )

    return response.data

def reactivate_hospital(hospital_id):
    response = (
        admin_supabase
        .table("hospitals")
        .update({"is_active": True})
        .eq("hospital_id", hospital_id)
        .execute()
    )

    return response.data

def upload_consent_signature(examination_id, file_bytes):
    """
    Upload a consent signature PNG to Supabase Storage.
    Returns the storage path (used to build a signed URL later).
    """
    from datetime import datetime, timezone

    try:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        file_path = f"{examination_id}/signature_{timestamp}.png"

        admin_supabase.storage.from_("consent-signatures").upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": "image/png", "upsert": "true"},
        )

        return file_path

    except Exception as e:
        print(f"Failed to upload signature: {e}")
        return None

def create_xray_request(
    examination_id,
    hospital_id,
    requested_by,
    body_part="Chest",
    priority="Routine",
    clinical_indication=None,
):
    """Insert a new X-ray request row."""
    data = {
        "examination_id": examination_id,
        "hospital_id": hospital_id,
        "requested_by": requested_by,
        "body_part": body_part,
        "priority": priority,
        "clinical_indication": clinical_indication,
        "status": "Pending",
    }

    response = (
        admin_supabase
        .table("xray_requests")
        .insert(data)
        .execute()
    )

    return response.data[0] if response.data else None


def upload_xray_image(
    request_id,
    file_bytes,
    filename,
    uploaded_by,
):
    """Upload X-ray image to Supabase Storage + save metadata."""
    from datetime import datetime, timezone

    try:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        file_path = f"{request_id}/{timestamp}_{filename}"

        # 1. Upload to storage
        admin_supabase.storage.from_("xray-images").upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": "image/png", "upsert": "true"},
        )

        # 2. Save metadata to DB
        data = {
            "request_id": request_id,
            "image_path": file_path,
            "uploaded_by": uploaded_by,
            "quality_status": "Pending",
        }

        response = (
            admin_supabase
            .table("xray_images")
            .insert(data)
            .execute()
        )

        return response.data[0] if response.data else None

    except Exception as e:
        print(f"Failed to upload X-ray: {e}")
        return None


def update_xray_request_status(request_id, status):
    """Update the X-ray request status."""
    from datetime import datetime, timezone

    response = (
        admin_supabase
        .table("xray_requests")
        .update({
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("request_id", request_id)
        .execute()
    )

    return response.data

def save_ai_result(
    image_id,
    ai_findings,
    ai_confidence,
    ai_model_version,
):
    """
    Save an AI prediction result for an X-ray image.
    ai_findings should be the LABEL (e.g. 'positive' or 'negative').
    """
    data = {
        "image_id": image_id,
        "ai_findings": ai_findings,
        "ai_confidence": ai_confidence,
        "ai_model_version": ai_model_version,
    }

    response = (
        admin_supabase
        .table("xray_ai_results")
        .insert(data)
        .execute()
    )

    return response.data[0] if response.data else None

def update_xray_image_quality(
    image_id,
    quality_status,
    quality_checked_by,
    quality_notes=None,
):
    """
    Update the quality check fields for an X-ray image.
    quality_status should be 'Passed' or 'Failed'.
    """
    from datetime import datetime, timezone

    data = {
        "quality_status": quality_status,
        "quality_notes": quality_notes,
        "quality_checked_by": quality_checked_by,
        "quality_checked_at": datetime.now(timezone.utc).isoformat(),
    }

    response = (
        admin_supabase
        .table("xray_images")
        .update(data)
        .eq("image_id", image_id)
        .execute()
    )

    return response.data

def save_xray_review(
    request_id,
    reviewed_by,
    findings=None,
    impression=None,
):
    """
    Save the doctor's review of an X-ray.
    """
    data = {
        "request_id": request_id,
        "reviewed_by": reviewed_by,
        "findings": findings,
        "impression": impression,
    }

    response = (
        admin_supabase
        .table("xray_reviews")
        .insert(data)
        .execute()
    )

    return response.data[0] if response.data else None

# ==========================================
# MEDICATIONS
# ==========================================

def add_medication(
    examination_id,
    drug_name,
    dose=None,
    frequency=None,
    duration=None,
    notes=None,
    prescribed_by=None,
):
    """Insert a medication row."""
    data = {
        "examination_id": examination_id,
        "drug_name": drug_name,
        "dose": dose,
        "frequency": frequency,
        "duration": duration,
        "notes": notes,
        "prescribed_by": prescribed_by,
    }

    response = (
        admin_supabase
        .table("medications")
        .insert(data)
        .execute()
    )

    return response.data[0] if response.data else None


# ==========================================
# REFERRALS
# ==========================================

def add_referral(
    examination_id,
    referred_to,
    reason=None,
    urgency="Routine",
    notes=None,
    referred_by=None,
):
    """Insert a referral row."""
    data = {
        "examination_id": examination_id,
        "referred_to": referred_to,
        "reason": reason,
        "urgency": urgency,
        "notes": notes,
        "referred_by": referred_by,
    }

    response = (
        admin_supabase
        .table("referrals")
        .insert(data)
        .execute()
    )

    return response.data[0] if response.data else None


def delete_medications_by_examination(examination_id):
    """Delete all medications for an examination (for re-save)."""
    response = (
        admin_supabase
        .table("medications")
        .delete()
        .eq("examination_id", examination_id)
        .execute()
    )
    return response.data


def delete_referrals_by_examination(examination_id):
    """Delete all referrals for an examination (for re-save)."""
    response = (
        admin_supabase
        .table("referrals")
        .delete()
        .eq("examination_id", examination_id)
        .execute()
    )
    return response.data
