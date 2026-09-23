from datetime import date

import streamlit as st

from backend.fetches import get_all_patients, get_all_hospitals
from backend.crud import create_patient, delete_patient, update_patient

from streamlit_app.components.ui import (
    load_css,
    page_header,
    empty_state,
    note,
    full_name,
    format_date,
    table_header,
    table_row,
    name_cell,
    text_cell,
    confirm_buttons,
    remember,
    refresh_data,
    show_flash_message,
)


# Column widths: patient id, name, birth date, sex, contact, hospital, edit, delete
WIDTHS = [1.3, 2.9, 1.5, 0.9, 1.7, 2, 0.5, 0.5]
HEADERS = ["Patient ID", "Name", "Date of birth", "Sex", "Contact", "Hospital", "Actions", ""]

CIVIL_STATUS_OPTIONS = ["Single", "Married", "Widowed", "Separated", "Divorced", "Annulled"]

# Role ids: 1 Superadmin, 3 Radiologist, 4 Radiologic Technologist, 6 and 7 hospital roles
CAN_EDIT_ROLES = [1, 3, 4, 6, 7]
CAN_DELETE_ROLES = [1, 6]

ROLE_SUPERADMIN = 1


# ============================================================
# SMALL HELPERS
# ============================================================

def load_patients():
    """Load all patients. Shows an error and returns [] if it fails."""

    try:
        return get_all_patients() or []

    except Exception as error:
        st.error(f"Unable to load patients: {error}")
        return []


def patient_name(patient):
    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )


def get_user_context():
    """(current_user, is_superadmin, hospital_id, hospital_name)"""

    current_user = st.session_state.get("user") or {}

    role_id = current_user.get("role_id")

    is_superadmin = role_id == ROLE_SUPERADMIN

    hospital_name = current_user.get("hospital_name") or current_user.get("hospital")

    return current_user, is_superadmin, current_user.get("hospital_id"), hospital_name


def find_duplicate_patient(patients, first_name, middle_name, last_name, date_of_birth, hospital_id):
    """A patient in the SAME hospital with the same first, middle, last name and birth date."""

    def clean(value):
        return (value or "").strip().lower()

    target_dob = date_of_birth.isoformat() if date_of_birth else None

    for patient in patients:

        if patient.get("hospital_id") != hospital_id:
            continue

        if (
            clean(patient.get("first_name")) == clean(first_name)
            and clean(patient.get("middle_name")) == clean(middle_name)
            and clean(patient.get("last_name")) == clean(last_name)
            and str(patient.get("date_of_birth") or "")[:10] == target_dob
        ):
            return patient

    return None


# ============================================================
# REGISTER / EDIT FORM (one form for both)
# ============================================================

