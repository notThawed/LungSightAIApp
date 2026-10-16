# streamlit_app/pages/manage_medical_records.py

"""
Manage Medical Records (3-level navigation, clone of physician_patient_records.py).

Level 1: Patient Overview  — 3 category cards
Level 2: Category List     — exams in one category / external records
Level 3: Examination Report — per-exam report

Role permissions:
    Superadmin          -> view all, heatmap, add external record
    Radiologist         -> view all, heatmap
    Radiologic Tech     -> view all
    Hospital Admin      -> view all, heatmap, add external record
    Staff               -> view all, add external record

Session keys (prefixed with mmr_ to isolate from physician page):
    mmr_selected_patient      -> dict
    mmr_selected_category     -> "general" | "followup" | "external"
    mmr_selected_examination  -> dict
    mmr_external_record       -> dict
    mmr_external_displayed    -> bool
"""

import streamlit as st

from datetime import datetime, date
from zoneinfo import ZoneInfo

from backend.fetches import (
    get_completed_patients_with_latest_ai,
    get_examinations_by_patient,
    get_medical_records_by_patient,
    get_xray_request_by_examination,
    get_xray_images_by_request,
    get_xray_image_url,
    get_xray_ai_result,
    get_xray_ai_heatmap,
    get_all_hospitals,
)

from backend.crud import (
    create_medical_record,
    upload_medical_record_file,
)

from streamlit_app.components.ui import (
    page_header,
    empty_state,
    section_title,
    show_rows,
    full_name,
    format_date,
    pill,
    remember,
    show_flash_message,
)

from shared.assets import load_css


# ============================================================
# CONFIG
# ============================================================

ROLE_SUPERADMIN = 1
ROLE_RADIOLOGIST = 3
ROLE_RADIOLOGIC_TECH = 4
ROLE_HOSPITAL_ADMIN = 6
ROLE_STAFF = 7

ALLOWED_ROLES = [
    ROLE_SUPERADMIN,
    ROLE_RADIOLOGIST,
    ROLE_RADIOLOGIC_TECH,
    ROLE_HOSPITAL_ADMIN,
    ROLE_STAFF,
]

HEATMAP_ROLES = [
    ROLE_SUPERADMIN,
    ROLE_RADIOLOGIST,
    ROLE_HOSPITAL_ADMIN,
]

ADD_RECORD_ROLES = [
    ROLE_SUPERADMIN,
    ROLE_HOSPITAL_ADMIN,
    ROLE_STAFF,
]

MANILA_TZ = ZoneInfo("Asia/Manila")

CATEGORY_GENERAL = "general"
CATEGORY_FOLLOWUP = "followup"
CATEGORY_EXTERNAL = "external"


# ============================================================
# SESSION KEYS (prefixed to isolate from physician page)
# ============================================================

KEY_PATIENT = "mmr_selected_patient"
KEY_CATEGORY = "mmr_selected_category"
KEY_EXAM = "mmr_selected_examination"
KEY_EXTERNAL = "mmr_external_record"
KEY_EXTERNAL_SHOWN = "mmr_external_displayed"
KEY_ADD_RECORD = "mmr_add_record_patient"


# ============================================================
# USER HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}


def current_role_id():
    return current_user().get("role_id")


def current_hospital_id():
    return current_user().get("hospital_id")


def can_view_heatmap():
    return current_role_id() in HEATMAP_ROLES


def can_add_record():
    return current_role_id() in ADD_RECORD_ROLES


def patient_name(patient):
    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )


def patient_code(patient):
    return patient.get("patient_code") or patient.get("patient_id")


def calculate_age(dob):
    if not dob:
        return "—"
    try:
        if isinstance(dob, str):
            dob_parsed = date.fromisoformat(str(dob)[:10])
        elif isinstance(dob, date):
            dob_parsed = dob
        else:
            return "—"

        today = date.today()
        age = today.year - dob_parsed.year

        if (today.month, today.day) < (dob_parsed.month, dob_parsed.day):
            age -= 1

        return age
    except Exception:
        return "—"


# ============================================================
# DATE / TIME
# ============================================================

def parse_datetime(value):
    if not value:
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=MANILA_TZ)

    return parsed.astimezone(MANILA_TZ)


def format_date_only(value):
    parsed = parse_datetime(value)
    if not parsed:
        return format_date(value) or "—"
    return parsed.strftime("%B %d, %Y")


def format_time_only(value):
    parsed = parse_datetime(value)
    if not parsed:
        return "—"
    return parsed.strftime("%I:%M %p")


# ============================================================
# RISK / CONFIDENCE
# ============================================================

def risk_from_ai_findings(ai_findings):
    if not ai_findings:
        return ("No AI Result", "slate")

    normalized = str(ai_findings).strip().lower()

    if normalized == "positive":
        return ("High Risk", "red")

    if normalized == "negative":
        return ("Low Risk", "green")

    return (str(ai_findings).title(), "slate")


