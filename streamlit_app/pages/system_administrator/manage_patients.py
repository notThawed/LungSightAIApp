from datetime import date

import streamlit as st

from backend.fetches import (
    get_all_patients,
    get_all_hospitals,
)

from backend.crud import (
    create_patient,
    delete_patient,
    update_patient,
)

from streamlit_app.components.ui import (
    page_header,
    empty_state,
    note,
    full_name,
    format_date,
    table_header,
    table_row,
    confirm_buttons,
    close_button,
    remember,
    refresh_data,
    show_flash_message,
    initials,
    safe,
    pill,
    metric_card,
)

from shared.assets import load_css

from backend.backend_utils.subscription_usage import (
    can_register_patient,
)


# ============================================================
# TABLE CONFIGURATION
# ============================================================

WIDTHS = [
    1.2,   # Patient ID
    2.8,   # Patient Name, Avatar & Demographics
    1.35,  # Date of Birth & Age
    0.85,  # Sex
    1.5,   # Contact
    1.8,   # Hospital
    0.95,  # Status
    1.35,  # Actions (View, Edit, Delete)
]

HEADERS = [
    "Patient ID",
    "Patient",
    "Date of Birth",
    "Sex",
    "Contact",
    "Hospital",
    "Status",
    "Actions",
]


def calculate_age(birthdate):
    """Calculate age from date, datetime or ISO string."""
    if not birthdate:
        return None
    if isinstance(birthdate, str):
        try:
            birthdate = date.fromisoformat(birthdate[:10])
        except ValueError:
            return None
    elif hasattr(birthdate, "date"):
        birthdate = birthdate.date()
    today = date.today()
    return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))


def patient_code_cell(column, code):
    if code:
        html = f"<div class='sa-code-cell'><span class='sa-code-badge'>{safe(code)}</span></div>"
    else:
        html = "<div class='sa-cell sa-cell-muted'>Not assigned</div>"
    column.markdown(html, unsafe_allow_html=True)


def patient_name_cell(column, patient):
    name = patient_name(patient)
    init = initials(name)
    dob = patient.get("date_of_birth")
    age = calculate_age(dob)
    civil = patient.get("civil_status") or ""
    sex = str(patient.get("sex") or "").strip().lower()

    avatar_class = "sa-patient-avatar"
    if sex == "male":
        avatar_class += " sa-patient-avatar-male"
    elif sex == "female":
        avatar_class += " sa-patient-avatar-female"

    parts = []
    if age is not None:
        parts.append(f"{age} yrs")
    if civil:
        parts.append(civil)
    sub = " · ".join(parts) if parts else ""
    sub_html = f"<span class='sa-patient-sub'>{safe(sub)}</span>" if sub else ""

    html = (
        f"<div class='sa-patient-cell'>"
        f"<div class='{avatar_class}'>{init}</div>"
        f"<div class='sa-patient-info'>"
        f"<span class='sa-patient-name'>{safe(name)}</span>"
        f"{sub_html}"
        f"</div>"
        f"</div>"
    )
    column.markdown(html, unsafe_allow_html=True)


def patient_dob_cell(column, dob):
    if not dob:
        column.markdown("<div class='sa-cell sa-cell-muted'>—</div>", unsafe_allow_html=True)
        return

    date_str = format_date(dob)
    age = calculate_age(dob)
    age_html = f"<span class='sa-dob-sub'>{age} yrs old</span>" if age is not None else ""
    html = (
        f"<div class='sa-dob-cell'>"
        f"<span class='sa-dob-date'>{safe(date_str)}</span>"
        f"{age_html}"
        f"</div>"
    )
    column.markdown(html, unsafe_allow_html=True)


def patient_sex_cell(column, sex):
    if not sex:
        column.markdown("<div class='sa-cell sa-cell-muted'>—</div>", unsafe_allow_html=True)
        return

    sex_lower = str(sex).strip().lower()
    tone = "blue" if sex_lower == "male" else ("teal" if sex_lower == "female" else "grey")
    html = f"<div class='sa-sex-cell'>{pill(sex, tone)}</div>"
    column.markdown(html, unsafe_allow_html=True)


