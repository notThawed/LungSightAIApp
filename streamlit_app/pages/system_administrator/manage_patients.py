import streamlit as st
import pandas as pd

from backend.fetches import get_all_patients, generate_patient_id, get_all_hospitals
from datetime import date
from backend.crud import create_patient, delete_patient, update_patient


def show():

    st.title("Manage Patients")
    st.caption("View and manage registered patients.")

    # ==========================================
    # CURRENT USER CONTEXT
    # ==========================================

    current_user = st.session_state.get("user") or {}

    current_role = (
        current_user.get("role") or ""
    ).strip().lower()

    current_hospital_id = current_user.get("hospital_id")

    is_hospital_admin = (current_role == "hospital admin")

    # ==========================================
    # ACTIONS + SEARCH
    # ==========================================

    show_patient_actions()

    search, sex_filter, status_filter = show_search_bar()

    # ==========================================
    # LOAD + SCOPE
    # ==========================================

    patients = load_patients()

    role_id = current_user.get("role_id")

    is_superadmin = (role_id == 1)

    if not is_superadmin:

        if current_hospital_id is None:
            st.error(
                "Your account is not assigned to a hospital. "
                "Please contact your Superadmin."
            )
            st.stop()

        patients = [
            p for p in patients
            if p.get("hospital_id") == current_hospital_id
        ]

    # ==========================================
    # FILTER
    # ==========================================

    patients = filter_patients(
        patients,
        search,
        sex_filter,
        status_filter
    )

    role_id = current_user.get("role_id")

    show_patient_table(patients, role_id)


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

