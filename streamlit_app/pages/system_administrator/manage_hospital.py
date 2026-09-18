import streamlit as st
import pandas as pd

from backend.fetches import get_all_hospitals
from backend.crud import create_hospital, update_hospital, deactivate_hospital, reactivate_hospital

# ============================================================
# PAGE ENTRY
# ============================================================
def show():
    st.title("Manage Hospitals")
    st.caption("View and manage registered hospitals.")

    search = show_search_bar()

    hospitals = load_hospitals()

    hospitals = filter_hospitals(hospitals, search)

    create_hospital_table(hospitals)


# ============================================================
# DATA LOADING
# ============================================================
def load_hospitals():
    try:
        return get_all_hospitals()
    except Exception as e:
        st.error(f"Unable to load hospitals: {str(e)}")
        return []


# ============================================================
# SEARCH BAR + BUTTON
# ============================================================
def show_search_bar():

    col1, col2 = st.columns([4, 1])

    with col1:
        search = st.text_input(
            "Search Hospital",
            placeholder="Search by name, code, or email...",
            label_visibility="collapsed"
        )

    with col2:
        if st.button("＋ Register Hospital", width="stretch"):
            show_add_hospital_form()

    return search


# ============================================================
# FILTER
# ============================================================
def filter_hospitals(hospitals, search):

    search = search.strip().lower()

    if not search:
        return hospitals

    filtered = []

    for hospital in hospitals:

        name  = (hospital.get("hospital_name") or "").lower()
        code  = (hospital.get("hospital_code") or "").lower()
        email = (hospital.get("email") or "").lower()

        if (
            search in name
            or search in code
            or search in email
        ):
            filtered.append(hospital)

    return filtered

# ============================================================
# TABLE
# ============================================================
def create_hospital_table(hospitals):

    if not hospitals:
        st.info("No hospitals registered.")
        return

    # ----------------------------------------------------------
    # HEADER
    # ----------------------------------------------------------
    col1, col2, col3, col4, col5, col6, col7 = st.columns(
        [1.2, 2.5, 1.5, 3, 2, 1, 1.5]
    )

    with col1:
        st.markdown("**Code**")

    with col2:
        st.markdown("**Hospital Name**")

    with col3:
        st.markdown("**Contact Number**")

    with col4:
        st.markdown("**Address**")

    with col5:
        st.markdown("**Email**")

    with col6:
        st.markdown("**Status**")

    with col7:
        st.markdown("**Action**")

    st.divider()

    # ----------------------------------------------------------
    # ROWS
    # ----------------------------------------------------------
    for hospital in hospitals:

        hospital_id = hospital.get("hospital_id")
        is_active   = hospital.get("is_active", True)

        col1, col2, col3, col4, col5, col6, col7 = st.columns(
            [1.2, 2.5, 1.5, 3, 2, 1, 1.5]
        )

        with col1:
            st.write(hospital.get("hospital_code") or "—")

        with col2:
            st.write(hospital.get("hospital_name") or "—")

        with col3:
            st.write(hospital.get("contact_number") or "—")

        with col4:
            st.write(hospital.get("address") or "—")

        with col5:
            st.write(hospital.get("email") or "—")

        with col6:
            if is_active:
                st.success("Active")
            else:
                st.error("Inactive")

        # ------------------------------------------------------
        # ACTION — Edit + (Deactivate / Reactivate) side by side
        # ------------------------------------------------------
        with col7:

            btn_col1, btn_col2 = st.columns(2)

            with btn_col1:
                if st.button(
                    "✏️",
                    key=f"edit_{hospital_id}",
                    help="Edit hospital"
                ):
                    show_edit_hospital_dialog(hospital)

            with btn_col2:
                if is_active:
                    if st.button(
                        "🗑️",
                        key=f"deactivate_{hospital_id}",
                        help="Deactivate hospital"
                    ):
                        show_deactivate_hospital_dialog(hospital)
                else:
                    if st.button(
                        "✅",
                        key=f"reactivate_{hospital_id}",
                        help="Reactivate hospital"
                    ):
                        show_reactivate_hospital_dialog(hospital)

        st.divider()