def patient_contact_cell(column, contact, emergency_no=None):
    if not contact and not emergency_no:
        column.markdown("<div class='sa-cell sa-cell-muted'>—</div>", unsafe_allow_html=True)
        return

    main_text = contact or "—"
    emg_html = (
        f"<span class='sa-contact-emg'>ICE: {safe(emergency_no)}</span>"
        if emergency_no
        else ""
    )
    html = (
        f"<div class='sa-contact-cell'>"
        f"<span class='sa-contact-main'>{safe(main_text)}</span>"
        f"{emg_html}"
        f"</div>"
    )
    column.markdown(html, unsafe_allow_html=True)


def patient_hospital_cell(column, hospital_name):
    if not hospital_name:
        column.markdown("<div class='sa-cell sa-cell-muted'>—</div>", unsafe_allow_html=True)
        return
    html = (
        f"<div class='sa-hospital-cell'>"
        f"<span class='sa-hospital-name'>{safe(hospital_name)}</span>"
        f"</div>"
    )
    column.markdown(html, unsafe_allow_html=True)


def patient_status_cell(column, status):
    status_str = (status or "Active").strip()
    is_active = status_str.lower() == "active"
    tone = "green" if is_active else "grey"
    html = f"<div class='sa-status-cell'>{pill(status_str.capitalize(), tone)}</div>"
    column.markdown(html, unsafe_allow_html=True)


