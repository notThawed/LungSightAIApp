import streamlit as st
from streamlit_app.components.ui import refresh_button


def show():

    title_col, refresh_col = st.columns([8, 0.7], vertical_alignment="center")
    with title_col:
        st.title("Radiologist Dashboard")
    with refresh_col:
        refresh_button("physician_dashboard_refresh")

    st.info("Dashboard coming soon...")