def render_patient_form(patient=None):
    """patient=None registers a new patient; otherwise edits that patient."""

    is_edit = patient is not None
    patient = patient or {}

    current_user, is_superadmin, editor_hospital_id, editor_hospital_name = get_user_context()

    hospital_options = {
        hospital["hospital_name"]: hospital["hospital_id"]
        for hospital in (get_all_hospitals() or [])
        if hospital
    }

    hospital_names = list(hospital_options.keys())
    hospital_by_id = {hospital_id: name for name, hospital_id in hospital_options.items()}

    hospital_index = (
        hospital_names.index(hospital_by_id[patient["hospital_id"]])
        if patient.get("hospital_id") in hospital_by_id
        else 0
    )

    # starting values
    try:
        dob_start = date.fromisoformat(str(patient.get("date_of_birth"))[:10])
    except ValueError:
        dob_start = date(2000, 1, 1)

    civil_start = patient.get("civil_status") or "Single"

    errors = st.container()

    with st.form("patient_form", clear_on_submit=False):

        first_col, middle_col, last_col, suffix_col = st.columns([2, 2, 2, 1])

        first_name = first_col.text_input("First name *", value=patient.get("first_name") or "")
        middle_name = middle_col.text_input("Middle name", value=patient.get("middle_name") or "")
        last_name = last_col.text_input("Last name *", value=patient.get("last_name") or "")
        suffix = suffix_col.text_input("Suffix", value=patient.get("suffix") or "", placeholder="Jr.")

        dob_col, sex_col, civil_col = st.columns(3)

        birthdate = dob_col.date_input(
            "Date of birth *",
            value=dob_start,
            min_value=date(1900, 1, 1),
            max_value=date.today(),
            format="YYYY-MM-DD",
        )

        sex = sex_col.selectbox("Sex", ["Male", "Female"], index=0 if patient.get("sex") != "Female" else 1)

        civil_status = civil_col.selectbox(
            "Civil status",
            CIVIL_STATUS_OPTIONS,
            index=CIVIL_STATUS_OPTIONS.index(civil_start) if civil_start in CIVIL_STATUS_OPTIONS else 0,
        )

        job_col, nation_col, religion_col = st.columns(3)

        occupation = job_col.text_input("Occupation", value=patient.get("occupation") or "")
        nationality = nation_col.text_input("Nationality", value=patient.get("nationality") or "Filipino")
        religion = religion_col.text_input("Religion", value=patient.get("religion") or "")

        contact_col, address_col = st.columns([1, 2])

        contact_number = contact_col.text_input(
            "Contact number", value=patient.get("contact_number") or "", placeholder="+63 000 000 0000"
        )
        address = address_col.text_input("Address", value=patient.get("address") or "")

        emergency_name_col, emergency_number_col = st.columns(2)

        emergency_name = emergency_name_col.text_input(
            "Emergency contact name", value=patient.get("emergency_contact_name") or ""
        )
        emergency_number = emergency_number_col.text_input(
            "Emergency contact number", value=patient.get("emergency_contact_no") or ""
        )

        # ------------------------------------------------------------
        # HOSPITAL FIELD
        # Superadmin -> dropdown (they must pick)
        # Everyone else -> hidden, auto-assigned from their profile
        # ------------------------------------------------------------

        selected_hospital = None

        if is_superadmin:
            if hospital_names:
                selected_hospital = st.selectbox("Hospital *", hospital_names, index=hospital_index)
            else:
                st.warning("No hospitals registered yet.")

        cancel_col, save_col = st.columns(2)

        cancel = cancel_col.form_submit_button("Cancel", width="stretch")
        submitted = save_col.form_submit_button(
            "Save changes" if is_edit else "Register patient", type="primary", width="stretch"
        )

    if cancel:
        st.rerun()

    if not submitted:
        return

    # ---- validation ----

    if not first_name.strip() or not last_name.strip():
        errors.error("First name and last name are required.")
        return

    if is_superadmin:
        # Superadmin: hospital comes from the dropdown
        if selected_hospital:
            hospital_id = hospital_options[selected_hospital]
        elif is_edit:
            hospital_id = None
        else:
            errors.error("Please select a hospital.")
            return
    else:
        # All other roles: hospital comes from their profile
        if editor_hospital_id is None:
            errors.error("Your account is not assigned to a hospital. Please contact your Superadmin.")
            return
        hospital_id = editor_hospital_id

    # The fields that are the same for "create" and "update"
    details = dict(
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
        emergency_contact_name=emergency_name.strip() or None,
        emergency_contact_no=emergency_number.strip() or None,
        hospital_id=hospital_id,
    )

    try:

        if is_edit:
            update_patient(patient_id=patient["patient_id"], **details)
            remember("Patient updated.")

        else:
            duplicate = find_duplicate_patient(
                get_all_patients() or [],
                first_name, middle_name, last_name, birthdate, hospital_id,
            )

            if duplicate:
                errors.error(
                    "A patient with the same name and date of birth already exists: "
                    f"{patient_name(duplicate)} (code {duplicate.get('patient_code') or '—'})."
                )
                return

            create_patient(created_by=current_user["user_id"], **details)
            remember("Patient registered.")

        st.rerun()

    except Exception as error:
        errors.error(f"Failed to save patient: {error}")


@st.dialog("Register patient", width="medium")
def show_add_patient_form():
    with st.container(key="sa_dialog"):
        render_patient_form()


