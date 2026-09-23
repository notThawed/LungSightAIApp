from backend.supabase_client import supabase, admin_supabase

from datetime import datetime
from zoneinfo import ZoneInfo

MANILA_TZ = ZoneInfo("Asia/Manila")


# ==========================================
# CONVERT TIMESTAMP TO PHILIPPINE TIME
# ==========================================

def convert_to_manila_time(timestamp):
    """
    Convert Supabase Auth timestamp to Philippine Standard Time.
    """

    if not timestamp:
        return None

    try:

        # Supabase may already return a datetime object
        if isinstance(timestamp, datetime):

            # If the datetime has no timezone,
            # assume it is UTC
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(
                    tzinfo=ZoneInfo("UTC")
                )

            return timestamp.astimezone(
                MANILA_TZ
            )

        # If Supabase returns a string instead
        if isinstance(timestamp, str):

            timestamp = timestamp.replace(
                "Z",
                "+00:00"
            )

            dt = datetime.fromisoformat(
                timestamp
            )

            return dt.astimezone(
                MANILA_TZ
            )

    except Exception as e:

        print(
            f"Failed to convert timestamp: {e}"
        )

    return timestamp


# ==========================================
# GET ALL AUTH USERS IN ONE REQUEST   (NEW)
# The old code asked Supabase Auth once PER USER.
# ==========================================

def get_auth_users_by_id():
    """Returns {user_id: auth_user} using as few requests as possible."""

    users_by_id = {}
    per_page = 1000
    page = 1

    while True:

        response = admin_supabase.auth.admin.list_users(
            page=page,
            per_page=per_page
        )

        # Depending on the supabase version this is a list, or an object with .users
        batch = (
            response
            if isinstance(response, list)
            else getattr(response, "users", None) or []
        )

        for auth_user in batch:
            users_by_id[str(auth_user.id)] = auth_user

        if len(batch) < per_page:
            break

        page += 1

    return users_by_id


# ==========================================
# USER PROFILES - database only, no Auth calls
# ==========================================

def _fetch_profiles():

    response = (
        admin_supabase
        .table("user_profiles")
        .select("""
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
            is_active,
            created_at,
            updated_at,
            hospital_id,

            roles (
                role_name
            ),

            hospitals (
                hospital_id,
                hospital_name,
                hospital_code
                )
        """)
        .order("user_lname")
        .execute()
    )

    return response.data or []


# ==========================================
# GET ALL USERS - one Auth request instead of one per user)
# ==========================================

def get_all_users():

    users = _fetch_profiles()

    # ------------------------------------------
    # GET AUTH INFORMATION (ONE request for everyone)
    # ------------------------------------------

    try:
        auth_by_id = get_auth_users_by_id()
    except Exception as e:
        print(f"Failed to fetch auth information: {e}")
        auth_by_id = {}

    for user in users:

        auth_user = auth_by_id.get(str(user["user_id"]))

        # EMAIL
        user["email"] = (
            (auth_user.email or "")
            if auth_user
            else ""
        )

        # LAST LOGIN
        user["last_login"] = (
            convert_to_manila_time(auth_user.last_sign_in_at)
            if auth_user
            else None
        )

    return users


# ==========================================
# GET ALL ROLES
# ==========================================

def get_all_roles():

    response = (
        supabase
        .table("roles")
        .select(
            "role_id, role_name"
        )
        .order("role_id")
        .execute()
    )

    return response.data or []


# ==========================================
# GENERATE EMPLOYEE ID
# ==========================================

def generate_employee_id():

    current_year = datetime.now().year

    prefix = f"EMP-{current_year}-"

    response = (
        admin_supabase
        .table("user_profiles")
        .select("employee_id")
        .like("employee_id", f"{prefix}%")
        .execute()
    )

    rows = response.data or []

    highest = 0

    for row in rows:

        emp_id = row.get("employee_id") or ""

        if not emp_id.startswith(prefix):
            continue

        try:
            number = int(emp_id[len(prefix):])
        except ValueError:
            continue

        if number > highest:
            highest = number

    return f"{prefix}{highest + 1:03d}"


# ==========================================
# GET SINGLE USER
# ==========================================

