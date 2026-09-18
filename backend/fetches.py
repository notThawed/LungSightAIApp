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
# GET ALL USERS
# ==========================================

def get_all_users():
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

    users = response.data or []


    # ------------------------------------------
    # GET AUTH INFORMATION
    # ------------------------------------------

    for user in users:

        user["email"] = ""
        user["last_login"] = None

        try:

            auth_response = (
                admin_supabase
                .auth
                .admin
                .get_user_by_id(
                    user["user_id"]
                )
            )

            if auth_response.user:

                # EMAIL
                user["email"] = (
                    auth_response.user.email
                    or ""
                )

                # LAST LOGIN
                user["last_login"] = (
                    convert_to_manila_time(
                        auth_response.user.last_sign_in_at
                    )
                )

        except Exception as e:

            print(
                f"Failed to fetch auth information "
                f"for {user['user_id']}: {e}"
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
# GET USER COUNTS
# ==========================================

def get_user_counts():

    users = get_all_users()

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
            clinical_notes,
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