@st.dialog("Edit patient", width="medium")
def show_edit_patient_dialog(patient):
    with st.container(key="sa_dialog"):
        render_patient_form(patient)


@st.dialog("Delete patient", width="small")
def show_delete_patient_dialog(patient):

    with st.container(key="sa_dialog"):

        st.markdown(
            f"<p class='sa-dialog-text'>Delete <b>{patient_name(patient)}</b>?</p>",
            unsafe_allow_html=True,
        )

        note("This permanently removes the patient record from the system.", "red")

        if confirm_buttons(f"delete_patient_{patient['patient_id']}", "Delete patient"):
            try:
                delete_patient(patient["patient_id"])
                remember("Patient deleted.")
                st.rerun()
            except Exception as error:
                st.error(f"Failed to delete patient: {error}")


# ============================================================
# FILTERS + TABLE
# ============================================================

def show_filters(patients):
    """Search, sex and status. Returns the matching patients."""

    search_col, sex_col, status_col, reset_col = st.columns([3, 1.2, 1.2, 1])

    search = search_col.text_input(
        "Search", placeholder="Search by name or contact number",
        label_visibility="collapsed", key="patients_search",
    ).strip().lower()

    sex = sex_col.selectbox("Sex", ["All sexes", "Male", "Female"], label_visibility="collapsed", key="patients_sex")

    status = status_col.selectbox(
        "Status", ["All status", "Active", "Inactive"], label_visibility="collapsed", key="patients_status"
    )

    if reset_col.button("Refresh", icon=":material/refresh:", width="stretch", key="patients_refresh"):
        refresh_data()

    matches = []

    for patient in patients:

        text = f"{patient_name(patient)} {patient.get('contact_number') or ''}".lower()

        if search and search not in text:
            continue
        if sex != "All sexes" and patient.get("sex") != sex:
            continue
        if status != "All status" and patient.get("status") != status:
            continue

        matches.append(patient)

    return matches


def render_patient_table(patients, role_id):

    if not patients:
        empty_state("No patients found.")
        return

    can_edit = role_id in CAN_EDIT_ROLES
    can_delete = role_id in CAN_DELETE_ROLES

    with st.container(key="sa_table_patients"):

        table_header(HEADERS, WIDTHS, "patients")

        for patient in patients:

            patient_id = patient.get("patient_id")
            name = patient_name(patient)

            with table_row(f"patients_{patient_id}", WIDTHS) as cols:

                text_cell(cols[0], patient.get("patient_code") or "Not assigned", muted=True)
                name_cell(cols[1], name)
                text_cell(cols[2], format_date(patient.get("date_of_birth")))
                text_cell(cols[3], patient.get("sex"))
                text_cell(cols[4], patient.get("contact_number"))
                text_cell(cols[5], (patient.get("hospitals") or {}).get("hospital_name"))

                if can_edit:
                    if cols[6].button("", key=f"edit_{patient_id}", icon=":material/edit:", help="Edit patient"):
                        show_edit_patient_dialog(patient)

                if can_delete:
                    if cols[7].button("", key=f"delete_{patient_id}", icon=":material/delete:", help="Delete patient"):
                        show_delete_patient_dialog(patient)


# ============================================================
# PAGE
# ============================================================

def show():

    load_css("manage_patients.css")
    show_flash_message()

    current_user, _, current_hospital_id, _ = get_user_context()

    role_id = current_user.get("role_id")

    with st.container(key="sa_page"):

        if page_header(
            "Manage patients",
            "View and manage registered patients.",
            "Register patient", "register_patient_button", "person_add",
        ):
            show_add_patient_form()

        patients = load_patients()

        # Everyone except the Superadmin only sees their own hospital
        if role_id != ROLE_SUPERADMIN:

            if current_hospital_id is None:
                st.error("Your account is not assigned to a hospital. Please contact your Superadmin.")
                st.stop()

            patients = [p for p in patients if p.get("hospital_id") == current_hospital_id]

        matches = show_filters(patients)

        render_patient_table(matches, role_id)