@st.dialog("Register New Hospital")
def show_add_hospital_form():

    with st.form(
        "add_hospital_form",
        clear_on_submit=True
    ):
        st.markdown("### Hospital Information")

        hospital_name = st.text_input(
            "Hospital Name"
        )

        hospital_code = st.text_input(
            "Hospital Code",
            placeholder="e.g. SLMC"
        )

        address = st.text_area(
            "Address"
        )

        col1, col2 = st.columns(2)

        with col1:
            contact_number = st.text_input(
                "Contact Number",
                placeholder="+63 000 000 0000"
            )

        with col2:
            email = st.text_input(
                "Email",
                placeholder="admin@hospital.com"
            )

        # BUTTONS
        col1, col2 = st.columns(2)

        with col1:
            submitted = st.form_submit_button(
                "Register Hospital",
                width="stretch"
            )

        with col2:
            cancel = st.form_submit_button(
                "Cancel",
                width="stretch"
            )

        if cancel:
            st.rerun()

        if submitted:

            if not hospital_name.strip():
                st.error("Hospital name required.")
                return

            if not address.strip():
                st.error("Address required.")
                return

            try:
                result = create_hospital(
                    hospital_name=hospital_name.strip(),
                    hospital_code=hospital_code.strip() or None,
                    address=address.strip(),
                    contact_number=contact_number.strip() or None,
                    email=email.strip() or None,
                    created_by=st.session_state["user"]["user_id"]
                )

                st.success("Hospital registered successfully!")
                st.rerun()

            except Exception as e:
                st.error(f"Failed to register hospital: {str(e)}")

@st.dialog("Edit Hospital")
def show_edit_hospital_dialog(hospital):

    st.markdown("### Hospital Information")

    hospital_name = st.text_input(
        "Hospital Name",
        value=hospital.get("hospital_name") or ""
    )

    hospital_code = st.text_input(
        "Hospital Code",
        value=hospital.get("hospital_code") or ""
    )

    address = st.text_area(
        "Address",
        value=hospital.get("address") or ""
    )

    col1, col2 = st.columns(2)

    with col1:
        contact_number = st.text_input(
            "Contact Number",
            value=hospital.get("contact_number") or ""
        )

    with col2:
        email = st.text_input(
            "Email",
            value=hospital.get("email") or ""
        )

    # ------- Buttons -------
    col1, col2 = st.columns(2)

    with col1:
        save = st.button(
            "Save Changes",
            width="stretch"
        )

    with col2:
        cancel = st.button(
            "Cancel",
            width="stretch"
        )

    if cancel:
        st.rerun()

    if save:

        if not hospital_name.strip():
            st.error("Hospital name is required.")
            return

        if not address.strip():
            st.error("Address is required.")
            return

        try:
            update_hospital(
                hospital_id=hospital["hospital_id"],
                hospital_name=hospital_name.strip(),
                hospital_code=hospital_code.strip() or None,
                address=address.strip(),
                contact_number=contact_number.strip() or None,
                email=email.strip() or None
            )

            st.success("Hospital updated successfully!")
            st.rerun()

        except Exception as e:
            st.error(f"Failed to update hospital: {str(e)}")

@st.dialog("Deactivate Hospital")
def show_deactivate_hospital_dialog(hospital):

    st.warning(
        f"Are you sure you want to deactivate "
        f"**{hospital.get('hospital_name')}**?"
    )

    st.write(
        "This will set the hospital status to **Inactive**. "
        "You can reactivate it later."
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "Deactivate",
            width="stretch"
        ):
            try:
                deactivate_hospital(hospital["hospital_id"])

                st.success("Hospital deactivated successfully!")
                st.rerun()

            except Exception as e:
                st.error(f"Failed to deactivate hospital: {str(e)}")

    with col2:
        if st.button(
            "Cancel",
            width="stretch"
        ):
            st.rerun()


@st.dialog("Reactivate Hospital")
def show_reactivate_hospital_dialog(hospital):

    st.info(
        f"Reactivate **{hospital.get('hospital_name')}**?"
    )

    st.write(
        "This will set the hospital status back to **Active**."
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "Reactivate",
            width="stretch"
        ):
            try:
                reactivate_hospital(hospital["hospital_id"])

                st.success("Hospital reactivated successfully!")
                st.rerun()

            except Exception as e:
                st.error(f"Failed to reactivate hospital: {str(e)}")

    with col2:
        if st.button(
            "Cancel",
            width="stretch"
        ):
            st.rerun()