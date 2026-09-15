import streamlit as st

from backend.fetches import get_all_patients, get_examinations_by_patient
from backend.crud import create_examination, update_examination_clinical_notes


def show():

    st.title("Manage Examinations")
    st.caption(
        "Select a patient to create and manage examinations."
    )

    patients = load_patients()

    search, sex_filter, status_filter = show_filters()

    patients = filter_patients(
        patients,
        search,
        sex_filter,
        status_filter
    )

    show_patient_table(patients)

    # ==========================================================
    # DIALOG CONTROLLER
    # ==========================================================

    dialog = st.session_state.get("examination_dialog")

    if dialog == "history":

        patient = st.session_state.get(
            "selected_patient"
        )

        if patient:
            show_examination_dialog(patient)

    elif dialog == "view":

        examination = st.session_state.get(
            "selected_examination"
        )

        if examination:
            show_examination_details_dialog(
                examination
            )

    elif dialog == "create":

        patient = st.session_state.get(
            "create_examination_patient"
        )

        if patient:
            show_create_examination_dialog(
                patient
            )


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
                st.session_state["selected_patient"] = patient
                st.session_state["examination_dialog"] = "history"

                st.rerun()

        st.divider()

@st.dialog("Patient Examinations")
def show_examination_dialog(patient):

    # ==========================================================
    # PATIENT INFORMATION
    # ==========================================================

    st.markdown("### Patient Information")

    full_name = " ".join(
        part for part in [
            patient.get("first_name"),
            patient.get("middle_name"),
            patient.get("last_name"),
            patient.get("suffix")
        ]
        if part
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Patient ID**")
        st.write(patient.get("patient_id"))

        st.markdown("**Patient Name**")
        st.write(full_name)

    with col2:
        st.markdown("**Date of Birth**")
        st.write(patient.get("date_of_birth"))

        st.markdown("**Sex**")
        st.write(patient.get("sex"))

    st.divider()

    # ==========================================================
    # EXAMINATION HISTORY
    # ==========================================================

    st.markdown("### Examination History")

    examinations = get_examinations_by_patient(
        patient["patient_id"]
    )

    if not examinations:

        st.info(
            "No examination history found for this patient."
        )

    else:

        for examination in examinations:

            col1, col2, col3, col4 = st.columns(
                [1.5, 2, 1.5, 1]
            )

            with col1:
                st.markdown("**Date**")
                st.write(
                    examination.get("examination_date")
                )

            with col2:
                st.markdown("**Type**")
                st.write(
                    examination.get("examination_type")
                )

            with col3:
                st.markdown("**Status**")
                st.write(
                    examination.get("status")
                )

            with col4:
                st.markdown("**Action**")

                if st.button(
                    "View",
                    key=f"view_exam_{examination['examination_id']}",
                    width="stretch"
                ):
                    st.session_state["selected_examination"] = examination
                    st.session_state["examination_dialog"] = "view"

                    st.rerun()

            st.divider()

    # ==========================================================
    # CREATE EXAMINATION
    # ==========================================================

    st.markdown("### New Examination")

    if st.button(
        "＋ Create Examination",
        width="stretch"
    ):
        st.session_state["create_examination_patient"] = patient
        st.session_state["examination_dialog"] = "create"

        st.rerun()

@st.dialog("Create Examination")
def show_create_examination_dialog(patient):

    # ==========================================================
    # PATIENT INFORMATION
    # ==========================================================

    st.markdown("### Patient Information")

    full_name = " ".join(
        part for part in [
            patient.get("first_name"),
            patient.get("middle_name"),
            patient.get("last_name"),
            patient.get("suffix")
        ]
        if part
    )

    col1, col2 = st.columns(2)

    with col1:

        st.text_input(
            "Patient ID",
            value=str(patient.get("patient_id")),
            disabled=True
        )

        st.text_input(
            "Patient Name",
            value=full_name,
            disabled=True
        )

    with col2:

        st.text_input(
            "Date of Birth",
            value=str(patient.get("date_of_birth")),
            disabled=True
        )

        st.text_input(
            "Sex",
            value=patient.get("sex", ""),
            disabled=True
        )

    st.divider()

    # ==========================================================
    # EXAMINATION INFORMATION
    # ==========================================================

    st.markdown("### Examination Information")

    examination_type = st.selectbox(
        "Examination Type",
        ["Chest X-Ray"]
    )

    examination_date = st.date_input(
        "Examination Date"
    )

    clinical_notes = st.text_area(
        "Clinical Notes",
        placeholder="Enter relevant clinical information..."
    )

    st.divider()

    # ==========================================================
    # ACTION BUTTONS
    # ==========================================================

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "Create Examination",
            width="stretch"
        ):

            try:

                created_by = st.session_state["user"]["user_id"]

                create_examination(
                    patient_id=patient["patient_id"],
                    examination_type=examination_type,
                    examination_date=examination_date,
                    clinical_notes=clinical_notes.strip() or None,
                    created_by=created_by
                )

                st.success(
                    "Examination created successfully!"
                )

                # Remove temporary patient
                st.session_state.pop(
                    "create_examination_patient",
                    None
                )

                st.rerun()

            except Exception as e:

                st.error(
                    f"Failed to create examination: {str(e)}"
                )

    with col2:

        if st.button(
            "Cancel",
            width="stretch"
        ):

            st.session_state.pop(
                "create_examination_patient",
                None
            )

            # Go back to Patient Examinations / History
            st.session_state["examination_dialog"] = "history"

            st.rerun()

@st.dialog("Examination Details")
def show_examination_details_dialog(examination):

    st.markdown("### Examination Information")

    # ==========================================================
    # EXAMINATION INFORMATION
    # ==========================================================

    col1, col2 = st.columns(2)

    with col1:

        st.markdown("**Examination ID**")
        st.write(
            examination.get("examination_id")
        )

        st.markdown("**Examination Type**")
        st.write(
            examination.get("examination_type")
        )

    with col2:

        st.markdown("**Examination Date**")
        st.write(
            examination.get("examination_date")
        )

        st.markdown("**Status**")
        st.write(
            examination.get("status")
        )

    st.divider()

    # ==========================================================
    # CLINICAL NOTES
    # ==========================================================

    st.markdown("### Clinical Notes")

    clinical_notes = st.text_area(
        "Clinical Notes",
        value=examination.get("clinical_notes") or "",
        height=180,
        placeholder="Enter clinical notes..."
    )

    st.divider()

    # ==========================================================
    # ACTION BUTTONS
    # ==========================================================

    col1, col2 = st.columns(2)

    # ----------------------------------------------------------
    # SAVE CHANGES
    # ----------------------------------------------------------

    with col1:

        if st.button(
            "Save Changes",
            width="stretch"
        ):

            try:

                update_examination_clinical_notes(
                    examination_id=examination["examination_id"],
                    clinical_notes=clinical_notes.strip() or None
                )

                # Clear dialog state
                st.session_state.pop(
                    "selected_examination",
                    None
                )

                st.session_state["examination_dialog"] = None

                st.rerun()

            except Exception as e:

                st.error(
                    f"Failed to update clinical notes: {str(e)}"
                )

    # ----------------------------------------------------------
    # CANCEL
    # ----------------------------------------------------------

    with col2:

        if st.button(
            "Cancel",
            width="stretch"
        ):

            # Clear dialog state
            st.session_state.pop(
                "selected_examination",
                None
            )

            st.session_state["examination_dialog"] = "history"

            st.rerun()