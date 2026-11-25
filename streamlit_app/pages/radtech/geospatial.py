import streamlit as st
from streamlit_app.components.ui import refresh_button


def show():

    title_col, refresh_col = st.columns([8, 0.7], vertical_alignment="center")
    with title_col:
        st.title("Geospatial Analysis")
    with refresh_col:
        refresh_button("radtech_geospatial_refresh")

    st.info("Geospatial analysis page coming soon...")
