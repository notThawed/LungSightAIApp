# streamlit_app/pages/physician/review_patient.py

"""
Physician — Review Patient.

Level 1: X-Ray Ready list
Level 2: Review X-Ray Report (per-examination)

Session keys:
    review_examination -> dict
    review_patient     -> dict
"""

import streamlit as st

from datetime import datetime, date, time
from zoneinfo import ZoneInfo

from backend.supabase_client import admin_supabase

from backend.fetches import (
    get_xray_ready_examinations,
    get_xray_request_by_examination,
    get_xray_images_by_request,
    get_xray_image_url,
    get_xray_ai_result,
    get_examinations_by_patient,
    get_medical_records_by_patient,
)

from backend.crud import (
    save_xray_review,
    update_examination,
)

from backend.backend_utils.followup_utils import (
    create_follow_up,
    reschedule_follow_up,
    cancel_follow_up,
)

from streamlit_app.components.ui import (
    page_header,
    empty_state,
    section_title,
    show_rows,
    full_name,
    format_date,
    pill,
    metric_card,
    table_header,
    table_row,
    name_cell,
    text_cell,
    pill_cell,
    remember,
    show_flash_message,
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

QUEUE_WIDTHS = [2.5, 1.2, 1.5, 1.5]
QUEUE_HEADERS = ["Patient", "Requested", "Status", "Action"]

DISPOSITION_OPTIONS = [
    "Admission",
    "Treated and Sent Home",
    "Referred",
    "Refused Admission",
    "Nowhere When Called",
]


# ============================================================
# USER HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}


def current_role_id():
    return current_user().get("role_id")


def current_hospital_id():
    return current_user().get("hospital_id")


def current_user_id():
    return current_user().get("user_id")


def patient_name(patient):
    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )


def patient_code(patient):
    return patient.get("patient_code") or patient.get("patient_id")


# ============================================================
# DATE / TIME HELPERS
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


def format_datetime(value):
    parsed = parse_datetime(value)
    if not parsed:
        return "—"
    return parsed.strftime("%B %d, %Y at %I:%M %p")


def format_date_only(value):
    parsed = parse_datetime(value)
    if not parsed:
        return format_date(value) or "—"
    return parsed.strftime("%B %d, %Y")


def examination_datetime(examination):
    return (
        examination.get("examination_date")
        or examination.get("created_at")
    )


# ============================================================
# AI HELPERS
# ============================================================

def risk_label_from_findings(ai_findings):
    if not ai_findings:
        return ("No AI Result", "slate")

    normalized = str(ai_findings).strip().lower()

    if normalized == "positive":
        return ("HIGH", "red")

    if normalized == "negative":
        return ("LOW", "green")

    return (str(ai_findings).title(), "slate")


def pneumonia_type_label(pneumonia_type, ai_findings=None):
    if pneumonia_type == "bacterial_pneumonia":
        return ("Bacterial Pneumonia", "red")
    if pneumonia_type == "viral_pneumonia":
        return ("Viral Pneumonia", "amber")

    if ai_findings:
        normalized = str(ai_findings).strip().lower()
        if normalized == "negative":
            return ("Not applicable", "slate")
        if normalized == "positive":
            return ("Type Not Classified", "amber")

    return ("—", "slate")


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


def ai_findings_narrative(ai_findings, pneumonia_type):
    if not ai_findings:
        return None

    normalized = str(ai_findings).strip().lower()

    if normalized == "positive":
        if pneumonia_type == "bacterial_pneumonia":
            return (
                "Bilateral consolidation detected. Findings "
                "consistent with <b>bacterial pneumonia</b>."
            )
        if pneumonia_type == "viral_pneumonia":
            return (
                "Bilateral opacity patterns detected. Findings "
                "consistent with <b>viral pneumonia</b>."
            )
        return (
            "Patterns consistent with <b>pneumonia</b> detected. "
            "Recommend clinical correlation."
        )

    if normalized == "negative":
        return (
            "No patterns consistent with pneumonia were detected. "
            "Continue standard clinical evaluation."
        )

    return None


