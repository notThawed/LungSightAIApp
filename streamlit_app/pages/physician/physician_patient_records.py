# streamlit_app/pages/physician/physician_patient_records.py

import streamlit as st
from datetime import datetime, date
from zoneinfo import ZoneInfo

from backend.supabase_client import admin_supabase
from backend.fetches import (
    get_completed_patients_with_latest_ai,
    get_examinations_by_patient,
    get_examination_vitals,
    get_medical_records_by_patient,
    get_xray_request_by_examination,
    get_xray_images_by_request,
    get_xray_image_url,
    get_xray_ai_result,
    get_xray_ai_heatmap,
    get_xray_review,
    get_medications_by_examination,
    get_referral_by_examination,
)
from backend.backend_utils.severity_utils import get_latest_severity, get_severity_alert

from streamlit_app.components.ui import (
    page_header, empty_state, section_title, show_rows, full_name,
    format_date, pill, show_flash_message,
)

from shared.assets import load_css


# ============================================================
# CONFIG
# ============================================================

ROLE_SUPERADMIN = 1
ROLE_RADIOLOGIST = 3
ROLE_HOSPITAL_ADMIN = 6
DOCTOR_ROLES = [ROLE_RADIOLOGIST]
ADMIN_ROLES = [ROLE_SUPERADMIN, ROLE_HOSPITAL_ADMIN]
MANILA_TZ = ZoneInfo("Asia/Manila")

CATEGORY_GENERAL = "general"
CATEGORY_FOLLOWUP = "followup"
CATEGORY_EXTERNAL = "external"

KEY_PATIENT = "physician_selected_patient"
KEY_CATEGORY = "physician_selected_category"
KEY_EXAM = "physician_selected_examination"
KEY_EXTERNAL = "pr_external_record"
KEY_EXTERNAL_SHOWN = "pr_external_displayed"


# ============================================================
# HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}

def current_role_id():
    return current_user().get("role_id")

def current_hospital_id():
    return current_user().get("hospital_id")

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

def parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
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
# EXAMINATION HELPERS
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
    normalized = str(exam_type).strip().lower().replace("_", " ").replace("-", " ")
    return "follow up" in normalized or "followup" in normalized

def is_inpatient_round(exam):
    """Check if this is a ward round record (child of admission)."""
    exam_type = (exam.get("examination_type") or "").strip().lower()
    return exam_type == "inpatient round"

def split_examination_history(examinations):
    """
    Split examinations into General Consults, Follow-Ups, and Inpatient Rounds.
    
    Inpatient Rounds are explicitly excluded from the General Consults list
    because they're rendered nested inside their parent admission record.
    """
    general, follow_ups, rounds = [], [], []
    for exam in examinations:
        if is_inpatient_round(exam):
            rounds.append(exam)
        elif is_follow_up_examination(exam):
            follow_ups.append(exam)
        else:
            general.append(exam)
    follow_ups.sort(key=lambda e: (e.get("follow_up_sequence") is None, e.get("follow_up_sequence") or 999999))
    return general, follow_ups, rounds

def display_exam_type(exam):
    if is_inpatient_round(exam):
        return "Inpatient Round"
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
        req = get_xray_request_by_examination(exam.get("examination_id"))
        if not req:
            return False
        imgs = get_xray_images_by_request(req.get("request_id")) or []
        return len(imgs) > 0
    except Exception:
        return False

def admission_status_badge(exam):
    """Return (label, tone) for the admission status."""
    if exam.get("status") == "Discharged":
        return ("Discharged", "green")
    if exam.get("status") == "Admitted":
        return ("Currently Admitted", "amber")
    if exam.get("disposition") == "Admission":
        return ("Admission Decision", "amber")
    return None


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

def load_patient_rows():
    role_id = current_role_id()
    hospital_id = current_hospital_id()
    if role_id == ROLE_SUPERADMIN:
        filter_hospital = None
    elif role_id in DOCTOR_ROLES or role_id == ROLE_HOSPITAL_ADMIN:
        filter_hospital = hospital_id
    else:
        return []
    try:
        return get_completed_patients_with_latest_ai(hospital_id=filter_hospital) or []
    except Exception as error:
        st.error(f"Failed to load patient records: {error}")
        return []


# ============================================================
# LEVEL 0 — PATIENT RECORDS LIST
# ============================================================

