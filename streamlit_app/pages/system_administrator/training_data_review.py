# streamlit_app/pages/system_administrator/training_data_review.py

"""
Training Data Review — Superadmin queue for ML ground-truth labels.

Level 0: Queue      — list of candidates with status filters
Level 1: Detail     — one candidate, X-ray + heatmap, approve/reject

Session keys:
    tdr_selected_candidate -> dict
"""

import streamlit as st

from datetime import datetime, date
from zoneinfo import ZoneInfo

from backend.fetches import (
    get_training_candidates_detailed,
    get_training_candidate_stats,
    get_xray_ai_heatmap,
    get_xray_image_url,
    get_all_hospitals,
)

from backend.crud import review_training_candidate

from streamlit_app.components.ui import (
    page_header,
    empty_state,
    section_title,
    full_name,
    format_date,
    pill,
    show_flash_message,
    remember,
)

from shared.assets import load_css


# ============================================================
# CONFIG
# ============================================================

MANILA_TZ = ZoneInfo("Asia/Manila")

LABEL_DISPLAY = {
    "normal":              "Normal",
    "bacterial_pneumonia": "Bacterial Pneumonia",
    "viral_pneumonia":     "Viral Pneumonia",
    "other_uncertain":     "Other / Uncertain",
}

STATUS_DISPLAY = {
    "pending_review":   ("Pending", "amber"),
    "approved":         ("Approved", "green"),
    "rejected":         ("Rejected", "red"),
    "used_in_training": ("Used in Training", "blue"),
}

RISK_DISPLAY = {
    "positive": ("HIGH", "red"),
    "negative": ("LOW", "green"),
}


# ============================================================
# SESSION KEYS
# ============================================================

KEY_CANDIDATE = "tdr_selected_candidate"


# ============================================================
# HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}


def current_user_id():
    return current_user().get("user_id")


def patient_name(patient):
    if not patient:
        return "—"
    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )


def patient_code(patient):
    if not patient:
        return "—"
    return patient.get("patient_code") or patient.get("patient_id")


def doctor_name(user):
    if not user:
        return "—"
    return full_name(
        user.get("user_fname"),
        user.get("user_mname"),
        user.get("user_lname"),
        None,
    )


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


def format_dt(value):
    parsed = parse_datetime(value)
    if not parsed:
        return "—"
    return parsed.strftime("%b %d, %Y · %I:%M %p")


def confidence_pct(value):
    if value is None:
        return None
    try:
        n = float(value)
        if n <= 1:
            n *= 100
        return round(n, 1)
    except (TypeError, ValueError):
        return None


def ai_label_from_row(row):
    """
    Convert the frozen AI snapshot into a human label.
    """
    ai_findings = (row.get("ai_findings") or "").strip().lower()
    pneumonia_type = (row.get("ai_pneumonia_type") or "").strip().lower()

    if ai_findings == "negative":
        return "Normal"

    if pneumonia_type == "bacterial_pneumonia":
        return "Bacterial Pneumonia"

    if pneumonia_type == "viral_pneumonia":
        return "Viral Pneumonia"

    if ai_findings == "positive":
        return "Pneumonia (type not classified)"

    return "No AI Result"


def get_confirmed_label_from_row(row):
    """Helper to extract the confirmed_label from the nested examination."""
    exam = row.get("examinations") or {}
    if isinstance(exam, list):
        exam = exam[0] if exam else {}
    return exam.get("confirmed_label")


# ============================================================
# NAVIGATION
# ============================================================

def go_to_detail(candidate):
    st.session_state[KEY_CANDIDATE] = candidate
    st.rerun()


def back_to_queue():
    st.session_state.pop(KEY_CANDIDATE, None)
    st.rerun()


# ============================================================
# LEVEL 0 — QUEUE
# ============================================================

def render_stat_card(label, value, icon, tone="blue"):
    with st.container(key=f"tdr_stat_{label.lower().replace(' ', '_')}"):
        st.markdown(
            "<div class='pr-hero-card' style='padding:16px;'>"
            f"<span class='material-symbols-rounded' "
            f"style='font-size:28px;color:#475569;'>{icon}</span>"
            f"<p style='margin:8px 0 4px 0;font-size:0.85rem;"
            f"color:#64748b;'>{label}</p>"
            f"<p style='margin:0;font-size:1.8rem;font-weight:700;'>"
            f"{value}</p>"
            "</div>",
            unsafe_allow_html=True,
        )


