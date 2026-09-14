import streamlit as st
import pandas as pd

from backend.fetches import get_all_patients
from datetime import date
from backend.crud import create_patient, delete_patient, update_patient


def show():
    st.title("Manage Patients")
    st.caption("View and manage registered patients.")

    show_patient_actions()

    search, sex_filter, status_filter = show_search_bar()

    patients = load_patients()

    patients = filter_patients(
        patients,
        search,
        sex_filter,
        status_filter
    )

    show_patient_table(patients)


def load_patients():

    print("=== load_patients() START ===")

    try:

        patients = get_all_patients()

        print("=== get_all_patients() RETURNED ===")
        print("Patients:", patients)
        print("Number of patients:", len(patients))

        return patients

    except Exception as e:

        print("=== ERROR ===")
        print(repr(e))

        st.error(
            f"Unable to load patients: {str(e)}"
        )

def create_patient_table(patients):
    if not patients:
        return pd.DataFrame(
            columns=[
                "Patient ID",
                "Patient Name",
                "Date of Birth",
                "Sex",
                "Contact Number",
                "Status"
            ]
        )

    rows = []

    for patient in patients:
        full_name = " ".join(
            part for part in [
                patient.get("first_name"),
                patient.get("middle_name"),
                patient.get("last_name"),
                patient.get("suffix")
            ]
            if part
        )

        rows.append({
            "Patient ID": patient.get("patient_id"),
            "Patient Name": full_name,
            "Date of Birth": patient.get("date_of_birth"),
            "Sex": patient.get("sex"),
            "Contact Number": patient.get("contact_number"),
            "Status": patient.get("status")
        })

    return pd.DataFrame(rows)

