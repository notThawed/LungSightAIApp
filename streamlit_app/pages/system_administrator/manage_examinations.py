import io
from datetime import date

import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image

from backend.fetches import (
    get_all_patients,
    get_all_hospitals,
    get_examinations_by_patient,
    get_examination_consents,
    get_examination_vitals,
    get_medical_records_by_patient,
    get_medical_record_images,
    get_consent_signature_url,
    get_medical_record_file_url,
)

from backend.crud import (
    create_examination,
    update_examination,
    update_examination_vitals,
    update_examination_consent,
    upload_consent_signature,
    delete_examination,
)

from streamlit_app.components.ui import (
    page_header,
    empty_state,
    section_title,
    show_rows,
    full_name,
    format_date,
    table_header,
    table_row,
    name_cell,
    text_cell,
    pill_cell,
    remember,
    show_flash_message,
    confirm_buttons,
    metric_card,
)

from shared.assets import load_css


# ============================================================
# CONFIG
# ============================================================

WIDTHS = [
    1.2,  # Patient ID
    2.8,  # Patient Name + Demographics
    1.4,  # Date of birth + Age
    0.9,  # Sex
    1.6,  # Contact
    1.3,  # Action (Examine)
]

WIDTHS_SUPERADMIN = [
    1.7,  # Hospital
    1.1,  # Patient ID
    2.4,  # Patient Name + Demographics
    1.3,  # Date of birth + Age
    0.8,  # Sex
    1.4,  # Contact
    1.3,  # Action (Examine)
]

HEADERS = [
    "Patient ID",
    "Name",
    "Date of birth",
    "Sex",
    "Contact",
    "Action",
]

HEADERS_SUPERADMIN = [
    "Hospital",
    "Patient ID",
    "Name",
    "Date of birth",
    "Sex",
    "Contact",
    "Action",
]

HISTORY_WIDTHS = [
    1.4,  # Date
    2.2,  # Examination Type
    1.4,  # Status
    1.0,  # Action
]

HISTORY_HEADERS = [
    "Date",
    "Type",
    "Status",
    "Action",
]

MEDICAL_HISTORY_WIDTHS = [
    1.4,  # Date
    1.8,  # Record type
    2.4,  # Facility
    1.0,  # Action
]

MEDICAL_HISTORY_HEADERS = [
    "Date",
    "Record type",
    "Facility",
    "Action",
]

STATUS_TONES = {
    "Completed": "green",
    "Pending": "amber",
    "In Progress": "blue",
    "Awaiting X-Ray": "amber",
    "X-Ray Ready": "blue",
    "Cancelled": "red",
}


# ============================================================
# ROLE IDs
# ============================================================

ROLE_SUPERADMIN = 1
ROLE_RADIOLOGIST = 3
ROLE_RADTECH = 4
ROLE_HOSPITAL_ADMIN = 6
ROLE_STAFF = 7

ADMIN_ROLES = [
    ROLE_SUPERADMIN,
    ROLE_HOSPITAL_ADMIN,
]

NURSE_ROLES = [
    ROLE_STAFF,
]

FIXED_EXAM_TYPE = "General Consult"


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


def patient_code(patient):
    return (
        patient.get("patient_code")
        or patient.get("patient_id")
        or "—"
    )


def patient_initials(first_name, last_name):
    f = (first_name or "").strip()[:1].upper()
    l = (last_name or "").strip()[:1].upper()
    return f"{f}{l}" or "PT"


def calculate_age(dob):
    if not dob:
        return "—"
    try:
        if isinstance(dob, str):
            dob = date.fromisoformat(str(dob)[:10])
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return "—"


def patient_hospital_name(patient):
    hospitals = patient.get("hospitals")
    if isinstance(hospitals, dict):
        return hospitals.get("hospital_name") or "—"
    if isinstance(hospitals, list) and hospitals:
        return hospitals[0].get("hospital_name") or "—"
    return "—"


def current_user():
    return st.session_state.get("user") or {}


def current_role_id():
    return current_user().get("role_id")


def current_hospital_id():
    return current_user().get("hospital_id")


def is_superadmin():
    return current_role_id() == ROLE_SUPERADMIN


def is_admin_role():
    return current_role_id() in ADMIN_ROLES


def is_nurse_role():
    return current_role_id() in NURSE_ROLES


def is_minor(date_of_birth):
    if not date_of_birth:
        return False
    try:
        dob = date.fromisoformat(str(date_of_birth)[:10])
    except (ValueError, TypeError):
        return False

    today = date.today()
    age = (
        today.year
        - dob.year
        - ((today.month, today.day) < (dob.month, dob.day))
    )
    return age < 18


def _get_vitals_value(vitals, field_name):
    if not vitals:
        return None
    for vital in vitals:
        if vital.get(field_name) is not None:
            return vital[field_name]
    return None


# ============================================================
# UI COMPONENTS & CELLS
# ============================================================