def render_candidate_row(row):
    candidate_id = row.get("candidate_id")
    patient = row.get("patients") or {}
    doctor = row.get("confirming_user") or {}

    ai_label = ai_label_from_row(row)
    
    # Get label from the nested examination
    confirmed_label_key = get_confirmed_label_from_row(row)
    doctor_label = LABEL_DISPLAY.get(
        confirmed_label_key,
        confirmed_label_key or "—",
    )

    is_override = (
        ai_label != doctor_label
        and row.get("ai_findings") is not None
    )

    status = row.get("status", "pending_review")
    status_label, status_tone = STATUS_DISPLAY.get(
        status, (status, "slate")
    )

    with st.container(key=f"tdr_row_{candidate_id}"):

        cols = st.columns([2.4, 2.2, 2.2, 1.2, 1.0])

        with cols[0]:
            st.markdown(
                f"<div class='pr-cell pr-cell-name'>"
                f"{patient_name(patient)}</div>"
                f"<div class='pr-cell pr-cell-id'>"
                f"{patient_code(patient)}</div>",
                unsafe_allow_html=True,
            )

        with cols[1]:
            st.markdown(
                f"<div class='pr-cell'>{ai_label}</div>",
                unsafe_allow_html=True,
            )

        with cols[2]:
            override_badge = (
                " <span style='color:#d97706;font-weight:700;'>"
                "⚠️</span>"
                if is_override
                else ""
            )
            st.markdown(
                f"<div class='pr-cell'>{doctor_label}"
                f"{override_badge}</div>",
                unsafe_allow_html=True,
            )

        with cols[3]:
            pill(status_label, status_tone)

        with cols[4]:
            if st.button(
                "View",
                key=f"tdr_view_{candidate_id}",
                icon=":material/visibility:",
                width="stretch",
            ):
                go_to_detail(row)


def render_queue():
    page_header(
        "Training Data Review",
        "Approve or reject doctor-confirmed labels before they "
        "enter the training set.",
    )

    # ----------------------------------------------
    # Stats
    # ----------------------------------------------

    stats = get_training_candidate_stats()

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        render_stat_card("Pending", stats.get("pending_review", 0), "hourglass_top")
    with m2:
        render_stat_card("Approved", stats.get("approved", 0), "check_circle")
    with m3:
        render_stat_card("Rejected", stats.get("rejected", 0), "cancel")
    with m4:
        render_stat_card("Total", stats.get("total", 0), "database")

    st.divider()

    # ----------------------------------------------
    # Filters
    # ----------------------------------------------

    hospitals = get_all_hospitals() or []

    hospital_names = ["All hospitals"] + sorted({
        h.get("hospital_name")
        for h in hospitals
        if h.get("hospital_name")
    })

    hospital_col, status_col, search_col, refresh_col = st.columns(
        [1.6, 1.5, 2.5, 0.8]
    )

    hospital_filter = hospital_col.selectbox(
        "Hospital",
        hospital_names,
        label_visibility="collapsed",
        key="tdr_hospital_filter",
    )

    status_filter = status_col.selectbox(
        "Status",
        [
            "Pending Review",
            "Approved",
            "Rejected",
            "Used in Training",
            "All",
        ],
        label_visibility="collapsed",
        key="tdr_status_filter",
    )

    search = search_col.text_input(
        "Search",
        placeholder="Search by patient name or ID",
        label_visibility="collapsed",
        key="tdr_search",
    ).strip().lower()

    if refresh_col.button(
        "Refresh",
        icon=":material/refresh:",
        width="stretch",
        key="tdr_refresh",
    ):
        st.rerun()

    # ----------------------------------------------
    # Map filter
    # ----------------------------------------------

    status_map = {
        "Pending Review":   "pending_review",
        "Approved":         "approved",
        "Rejected":         "rejected",
        "Used in Training": "used_in_training",
        "All":              None,
    }

    selected_hospital_id = None

    if hospital_filter != "All hospitals":
        selected_hospital_id = next(
            (
                h.get("hospital_id")
                for h in hospitals
                if h.get("hospital_name") == hospital_filter
            ),
            None,
        )

    rows = get_training_candidates_detailed(
        status=status_map.get(status_filter),
        hospital_id=selected_hospital_id,
    )

    if search:
        rows = [
            r for r in rows
            if search in " ".join([
                str(patient_name(r.get("patients")) or ""),
                str(patient_code(r.get("patients")) or ""),
            ]).lower()
        ]

    if not rows:
        empty_state("No training candidates match this filter.")
        return

    # ----------------------------------------------
    # Header
    # ----------------------------------------------

    with st.container(key="tdr_table_header"):
        cols = st.columns([2.4, 2.2, 2.2, 1.2, 1.0])
        for col, label in zip(cols, [
            "Patient",
            "AI Prediction",
            "Doctor Confirmed",
            "Status",
            "Action",
        ]):
            with col:
                st.markdown(
                    f"<div class='pr-header-cell'>{label}</div>",
                    unsafe_allow_html=True,
                )

    for row in rows:
        render_candidate_row(row)

    st.caption(f"Showing {len(rows)} candidate(s)")


