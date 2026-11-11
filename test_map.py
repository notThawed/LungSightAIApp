# test_map.py — throwaway file, delete after verifying

import streamlit as st

from backend.fetches import get_hospital_locations
from streamlit_app.components.map import render_hospital_map


st.title("Hospital Map — Test")

hospitals = get_hospital_locations()

st.write(f"Loaded {len(hospitals)} hospitals with coordinates.")

if hospitals:

    output = render_hospital_map(
        hospitals,
        key="test_map",
    )

    st.write("Click a marker to see the event:")
    st.write(output)

else:

    st.error("No hospitals with coordinates found.")