def show_patient_table(patients, role_id):
    if not patients:
        st.info("No patients registered.")
        return

    # ==========================================================
    # ROLE PERMISSIONS
    # ==========================================================

    # Role 1 = Superadmin
    # Role 3 = Radiologist
    # Role 4 = Radiologic Technologist

    can_edit = role_id in [1, 3, 4, 6, 7]
    can_delete = role_id in [1, 6]

    # ==========================================================
    # TABLE HEADER
    # ==========================================================

    if can_delete:

        # ------------------------------------------------------
        # SUPERADMIN TABLE
        # ------------------------------------------------------

        col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(
            [1.5, 2.5, 1.5, 1, 2, 1.5, 0.8, 0.8]
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
            st.markdown("**Hospital**")

        with col7:
            st.markdown("**Edit**")

        with col8:
            st.markdown("**Delete**")

    else:

        # ------------------------------------------------------
        # RADIOLOGIST / RADIOLOGIC TECHNOLOGIST TABLE
        # ------------------------------------------------------

        col1, col2, col3, col4, col5, col6, col7 = st.columns(
            [1.5, 2.5, 1.5, 1, 2, 1.5, 0.8]
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
            st.markdown("**Hospital**")

        with col7:
            st.markdown("**Edit**")

    st.divider()

    # ==========================================================
    # PATIENT ROWS
    # ==========================================================

    for patient in patients:

        patient_id = patient.get("patient_id")

        patient_code = patient.get("patient_code")

        if not patient_code:
            patient_code = "Not Assigned"

        full_name = " ".join(
            part
            for part in [
                patient.get("first_name"),
                patient.get("middle_name"),
                patient.get("last_name"),
                patient.get("suffix")
            ]
            if part
        )

        # ======================================================
        # SUPERADMIN
        # ======================================================

        if can_delete:

            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(
                [1.5, 2.5, 1.5, 1, 2, 1.5, 0.8, 0.8]
            )

            # --------------------------------------------------
            # PATIENT ID
            # --------------------------------------------------

            with col1:
                st.write(patient_code)

            # --------------------------------------------------
            # PATIENT NAME
            # --------------------------------------------------

            with col2:
                st.write(full_name)

            # --------------------------------------------------
            # DATE OF BIRTH
            # --------------------------------------------------

            with col3:
                st.write(patient.get("date_of_birth"))

            # --------------------------------------------------
            # SEX
            # --------------------------------------------------

            with col4:
                st.write(patient.get("sex"))

            # --------------------------------------------------
            # CONTACT NUMBER
            # --------------------------------------------------

            with col5:
                st.write(patient.get("contact_number") or "—")

            # --------------------------------------------------
            # HOSPITAL  ← NEW
            # --------------------------------------------------

            with col6:

                hospital_data = patient.get("hospitals") or {}

                st.write(
                    hospital_data.get("hospital_name") or "—"
                )

            # --------------------------------------------------
            # EDIT
            # --------------------------------------------------

            with col7:

                if can_edit:

                    if st.button(
                        "✏️",
                        key=f"edit_{patient_id}",
                        help="Edit patient"
                    ):
                        show_edit_patient_dialog(patient)

            # --------------------------------------------------
            # DELETE
            # --------------------------------------------------

            with col8:

                if st.button(
                    "🗑️",
                    key=f"delete_{patient_id}",
                    help="Delete patient"
                ):
                    show_delete_patient_dialog(patient)

        # ======================================================
        # RADIOLOGIST / RADIOLOGIC TECHNOLOGIST
        # ======================================================

        else:

            col1, col2, col3, col4, col5, col6, col7 = st.columns(
                [1.5, 2.5, 1.5, 1, 2, 1.5, 0.8]
            )

            # --------------------------------------------------
            # PATIENT ID
            # --------------------------------------------------

            with col1:
                st.write(patient_code)

            # --------------------------------------------------
            # PATIENT NAME
            # --------------------------------------------------

            with col2:
                st.write(full_name)

            # --------------------------------------------------
            # DATE OF BIRTH
            # --------------------------------------------------

            with col3:
                st.write(patient.get("date_of_birth"))

            # --------------------------------------------------
            # SEX
            # --------------------------------------------------

            with col4:
                st.write(patient.get("sex"))

            # --------------------------------------------------
            # CONTACT NUMBER
            # --------------------------------------------------

            with col5:
                st.write(patient.get("contact_number") or "—")

            # --------------------------------------------------
            # HOSPITAL  ← NEW
            # --------------------------------------------------

            with col6:

                hospital_data = patient.get("hospitals") or {}

                st.write(
                    hospital_data.get("hospital_name") or "—"
                )

            # --------------------------------------------------
            # EDIT ONLY
            # --------------------------------------------------

            with col7:
                if can_edit:
                    if st.button(
                        "✏️",
                        key=f"edit_{patient_id}",
                        help="Edit patient"
                    ):
                        show_edit_patient_dialog(patient)

        st.divider()
    
@st.dialog("Edit Patient")
def show_edit_patient_dialog(patient):

    # ------------------------------------------
    # CURRENT USER + HOSPITALS
    # ------------------------------------------

    current_user = st.session_state.get("user") or {}

    current_role = (
        current_user.get("role") or ""
    ).strip().lower()

    is_hospital_admin = (current_role == "hospital admin")

    editor_hospital_id = current_user.get("hospital_id")

    editor_hospital_name = (
        current_user.get("hospital_name")
        or current_user.get("hospital")
        or None
    )

    hospitals = get_all_hospitals() or []

    hospital_options = {
        h["hospital_name"]: h["hospital_id"]
        for h in hospitals
        if h
    }

    hospital_names = list(hospital_options.keys())

    patient_hospital_id = patient.get("hospital_id")

    patient_hospital_name = next(
        (
            name
            for name, hid in hospital_options.items()
            if hid == patient_hospital_id
        ),
        None
    )

    current_hospital_index = (
        hospital_names.index(patient_hospital_name)
        if patient_hospital_name in hospital_names
        else 0
    )

    # ------------------------------------------
    # FORM
    # ------------------------------------------

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

    col1, col2, col3 = st.columns(3)

    dob_raw = patient.get("date_of_birth")

    if isinstance(dob_raw, str) and dob_raw:
        try:
            dob_value = date.fromisoformat(dob_raw[:10])
        except ValueError:
            dob_value = date(2000, 1, 1)
    elif isinstance(dob_raw, date):
        dob_value = dob_raw
    else:
        dob_value = date(2000, 1, 1)

    with col1:
        birthdate = st.date_input(
            "Date of Birth",
            value=dob_value,
            min_value=date(1900, 1, 1),
            max_value=date.today(),
            format="YYYY-MM-DD"
        )

    with col2:
        sex = st.selectbox(
            "Sex",
            ["Male", "Female"],
            index=(0 if patient.get("sex") == "Male" else 1)
        )

    CIVIL_STATUS_OPTIONS = [
        "Single",
        "Married",
        "Widowed",
        "Separated",
        "Divorced",
        "Annulled"
    ]

    current_civil_status = patient.get("civil_status") or "Single"

    civil_index = (
        CIVIL_STATUS_OPTIONS.index(current_civil_status)
        if current_civil_status in CIVIL_STATUS_OPTIONS
        else 0
    )

    with col3:
        civil_status = st.selectbox(
            "Civil Status",
            CIVIL_STATUS_OPTIONS,
            index=civil_index
        )

    col1, col2, col3 = st.columns(3)

    with col1:
        occupation = st.text_input(
            "Occupation",
            value=patient.get("occupation") or "",
            placeholder="e.g. Student, Teacher, Engineer"
        )

    with col2:
        nationality = st.text_input(
            "Nationality",
            value=patient.get("nationality") or "Filipino"
        )

    with col3:
        religion = st.text_input(
            "Religion",
            value=patient.get("religion") or "",
            placeholder="e.g. Roman Catholic"
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

    # ======================================
    # HOSPITAL ASSIGNMENT  ← NEW
    # ======================================

    st.markdown("### Hospital Assignment")

    if is_hospital_admin:

        if editor_hospital_name is None:
            editor_hospital_name = next(
                (
                    name
                    for name, hid in hospital_options.items()
                    if hid == editor_hospital_id
                ),
                None
            )

        st.info(
            f"This patient belongs to your hospital: "
            f"**{editor_hospital_name or editor_hospital_id or '—'}**"
        )

        selected_hospital = None

    else:

        if not hospital_names:
            st.warning("No hospitals registered yet.")
            selected_hospital = None
        else:
            selected_hospital = st.selectbox(
                "Assign to Hospital",
                hospital_names,
                index=current_hospital_index
            )

    # ======================================
    # BUTTONS
    # ======================================

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

        # ----------------------------------
        # HOSPITAL  ← NEW
        # ----------------------------------

        if is_hospital_admin:

            if editor_hospital_id is None:
                st.error(
                    "Your account is not assigned to a hospital. "
                    "Please contact your Superadmin."
                )
                return

            hospital_id = editor_hospital_id

        else:

            if selected_hospital:
                hospital_id = hospital_options[selected_hospital]
            else:
                hospital_id = None

        try:

            update_patient(
                patient_id=patient["patient_id"],
                first_name=first_name.strip(),
                middle_name=middle_name.strip() or None,
                last_name=last_name.strip(),
                suffix=suffix.strip() or None,
                date_of_birth=birthdate,
                sex=sex,
                civil_status=civil_status or None,
                occupation=occupation.strip() or None,
                nationality=nationality.strip() or None,
                religion=religion.strip() or None,
                contact_number=contact_number.strip() or None,
                address=address.strip() or None,
                emergency_contact_name=(
                    emergency_contact_name.strip() or None
                ),
                emergency_contact_no=(
                    emergency_contact_number.strip() or None
                ),
                hospital_id=hospital_id,          # ← NEW
            )

            st.success("Patient updated successfully!")
            st.rerun()

        except Exception as e:
            st.error(f"Failed to update patient: {str(e)}")

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


def find_duplicate_patient(
    patients,
    first_name,
    middle_name,
    last_name,
    date_of_birth,
    hospital_id,
):
    """
    Return the first patient in the SAME HOSPITAL that
    matches ALL FOUR: first_name + middle_name + last_name + DOB.
    Returns None if no match.
    """

    target_first = (first_name or "").strip().lower()
    target_middle = (middle_name or "").strip().lower()
    target_last = (last_name or "").strip().lower()

    target_dob = (
        date_of_birth.isoformat()
        if date_of_birth else None
    )

    for p in patients:

        # Only compare within the same hospital
        if p.get("hospital_id") != hospital_id:
            continue

        p_first = (p.get("first_name") or "").strip().lower()
        p_middle = (p.get("middle_name") or "").strip().lower()
        p_last = (p.get("last_name") or "").strip().lower()

        p_dob = p.get("date_of_birth") or ""

        if isinstance(p_dob, str):
            p_dob = p_dob[:10]
        else:
            p_dob = str(p_dob)

        if (
            p_first == target_first
            and p_middle == target_middle
            and p_last == target_last
            and p_dob == target_dob
        ):
            return p

    return None


@st.dialog("Register New Patient")
def show_add_patient_form():

    st.subheader("Register New Patient")

    # ------------------------------------------
    # CURRENT USER + HOSPITALS
    # ------------------------------------------

    current_user = st.session_state.get("user") or {}

    current_role = (
        current_user.get("role") or ""
    ).strip().lower()

    is_hospital_admin = (current_role == "hospital admin")

    current_hospital_id = current_user.get("hospital_id")

    current_hospital_name = (
        current_user.get("hospital_name")
        or current_user.get("hospital")
        or None
    )

    hospitals = get_all_hospitals() or []

    hospital_options = {
        h["hospital_name"]: h["hospital_id"]
        for h in hospitals
        if h
    }

    with st.form(
        "add_patient_form",
        clear_on_submit=True
    ):
        st.markdown("### Personal Information")

        col1, col2, col3 = st.columns(3)

        with col1:
            first_name = st.text_input("First Name")

        with col2:
            middle_name = st.text_input("Middle Name")

        with col3:
            last_name = st.text_input("Last Name")

        suffix = st.text_input(
            "Suffix",
            placeholder="Jr., Sr., III"
        )

        col1, col2, col3 = st.columns(3)

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
                ["Male", "Female"]
            )

        with col3:
            civil_status = st.selectbox(
                "Civil Status",
                [
                    "Single",
                    "Married",
                    "Widowed",
                    "Separated",
                    "Divorced",
                    "Annulled"
                ]
            )

        col1, col2 = st.columns(2)

        with col1:
            occupation = st.text_input(
                "Occupation",
                placeholder="e.g. Student, Teacher, Engineer"
            )

        with col2:
            nationality = st.text_input(
                "Nationality",
                value="Filipino"
            )

        religion = st.text_input(
            "Religion",
            placeholder="e.g. Roman Catholic, Islam, INC"
        )

        st.markdown("### CONTACT INFORMATION")

        contact_number = st.text_input(
            "Contact Number",
            placeholder="+63 000 000 0000"
        )

        address = st.text_input("Address")

        emergency_contact_name = st.text_input(
            "Emergency Contact Name"
        )

        emergency_contact_number = st.text_input(
            "Emergency Contact Number",
            placeholder="+63 000 000 0000"
        )

        # ======================================
        # HOSPITAL ASSIGNMENT
        # ======================================

        st.markdown("### Hospital Assignment")

        if is_hospital_admin:

            if current_hospital_name is None:
                current_hospital_name = next(
                    (
                        name
                        for name, hid in hospital_options.items()
                        if hid == current_hospital_id
                    ),
                    None
                )

            st.info(
                f"This patient will be registered under your hospital: "
                f"**{current_hospital_name or current_hospital_id or '—'}**"
            )

            selected_hospital = None

        else:

            if not hospital_options:
                st.warning(
                    "No hospitals registered yet. "
                    "Please create a hospital first."
                )
                selected_hospital = None
            else:
                selected_hospital = st.selectbox(
                    "Register under Hospital",
                    options=list(hospital_options.keys())
                )

        # ======================================
        # BUTTONS
        # ======================================

        col1, col2 = st.columns(2)

        with col1:
            submitted = st.form_submit_button(
                "Register Patient",
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

            # ----------------------------------
            # REQUIRED FIELDS
            # ----------------------------------

            if not first_name.strip():
                st.error("First name required.")
                return

            if not last_name.strip():
                st.error("Last name required.")
                return

            if birthdate is None:
                st.error("Birth Date is required.")
                return

            # ----------------------------------
            # HOSPITAL
            # ----------------------------------

            if is_hospital_admin:

                if current_hospital_id is None:
                    st.error(
                        "Your account is not assigned to a hospital. "
                        "Please contact your Superadmin."
                    )
                    return

                hospital_id = current_hospital_id

            else:

                if not selected_hospital:
                    st.error("Please select a hospital.")
                    return

                hospital_id = hospital_options[selected_hospital]

            # ----------------------------------
            # DUPLICATE CHECK
            # ----------------------------------

            all_patients = get_all_patients() or []

            duplicate = find_duplicate_patient(
                all_patients,
                first_name.strip(),
                middle_name.strip(),
                last_name.strip(),
                birthdate,
                hospital_id,          # ← NEW
            )

            if duplicate:

                st.error(
                    f"A patient with the same name and date of birth "
                    f"already exists: "
                    f"**{duplicate.get('first_name')} "
                    f"{duplicate.get('middle_name') or ''} "
                    f"{duplicate.get('last_name')}** "
                    f"(Code: `{duplicate.get('patient_code') or '—'}`, "
                    f"DOB: `{duplicate.get('date_of_birth') or '—'}`)."
                )

                return

            # ----------------------------------
            # CREATE
            # ----------------------------------

            try:

                create_patient(
                    first_name=first_name.strip(),
                    middle_name=middle_name.strip() or None,
                    last_name=last_name.strip(),
                    suffix=suffix.strip() or None,
                    date_of_birth=birthdate,
                    sex=sex,
                    civil_status=civil_status or None,
                    occupation=occupation.strip() or None,
                    nationality=nationality.strip() or None,
                    religion=religion.strip() or None,
                    contact_number=contact_number.strip() or None,
                    address=address.strip() or None,
                    emergency_contact_name=(
                        emergency_contact_name.strip() or None
                    ),
                    emergency_contact_no=(
                        emergency_contact_number.strip() or None
                    ),
                    created_by=st.session_state["user"]["user_id"],
                    hospital_id=hospital_id,
                )

                st.success("Patient registered successfully!")
                st.rerun()

            except Exception as e:
                st.error(f"Failed to register patient: {str(e)}")
                    