# ============================================================
# LEVEL 1 — DETAIL
# ============================================================

def render_image_section(row):
    section_title("X-Ray Evidence")

    image = row.get("image")
    ai_result_id = row.get("ai_result_id")

    if not image or not image.get("image_path"):
        st.markdown(
            "<div class='pr-no-xray'>"
            "<span class='pr-no-xray-icon material-symbols-rounded'>"
            "radiology</span>"
            "<p class='pr-no-xray-title'>No X-Ray Image</p>"
            "<p class='pr-no-xray-text'>"
            "No image is linked to this candidate."
            "</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    image_url = get_xray_image_url(image.get("image_path"))
    heatmap_bytes = (
        get_xray_ai_heatmap(ai_result_id)
        if ai_result_id
        else None
    )

    original_col, heatmap_col = st.columns(2, gap="medium")

    with original_col:
        st.markdown(
            "<p class='pr-img-label'>Original X-Ray</p>",
            unsafe_allow_html=True,
        )
        if image_url:
            st.image(image_url, width="stretch")
        else:
            st.warning("Unable to load image.")

    with heatmap_col:
        st.markdown(
            "<p class='pr-img-label'>AI Heatmap Overlay</p>",
            unsafe_allow_html=True,
        )
        if heatmap_bytes:
            st.image(
                heatmap_bytes,
                caption=(
                    "Grad-CAM overlay — highlighted regions "
                    "influenced the AI prediction."
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
                "No saved Grad-CAM visualization for this X-ray."
                "</p>"
                "</div>",
                unsafe_allow_html=True,
            )


def render_case_summary(row):
    section_title("Case Summary")

    patient = row.get("patients") or {}
    exam = row.get("examinations") or {}
    doctor = row.get("confirming_user") or {}

    hospital = (patient.get("hospitals") or {})
    if isinstance(hospital, list):
        hospital = hospital[0] if hospital else {}

    st.markdown(
        "<div class='pr-hero-card'>"
        "<div class='pr-hero-row'>"
        "<span>Patient</span>"
        f"<b>{patient_name(patient)}</b>"
        "</div>"
        "<div class='pr-hero-row'>"
        "<span>Patient ID</span>"
        f"<b>{patient_code(patient)}</b>"
        "</div>"
        "<div class='pr-hero-row'>"
        "<span>Hospital</span>"
        f"<b>{hospital.get('hospital_name') or '—'}</b>"
        "</div>"
        "<div class='pr-hero-row'>"
        "<span>Examination</span>"
        f"<b>{exam.get('examination_type') or '—'}</b>"
        "</div>"
        "<div class='pr-hero-row'>"
        "<span>Confirmed By</span>"
        f"<b>{doctor_name(doctor)}</b>"
        "</div>"
        "<div class='pr-hero-row'>"
        "<span>Confirmed At</span>"
        f"<b>{format_dt(row.get('confirmed_at'))}</b>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_ai_card(row):
    section_title("AI Prediction (Frozen Snapshot)")

    ai_findings = row.get("ai_findings")
    ai_conf = confidence_pct(row.get("ai_confidence"))
    class_conf = confidence_pct(
        row.get("ai_classification_confidence")
    )

    risk_label, risk_tone = RISK_DISPLAY.get(
        (ai_findings or "").strip().lower(),
        ("No Result", "slate"),
    )

    ai_label = ai_label_from_row(row)

    st.markdown(
        "<div class='pr-hero-card'>"
        "<div class='pr-hero-row'>"
        "<span>Predicted Label</span>"
        f"<b>{ai_label}</b>"
        "</div>"
        "<div class='pr-hero-row'>"
        "<span>Risk Level</span>"
        f"<div>{pill(risk_label, risk_tone)}</div>"
        "</div>"
        "<div class='pr-hero-row'>"
        "<span>Confidence</span>"
        f"<b>{f'{ai_conf:.1f}%' if ai_conf is not None else '—'}</b>"
        "</div>"
        "<div class='pr-hero-row'>"
        "<span>Type Confidence</span>"
        f"<b>{f'{class_conf:.1f}%' if class_conf is not None else '—'}</b>"
        "</div>"
        "<div class='pr-hero-row'>"
        "<span>ResNet Version</span>"
        f"<b>{row.get('ai_model_version') or '—'}</b>"
        "</div>"
        "<div class='pr-hero-row'>"
        "<span>DenseNet Version</span>"
        f"<b>{row.get('ai_classification_model_version') or '—'}</b>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_doctor_card(row):
    section_title("Doctor Confirmation")

    confirmed_label_key = get_confirmed_label_from_row(row)
    doctor_label = LABEL_DISPLAY.get(
        confirmed_label_key,
        confirmed_label_key or "—",
    )

    ai_label = ai_label_from_row(row)
    is_override = (
        ai_label != doctor_label
        and row.get("ai_findings") is not None
    )

    override_note = (
        "<div class='pr-hero-row'>"
        "<span>Override</span>"
        "<b style='color:#d97706;'>⚠️ Yes — doctor disagreed with AI</b>"
        "</div>"
        if is_override
        else ""
    )

    st.markdown(
        "<div class='pr-hero-card'>"
        "<div class='pr-hero-row'>"
        "<span>Confirmed Label</span>"
        f"<b>{doctor_label}</b>"
        "</div>"
        f"{override_note}"
        "<div class='pr-hero-row'>"
        "<span>Notes</span>"
        f"<b>{row.get('doctor_notes') or '—'}</b>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_review_actions(row):
    section_title("Review Decision")

    candidate_id = row.get("candidate_id")
    current_status = row.get("status")

    if current_status in ("approved", "rejected"):

        status_label, status_tone = STATUS_DISPLAY.get(
            current_status, (current_status, "slate")
        )

        st.markdown(
            "<div class='pr-hero-card'>"
            "<div class='pr-hero-row'>"
            "<span>Already Reviewed</span>"
            f"<div>{pill(status_label, status_tone)}</div>"
            "</div>"
            "<div class='pr-hero-row'>"
            "<span>Reviewed At</span>"
            f"<b>{format_dt(row.get('reviewed_at'))}</b>"
            "</div>"
            "<div class='pr-hero-row'>"
            "<span>Review Notes</span>"
            f"<b>{row.get('review_notes') or '—'}</b>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    review_notes = st.text_area(
        "Review notes (optional)",
        height=80,
        key=f"tdr_notes_{candidate_id}",
        placeholder=(
            "Why are you approving or rejecting this label?"
        ),
    )

    st.write("")

    reject_col, approve_col = st.columns(2)

    if reject_col.button(
        "Reject",
        key=f"tdr_reject_{candidate_id}",
        icon=":material/cancel:",
        width="stretch",
    ):
        _submit_decision(
            candidate_id,
            "reject",
            review_notes,
        )

    if approve_col.button(
        "Approve",
        key=f"tdr_approve_{candidate_id}",
        icon=":material/check_circle:",
        type="primary",
        width="stretch",
    ):
        _submit_decision(
            candidate_id,
            "approve",
            review_notes,
        )


def _submit_decision(candidate_id, decision, review_notes):
    result = review_training_candidate(
        candidate_id=candidate_id,
        decision=decision,
        reviewer_id=current_user_id(),
        review_notes=review_notes.strip() or None,
    )

    if result.get("success"):
        remember(
            "Candidate approved."
            if decision == "approve"
            else "Candidate rejected."
        )
        back_to_queue()
    else:
        st.error(
            f"Failed to {decision}: "
            f"{result.get('message', 'Unknown error')}"
        )


def render_detail(row):
    if st.button(
        "Back to Queue",
        key="tdr_back",
        icon=":material/arrow_back:",
    ):
        back_to_queue()

    patient = row.get("patients") or {}

    st.markdown(
        "<div class='pr-report-header'>"
        "<p class='pr-report-title'>Candidate Review</p>"
        f"<p class='pr-report-sub'>"
        f"{patient_name(patient)} · {patient_code(patient)}"
        f"</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    left_col, right_col = st.columns([1.4, 1], gap="large")

    with left_col:
        render_image_section(row)
        render_case_summary(row)

    with right_col:
        render_ai_card(row)
        render_doctor_card(row)
        render_review_actions(row)


# ============================================================
# PAGE
# ============================================================

def show():
    load_css("patient_records.css")
    show_flash_message()

    selected = st.session_state.get(KEY_CANDIDATE)

    if selected:
        render_detail(selected)
        return

    render_queue()