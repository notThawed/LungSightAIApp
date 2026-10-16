from datetime import datetime
from zoneinfo import ZoneInfo

from backend.supabase_client import (
    supabase,
    admin_supabase,
)


# ==========================================
# TIMEZONE
# ==========================================

MANILA_TZ = ZoneInfo("Asia/Manila")
UTC_TZ = ZoneInfo("UTC")


# ==========================================
# CONVERT TIMESTAMP TO PHILIPPINE TIME
# ==========================================

def convert_to_manila_time(timestamp):
    """
    Convert a Supabase timestamp to Philippine Standard Time.

    Supports:
    - datetime objects
    - ISO timestamp strings
    """

    if not timestamp:
        return None

    try:
        if isinstance(timestamp, datetime):

            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(
                    tzinfo=UTC_TZ
                )

            return timestamp.astimezone(
                MANILA_TZ
            )

        if isinstance(timestamp, str):

            timestamp = timestamp.replace(
                "Z",
                "+00:00"
            )

            dt = datetime.fromisoformat(
                timestamp
            )

            if dt.tzinfo is None:
                dt = dt.replace(
                    tzinfo=UTC_TZ
                )

            return dt.astimezone(
                MANILA_TZ
            )

    except Exception as exc:
        print(
            f"Failed to convert timestamp: {exc}"
        )

    return timestamp


# ==========================================
# GET ALL AUTH USERS
# ==========================================

def get_auth_users_by_id():
    """
    Get all Supabase Auth users and return them
    as:

        {
            "user_uuid": auth_user
        }

    Uses pagination instead of making one Auth
    request for every user.
    """

    users_by_id = {}

    per_page = 1000
    page = 1

    while True:

        response = (
            admin_supabase
            .auth
            .admin
            .list_users(
                page=page,
                per_page=per_page,
            )
        )

        if isinstance(response, list):
            batch = response

        else:
            batch = (
                getattr(
                    response,
                    "users",
                    None,
                )
                or []
            )

        for auth_user in batch:

            user_id = getattr(
                auth_user,
                "id",
                None,
            )

            if user_id:
                users_by_id[str(user_id)] = (
                    auth_user
                )

        if len(batch) < per_page:
            break

        page += 1

    return users_by_id


# ==========================================
# USER PROFILES
# ==========================================

def _fetch_profiles():
    """
    Fetch user profiles from the database.

    Email and last-login information are intentionally
    not fetched here because those belong to Supabase Auth.
    """

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
        .order(
            "user_lname",
            desc=False,
        )
        .execute()
    )

    return response.data or []


# ==========================================
# GET ALL USERS
# ==========================================

def get_all_users():
    """
    Get all users.

    Database information comes from user_profiles.
    Email and last login come from Supabase Auth.
    """

    users = _fetch_profiles()

    try:
        auth_by_id = get_auth_users_by_id()

    except Exception as exc:

        print(
            f"Failed to fetch Auth users: {exc}"
        )

        auth_by_id = {}

    for user in users:

        user_id = str(
            user.get("user_id") or ""
        )

        auth_user = auth_by_id.get(
            user_id
        )

        user["email"] = ""
        user["last_login"] = None

        if auth_user:

            user["email"] = (
                getattr(
                    auth_user,
                    "email",
                    None,
                )
                or ""
            )

            user["last_login"] = (
                convert_to_manila_time(
                    getattr(
                        auth_user,
                        "last_sign_in_at",
                        None,
                    )
                )
            )

    return users


# ==========================================
# GET ALL ROLES
# ==========================================

def get_all_roles():

    response = (
        admin_supabase
        .table("roles")
        .select(
            "role_id, role_name"
        )
        .order(
            "role_id",
            desc=False,
        )
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
        .like(
            "employee_id",
            f"{prefix}%",
        )
        .execute()
    )

    rows = response.data or []

    highest = 0

    for row in rows:

        employee_id = (
            row.get("employee_id")
            or ""
        )

        if not employee_id.startswith(
            prefix
        ):
            continue

        try:
            number = int(
                employee_id[
                    len(prefix):
                ]
            )

        except (
            ValueError,
            TypeError,
        ):
            continue

        highest = max(
            highest,
            number,
        )

    return (
        f"{prefix}"
        f"{highest + 1:03d}"
    )


# ==========================================
# GET SINGLE USER
# ==========================================

