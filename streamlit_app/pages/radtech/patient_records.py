import streamlit as st
from streamlit_app.components.ui import refresh_button


def show():

    title_col, refresh_col = st.columns([8, 0.7], vertical_alignment="center")
    with title_col:
        st.title("Patient Record X-Ray")
    with refresh_col:
        refresh_button("radtech_patient_records_refresh")

    st.info("Patient Record page coming soon...")
