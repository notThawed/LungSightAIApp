import streamlit as st

from auth.login import show_login

from layouts.physician_layout import show_physician_layout
from layouts.radtech_layout import show_radtech_layout
from layouts.system_admin_layout import show_system_admin_layout
from layouts.staff_layout import show_staff_layout
from layouts.hospital_admin_layout import show_hospital_admin_layout


st.set_page_config(
    page_title="LungSight",
    page_icon=":microscope:",
    layout="wide",
)

# ==================================================
# INVITE / SET PASSWORD ROUTE
# ==================================================

# Supabase puts the invite token in the URL fragment
# (#access_token=...). Streamlit can't read fragments,
# so this JS snippet reloads the page with the token
# moved into query params (?access_token=...).

if st.query_params.get("access_token"):
    from screens.set_password import show as show_set_password
    show_set_password()
    st.stop()

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

    show_hospital_admin_layout()


elif role == "Superadmin":

    show_system_admin_layout()


elif role == "Staff":

    show_staff_layout()

else:

    st.error(
        "Invalid user role. "
        "Please contact the administrator."
    )