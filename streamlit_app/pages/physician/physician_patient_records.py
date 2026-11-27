# streamlit_app/pages/physician/physician_patient_records.py

import streamlit as st
# LUNGSIGHT_GEOSPATIAL_RECORDS_FIX_20261118
from backend.backend_utils.examination_record_utils import (
    is_finalized_examination_record, finalized_examination_records,
)
import streamlit.components.v1 as components
from datetime import datetime, date
from zoneinfo import ZoneInfo

from backend.supabase_client import admin_supabase
from backend.fetches import (
    get_completed_patients_with_latest_ai,
    get_examinations_by_patient,
    get_medical_records_by_patient,
    get_xray_request_by_examination,
    get_xray_images_by_request,
    get_xray_image_url,
    get_xray_ai_result,
    get_xray_ai_heatmap,
    get_all_patients,
    get_patient_xray_history,
)
from backend.backend_utils.severity_utils import get_latest_severity, get_severity_alert

from streamlit_app.components.ui import (
    page_header, empty_state, section_title, show_rows, full_name,
    format_date, pill, show_flash_message,
)
from streamlit_app.components.xray_comparison import (
    show_xray_comparison,
)

from backend.backend_utils.lab_request_utils import (
    get_requests_for_examination,
    get_requests_for_follow_up,
    signed_lab_document_url,
)

from shared.assets import load_css

# Share the existing hospital-branded X-ray print report with Medical Records.
from streamlit_app.pages.system_administrator.manage_medical_records import (
    trigger_print_report,
)


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
    exam_type = (exam.get("examination_type") or "").strip().lower()
    return exam_type == "inpatient round"

def split_examination_history(examinations):
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
    if exam.get("status") == "Discharged":
        return ("Discharged", "green")
    if exam.get("status") == "Admitted":
        return ("Currently Admitted", "amber")
    if exam.get("disposition") == "Admission":
        return ("Admission Decision", "amber")
    return None

def get_latest_patient_record_exam(examinations):
    """
    Return the newest finalized General Consult or
    Follow-Up Examination.

    Excludes inpatient rounds and unfinished examinations.
    Does not require a CURB-65 or manual severity assessment.
    """

    eligible = [
        exam
        for exam in (examinations or [])
        if is_finalized_examination_record(exam)
    ]

    if not eligible:
        return None

    def exam_sort_key(exam):
        exam_date = parse_datetime(
            exam.get("examination_date")
            or exam.get("created_at")
        )

        created_at = parse_datetime(
            exam.get("created_at")
        )

        return (
            exam_date.timestamp() if exam_date else 0,
            created_at.timestamp() if created_at else 0,
            str(exam.get("examination_id") or ""),
        )

    return max(eligible, key=exam_sort_key)

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
        rows = (
            get_completed_patients_with_latest_ai(
                hospital_id=filter_hospital
            )
            or []
        )

        updated_rows = []

        for original_row in rows:
            row = original_row.copy()

            patient = row.get("patient") or {}
            patient_id = patient.get("patient_id")

            if not patient_id:
                updated_rows.append(row)
                continue

            # Fetch this patient's complete examination history.
            examinations = (
                get_examinations_by_patient(patient_id)
                or []
            )

            # Use the same latest-examination rule
            # as the Patient Overview.
            latest_exam = get_latest_patient_record_exam(
                examinations
            )

            if latest_exam:
                row["examination_id"] = (
                    latest_exam.get("examination_id")
                )

                row["examination_date"] = (
                    latest_exam.get("examination_date")
                    or latest_exam.get("created_at")
                )

                row["examination_type"] = (
                    display_exam_type(latest_exam)
                )

                row["curb65_score"] = (
                    latest_exam.get("curb65_score")
                )

                row["severity_status"] = (
                    latest_exam.get("severity_status")
                )

            else:
                # Do not show outdated severity values
                # from a different examination.
                row["examination_id"] = None
                row["examination_date"] = None
                row["examination_type"] = None
                row["curb65_score"] = None
                row["severity_status"] = None

            # Preserve AI findings from the original query.
            updated_rows.append(row)

        # Sort patients by their actual latest examination.
        updated_rows.sort(
            key=lambda row: (
                parse_datetime(
                    row.get("examination_date")
                ).timestamp()
                if parse_datetime(
                    row.get("examination_date")
                )
                else 0
            ),
            reverse=True,
        )

        return updated_rows

    except Exception as error:
        st.error(
            f"Failed to load patient records: {error}"
        )
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
            exam_date = row.get("examination_date")
            exam_date_str = format_date_only(exam_date) if exam_date else "—"
            st.markdown(f"<div class='pr-cell'>{exam_date_str}</div>", unsafe_allow_html=True)
        with cols[4]:
            st.markdown(f"<div class='pr-cell'>{pill(curb_text, curb_tone)}</div>", unsafe_allow_html=True)
        with cols[5]:
            st.markdown(f"<div class='pr-cell'>{pill(phys_text, phys_tone)}</div>", unsafe_allow_html=True)
        with cols[6]:
            if st.button("View", key=f"view_pr_{patient_id}", icon=":material/visibility:", width="stretch"):
                go_to_patient_overview(patient)


