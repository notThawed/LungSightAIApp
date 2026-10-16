from backend.supabase_client import (
    supabase,
    admin_supabase,
)


# ============================================================
# LOGIN
# ============================================================

def login_user(email, password):
    """
    Authenticate the user through Supabase Auth
    and retrieve their complete LungSight profile.

    Returned user data includes:

        - Supabase Auth information
        - User profile information
        - Role information
        - Hospital information
        - Profile picture URL
        - Hospital logo URL
        - Authentication tokens
    """

    # --------------------------------------------------------
    # 1. AUTHENTICATE WITH SUPABASE AUTH
    # --------------------------------------------------------

    response = supabase.auth.sign_in_with_password(
        {
            "email": email,
            "password": password,
        }
    )

    if not response.user:
        return None

    user_id = response.user.id

    print("====================================")
    print("SUPABASE LOGIN SUCCESSFUL")
    print("User ID:", user_id)
    print("Email:", response.user.email)
    print("====================================")

    # --------------------------------------------------------
    # 2. GET USER PROFILE
    # --------------------------------------------------------

    profile_response = (
        supabase
        .table("user_profiles")
        .select(
            """
            user_id,
            user_fname,
            user_mname,
            user_lname,
            user_contact_number,
            profile_picture_url,
            role_id,
            hospital_id,
            is_active,
            theme_preference,
            roles (
                role_id,
                role_name
            )
            """
        )
        .eq("user_id", user_id)
        .execute()
    )

    profiles = profile_response.data

    print("PROFILE RESULT:", profiles)

    # --------------------------------------------------------
    # 3. PROFILE DOES NOT EXIST
    # --------------------------------------------------------

    if not profiles:

        supabase.auth.sign_out()

        raise ValueError(
            "Authentication succeeded, but this user "
            "does not have a LungSight profile."
        )

    profile = profiles[0]

    # --------------------------------------------------------
    # 4. CHECK ACCOUNT STATUS
    # --------------------------------------------------------

    if not profile.get("is_active", False):

        supabase.auth.sign_out()

        raise ValueError(
            "Your LungSight account is inactive."
        )

    # --------------------------------------------------------
    # 5. GET ROLE
    # --------------------------------------------------------

    role = profile.get("roles")

    if not role:

        supabase.auth.sign_out()

        raise ValueError(
            "Your LungSight profile does not have a valid role."
        )

    role_name = role.get("role_name")

    if not role_name:

        supabase.auth.sign_out()

        raise ValueError(
            "Your LungSight profile does not have a valid role."
        )

    # --------------------------------------------------------
    # 6. GET HOSPITAL INFORMATION
    # --------------------------------------------------------

    hospital_id = profile.get("hospital_id")

    hospital_name = None
    hospital_logo_url = None

    if hospital_id:

        try:

            hospital_response = (
                admin_supabase
                .table("hospitals")
                .select(
                    """
                    hospital_id,
                    hospital_name,
                    hospital_logo_url,
                    is_active
                    """
                )
                .eq(
                    "hospital_id",
                    hospital_id,
                )
                .maybe_single()
                .execute()
            )

            hospital = hospital_response.data

            # ------------------------------------------------
            # HOSPITAL DOES NOT EXIST
            # ------------------------------------------------

            if not hospital:

                supabase.auth.sign_out()

                raise ValueError(
                    "Your account is assigned to a hospital "
                    "that could not be found. "
                    "Please contact the system administrator."
                )

            # ------------------------------------------------
            # HOSPITAL IS DEACTIVATED
            # ------------------------------------------------

            if not hospital.get("is_active", False):

                supabase.auth.sign_out()

                raise ValueError(
                    "This hospital is currently deactivated "
                    "in the LungSight system. "
                    "Please contact your hospital administrator "
                    "or LungSight system administrator for assistance."
                )

            # ------------------------------------------------
            # HOSPITAL IS ACTIVE
            # ------------------------------------------------

            hospital_name = hospital.get(
                "hospital_name"
            )

            hospital_logo_url = hospital.get(
                "hospital_logo_url"
            )

        except ValueError:
            raise

        except Exception as exc:

            print(
                "HOSPITAL LOOKUP ERROR:",
                repr(exc),
            )

    # --------------------------------------------------------
    # 7. BUILD FULL NAME
    # --------------------------------------------------------

    first_name = profile.get("user_fname") or ""
    middle_name = profile.get("user_mname") or ""
    last_name = profile.get("user_lname") or ""

    full_name = " ".join(
        part
        for part in [
            first_name,
            middle_name,
            last_name,
        ]
        if part
    ).strip()

    if not full_name:
        full_name = "User"

    # --------------------------------------------------------
    # 8. RETURN USER
    # --------------------------------------------------------

    user_data = {

        # ----------------------------------------------------
        # Auth
        # ----------------------------------------------------

        "user_id":
            user_id,

        "email":
            response.user.email,

        "theme_preference":
            profile.get(
                "theme_preference"
            )or "light",

        # ----------------------------------------------------
        # Name
        # ----------------------------------------------------

        "name":
            full_name,

        "first_name":
            first_name,

        "middle_name":
            middle_name or None,

        "last_name":
            last_name,

        # ----------------------------------------------------
        # Contact
        # ----------------------------------------------------

        "contact_number":
            profile.get(
                "user_contact_number"
            ),

        # ----------------------------------------------------
        # Role
        # ----------------------------------------------------

        "role":
            role_name,

        "role_id":
            profile.get("role_id"),

        # ----------------------------------------------------
        # Hospital
        # ----------------------------------------------------

        "hospital_id":
            hospital_id,

        "hospital_name":
            hospital_name,

        "hospital_logo_url":
            hospital_logo_url,

        # ----------------------------------------------------
        # Profile picture
        # ----------------------------------------------------

        "profile_picture_url":
            profile.get(
                "profile_picture_url"
            ),

        # ----------------------------------------------------
        # Supabase Auth session
        # ----------------------------------------------------

        "access_token": (
            response.session.access_token
            if response.session
            else None
        ),

        "refresh_token": (
            response.session.refresh_token
            if response.session
            else None
        ),
    }

    print("====================================")
    print("LUNGSIGHT USER DATA")
    print("Name:", user_data["name"])
    print("Role:", user_data["role"])
    print("Hospital:", user_data["hospital_name"])
    print("Theme:", user_data["theme_preference"])
    print(
        "Profile Picture:",
        bool(user_data["profile_picture_url"]),
    )
    print(
        "Hospital Logo:",
        bool(user_data["hospital_logo_url"]),
    )
    print("====================================")

    return user_data