def render_patient_row(row):
    patient = row["patient"]
    patient_id = patient.get("patient_id")
    risk_label, risk_tone = risk_from_ai_findings(row.get("ai_findings"))
    curb_score = row.get("curb65_score")
    phys_sev = row.get("severity_status")

    if curb_score is not None:
        if curb_score <= 1: curb_tone, curb_text = "green", f"{curb_score}/5"
        elif curb_score == 2: curb_tone, curb_text = "amber", f"{curb_score}/5"
        else: curb_tone, curb_text = "red", f"{curb_score}/5"
    else:
        curb_tone, curb_text = "slate", "—"

    if phys_sev and phys_sev != "Not Assessed":
        if "Low" in phys_sev: phys_tone = "green"
        elif "Moderate" in phys_sev: phys_tone = "amber"
        elif "High" in phys_sev: phys_tone = "red"
        else: phys_tone = "slate"
        phys_text = phys_sev.replace(" Risk", "")
    else:
        phys_tone, phys_text = "slate", "—"

    with st.container(key=f"pr_row_{patient_id}"):
        cols = st.columns([1.2, 2.0, 0.6, 1.2, 1.0, 1.0, 0.8])
        with cols[0]:
            st.markdown(f"<div class='pr-cell pr-cell-id'>{patient_code(patient)}</div>", unsafe_allow_html=True)
        with cols[1]:
            st.markdown(
                f"<div class='pr-cell pr-cell-name'>{patient_name(patient)}</div>"
                f"<div class='pr-cell' style='font-size:0.7rem; padding-top:0;'>AI: {risk_label}</div>",
                unsafe_allow_html=True,
            )
        with cols[2]:
            st.markdown(f"<div class='pr-cell'>{calculate_age(patient.get('date_of_birth'))}</div>", unsafe_allow_html=True)
        with cols[3]:
            st.markdown(f"<div class='pr-cell'>{format_date_only(row.get('examination_date'))}</div>", unsafe_allow_html=True)
        with cols[4]:
            st.markdown(f"<div class='pr-cell'>{pill(curb_text, curb_tone)}</div>", unsafe_allow_html=True)
        with cols[5]:
            st.markdown(f"<div class='pr-cell'>{pill(phys_text, phys_tone)}</div>", unsafe_allow_html=True)
        with cols[6]:
            if st.button("View", key=f"view_pr_{patient_id}", icon=":material/visibility:", width="stretch"):
                go_to_patient_overview(patient)


def render_patient_list(rows):
    with st.container(key="physician_patient_records_page"):
        page_header("Patient Records", "View completed patient X-ray analyses and clinical history.")
        search = st.text_input(
            "Search patient",
            placeholder="Search by patient ID, name, or contact number",
            key="physician_patient_records_search",
            label_visibility="collapsed",
        ).strip().lower()

        if search:
            filtered = [r for r in rows if search in " ".join([
                str(patient_code(r["patient"]) or ""),
                str(patient_name(r["patient"]) or ""),
                str(r["patient"].get("contact_number") or ""),
            ]).lower()]
        else:
            filtered = rows

        st.divider()
        if not filtered:
            empty_state("No completed patient records found.")
            return

        with st.container(key="pr_table_header"):
            cols = st.columns([1.2, 2.0, 0.6, 1.2, 1.0, 1.0, 0.8])
            headers = ["Patient ID", "Patient Name", "Age", "Latest Exam", "CURB-65", "Clinical", "Action"]
            for col, label in zip(cols, headers):
                with col:
                    st.markdown(f"<div class='pr-header-cell'>{label}</div>", unsafe_allow_html=True)

        for row in filtered:
            render_patient_row(row)

        st.caption(f"Showing {len(filtered)} of {len(rows)} records")


# ============================================================
# LEVEL 1 — PATIENT OVERVIEW
# ============================================================

def count_category_items(patient):
    patient_id = patient.get("patient_id")
    exams = get_examinations_by_patient(patient_id) or []
    
    # IMPORTANT: Include Admitted and Discharged exams (not just Completed)
    # so admissions show up in the General Consults list.
    eligible = [e for e in exams if e.get("status") in ("Completed", "Admitted", "Discharged")]
    general, follow_ups, _rounds = split_examination_history(eligible)
    records = get_medical_records_by_patient(patient_id) or []
    return {
        CATEGORY_GENERAL: len(general),
        CATEGORY_FOLLOWUP: len(follow_ups),
        CATEGORY_EXTERNAL: len(records),
    }


