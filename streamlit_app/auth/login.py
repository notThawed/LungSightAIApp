# auth/login.py

import streamlit as st
from auth.auth_manager import authenticate


def show_login():

    st.title("🫁 LungSight")

    st.subheader("AI-Powered Chest X-Ray Analysis")

    email = st.text_input("Email")

    password = st.text_input(
        "Password",
        type="password"
    )

    if st.button("Login"):

        user = authenticate(email, password)

        if user:

            st.session_state.logged_in = True
            st.session_state.user = user

            st.rerun()

        else:

            st.error("Invalid email or password.")