def get_user(user_id):

    # ------------------------------------------
    # GET PROFILE
    # ------------------------------------------

    profile_response = (
        admin_supabase
        .table("user_profiles")
        .select("""
            *,
            roles (
                role_id,
                role_name
            ),
            hospitals (
                hospital_id,
                hospital_name,
                hospital_code
            )
        """)
        .eq("user_id", user_id)
        .limit(1)          # ← was .single()
        .execute()
    )

    rows = profile_response.data or []

    if not rows:
        return None

    profile = rows[0]      # ← now we pull the first row ourselves

    # ------------------------------------------
    # DEFAULT AUTH VALUES
    # ------------------------------------------

    profile["email"] = ""
    profile["last_login"] = None

    # ------------------------------------------
    # GET AUTH USER
    # ------------------------------------------

    try:

        auth_response = (
            admin_supabase
            .auth
            .admin
            .get_user_by_id(user_id)
        )

        if auth_response.user:

            # EMAIL
            profile["email"] = (
                auth_response.user.email
                or ""
            )

            # LAST LOGIN
            profile["last_login"] = (
                convert_to_manila_time(
                    auth_response.user.last_sign_in_at
                )
            )

    except Exception as e:

        print(f"Failed to fetch auth user: {e}")

    return profile


# ==========================================
# GET USER COUNTS   (CHANGED: no Auth requests at all)
# ==========================================

def get_user_counts():

    users = _fetch_profiles()

    total_staff = 0
    radiologist_count = 0
    radiologic_technologist_count = 0

    for user in users:

        role_data = user.get("roles")

        if not role_data:
            continue

        role_name = role_data.get(
            "role_name"
        )

        if role_name == "Radiologist":

            radiologist_count += 1
            total_staff += 1

        elif role_name == "Radiologic Technologist":

            radiologic_technologist_count += 1
            total_staff += 1

        elif role_name == "Staff":

            total_staff += 1

    return {

        "total_staff": total_staff,

        "radiologist":
            radiologist_count,

        "radiologic_technologist":
            radiologic_technologist_count,

        "total_patients":
            0
    }

# GET ALL PATIENTS

def get_all_patients():
    response = (
        admin_supabase
        .table("patients")
        .select(
            """
            patient_id,
            patient_code,
            first_name,
            middle_name,
            last_name,
            suffix,
            date_of_birth,
            sex,
            civil_status,
            occupation,
            nationality,
            religion,
            contact_number,
            address,
            emergency_contact_name,
            emergency_contact_no,
            status,
            created_at,
            hospital_id,
            hospitals (
                hospital_id,
                hospital_name
            )
            """
        )
        .order("last_name", desc=False)
        .order("first_name", desc=False)
        .execute()
    )

    return response.data