def render_patient_hero(patient):
    """Renders a sleek clinical hero banner with patient avatar, code, and demographic chips."""
    fname = patient.get("first_name", "")
    lname = patient.get("last_name", "")
    full_n = patient_name(patient)
    code = patient_code(patient)
    p_sex = patient.get("sex") or "—"
    dob_fmt = format_date(patient.get("date_of_birth"))
    age_val = calculate_age(patient.get("date_of_birth"))
    contact = patient.get("contact_number") or "No contact"
    hospital = patient_hospital_name(patient)

    initials = patient_initials(fname, lname)
    avatar_class = "sa-dialog-avatar-female" if p_sex.lower() == "female" else "sa-dialog-avatar"

    st.markdown(
        f"""
        <div class="sa-dialog-hero">
            <div class="{avatar_class}">{initials}</div>
            <div class="sa-dialog-info">
                <div class="sa-dialog-name">{full_n}</div>
                <div class="sa-dialog-badges">
                    <span class="sa-code-badge">#{code}</span>
                    <span class="sa-chip">{p_sex}</span>
                    <span class="sa-chip">{age_val} yrs ({dob_fmt})</span>
                    <span class="sa-chip">{contact}</span>
                    <span class="sa-chip">{hospital}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def patient_code_cell(column, code):
    column.markdown(
        f"<div class='sa-code-cell'><span class='sa-code-badge'>#{code}</span></div>",
        unsafe_allow_html=True,
    )


def patient_name_cell(column, patient):
    fname = patient.get("first_name", "")
    lname = patient.get("last_name", "")
    full_n = patient_name(patient)
    initials = patient_initials(fname, lname)
    sex = (patient.get("sex") or "").lower()

    avatar_class = "sa-patient-avatar"
    if sex == "female":
        avatar_class += " sa-patient-avatar-female"
    elif sex == "male":
        avatar_class += " sa-patient-avatar-male"

    age_val = calculate_age(patient.get("date_of_birth"))
    sub_text = f"{age_val} yrs" if age_val != "—" else ""
    civil = patient.get("civil_status")
    if civil:
        sub_text += f" &bull; {civil}" if sub_text else civil

    column.markdown(
        f"<div class='sa-patient-cell'>"
        f"  <div class='{avatar_class}'>{initials}</div>"
        f"  <div class='sa-patient-info'>"
        f"    <span class='sa-patient-name'>{full_n}</span>"
        f"    <span class='sa-patient-sub'>{sub_text}</span>"
        f"  </div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def patient_dob_cell(column, dob):
    if not dob:
        column.markdown("<span style='color:var(--sa-slate);'>—</span>", unsafe_allow_html=True)
        return
    formatted = format_date(dob)
    age = calculate_age(dob)
    age_str = f"{age} yrs old" if age != "—" else ""
    column.markdown(
        f"<div class='sa-dob-cell'>"
        f"  <span class='sa-dob-date'>{formatted}</span>"
        f"  <span class='sa-dob-sub'>{age_str}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


def patient_contact_cell(column, contact, emergency=None):
    if not contact and not emergency:
        column.markdown("<span style='color:var(--sa-slate);'>—</span>", unsafe_allow_html=True)
        return
    emg_html = (
        f"<span class='sa-contact-emg'>ICE: {emergency}</span>"
        if emergency
        else ""
    )
    column.markdown(
        f"<div class='sa-contact-cell'>"
        f"  <span class='sa-contact-main'>{contact or '—'}</span>"
        f"  {emg_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_table_pagination(current_page, total_pages, total_items, start_idx, end_idx):
    st.markdown("<div class='sa-pagination-bar'>", unsafe_allow_html=True)
    if total_pages > 1:
        col_prev, col_info, col_next = st.columns([1, 2.5, 1], vertical_alignment="center")

        with col_prev:
            if st.button(
                "Previous",
                icon=":material/chevron_left:",
                key="exam_page_prev",
                disabled=(current_page <= 1),
                width="stretch",
            ):
                st.session_state["exam_page"] = current_page - 1
                st.rerun()

        with col_info:
            st.markdown(
                f"<div class='sa-pagination-info'>"
                f"Showing <b>{start_idx + 1}–{end_idx}</b> of <b>{total_items}</b> &bull; Page <b>{current_page}</b> of <b>{total_pages}</b>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with col_next:
            if st.button(
                "Next",
                icon=":material/chevron_right:",
                key="exam_page_next",
                disabled=(current_page >= total_pages),
                width="stretch",
            ):
                st.session_state["exam_page"] = current_page + 1
                st.rerun()
    else:
        st.markdown(
            f"<div class='sa-pagination-info' style='text-align:center; padding: 0.5rem 0 0.8rem;'>"
            f"Showing all <b>{total_items}</b> records"
            f"</div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# DIALOG STATE
# ============================================================

def open_dialog(name, **state):
    st.session_state["examination_dialog"] = name
    for key, value in state.items():
        st.session_state[key] = value
    st.rerun()


def close_dialog():
    st.session_state["examination_dialog"] = None
    st.session_state["selected_examination"] = None
    st.session_state["selected_medical_record"] = None
    st.session_state["create_examination_patient"] = None
    st.session_state["delete_examination_target"] = None


# ============================================================
# PATIENT EXAMINATION HISTORY DIALOG
# ============================================================

@st.dialog("Patient Examination History", width="large")
def show_patient_history(patient):
    examinations = get_examinations_by_patient(patient["patient_id"]) or []
    medical_records = get_medical_records_by_patient(patient["patient_id"]) or []

    with st.container(key="sa_dialog"):
        # Sleek Hero Card
        render_patient_hero(patient)

        # Action bar at top
        if is_nurse_role() or is_admin_role():
            action_col1, action_col2 = st.columns([2.5, 1.5], vertical_alignment="center")
            with action_col2:
                if st.button(
                    "Examine Patient",
                    key=f"hist_cta_examine_{patient['patient_id']}",
                    icon=":material/clinical_notes:",
                    type="primary",
                    width="stretch",
                ):
                    open_dialog("create", create_examination_patient=patient)

        # Tabbed Clinical History
        tab_exams, tab_records = st.tabs([
            f"Examinations ({len(examinations)})",
            f"Previous Medical Records ({len(medical_records)})",
        ])

        with tab_exams:
            if not examinations:
                empty_state("No examination records found for this patient.")
            else:
                with st.container(key="sa_table_exam_history"):
                    table_header(HISTORY_HEADERS, HISTORY_WIDTHS, "exam_history")

                    for examination in examinations:
                        exam_id = examination["examination_id"]
                        status = examination.get("status") or "—"

                        with table_row(f"exam_history_{exam_id}", HISTORY_WIDTHS) as cols:
                            text_cell(cols[0], format_date(examination.get("examination_date")))
                            text_cell(cols[1], examination.get("examination_type"))
                            pill_cell(cols[2], status, STATUS_TONES.get(status, "grey"))

                            if cols[3].button(
                                "View",
                                key=f"history_view_{exam_id}",
                                icon=":material/visibility:",
                                width="stretch",
                            ):
                                open_dialog(
                                    "view_exam",
                                    selected_examination=examination,
                                    selected_patient=patient,
                                )

        with tab_records:
            if not medical_records:
                empty_state("No previous external medical records found.")
            else:
                with st.container(key="sa_table_medical_history"):
                    table_header(MEDICAL_HISTORY_HEADERS, MEDICAL_HISTORY_WIDTHS, "medical_history")

                    for record in medical_records:
                        record_id = record["medical_record_id"]

                        with table_row(f"medical_history_{record_id}", MEDICAL_HISTORY_WIDTHS) as cols:
                            text_cell(cols[0], format_date(record.get("record_date")))
                            text_cell(cols[1], record.get("record_type") or "—")
                            text_cell(cols[2], record.get("facility_name") or "—")

                            if cols[3].button(
                                "View",
                                key=f"history_medical_{record_id}",
                                icon=":material/visibility:",
                                width="stretch",
                            ):
                                open_dialog(
                                    "view_medical_record",
                                    selected_medical_record=record,
                                    selected_patient=patient,
                                )

        # Footer Close Button
        st.divider()
        _, close_col = st.columns([3.5, 1])
        with close_col:
            if st.button("Close", key=f"close_hist_{patient['patient_id']}", width="stretch"):
                close_dialog()
                st.rerun()


# ============================================================
# EXAMINATION DETAILS DIALOG
# ============================================================

@st.dialog("Examination Details", width="large")
def show_examination_details(patient, examination):
    examination_id = examination["examination_id"]
    consents = get_examination_consents(examination_id) or []
    consent = consents[0] if consents else None
    vitals = get_examination_vitals(examination_id) or []
    vital = vitals[0] if vitals else {}

    with st.container(key="sa_dialog"):
        render_patient_hero(patient)

        # Header Info Bar
        exam_status = examination.get("status") or "Pending"
        tone = STATUS_TONES.get(exam_status, "grey")
        exam_date_fmt = format_date(examination.get("examination_date"))
        exam_type = examination.get("examination_type") or FIXED_EXAM_TYPE

        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between; align-items: center; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 0.65rem 1rem; margin-bottom: 1rem;">
                <div style="display: flex; align-items: center; gap: 0.65rem;">
                    <span style="font-size: 1rem; font-weight: 700; color: var(--sa-ink);">{exam_type}</span>
                    <span style="font-size: 0.8rem; color: var(--sa-slate);">&bull; Date: <b>{exam_date_fmt}</b></span>
                </div>
                <div class="sa-pill sa-pill-{tone}">{exam_status}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab_vitals, tab_consent, tab_disposition = st.tabs([
            "Vital Signs & Findings",
            "Consent & Verification",
            "Disposition & Follow-up",
        ])

        # --- Tab 1: Vitals & Clinical Assessment ---
        with tab_vitals:
            st.markdown("<div class='sa-form-section-title' style='margin-top:0.25rem;'>Vital Signs Readings</div>", unsafe_allow_html=True)
            if vital:
                bp_sys = vital.get("bp_systolic")
                bp_dia = vital.get("bp_diastolic")
                bp_val = f"{bp_sys}/{bp_dia}" if (bp_sys or bp_dia) else "—"
                temp = vital.get("temperature")
                pulse = vital.get("pulse_rate")
                resp = vital.get("respiratory_rate")
                spo2 = vital.get("spo2")
                weight = vital.get("weight_kg")
                height = vital.get("height_cm")
                bmi = vital.get("bmi")

                st.markdown(
                    f"""
                    <div class="sa-vitals-grid">
                        <div class="sa-vital-card">
                            <span class="sa-vital-label">Blood Pressure</span>
                            <span class="sa-vital-value">{bp_val} <span class="sa-vital-unit">mmHg</span></span>
                        </div>
                        <div class="sa-vital-card">
                            <span class="sa-vital-label">Temperature</span>
                            <span class="sa-vital-value">{temp or '—'} <span class="sa-vital-unit">°C</span></span>
                        </div>
                        <div class="sa-vital-card">
                            <span class="sa-vital-label">Pulse Rate</span>
                            <span class="sa-vital-value">{pulse or '—'} <span class="sa-vital-unit">bpm</span></span>
                        </div>
                        <div class="sa-vital-card">
                            <span class="sa-vital-label">Resp. Rate</span>
                            <span class="sa-vital-value">{resp or '—'} <span class="sa-vital-unit">cpm</span></span>
                        </div>
                        <div class="sa-vital-card">
                            <span class="sa-vital-label">Oxygen (SpO2)</span>
                            <span class="sa-vital-value">{spo2 or '—'} <span class="sa-vital-unit">%</span></span>
                        </div>
                        <div class="sa-vital-card">
                            <span class="sa-vital-label">Weight</span>
                            <span class="sa-vital-value">{weight or '—'} <span class="sa-vital-unit">kg</span></span>
                        </div>
                        <div class="sa-vital-card">
                            <span class="sa-vital-label">Height</span>
                            <span class="sa-vital-value">{height or '—'} <span class="sa-vital-unit">cm</span></span>
                        </div>
                        <div class="sa-vital-card">
                            <span class="sa-vital-label">BMI</span>
                            <span class="sa-vital-value">{bmi or '—'}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No vital signs recorded for this examination.")

            st.markdown("<div class='sa-form-section-title' style='margin-top:1rem;'>Clinical Assessment</div>", unsafe_allow_html=True)
            show_rows([
                ("Chief complaint", examination.get("chief_complaint") or "—"),
                ("History of present illness", examination.get("history_of_present_illness") or "—"),
                ("Physical examination", examination.get("physical_examination") or "—"),
                ("Diagnosis", examination.get("diagnosis") or "—"),
                ("Plans / orders", examination.get("plans_orders") or "—"),
            ])

        # --- Tab 2: Consent & Verification ---
        with tab_consent:
            if consent:
                show_rows([
                    ("Consent type", consent.get("consent_type") or "General Examination"),
                    ("Consent given", "Yes" if consent.get("given") else "No"),
                    ("Signed by", consent.get("signed_by_name") or "—"),
                    ("Signer type", consent.get("signed_by_type") or "patient"),
                    ("Guardian name", consent.get("guardian_name") or "—"),
                    ("Relationship", consent.get("guardian_relation") or "—"),
                ])

                sig_path = consent.get("signature_path")
                if sig_path:
                    st.markdown("<div class='sa-form-section-title' style='margin-top:0.75rem;'>Digital Signature</div>", unsafe_allow_html=True)
                    sig_url = get_consent_signature_url(sig_path)
                    if sig_url:
                        st.image(sig_url, width=240)
                    else:
                        st.caption("Signature path recorded, but file URL is inaccessible.")
                else:
                    st.caption("No digital signature captured.")
            else:
                st.caption("No consent record found for this examination.")

        # --- Tab 3: Disposition & Follow-up ---
        with tab_disposition:
            show_rows([
                ("Disposition", examination.get("disposition") or "—"),
                ("Disposition notes", examination.get("disposition_notes") or "—"),
                ("Follow-up date", format_date(examination.get("follow_up_date")) or "—"),
                ("Follow-up notes", examination.get("follow_up_notes") or "—"),
            ])

        # Footer Actions
        st.divider()
        b_col1, b_col2, b_col3 = st.columns([2, 1, 1])

        with b_col1:
            if st.button(
                "Back to Patient History",
                key=f"back_exam_{examination_id}",
                icon=":material/arrow_back:",
            ):
                open_dialog("history", selected_patient=patient)

        with b_col2:
            if is_admin_role():
                if st.button(
                    "Delete",
                    key=f"del_exam_btn_{examination_id}",
                    icon=":material/delete:",
                    type="secondary",
                    width="stretch",
                ):
                    open_dialog("delete", delete_examination_target=examination)

        with b_col3:
            if st.button("Close", key=f"close_detail_{examination_id}", width="stretch"):
                close_dialog()
                st.rerun()


# ============================================================
# PREVIOUS MEDICAL RECORD DETAILS DIALOG
# ============================================================

@st.dialog("Previous Medical Record", width="large")
def show_medical_record_details(patient, record):
    record_id = record["medical_record_id"]

    with st.container(key="sa_dialog"):
        render_patient_hero(patient)

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("<div class='sa-form-section-title'>Facility & Provider</div>", unsafe_allow_html=True)
            show_rows([
                ("Record date", format_date(record.get("record_date")) or "—"),
                ("Record type", record.get("record_type") or "—"),
                ("Facility", record.get("facility_name") or "—"),
                ("Department", record.get("department") or "—"),
                ("Attending physician", record.get("attending_physician") or "—"),
                ("Status", record.get("record_status") or "—"),
            ])

        with col_right:
            st.markdown("<div class='sa-form-section-title'>Clinical Record</div>", unsafe_allow_html=True)
            show_rows([
                ("Chief complaint", record.get("chief_complaint") or "—"),
                ("Diagnosis", record.get("diagnosis") or "—"),
                ("Procedure", record.get("procedure_name") or "—"),
                ("Findings", record.get("findings") or "—"),
                ("Impression", record.get("impression") or "—"),
                ("Treatment", record.get("treatment") or "—"),
                ("Follow-up", record.get("follow_up") or "—"),
            ])

        # Attached Images/Files
        try:
            images = get_medical_record_images(record_id) or []
            if images:
                st.markdown("<div class='sa-form-section-title' style='margin-top:1rem;'>Attached Images & Scans</div>", unsafe_allow_html=True)
                img_cols = st.columns(min(len(images), 3))
                for idx, img_info in enumerate(images):
                    file_path = img_info.get("file_path")
                    if file_path:
                        img_url = get_medical_record_file_url(file_path)
                        if img_url:
                            with img_cols[idx % 3]:
                                st.image(img_url, caption=img_info.get("caption") or f"Scan #{idx + 1}")
        except Exception:
            pass

        st.divider()
        b_col1, b_col2 = st.columns([3, 1])

        with b_col1:
            if st.button(
                "Back to Patient History",
                key=f"back_med_{record_id}",
                icon=":material/arrow_back:",
            ):
                open_dialog("history", selected_patient=patient)

        with b_col2:
            if st.button("Close", key=f"close_med_{record_id}", width="stretch"):
                close_dialog()
                st.rerun()


# ============================================================
# DELETE EXAMINATION DIALOG
# ============================================================

@st.dialog("Delete Examination", width="small")
def show_delete_examination_dialog(examination):
    with st.container(key="sa_dialog"):
        exam_type = examination.get("examination_type") or FIXED_EXAM_TYPE
        exam_date = format_date(examination.get("examination_date"))

        st.markdown(
            f"<p class='sa-dialog-text'>"
            f"Are you sure you want to permanently delete the <b>{exam_type}</b> "
            f"examination record from <b>{exam_date}</b>?"
            f"</p>",
            unsafe_allow_html=True,
        )

        st.warning("This will permanently remove the examination and its associated vitals and consent data.")

        if confirm_buttons(f"delete_exam_{examination['examination_id']}", "Delete permanently"):
            try:
                delete_examination(examination["examination_id"])
                remember("Examination deleted successfully.")
                open_dialog("history", selected_patient=st.session_state.get("selected_patient"))
            except Exception as error:
                st.error(f"Failed to delete examination: {error}")


# ============================================================
# CREATE / EDIT EXAMINATION FORM DIALOG
# ============================================================

@st.dialog("Examine Patient", width="large")
def show_examination_form(patient, examination=None):
    user_id = current_user().get("user_id")
    is_edit = examination is not None
    examination_id = examination.get("examination_id") if examination else None

    existing_consent = None
    existing_vitals = []

    if is_edit:
        consents = get_examination_consents(examination_id) or []
        existing_consent = consents[0] if consents else None
        existing_vitals = get_examination_vitals(examination_id) or []

    with st.container(key="sa_dialog"):
        render_patient_hero(patient)

        tab_form, tab_history = st.tabs([
            "Examination Entry",
            "Patient Medical Background",
        ])

        with tab_form:
            # 1. Vital Signs
            st.markdown("<div class='sa-form-section-title'>1. Initial Vital Signs</div>", unsafe_allow_html=True)
            v1, v2, v3 = st.columns(3)

            bp_sys = v1.number_input(
                "Systolic BP (mmHg)",
                min_value=0,
                max_value=300,
                step=1,
                value=int(_get_vitals_value(existing_vitals, "bp_systolic") or 120),
                key="exam_bp_sys",
            )

            bp_dia = v2.number_input(
                "Diastolic BP (mmHg)",
                min_value=0,
                max_value=200,
                step=1,
                value=int(_get_vitals_value(existing_vitals, "bp_diastolic") or 80),
                key="exam_bp_dia",
            )

            temperature = v3.number_input(
                "Temperature (°C)",
                min_value=30.0,
                max_value=45.0,
                step=0.1,
                value=float(_get_vitals_value(existing_vitals, "temperature") or 36.5),
                key="exam_temperature",
            )

            st.write("")

            # 2. Informed Consent
            st.markdown("<div class='sa-form-section-title'>2. Informed Consent & Signature</div>", unsafe_allow_html=True)

            signed_by_name = st.text_input(
                "Patient or Guardian Full Name",
                value=(
                    (existing_consent or {}).get("signed_by_name")
                    or patient_name(patient)
                ),
                key="exam_consent_name",
            )

            guardian_name = None
            guardian_relation = None
            signed_by_type = "patient"

            if is_minor(patient.get("date_of_birth")):
                signed_by_type = "guardian"
                guardian_col, relation_col = st.columns(2)

                guardian_name = guardian_col.text_input(
                    "Guardian Name",
                    value=(
                        (existing_consent or {}).get("guardian_name")
                        or patient.get("emergency_contact_name")
                        or ""
                    ),
                    key="exam_guardian_name",
                )

                relation_options = ["Parent", "Guardian", "Spouse", "Sibling", "Other"]
                current_relation = (existing_consent or {}).get("guardian_relation") or "Parent"

                guardian_relation = relation_col.selectbox(
                    "Guardian Relationship",
                    relation_options,
                    index=relation_options.index(current_relation) if current_relation in relation_options else 0,
                    key="exam_guardian_relation",
                )

            if existing_consent and existing_consent.get("signature_path"):
                existing_sig_url = get_consent_signature_url(existing_consent["signature_path"])
                if existing_sig_url:
                    st.caption("Existing signature on file:")
                    st.image(existing_sig_url, width=180)
                    st.markdown("<span style='font-size:0.84rem; font-weight:600; color:var(--sa-ink);'>Update Signature (Draw below to replace):</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span style='font-size:0.84rem; font-weight:600; color:var(--sa-ink);'>Digital Signature (Draw below):</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span style='font-size:0.84rem; font-weight:600; color:var(--sa-ink);'>Digital Signature (Draw below):</span>", unsafe_allow_html=True)

            canvas_result = st_canvas(
                stroke_width=2,
                stroke_color="#0F172A",
                background_color="#FFFFFF",
                height=140,
                width=540,
                drawing_mode="freedraw",
                key=f"signature_canvas_{examination_id or 'new'}",
            )

            consent_confirmed = st.checkbox(
                "I confirm that the patient/guardian has willingly given informed consent for this examination.",
                key="exam_consent_confirm",
                value=True if is_edit else False,
            )

            # 3. AI Training Consent
            st.markdown("<div class='sa-form-section-title' style='margin-top:1.25rem;'>3. Research & AI Training Consent</div>", unsafe_allow_html=True)
            st.info("Under the Data Privacy Act, the patient must explicitly consent to their de-identified data being used for AI diagnostic research.")

            ai_consent = st.checkbox(
                "The patient has been informed and consents to their de-identified X-ray and clinical data being used to train the LungSight AI model.",
                key="exam_ai_consent_checkbox",
                value=True,
            )

            errors = st.container()

            # Actions
            st.divider()
            cancel_col, save_col = st.columns(2)

            cancel = cancel_col.button(
                "Cancel",
                key="exam_cancel",
                width="stretch",
            )

            save = save_col.button(
                "Save Examination",
                key="exam_save",
                type="primary",
                icon=":material/check_circle:",
                width="stretch",
            )

        with tab_history:
            prev_exams = get_examinations_by_patient(patient["patient_id"]) or []
            prev_records = get_medical_records_by_patient(patient["patient_id"]) or []

            st.markdown("<div class='sa-form-section-title'>Prior Examinations</div>", unsafe_allow_html=True)
            if prev_exams:
                for old_exam in prev_exams:
                    old_id = old_exam["examination_id"]
                    c1, c2, c3, c4 = st.columns([1.4, 2, 1.4, 1])
                    text_cell(c1, format_date(old_exam.get("examination_date")))
                    text_cell(c2, old_exam.get("examination_type"))
                    pill_cell(c3, old_exam.get("status"), STATUS_TONES.get(old_exam.get("status"), "grey"))
                    if c4.button("View", key=f"form_view_exam_{old_id}", width="stretch"):
                        open_dialog("view_exam", selected_examination=old_exam, selected_patient=patient)
            else:
                st.caption("No previous examination records.")

            st.markdown("<div class='sa-form-section-title' style='margin-top:1.2rem;'>External Medical Records</div>", unsafe_allow_html=True)
            if prev_records:
                for rec in prev_records:
                    rec_id = rec["medical_record_id"]
                    c1, c2, c3, c4 = st.columns([1.4, 1.8, 2.2, 1])
                    text_cell(c1, format_date(rec.get("record_date")))
                    text_cell(c2, rec.get("record_type") or "—")
                    text_cell(c3, rec.get("facility_name") or "—")
                    if c4.button("View", key=f"form_view_medical_{rec_id}", width="stretch"):
                        open_dialog("view_medical_record", selected_medical_record=rec, selected_patient=patient)
            else:
                st.caption("No previous external medical records.")

    if cancel:
        close_dialog()
        st.rerun()

    if not save:
        return

    if not signed_by_name.strip():
        errors.error("Patient/Guardian name is required.")
        return

    if not consent_confirmed:
        errors.error("Please confirm the informed consent.")
        return

    has_signature = False
    if canvas_result is not None and getattr(canvas_result, "image_data", None) is not None:
        json_objs = (canvas_result.json_data or {}).get("objects", []) if getattr(canvas_result, "json_data", None) else []
        if len(json_objs) > 0:
            has_signature = True
        elif canvas_result.image_data.ndim == 3 and canvas_result.image_data.shape[2] == 4:
            rgb = canvas_result.image_data[:, :, :3]
            alpha = canvas_result.image_data[:, :, 3]
            has_signature = bool((alpha > 0).any() and (rgb < 250).any())

    if not has_signature and not (existing_consent and existing_consent.get("signature_path")):
        errors.error("Please draw the patient/guardian signature on the canvas.")
        return

    try:
        if not is_edit:
            rows = create_examination(
                patient_id=patient["patient_id"],
                examination_type=FIXED_EXAM_TYPE,
                examination_date=date.today(),
                created_by=user_id,
                consent_given=True,
                consent_signed_by_name=signed_by_name.strip(),
                consent_signed_by_type=signed_by_type,
                consent_guardian_name=(guardian_name or "").strip() or None,
                consent_guardian_relation=guardian_relation,
                consent_witnessed_by=user_id,
                bp_systolic=bp_sys or None,
                bp_diastolic=bp_dia or None,
                temperature=temperature or None,
                ai_consent_given=ai_consent,
            )

            if not rows:
                errors.error("Failed to create examination record.")
                return

            exam_id = rows[0]["examination_id"]

            if has_signature:
                image = Image.fromarray(
                    canvas_result.image_data.astype("uint8"),
                    "RGBA",
                )
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")

                signature_path = upload_consent_signature(exam_id, buffer.getvalue())
                if signature_path:
                    consents = get_examination_consents(exam_id) or []
                    if consents:
                        update_examination_consent(
                            consents[0]["consent_id"],
                            signature_path=signature_path,
                        )

        else:
            if existing_consent:
                new_signature_path = None
                if has_signature:
                    image = Image.fromarray(
                        canvas_result.image_data.astype("uint8"),
                        "RGBA",
                    )
                    buffer = io.BytesIO()
                    image.save(buffer, format="PNG")
                    new_signature_path = upload_consent_signature(examination_id, buffer.getvalue())

                consent_kwargs = {
                    "given": True,
                    "signed_by_name": signed_by_name.strip(),
                    "signed_by_type": signed_by_type,
                    "guardian_name": (guardian_name or "").strip() or None,
                    "guardian_relation": guardian_relation,
                }
                if new_signature_path:
                    consent_kwargs["signature_path"] = new_signature_path

                update_examination_consent(
                    existing_consent["consent_id"],
                    **consent_kwargs,
                )

            if existing_vitals:
                update_examination_vitals(
                    existing_vitals[0]["vitals_id"],
                    bp_systolic=bp_sys or None,
                    bp_diastolic=bp_dia or None,
                    temperature=temperature or None,
                )

            update_examination(
                examination_id=examination_id,
                status="Pending",
            )

        remember("Examination saved successfully.")
        close_dialog()
        st.rerun()

    except Exception as error:
        errors.error(f"Failed to save examination: {error}")


# ============================================================
# FILTERS & SEARCH
# ============================================================

def show_filters(patients, hospitals=None):
    with st.container(key="sa_patient_filters"):
        if is_superadmin() and hospitals is not None:
            hospital_col, search_col, sex_col, status_col, reset_col = st.columns(
                [1.6, 2.6, 1.1, 1.1, 0.9],
                vertical_alignment="center",
            )

            hospital_names = ["All hospitals"] + sorted({
                h.get("hospital_name")
                for h in hospitals
                if h.get("hospital_name")
            })

            hospital_filter = hospital_col.selectbox(
                "Hospital",
                hospital_names,
                label_visibility="collapsed",
                key="exam_hospital_filter",
            )
        else:
            search_col, sex_col, status_col, reset_col = st.columns(
                [3.2, 1.2, 1.2, 0.9],
                vertical_alignment="center",
            )
            hospital_filter = "All hospitals"

        search = search_col.text_input(
            "Search",
            placeholder="Search by name, ID, or contact number...",
            label_visibility="collapsed",
            key="exam_search",
        ).strip().lower()

        sex = sex_col.selectbox(
            "Sex",
            ["All sexes", "Male", "Female"],
            label_visibility="collapsed",
            key="exam_sex",
        )

        status = status_col.selectbox(
            "Status",
            ["All status", "Active", "Inactive"],
            label_visibility="collapsed",
            key="exam_status",
        )

        def _reset_filters():
            st.session_state["exam_page"] = 1
            st.session_state["exam_search"] = ""
            st.session_state["exam_sex"] = "All sexes"
            st.session_state["exam_status"] = "All status"
            if "exam_hospital_filter" in st.session_state:
                st.session_state["exam_hospital_filter"] = "All hospitals"
            st.cache_data.clear()

        reset_col.button(
            "Reset",
            icon=":material/refresh:",
            width="stretch",
            key="exam_refresh",
            on_click=_reset_filters,
            help="Reset filters and refresh list",
        )

    # Track filter changes to reset pagination to page 1
    curr_filter_key = (search, sex, status, hospital_filter)
    prev_filter_key = (
        st.session_state.get("_prev_exam_search"),
        st.session_state.get("_prev_exam_sex"),
        st.session_state.get("_prev_exam_status"),
        st.session_state.get("_prev_exam_hosp"),
    )
    if prev_filter_key != curr_filter_key:
        st.session_state["exam_page"] = 1
        st.session_state["_prev_exam_search"] = search
        st.session_state["_prev_exam_sex"] = sex
        st.session_state["_prev_exam_status"] = status
        st.session_state["_prev_exam_hosp"] = hospital_filter

    matches = []
    for patient in patients:
        text = (
            f"{patient_name(patient)} "
            f"{patient.get('patient_code') or ''} "
            f"{patient.get('contact_number') or ''}"
        ).lower()

        if hospital_filter != "All hospitals" and patient_hospital_name(patient) != hospital_filter:
            continue

        if search and search not in text:
            continue

        if sex != "All sexes" and (patient.get("sex") or "").strip().lower() != sex.lower():
            continue

        patient_status = (patient.get("status") or "active").strip().lower()
        if status != "All status" and patient_status != status.lower():
            continue

        matches.append(patient)

    return matches


# ============================================================
# PATIENT TABLE WITH PAGINATION
# ============================================================

def render_patient_table(patients):
    if not patients:
        empty_state("No patients found matching your search or filter criteria.")
        return

    PAGE_SIZE = 15
    total_items = len(patients)
    total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)
    current_page = st.session_state.get("exam_page", 1)
    if current_page > total_pages:
        current_page = total_pages
        st.session_state["exam_page"] = current_page
    elif current_page < 1:
        current_page = 1
        st.session_state["exam_page"] = current_page

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

    if is_superadmin():
        with st.container(key="sa_table_exam_patients"):
            table_header(HEADERS_SUPERADMIN, WIDTHS_SUPERADMIN, "exam_patients")

            for patient in page_patients:
                patient_id = patient["patient_id"]

                with table_row(f"exam_patients_{patient_id}", WIDTHS_SUPERADMIN) as cols:
                    text_cell(cols[0], patient_hospital_name(patient), muted=True)
                    patient_code_cell(cols[1], patient_code(patient))
                    patient_name_cell(cols[2], patient)
                    patient_dob_cell(cols[3], patient.get("date_of_birth"))
                    pill_cell(cols[4], patient.get("sex") or "—", "blue" if (patient.get("sex") or "").lower() == "male" else "pink")
                    patient_contact_cell(cols[5], patient.get("contact_number"), patient.get("emergency_contact_no"))

                    if cols[6].button(
                        "Examine",
                        key=f"examine_{patient_id}",
                        icon=":material/clinical_notes:",
                        width="stretch",
                    ):
                        open_dialog("history", selected_patient=patient)

    else:
        with st.container(key="sa_table_exam_patients"):
            table_header(HEADERS, WIDTHS, "exam_patients")

            for patient in page_patients:
                patient_id = patient["patient_id"]

                with table_row(f"exam_patients_{patient_id}", WIDTHS) as cols:
                    patient_code_cell(cols[0], patient_code(patient))
                    patient_name_cell(cols[1], patient)
                    patient_dob_cell(cols[2], patient.get("date_of_birth"))
                    pill_cell(cols[3], patient.get("sex") or "—", "blue" if (patient.get("sex") or "").lower() == "male" else "pink")
                    patient_contact_cell(cols[4], patient.get("contact_number"), patient.get("emergency_contact_no"))

                    if cols[5].button(
                        "Examine",
                        key=f"examine_{patient_id}",
                        icon=":material/clinical_notes:",
                        width="stretch",
                    ):
                        open_dialog("history", selected_patient=patient)

    # Bottom pagination
    render_table_pagination(current_page, total_pages, total_items, start_idx, end_idx)