# ============================================================
# FOLLOW-UP HELPERS
# ============================================================

def load_follow_up_for_examination(examination_id):
    """
    Fetch the active follow-up tied to this examination.
    Returns the dict, or None.
    """
    if not examination_id:
        return None

    try:
        response = (
            admin_supabase
            .table("follow_ups")
            .select("*")
            .eq("source_examination_id", examination_id)
            .in_("status", ["Scheduled", "Rescheduled"])
            .order("follow_up_date", desc=True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None

    except Exception as exc:
        print(f"Failed to load follow-up: {exc}")
        return None


def format_follow_up_when(follow_up):
    if not follow_up:
        return "—"

    date_val = follow_up.get("follow_up_date")
    time_val = follow_up.get("follow_up_time")

    if not date_val:
        return "—"

    try:
        parsed_date = date.fromisoformat(str(date_val)[:10])
        date_text = parsed_date.strftime("%B %d, %Y")
    except Exception:
        date_text = str(date_val)

    if time_val:
        try:
            parsed_time = time.fromisoformat(str(time_val)[:8])
            time_text = parsed_time.strftime("%I:%M %p")
        except Exception:
            time_text = str(time_val)
        return f"{date_text} · {time_text}"

    return date_text


# ============================================================
# STATE
# ============================================================

def go_to_review(examination, patient):
    st.session_state["review_examination"] = examination
    st.session_state["review_patient"] = patient
    st.rerun()


def back_to_list():
    st.session_state.pop("review_examination", None)
    st.session_state.pop("review_patient", None)
    st.rerun()


def clear_review_state():
    for key in (
        "review_examination",
        "review_patient",
        "review_history_patient",
        "review_previous_examinations",
        "review_previous_medical_records",
        "review_schedule_followup_open",
        "review_edit_followup_open",
        "review_remove_followup_open",
    ):
        st.session_state.pop(key, None)


# ============================================================
# DIALOG — PREVIOUS EXAMINATIONS
# ============================================================

@st.dialog("Examination Histories", width="large")
def show_previous_examinations(patient):

    patient_id = patient.get("patient_id")
    examinations = get_examinations_by_patient(patient_id) or []

    previous = [
        e for e in examinations
        if e.get("status") in ("Completed", "Cancelled")
    ]

    section_title(f"Previous Examinations ({len(previous)})")

    if not previous:
        empty_state("No previous examinations found.")
    else:
        for exam in sorted(
            previous,
            key=lambda item: examination_datetime(item) or "",
            reverse=True,
        ):
            status = exam.get("status") or "Unknown"
            tone = "green" if status == "Completed" else "red"

            st.markdown(
                f"### {exam.get('examination_type') or 'Examination'}"
            )
            st.markdown(
                f"**Date:** {format_datetime(examination_datetime(exam))}"
            )
            st.markdown(
                f"**Status:** {pill(status, tone)}",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"**Chief Complaint:** {exam.get('chief_complaint') or '—'}"
            )
            st.markdown(
                f"**Diagnosis:** {exam.get('diagnosis') or '—'}"
            )
            st.markdown(
                f"**Plans / Orders:** {exam.get('plans_orders') or '—'}"
            )
            st.markdown(
                f"**Disposition:** {exam.get('disposition') or '—'}"
            )
            st.divider()

    if st.button(
        "Close",
        key="review_previous_exams_close",
        width="stretch",
    ):
        st.session_state.pop("review_previous_examinations", None)
        st.rerun()


# ============================================================
# DIALOG — PREVIOUS MEDICAL RECORDS
# ============================================================

@st.dialog("Previous Medical Histories", width="large")
def show_previous_medical_records(patient):

    patient_id = patient.get("patient_id")
    records = get_medical_records_by_patient(patient_id) or []

    section_title(f"Previous Medical Records ({len(records)})")

    if not records:
        empty_state("No previous external medical records found.")
    else:
        for record in sorted(
            records,
            key=lambda item: (
                item.get("record_date")
                or item.get("created_at")
                or ""
            ),
            reverse=True,
        ):
            record_date = (
                record.get("record_date")
                or record.get("created_at")
            )

            st.markdown(
                f"### {record.get('record_type') or 'Medical Record'}"
            )
            st.markdown(
                f"**Date:** {format_datetime(record_date)}"
            )
            st.markdown(
                f"**Facility:** {record.get('facility_name') or '—'}"
            )
            st.markdown(
                f"**Diagnosis:** {record.get('diagnosis') or '—'}"
            )
            st.markdown(
                f"**Treatment:** {record.get('treatment') or '—'}"
            )
            st.markdown(
                f"**Notes:** {record.get('notes') or '—'}"
            )
            st.divider()

    if st.button(
        "Close",
        key="review_previous_medical_close",
        width="stretch",
    ):
        st.session_state.pop("review_previous_medical_records", None)
        st.rerun()


# ============================================================
# DIALOG — SCHEDULE FOLLOW-UP
# ============================================================

@st.dialog("Schedule Follow-Up", width="small")
def show_schedule_followup_dialog(patient, examination):

    patient_id = patient.get("patient_id")
    examination_id = examination.get("examination_id")
    user_id = current_user_id()

    st.markdown(
        f"Schedule a follow-up appointment for "
        f"**{patient_name(patient)}** ({patient_code(patient)})."
    )

    st.divider()

    follow_up_date = st.date_input(
        "Follow-Up Date *",
        min_value=date.today(),
        key="review_fu_date",
    )

    follow_up_time = st.time_input(
        "Follow-Up Time *",
        value=time(9, 0),
        key="review_fu_time",
    )

    follow_up_notes = st.text_area(
        "Notes",
        height=100,
        key="review_fu_notes",
        placeholder=(
            "Example: Reassess symptoms, review response "
            "to treatment, repeat X-ray if needed."
        ),
    )

    st.divider()

    cancel_col, confirm_col = st.columns(2)

    if cancel_col.button(
        "Cancel",
        key="review_fu_cancel",
        width="stretch",
    ):
        st.session_state.pop("review_schedule_followup_open", None)
        st.rerun()

    if confirm_col.button(
        "Confirm Follow-Up",
        key="review_fu_confirm",
        type="primary",
        width="stretch",
    ):
        result = create_follow_up(
            patient_id=patient_id,
            examination_id=examination_id,
            follow_up_date=follow_up_date,
            follow_up_time=follow_up_time,
            notes=follow_up_notes or None,
            created_by=user_id,
        )

        if result.get("success"):
            st.session_state.pop("review_schedule_followup_open", None)
            st.session_state["review_fu_flash"] = (
                "Follow-up scheduled successfully."
            )
            st.rerun()
        else:
            st.error(
                "Could not schedule follow-up: "
                f"{result.get('message', 'Unknown error')}"
            )


# ============================================================
# DIALOG — EDIT FOLLOW-UP
# ============================================================

@st.dialog("Edit Follow-Up", width="small")
def show_edit_followup_dialog(follow_up):

    if not follow_up:
        st.error("Follow-up not found.")
        return

    follow_up_id = follow_up.get("follow_up_id")

    # Prefill from existing
    existing_date_str = follow_up.get("follow_up_date")
    existing_time_str = follow_up.get("follow_up_time")
    existing_notes = follow_up.get("notes") or ""

    try:
        existing_date = date.fromisoformat(str(existing_date_str)[:10])
    except Exception:
        existing_date = date.today()

    if existing_date < date.today():
        existing_date = date.today()

    try:
        existing_time = time.fromisoformat(str(existing_time_str)[:8])
    except Exception:
        existing_time = time(9, 0)

    st.markdown("Update the follow-up appointment details.")

    st.divider()

    new_date = st.date_input(
        "Follow-Up Date *",
        value=existing_date,
        min_value=date.today(),
        key="review_fu_edit_date",
    )

    new_time = st.time_input(
        "Follow-Up Time *",
        value=existing_time,
        key="review_fu_edit_time",
    )

    new_notes = st.text_area(
        "Notes",
        value=existing_notes,
        height=100,
        key="review_fu_edit_notes",
    )

    st.divider()

    cancel_col, confirm_col = st.columns(2)

    if cancel_col.button(
        "Cancel",
        key="review_fu_edit_cancel",
        width="stretch",
    ):
        st.session_state.pop("review_edit_followup_open", None)
        st.rerun()

    if confirm_col.button(
        "Save Changes",
        key="review_fu_edit_confirm",
        type="primary",
        width="stretch",
    ):
        result = reschedule_follow_up(
            follow_up_id=follow_up_id,
            new_date=new_date,
            new_time=new_time,
            notes=new_notes or None,
        )

        if result.get("success"):
            st.session_state.pop("review_edit_followup_open", None)
            st.session_state["review_fu_flash"] = (
                "Follow-up updated successfully."
            )
            st.rerun()
        else:
            st.error(
                "Could not update follow-up: "
                f"{result.get('message', 'Unknown error')}"
            )


# ============================================================
# DIALOG — REMOVE FOLLOW-UP
# ============================================================

@st.dialog("Remove Follow-Up", width="small")
def show_remove_followup_dialog(follow_up):

    if not follow_up:
        st.error("Follow-up not found.")
        return

    follow_up_id = follow_up.get("follow_up_id")

    st.warning(
        "Are you sure you want to remove this scheduled "
        "follow-up appointment?"
    )

    st.markdown(
        f"**Scheduled for:** {format_follow_up_when(follow_up)}"
    )

    st.caption(
        "The record will be marked as **Cancelled** "
        "rather than deleted."
    )

    st.divider()

    cancel_col, remove_col = st.columns(2)

    if cancel_col.button(
        "Keep Follow-Up",
        key="review_fu_remove_cancel",
        width="stretch",
    ):
        st.session_state.pop("review_remove_followup_open", None)
        st.rerun()

    if remove_col.button(
        "Remove Follow-Up",
        key="review_fu_remove_confirm",
        type="primary",
        width="stretch",
    ):
        result = cancel_follow_up(follow_up_id)

        if result.get("success"):
            st.session_state.pop("review_remove_followup_open", None)
            st.session_state["review_fu_flash"] = (
                "Follow-up removed."
            )
            st.rerun()
        else:
            st.error(
                "Could not remove follow-up: "
                f"{result.get('message', 'Unknown error')}"
            )


# ============================================================
# REPORT — X-RAY SECTION
# ============================================================

def render_xray_section(examination):

    section_title("X-Ray Analysis")

    exam_id = examination.get("examination_id")
    request = get_xray_request_by_examination(exam_id)

    if not request:
        st.markdown(
            "<div class='rx-no-xray'>"
            "<span class='rx-no-xray-icon material-symbols-rounded'>"
            "radiology</span>"
            "<p class='rx-no-xray-title'>No X-Ray Requested</p>"
            "<p class='rx-no-xray-text'>"
            "No chest X-ray was requested for this examination."
            "</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return None, None, None

    images = get_xray_images_by_request(request["request_id"]) or []

    if not images:
        st.markdown(
            "<div class='rx-no-xray'>"
            "<span class='rx-no-xray-icon material-symbols-rounded'>"
            "schedule</span>"
            "<p class='rx-no-xray-title'>X-Ray Pending</p>"
            "<p class='rx-no-xray-text'>"
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

    original_col, heatmap_col = st.columns(2, gap="medium")

    with original_col:
        st.markdown(
            "<p class='rx-img-label'>Original X-Ray</p>",
            unsafe_allow_html=True,
        )
        if image_url:
            with st.container(key="rx_xray_frame"):
                st.image(image_url, width="stretch")
        else:
            st.warning("Unable to load the X-ray image.")

    with heatmap_col:
        st.markdown(
            "<p class='rx-img-label'>AI Heatmap Overlay</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='rx-heatmap-placeholder'>"
            "<span class='rx-heatmap-icon material-symbols-rounded'>"
            "radiology</span>"
            "<p class='rx-heatmap-title'>Heatmap Coming Soon</p>"
            "<p class='rx-heatmap-text'>"
            "Grad-CAM visualization will appear here."
            "</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    return request, image, ai


# ============================================================
# REPORT — CLINICAL CONTEXT
# ============================================================

def render_clinical_context(examination, request):

    section_title("Clinical Context")

    rows = [
        ("Chief Complaint", examination.get("chief_complaint") or "—"),
        (
            "History of Present Illness",
            examination.get("history_of_present_illness") or "—",
        ),
        (
            "Physical Examination",
            examination.get("physical_examination") or "—",
        ),
    ]

    if request:
        rows.append(
            ("Clinical Indication", request.get("clinical_indication") or "—")
        )

    st.markdown(
        "<div class='rx-context-card'>"
        + "".join(
            f"<div class='rx-context-row'>"
            f"<span>{label}</span><b>{value}</b>"
            f"</div>"
            for label, value in rows
        )
        + "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# REPORT — PATIENT HISTORY BUTTONS
# ============================================================

def render_patient_history_buttons(patient, key_prefix):

    section_title("Patient History")

    st.caption(
        "Open each history separately to review the patient's "
        "longitudinal record."
    )

    col1, col2 = st.columns(2)

    if col1.button(
        "View Examination Histories",
        key=f"{key_prefix}_exam_history",
        icon=":material/history:",
        width="stretch",
    ):
        st.session_state["review_previous_examinations"] = patient
        st.rerun()

    if col2.button(
        "View Medical Histories",
        key=f"{key_prefix}_medical_history",
        icon=":material/medical_information:",
        width="stretch",
    ):
        st.session_state["review_previous_medical_records"] = patient
        st.rerun()


# ============================================================
# REPORT — AI RESULT CARD
# ============================================================

def render_ai_result_card(ai):

    ai_findings = (ai or {}).get("ai_findings")
    pneumonia_type = (ai or {}).get("pneumonia_type")
    ai_conf = (ai or {}).get("ai_confidence")
    class_conf = (ai or {}).get("classification_confidence")

    risk_label, risk_tone = risk_label_from_findings(ai_findings)
    type_label, type_tone = pneumonia_type_label(
        pneumonia_type, ai_findings
    )

    conf_pct = confidence_percent(ai_conf)
    class_conf_pct = confidence_percent(class_conf)

    narrative = ai_findings_narrative(ai_findings, pneumonia_type)

    # Confidence bar
    if conf_pct is not None:
        conf_block = (
            "<div class='rx-ai-row rx-ai-row-block'>"
            "<div class='rx-ai-label'>"
            "<span>AI Confidence</span>"
            f"<b>{conf_pct:.1f}%</b>"
            "</div>"
            "<div class='rx-conf-bar'>"
            f"<div class='rx-conf-fill' style='width:{conf_pct}%'></div>"
            "</div>"
            "</div>"
        )
    else:
        conf_block = (
            "<div class='rx-ai-row'>"
            "<span>AI Confidence</span><b>—</b>"
            "</div>"
        )

    # Classification confidence
    if class_conf_pct is not None:
        class_conf_block = (
            "<div class='rx-ai-row'>"
            "<span>Classification Conf.</span>"
            f"<b>{class_conf_pct:.1f}%</b>"
            "</div>"
        )
    else:
        class_conf_block = ""

    # Findings narrative
    if narrative:
        findings_block = (
            "<div class='rx-ai-findings'>"
            "<p class='rx-ai-findings-label'>AI Findings</p>"
            f"<p class='rx-ai-findings-text'>{narrative}</p>"
            "</div>"
        )
    else:
        findings_block = (
            "<div class='rx-ai-findings rx-ai-findings-empty'>"
            "<p class='rx-ai-findings-text'>"
            "No AI result available for this image."
            "</p>"
            "</div>"
        )

    st.markdown(
        "<div class='rx-panel-title-row'>"
        "<p class='rx-panel-title'>AI Analysis Result</p>"
        "</div>"
        "<div class='rx-ai-card'>"
        "<div class='rx-ai-row'>"
        "<span>Risk Level</span>"
        f"<div>{pill(risk_label, risk_tone)}</div>"
        "</div>"
        "<div class='rx-ai-row'>"
        "<span>Pneumonia Type</span>"
        f"<div>{pill(type_label, type_tone)}</div>"
        "</div>"
        f"{conf_block}"
        f"{class_conf_block}"
        f"{findings_block}"
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# REPORT — PHYSICIAN FORM
# ============================================================

def render_physician_form(examination):

    exam_id = examination.get("examination_id")

    section_title("Physician X-Ray Interpretation")

    findings = st.text_area(
        "X-Ray Findings *",
        value="",
        height=110,
        key=f"review_{exam_id}_findings",
        help="Describe relevant findings on the chest X-ray.",
    )

    impression = st.text_area(
        "Impression",
        value="",
        height=100,
        key=f"review_{exam_id}_impression",
        help="Provide your clinical interpretation.",
    )

    st.markdown(
        "<p class='rx-form-divider'></p>",
        unsafe_allow_html=True,
    )

    section_title("Final Assessment")

    diagnosis = st.text_area(
        "Diagnosis / Assessment *",
        value=examination.get("diagnosis") or "",
        height=100,
        key=f"review_{exam_id}_diagnosis",
    )

    plans = st.text_area(
        "Plans / Orders",
        value=examination.get("plans_orders") or "",
        height=100,
        key=f"review_{exam_id}_plans",
    )

    st.markdown(
        "<p class='rx-form-divider'></p>",
        unsafe_allow_html=True,
    )

    section_title("Disposition")

    current_disposition = examination.get("disposition")
    disposition_index = (
        DISPOSITION_OPTIONS.index(current_disposition)
        if current_disposition in DISPOSITION_OPTIONS
        else 0
    )

    disposition = st.selectbox(
        "Disposition",
        DISPOSITION_OPTIONS,
        index=disposition_index,
        key=f"review_{exam_id}_disposition",
    )

    disposition_notes = st.text_area(
        "Disposition Notes",
        value=examination.get("disposition_notes") or "",
        height=80,
        key=f"review_{exam_id}_disposition_notes",
    )

    return {
        "findings": findings,
        "impression": impression,
        "diagnosis": diagnosis,
        "plans": plans,
        "disposition": disposition,
        "disposition_notes": disposition_notes,
    }


# ============================================================
# REPORT — FOLLOW-UP CARD
# ============================================================

def render_followup_card(examination):

    exam_id = examination.get("examination_id")

    section_title("Follow-Up")

    follow_up = load_follow_up_for_examination(exam_id)

    with st.container(key=f"review_fu_card_{exam_id}"):

        if follow_up:

            when = format_follow_up_when(follow_up)
            notes = follow_up.get("notes") or ""

            notes_block = (
                f"<p class='rx-fu-notes'>{notes}</p>"
                if notes
                else ""
            )

            st.markdown(
                "<div class='rx-fu-card rx-fu-card--scheduled'>"
                "<div class='rx-fu-head'>"
                "<span class='material-symbols-rounded rx-fu-icon'>"
                "event_available</span>"
                "<p class='rx-fu-title'>Scheduled</p>"
                "</div>"
                f"<p class='rx-fu-when'>{when}</p>"
                f"{notes_block}"
                "</div>",
                unsafe_allow_html=True,
            )

            edit_col, remove_col = st.columns(2)

            if edit_col.button(
                "Edit",
                key=f"review_fu_edit_{exam_id}",
                icon=":material/edit:",
                width="stretch",
            ):
                st.session_state["review_edit_followup_open"] = follow_up
                st.rerun()

            if remove_col.button(
                "Remove",
                key=f"review_fu_remove_{exam_id}",
                icon=":material/delete:",
                width="stretch",
            ):
                st.session_state["review_remove_followup_open"] = follow_up
                st.rerun()

        else:

            st.markdown(
                "<div class='rx-fu-card rx-fu-card--empty'>"
                "<div class='rx-fu-head'>"
                "<span class='material-symbols-rounded rx-fu-icon'>"
                "event_busy</span>"
                "<p class='rx-fu-title'>No follow-up scheduled</p>"
                "</div>"
                "<p class='rx-fu-text'>"
                "Schedule a follow-up appointment if continued "
                "monitoring is required."
                "</p>"
                "</div>",
                unsafe_allow_html=True,
            )

            if st.button(
                "Schedule Follow-Up",
                key=f"review_fu_open_{exam_id}",
                icon=":material/event_available:",
                width="stretch",
            ):
                st.session_state["review_schedule_followup_open"] = True
                st.rerun()


# ============================================================
# REPORT — ACTION BUTTONS
# ============================================================

def render_report_actions(examination, patient, form_values, request):

    exam_id = examination.get("examination_id")
    user_id = current_user_id()

    st.divider()

    cancel_col, save_col = st.columns(2)

    cancel_clicked = cancel_col.button(
        "Cancel",
        key=f"review_{exam_id}_cancel",
        width="stretch",
    )

    save_clicked = save_col.button(
        "Save Final Diagnosis",
        key=f"review_{exam_id}_save",
        icon=":material/save:",
        type="primary",
        width="stretch",
    )

    if cancel_clicked:
        clear_review_state()
        st.rerun()

    if not save_clicked:
        return

    # Validation
    if not form_values["findings"].strip():
        st.error("X-Ray Findings is required.")
        return

    if not form_values["diagnosis"].strip():
        st.error("Diagnosis / Assessment is required.")
        return

    if not request:
        st.error("X-Ray request not found.")
        return

    try:
        # Save X-ray review
        save_xray_review(
            request_id=request["request_id"],
            reviewed_by=user_id,
            findings=form_values["findings"].strip() or None,
            impression=form_values["impression"].strip() or None,
        )

        # Complete examination
        update_examination(
            examination_id=exam_id,
            status="Completed",
            reviewed_by=user_id,
            diagnosis=form_values["diagnosis"].strip() or None,
            plans_orders=form_values["plans"].strip() or None,
            disposition=form_values["disposition"],
            disposition_notes=(
                form_values["disposition_notes"].strip() or None
            ),
        )

        clear_review_state()
        remember("X-Ray reviewed successfully. Examination completed.")
        st.rerun()

    except Exception as error:
        st.error(f"Failed to save review: {error}")


# ============================================================
# REPORT PAGE
# ============================================================

def render_review_report_page(patient, examination):

    # Back button
    if st.button(
        "Back",
        key="review_back_to_list",
        icon=":material/arrow_back:",
    ):
        back_to_list()

    exam_date = examination_datetime(examination)

    st.markdown(
        "<div class='rx-report-header'>"
        "<p class='rx-report-title'>Review X-Ray</p>"
        f"<p class='rx-report-sub'>Reviewing: {patient_name(patient)}"
        f" · {patient_code(patient)}</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Fetch shared data
    exam_id = examination.get("examination_id")
    request = get_xray_request_by_examination(exam_id)

    ai = None
    if request:
        try:
            imgs = get_xray_images_by_request(request["request_id"]) or []
            if imgs:
                ai = get_xray_ai_result(imgs[0].get("image_id"))
        except Exception:
            pass

    # Two-column layout
    left_col, right_col = st.columns([1.4, 1], gap="large")

    # --------------------------------------------------------
    # LEFT COLUMN
    # --------------------------------------------------------
    with left_col:

        render_xray_section(examination)

        render_clinical_context(examination, request)

        render_patient_history_buttons(
            patient,
            key_prefix=f"review_{exam_id}",
        )

    # --------------------------------------------------------
    # RIGHT COLUMN
    # --------------------------------------------------------
    with right_col:

        render_ai_result_card(ai)

        form_values = render_physician_form(examination)

        render_followup_card(examination)

        render_report_actions(
            examination,
            patient,
            form_values,
            request,
        )


# ============================================================
# LIST PAGE
# ============================================================

def render_review_table(examinations, key_prefix="review"):

    if not examinations:
        empty_state("No patients are currently waiting for X-Ray review.")
        return

    with st.container(key="physician_review_table"):

        table_header(QUEUE_HEADERS, QUEUE_WIDTHS, key_prefix)

        for exam in examinations:

            patient = exam.get("patients") or {}
            patient_id = patient.get("patient_id")
            examination_id = exam.get("examination_id")

            request_time = (
                exam.get("updated_at")
                or exam.get("created_at")
            )

            with table_row(
                f"review_row_{examination_id}",
                QUEUE_WIDTHS,
            ) as cols:

                name_cell(
                    cols[0],
                    patient_name(patient),
                    sub=patient_code(patient),
                )

                text_cell(
                    cols[1],
                    format_datetime(request_time),
                )

                pill_cell(
                    cols[2],
                    "X-Ray Ready",
                    "green",
                )

                if cols[3].button(
                    "Review",
                    key=f"{key_prefix}_review_{examination_id}",
                    icon=":material/radiology:",
                    type="primary",
                    width="stretch",
                ):
                    go_to_review(exam, patient)


def render_metrics(examinations):

    total = len(examinations)

    patients = len({
        (e.get("patients") or {}).get("patient_id")
        for e in examinations
    })

    m1, m2 = st.columns(2)

    with m1:
        metric_card(
            "X-Ray ready",
            total,
            "medical_information",
            tone="blue",
        )

    with m2:
        metric_card(
            "Patients to review",
            patients,
            "pending",
            tone="amber",
        )


def render_review_list_page():

    role_id = current_role_id()
    hospital_id = current_hospital_id()

    if role_id == ROLE_SUPERADMIN:
        filter_hospital = None
    elif role_id in DOCTOR_ROLES or role_id == ROLE_HOSPITAL_ADMIN:
        filter_hospital = hospital_id
    else:
        st.error("You don't have access to Review Patient.")
        return

    with st.container(key="physician_review_patient_page"):

        page_header(
            "Review Patient",
            "Review completed chest X-Rays and finalize the patient's examination.",
        )

        if st.button(
            "Refresh",
            icon=":material/refresh:",
            key="review_patient_refresh",
            width="stretch",
        ):
            st.rerun()

        try:
            xray_ready = get_xray_ready_examinations(
                hospital_id=filter_hospital
            )
        except Exception as error:
            st.error(f"Failed to load X-Ray ready examinations: {error}")
            xray_ready = []

        render_metrics(xray_ready)

        st.divider()

        section_title("X-Ray Ready for Review")

        st.caption(
            "Patients appear here after their requested chest X-Ray "
            "has been uploaded and marked ready."
        )

        render_review_table(xray_ready, key_prefix="review")


# ============================================================
# PAGE
# ============================================================

def show():

    load_css("review_patient.css")
    show_flash_message()

    # Follow-up flash from previous dialog action
    fu_flash = st.session_state.pop("review_fu_flash", None)
    if fu_flash:
        st.toast(fu_flash)

    role_id = current_role_id()

    if role_id not in (DOCTOR_ROLES + ADMIN_ROLES):
        st.error("You don't have access to Review Patient.")
        return

    # ------------------------------------------------
    # Router: report page vs list page
    # ------------------------------------------------
    selected_exam = st.session_state.get("review_examination")
    selected_patient = st.session_state.get("review_patient")

    with st.container(key="physician_review_patient_root"):

        if selected_exam and selected_patient:
            render_review_report_page(selected_patient, selected_exam)
        else:
            render_review_list_page()

    # ------------------------------------------------
    # Dialog dispatcher (independent of page level)
    # ------------------------------------------------

    if st.session_state.get("review_previous_examinations"):
        show_previous_examinations(
            st.session_state["review_previous_examinations"]
        )

    elif st.session_state.get("review_previous_medical_records"):
        show_previous_medical_records(
            st.session_state["review_previous_medical_records"]
        )

    elif st.session_state.get("review_schedule_followup_open"):
        if selected_exam and selected_patient:
            show_schedule_followup_dialog(
                selected_patient, selected_exam
            )

    elif st.session_state.get("review_edit_followup_open"):
        show_edit_followup_dialog(
            st.session_state["review_edit_followup_open"]
        )

    elif st.session_state.get("review_remove_followup_open"):
        show_remove_followup_dialog(
            st.session_state["review_remove_followup_open"]
        )