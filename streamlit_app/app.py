import streamlit as st

from auth.login import show_login

from layouts.physician_layout import show_physician_layout
from layouts.radtech_layout import show_radtech_layout
from layouts.system_admin_layout import show_admin_layout


st.set_page_config(
    page_title="LungSight",
    page_icon=":microscope:",
    layout="wide",
)


# ==================================================
# SESSION STATE
# ==================================================

if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user" not in st.session_state:
    st.session_state.user = None


# ==================================================
# LOGIN
# ==================================================

if not st.session_state.logged_in:

    show_login()

    st.stop()


# ==================================================
# LOGGED-IN USER
# ==================================================

user = st.session_state.user

role = user.get("role")


# ==================================================
# ROLE-BASED DASHBOARD
# ==================================================

if role == "Radiologist":

    show_physician_layout()


elif role == "Radiologic Technologist":

    show_radtech_layout()


elif role == "Hospital Admin":

    show_admin_layout()


elif role == "Superadmin":

    # For now, use the admin layout.
    # We can create a dedicated superadmin layout later.

    show_admin_layout()


elif role == "Staff":

    # We can create a staff layout later.

    st.info(
        "Staff dashboard is not yet implemented."
    )


else:

    st.error(
        "Invalid user role. "
        "Please contact the administrator."
    )