# ============================================================
# PAGE
# ============================================================

def show():
    load_css("manage_examinations.css")
    show_flash_message()

    hospital_id = current_hospital_id()

    with st.container(key="sa_page"):
        page_header(
            "Examinations",
            "Review patient examination histories, vital records, and clinical evaluations.",
        )

        patients = load_patients()

        # Role & Hospital Filtering
        if is_superadmin():
            hospitals = get_all_hospitals() or []
            matches = show_filters(patients, hospitals=hospitals)
        else:
            if hospital_id is None:
                st.error("Your account is not assigned to a hospital. Please contact your Superadmin.")
                st.stop()

            patients = [
                patient
                for patient in patients
                if patient.get("hospital_id") == hospital_id
            ]
            matches = show_filters(patients)

        # Overview Metrics Cards
        total_p = len(patients)
        active_p = sum(1 for p in patients if (p.get("status") or "active").strip().lower() == "active")
        male_p = sum(1 for p in patients if (p.get("sex") or "").strip().lower() == "male")
        female_p = sum(1 for p in patients if (p.get("sex") or "").strip().lower() == "female")

        m_cols = st.columns(4)
        with m_cols[0]:
            metric_card("Total Patients", total_p, "groups", "teal")
        with m_cols[1]:
            metric_card("Active Patients", active_p, "verified", "green")
        with m_cols[2]:
            metric_card("Male Patients", male_p, "male", "blue")
        with m_cols[3]:
            metric_card("Female Patients", female_p, "female", "amber")

        st.write("")

        # Render Main Patient Table
        render_patient_table(matches)

    # ========================================================
    # DIALOG ROUTER
    # ========================================================

    dialog = st.session_state.get("examination_dialog")

    if dialog == "history" and st.session_state.get("selected_patient"):
        show_patient_history(st.session_state["selected_patient"])

    elif dialog == "view_exam" and st.session_state.get("selected_examination"):
        show_examination_details(
            st.session_state["selected_patient"],
            st.session_state["selected_examination"],
        )

    elif dialog == "view_medical_record" and st.session_state.get("selected_medical_record"):
        show_medical_record_details(
            st.session_state["selected_patient"],
            st.session_state["selected_medical_record"],
        )

    elif dialog == "create" and st.session_state.get("create_examination_patient"):
        show_examination_form(
            st.session_state["create_examination_patient"],
            st.session_state.get("selected_examination"),
        )

    elif dialog == "delete" and st.session_state.get("delete_examination_target"):
        show_delete_examination_dialog(
            st.session_state["delete_examination_target"]
        )