def _clear_patient_search():
    st.session_state["physician_patient_records_search"] = ""


def render_patient_list(rows):
    with st.container(key="physician_patient_records_page"):
        page_header("Patient Records", "View completed patient X-ray analyses and clinical history.")

        search_col, clear_col = st.columns([5, 1])

        search = search_col.text_input(
            "Search patient",
            placeholder="Search by patient ID, name, or contact number",
            key="physician_patient_records_search",
            label_visibility="collapsed",
        ).strip().lower()

        # FIX: Use on_click callback to safely clear state without crashing
        clear_col.button(
            "Clear", 
            key="pr_clear_search", 
            icon=":material/close:",
            on_click=_clear_patient_search
        )

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
            if search:
                empty_state(f"No patient records match '{search}'.")
            else:
                empty_state("No patient records found.")
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
    eligible = finalized_examination_records(exams)
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
    # ============================================================
    # BACK NAVIGATION
    # ============================================================

    if st.button(
        "Back to Patient Records",
        key="pr_back_to_list",
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

    # ============================================================
    # PATIENT AND HOSPITAL INFORMATION
    # ============================================================

    patient_id = patient.get("patient_id")
    hospital_id = current_hospital_id()

    scoped_hospital_id = (
        None
        if current_role_id() == ROLE_SUPERADMIN
        else hospital_id
    )

    # ============================================================
    # X-RAY COMPARISON
    # ============================================================

    try:
        xray_history = (
            get_patient_xray_history(
                patient_id,
                hospital_id=scoped_hospital_id,
            )
            or []
        )
    except Exception:
        xray_history = []

    if len(xray_history) >= 2:
        if st.button(
            "Compare X-Rays",
            key=f"pr_compare_xray_{patient_id}",
            icon=":material/compare:",
            type="primary",
            width="stretch",
        ):
            show_xray_comparison(
                patient_id=patient_id,
                hospital_id=scoped_hospital_id,
            )

    # ============================================================
    # PATIENT INFORMATION
    # ============================================================

    st.markdown(
        "<div class='pr-hero-card'>"
        "<p class='pr-hero-eyebrow'>Patient Information</p>"
        f"<p class='pr-hero-name'>{patient_name(patient)}</p>"

        "<div class='pr-hero-row'>"
        f"<span>Patient ID</span>"
        f"<b>{patient_code(patient)}</b>"
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

    # ============================================================
    # LATEST SEVERITY ASSESSMENT
    # ============================================================
    #
    # IMPORTANT:
    #
    # Use the SAME examination-selection helper used by
    # load_patient_rows().
    #
    # This ensures the Patient Records table and Patient
    # Overview display information from the same examination.
    #
    # Eligible examinations:
    # - Completed General Consultation
    # - Completed Follow-Up Examination
    # - Admitted / Discharged examinations
    #
    # Excluded:
    # - Pending examinations
    # - Inpatient rounds
    #
    # Do not fall back to an older examination simply
    # because the latest examination has no severity score.
    # ============================================================

    try:
        exams = (
            get_examinations_by_patient(patient_id)
            or []
        )
    except Exception as error:
        st.error(
            f"Failed to load examination history: {error}"
        )
        return

    latest = get_latest_patient_record_exam(exams)

    # ============================================================
    # SEVERITY ALERT
    # ============================================================

    if latest:
        alert_level, alert_msg = get_severity_alert(
            exams,
            latest,
        )
    else:
        alert_level, alert_msg = None, None

    # ============================================================
    # LATEST EXAMINATION TYPE AND DATE
    # ============================================================

    if latest:
        latest_exam_type = display_exam_type(latest)

        latest_exam_date = format_date_only(
            latest.get("examination_date")
            or latest.get("created_at")
        )

        latest_exam_label = (
            f"{latest_exam_type} · {latest_exam_date}"
        )

    else:
        latest_exam_label = "No finalized examination"

    # ============================================================
    # CURB-65 ASSESSMENT
    # ============================================================

    curb_score = (
        latest.get("curb65_score")
        if latest
        else None
    )

    try:
        curb_score = (
            int(curb_score)
            if curb_score is not None
            else None
        )
    except (TypeError, ValueError):
        curb_score = None

    if curb_score is not None:

        if curb_score <= 1:
            curb_tone = "green"
            curb_label = "Low Risk"

        elif curb_score == 2:
            curb_tone = "amber"
            curb_label = "Moderate Risk"

        else:
            curb_tone = "red"
            curb_label = "High Risk"

        curb_pill = pill(
            f"Score: {curb_score} - {curb_label}",
            curb_tone,
        )

    else:
        curb_pill = pill(
            "Not Assessed",
            "slate",
        )

    # ============================================================
    # PHYSICIAN MANUAL SEVERITY
    # ============================================================

    phys_sev = (
        latest.get("severity_status")
        if latest
        else None
    )

    phys_sev = str(phys_sev or "").strip()

    if (
        phys_sev
        and phys_sev.lower() != "not assessed"
    ):

        normalized_severity = phys_sev.lower()

        if "low" in normalized_severity:
            phys_tone = "green"

        elif "moderate" in normalized_severity:
            phys_tone = "amber"

        elif "high" in normalized_severity:
            phys_tone = "red"

        else:
            phys_tone = "slate"

        phys_pill = pill(
            phys_sev,
            phys_tone,
        )

    else:
        phys_pill = pill(
            "Not Assessed",
            "slate",
        )

    # ============================================================
    # SEVERITY ALERT
    # ============================================================

    alert_html = ""

    if alert_level == "warning":
        alert_html = (
            "<div style='"
            "margin-top:1rem;"
            "padding:0.75rem;"
            "background:#FEE2E2;"
            "color:#B91C1C;"
            "border-radius:8px;"
            "font-size:0.8rem;"
            "font-weight:500;"
            "'>"
            f"{alert_msg or ''}"
            "</div>"
        )

    elif alert_level == "info":
        alert_html = (
            "<div style='"
            "margin-top:1rem;"
            "padding:0.75rem;"
            "background:#E8F4F6;"
            "color:#0F7C88;"
            "border-radius:8px;"
            "font-size:0.8rem;"
            "font-weight:500;"
            "'>"
            f"{alert_msg or ''}"
            "</div>"
        )

    # ============================================================
    # RENDER LATEST SEVERITY ASSESSMENT
    # ============================================================

    st.markdown(
        "<div class='pr-hero-card'>"

        "<p class='pr-hero-eyebrow'>"
        "Latest Severity Assessment"
        "</p>"

        "<p class='pr-hero-name' style='"
        "font-size:0.9rem;"
        "color:#5A6F7F;"
        "margin-bottom:0.75rem;"
        "font-weight:500;"
        "'>"
        f"Based on examination: {latest_exam_label}"
        "</p>"

        "<div style='"
        "display:flex;"
        "gap:2rem;"
        "margin-top:0.5rem;"
        "'>"

        # CURB-65
        "<div style='flex:1;'>"
        "<p style='"
        "color:#0F7C88;"
        "font-weight:700;"
        "font-size:0.75rem;"
        "text-transform:uppercase;"
        "margin-bottom:0.25rem;"
        "'>"
        "CURB-65 (Calculated)"
        "</p>"
        f"<div>{curb_pill}</div>"
        "</div>"

        # Physician Manual Severity
        "<div style='flex:1;'>"
        "<p style='"
        "color:#B45309;"
        "font-weight:700;"
        "font-size:0.75rem;"
        "text-transform:uppercase;"
        "margin-bottom:0.25rem;"
        "'>"
        "Physician Manual (Clinical)"
        "</p>"
        f"<div>{phys_pill}</div>"
        "</div>"

        "</div>"

        f"{alert_html}"

        "</div>",
        unsafe_allow_html=True,
    )
    render_consultation_history(patient)








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
        eligible = finalized_examination_records(exams)
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
    if exam.get("disposition") != "Admission":
        return
    status = exam.get("status")
    if status == "Discharged":
        discharge_date = format_date_only(exam.get("time_of_discharge"))
        st.markdown(
            f"<div style='padding: 1rem 1.25rem; background: #EAF6F1; border-left: 4px solid #2E8B6A; border-radius: 8px; margin-bottom: 1.5rem;'>"
            f"<p style='margin: 0 0 0.25rem 0; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #2E8B6A;'>Admission Episode — Discharged</p>"
            f"<p style='margin: 0; font-size: 0.9rem; color: #12283A; font-weight: 600;'>Discharged on {discharge_date}. This admission episode is closed.</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
    elif status == "Admitted":
        admitted_at = format_date_only(exam.get("time_in") or exam.get("examination_date"))
        st.markdown(
            f"<div style='padding: 1rem 1.25rem; background: #FEF3C7; border-left: 4px solid #B45309; border-radius: 8px; margin-bottom: 1.5rem;'>"
            f"<p style='margin: 0 0 0.25rem 0; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #B45309;'>Admission Episode — Currently Admitted</p>"
            f"<p style='margin: 0; font-size: 0.9rem; color: #12283A; font-weight: 600;'>Admitted on {admitted_at}. Patient is currently under inpatient care.</p>"
            f"</div>",
            unsafe_allow_html=True,
        )


def render_inpatient_timeline(exam):
    if exam.get("disposition") != "Admission":
        return
    exam_id = exam.get("examination_id")
    st.divider()
    section_title("Inpatient Monitoring")
    try:
        res = admin_supabase.table("examinations").select("*").eq("parent_examination_id", exam_id).order("examination_date", desc=True).execute()
        rounds = res.data or []
    except Exception as e:
        st.error(f"Failed to load inpatient rounds: {e}")
        rounds = []

    v_map = {}
    if rounds:
        round_ids = [r["examination_id"] for r in rounds]
        try:
            v_res = admin_supabase.table("examination_vitals").select("*").in_("examination_id", round_ids).order("recorded_at", desc=True).execute()
            for v in v_res.data or []:
                v_map.setdefault(v.get("examination_id"), v)
        except Exception:
            pass

    if not rounds:
        st.info("No daily rounds have been logged for this admission yet.")
    else:
        total_rounds = len(rounds)
        st.caption(f"{total_rounds} inpatient round(s) recorded for this admission.")
        widths = [1.5, 0.8, 0.8, 0.8, 0.9, 3.0]
        with st.container(key=f"pr_inpatient_header_{exam_id}"):
            h1, h2, h3, h4, h5, h6 = st.columns(widths)
            h1.markdown("<span class='ip-th'>Date & Time</span>", unsafe_allow_html=True)
            h2.markdown("<span class='ip-th'>Day</span>", unsafe_allow_html=True)
            h3.markdown("<span class='ip-th'>SpO₂</span>", unsafe_allow_html=True)
            h4.markdown("<span class='ip-th'>Temp</span>", unsafe_allow_html=True)
            h5.markdown("<span class='ip-th'>Resp. Rate</span>", unsafe_allow_html=True)
            h6.markdown("<span class='ip-th'>Clinical Notes</span>", unsafe_allow_html=True)
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


# ============================================================
# LABORATORY REQUESTS & RESULTS
# ============================================================


def _laboratory_document_kind(document):
    """Determine whether the uploaded result supports an inline preview."""

    filename = str(document.get("original_filename") or "").lower()
    content_type = str(document.get("content_type") or "").lower()

    if content_type.startswith("image/") or filename.endswith(
        (".png", ".jpg", ".jpeg", ".webp")
    ):
        return "image"

    if content_type == "application/pdf" or filename.endswith(".pdf"):
        return "pdf"

    return "other"


def _get_examination_lab_requests(exam, actor_id):
    """Load orders for an examination and attach their follow-up documents."""

    examination_id = exam.get("examination_id")

    if not examination_id:
        return []

    requests = get_requests_for_examination(examination_id, actor_id) or []

    # A follow-up identifier may be present on the examination itself or
    # on individual laboratory orders, depending on the backend response.
    examination_follow_up_id = exam.get("follow_up_id")
    follow_up_cache = {}

    for request in requests:
        follow_up_id = (
            request.get("follow_up_id")
            or examination_follow_up_id
        )

        request["_resolved_follow_up_id"] = follow_up_id
        request["_result_documents"] = request.get("documents") or []

        if not follow_up_id:
            continue

        if follow_up_id not in follow_up_cache:
            follow_up_cache[follow_up_id] = (
                get_requests_for_follow_up(follow_up_id, actor_id) or []
            )

        request_id = str(request.get("lab_request_id"))

        matching_request = next(
            (
                item
                for item in follow_up_cache[follow_up_id]
                if str(item.get("lab_request_id")) == request_id
            ),
            None,
        )

        if matching_request is not None:
            request["_result_documents"] = (
                matching_request.get("documents") or []
            )

    return requests


@st.dialog("Laboratory Result", width="large")
def show_examination_lab_result_dialog(request, actor_id):
    """Preview an individual laboratory order's uploaded documents."""

    test_type = request.get("test_type") or "Laboratory Test"
    documents = request.get("_result_documents") or []
    request_id = str(request.get("lab_request_id") or "unknown")

    st.subheader(test_type)
    st.caption("Laboratory results and supporting documents · Read only")

    if not documents:
        st.info("No laboratory result documents have been uploaded yet.")
        return

    document_options = {
        str(document.get("document_id")): document
        for document in documents
        if document.get("document_id")
    }

    if not document_options:
        st.info("No accessible laboratory documents were found.")
        return

    def _document_label(document_id):
        document = document_options[document_id]
        filename = document.get("original_filename") or "Laboratory Result"
        uploaded_at = str(document.get("uploaded_at") or "")[:16]

        if uploaded_at:
            return f"{filename} — {uploaded_at.replace('T', ' ')}"

        return filename

    selected_document_id = st.selectbox(
        "Choose a document",
        options=list(document_options),
        format_func=_document_label,
        key=f"pr_lab_document_{request_id}",
    )

    selected_document = document_options[selected_document_id]
    filename = selected_document.get("original_filename") or "Laboratory Result"

    try:
        signed_url = signed_lab_document_url(
            selected_document_id,
            actor_id,
        )
    except Exception as error:
        st.error(f"Unable to access laboratory document: {error}")
        return

    if not signed_url:
        st.warning("The selected document is currently unavailable.")
        return

    document_kind = _laboratory_document_kind(selected_document)

    st.markdown(f"**{filename}**")

    if document_kind == "image":
        st.image(
            signed_url,
            caption=filename,
            use_container_width=True,
        )

    elif document_kind == "pdf":
        from html import escape

        safe_url = escape(signed_url, quote=True)

        components.html(
            f'<iframe src="{safe_url}" width="100%" height="540" '
            'style="border:1px solid #e2e8f0; border-radius:10px;" '
            'title="Laboratory PDF Result"></iframe>',
            height=560,
            scrolling=False,
        )

    else:
        st.info("Preview is unavailable for this document type.")

    st.link_button(
        "Open Original File",
        signed_url,
        icon=":material/open_in_new:",
    )


def render_examination_lab_results(exam):
    """Display laboratory orders associated with the selected examination."""

    st.divider()

    section_title(
        "Laboratory Requests & Results",
        "Tests ordered for this examination and their uploaded results.",
    )

    actor_id = current_user().get("user_id")

    if not actor_id:
        st.warning("Unable to identify the current user for laboratory access.")
        return

    try:
        requests = _get_examination_lab_requests(exam, actor_id)
    except Exception as error:
        st.error(f"Unable to load laboratory requests: {error}")
        return

    if not requests:
        st.caption("No laboratory requests are associated with this examination.")
        return

    for request in requests:
        request_id = str(request.get("lab_request_id") or "unknown")
        test_type = request.get("test_type") or "Laboratory Test"
        documents = request.get("_result_documents") or []
        status = request.get("status") or "Pending"

        with st.container(border=True):
            info_col, action_col = st.columns(
                [3, 1],
                vertical_alignment="center",
            )

            with info_col:
                st.markdown(f"**{test_type}**")

                if documents:
                    st.caption(
                        f"Result Uploaded · {len(documents)} document(s)"
                    )
                else:
                    st.caption(f"{status} · No uploaded result")

            with action_col:
                if documents:
                    if st.button(
                        "View Result",
                        icon=":material/visibility:",
                        key=f"pr_lab_view_{request_id}",
                        width="stretch",
                    ):
                        show_examination_lab_result_dialog(
                            request,
                            actor_id,
                        )
                else:
                    st.button(
                        "Awaiting Result",
                        key=f"pr_lab_pending_{request_id}",
                        disabled=True,
                        width="stretch",
                    )


def render_examination_report(patient, exam):
    # The print report is identical in Physician and Medical Records portals.
    back_col, print_col, _ = st.columns([2, 2, 6], vertical_alignment="center")
    with back_col:
        if st.button(
            "Back to Records",
            key="pr_back_to_category",
            icon=":material/arrow_back:",
            width="stretch",
        ):
            back_to_category()
    with print_col:
        if st.button(
            "Print Result",
            key="pr_print_result",
            icon=":material/print:",
            type="primary",
            width="stretch",
        ):
            examination_id = exam.get("examination_id")
            try:
                request = get_xray_request_by_examination(examination_id)
                ai_result = None
                if request:
                    images = get_xray_images_by_request(request["request_id"]) or []
                    if images:
                        ai_result = get_xray_ai_result(images[0].get("image_id"))
                trigger_print_report(patient, exam, request or {}, ai_result)
            except Exception as error:
                st.error(f"Could not prepare the X-ray report: {error}")
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
    render_inpatient_timeline(exam)
    render_examination_lab_results(exam)


# ============================================================
# PAGE
# ============================================================

def show():
    load_css("patient_records.css", "inpatient_dashboard.css")
    from pathlib import Path as _LSPath
    _css = _LSPath(__file__).resolve().parents[3] / "shared/theme/css_content/consultation_history_v3.css"
    st.markdown("<style>" + _css.read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)
    show_flash_message()
    if current_role_id() not in (DOCTOR_ROLES + ADMIN_ROLES):
        st.error("You don't have access to Patient Records.")
        return
    patient = st.session_state.get(KEY_PATIENT)
    if not patient:
        render_patient_list(load_patient_rows())
        return
    selection = st.session_state.pop(KEY_EXAM,None)
    external = st.session_state.pop(KEY_EXTERNAL,None)
    st.session_state.pop(KEY_EXTERNAL_SHOWN,None)
    pass
    st.session_state.pop(KEY_CATEGORY,None)
    with st.container(key='sa_page' if False else 'ls_physician_page'):
        render_patient_overview(patient)
    if selection:
        show_examination_archive_dialog(patient,selection)
    elif external:
        show_external_record_dialog(external)
    



# LUNGSIGHT_HISTORY_V2

from backend.backend_utils.consultation_history_utils import group_consultations


def _ls_history_data(patient):
    pid = patient['patient_id']
    exams = get_examinations_by_patient(pid) or []
    links = []
    offset = 0
    while True:
        batch = (admin_supabase.table('follow_ups')
                 .select('source_examination_id,follow_up_examination_id')
                 .eq('patient_id', pid).order('follow_up_id').range(offset, offset+499).execute().data or [])
        links.extend(batch)
        if len(batch) < 500: break
        offset += 500
    return group_consultations(exams, links)


def _ls_diagnosis(exam):
    label = exam.get('confirmed_label')
    return str(label).replace('_', ' ').title() if label else str(exam.get('diagnosis') or 'Not recorded')


def _ls_row(patient, exam, root, previous=None):
    with st.container(border=True):
        a,b,c = st.columns([2.5,2,0.8], vertical_alignment='center')
        icon = 'assignment' if root and exam.get('examination_id') == root.get('examination_id') else 'event_available'
        title = _ls_escape(str(display_exam_type(exam)))
        date = _ls_escape(str(format_date_only(exam.get('examination_date') or exam.get('created_at'))))
        a.markdown(f'<div class="lsv3-row"><span class="lsv3-icon material-symbols-rounded">{icon}</span><div><strong>{title}</strong><small>{date}</small></div></div>', unsafe_allow_html=True)
        status = str(exam.get('status') or 'Not recorded')
        tone = 'done' if status.lower() in ('completed','discharged') else ''
        diagnosis = _ls_diagnosis(exam)
        b.markdown(f'<div class="lsv3-row"><div><strong>{_ls_escape(diagnosis[:120])}{"…" if len(diagnosis)>120 else ""}</strong><span class="lsv3-status {tone}">{_ls_escape(status)}</span></div></div>', unsafe_allow_html=True)
        if c.button('View', key='ls_view_'+str(exam['examination_id']), width='stretch', icon=':material/visibility:'):
            st.session_state[KEY_EXAM] = {'exam':exam,'root':root,'previous':previous}
            st.rerun()




def render_consultation_history(patient):
    with st.container(key='ls_history'):
        try:
            roots, groups, orphaned = _ls_history_data(patient)
        except Exception as error:
            st.error(f'Unable to load consultation relationships: {error}')
            return
        a,b,c = st.columns(3)
        a.metric('General consultations',len(roots))
        b.metric('Linked follow-ups',sum(map(len,groups.values())))
        c.metric('Needs review',len(orphaned))
        history, external = st.tabs(['Consultation History','External Records'])
        with history:
            st.markdown('<div class="lsv3-kicker">Longitudinal clinical history</div>', unsafe_allow_html=True)
            st.caption('Expand a consultation to review its complete examination history.')
            if not roots and not orphaned: st.info('No finalized examinations.')
            for i, root in enumerate(roots):
                children = groups[str(root['examination_id'])]
                date = format_date_only(root.get('examination_date') or root.get('created_at'))
                with st.expander(f'General Consultation {len(roots)-i:03d}  |  {date}  |  {len(children)} follow-up(s)'):
                    st.markdown('<div class="lsv3-kicker">Initial consultation</div>', unsafe_allow_html=True)
                    _ls_row(patient,root,root)
                    st.markdown('<div class="lsv3-kicker">Follow-up timeline</div>', unsafe_allow_html=True)
                    previous = root
                    for child in children:
                        _ls_row(patient,child,root,previous)
                        previous = child
                    if not children: st.info('No finalized follow-ups.')
            if orphaned:
                with st.expander(f'Relationships needing review ({len(orphaned)})'):
                    st.warning('Missing or conflicting consultation links. No relationship has been guessed.')
                    for child in orphaned: _ls_row(patient,child,None)
        with external:
            pass
            records = get_medical_records_by_patient(patient['patient_id']) or []
            if not records: st.info('No external medical records.')
            for record in records: render_record_list_card(record)


def _ls_field(label, value):
    value = 'Not recorded' if value is None or value == '' else str(value)
    st.markdown(f'<div class="lsv3-field"><label>{_ls_escape(str(label))}</label><div>{_ls_escape(value)}</div></div>', unsafe_allow_html=True)




@st.dialog('Examination Details', width='large')
def show_examination_archive_dialog(patient, selection):
    exam = selection.get('exam',selection)
    root, previous = selection.get('root'), selection.get('previous')
    with st.container(key='ls_exam'):
        _ls_v3_hero(str(display_exam_type(exam)), f"{patient_name(patient)} · {patient_code(patient)} · {format_date_only(exam.get('examination_date'))}", 'Rx')
        a,b = st.columns([3,1])
        a.caption(str(exam.get('status') or 'Not recorded'))
        if b.button('Close',key='ls_close'): st.rerun()
        _ls_field('Physician-confirmed classification / recorded diagnosis',_ls_diagnosis(exam))
        if root and root.get('examination_id') != exam.get('examination_id'):
            st.caption('Originating consultation: '+format_date_only(root.get('examination_date')))
        clinical,vitals,xray,labs,care = st.tabs(['Clinical','Vitals & Severity','X-Ray & AI','Laboratory','Care Plan'])
        with clinical:
            if previous: _ls_field('Previous examination diagnosis',_ls_diagnosis(previous))
            for label,key in [('Chief complaint','chief_complaint'),('History of present illness','history_of_present_illness'),('Physical examination','physical_examination'),('Clinical diagnosis','diagnosis')]:
                _ls_field(label,exam.get(key))
        with vitals:
            for label,keys in [('Blood pressure',('blood_pressure','bp')),('Temperature',('temperature','body_temperature')),('Heart rate',('heart_rate','pulse_rate')),('Respiratory rate',('respiratory_rate',)),('Oxygen saturation',('spo2','oxygen_saturation')),('Weight',('weight',))]:
                _ls_field(label,next((exam[k] for k in keys if exam.get(k) is not None),None))
            render_severity_card(exam)
        with xray:
            request,image,ai = render_xray_analysis(exam)
            if ai:
                render_risk_card(ai.get('ai_findings'),ai.get('ai_confidence'),ai.get('pneumonia_type'))
                render_ai_summary(ai,ai.get('ai_findings'),ai.get('pneumonia_type'),ai.get('ai_confidence'))
            if st.button('Print Result',key='ls_print',icon=':material/print:'):
                trigger_print_report(patient,exam,request or {},ai)
        with labs:
            actor = current_user().get('user_id')
            requests = _get_examination_lab_requests(exam,actor) if actor else []
            if not requests: st.info('No accessible laboratory requests.')
            for item in requests:
                with st.container(border=True):
                    st.write(item.get('test_type') or 'Laboratory request')
                    st.caption(str(item.get('status') or 'Not recorded'))
                    for doc in item.get('_result_documents') or []:
                        if doc.get('document_id'):
                            url = signed_lab_document_url(doc['document_id'],actor)
                            if url: st.link_button(doc.get('original_filename') or 'Open result',url)
        with care:
            for label,key in [('Plans / Orders','plans_orders'),('Disposition','disposition'),('Disposition notes','disposition_notes'),('Follow-up date','follow_up_date'),('Follow-up notes','follow_up_notes')]:
                _ls_field(label,exam.get(key))
            render_admission_banner(exam)
            render_inpatient_timeline(exam)

# LUNGSIGHT_HISTORY_V3
from html import escape as _ls_escape
def _ls_v3_hero(title, subtitle, initials):
    st.markdown(f'<div class="lsv3-hero"><div class="lsv3-avatar">{_ls_escape(initials)}</div><div><h3>{_ls_escape(title)}</h3><small>{_ls_escape(subtitle)}</small></div></div>', unsafe_allow_html=True)