def pneumonia_type_label(pneumonia_type):
    if pneumonia_type == "bacterial_pneumonia":
        return ("Bacterial Pneumonia", "red")
    if pneumonia_type == "viral_pneumonia":
        return ("Viral Pneumonia", "amber")
    return ("Not applicable", "slate")


def confidence_percent(value):
    if value is None:
        return None
    try:
        n = float(value)
        if n <= 1:
            n *= 100
        return round(n, 1)
    except (TypeError, ValueError):
        return None


# ============================================================
# EXAMINATION TYPE HELPERS
# ============================================================

def is_follow_up_examination(exam):
    sequence = exam.get("follow_up_sequence")
    if sequence is not None:
        try:
            if int(sequence) > 0:
                return True
        except (TypeError, ValueError):
            return True

    exam_type = exam.get("examination_type") or ""
    normalized = (
        str(exam_type)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )
    return "follow up" in normalized or "followup" in normalized


def split_examination_history(examinations):
    general = []
    follow_ups = []

    for exam in examinations:
        if is_follow_up_examination(exam):
            follow_ups.append(exam)
        else:
            general.append(exam)

    follow_ups.sort(
        key=lambda e: (
            e.get("follow_up_sequence") is None,
            e.get("follow_up_sequence") or 999999,
        )
    )

    return general, follow_ups


def display_exam_type(exam):
    if not is_follow_up_examination(exam):
        return exam.get("examination_type") or "General Consultation"

    seq = exam.get("follow_up_sequence")
    if seq is not None:
        try:
            return f"Follow-Up Examination {int(seq):03d}"
        except (TypeError, ValueError):
            pass

    return "Follow-Up Examination"


def exam_has_xray(exam):
    try:
        req = get_xray_request_by_examination(
            exam.get("examination_id")
        )
        if not req:
            return False
        imgs = get_xray_images_by_request(req.get("request_id")) or []
        return len(imgs) > 0
    except Exception:
        return False


# ============================================================
# NAVIGATION
# ============================================================

def go_to_patient_overview(patient):
    st.session_state[KEY_PATIENT] = patient
    st.session_state.pop(KEY_CATEGORY, None)
    st.session_state.pop(KEY_EXAM, None)
    st.rerun()


def go_to_category(patient, category):
    st.session_state[KEY_PATIENT] = patient
    st.session_state[KEY_CATEGORY] = category
    st.session_state.pop(KEY_EXAM, None)
    st.rerun()


def go_to_examination(exam):
    st.session_state[KEY_EXAM] = exam
    st.rerun()


def back_to_records_list():
    st.session_state.pop(KEY_PATIENT, None)
    st.session_state.pop(KEY_CATEGORY, None)
    st.session_state.pop(KEY_EXAM, None)
    st.rerun()


def back_to_patient_overview():
    st.session_state.pop(KEY_CATEGORY, None)
    st.session_state.pop(KEY_EXAM, None)
    st.rerun()


def back_to_category():
    st.session_state.pop(KEY_EXAM, None)
    st.rerun()


# ============================================================
# DATA LOADING
# ============================================================

def load_patient_rows(hospital_id=None):
    role_id = current_role_id()
    user_hospital_id = current_hospital_id()

    if role_id == ROLE_SUPERADMIN:
        filter_hospital = hospital_id  # may be None = all
    else:
        filter_hospital = user_hospital_id

    try:
        return get_completed_patients_with_latest_ai(
            hospital_id=filter_hospital
        ) or []
    except Exception as error:
        st.error(f"Failed to load patient records: {error}")
        return []


# ============================================================
# LEVEL 0 — PATIENT RECORDS LIST
# ============================================================

def render_patient_row(row):
    patient = row["patient"]
    patient_id = patient.get("patient_id")

    with st.container(key=f"mmr_row_{patient_id}"):

        cols = st.columns([1.4, 2.6, 0.9, 1.6, 1.0])

        with cols[0]:
            st.markdown(
                f"<div class='pr-cell pr-cell-id'>"
                f"{patient_code(patient)}</div>",
                unsafe_allow_html=True,
            )

        with cols[1]:
            st.markdown(
                f"<div class='pr-cell pr-cell-name'>"
                f"{patient_name(patient)}</div>",
                unsafe_allow_html=True,
            )

        with cols[2]:
            st.markdown(
                f"<div class='pr-cell'>"
                f"{calculate_age(patient.get('date_of_birth'))}</div>",
                unsafe_allow_html=True,
            )

        with cols[3]:
            st.markdown(
                f"<div class='pr-cell'>"
                f"{format_date_only(row.get('examination_date'))}</div>",
                unsafe_allow_html=True,
            )

        with cols[4]:
            if st.button(
                "View",
                key=f"mmr_view_{patient_id}",
                icon=":material/visibility:",
                width="stretch",
            ):
                go_to_patient_overview(patient)