# ============================================================
# CHECK IF EMAIL EXISTS IN SUPABASE AUTH
# ============================================================

def auth_email_exists(email: str) -> bool:
    """
    Check whether an email already exists in Supabase Auth.

    Uses the Supabase Admin API.
    Returns True if the email exists, otherwise False.
    """

    email = email.strip().lower()

    print("====================================")
    print("AUTH EMAIL CHECK")
    print("Email:", email)
    print("Using Supabase Auth")
    print("====================================")

    try:

        users = admin_supabase.auth.admin.list_users()

        print(
            "AUTH LIST USERS RESPONSE RECEIVED"
        )

        print(
            "Response type:",
            type(users),
        )

        # ----------------------------------------------------
        # Supabase versions may return the users directly
        # as a list, or return an object containing users.
        # ----------------------------------------------------

        if isinstance(users, list):

            user_list = users

        elif hasattr(users, "users"):

            user_list = users.users

        else:

            print(
                "Unexpected Supabase list_users response:",
                repr(users),
            )

            return False

        # ----------------------------------------------------
        # Check email
        # ----------------------------------------------------

        for user in user_list:

            user_email = getattr(
                user,
                "email",
                None,
            )

            print(
                "Checking:",
                user_email,
            )

            if (
                user_email
                and user_email.strip().lower()
                == email
            ):

                print(
                    "AUTH EMAIL EXISTS: TRUE"
                )

                return True

        print(
            "AUTH EMAIL EXISTS: FALSE"
        )

        return False

    except Exception as e:

        print(
            "AUTH EMAIL ERROR:",
            repr(e),
        )

        raise Exception(
            f"Unable to verify authentication email: {e}"
        )


# ============================================================
# LOGOUT
# ============================================================

def logout_user():
    """Sign out from Supabase."""

    supabase.auth.sign_out()