def get_user(user_id):

    if not user_id:
        return None

    response = (
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

    profile = rows[0]

    profile["email"] = ""
    profile["last_login"] = None

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

            profile["email"] = (
                getattr(
                    auth_user,
                    "email",
                    None,
                )
                or ""
            )

            profile["last_login"] = (
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
            f"Failed to fetch Auth user: {exc}"
        )

    return profile


# ==========================================
# GET USER COUNTS
# ==========================================

def get_user_counts():

    users = _fetch_profiles()

    total_staff = 0
    radiologist_count = 0
    radiologic_technologist_count = 0

    for user in users:

        role_data = user.get("roles")

        if isinstance(
            role_data,
            list,
        ):
            role_data = (
                role_data[0]
                if role_data
                else None
            )

        if not role_data:
            continue

        role_name = role_data.get(
            "role_name"
        )

        if role_name == "Radiologist":

            radiologist_count += 1
            total_staff += 1

        elif role_name == (
            "Radiologic Technologist"
        ):

            radiologic_technologist_count += 1
            total_staff += 1

        elif role_name == "Staff":

            total_staff += 1

    return {
        "total_staff": total_staff,
        "radiologist": radiologist_count,
        "radiologic_technologist": (
            radiologic_technologist_count
        ),
        "total_patients": 0,
    }


# ==========================================
# PATIENTS
# ==========================================

def get_all_patients():

    response = (
        admin_supabase
        .table("patients")
        .select("""
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
            created_by,
            updated_at,
            hospital_id,

            hospitals (
                hospital_id,
                hospital_name,
                hospital_code
            )
        """)
        .order(
            "last_name",
            desc=False,
        )
        .order(
            "first_name",
            desc=False,
        )
        .execute()
    )

    return response.data or []


def generate_patient_id():

    current_year = datetime.now().year

    prefix = f"LSP-{current_year}-"

    response = (
        admin_supabase
        .table("patients")
        .select("patient_code")
        .like(
            "patient_code",
            f"{prefix}%",
        )
        .order(
            "patient_code",
            desc=True,
        )
        .limit(1)
        .execute()
    )

    rows = response.data or []

    if not rows:
        return f"{prefix}001"

    last_id = (
        rows[0].get("patient_code")
        or ""
    )

    if not last_id.startswith(prefix):
        return f"{prefix}001"

    try:

        number = int(
            last_id.split("-")[-1]
        )

    except (
        ValueError,
        TypeError,
    ):

        number = 0

    return (
        f"{prefix}"
        f"{number + 1:03d}"
    )


# ==========================================
# EXAMINATIONS
# ==========================================

def get_examinations_by_patient(patient_id):
    if not patient_id:
        return []

    response = (
        admin_supabase
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
            follow_up_date,
            follow_up_notes,
            follow_up_sequence,
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



# ==========================================
# CONSENTS
# ==========================================

def get_examination_consents(
    examination_id,
):

    if not examination_id:
        return []

    try:

        response = (
            admin_supabase
            .table("examination_consents")
            .select("*")
            .eq(
                "examination_id",
                examination_id,
            )
            .order(
                "created_at",
                desc=True,
            )
            .execute()
        )

        return response.data or []

    except Exception as exc:

        print(
            f"Error fetching consents: {exc}"
        )

        return []


# ==========================================
# VITALS
# ==========================================

def get_examination_vitals(
    examination_id,
):

    if not examination_id:
        return []

    try:

        response = (
            admin_supabase
            .table("examination_vitals")
            .select("*")
            .eq(
                "examination_id",
                examination_id,
            )
            .order(
                "recorded_at",
                desc=True,
            )
            .execute()
        )

        return response.data or []

    except Exception as exc:

        print(
            f"Error fetching vitals: {exc}"
        )

        return []


# ==========================================
# EXTERNAL MEDICAL RECORDS
# ==========================================

def get_medical_records_by_patient(
    patient_id,
):

    if not patient_id:
        return []

    try:

        response = (
            admin_supabase
            .table("medical_records")
            .select("*")
            .eq(
                "patient_id",
                patient_id,
            )
            .order(
                "record_date",
                desc=True,
            )
            .execute()
        )

        return response.data or []

    except Exception as exc:

        print(
            "Error fetching medical records "
            f"for patient {patient_id}: {exc}"
        )

        return []


def get_medical_record_images(
    medical_record_id,
):

    if not medical_record_id:
        return []

    try:

        response = (
            admin_supabase
            .table("medical_record_images")
            .select("*")
            .eq(
                "medical_record_id",
                medical_record_id,
            )
            .order(
                "uploaded_at",
                desc=False,
            )
            .execute()
        )

        return response.data or []

    except Exception as exc:

        print(
            "Error fetching medical record images: "
            f"{exc}"
        )

        return []


def get_medical_record_file_url(
    file_path,
):

    if not file_path:
        return None

    try:

        response = (
            admin_supabase
            .storage
            .from_("external-medical-records")
            .create_signed_url(
                file_path,
                3600,
            )
        )

        return response.get(
            "signedURL"
        )

    except Exception as exc:

        print(
            "Error creating medical record "
            f"signed URL: {exc}"
        )

        return None


# ==========================================
# HOSPITALS
# ==========================================

def get_all_hospitals():

    response = (
        admin_supabase
        .table("hospitals")
        .select("*")
        .order(
            "hospital_name",
            desc=False,
        )
        .execute()
    )

    return response.data or []


# ==========================================
# HOSPITAL STAFF
# ==========================================

def get_hospital_staff(
    hospital_id,
    active_only=False,
):
    """
    Get all staff belonging to a hospital.

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
            "user_lname",
            desc=False,
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

    try:
        auth_by_id = get_auth_users_by_id()

    except Exception as exc:

        print(
            "Failed to fetch Auth users "
            f"for hospital staff: {exc}"
        )

        auth_by_id = {}

    for member in staff:

        user_id = str(
            member.get("user_id")
            or ""
        )

        auth_user = auth_by_id.get(
            user_id
        )

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

def get_hospital_staff_member(
    user_id,
):

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

    member["email"] = ""
    member["last_login"] = None

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
            "Failed to fetch Auth information "
            f"for staff member {user_id}: {exc}"
        )

    return member


# ==========================================
# GET USER HOSPITAL STATUS
# ==========================================

def get_user_hospital_status(
    user_id,
):

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
                user_id,
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

        if isinstance(
            hospital,
            list,
        ):
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


# ==========================================
# CONSENT SIGNATURE
# ==========================================

def get_consent_signature_url(
    signature_path,
):
    """
    Return a signed URL for a consent signature.
    URL is valid for one hour.
    """

    if not signature_path:
        return None

    try:

        response = (
            admin_supabase
            .storage
            .from_("consent-signatures")
            .create_signed_url(
                signature_path,
                3600,
            )
        )

        return response.get(
            "signedURL"
        )

    except Exception as exc:

        print(
            "Failed to create signed URL "
            f"for signature: {exc}"
        )

        return None


# ==========================================
# PENDING EXAMINATIONS
# ==========================================

def get_pending_examinations(
    hospital_id=None,
):
    """
    Get examinations with status = Pending.
    """

    query = (
        admin_supabase
        .table("examinations")
        .select("""
            examination_id,
            patient_id,
            examination_type,
            examination_date,
            follow_up_sequence,
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
        .eq(
            "status",
            "Pending",
        )
        .order(
            "created_at",
            desc=False,
        )
    )

    if hospital_id:

        query = query.eq(
            "patients.hospital_id",
            hospital_id,
        )

    response = query.execute()

    return response.data or []


# ==========================================
# AWAITING X-RAY
# ==========================================

def get_pending_xray_examinations(
    hospital_id=None,
):
    """
    Get examinations with status =
    Awaiting X-Ray.
    """

    query = (
        admin_supabase
        .table("examinations")
        .select("""
            examination_id,
            patient_id,
            examination_type,
            examination_date,
            follow_up_sequence,
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
        .eq(
            "status",
            "Awaiting X-Ray",
        )
        .order(
            "created_at",
            desc=False,
        )
    )

    if hospital_id:

        query = query.eq(
            "patients.hospital_id",
            hospital_id,
        )

    response = query.execute()

    return response.data or []


# ==========================================
# X-RAY REQUEST
# ==========================================

def get_xray_request_by_examination(
    examination_id,
):

    if not examination_id:
        return None

    try:

        response = (
            admin_supabase
            .table("xray_requests")
            .select("*")
            .eq(
                "examination_id",
                examination_id,
            )
            .order(
                "requested_at",
                desc=True,
            )
            .limit(1)
            .execute()
        )

        rows = response.data or []

        return (
            rows[0]
            if rows
            else None
        )

    except Exception as exc:

        print(
            f"Error fetching X-ray request: {exc}"
        )

        return None


def get_xray_images_by_request(
    request_id,
):

    if not request_id:
        return []

    try:

        response = (
            admin_supabase
            .table("xray_images")
            .select("*")
            .eq(
                "request_id",
                request_id,
            )
            .order(
                "uploaded_at",
                desc=True,
            )
            .execute()
        )

        return response.data or []

    except Exception as exc:

        print(
            f"Error fetching X-ray images: {exc}"
        )

        return []


def get_xray_image_url(
    image_path,
):

    if not image_path:
        return None

    try:

        response = (
            admin_supabase
            .storage
            .from_("xray-images")
            .create_signed_url(
                image_path,
                3600,
            )
        )

        return response.get(
            "signedURL"
        )

    except Exception as exc:

        print(
            "Error creating X-ray signed URL: "
            f"{exc}"
        )

        return None


# ==========================================
# X-RAY AI RESULT
# ==========================================

def get_xray_ai_result(
    image_id,
):

    if not image_id:
        return None

    try:

        response = (
            admin_supabase
            .table("xray_ai_results")
            .select("*")
            .eq(
                "image_id",
                image_id,
            )
            .order(
                "processed_at",
                desc=True,
            )
            .limit(1)
            .execute()
        )

        rows = response.data or []

        return (
            rows[0]
            if rows
            else None
        )

    except Exception as exc:

        print(
            f"Error fetching AI result: {exc}"
        )

        return None


# ==========================================
# X-RAY REVIEW
# ==========================================

def get_xray_review(
    request_id,
):

    if not request_id:
        return None

    try:

        response = (
            admin_supabase
            .table("xray_reviews")
            .select("*")
            .eq(
                "request_id",
                request_id,
            )
            .order(
                "reviewed_at",
                desc=True,
            )
            .limit(1)
            .execute()
        )

        rows = response.data or []

        return (
            rows[0]
            if rows
            else None
        )

    except Exception as exc:

        print(
            f"Error fetching X-ray review: {exc}"
        )

        return None


# ==========================================
# X-RAY READY
# ==========================================

def get_xray_ready_examinations(
    hospital_id=None,
):
    """
    Get examinations with status =
    X-Ray Ready.
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
        .eq(
            "status",
            "X-Ray Ready",
        )
        .order(
            "created_at",
            desc=False,
        )
    )

    if hospital_id:

        query = query.eq(
            "patients.hospital_id",
            hospital_id,
        )

    response = query.execute()

    return response.data or []


# ==========================================
# MEDICATIONS
# ==========================================

def get_medications_by_examination(
    examination_id,
):

    if not examination_id:
        return []

    try:

        response = (
            admin_supabase
            .table("medications")
            .select("*")
            .eq(
                "examination_id",
                examination_id,
            )
            .order(
                "prescribed_at",
                desc=False,
            )
            .execute()
        )

        return response.data or []

    except Exception as exc:

        print(
            f"Error fetching medications: {exc}"
        )

        return []


# ==========================================
# REFERRAL
# ==========================================

def get_referral_by_examination(
    examination_id,
):

    if not examination_id:
        return None

    try:

        response = (
            admin_supabase
            .table("referrals")
            .select("*")
            .eq(
                "examination_id",
                examination_id,
            )
            .order(
                "referred_at",
                desc=True,
            )
            .limit(1)
            .execute()
        )

        rows = response.data or []

        return (
            rows[0]
            if rows
            else None
        )

    except Exception as exc:

        print(
            f"Error fetching referral: {exc}"
        )

        return None

# ==========================================
# PENDING X-RAY REQUESTS
# ==========================================

def get_pending_xray_requests(
    hospital_id=None,
):
    """
    Get pending X-Ray requests for the physician
    Patient Queue.

    Returns one flattened dictionary per pending
    X-Ray request.

    Structure:

        {
            "request_id": "...",
            "examination_id": "...",
            "hospital_id": "...",
            "requested_by": "...",
            "body_part": "Chest",
            "clinical_indication": "...",
            "priority": "Routine",
            "status": "Pending",
            "requested_at": "...",
            "updated_at": "...",

            "examination": {...},

            "patients": {...}
        }
    """

    try:

        query = (
            admin_supabase
            .table("xray_requests")
            .select("""
                request_id,
                examination_id,
                hospital_id,
                requested_by,
                body_part,
                clinical_indication,
                priority,
                status,
                requested_at,
                updated_at,

                examinations!inner (
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
                        hospital_id
                    )
                )
            """)
            .eq(
                "status",
                "Pending",
            )
            .order(
                "requested_at",
                desc=False,
            )
        )

        # ------------------------------------------
        # HOSPITAL FILTER
        # ------------------------------------------

        if hospital_id:

            query = query.eq(
                "hospital_id",
                hospital_id,
            )

        response = query.execute()

        rows = response.data or []

        print(
            "PENDING X-RAY REQUESTS FOUND:",
            len(rows),
        )

        print(
            "PENDING X-RAY RAW DATA:",
            rows,
        )

        pending_requests = []

        # ------------------------------------------
        # PROCESS REQUESTS
        # ------------------------------------------

        for request in rows:

            examination = (
                request.get("examinations")
            )

            # --------------------------------------
            # SUPABASE MAY RETURN A LIST
            # --------------------------------------

            if isinstance(
                examination,
                list,
            ):

                examination = (
                    examination[0]
                    if examination
                    else None
                )

            if not examination:

                print(
                    "Skipping X-Ray request "
                    f"{request.get('request_id')}: "
                    "missing examination."
                )

                continue

            # --------------------------------------
            # GET PATIENT
            # --------------------------------------

            patient = (
                examination.get("patients")
            )

            if isinstance(
                patient,
                list,
            ):

                patient = (
                    patient[0]
                    if patient
                    else None
                )

            if not patient:

                print(
                    "Skipping X-Ray request "
                    f"{request.get('request_id')}: "
                    "missing patient."
                )

                continue

            # --------------------------------------
            # FLATTEN DATA
            # --------------------------------------

            flattened = {

                # X-Ray request
                "request_id": request.get(
                    "request_id"
                ),

                "examination_id": request.get(
                    "examination_id"
                ),

                "hospital_id": request.get(
                    "hospital_id"
                ),

                "requested_by": request.get(
                    "requested_by"
                ),

                "body_part": request.get(
                    "body_part"
                ),

                "clinical_indication": (
                    request.get(
                        "clinical_indication"
                    )
                ),

                "priority": request.get(
                    "priority"
                ),

                "status": request.get(
                    "status"
                ),

                "requested_at": request.get(
                    "requested_at"
                ),

                "updated_at": request.get(
                    "updated_at"
                ),

                # Examination
                "examination": examination,

                # Patient
                "patients": patient,
            }

            pending_requests.append(
                flattened
            )

        print(
            "PENDING X-RAY REQUESTS RETURNED:",
            len(pending_requests),
        )

        return pending_requests

    except Exception as exc:

        print(
            "Failed to fetch pending X-Ray "
            f"requests: {exc}"
        )

        return []


def get_completed_patient_records(
    hospital_id=None,
):
    """
    Get unique patients who have at least one
    completed examination.

    A patient appears only once even when the
    patient has multiple completed examinations.

    The returned patient dictionaries contain
    basic patient information only. Detailed
    examination history is loaded separately
    using get_examinations_by_patient().
    """

    try:

        query = (
            admin_supabase
            .table("examinations")
            .select("""
                examination_id,
                patient_id,
                status,

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
                    address,
                    hospital_id,

                    hospitals (
                        hospital_id,
                        hospital_name,
                        hospital_code
                    )
                )
            """)
            .eq(
                "status",
                "Completed",
            )
            .order(
                "created_at",
                desc=True,
            )
        )

        if hospital_id:

            query = query.eq(
                "patients.hospital_id",
                hospital_id,
            )

        response = query.execute()

        rows = response.data or []

        unique_patients = {}
        latest_examination = {}

        for row in rows:

            patient = (
                row.get("patients")
                or {}
            )

            if isinstance(
                patient,
                list,
            ):

                patient = (
                    patient[0]
                    if patient
                    else None
                )

            if not patient:
                continue

            patient_id = patient.get(
                "patient_id"
            )

            if not patient_id:
                continue

            # --------------------------------------
            # KEEP ONLY ONE PATIENT ENTRY
            # --------------------------------------

            if patient_id not in unique_patients:

                unique_patients[
                    patient_id
                ] = patient

                latest_examination[
                    patient_id
                ] = row

        return list(
            unique_patients.values()
        )

    except Exception as exc:

        print(
            "Failed to fetch completed "
            f"patient records: {exc}"
        )

        return []

# ==========================================
# HOSPITAL LOCATIONS
# ==========================================

def get_hospital_locations(hospital_id=None):
    """
    Return hospitals that have coordinates.

    If hospital_id is given, returns a single-item list
    containing just that hospital.

    If hospital_id is None, returns every hospital with
    latitude and longitude set (used by the system admin).

    Hospitals without coordinates are excluded — they
    simply don't appear on the map.
    """

    query = (
        admin_supabase
        .table("hospitals")
        .select("""
            hospital_id,
            hospital_name,
            hospital_code,
            address,
            contact_number,
            email,
            website,
            hospital_type,
            hospital_logo_url,
            latitude,
            longitude,
            is_active,
            created_at
        """)
        .not_.is_("latitude", "null")
        .not_.is_("longitude", "null")
        .order("hospital_name", desc=False)
    )

    if hospital_id:
        query = query.eq("hospital_id", hospital_id)

    response = query.execute()

    return response.data or []


def get_hospital_without_coordinates():
    """
    Return hospitals that still lack coordinates.

    Useful for showing an admin which hospitals
    need geocoding.
    """

    response = (
        admin_supabase
        .table("hospitals")
        .select("""
            hospital_id,
            hospital_name,
            hospital_code,
            address,
            is_active
        """)
        .or_("latitude.is.null,longitude.is.null")
        .order("hospital_name", desc=False)
        .execute()
    )

    return response.data or []


# ==========================================
# HOSPITAL PATIENT LOCATIONS
# (placeholder — will be enabled once the
# patients table has lat/lon columns)
# ==========================================

def get_hospital_patient_locations(hospital_id):
    """
    Return patients with coordinates for a hospital.

    Currently returns an empty list because the
    patients table does not yet have latitude /
    longitude columns.

    Once those columns are added, replace the body
    with the actual query (kept in the comment below).

    Expected future query:
        response = (
            admin_supabase
            .table("patients")
            .select(
                "patient_id, patient_code, first_name, "
                "last_name, address, latitude, longitude"
            )
            .eq("hospital_id", hospital_id)
            .not_.is_("latitude", "null")
            .not_.is_("longitude", "null")
            .execute()
        )
        return response.data or []
    """

    if not hospital_id:
        return []

    return []

def get_completed_patients_with_latest_ai(hospital_id=None):
    """
    Return one row per patient who has at least one
    completed examination with an uploaded X-ray.

    Each row includes:
      - patient info (name, DOB, sex, contact, hospital)
      - latest_examination_date      (from the completed exam)
      - latest_image_id              (for AI lookup)
      - ai_findings                  ("positive" | "negative" | None)
      - ai_confidence                (0–1 | None)
      - pneumonia_type               ("bacterial_pneumonia" |
                                      "viral_pneumonia" | None)
      - classification_confidence    (0–1 | None)

    Optimized: queries each table once and merges in Python,
    so the physician list page makes ~4 queries total instead
    of N queries per patient.

    Returns:
        list[dict]
    """

    try:

        # ------------------------------------------
        # 1. Completed examinations
        # ------------------------------------------

        exam_query = (
            admin_supabase
            .table("examinations")
            .select("""
                examination_id,
                patient_id,
                status,
                examination_date,
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
                    address,
                    hospital_id,

                    hospitals (
                        hospital_id,
                        hospital_name,
                        hospital_code
                    )
                )
            """)
            .eq("status", "Completed")
            .order("examination_date", desc=True)
        )

        if hospital_id:
            exam_query = exam_query.eq(
                "patients.hospital_id",
                hospital_id,
            )

        exam_rows = exam_query.execute().data or []

        if not exam_rows:
            return []

        # ------------------------------------------
        # 2. Keep only the LATEST completed exam
        #    per patient
        # ------------------------------------------

        latest_by_patient = {}

        for row in exam_rows:

            patient = row.get("patients") or {}

            if isinstance(patient, list):
                patient = patient[0] if patient else None

            if not patient:
                continue

            patient_id = patient.get("patient_id")

            if not patient_id:
                continue

            if patient_id not in latest_by_patient:
                latest_by_patient[patient_id] = {
                    "patient": patient,
                    "exam": row,
                }

        # ------------------------------------------
        # 3. Fetch X-ray requests for those exams
        # ------------------------------------------

        exam_ids = [
            item["exam"]["examination_id"]
            for item in latest_by_patient.values()
        ]

        req_response = (
            admin_supabase
            .table("xray_requests")
            .select("request_id, examination_id")
            .in_("examination_id", exam_ids)
            .execute()
        )

        req_rows = req_response.data or []

        request_by_exam = {
            r["examination_id"]: r["request_id"]
            for r in req_rows
        }

        # ------------------------------------------
        # 4. Fetch X-ray images for those requests
        # ------------------------------------------

        request_ids = list(request_by_exam.values())

        latest_image_by_request = {}

        if request_ids:

            img_response = (
                admin_supabase
                .table("xray_images")
                .select("image_id, request_id, uploaded_at")
                .in_("request_id", request_ids)
                .order("uploaded_at", desc=True)
                .execute()
            )

            for img in (img_response.data or []):

                rid = img.get("request_id")

                if rid and rid not in latest_image_by_request:
                    latest_image_by_request[rid] = img

        # ------------------------------------------
        # 5. Fetch AI results for those images
        # ------------------------------------------

        image_ids = [
            img["image_id"]
            for img in latest_image_by_request.values()
        ]

        ai_by_image = {}

        if image_ids:

            ai_response = (
                admin_supabase
                .table("xray_ai_results")
                .select(
                    "image_id, ai_findings, ai_confidence, "
                    "pneumonia_type, classification_confidence, "
                    "processed_at"
                )
                .in_("image_id", image_ids)
                .order("processed_at", desc=True)
                .execute()
            )

            for ai in (ai_response.data or []):

                iid = ai.get("image_id")

                if iid and iid not in ai_by_image:
                    ai_by_image[iid] = ai

        # ------------------------------------------
        # 6. Merge everything
        # ------------------------------------------

        results = []

        for patient_id, item in latest_by_patient.items():

            patient = item["patient"]
            exam = item["exam"]

            request_id = request_by_exam.get(
                exam["examination_id"]
            )

            image = (
                latest_image_by_request.get(request_id)
                if request_id
                else None
            )

            ai = (
                ai_by_image.get(image["image_id"])
                if image
                else None
            )

            results.append({
                "patient": patient,
                "examination_id": exam.get("examination_id"),
                "examination_date": (
                    exam.get("examination_date")
                    or exam.get("created_at")
                ),
                "image_id": image.get("image_id") if image else None,
                "ai_findings": ai.get("ai_findings") if ai else None,
                "ai_confidence": (
                    ai.get("ai_confidence") if ai else None
                ),
                "pneumonia_type": (
                    ai.get("pneumonia_type") if ai else None
                ),
                "classification_confidence": (
                    ai.get("classification_confidence")
                    if ai else None
                ),
            })

        # ------------------------------------------
        # 7. Sort by examination date (newest first)
        # ------------------------------------------

        results.sort(
            key=lambda r: r.get("examination_date") or "",
            reverse=True,
        )

        return results

    except Exception as exc:

        print(
            "Failed to fetch completed patients with AI: "
            f"{exc}"
        )

        return []


# ==========================================
# X-RAY AI HEATMAP (GRAD-CAM)
# ==========================================

def get_xray_ai_heatmap(ai_result_id):
    """
    Retrieve the saved Grad-CAM heatmap for an AI result.

    Returns the PNG image bytes, or None if unavailable.
    """

    if not ai_result_id:
        return None

    try:

        # 1. Find the saved heatmap file path.
        response = (
            admin_supabase
            .table("xray_ai_heatmaps")
            .select("heatmap_path")
            .eq(
                "ai_result_id",
                ai_result_id,
            )
            .limit(1)
            .execute()
        )

        rows = response.data or []

        if not rows:
            return None

        heatmap_path = rows[0].get(
            "heatmap_path"
        )

        if not heatmap_path:
            return None

        # 2. Download the PNG from private Storage.
        image_bytes = (
            admin_supabase
            .storage
            .from_("xray-ai-heatmaps")
            .download(heatmap_path)
        )

        return image_bytes

    except Exception as exc:

        print(
            f"Failed to retrieve Grad-CAM heatmap: {exc}"
        )

        return None



# ==========================================
# X-RAY TRAINING CANDIDATES
# ==========================================

def get_training_candidates(
    status=None,
    hospital_id=None,
    limit=500,
):
    """
    Fetch training candidates for review or analysis.

    Parameters
    ----------
    status : str | None
        Filter by workflow status:
            "pending_review" | "approved" | "rejected" | "used_in_training"
        None = return all statuses.

    hospital_id : str | None
        Filter by patient's hospital.
        None = return all hospitals.

    limit : int
        Maximum rows to return. Default 500.
    """

    try:

        query = (
            admin_supabase
            .table("xray_training_candidates")
            .select("""
                candidate_id,
                image_id,
                ai_result_id,
                request_id,
                examination_id,
                patient_id,

                ai_findings,
                ai_confidence,
                ai_pneumonia_type,
                ai_classification_confidence,
                ai_model_version,

                confirmed_label,
                doctor_notes,
                confirmed_by,
                confirmed_at,

                status,
                reviewed_by,
                reviewed_at,
                review_notes,
                used_in_model_version,

                created_at,
                updated_at
            """)
            .order("confirmed_at", desc=True)
            .limit(limit)
        )

        if status:
            query = query.eq("status", status)

        response = query.execute()

        rows = response.data or []

        # ------------------------------------------
        # Optional hospital filter
        # (patient's hospital_id, not candidate's)
        # ------------------------------------------

        if hospital_id and rows:

            patient_ids = list({
                row.get("patient_id")
                for row in rows
                if row.get("patient_id")
            })

            if patient_ids:

                patient_response = (
                    admin_supabase
                    .table("patients")
                    .select("patient_id, hospital_id")
                    .in_("patient_id", patient_ids)
                    .execute()
                )

                patient_hospital_map = {
                    p["patient_id"]: p.get("hospital_id")
                    for p in (patient_response.data or [])
                }

                rows = [
                    row for row in rows
                    if patient_hospital_map.get(
                        row.get("patient_id")
                    ) == hospital_id
                ]

        return rows

    except Exception as exc:

        print(
            f"Failed to fetch training candidates: {exc}"
        )

        return []


def get_training_candidate_stats():
    """
    Return counts of candidates grouped by status.

    Useful for showing badges like
    "12 pending review" on an admin dashboard.
    """

    try:

        response = (
            admin_supabase
            .table("xray_training_candidates")
            .select("status")
            .execute()
        )

        rows = response.data or []

        stats = {
            "pending_review": 0,
            "approved": 0,
            "rejected": 0,
            "used_in_training": 0,
            "total": len(rows),
        }

        for row in rows:

            status = row.get("status")

            if status in stats:
                stats[status] += 1

        return stats

    except Exception as exc:

        print(
            f"Failed to fetch candidate stats: {exc}"
        )

        return {
            "pending_review": 0,
            "approved": 0,
            "rejected": 0,
            "used_in_training": 0,
            "total": 0,
        }



def get_training_candidates_detailed(
    status=None,
    hospital_id=None,
    limit=200,
):
    """
    Return training candidates joined with patient, examination,
    X-ray image, and doctor info.

    Used by the Training Data Review page.

    Each row contains:
        -- candidate fields (all)
        -- patient         (dict)
        -- examination     (dict)
        -- image           (dict)
        -- confirming_user (dict: user_fname, user_lname)
    """

    try:

        query = (
            admin_supabase
            .table("xray_training_candidates")
            .select("""
                *,

                patients (
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
                ),

                examinations (
                    examination_id,
                    examination_type,
                    examination_date,
                    status,
                    follow_up_sequence,
                    chief_complaint,
                    diagnosis
                )
            """)
            .order("confirmed_at", desc=True)
            .limit(limit)
        )

        if status:
            query = query.eq("status", status)

        response = query.execute()
        rows = response.data or []

        # ------------------------------------------
        # Resolve image + user info in bulk
        # ------------------------------------------

        if rows:

            # Images
            image_ids = list({
                r.get("image_id")
                for r in rows
                if r.get("image_id")
            })

            image_map = {}

            if image_ids:
                img_response = (
                    admin_supabase
                    .table("xray_images")
                    .select("image_id, image_path, request_id")
                    .in_("image_id", image_ids)
                    .execute()
                )
                image_map = {
                    img["image_id"]: img
                    for img in (img_response.data or [])
                }

            # Confirmers
            user_ids = list({
                r.get("confirmed_by")
                for r in rows
                if r.get("confirmed_by")
            })

            user_map = {}

            if user_ids:
                user_response = (
                    admin_supabase
                    .table("user_profiles")
                    .select(
                        "user_id, user_fname, user_mname, "
                        "user_lname"
                    )
                    .in_("user_id", user_ids)
                    .execute()
                )
                user_map = {
                    u["user_id"]: u
                    for u in (user_response.data or [])
                }

            # Attach
            for row in rows:
                row["image"] = image_map.get(row.get("image_id"))
                row["confirming_user"] = user_map.get(
                    row.get("confirmed_by")
                )

        # ------------------------------------------
        # Optional hospital filter
        # ------------------------------------------

        if hospital_id and rows:
            rows = [
                r for r in rows
                if (r.get("patients") or {}).get("hospital_id")
                == hospital_id
            ]

        return rows

    except Exception as exc:

        print(
            f"Failed to fetch detailed training candidates: {exc}"
        )

        return []