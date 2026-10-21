<<<<<<< HEAD
# auth/auth_manager.py

USERS = {
    "radtech@lungsight.com": {
        "password": "123456",
        "name": "John RadTech",
        "role": "radtech"
    },
    "doctor@lungsight.com": {
        "password": "123456",
        "name": "Dr. Smith",
        "role": "physician"
    }
}


def authenticate(email, password):
    user = USERS.get(email)

    if user and user["password"] == password:
        return {
            "email": email,
            "name": user["name"],
            "role": user["role"]
        }

    return None
=======
import streamlit as st

from backend.auth import login_user, logout_user


def initialize_auth():

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if "user" not in st.session_state:
        st.session_state.user = None


def authenticate(email, password):

    try:

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

        raise


def logout():
    try:
        logout_user()
    except Exception as e:
        print(f"Logout error: {e}")

    st.session_state.logged_in = False
    st.session_state.user = None

    # ----------------------------------------------------
    # Clear cached subscription state so the next login
    # re-fetches from the database
    # ----------------------------------------------------

    st.session_state.pop("subscription_context", None)

    st.session_state.pop("grace_info", None)


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
>>>>>>> origin/LungSightV2
