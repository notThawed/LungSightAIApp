import sys
from pathlib import Path

# ------------------------------------------------------------
# Path shims so this file can be run from anywhere
# ------------------------------------------------------------

# streamlit_app/  (so `from pages...` works)
STREAMLIT_APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STREAMLIT_APP_DIR))

# project root  (so `from backend...` works)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


import streamlit as st

from pages.hospital_administrator import subscription_gate


st.set_page_config(
    page_title="Subscription Gate Preview",
    layout="wide",
)


st.title("Subscription Gate — Preview")


state = st.radio(
    "Which state to preview?",
    ["expired", "grace", "pre_expiry"],
    horizontal=True,
)


st.divider()


if state == "expired":

    subscription_gate.show_expired_screen(
        hospital_name="Ryle Hospital",
        plan_name="Enterprise",
        end_date="2026-10-19",
    )

elif state == "grace":

    subscription_gate.show_grace_banner(
        end_date="2026-10-19",
        days_left=5,
        hospital_name="Ryle Hospital",
    )

    st.success(
        "Dashboard content would appear below this banner."
    )

elif state == "pre_expiry":

    subscription_gate.show_pre_expiry_banner(
        end_date="2026-10-19",
        days_left=5,
        hospital_name="Ryle Hospital",
    )

    st.success(
        "Dashboard content would appear below this banner."
    )