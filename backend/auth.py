from backend.supabase_client import supabase


def login_user(email, password):
    """
    Authenticate the user through Supabase Auth
    and retrieve their LungSight profile.
    """

    # ============================================
    # 1. AUTHENTICATE WITH SUPABASE
    # ============================================

    response = supabase.auth.sign_in_with_password({
        "email": email,
        "password": password
    })

    if not response.user:
        return None

    user_id = response.user.id

    print("====================================")
    print("SUPABASE LOGIN SUCCESSFUL")
    print("User ID:", user_id)
    print("Email:", response.user.email)
    print("====================================")

    # ============================================
    # 2. GET USER PROFILE
    # ============================================

    profile_response = (
        supabase
        .table("user_profiles")
        .select(
            """
            user_id,
            user_fname,
            user_mname,
            user_lname,
            role_id,
            hospital_id,
            employee_id,
            user_contact_number,
            is_active,
            roles (
                role_id,
                role_name
            )
            """
        )
        .eq(
            "user_id",
            user_id
        )
        .execute()
    )

    profiles = profile_response.data

    print("PROFILE RESULT:", profiles)

    # ============================================
    # 3. PROFILE DOES NOT EXIST
    # ============================================

    if not profiles:

        supabase.auth.sign_out()

        raise ValueError(
            "Authentication succeeded, but this user "
            "does not have a LungSight profile."
        )

    profile = profiles[0]

    # ============================================
    # 4. CHECK ACCOUNT STATUS
    # ============================================

    if not profile.get("is_active", False):

        supabase.auth.sign_out()

        raise ValueError(
            "Your LungSight account is inactive."
        )

    # ============================================
    # 5. GET ROLE
    # ============================================

    role = profile.get("roles")

    if not role:

        supabase.auth.sign_out()

        raise ValueError(
            "Your LungSight profile does not have a valid role."
        )

    role_name = role["role_name"]

    # ============================================
    # 6. GET HOSPITAL ID
    # ============================================

    hospital_id = profile.get(
        "hospital_id"
    )

    # ============================================
    # 7. RETURN USER
    # ============================================

    user = {

        "user_id":
            user_id,

        "email":
            response.user.email,

        "name":
            (
                f"{profile.get('user_fname', '')} "
                f"{profile.get('user_lname', '')}"
            ).strip(),

        "first_name":
            profile.get("user_fname"),

        "middle_name":
            profile.get("user_mname"),

        "last_name":
            profile.get("user_lname"),

        "role":
            role_name,

        "role_id":
            profile.get("role_id"),

        "hospital_id":
            hospital_id,

        "employee_id":
            profile.get("employee_id"),

        "user_contact_number":
            profile.get("user_contact_number"),

        "is_active":
            profile.get("is_active"),

    }

    # ============================================
    # DEBUG INFORMATION
    # ============================================

    print("====================================")
    print("LUNGSIGHT USER")
    print("User ID:", user.get("user_id"))
    print("Name:", user.get("name"))
    print("Role:", user.get("role"))
    print("Hospital ID:", user.get("hospital_id"))
    print("Employee ID:", user.get("employee_id"))
    print("====================================")

    return user


def logout_user():
    """Sign out from Supabase."""

    supabase.auth.sign_out()