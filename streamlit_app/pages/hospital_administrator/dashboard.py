import streamlit as st
from streamlit_app.components.ui import refresh_button

def show():

    title_col, refresh_col = st.columns([8, 0.7], vertical_alignment="center")
    with title_col:
        st.header("Hospital Admin Dashboard")
    with refresh_col:
        refresh_button("hospital_admin_dashboard_refresh")

    st.info("Hospital Administration Dashboard Coming Soon..")
