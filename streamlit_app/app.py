import streamlit as st

from auth.login import show_login


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False


if not st.session_state.logged_in:

    show_login()

else:

    user = st.session_state.user

    st.success(f"Welcome {user['name']}!")

    st.write(f"Role: {user['role']}")

    if user["role"] == "radtech":

        st.header("Receptionist / RadTech Dashboard")

    elif user["role"] == "physician":

        st.header("Radiologist Dashboard")