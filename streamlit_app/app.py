import streamlit as st

from auth.login import show_login

from layouts.physician_layout import show_physician_layout
from layouts.radtech_layout import show_radtech_layout
from layouts.admin_layout import show_admin_layout

st.set_page_config(
    page_title="LungSight",
    page_icon=":microscope:",
    layout="wide",
)

if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user" not in st.session_state:
    st.session_state.user = None



if not st.session_state.logged_in:

    show_login()

else:

    role = st.session_state.user["role"]

    if role == "physician":
        show_physician_layout()

    elif role == "admin":
        show_admin_layout()

    elif role == "radtech":
        show_radtech_layout()

    else:
        st.error("Invalid user role. Please contact the administrator.")