def show_search_bar():
    """
    Display patient search and filter controls.
    """

    col1, col2, col3, col4 = st.columns([3, 1.2, 1.2, 1])

    with col1:
        search = st.text_input(
            "Search Patient",
            placeholder="Search by name or contact number...",
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
        reset = st.button(
            "↻ Reset",
            width="stretch"
        )

    if reset:
        st.rerun()

    return search, sex_filter, status_filter

def filter_patients(patients, search, sex_filter, status_filter):

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

        # Search filter
        if search:
            if search not in full_name and search not in contact:
                continue

        # Sex filter
        if sex_filter != "All":
            if patient.get("sex") != sex_filter:
                continue

        # Status filter
        if status_filter != "All":
            if patient.get("status") != status_filter:
                continue

        filtered.append(patient)

    return filtered

def show_patient_table(patients, is_admin=True):
    if not patients:
        st.info("No patients registered.")
        return

    if is_admin:
        col1, col2, col3, col4, col5, col6, col7 = st.columns(
            [1.5, 2.5, 1.5, 1, 2, 0.8, 0.8]
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
            st.markdown("**Edit**")

        with col7:
            st.markdown("**Delete**")

        st.divider()

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

            col1, col2, col3, col4, col5, col6, col7 = st.columns(
                [1.5, 2.5, 1.5, 1, 2, 0.8, 0.8]
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
                st.write(patient.get("contact_number") or "—")

            with col6:
                if st.button(
                    "✏️",
                    key=f"edit_{patient_id}",
                    help="Edit patient"
                ):
                    show_edit_patient_dialog(patient)

            with col7:
                if st.button(
                    "🗑️",
                    key=f"delete_{patient_id}",
                    help="Delete patient"
                ):
                    show_delete_patient_dialog(patient)

            st.divider()

    else:
        # RadTech table
        col1, col2, col3, col4, col5, col6 = st.columns(
            [1.5, 2.5, 1.5, 1, 2, 0.8]
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
            st.markdown("**Edit**")

        st.divider()

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
                [1.5, 2.5, 1.5, 1, 2, 0.8]
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
                st.write(patient.get("contact_number") or "—")

            with col6:
                if st.button(
                    "✏️",
                    key=f"edit_{patient_id}",
                    help="Edit patient"
                ):
                    show_edit_patient_dialog(patient)

            st.divider()
    

@st.dialog("Edit Patient")
def show_edit_patient_dialog(patient):

    st.markdown("### Personal Information")

    col1, col2, col3 = st.columns(3)

    with col1:
        first_name = st.text_input(
            "First Name",
            value=patient.get("first_name") or ""
        )

    with col2:
        middle_name = st.text_input(
            "Middle Name",
            value=patient.get("middle_name") or ""
        )

    with col3:
        last_name = st.text_input(
            "Last Name",
            value=patient.get("last_name") or ""
        )

    suffix = st.text_input(
        "Suffix",
        value=patient.get("suffix") or "",
        placeholder="Jr., Sr., III"
    )

    col1, col2 = st.columns(2)

    with col1:
        birthdate = st.date_input(
            "Date of Birth",
            value=patient.get("date_of_birth")
        )

    with col2:
        sex = st.selectbox(
            "Sex",
            ["Male", "Female"],
            index=(
                0 if patient.get("sex") == "Male"
                else 1
            )
        )

    st.markdown("### Contact Information")

    contact_number = st.text_input(
        "Contact Number",
        value=patient.get("contact_number") or "",
        placeholder="+63 000 000 0000"
    )

    address = st.text_input(
        "Address",
        value=patient.get("address") or ""
    )

    emergency_contact_name = st.text_input(
        "Emergency Contact Name",
        value=patient.get("emergency_contact_name") or ""
    )

    emergency_contact_number = st.text_input(
        "Emergency Contact Number",
        value=patient.get("emergency_contact_no") or "",
        placeholder="+63 000 000 0000"
    )

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

        if not first_name.strip():
            st.error("First name is required.")
            return

        if not last_name.strip():
            st.error("Last name is required.")
            return

        try:
            update_patient(
                patient_id=patient["patient_id"],
                first_name=first_name.strip(),
                middle_name=middle_name.strip() or None,
                last_name=last_name.strip(),
                suffix=suffix.strip() or None,
                date_of_birth=birthdate,
                sex=sex,
                contact_number=contact_number.strip() or None,
                address=address.strip() or None,
                emergency_contact_name=(
                    emergency_contact_name.strip() or None
                ),
                emergency_contact_no=(
                    emergency_contact_number.strip() or None
                )
            )

            st.success("Patient updated successfully!")

            st.rerun()

        except Exception as e:
            st.error(
                f"Failed to update patient: {str(e)}"
            )

@st.dialog("Delete Patient")
def show_delete_patient_dialog(patient):

    full_name = " ".join(
        part for part in [
            patient.get("first_name"),
            patient.get("middle_name"),
            patient.get("last_name"),
            patient.get("suffix")
        ]
        if part
    )

    st.warning(
        f"Are you sure you want to delete **{full_name}**?"
    )

    st.write(
        "This action will permanently remove the patient "
        "record from the system."
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "Delete Patient",
            width="stretch"
        ):
            try:
                delete_patient(patient["patient_id"])

                st.success(
                    "Patient deleted successfully!"
                )

                st.rerun()

            except Exception as e:
                st.error(
                    f"Failed to delete patient: {str(e)}"
                )

    with col2:
        if st.button(
            "Cancel",
            width="stretch"
        ):
            st.rerun()

def show_patient_actions():

    col1, col2 = st.columns([1, 1])

    with col1:

        if st.button(
            "＋ Register Patient",
            use_container_width=True
        ):

            show_add_patient_form()

    with col2:

        if st.button(
            "↻ Refresh",
            use_container_width=True
        ):

            st.rerun()

@st.dialog("Register New Patient")
def show_add_patient_form():
    st.subheader("OTEN")

    with st.form(
        "add_patient_form",
        clear_on_submit = True
    ):
        st.markdown(
            "### Personal Information"
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            first_name = st.text_input(
                "First Name"
            )

        with col2:
            middle_name = st.text_input(
                "Middle Name"
            )

        with col3:
            last_name = st.text_input(
                "Last Name"
            )

        suffix = st.text_input(
            "Suffix",
            placeholder = "Jr., Sr., III"
        )

        col1, col2 = st.columns(2)

        with col1:
            birthdate = st.date_input(
                "Date of Birth",
                value=date(2000, 1, 1),
                min_value=date(1900, 1, 1),
                max_value=date.today(),
                format="YYYY-MM-DD"
            )

        with col2:
            sex = st.selectbox(
                "Sex",
                [
                    "Male",
                    "Female"
                ]
            )

        st.markdown(
            '### CONTACT INFORMATION'
        )
        contact_number = st.text_input(
            "Contact Number",
            placeholder = "+63 000 000 0000"
        )

        address = st.text_input(
            "Address"
        )

        emergency_contact_name = st.text_input(
            "Emergency Contact Name"
        )

        emergency_contact_number = st.text_input(
            "Emergency Contact Number",
            placeholder = "+63 000 000 0000"
        )

        #BUTTONS
        col1, col2 = st.columns(2)

        with col1:
            submitted = st.form_submit_button(
                "Register Patient",
                width = "stretch"
            )

        with col2:
            cancel = st.form_submit_button(
                "Cancel",
                width = "stretch"
            )

        if cancel:
            st.rerun()

        if submitted:

            if not first_name.strip():
                st.error("First name required.")
                return

            if not last_name.strip():
                st.error("Last name required.")
                return

            if birthdate is None:
                st.error("Birth Date is required.")
                return

            try:
                result = create_patient(
                    first_name=first_name.strip(),
                    middle_name=middle_name.strip() or None,
                    last_name=last_name.strip(),
                    suffix=suffix.strip() or None,
                    date_of_birth=birthdate,
                    sex=sex,
                    contact_number=contact_number.strip() or None,
                    address=address.strip() or None,
                    emergency_contact_name=(
                        emergency_contact_name.strip() or None
                    ),
                    emergency_contact_no=(
                        emergency_contact_number.strip() or None
                    ),
                    created_by = st.session_state["user"]["user_id"]
                )

                st.success("Patient registered successfully!")

                st.write("Database response:", result)

            except Exception as e:

                st.error(
                    f"Failed to register patient: {str(e)}"
                )
                    