def render_patient_list(rows):
    with st.container(key="manage_medical_records_page"):

        page_header(
            "Patient Records",
            "View completed patient X-ray analyses and clinical history.",
        )

        # ----------------------------------------------
        # FILTERS
        # ----------------------------------------------

        role_id = current_role_id()

        if role_id == ROLE_SUPERADMIN:
            hospital_col, search_col = st.columns([1.5, 3])

            hospitals = get_all_hospitals() or []

            hospital_names = ["All hospitals"] + sorted({
                h.get("hospital_name")
                for h in hospitals
                if h.get("hospital_name")
            })

            hospital_filter = hospital_col.selectbox(
                "Hospital",
                hospital_names,
                label_visibility="collapsed",
                key="mmr_hospital_filter",
            )

            search = search_col.text_input(
                "Search patient",
                placeholder="Search by patient ID, name, or contact number",
                key="mmr_search",
                label_visibility="collapsed",
            ).strip().lower()

            # Reload rows filtered by the selected hospital
            if hospital_filter != "All hospitals":
                selected_hospital_id = next(
                    (
                        h.get("hospital_id")
                        for h in hospitals
                        if h.get("hospital_name") == hospital_filter
                    ),
                    None,
                )
                rows = load_patient_rows(hospital_id=selected_hospital_id)
            else:
                rows = load_patient_rows(hospital_id=None)

        else:
            search = st.text_input(
                "Search patient",
                placeholder="Search by patient ID, name, or contact number",
                key="mmr_search",
                label_visibility="collapsed",
            ).strip().lower()

        # ----------------------------------------------
        # APPLY SEARCH
        # ----------------------------------------------

        if search:
            filtered = [
                r for r in rows
                if search in " ".join([
                    str(patient_code(r["patient"]) or ""),
                    str(patient_name(r["patient"]) or ""),
                    str(r["patient"].get("contact_number") or ""),
                ]).lower()
            ]
        else:
            filtered = rows

        st.divider()

        if not filtered:
            empty_state("No completed patient records found.")
            return

        # ----------------------------------------------
        # TABLE HEADER
        # ----------------------------------------------

        with st.container(key="mmr_table_header"):
            cols = st.columns([1.4, 2.6, 0.9, 1.6, 1.0])
            for col, label in zip(cols, [
                "Patient ID",
                "Patient Name",
                "Age",
                "Date",
                "Action",
            ]):
                with col:
                    st.markdown(
                        f"<div class='pr-header-cell'>{label}</div>",
                        unsafe_allow_html=True,
                    )

        for row in filtered:
            render_patient_row(row)

        st.caption(f"Showing {len(filtered)} of {len(rows)} records")


# ============================================================
# LEVEL 1 — PATIENT OVERVIEW
# ============================================================

def count_category_items(patient):
    patient_id = patient.get("patient_id")

    exams = get_examinations_by_patient(patient_id) or []
    completed = [e for e in exams if e.get("status") == "Completed"]

    general, follow_ups = split_examination_history(completed)
    records = get_medical_records_by_patient(patient_id) or []

    return {
        CATEGORY_GENERAL: len(general),
        CATEGORY_FOLLOWUP: len(follow_ups),
        CATEGORY_EXTERNAL: len(records),
    }


def render_category_card(
    patient,
    category,
    title,
    icon,
    count,
    allow_add=False,
):
    with st.container(key=f"mmr_cat_{category}"):

        st.markdown(
            "<div class='pr-cat-card'>"
            f"<span class='pr-cat-icon material-symbols-rounded'>{icon}</span>"
            f"<p class='pr-cat-title'>{title}</p>"
            f"<p class='pr-cat-count'>{count} "
            f"record{'s' if count != 1 else ''}</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        if st.button(
            "View",
            key=f"mmr_cat_view_{category}",
            icon=":material/arrow_forward:",
            type="primary",
            width="stretch",
        ):
            go_to_category(patient, category)

        if allow_add:
            if st.button(
                "Add",
                key=f"mmr_cat_add_{category}",
                icon=":material/add:",
                width="stretch",
            ):
                st.session_state[KEY_ADD_RECORD] = patient
                st.rerun()