def render_table_pagination(current_page, total_pages, total_items, start_idx, end_idx):
    st.markdown("<div class='sa-pagination-bar'>", unsafe_allow_html=True)
    if total_pages > 1:
        col_prev, col_info, col_next = st.columns([1, 2.5, 1], vertical_alignment="center")

        with col_prev:
            if st.button(
                "Previous",
                icon=":material/chevron_left:",
                key="patients_page_prev",
                disabled=(current_page <= 1),
                width="stretch",
            ):
                st.session_state["patients_page"] = current_page - 1
                st.rerun()

        with col_info:
            st.markdown(
                f"<div class='sa-pagination-info'>"
                f"Showing <b>{start_idx + 1}–{end_idx}</b> of <b>{total_items}</b> · Page <b>{current_page}</b> of <b>{total_pages}</b>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with col_next:
            if st.button(
                "Next",
                icon=":material/chevron_right:",
                key="patients_page_next",
                disabled=(current_page >= total_pages),
                width="stretch",
            ):
                st.session_state["patients_page"] = current_page + 1
                st.rerun()
    else:
        st.markdown(
            f"<div class='sa-pagination-info' style='padding: 0.4rem 0 0.8rem;'>"
            f"Showing all <b>{total_items}</b> {'patients' if total_items != 1 else 'patient'}"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


CIVIL_STATUS_OPTIONS = [
    "Single",
    "Married",
    "Widowed",
    "Separated",
    "Divorced",
    "Annulled",
]


# ============================================================
# ROLE IDs
# ============================================================

ROLE_SUPERADMIN = 1

CAN_EDIT_ROLES = [
    1,
    3,
    4,
    6,
    7,
]

CAN_DELETE_ROLES = [
    1,
    6,
]


# ============================================================
# HELPERS
# ============================================================

def load_patients():
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
    current_user = st.session_state.get("user") or {}
    role_id = current_user.get("role_id")
    is_superadmin = (role_id == ROLE_SUPERADMIN)
    hospital_name = (
        current_user.get("hospital_name")
        or current_user.get("hospital")
    )
    return (
        current_user,
        is_superadmin,
        current_user.get("hospital_id"),
        hospital_name,
    )


def find_duplicate_patient(
    patients,
    first_name,
    middle_name,
    last_name,
    date_of_birth,
    hospital_id,
):
    """Prevent duplicate registration inside the same hospital."""
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
# VIEW PATIENT
# ============================================================

@st.dialog(
    "Patient details",
    width="large",
)
def show_view_patient(patient):
    with st.container(key="sa_dialog"):
        if not patient:
            st.error("Patient not found.")
            return

        patient_id = patient.get("patient_id")
        name = patient_name(patient)
        init = initials(name)
        code = patient.get("patient_code") or "Not assigned"
        dob = patient.get("date_of_birth")
        age = calculate_age(dob)
        sex = patient.get("sex") or "—"
        status = (patient.get("status") or "Active").strip()
        status_tone = "green" if status.lower() == "active" else "grey"
        sex_tone = "blue" if sex.lower() == "male" else ("teal" if sex.lower() == "female" else "grey")

        hospital = patient.get("hospitals") or {}
        if isinstance(hospital, list):
            hospital = hospital[0] if hospital else {}
        hospital_name = hospital.get("hospital_name") or "—"
        hospital_id = patient.get("hospital_id") or "—"

        # Hero Header Card
        age_str = f"{age} years old · " if age is not None else ""
        hero_html = (
            f"<div class='sa-dialog-hero'>"
            f"<div class='sa-dialog-avatar'>{init}</div>"
            f"<div class='sa-dialog-info'>"
            f"<div class='sa-dialog-name'>{safe(name)}</div>"
            f"<div class='sa-dialog-badges'>"
            f"<span class='sa-code-badge'>{safe(code)}</span>"
            f"{pill(status.capitalize(), status_tone)}"
            f"{pill(sex, sex_tone)}"
            f"<span style='font-size:0.8rem; color:var(--sa-slate); font-weight:600;'>{age_str}{format_date(dob)}</span>"
            f"</div>"
            f"</div>"
            f"</div>"
        )
        st.markdown(hero_html, unsafe_allow_html=True)

        left_col, right_col = st.columns(2)

        with left_col:
            st.markdown(
                f"<div class='sa-view-card'>"
                f"<div class='sa-view-card-header'>"
                f"<span class='material-symbols-rounded'>person</span> Personal & Demographics"
                f"</div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Full name</span><span class='sa-view-value'>{safe(name)}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Date of birth</span><span class='sa-view-value'>{safe(format_date(dob))}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Age</span><span class='sa-view-value'>{f'{age} yrs old' if age is not None else '—'}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Sex</span><span class='sa-view-value'>{safe(sex)}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Civil status</span><span class='sa-view-value'>{safe(patient.get('civil_status'))}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Occupation</span><span class='sa-view-value'>{safe(patient.get('occupation'))}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Nationality</span><span class='sa-view-value'>{safe(patient.get('nationality'))}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Religion</span><span class='sa-view-value'>{safe(patient.get('religion'))}</span></div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with right_col:
            st.markdown(
                f"<div class='sa-view-card'>"
                f"<div class='sa-view-card-header'>"
                f"<span class='material-symbols-rounded'>contacts</span> Contact Details"
                f"</div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Contact number</span><span class='sa-view-value'>{safe(patient.get('contact_number'))}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Address</span><span class='sa-view-value'>{safe(patient.get('address'))}</span></div>"
                f"</div>"
                f"<div class='sa-view-card'>"
                f"<div class='sa-view-card-header'>"
                f"<span class='material-symbols-rounded'>emergency</span> Emergency / Guardian Contact"
                f"</div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Guardian name</span><span class='sa-view-value'>{safe(patient.get('emergency_contact_name'))}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Emergency number</span><span class='sa-view-value'>{safe(patient.get('emergency_contact_no'))}</span></div>"
                f"</div>"
                f"<div class='sa-view-card'>"
                f"<div class='sa-view-card-header'>"
                f"<span class='material-symbols-rounded'>local_hospital</span> Hospital Affiliation"
                f"</div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Hospital</span><span class='sa-view-value'>{safe(hospital_name)}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Hospital ID</span><span class='sa-view-value'>{safe(hospital_id)}</span></div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        (current_user, _, _, _) = get_user_context()
        can_edit = current_user.get("role_id") in CAN_EDIT_ROLES

        if can_edit:
            close_col, edit_col = st.columns(2)
            with close_col:
                if st.button("Close", key=f"close_patient_{patient_id}", width="stretch"):
                    st.rerun()
            with edit_col:
                if st.button(
                    "Edit patient",
                    key=f"view_to_edit_{patient_id}",
                    icon=":material/edit:",
                    type="primary",
                    width="stretch",
                ):
                    show_edit_patient_dialog(patient)
        else:
            close_button(f"close_patient_{patient_id}")


# ============================================================
# REGISTER / EDIT FORM
# ============================================================

def render_patient_form(patient=None):
    is_edit = patient is not None
    form_prefix = "edit_" if is_edit else "new_"
    patient = patient or {}

    (
        current_user,
        is_superadmin,
        editor_hospital_id,
        _,
    ) = get_user_context()

    hospitals = get_all_hospitals() or []
    hospital_options = {
        hospital["hospital_name"]: hospital["hospital_id"]
        for hospital in hospitals
        if hospital
    }
    hospital_names = list(hospital_options.keys())
    selected_hospital_name = None

    if patient.get("hospital_id"):
        for name, hospital_id in hospital_options.items():
            if hospital_id == patient.get("hospital_id"):
                selected_hospital_name = name
                break

    hospital_index = (
        hospital_names.index(selected_hospital_name)
        if selected_hospital_name in hospital_names
        else 0
    )

    # DOB Parsing for selectboxes
    try:
        existing_dob = date.fromisoformat(str(patient.get("date_of_birth"))[:10])
        dob_day = existing_dob.day
        dob_month = existing_dob.month
        dob_year = existing_dob.year
    except (ValueError, TypeError):
        dob_day = 1
        dob_month = 1
        dob_year = 1950

    civil_start = patient.get("civil_status") or "Single"

    errors = st.container()

    with st.form(f"patient_form_{form_prefix}", clear_on_submit=False):
        # 1. Personal Information Section
        st.markdown(
            "<div class='sa-form-section-title'>"
            "<span class='material-symbols-rounded'>person</span> Personal Information"
            "</div>",
            unsafe_allow_html=True,
        )

        first_col, middle_col, last_col, suffix_col = st.columns([2, 2, 2, 1])

        first_name = first_col.text_input(
            "First name *",
            value=patient.get("first_name") or "",
            key=f"{form_prefix}first_name",
        )

        middle_name = middle_col.text_input(
            "Middle name",
            value=patient.get("middle_name") or "",
            key=f"{form_prefix}middle_name",
        )

        last_name = last_col.text_input(
            "Last name *",
            value=patient.get("last_name") or "",
            key=f"{form_prefix}last_name",
        )

        suffix = suffix_col.text_input(
            "Suffix",
            value=patient.get("suffix") or "",
            placeholder="Jr.",
            key=f"{form_prefix}suffix",
        )

        # 2. Date of Birth & Demographics
        st.markdown(
            "<div class='sa-form-section-title'>"
            "<span class='material-symbols-rounded'>cake</span> Date of Birth & Demographics"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div class='sa-form-dob-box'>"
            "<div class='sa-form-dob-title'>"
            "<span class='material-symbols-rounded' style='font-size:16px;'>calendar_month</span> Date of birth *"
            "<span class='sa-form-dob-hint'>Select day, month, and year</span>"
            "</div>",
            unsafe_allow_html=True,
        )

        dob_col1, dob_col2, dob_col3 = st.columns([1, 1.4, 1])

        days = list(range(1, 32))
        months = list(range(1, 13))
        years = list(range(date.today().year, 1899, -1))

        selected_day = dob_col1.selectbox(
            "Day",
            days,
            index=days.index(dob_day) if dob_day in days else 0,
            key=f"{form_prefix}dob_day",
        )

        selected_month = dob_col2.selectbox(
            "Month",
            months,
            index=months.index(dob_month) if dob_month in months else 0,
            format_func=lambda m: date(2000, m, 1).strftime("%B"),
            key=f"{form_prefix}dob_month",
        )

        selected_year = dob_col3.selectbox(
            "Year",
            years,
            index=years.index(dob_year) if dob_year in years else years.index(1950),
            key=f"{form_prefix}dob_year",
        )

        st.markdown("</div>", unsafe_allow_html=True)

        sex_col, civil_col = st.columns(2)

        sex = sex_col.selectbox(
            "Sex *",
            ["Male", "Female"],
            index=1 if patient.get("sex") == "Female" else 0,
            key=f"{form_prefix}sex",
        )

        civil_status = civil_col.selectbox(
            "Civil status",
            CIVIL_STATUS_OPTIONS,
            index=(
                CIVIL_STATUS_OPTIONS.index(civil_start)
                if civil_start in CIVIL_STATUS_OPTIONS
                else 0
            ),
            key=f"{form_prefix}civil_status",
        )

        # Validate date
        try:
            birthdate = date(selected_year, selected_month, selected_day)
        except ValueError:
            errors.error("Invalid date selected (e.g., February 30 does not exist).")
            birthdate = None

        # 3. Socioeconomic & Background
        st.markdown(
            "<div class='sa-form-section-title'>"
            "<span class='material-symbols-rounded'>badge</span> Background & Demographics"
            "</div>",
            unsafe_allow_html=True,
        )

        job_col, nation_col, religion_col = st.columns(3)

        occupation = job_col.text_input(
            "Occupation",
            value=patient.get("occupation") or "",
            key=f"{form_prefix}occupation",
        )

        nationality = nation_col.text_input(
            "Nationality",
            value=patient.get("nationality") or "Filipino",
            key=f"{form_prefix}nationality",
        )

        religion = religion_col.text_input(
            "Religion",
            value=patient.get("religion") or "",
            key=f"{form_prefix}religion",
        )

        # 4. Contact & Address
        st.markdown(
            "<div class='sa-form-section-title'>"
            "<span class='material-symbols-rounded'>call</span> Contact & Residence"
            "</div>",
            unsafe_allow_html=True,
        )

        contact_col, address_col = st.columns([1.2, 2])

        contact_number = contact_col.text_input(
            "Contact number",
            value=patient.get("contact_number") or "",
            placeholder="09XX XXX XXXX",
            key=f"{form_prefix}contact",
        )

        address = address_col.text_input(
            "Residential address",
            value=patient.get("address") or "",
            placeholder="Street, Barangay, City, Province",
            key=f"{form_prefix}address",
        )

        # 5. Emergency Contact
        st.markdown(
            "<div class='sa-form-section-title'>"
            "<span class='material-symbols-rounded'>emergency</span> Guardian / Emergency Contact"
            "</div>",
            unsafe_allow_html=True,
        )

        emergency_name_col, emergency_number_col = st.columns(2)

        emergency_name = emergency_name_col.text_input(
            "Guardian / emergency contact name",
            value=patient.get("emergency_contact_name") or "",
            key=f"{form_prefix}emergency_name",
        )

        emergency_number = emergency_number_col.text_input(
            "Guardian / emergency contact number",
            value=patient.get("emergency_contact_no") or "",
            placeholder="09XX XXX XXXX",
            key=f"{form_prefix}emergency_number",
        )

        # 6. Hospital Assignment
        selected_hospital = None
        if is_superadmin:
            st.markdown(
                "<div class='sa-form-section-title'>"
                "<span class='material-symbols-rounded'>local_hospital</span> Hospital Assignment"
                "</div>",
                unsafe_allow_html=True,
            )
            if hospital_names:
                selected_hospital = st.selectbox(
                    "Hospital *",
                    hospital_names,
                    index=hospital_index,
                    key=f"{form_prefix}hospital",
                )
            else:
                st.warning("No hospitals registered yet.")

        st.write("")
        cancel_col, save_col = st.columns(2)

        cancel = cancel_col.form_submit_button(
            "Cancel",
            icon=":material/close:",
            width="stretch",
        )

        submitted = save_col.form_submit_button(
            "Save changes" if is_edit else "Register patient",
            icon=":material/check_circle:",
            type="primary",
            width="stretch",
        )

    if cancel:
        st.rerun()

    if not submitted:
        return

    if birthdate is None:
        return

    if (
        not first_name.strip()
        or not last_name.strip()
    ):
        errors.error("First name and last name are required.")
        return

    if is_superadmin:
        if selected_hospital:
            hospital_id = hospital_options[selected_hospital]
        elif is_edit:
            hospital_id = patient.get("hospital_id")
        else:
            errors.error("Please select a hospital.")
            return
    else:
        if editor_hospital_id is None:
            errors.error(
                "Your account is not assigned to a hospital. "
                "Please contact your Superadmin."
            )
            return
        hospital_id = editor_hospital_id

    details = {
        "first_name": first_name.strip(),
        "middle_name": middle_name.strip() or None,
        "last_name": last_name.strip(),
        "suffix": suffix.strip() or None,
        "date_of_birth": birthdate,
        "sex": sex,
        "civil_status": civil_status or None,
        "occupation": occupation.strip() or None,
        "nationality": nationality.strip() or None,
        "religion": religion.strip() or None,
        "contact_number": contact_number.strip() or None,
        "address": address.strip() or None,
        "emergency_contact_name": emergency_name.strip() or None,
        "emergency_contact_no": emergency_number.strip() or None,
        "hospital_id": hospital_id,
    }

    try:
        if is_edit:
            update_patient(
                patient_id=patient["patient_id"],
                **details,
            )
            remember("Patient updated.")
        else:
            duplicate = find_duplicate_patient(
                get_all_patients() or [],
                first_name,
                middle_name,
                last_name,
                birthdate,
                hospital_id,
            )
            if duplicate:
                errors.error(
                    "A patient with the same name and date of birth "
                    f"already exists: {patient_name(duplicate)} "
                    f"(code {duplicate.get('patient_code') or '—'})."
                )
                return

            subscription_check = can_register_patient(hospital_id)
            if not subscription_check.get("allowed"):
                errors.error(
                    subscription_check.get(
                        "message",
                        "Patient limit reached.",
                    )
                )
                return

            create_patient(
                created_by=current_user.get("user_id"),
                **details,
            )
            remember("Patient registered.")

        st.rerun()

    except Exception as error:
        errors.error(f"Failed to save patient: {error}")


# ============================================================
# ADD PATIENT
# ============================================================

@st.dialog(
    "Register patient",
    width="large",
)
def show_add_patient_form():
    with st.container(key="sa_dialog"):
        render_patient_form()


# ============================================================
# EDIT PATIENT
# ============================================================

@st.dialog(
    "Edit patient",
    width="large",
)
def show_edit_patient_dialog(patient):
    with st.container(key="sa_dialog"):
        render_patient_form(patient)


# ============================================================
# DELETE PATIENT
# ============================================================

@st.dialog(
    "Delete patient",
    width="small",
)
def show_delete_patient_dialog(patient):
    with st.container(key="sa_dialog"):
        st.markdown(
            f"<p class='sa-dialog-text'>"
            f"Delete <b>{patient_name(patient)}</b>?"
            f"</p>",
            unsafe_allow_html=True,
        )

        note(
            "This permanently removes the patient record from the system.",
            "red",
        )

        if confirm_buttons(
            f"delete_patient_{patient['patient_id']}",
            "Delete patient",
        ):
            try:
                delete_patient(patient["patient_id"])
                remember("Patient deleted.")
                st.rerun()
            except Exception as error:
                st.error(f"Failed to delete patient: {error}")


# ============================================================
# FILTERS
# ============================================================

def show_filters(
    patients,
    hospital_names=None,
    is_superadmin=False,
):
    with st.container(key="sa_patient_filters"):
        if is_superadmin and hospital_names:
            search_col, sex_col, status_col, hosp_col, reset_col = st.columns(
                [2.8, 1.2, 1.2, 1.8, 0.9],
                vertical_alignment="center",
            )
            hospital_filter = hosp_col.selectbox(
                "Hospital",
                ["All hospitals"] + hospital_names,
                label_visibility="collapsed",
                key="patients_hospital_filter",
            )
        else:
            search_col, sex_col, status_col, reset_col = st.columns(
                [3.2, 1.3, 1.3, 1],
                vertical_alignment="center",
            )
            hospital_filter = "All hospitals"

        search = search_col.text_input(
            "Search",
            placeholder="Search by name, ID, or contact number...",
            label_visibility="collapsed",
            key="patients_search",
        ).strip().lower()

        sex = sex_col.selectbox(
            "Sex",
            [
                "All sexes",
                "Male",
                "Female",
            ],
            label_visibility="collapsed",
            key="patients_sex",
        )

        status = status_col.selectbox(
            "Status",
            [
                "All status",
                "Active",
                "Inactive",
            ],
            label_visibility="collapsed",
            key="patients_status",
        )

        def _reset_filters():
            st.session_state["patients_page"] = 1
            st.session_state["patients_search"] = ""
            st.session_state["patients_sex"] = "All sexes"
            st.session_state["patients_status"] = "All status"
            if "patients_hospital_filter" in st.session_state:
                st.session_state["patients_hospital_filter"] = "All hospitals"
            st.cache_data.clear()

        reset_col.button(
            "Reset",
            icon=":material/refresh:",
            width="stretch",
            key="patients_refresh",
            on_click=_reset_filters,
            help="Reset filters and refresh data",
        )

    # Track filter changes to reset pagination to page 1
    curr_filter_key = (search, sex, status, hospital_filter)
    prev_filter_key = (
        st.session_state.get("_prev_patients_search"),
        st.session_state.get("_prev_patients_sex"),
        st.session_state.get("_prev_patients_status"),
        st.session_state.get("_prev_patients_hosp"),
    )
    if prev_filter_key != curr_filter_key:
        st.session_state["patients_page"] = 1
        st.session_state["_prev_patients_search"] = search
        st.session_state["_prev_patients_sex"] = sex
        st.session_state["_prev_patients_status"] = status
        st.session_state["_prev_patients_hosp"] = hospital_filter

    matches = []

    for patient in patients:
        text = (
            f"{patient_name(patient)} "
            f"{patient.get('patient_code') or ''} "
            f"{patient.get('contact_number') or ''}"
        ).lower()

        if search and search not in text:
            continue

        if (
            sex != "All sexes"
            and (patient.get("sex") or "").strip().lower() != sex.lower()
        ):
            continue

        patient_status = (patient.get("status") or "active").strip().lower()
        if (
            status != "All status"
            and patient_status != status.lower()
        ):
            continue

        if hospital_filter != "All hospitals":
            hosp = patient.get("hospitals") or {}
            if isinstance(hosp, list):
                hosp = hosp[0] if hosp else {}
            hosp_name = hosp.get("hospital_name") or ""
            if hosp_name != hospital_filter:
                continue

        matches.append(patient)

    return matches


# ============================================================
# PATIENT TABLE
# ============================================================

def render_patient_table(
    patients,
    role_id,
):
    if not patients:
        empty_state(
            "No patients found matching your search or filter criteria."
        )
        return

    can_edit = role_id in CAN_EDIT_ROLES
    can_delete = role_id in CAN_DELETE_ROLES

    PAGE_SIZE = 15
    total_items = len(patients)
    total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)
    current_page = st.session_state.get("patients_page", 1)
    if current_page > total_pages:
        current_page = total_pages
        st.session_state["patients_page"] = current_page
    elif current_page < 1:
        current_page = 1
        st.session_state["patients_page"] = current_page

    start_idx = (current_page - 1) * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, total_items)
    page_patients = patients[start_idx:end_idx]

    # Toolbar with patient count
    st.markdown(
        f"<div class='sa-table-toolbar'>"
        f"<div class='sa-table-count-badge'>"
        f"Showing <b>{start_idx + 1}–{end_idx}</b> of <b>{total_items}</b> patients"
        f"</div>"
        f"<span style='font-size:0.78rem; color:var(--sa-slate);'>Page {current_page} of {total_pages}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    with st.container(key="sa_table_patients"):
        table_header(
            HEADERS,
            WIDTHS,
            "patients",
        )

        for patient in page_patients:
            patient_id = patient.get("patient_id")

            with table_row(
                f"patients_{patient_id}",
                WIDTHS,
            ) as cols:
                # 0. Patient Code
                patient_code_cell(
                    cols[0],
                    patient.get("patient_code")
                )

                # 1. Patient Name + Avatar + Demographics
                patient_name_cell(
                    cols[1],
                    patient
                )

                # 2. Date of Birth & Age
                patient_dob_cell(
                    cols[2],
                    patient.get("date_of_birth")
                )

                # 3. Sex Pill
                patient_sex_cell(
                    cols[3],
                    patient.get("sex")
                )

                # 4. Contact
                patient_contact_cell(
                    cols[4],
                    patient.get("contact_number"),
                    patient.get("emergency_contact_no"),
                )

                # 5. Hospital
                hospital = patient.get("hospitals") or {}
                if isinstance(hospital, list):
                    hospital = hospital[0] if hospital else {}
                patient_hospital_cell(
                    cols[5],
                    hospital.get("hospital_name")
                )

                # 6. Status
                patient_status_cell(
                    cols[6],
                    patient.get("status")
                )

                # 7. Actions (View, Edit, Delete)
                with cols[7]:
                    actions_count = 1 + (1 if can_edit else 0) + (1 if can_delete else 0)
                    act_cols = st.columns(actions_count, gap="small", vertical_alignment="center")
                    idx = 0

                    with act_cols[idx]:
                        if st.button(
                            "",
                            key=f"view_{patient_id}",
                            icon=":material/visibility:",
                            help="View patient details",
                            width="stretch",
                        ):
                            show_view_patient(patient)
                    idx += 1

                    if can_edit:
                        with act_cols[idx]:
                            if st.button(
                                "",
                                key=f"edit_{patient_id}",
                                icon=":material/edit:",
                                help="Edit patient",
                                width="stretch",
                            ):
                                show_edit_patient_dialog(patient)
                        idx += 1

                    if can_delete:
                        with act_cols[idx]:
                            if st.button(
                                "",
                                key=f"delete_{patient_id}",
                                icon=":material/delete:",
                                help="Delete patient",
                                width="stretch",
                            ):
                                show_delete_patient_dialog(patient)

    # Pagination controls & bottom status
    render_table_pagination(current_page, total_pages, total_items, start_idx, end_idx)


# ============================================================
# PAGE
# ============================================================

def show():
    load_css("manage_patients.css")
    show_flash_message()

    (
        current_user,
        is_superadmin,
        current_hospital_id,
        hospital_name,
    ) = get_user_context()

    role_id = current_user.get("role_id")

    with st.container(key="sa_page"):
        if page_header(
            "Manage patients",
            "Register and manage patient demographic information.",
            "Register patient",
            "register_patient_button",
            "person_add",
        ):
            show_add_patient_form()

        patients = load_patients()

        if role_id != ROLE_SUPERADMIN:
            if current_hospital_id is None:
                st.error(
                    "Your account is not assigned to a hospital. "
                    "Please contact your Superadmin."
                )
                st.stop()

            patients = [
                patient
                for patient in patients
                if patient.get("hospital_id") == current_hospital_id
            ]

        # ---------------- Metrics ----------------
        total_p = len(patients)
        active_p = sum(1 for p in patients if (p.get("status") or "active").strip().lower() == "active")
        male_p = sum(1 for p in patients if (p.get("sex") or "").strip().lower() == "male")
        female_p = sum(1 for p in patients if (p.get("sex") or "").strip().lower() == "female")

        metrics = [
            ("Total patients", total_p, "groups", "teal"),
            ("Active patients", active_p, "verified", "green"),
            ("Male patients", male_p, "male", "blue"),
            ("Female patients", female_p, "female", "amber"),
        ]

        columns = st.columns(4)
        for column, (title, value, icon, tone) in zip(columns, metrics):
            with column:
                metric_card(title, value, icon, tone)

        hospital_names = None
        if role_id == ROLE_SUPERADMIN:
            hospital_names = sorted({
                (h.get("hospital_name") if isinstance(h, dict) else h)
                for h in (get_all_hospitals() or [])
                if (h.get("hospital_name") if isinstance(h, dict) else h)
            })

        matches = show_filters(
            patients,
            hospital_names=hospital_names,
            is_superadmin=(role_id == ROLE_SUPERADMIN),
        )

        render_patient_table(
            matches,
            role_id,
        )
