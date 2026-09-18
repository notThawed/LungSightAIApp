import streamlit as st

from backend.supabase_client import supabase


def show():

    st.set_page_config(
        page_title="Set Password",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="collapsedControl"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    access_token = st.query_params.get("access_token")
    refresh_token = st.query_params.get("refresh_token")

    st.title("Set Your Password")
    st.caption("Complete your LungSight account setup.")

    # ------------------------------------------
    # SUCCESS SCREEN
    # ------------------------------------------

    if st.session_state.get("password_set_success"):

        st.success(
            "Password set successfully! "
            "You can now log in with your email and password."
        )

        st.balloons()

        if st.button("Go to Login", type="primary"):

            # Clear the invite session state
            st.session_state.pop("password_set_success", None)
            st.session_state.pop("invite_session_ready", None)

            # Clear the query params so Streamlit returns to the login page
            st.query_params.clear()

            st.rerun()

        return

    # ------------------------------------------
    # TOKEN CHECK
    # ------------------------------------------

    if not access_token or not refresh_token:

        st.warning(
            "This page is only accessible from an invitation link. "
            "If you're seeing this message, please use the link "
            "from your email."
        )

        return

    # ------------------------------------------
    # ESTABLISH SESSION (ONCE)
    # ------------------------------------------

    if not st.session_state.get("invite_session_ready"):

        try:

            supabase.auth.set_session(
                access_token,
                refresh_token,
            )

            st.session_state["invite_session_ready"] = True

        except Exception:

            st.error(
                "This invitation link is invalid or has expired. "
                "Please request a new invitation from your administrator."
            )

            return

    # ------------------------------------------
    # PASSWORD FORM
    # ------------------------------------------

    with st.form("set_password_form"):

        password = st.text_input(
            "New Password",
            type="password",
        )

        confirm = st.text_input(
            "Confirm Password",
            type="password",
        )

        submitted = st.form_submit_button(
            "Set Password",
            type="primary",
        )

    if submitted:

        if not password:
            st.error("Password is required.")
            return

        if password != confirm:
            st.error("Passwords do not match.")
            return

        if len(password) < 8:
            st.error("Password must be at least 8 characters.")
            return

        try:

            supabase.auth.update_user({
                "password": password,
            })

            st.session_state["password_set_success"] = True

            st.rerun()

        except Exception as e:

            st.error(f"Failed to set password: {e}")