def render_patient_overview(patient):
    if st.button(
        "Back to Patient Records",
        key="mmr_back_to_list",
        icon=":material/arrow_back:",
    ):
        back_to_records_list()

    st.markdown(
        "<div class='pr-report-header'>"
        "<p class='pr-report-title'>Patient Overview</p>"
        f"<p class='pr-report-sub'>Patient ID: {patient_code(patient)}</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='pr-hero-card'>"
        "<p class='pr-hero-eyebrow'>Patient Information</p>"
        f"<p class='pr-hero-name'>{patient_name(patient)}</p>"
        "<div class='pr-hero-row'>"
        f"<span>Patient ID</span><b>{patient_code(patient)}</b>"
        "</div>"
        "<div class='pr-hero-row'>"
        "<span>Age / Gender</span>"
        f"<b>{calculate_age(patient.get('date_of_birth'))} / "
        f"{patient.get('sex') or '—'}</b>"
        "</div>"
        "<div class='pr-hero-row'>"
        "<span>Contact</span>"
        f"<b>{patient.get('contact_number') or '—'}</b>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<p class='pr-section-label'>Select a category to review</p>",
        unsafe_allow_html=True,
    )

    counts = count_category_items(patient)

    col1, col2, col3 = st.columns(3, gap="medium")

    with col1:
        render_category_card(
            patient,
            CATEGORY_GENERAL,
            "General Consults",
            "clinical_notes",
            counts[CATEGORY_GENERAL],
        )

    with col2:
        render_category_card(
            patient,
            CATEGORY_FOLLOWUP,
            "Follow-Up Examinations",
            "event_repeat",
            counts[CATEGORY_FOLLOWUP],
        )

    with col3:
        render_category_card(
            patient,
            CATEGORY_EXTERNAL,
            "External Records",
            "folder_shared",
            counts[CATEGORY_EXTERNAL],
            allow_add=can_add_record(),
        )


# ============================================================
# LEVEL 2 — CATEGORY LIST
# ============================================================

def render_exam_list_card(exam):
    exam_id = exam.get("examination_id")
    exam_date = exam.get("examination_date") or exam.get("created_at")

    has_xray = exam_has_xray(exam)

    if has_xray:
        xray_icon = "check_circle"
        xray_text = "Available"
        xray_class = "pr-xray-available"
    else:
        xray_icon = "warning"
        xray_text = "No X-Ray"
        xray_class = "pr-xray-missing"

    chief = (exam.get("chief_complaint") or "—").strip()
    if len(chief) > 80:
        chief = chief[:80] + "…"

    diagnosis = (exam.get("diagnosis") or "—").strip()
    if len(diagnosis) > 80:
        diagnosis = diagnosis[:80] + "…"

    with st.container(key=f"mmr_exam_card_{exam_id}"):

        st.markdown(
            "<div class='pr-exam-card'>"
            "<div class='pr-exam-head'>"
            f"<p class='pr-exam-title'>{display_exam_type(exam)}</p>"
            f"<span class='pr-exam-date'>"
            f"{format_date_only(exam_date)} · "
            f"{format_time_only(exam_date)}</span>"
            "</div>"
            "<div class='pr-exam-row'>"
            f"<span>Chief Complaint</span><b>{chief}</b>"
            "</div>"
            "<div class='pr-exam-row'>"
            f"<span>Diagnosis</span><b>{diagnosis}</b>"
            "</div>"
            "<div class='pr-exam-row'>"
            "<span>X-Ray</span>"
            f"<b class='{xray_class}'>"
            f"<span class='material-symbols-rounded pr-xray-icon'>"
            f"{xray_icon}</span>{xray_text}</b>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        if st.button(
            "View Details",
            key=f"mmr_exam_view_{exam_id}",
            icon=":material/arrow_forward:",
            type="primary",
            width="stretch",
        ):
            go_to_examination(exam)


def render_record_list_card(record):
    record_id = record.get("medical_record_id") or record.get("record_id")

    with st.container(key=f"mmr_rec_card_{record_id}"):

        st.markdown(
            "<div class='pr-exam-card'>"
            "<div class='pr-exam-head'>"
            f"<p class='pr-exam-title'>"
            f"{record.get('record_type') or 'Medical Record'}</p>"
            f"<span class='pr-exam-date'>"
            f"{format_date(record.get('record_date'))}</span>"
            "</div>"
            "<div class='pr-exam-row'>"
            f"<span>Facility</span>"
            f"<b>{record.get('facility_name') or '—'}</b>"
            "</div>"
            "<div class='pr-exam-row'>"
            f"<span>Diagnosis</span>"
            f"<b>{record.get('diagnosis') or '—'}</b>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        if st.button(
            "View Details",
            key=f"mmr_rec_view_{record_id}",
            icon=":material/open_in_new:",
            width="stretch",
        ):
            st.session_state[KEY_EXTERNAL] = record
            st.session_state.pop(KEY_EXTERNAL_SHOWN, None)
            st.rerun()


