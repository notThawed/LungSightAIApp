import streamlit as st

# Preconfigured test users for UI review & testing
DEMO_USERS = {
    "radiologist@lungsight.ai": {
        "user_id": "demo-rad-001",
        "email": "radiologist@lungsight.ai",
        "name": "Dr. Sarah Jenkins, MD",
        "first_name": "Sarah",
        "last_name": "Jenkins",
        "role": "Radiologist",
        "role_id": 1,
    },
    "radtech@lungsight.ai": {
        "user_id": "demo-tech-002",
        "email": "radtech@lungsight.ai",
        "name": "Alex Rivera, RTR",
        "first_name": "Alex",
        "last_name": "Rivera",
        "role": "Radiologic Technologist",
        "role_id": 2,
    },
    "admin@lungsight.ai": {
        "user_id": "demo-adm-003",
        "email": "admin@lungsight.ai",
        "name": "Marcus Vance",
        "first_name": "Marcus",
        "last_name": "Vance",
        "role": "Hospital Admin",
        "role_id": 3,
    },
}


def initialize_auth():

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if "user" not in st.session_state:
        st.session_state.user = None


def login_as_demo_user(email_key: str):
    email_clean = email_key.strip().lower()
    if email_clean in DEMO_USERS:
        user = DEMO_USERS[email_clean]
        st.session_state.logged_in = True
        st.session_state.user = user
        st.session_state.current_page = "Dashboard"
        return user
    return None


def authenticate(email, password):
    email_clean = email.strip().lower()

    # Allow instant demo login for the 3 roles
    if email_clean in DEMO_USERS:
        return login_as_demo_user(email_clean)

    try:
        from backend.auth import login_user
        user = login_user(
            email,
            password
        )

        if user:

            st.session_state.logged_in = True
            st.session_state.user = user

            return user

        return None

    except Exception as e:

        print(f"Authentication error: {e}")

        return None


def logout():

    try:
        from backend.auth import logout_user
        logout_user()

    except Exception as e:
        print(f"Logout error: {e}")

    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.current_page = "Dashboard"


def is_authenticated():

    return st.session_state.get(
        "logged_in",
        False
    )


def get_current_user():

    return st.session_state.get(
        "user"
    )


def get_current_role():

    user = get_current_user()

    if not user:
        return None

    return user.get("role")