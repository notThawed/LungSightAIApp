import streamlit as st

from backend.fetches import get_all_patients


def show():
    st.title("Manage Examinations")
    st.caption("Select a patient to create and manage examinations.")

    patients = load_patients()

    search, sex_filter, status_filter = show_filters()

    patients = filter_patients(
        patients,
        search,
        sex_filter,
        status_filter
    )

    show_patient_table(patients)


def load_patients():
    try:
        patients = get_all_patients()
        return patients or []

    except Exception as e:
        st.error(
            f"Unable to load patients: {str(e)}"
        )
        return []


def show_filters():
    """
    Display search and patient filters.
    """

    col1, col2, col3, col4 = st.columns(
        [3, 1.2, 1.2, 1]
    )

    with col1:
        search = st.text_input(
            "Search Patient",
            placeholder="Search by patient name or contact number...",
            label_visibility="collapsed"
        )

    with col2:
        sex_filter = st.selectbox(
            "Sex",
            ["All", "Male", "Female"],
            label_visibility="collapsed"
        )

    with col3:
        status_filter = st.selectbox(
            "Status",
            ["All", "Active", "Inactive"],
            label_visibility="collapsed"
        )

    with col4:
        if st.button(
            "↻ Reset",
            width="stretch"
        ):
            st.rerun()

    return search, sex_filter, status_filter


def filter_patients(
    patients,
    search,
    sex_filter,
    status_filter
):
    """
    Filter patients based on search,
    sex, and status.
    """

    filtered = []

    search = search.strip().lower()

    for patient in patients:

        full_name = " ".join(
            part for part in [
                patient.get("first_name"),
                patient.get("middle_name"),
                patient.get("last_name"),
                patient.get("suffix")
            ]
            if part
        ).lower()

        contact = (
            patient.get("contact_number") or ""
        ).lower()

        # Search
        if search:
            if (
                search not in full_name
                and search not in contact
            ):
                continue

        # Sex
        if sex_filter != "All":
            if patient.get("sex") != sex_filter:
                continue

        # Status
        if status_filter != "All":
            if patient.get("status") != status_filter:
                continue

        filtered.append(patient)

    return filtered


def show_patient_table(patients):
    """
    Display patients available for examination.
    """

    if not patients:
        st.info("No patients found.")
        return

    # Table header
    col1, col2, col3, col4, col5, col6 = st.columns(
        [1.5, 2.5, 1.5, 1, 2, 1]
    )

    with col1:
        st.markdown("**Patient ID**")

    with col2:
        st.markdown("**Patient Name**")

    with col3:
        st.markdown("**Date of Birth**")

    with col4:
        st.markdown("**Sex**")

    with col5:
        st.markdown("**Contact Number**")

    with col6:
        st.markdown("**Action**")

    st.divider()

    # Patient rows
    for patient in patients:

        patient_id = patient.get("patient_id")

        full_name = " ".join(
            part for part in [
                patient.get("first_name"),
                patient.get("middle_name"),
                patient.get("last_name"),
                patient.get("suffix")
            ]
            if part
        )

        col1, col2, col3, col4, col5, col6 = st.columns(
            [1.5, 2.5, 1.5, 1, 2, 1]
        )

        with col1:
            st.write(patient_id)

        with col2:
            st.write(full_name)

        with col3:
            st.write(patient.get("date_of_birth"))

        with col4:
            st.write(patient.get("sex"))

        with col5:
            st.write(
                patient.get("contact_number") or "—"
            )

        with col6:
            if st.button(
                "Examine",
                key=f"examine_{patient_id}",
                width="stretch"
            ):
                show_examination_dialog(patient)

        st.divider()

@st.dialog("Create Examination")
def show_examination_dialog(patient):
    st.markdown("OTEN")