def render_category_list(patient, category):
    category_titles = {
        CATEGORY_GENERAL: "General Consults",
        CATEGORY_FOLLOWUP: "Follow-Up Examinations",
        CATEGORY_EXTERNAL: "External Records",
    }

    back_col, add_col = st.columns([3, 1.4])

    with back_col:
        if st.button(
            "Back to Patient Overview",
            key="mmr_back_to_overview",
            icon=":material/arrow_back:",
        ):
            back_to_patient_overview()

    with add_col:
        if category == CATEGORY_EXTERNAL and can_add_record():
            if st.button(
                "Add External Record",
                key="mmr_add_from_list",
                icon=":material/add:",
                type="primary",
                width="stretch",
            ):
                st.session_state[KEY_ADD_RECORD] = patient
                st.rerun()

    st.markdown(
        "<div class='pr-report-header'>"
        f"<p class='pr-report-title'>"
        f"{category_titles.get(category, 'Records')}</p>"
        f"<p class='pr-report-sub'>"
        f"{patient_name(patient)} · {patient_code(patient)}</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    patient_id = patient.get("patient_id")

    if category in (CATEGORY_GENERAL, CATEGORY_FOLLOWUP):
        exams = get_examinations_by_patient(patient_id) or []
        completed = [e for e in exams if e.get("status") == "Completed"]
        general, follow_ups = split_examination_history(completed)

        items = general if category == CATEGORY_GENERAL else follow_ups

        if not items:
            empty_state(
                f"No completed "
                f"{category_titles.get(category, 'records').lower()}."
            )
            return

        for exam in items:
            render_exam_list_card(exam)

        return

    records = get_medical_records_by_patient(patient_id) or []

    if not records:
        empty_state("No external medical records found.")
        return

    for record in records:
        render_record_list_card(record)


# ============================================================
# EXTERNAL RECORD DIALOG (view)
# ============================================================

@st.dialog("External Medical Record", width="medium")
def show_external_record_dialog(record):
    st.markdown(
        "<div class='pr-report-header'>"
        f"<p class='pr-report-title'>"
        f"{record.get('record_type') or 'Medical Record'}</p>"
        f"<p class='pr-report-sub'>"
        f"{format_date(record.get('record_date'))}</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    show_rows([
        ("Facility", record.get("facility_name") or "—"),
        ("Department", record.get("department") or "—"),
        ("Attending Physician", record.get("attending_physician") or "—"),
        ("Chief Complaint", record.get("chief_complaint") or "—"),
        ("Clinical History", record.get("clinical_history") or "—"),
        ("Diagnosis", record.get("diagnosis") or "—"),
        ("Procedure", record.get("procedure_name") or "—"),
        ("Findings", record.get("findings") or "—"),
        ("Impression", record.get("impression") or "—"),
        ("Treatment", record.get("treatment") or "—"),
        ("Follow-Up", record.get("follow_up") or "—"),
    ])

    st.divider()

    if st.button(
        "Close",
        key="mmr_external_close",
        width="stretch",
    ):
        st.session_state.pop(KEY_EXTERNAL, None)
        st.session_state.pop(KEY_EXTERNAL_SHOWN, None)
        st.rerun()


# ============================================================
# ADD EXTERNAL RECORD DIALOG
# ============================================================

@st.dialog("Add External Medical Record", width="large")
def show_add_medical_record_dialog(patient):
    show_rows([
        ("Patient ID", patient_code(patient)),
        ("Patient", patient_name(patient)),
    ])

    with st.form("mmr_add_medical_record_form"):

        record_date = st.date_input(
            "Record date",
            value=date.today(),
            format="YYYY-MM-DD",
        )

        record_type = st.selectbox(
            "Record type",
            [
                "Consultation",
                "Hospitalization",
                "Laboratory",
                "Imaging",
                "Treatment",
                "Discharge Summary",
                "Other",
            ],
        )

        facility_name = st.text_input("Facility / Hospital")
        department = st.text_input("Department")
        attending_physician = st.text_input("Attending physician")
        chief_complaint = st.text_area("Chief complaint")
        clinical_history = st.text_area("Clinical history")
        diagnosis = st.text_area("Diagnosis")
        procedure_name = st.text_input("Procedure")
        findings = st.text_area("Findings")
        impression = st.text_area("Impression")
        treatment = st.text_area("Treatment")
        follow_up = st.text_area("Follow-up")

        uploaded_files = st.file_uploader(
            "Attach supporting files",
            type=["png", "jpg", "jpeg", "pdf"],
            accept_multiple_files=True,
        )

        cancel_col, save_col = st.columns(2)

        cancel = cancel_col.form_submit_button(
            "Cancel",
            width="stretch",
        )

        submitted = save_col.form_submit_button(
            "Save Medical Record",
            type="primary",
            width="stretch",
        )

    if cancel:
        st.session_state.pop(KEY_ADD_RECORD, None)
        st.rerun()

    if not submitted:
        return

    if not facility_name.strip():
        st.error("Facility / Hospital is required.")
        return

    try:
        result = create_medical_record(
            patient_id=patient["patient_id"],
            record_date=record_date,
            record_type=record_type,
            facility_name=facility_name.strip(),
            department=department.strip() or None,
            attending_physician=attending_physician.strip() or None,
            chief_complaint=chief_complaint.strip() or None,
            clinical_history=clinical_history.strip() or None,
            diagnosis=diagnosis.strip() or None,
            procedure_name=procedure_name.strip() or None,
            findings=findings.strip() or None,
            impression=impression.strip() or None,
            treatment=treatment.strip() or None,
            follow_up=follow_up.strip() or None,
            created_by=current_user().get("user_id"),
        )

        if not result.get("success"):
            st.error(
                result.get("message")
                or "Unable to create medical record."
            )
            return

        medical_record_id = result["data"]["medical_record_id"]

        for uploaded_file in (uploaded_files or []):
            upload_medical_record_file(
                medical_record_id=medical_record_id,
                uploaded_file=uploaded_file,
                image_type=uploaded_file.type or "File",
                description=uploaded_file.name,
            )

        remember("External medical record added.")

        # Clear dialog + force category refresh
        st.session_state.pop(KEY_ADD_RECORD, None)
        st.session_state[KEY_CATEGORY] = CATEGORY_EXTERNAL

        # If we were deep in an exam, back out to the external list
        st.session_state.pop(KEY_EXAM, None)

        st.rerun()

    except Exception as error:
        st.error(f"Failed to save medical record: {error}")