def render_category_card(patient, category, title, icon, count):
    with st.container(key=f"pr_cat_{category}"):
        st.markdown(
            "<div class='pr-cat-card'>"
            f"<span class='pr-cat-icon material-symbols-rounded'>{icon}</span>"
            f"<p class='pr-cat-title'>{title}</p>"
            f"<p class='pr-cat-count'>{count} record{'s' if count != 1 else ''}</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("View", key=f"pr_cat_view_{category}", icon=":material/arrow_forward:", type="primary", width="stretch"):
            go_to_category(patient, category)


def render_patient_overview(patient):
    if st.button("Back to Patient Records", key="pr_back_to_list", icon=":material/arrow_back:"):
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
        f"<b>{calculate_age(patient.get('date_of_birth'))} / {patient.get('sex') or '—'}</b>"
        "</div>"
        "<div class='pr-hero-row'>"
        "<span>Contact</span>"
        f"<b>{patient.get('contact_number') or '—'}</b>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Latest severity assessment
    exams = get_examinations_by_patient(patient.get("patient_id")) or []
    latest = get_latest_severity(exams)
    alert_level, alert_msg = get_severity_alert(exams, latest)

    curb_score = latest.get("curb65_score") if latest else None
    phys_sev = latest.get("severity_status") if latest else None

    if curb_score is not None:
        if curb_score <= 1: curb_tone, curb_label = "green", "Low Risk"
        elif curb_score == 2: curb_tone, curb_label = "amber", "Moderate Risk"
        else: curb_tone, curb_label = "red", "High Risk"
        curb_pill = pill(f"Score: {curb_score} - {curb_label}", curb_tone)
    else:
        curb_pill = pill("Not Assessed", "slate")

    if phys_sev and phys_sev != "Not Assessed":
        if "Low" in phys_sev: phys_tone = "green"
        elif "Moderate" in phys_sev: phys_tone = "amber"
        elif "High" in phys_sev: phys_tone = "red"
        else: phys_tone = "slate"
        phys_pill = pill(phys_sev, phys_tone)
    else:
        phys_pill = pill("Not Assessed", "slate")

    alert_html = ""
    if alert_level == "warning":
        alert_html = f"<div style='margin-top: 1rem; padding: 0.75rem; background: #FEE2E2; color: #B91C1C; border-radius: 8px; font-size: 0.8rem; font-weight: 500;'>{alert_msg}</div>"
    elif alert_level == "info":
        alert_html = f"<div style='margin-top: 1rem; padding: 0.75rem; background: #E8F4F6; color: #0F7C88; border-radius: 8px; font-size: 0.8rem; font-weight: 500;'>{alert_msg}</div>"

    st.markdown(
        "<div class='pr-hero-card'>"
        "<p class='pr-hero-eyebrow'>Latest Severity Assessment</p>"
        f"<p class='pr-hero-name' style='font-size:0.9rem; color:#5A6F7F; margin-bottom:0.75rem; font-weight:500;'>Based on examination: {format_date_only(latest.get('examination_date')) if latest else 'None'}</p>"
        "<div style='display: flex; gap: 2rem; margin-top: 0.5rem;'>"
        "<div style='flex: 1;'>"
        "<p style='color:#0F7C88; font-weight:700; font-size:0.75rem; text-transform:uppercase; margin-bottom:0.25rem;'>CURB-65 (Calculated)</p>"
        f"<div>{curb_pill}</div>"
        "</div>"
        "<div style='flex: 1;'>"
        "<p style='color:#B45309; font-weight:700; font-size:0.75rem; text-transform:uppercase; margin-bottom:0.25rem;'>Physician Manual (Clinical)</p>"
        f"<div>{phys_pill}</div>"
        "</div>"
        "</div>"
        f"{alert_html}"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<p class='pr-section-label'>Select a category to review</p>", unsafe_allow_html=True)

    counts = count_category_items(patient)
    col1, col2, col3 = st.columns(3, gap="medium")
    with col1:
        render_category_card(patient, CATEGORY_GENERAL, "General Consults", "clinical_notes", counts[CATEGORY_GENERAL])
    with col2:
        render_category_card(patient, CATEGORY_FOLLOWUP, "Follow-Up Examinations", "event_repeat", counts[CATEGORY_FOLLOWUP])
    with col3:
        render_category_card(patient, CATEGORY_EXTERNAL, "External Records", "folder_shared", counts[CATEGORY_EXTERNAL])


# ============================================================
# LEVEL 2 — CATEGORY LIST
# ============================================================

def render_exam_list_card(exam):
    exam_id = exam.get("examination_id")
    exam_date = exam.get("examination_date") or exam.get("created_at")
    has_xray = exam_has_xray(exam)

    if has_xray:
        xray_icon, xray_text, xray_class = "check_circle", "Available", "pr-xray-available"
    else:
        xray_icon, xray_text, xray_class = "warning", "No X-Ray", "pr-xray-missing"

    chief = (exam.get("chief_complaint") or "—").strip()
    if len(chief) > 80: chief = chief[:80] + "…"
    diagnosis = (exam.get("diagnosis") or "—").strip()
    if len(diagnosis) > 80: diagnosis = diagnosis[:80] + "…"

    # Admission status badge
    adm_badge = admission_status_badge(exam)
    badge_html = ""
    if adm_badge:
        badge_label, badge_tone = adm_badge
        badge_html = f"<div style='margin-bottom:0.4rem;'>{pill(badge_label, badge_tone)}</div>"

    with st.container(key=f"pr_exam_card_{exam_id}"):
        st.markdown(
            "<div class='pr-exam-card'>"
            "<div class='pr-exam-head'>"
            f"<p class='pr-exam-title'>{display_exam_type(exam)}</p>"
            f"<span class='pr-exam-date'>{format_date_only(exam_date)} · {format_time_only(exam_date)}</span>"
            "</div>"
            f"{badge_html}"
            "<div class='pr-exam-row'>"
            f"<span>Chief Complaint</span><b>{chief}</b>"
            "</div>"
            "<div class='pr-exam-row'>"
            f"<span>Diagnosis</span><b>{diagnosis}</b>"
            "</div>"
            "<div class='pr-exam-row'>"
            "<span>X-Ray</span>"
            f"<b class='{xray_class}'><span class='material-symbols-rounded pr-xray-icon'>{xray_icon}</span>{xray_text}</b>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("View Details", key=f"pr_exam_view_{exam_id}", icon=":material/arrow_forward:", type="primary", width="stretch"):
            go_to_examination(exam)


def render_record_list_card(record):
    record_id = record.get("medical_record_id") or record.get("record_id")
    with st.container(key=f"pr_rec_card_{record_id}"):
        st.markdown(
            "<div class='pr-exam-card'>"
            "<div class='pr-exam-head'>"
            f"<p class='pr-exam-title'>{record.get('record_type') or 'Medical Record'}</p>"
            f"<span class='pr-exam-date'>{format_date(record.get('record_date'))}</span>"
            "</div>"
            "<div class='pr-exam-row'>"
            f"<span>Facility</span><b>{record.get('facility_name') or '—'}</b>"
            "</div>"
            "<div class='pr-exam-row'>"
            f"<span>Diagnosis</span><b>{record.get('diagnosis') or '—'}</b>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("View Details", key=f"pr_rec_view_{record_id}", icon=":material/open_in_new:", width="stretch"):
            st.session_state[KEY_EXTERNAL] = record
            st.session_state.pop(KEY_EXTERNAL_SHOWN, None)
            st.rerun()


def render_category_list(patient, category):
    category_titles = {
        CATEGORY_GENERAL: "General Consults",
        CATEGORY_FOLLOWUP: "Follow-Up Examinations",
        CATEGORY_EXTERNAL: "External Records",
    }
    if st.button("Back to Patient Overview", key="pr_back_to_overview", icon=":material/arrow_back:"):
        back_to_patient_overview()

    st.markdown(
        "<div class='pr-report-header'>"
        f"<p class='pr-report-title'>{category_titles.get(category, 'Records')}</p>"
        f"<p class='pr-report-sub'>{patient_name(patient)} · {patient_code(patient)}</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    patient_id = patient.get("patient_id")
    if category in (CATEGORY_GENERAL, CATEGORY_FOLLOWUP):
        exams = get_examinations_by_patient(patient_id) or []
        # Include Admitted and Discharged so admission records show up
        eligible = [e for e in exams if e.get("status") in ("Completed", "Admitted", "Discharged")]
        general, follow_ups, _rounds = split_examination_history(eligible)
        items = general if category == CATEGORY_GENERAL else follow_ups
        if not items:
            empty_state(f"No completed {category_titles.get(category, 'records').lower()}.")
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
# EXTERNAL RECORD DIALOG
# ============================================================

@st.dialog("External Medical Record", width="medium")
def show_external_record_dialog(record):
    st.markdown(
        "<div class='pr-report-header'>"
        f"<p class='pr-report-title'>{record.get('record_type') or 'Medical Record'}</p>"
        f"<p class='pr-report-sub'>{format_date(record.get('record_date'))}</p>"
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
    if st.button("Close", key="pr_external_close", width="stretch"):
        st.session_state.pop(KEY_EXTERNAL, None)
        st.session_state.pop(KEY_EXTERNAL_SHOWN, None)
        st.rerun()


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
        f"<b>{calculate_age(patient.get('date_of_birth'))} / {patient.get('sex') or '—'}</b>"
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
            f"<div class='pr-conf-label'><span>AI Confidence</span><b>{conf_pct:.1f}%</b></div>"
            f"<div class='pr-conf-bar'><div class='pr-conf-fill' style='width:{conf_pct}%'></div></div>"
            "</div>"
        )
    else:
        conf_block = "<div class='pr-hero-row'><span>AI Confidence</span><b>—</b></div>"

    st.markdown(
        "<div class='pr-hero-card'>"
        "<p class='pr-hero-eyebrow'>Risk Assessment</p>"
        "<div class='pr-hero-row'><span>Risk Level</span>"
        f"<div>{pill(risk_label, risk_tone)}</div></div>"
        "<div class='pr-hero-row'><span>Pneumonia Type</span>"
        f"<div>{pill(type_label, type_tone)}</div></div>"
        f"{conf_block}"
        "</div>",
        unsafe_allow_html=True,
    )


def render_severity_card(exam):
    curb_score = exam.get("curb65_score")
    phys_sev = exam.get("severity_status")

    if curb_score is not None:
        if curb_score <= 1: curb_tone, curb_label = "green", "Low Risk"
        elif curb_score == 2: curb_tone, curb_label = "amber", "Moderate Risk"
        else: curb_tone, curb_label = "red", "High Risk"
        curb_html = f"<div class='pr-hero-row'><span>Calculated Score</span><div>{pill(f'Score: {curb_score} - {curb_label}', curb_tone)}</div></div>"
    else:
        curb_html = "<div class='pr-hero-row'><span>Calculated Score</span><b>Not assessed</b></div>"

    if phys_sev and phys_sev != "Not Assessed":
        if "Low" in phys_sev: phys_tone = "green"
        elif "Moderate" in phys_sev: phys_tone = "amber"
        elif "High" in phys_sev: phys_tone = "red"
        else: phys_tone = "slate"
        phys_html = f"<div class='pr-hero-row'><span>Clinical Judgment</span><div>{pill(phys_sev, phys_tone)}</div></div>"
    else:
        phys_html = "<div class='pr-hero-row'><span>Clinical Judgment</span><b>Not assessed</b></div>"

    st.markdown(
        "<div class='pr-hero-card'>"
        "<p class='pr-hero-eyebrow'>Severity Assessment</p>"
        "<p class='pr-hero-name' style='font-size:0.9rem; color:#5A6F7F; margin-bottom:0.75rem; font-weight:500;'>Two independent severity statuses</p>"
        "<p class='pr-sub-label' style='color:#0F7C88; font-weight:700; font-size:0.75rem; text-transform:uppercase; margin-top:0.5rem;'>CURB-65 (Calculated)</p>"
        f"{curb_html}"
        "<p class='pr-sub-label' style='color:#B45309; font-weight:700; font-size:0.75rem; text-transform:uppercase; margin-top:1rem;'>Physician Manual (Clinical)</p>"
        f"{phys_html}"
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
        + "".join(f"<div class='pr-hero-row'><span>{label}</span><b>{value}</b></div>" for label, value in rows)
        + "</div>",
        unsafe_allow_html=True,
    )


def render_xray_analysis(exam):
    section_title("X-Ray Analysis", "Chest X-ray submitted for this examination.")
    exam_id = exam.get("examination_id")
    request = get_xray_request_by_examination(exam_id)

    if not request:
        st.markdown(
            "<div class='pr-no-xray'>"
            "<span class='pr-no-xray-icon material-symbols-rounded'>radiology</span>"
            "<p class='pr-no-xray-title'>No X-Ray Requested</p>"
            "<p class='pr-no-xray-text'>No chest X-ray was requested for this examination.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return None, None, None

    images = get_xray_images_by_request(request["request_id"]) or []
    if not images:
        st.markdown(
            "<div class='pr-no-xray'>"
            "<span class='pr-no-xray-icon material-symbols-rounded'>schedule</span>"
            "<p class='pr-no-xray-title'>X-Ray Pending</p>"
            "<p class='pr-no-xray-text'>An X-ray was requested but no image has been uploaded yet.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return request, None, None

    image = images[0]
    image_url = get_xray_image_url(image.get("image_path"))
    ai = get_xray_ai_result(image.get("image_id"))

    original_col, heatmap_col = st.columns(2, gap="medium")
    with original_col:
        st.markdown("<p class='pr-img-label'>Original X-Ray</p>", unsafe_allow_html=True)
        if image_url:
            with st.container(key="pr_xray_frame"):
                st.image(image_url, width="stretch")
        else:
            st.warning("Unable to load the X-ray image.")

    with heatmap_col:
        st.markdown("<p class='pr-img-label'>AI Heatmap Overlay</p>", unsafe_allow_html=True)
        heatmap_bytes = get_xray_ai_heatmap(ai.get("ai_result_id")) if ai and ai.get("ai_result_id") else None
        if heatmap_bytes:
            st.image(heatmap_bytes, caption="Grad-CAM overlay — highlighted regions indicate areas that influenced the AI prediction. This is an explanatory aid, not a diagnosis.", width="stretch")
        else:
            st.markdown(
                "<div class='pr-heatmap-placeholder'>"
                "<span class='pr-heatmap-icon material-symbols-rounded'>radiology</span>"
                "<p class='pr-heatmap-title'>Heatmap Unavailable</p>"
                "<p class='pr-heatmap-text'>No saved Grad-CAM visualization is available for this X-ray.</p>"
                "</div>",
                unsafe_allow_html=True,
            )
    return request, image, ai


def ai_findings_narrative(ai_findings, pneumonia_type):
    if not ai_findings: return None
    normalized = str(ai_findings).strip().lower()
    if normalized == "positive":
        if pneumonia_type == "bacterial_pneumonia":
            return "The AI model has detected patterns consistent with <b>bacterial pneumonia</b>. Recommend clinical correlation, CBC and blood culture, and consideration of empirical antibiotic therapy."
        if pneumonia_type == "viral_pneumonia":
            return "The AI model has detected patterns consistent with <b>viral pneumonia</b>. Recommend clinical correlation, symptomatic management, and follow-up assessment."
        return "The AI model has detected patterns consistent with <b>pneumonia</b>. Recommend clinical correlation and physician review."
    if normalized == "negative":
        return "The AI model has <b>not</b> detected patterns consistent with pneumonia. Continue standard clinical evaluation."
    return None


def ai_recommendations(ai_findings, pneumonia_type):
    if not ai_findings: return []
    normalized = str(ai_findings).strip().lower()
    if normalized == "positive":
        base = ["Immediate clinical evaluation recommended", "Consider blood culture and CBC"]
        if pneumonia_type == "bacterial_pneumonia": base.append("Initiate empirical antibiotic therapy")
        elif pneumonia_type == "viral_pneumonia": base.append("Consider antiviral or supportive therapy")
        base.append("Follow-up X-ray in 48–72 hours")
        return base
    if normalized == "negative":
        return ["Continue standard clinical evaluation", "Reassess if symptoms worsen"]
    return []


def render_ai_summary(ai, ai_findings, pneumonia_type, ai_conf):
    section_title("AI Findings Summary")
    narrative = ai_findings_narrative(ai_findings, pneumonia_type)
    if not narrative:
        st.caption("No AI summary available for this record.")
        return

    risk_label, risk_tone = risk_from_ai_findings(ai_findings)
    conf_pct = confidence_percent(ai_conf)
    tone_class = "pr-ai-summary-positive" if risk_tone == "red" else "pr-ai-summary-negative"
    conf_line = f"<br><span class='pr-ai-summary-meta'>Confidence: <b>{conf_pct:.1f}%</b></span>" if conf_pct is not None else ""

    st.markdown(f"<div class='pr-ai-summary {tone_class}'><p class='pr-ai-summary-text'>{narrative}</p>{conf_line}</div>", unsafe_allow_html=True)

    recs = ai_recommendations(ai_findings, pneumonia_type)
    if recs:
        section_title("Recommendations")
        items = "".join(f"<li><span class='pr-rec-num'>{i+1}</span><span>{text}</span></li>" for i, text in enumerate(recs))
        st.markdown(f"<ul class='pr-rec-list'>{items}</ul>", unsafe_allow_html=True)

    st.markdown(
        "<div class='pr-disclaimer'><b>Disclaimer:</b> This AI-generated analysis is intended to assist medical professionals and should not be used as the sole basis for clinical decisions. Always correlate with clinical findings and consult with qualified healthcare providers.</div>",
        unsafe_allow_html=True,
    )


def render_admission_banner(exam):
    """
    Show admission status prominently at the top of the admission consult.
    This is the parent consult that triggered the admission.
    """
    if exam.get("disposition") != "Admission":
        return

    status = exam.get("status")
    if status == "Discharged":
        discharge_date = format_date_only(exam.get("time_of_discharge"))
        st.markdown(
            f"<div style='padding: 1rem 1.25rem; background: #EAF6F1; border-left: 4px solid #2E8B6A; border-radius: 8px; margin-bottom: 1.5rem;'>"
            f"<p style='margin: 0 0 0.25rem 0; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #2E8B6A;'>"
            f"Admission Episode — Discharged"
            f"</p>"
            f"<p style='margin: 0; font-size: 0.9rem; color: #12283A; font-weight: 600;'>"
            f"Discharged on {discharge_date}. This admission episode is closed."
            f"</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
    elif status == "Admitted":
        admitted_at = format_date_only(exam.get("time_in") or exam.get("examination_date"))
        st.markdown(
            f"<div style='padding: 1rem 1.25rem; background: #FEF3C7; border-left: 4px solid #B45309; border-radius: 8px; margin-bottom: 1.5rem;'>"
            f"<p style='margin: 0 0 0.25rem 0; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #B45309;'>"
            f"Admission Episode — Currently Admitted"
            f"</p>"
            f"<p style='margin: 0; font-size: 0.9rem; color: #12283A; font-weight: 600;'>"
            f"Admitted on {admitted_at}. Patient is currently under inpatient care."
            f"</p>"
            f"</div>",
            unsafe_allow_html=True,
        )


def render_inpatient_timeline(exam):
    """
    Show the inpatient rounds and discharge info nested inside the parent admission.
    """
    if exam.get("disposition") != "Admission":
        return

    exam_id = exam.get("examination_id")
    st.divider()
    section_title("Inpatient Monitoring")

    # Fetch rounds
    try:
        res = (
            admin_supabase.table("examinations")
            .select("*")
            .eq("parent_examination_id", exam_id)
            .order("examination_date", desc=True)
            .execute()
        )
        rounds = res.data or []
    except Exception as e:
        st.error(f"Failed to load inpatient rounds: {e}")
        rounds = []

    # Fetch vitals for all rounds
    v_map = {}
    if rounds:
        round_ids = [r["examination_id"] for r in rounds]
        try:
            v_res = (
                admin_supabase.table("examination_vitals")
                .select("*")
                .in_("examination_id", round_ids)
                .order("recorded_at", desc=True)
                .execute()
            )
            for v in v_res.data or []:
                v_map.setdefault(v.get("examination_id"), v)
        except Exception:
            pass

    # Summary banner
    if not rounds:
        st.info("No daily rounds have been logged for this admission yet.")
    else:
        total_rounds = len(rounds)
        st.caption(f"{total_rounds} inpatient round(s) recorded for this admission.")

        # Table-style rendering
        widths = [1.5, 0.8, 0.8, 0.8, 0.9, 3.0]
        with st.container(key=f"pr_inpatient_header_{exam_id}"):
            h1, h2, h3, h4, h5, h6 = st.columns(widths)
            h1.markdown("<span class='ip-th'>Date & Time</span>", unsafe_allow_html=True)
            h2.markdown("<span class='ip-th'>Day</span>", unsafe_allow_html=True)
            h3.markdown("<span class='ip-th'>SpO₂</span>", unsafe_allow_html=True)
            h4.markdown("<span class='ip-th'>Temp</span>", unsafe_allow_html=True)
            h5.markdown("<span class='ip-th'>Resp. Rate</span>", unsafe_allow_html=True)
            h6.markdown("<span class='ip-th'>Clinical Notes</span>", unsafe_allow_html=True)

        # Admission day for Hospital Day calc
        admit_day = parse_datetime(exam.get("time_in") or exam.get("examination_date"))
        admit_day = admit_day.date() if admit_day else date.today()

        for r in rounds:
            v = v_map.get(r["examination_id"], {})
            r_dt = parse_datetime(r.get("examination_date"))
            if r_dt:
                date_str = r_dt.strftime("%b %d, %I:%M %p")
                r_day = max(1, (r_dt.date() - admit_day).days + 1)
            else:
                date_str = "—"
                r_day = 1

            with st.container(key=f"pr_inpatient_row_{r['examination_id']}"):
                c1, c2, c3, c4, c5, c6 = st.columns(widths, vertical_alignment="center")
                c1.markdown(f"<span class='ip-cell-strong'>{date_str}</span>", unsafe_allow_html=True)
                c2.markdown(f"<span class='ip-cell'>Day {r_day}</span>", unsafe_allow_html=True)
                c3.markdown(f"<span class='ip-cell'>{v.get('spo2') or '—'}%</span>", unsafe_allow_html=True)
                c4.markdown(f"<span class='ip-cell'>{v.get('temperature') or '—'}°C</span>", unsafe_allow_html=True)
                c5.markdown(f"<span class='ip-cell'>{v.get('respiratory_rate') or '—'}/min</span>", unsafe_allow_html=True)
                c6.markdown(f"<span class='ip-cell-notes'>{r.get('diagnosis') or '—'}</span>", unsafe_allow_html=True)

    # Linked follow-up
    if exam.get("status") == "Discharged":
        from backend.backend_utils.followup_utils import get_upcoming_follow_ups_by_patient
        try:
            patient_id = (exam.get("patients") or {}).get("patient_id") or exam.get("patient_id")
            follow_ups = get_upcoming_follow_ups_by_patient(patient_id) or []
            linked_fu = next((fu for fu in follow_ups if fu.get("source_examination_id") == exam_id), None)
            if linked_fu:
                st.markdown(
                    f"<div class='pr-hero-card' style='padding: 1rem; margin-top: 1rem; border-left: 3px solid #0F7C88;'>"
                    f"<p class='pr-hero-eyebrow' style='font-size: 0.7rem;'>Linked Post-Discharge Follow-Up</p>"
                    f"<p style='font-size: 0.85rem; color: #12283A; font-weight: 600; margin: 0;'>"
                    f"Scheduled for {format_date_only(linked_fu.get('follow_up_date'))}</p>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        except Exception:
            pass


def render_examination_report(patient, exam):
    if st.button("Back to Records", key="pr_back_to_category", icon=":material/arrow_back:"):
        back_to_category()

    # Admission banner if this is an admission
    render_admission_banner(exam)

    exam_date = exam.get("examination_date") or exam.get("created_at")
    st.markdown(
        "<div class='pr-report-header'>"
        "<p class='pr-report-title'>Analysis Report</p>"
        f"<p class='pr-report-sub'>Patient ID: {patient_code(patient)} · {format_date_only(exam_date)}</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    exam_id = exam.get("examination_id")
    ai, request, image = None, None, None

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
        with st.container(key="pr_hero_left"):
            render_patient_info_card(patient, exam)
            render_risk_card(ai_findings, ai_conf, pneumonia_type)
            render_severity_card(exam)
            render_examination_details_card(exam)
    with right_col:
        render_xray_analysis(exam)
        render_ai_summary(ai, ai_findings, pneumonia_type, ai_conf)

    # Inpatient timeline (only for admissions)
    render_inpatient_timeline(exam)


# ============================================================
# PAGE
# ============================================================

def show():
    load_css("patient_records.css", "inpatient_dashboard.css")
    show_flash_message()

    role_id = current_role_id()
    if role_id not in (DOCTOR_ROLES + ADMIN_ROLES):
        st.error("You don't have access to Patient Records.")
        return

    if st.session_state.get(KEY_EXTERNAL):
        if not st.session_state.get(KEY_EXTERNAL_SHOWN):
            show_external_record_dialog(st.session_state[KEY_EXTERNAL])
            st.session_state[KEY_EXTERNAL_SHOWN] = True
        else:
            st.session_state.pop(KEY_EXTERNAL, None)
            st.session_state.pop(KEY_EXTERNAL_SHOWN, None)
            st.rerun()

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