def generate_patient_id():

    current_year = datetime.now().year
    response = (
        supabase
        .table("patients")
        .select("patient_code")
        .like(
            "patient_code",
            f"LSP-{current_year}-%"
        )
        .order(
            "patient_code",
            desc=True
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        return (
            f"LSP-{current_year}-001"
        )
    last_id = response.data[0].get(
        "patient_code"
    )

    if not last_id:

        return (
            f"LSP-{current_year}-001"
        )
    try:
        number = int(
            last_id.split("-")[-1]
        )

    except (
        ValueError,
        TypeError
    ): number = 0

    return(
        f"LSP-{current_year}-{number + 1:03d}"
    )


def get_examinations_by_patient(patient_id):

    response = (
        supabase
        .table("examinations")
        .select("""
            examination_id,
            patient_id,
            examination_type,
            examination_date,
            history_of_present_illness,
            chief_complaint,
            physical_examination,
            diagnosis,
            plans_orders,
            time_in,
            disposition,
            disposition_notes,
            time_of_discharge,
            status,
            created_by,
            reviewed_by,
            reviewed_at,
            created_at,
            updated_at
        """)
        .eq("patient_id", patient_id)
        .order("examination_date", desc=True)
        .execute()
    )

    return response.data or []

def get_examination_consents(examination_id):
    """Get all consent rows for an examination."""
    try:
        response = (
            admin_supabase
            .table("examination_consents")
            .select("*")
            .eq("examination_id", examination_id)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []
    except Exception as e:
        print(f"Error fetching consents: {e}")
        return []


def get_examination_vitals(examination_id):
    """Get all vitals rows for an examination, newest first."""
    try:
        response = (
            admin_supabase
            .table("examination_vitals")
            .select("*")
            .eq("examination_id", examination_id)
            .order("recorded_at", desc=True)
            .execute()
        )
        return response.data or []
    except Exception as e:
        print(f"Error fetching vitals: {e}")
        return []


def get_medical_records_by_patient(patient_id):
    try:
        response = (
            admin_supabase
            .table("medical_records")
            .select("*")
            .eq("patient_id", patient_id)
            .order("record_date", desc=True)
            .execute()
        )

        print("MEDICAL RECORD FETCH RESPONSE:", response.data)

        return response.data or []

    except Exception as e:
        print(f"Error fetching medical records: {e}")
        return []

def get_medical_record_images(medical_record_id):
    try:
        response = (
            admin_supabase
            .table("medical_record_images")
            .select("*")
            .eq(
                "medical_record_id",
                medical_record_id
            )
            .order("uploaded_at", desc=False)
            .execute()
        )

        return response.data or []

    except Exception as e:
        print(
            f"Error fetching medical record images: {e}"
        )
        return []

def get_medical_record_file_url(file_path):
    try:
        response = (
            admin_supabase
            .storage
            .from_("external-medical-records")
            .create_signed_url(
                file_path,
                3600
            )
        )

        return response.get("signedURL")

    except Exception as e:
        print(
            f"Error creating signed URL: {e}"
        )
        return None

def get_all_hospitals():
    response = (
        admin_supabase
        .table("hospitals")
        .select("*")
        .order("hospital_name")
        .execute()
    )
    return response.data or []

# Below are some functions for the Hospital Management
# 1.) Get a hospital Staff. - Who Belongs to this Hospital [ get_hospital_staff Function ]
# 2.) Get one hospital Staff Member - Self explanatory [ get_hospital_staff_member Function ]


# ==========================================
# GET HOSPITAL STAFF
# ==========================================

def get_hospital_staff(
    hospital_id,
    active_only=False,
):
    """
    Get all staff assigned to a hospital.

    Profile information comes from user_profiles.
    Email and last login come from Supabase Auth.
    """

    if not hospital_id:
        return []

    query = (
        admin_supabase
        .table("user_profiles")
        .select("""
            user_id,
            employee_id,
            user_fname,
            user_mname,
            user_lname,
            user_birthdate,
            user_sex,
            user_contact_number,
            user_address,
            user_department,
            role_id,
            is_active,
            created_at,
            updated_at,
            hospital_id,
            profile_picture_url,

            roles (
                role_id,
                role_name
            ),

            hospitals (
                hospital_id,
                hospital_name,
                hospital_code
            )
        """)
        .eq(
            "hospital_id",
            hospital_id,
        )
        .order(
            "user_lname"
        )
    )

    if active_only:

        query = query.eq(
            "is_active",
            True,
        )

    response = query.execute()

    staff = response.data or []

    if not staff:
        return []

    # ------------------------------------------------------
    # GET SUPABASE AUTH USERS
    # ------------------------------------------------------
    #
    # Email and last login belong to Supabase Auth.
    # We fetch Auth users once instead of making one request
    # for every staff member.
    # ------------------------------------------------------

    try:

        auth_by_id = get_auth_users_by_id()

    except Exception as exc:

        print(
            f"Failed to fetch Auth users for hospital staff: {exc}"
        )

        auth_by_id = {}

    # ------------------------------------------------------
    # MERGE AUTH DATA INTO USER PROFILE DATA
    # ------------------------------------------------------

    for member in staff:

        user_id = str(
            member.get("user_id")
            or ""
        )

        auth_user = auth_by_id.get(
            user_id
        )

        # Default values
        member["email"] = ""
        member["last_login"] = None

        if auth_user:

            member["email"] = (
                getattr(
                    auth_user,
                    "email",
                    None,
                )
                or ""
            )

            member["last_login"] = (
                convert_to_manila_time(
                    getattr(
                        auth_user,
                        "last_sign_in_at",
                        None,
                    )
                )
            )

    return staff


# ==========================================
# GET SINGLE HOSPITAL STAFF MEMBER
# ==========================================

def get_hospital_staff_member(user_id):
    """
    Get one hospital staff member.

    Profile information comes from user_profiles.
    Email and last login come from Supabase Auth.
    """

    if not user_id:
        return None

    response = (
        admin_supabase
        .table("user_profiles")
        .select("""
            user_id,
            employee_id,
            user_fname,
            user_mname,
            user_lname,
            user_birthdate,
            user_sex,
            user_contact_number,
            user_address,
            user_department,
            role_id,
            is_active,
            created_at,
            updated_at,
            hospital_id,
            profile_picture_url,

            roles (
                role_id,
                role_name
            ),

            hospitals (
                hospital_id,
                hospital_name,
                hospital_code
            )
        """)
        .eq(
            "user_id",
            user_id,
        )
        .limit(1)
        .execute()
    )

    rows = response.data or []

    if not rows:
        return None

    member = rows[0]

    # ------------------------------------------------------
    # DEFAULT AUTH VALUES
    # ------------------------------------------------------

    member["email"] = ""
    member["last_login"] = None

    # ------------------------------------------------------
    # GET AUTH USER
    # ------------------------------------------------------

    try:

        auth_response = (
            admin_supabase
            .auth
            .admin
            .get_user_by_id(
                user_id
            )
        )

        auth_user = getattr(
            auth_response,
            "user",
            None,
        )

        if auth_user:

            member["email"] = (
                getattr(
                    auth_user,
                    "email",
                    None,
                )
                or ""
            )

            member["last_login"] = (
                convert_to_manila_time(
                    getattr(
                        auth_user,
                        "last_sign_in_at",
                        None,
                    )
                )
            )

    except Exception as exc:

        print(
            f"Failed to fetch Auth information "
            f"for staff member {user_id}: {exc}"
        )

    return member

def get_user_hospital_status(user_id):

    if not user_id:
        return None

    try:

        response = (
            admin_supabase
            .table("user_profiles")
            .select("""
                user_id,
                hospital_id,
                hospitals (
                    hospital_id,
                    hospital_name,
                    is_active
                )
            """)
            .eq(
                "user_id",
                user_id
            )
            .limit(1)
            .execute()
        )

        rows = response.data or []

        if not rows:
            return None

        profile = rows[0]

        hospital = profile.get(
            "hospitals"
        )

        if isinstance(hospital, list):

            hospital = (
                hospital[0]
                if hospital
                else None
            )

        if not hospital:

            return None

        return {
            "hospital_id": hospital.get(
                "hospital_id"
            ),
            "hospital_name": hospital.get(
                "hospital_name"
            ),
            "is_active": hospital.get(
                "is_active",
                True,
            ),
        }

    except Exception as exc:

        print(
            f"Failed to check hospital status: {exc}"
        )

        return None

def get_consent_signature_url(signature_path):
    """Return a signed URL for a consent signature (1 hour valid)."""
    if not signature_path:
        return None

    try:
        response = (
            admin_supabase
            .storage
            .from_("consent-signatures")
            .create_signed_url(signature_path, 3600)
        )
        return response.get("signedURL")

    except Exception as e:
        print(f"Failed to create signed URL for signature: {e}")
        return None

def get_pending_examinations(hospital_id=None):
    """
    Get all pending examinations with patient info.
    If hospital_id is None, returns pending exams from ALL hospitals.
    """

    query = (
        admin_supabase
        .table("examinations")
        .select("""
            examination_id,
            patient_id,
            examination_type,
            examination_date,
            status,
            created_by,
            created_at,
            patients!inner (
                patient_id,
                patient_code,
                first_name,
                middle_name,
                last_name,
                suffix,
                date_of_birth,
                sex,
                contact_number,
                hospital_id,
                hospitals (
                    hospital_id,
                    hospital_name
                )
            )
        """)
        .eq("status", "Pending")
        .order("created_at", desc=False)
    )

    if hospital_id:
        query = query.eq("patients.hospital_id", hospital_id)

    response = query.execute()
    return response.data or []

def get_pending_xray_examinations(hospital_id=None):
    """
    Get all examinations with status = 'Awaiting X-Ray'.
    """
    query = (
        admin_supabase
        .table("examinations")
        .select("""
            examination_id,
            patient_id,
            examination_type,
            examination_date,
            status,
            created_by,
            created_at,
            chief_complaint,
            physical_examination,
            patients!inner (
                patient_id,
                patient_code,
                first_name,
                middle_name,
                last_name,
                suffix,
                date_of_birth,
                sex,
                contact_number,
                hospital_id,
                hospitals (
                    hospital_id,
                    hospital_name
                )
            )
        """)
        .eq("status", "Awaiting X-Ray")
        .order("created_at", desc=False)
    )

    if hospital_id:
        query = query.eq("patients.hospital_id", hospital_id)

    response = query.execute()
    return response.data or []

def get_xray_request_by_examination(examination_id):
    """Get the X-ray request for an examination."""
    try:
        response = (
            admin_supabase
            .table("xray_requests")
            .select("*")
            .eq("examination_id", examination_id)
            .order("requested_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None
    except Exception as e:
        print(f"Error fetching xray request: {e}")
        return None

def get_xray_images_by_request(request_id):
    """Get all X-ray images for a request."""
    try:
        response = (
            admin_supabase
            .table("xray_images")
            .select("*")
            .eq("request_id", request_id)
            .order("uploaded_at", desc=True)
            .execute()
        )
        return response.data or []
    except Exception as e:
        print(f"Error fetching xray images: {e}")
        return []


def get_xray_image_url(image_path):
    """Get a signed URL for an X-ray image (1 hour)."""
    if not image_path:
        return None
    try:
        response = (
            admin_supabase
            .storage
            .from_("xray-images")
            .create_signed_url(image_path, 3600)
        )
        return response.get("signedURL")
    except Exception as e:
        print(f"Error creating X-ray signed URL: {e}")
        return None

def get_xray_ai_result(image_id):
    """Get the AI result for an X-ray image."""
    try:
        response = (
            admin_supabase
            .table("xray_ai_results")
            .select("*")
            .eq("image_id", image_id)
            .order("processed_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None
    except Exception as e:
        print(f"Error fetching AI result: {e}")
        return None

def get_xray_review(request_id):
    """Get the doctor's review for an X-ray request (if any)."""
    try:
        response = (
            admin_supabase
            .table("xray_reviews")
            .select("*")
            .eq("request_id", request_id)
            .order("reviewed_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None
    except Exception as e:
        print(f"Error fetching X-ray review: {e}")
        return None

def get_xray_ready_examinations(hospital_id=None):
    """
    Get all examinations with status = 'X-Ray Ready'.
    """
    query = (
        admin_supabase
        .table("examinations")
        .select("""
            examination_id,
            patient_id,
            examination_type,
            examination_date,
            status,
            created_by,
            created_at,
            chief_complaint,
            physical_examination,
            patients!inner (
                patient_id,
                patient_code,
                first_name,
                middle_name,
                last_name,
                suffix,
                date_of_birth,
                sex,
                contact_number,
                hospital_id,
                hospitals (
                    hospital_id,
                    hospital_name
                )
            )
        """)
        .eq("status", "X-Ray Ready")
        .order("created_at", desc=False)
    )

    if hospital_id:
        query = query.eq("patients.hospital_id", hospital_id)

    response = query.execute()
    return response.data or []

def get_medications_by_examination(examination_id):
    """Get all medications for an examination."""
    try:
        response = (
            admin_supabase
            .table("medications")
            .select("*")
            .eq("examination_id", examination_id)
            .order("prescribed_at", desc=False)
            .execute()
        )
        return response.data or []
    except Exception as e:
        print(f"Error fetching medications: {e}")
        return []


def get_referral_by_examination(examination_id):
    """Get the referral for an examination (if any)."""
    try:
        response = (
            admin_supabase
            .table("referrals")
            .select("*")
            .eq("examination_id", examination_id)
            .order("referred_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None
    except Exception as e:
        print(f"Error fetching referral: {e}")
        return None 