# ============================================================
# LEVEL 3 — EXAMINATION REPORT
# ============================================================

def render_patient_info_card(patient, exam):
    exam_date = exam.get("examination_date") or exam.get("created_at")

    st.markdown(
        "<div class='pr-hero-card'>"
        "<p class='pr-hero-eyebrow'>Patient Information</p>"
        f"<p class='pr-hero-name'>{patient_name(patient)}</p>"
        "<div class='pr-hero-row'>"
        f"<span>Patient ID</span><b>{patient_code(patient)}</b>"
        "</div>"
        "<div class='pr-hero-row'>"
        "<span>Age / Gender</span>"
        f"<b>{calculate_age(patient.get('date_of_birth'))} / "
        f"{patient.get('sex') or '—'}</b>"
        "</div>"
        "<div class='pr-hero-row'>"
        "<span>Scan Date</span>"
        f"<b>{format_date_only(exam_date)}</b>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_risk_card(ai_findings, ai_conf, pneumonia_type=None):
    risk_label, risk_tone = risk_from_ai_findings(ai_findings)
    conf_pct = confidence_percent(ai_conf)
    type_label, type_tone = pneumonia_type_label(pneumonia_type)

    if conf_pct is not None:
        conf_block = (
            "<div class='pr-hero-row pr-hero-row-block'>"
            "<div class='pr-conf-label'>"
            "<span>AI Confidence</span>"
            f"<b>{conf_pct:.1f}%</b>"
            "</div>"
            "<div class='pr-conf-bar'>"
            f"<div class='pr-conf-fill' style='width:{conf_pct}%'></div>"
            "</div>"
            "</div>"
        )
    else:
        conf_block = (
            "<div class='pr-hero-row'>"
            "<span>AI Confidence</span><b>—</b>"
            "</div>"
        )

    st.markdown(
        "<div class='pr-hero-card'>"
        "<p class='pr-hero-eyebrow'>Risk Assessment</p>"
        "<div class='pr-hero-row'>"
        "<span>Risk Level</span>"
        f"<div>{pill(risk_label, risk_tone)}</div>"
        "</div>"
        "<div class='pr-hero-row'>"
        "<span>Pneumonia Type</span>"
        f"<div>{pill(type_label, type_tone)}</div>"
        "</div>"
        f"{conf_block}"
        "</div>",
        unsafe_allow_html=True,
    )


def render_examination_details_card(exam):
    exam_date = exam.get("examination_date") or exam.get("created_at")

    rows = [
        ("Type", display_exam_type(exam)),
        ("Date", format_date_only(exam_date)),
        ("Time", format_time_only(exam_date)),
        ("Status", exam.get("status") or "—"),
        ("Chief Complaint", exam.get("chief_complaint") or "—"),
        ("HPI", exam.get("history_of_present_illness") or "—"),
        ("Physical Exam", exam.get("physical_examination") or "—"),
        ("Diagnosis", exam.get("diagnosis") or "—"),
        ("Plans / Orders", exam.get("plans_orders") or "—"),
        ("Disposition", exam.get("disposition") or "—"),
    ]

    st.markdown(
        "<div class='pr-hero-card'>"
        "<p class='pr-hero-eyebrow'>Examination Details</p>"
        + "".join(
            f"<div class='pr-hero-row'>"
            f"<span>{label}</span><b>{value}</b>"
            f"</div>"
            for label, value in rows
        )
        + "</div>",
        unsafe_allow_html=True,
    )


def render_xray_analysis(exam):
    section_title(
        "X-Ray Analysis",
        "Chest X-ray submitted for this examination.",
    )

    exam_id = exam.get("examination_id")
    request = get_xray_request_by_examination(exam_id)

    if not request:
        st.markdown(
            "<div class='pr-no-xray'>"
            "<span class='pr-no-xray-icon material-symbols-rounded'>"
            "radiology</span>"
            "<p class='pr-no-xray-title'>No X-Ray Requested</p>"
            "<p class='pr-no-xray-text'>"
            "No chest X-ray was requested for this examination."
            "</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return None, None, None

    images = get_xray_images_by_request(request["request_id"]) or []

    if not images:
        st.markdown(
            "<div class='pr-no-xray'>"
            "<span class='pr-no-xray-icon material-symbols-rounded'>"
            "schedule</span>"
            "<p class='pr-no-xray-title'>X-Ray Pending</p>"
            "<p class='pr-no-xray-text'>"
            "An X-ray was requested but no image has been "
            "uploaded yet."
            "</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return request, None, None

    image = images[0]
    image_url = get_xray_image_url(image.get("image_path"))
    ai = get_xray_ai_result(image.get("image_id"))

    show_heatmap = can_view_heatmap()

    if show_heatmap:
        original_col, heatmap_col = st.columns(2, gap="medium")
    else:
        original_col = st.container()
        heatmap_col = None

    with original_col:
        st.markdown(
            "<p class='pr-img-label'>Original X-Ray</p>",
            unsafe_allow_html=True,
        )
        if image_url:
            with st.container(key="mmr_xray_frame"):
                st.image(image_url, width="stretch")
        else:
            st.warning("Unable to load the X-ray image.")

    if show_heatmap and heatmap_col is not None:
        with heatmap_col:
            st.markdown(
                "<p class='pr-img-label'>AI Heatmap Overlay</p>",
                unsafe_allow_html=True,
            )

            heatmap_bytes = None

            if ai and ai.get("ai_result_id"):
                heatmap_bytes = get_xray_ai_heatmap(
                    ai.get("ai_result_id")
                )

            if heatmap_bytes:
                st.image(
                    heatmap_bytes,
                    caption=(
                        "Grad-CAM overlay — highlighted regions indicate "
                        "areas that influenced the AI prediction. This is "
                        "an explanatory aid, not a diagnosis."
                    ),
                    width="stretch",
                )
            else:
                st.markdown(
                    "<div class='pr-heatmap-placeholder'>"
                    "<span class='pr-heatmap-icon material-symbols-rounded'>"
                    "radiology</span>"
                    "<p class='pr-heatmap-title'>Heatmap Unavailable</p>"
                    "<p class='pr-heatmap-text'>"
                    "No saved Grad-CAM visualization is available for this X-ray."
                    "</p>"
                    "</div>",
                    unsafe_allow_html=True,
                )

    return request, image, ai


def ai_findings_narrative(ai_findings, pneumonia_type):
    if not ai_findings:
        return None

    normalized = str(ai_findings).strip().lower()

    if normalized == "positive":
        if pneumonia_type == "bacterial_pneumonia":
            return (
                "The AI model has detected patterns consistent "
                "with <b>bacterial pneumonia</b>. Recommend "
                "clinical correlation, CBC and blood culture, "
                "and consideration of empirical antibiotic therapy."
            )
        if pneumonia_type == "viral_pneumonia":
            return (
                "The AI model has detected patterns consistent "
                "with <b>viral pneumonia</b>. Recommend clinical "
                "correlation, symptomatic management, and "
                "follow-up assessment."
            )
        return (
            "The AI model has detected patterns consistent "
            "with <b>pneumonia</b>. Recommend clinical "
            "correlation and physician review."
        )

    if normalized == "negative":
        return (
            "The AI model has <b>not</b> detected patterns "
            "consistent with pneumonia. Continue standard "
            "clinical evaluation."
        )

    return None


def ai_recommendations(ai_findings, pneumonia_type):
    if not ai_findings:
        return []

    normalized = str(ai_findings).strip().lower()

    if normalized == "positive":
        base = [
            "Immediate clinical evaluation recommended",
            "Consider blood culture and CBC",
        ]

        if pneumonia_type == "bacterial_pneumonia":
            base.append("Initiate empirical antibiotic therapy")
        elif pneumonia_type == "viral_pneumonia":
            base.append("Consider antiviral or supportive therapy")

        base.append("Follow-up X-ray in 48–72 hours")
        return base

    if normalized == "negative":
        return [
            "Continue standard clinical evaluation",
            "Reassess if symptoms worsen",
        ]

    return []


def render_ai_summary(ai, ai_findings, pneumonia_type, ai_conf):
    section_title("AI Findings Summary")

    narrative = ai_findings_narrative(ai_findings, pneumonia_type)

    if not narrative:
        st.caption("No AI summary available for this record.")
        return

    risk_label, risk_tone = risk_from_ai_findings(ai_findings)
    conf_pct = confidence_percent(ai_conf)

    tone_class = (
        "pr-ai-summary-positive"
        if risk_tone == "red"
        else "pr-ai-summary-negative"
    )

    conf_line = (
        "<br><span class='pr-ai-summary-meta'>"
        f"Confidence: <b>{conf_pct:.1f}%</b>"
        "</span>"
        if conf_pct is not None
        else ""
    )

    st.markdown(
        f"<div class='pr-ai-summary {tone_class}'>"
        f"<p class='pr-ai-summary-text'>{narrative}</p>"
        f"{conf_line}"
        "</div>",
        unsafe_allow_html=True,
    )

    recs = ai_recommendations(ai_findings, pneumonia_type)

    if recs:
        section_title("Recommendations")

        items = "".join(
            f"<li><span class='pr-rec-num'>{i+1}</span>"
            f"<span>{text}</span></li>"
            for i, text in enumerate(recs)
        )

        st.markdown(
            f"<ul class='pr-rec-list'>{items}</ul>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<div class='pr-disclaimer'>"
        "<b>Disclaimer:</b> This AI-generated analysis is intended "
        "to assist medical professionals and should not be used as "
        "the sole basis for clinical decisions. Always correlate with "
        "clinical findings and consult with qualified healthcare providers."
        "</div>",
        unsafe_allow_html=True,
    )


def render_examination_report(patient, exam):
    if st.button(
        "Back to Records",
        key="mmr_back_to_category",
        icon=":material/arrow_back:",
    ):
        back_to_category()

    exam_date = exam.get("examination_date") or exam.get("created_at")

    st.markdown(
        "<div class='pr-report-header'>"
        "<p class='pr-report-title'>Analysis Report</p>"
        f"<p class='pr-report-sub'>"
        f"Patient ID: {patient_code(patient)} · "
        f"{format_date_only(exam_date)}</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    exam_id = exam.get("examination_id")

    ai = None
    request = None
    image = None

    try:
        request = get_xray_request_by_examination(exam_id)
        if request:
            imgs = get_xray_images_by_request(request["request_id"]) or []
            if imgs:
                image = imgs[0]
                ai = get_xray_ai_result(image.get("image_id"))
    except Exception:
        pass

    ai_findings = (ai or {}).get("ai_findings")
    pneumonia_type = (ai or {}).get("pneumonia_type")
    ai_conf = (ai or {}).get("ai_confidence")

    left_col, right_col = st.columns([1, 1.5], gap="large")

    with left_col:
        with st.container(key="mmr_hero_left"):
            render_patient_info_card(patient, exam)
            render_risk_card(ai_findings, ai_conf, pneumonia_type)
            render_examination_details_card(exam)

    with right_col:
        render_xray_analysis(exam)
        render_ai_summary(ai, ai_findings, pneumonia_type, ai_conf)


# ============================================================
# PAGE
# ============================================================

def show():
    load_css("patient_records.css")
    show_flash_message()

    role_id = current_role_id()

    if role_id not in ALLOWED_ROLES:
        st.error("You don't have access to Patient Records.")
        return

    # ========================================================
    # EXTERNAL RECORD DIALOG DISPATCHER — one-shot display
    # ========================================================

    if st.session_state.get(KEY_EXTERNAL):
        if not st.session_state.get(KEY_EXTERNAL_SHOWN):
            show_external_record_dialog(
                st.session_state[KEY_EXTERNAL]
            )
            st.session_state[KEY_EXTERNAL_SHOWN] = True
        else:
            st.session_state.pop(KEY_EXTERNAL, None)
            st.session_state.pop(KEY_EXTERNAL_SHOWN, None)
            st.rerun()

    # ========================================================
    # ADD RECORD DIALOG DISPATCHER
    # ========================================================

    if (
        st.session_state.get(KEY_ADD_RECORD)
        and can_add_record()
    ):
        show_add_medical_record_dialog(
            st.session_state[KEY_ADD_RECORD]
        )

    # ========================================================
    # ROUTER
    # ========================================================

    selected_patient = st.session_state.get(KEY_PATIENT)
    selected_category = st.session_state.get(KEY_CATEGORY)
    selected_exam = st.session_state.get(KEY_EXAM)

    if selected_patient and selected_exam:
        render_examination_report(selected_patient, selected_exam)
        return

    if selected_patient and selected_category:
        render_category_list(selected_patient, selected_category)
        return

    if selected_patient:
        render_patient_overview(selected_patient)
        return

    rows = load_patient_rows()
    render_patient_list(rows)