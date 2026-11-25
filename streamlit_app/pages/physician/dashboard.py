"""Physician dashboard: hospital-scoped clinical workbench.

Replace streamlit_app/pages/physician/dashboard.py with this file.
"""

from collections import Counter
from pathlib import Path
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import altair as alt
import streamlit as st

from backend.fetches import (
    get_pending_examinations,
    get_pending_xray_requests,
    get_xray_ready_examinations,
    get_completed_patients_with_latest_ai,
)
from backend.backend_utils.followup_utils import get_hospital_follow_ups
from streamlit_app.components.ui import refresh_button, full_name, safe

MANILA = ZoneInfo("Asia/Manila")
ROLE_RADIOLOGIST = 3
ACTIVE_FOLLOW_UPS = {"Scheduled", "Rescheduled"}


def _patient(record):
    value = record.get("patients") or {}
    return (value[0] if value else {}) if isinstance(value, list) else value


def _name(patient):
    return full_name(
        patient.get("first_name"), patient.get("middle_name"),
        patient.get("last_name"), patient.get("suffix"),
    ) or "Unnamed patient"


def _date(value):
    if not value:
        return None
    try:
        if isinstance(value, datetime):
            return value.astimezone(MANILA).date() if value.tzinfo else value.date()
        if isinstance(value, date):
            return value
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None


def _datetime(value):
    if not value:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(MANILA)
    except (TypeError, ValueError):
        return None


def _go(page):
    st.session_state.current_page = page
    st.rerun()


ICON_GLYPHS = {
    "person_search": "◉", "pending_actions": "◷",
    "radiology": "✚", "event_available": "▣",
    "clinical_notes": "▤", "monitoring": "▥",
    "neurology": "✧", "event_upcoming": "▣", "bolt": "ϟ",
}


def _icon(name):
    # Glyphs render even when Google Material Symbols is blocked.
    return safe(ICON_GLYPHS.get(name, "•"))


def _metric(title, value, icon, tone, note):
    markup = (
        f'<div class="pd-metric pd-{tone}">'
        f'<div class="pd-metric-top"><span class="material-symbols-rounded">{_icon(icon)}</span>'
        f'<span class="pd-metric-label">{safe(title)}</span></div>'
        f'<div class="pd-metric-number">{safe(value)}</div>'
        f'<div class="pd-metric-note">{safe(note)}</div></div>'
    )
    st.markdown(markup, unsafe_allow_html=True)


def _section(title, subtitle, icon):
    st.markdown(
        f'<div class="pd-section-title"><span class="material-symbols-rounded">{_icon(icon)}</span>'
        f'<strong>{safe(title)}</strong></div>'
        f'<div class="pd-section-subtitle">{safe(subtitle)}</div>',
        unsafe_allow_html=True,
    )


def _load(hospital_id):
    # The hospital ID comes only from the authenticated server session.
    return {
        "pending": get_pending_examinations(hospital_id=hospital_id),
        "requests": get_pending_xray_requests(hospital_id=hospital_id),
        "ready": get_xray_ready_examinations(hospital_id=hospital_id),
        "followups": get_hospital_follow_ups(hospital_id=hospital_id),
        "latest_ai": get_completed_patients_with_latest_ai(hospital_id=hospital_id),
    }


def _review_queue(examinations):
    _section("Ready for clinical review", "X-rays awaiting physician interpretation", "clinical_notes")
    if not examinations:
        st.info("No X-rays are currently awaiting physician review.")
    else:
        ordered = sorted(
            examinations,
            key=lambda e: _datetime(e.get("created_at"))
            or datetime.max.replace(tzinfo=MANILA),
        )
        for exam in ordered[:5]:
            patient = _patient(exam)
            with st.container(border=True):
                left, right = st.columns([4, 1], vertical_alignment="center")
                with left:
                    st.markdown(f"**{safe(_name(patient))}**")
                    st.caption(
                        f"{patient.get('patient_code') or 'No patient code'} · "
                        f"{exam.get('examination_type') or 'Examination'}"
                    )
                with right:
                    if st.button(
                        "Review", key=f"pd_review_{exam.get('examination_id')}",
                        type="primary", width="stretch",
                    ):
                        st.session_state["review_examination"] = exam
                        st.session_state["review_patient"] = patient
                        _go("Review Patient")
    if st.button("Open full review queue", key="pd_full_reviews", width="stretch"):
        _go("Review Patient")


def _activity(pending, ready, requests):
    _section("Clinical workload", "Current examination and imaging pipeline", "monitoring")
    data = pd.DataFrame(
        {
            "Workflow": ["Pending examination", "Pending X-ray request", "X-ray ready"],
            "Cases": [len(pending), len(requests), len(ready)],
        }
    ).set_index("Workflow")
    st.bar_chart(data, horizontal=True, height=240, color="#0797a4")
    st.caption("Current workflow counts — not historical physician review totals.")


def _ai_summary(rows):
    _section(
        "AI Findings Summary",
        "Latest eligible AI screening result per patient",
        "neurology",
    )

    findings = Counter()
    for row in rows:
        value = str(row.get("ai_findings") or "").strip().lower()
        if value == "positive":
            findings["Positive"] += 1
        elif value == "negative":
            findings["Negative"] += 1
        elif value:
            findings["Other / Uncertain"] += 1

    total = sum(findings.values())
    if not total:
        st.info("No eligible AI screening results are available.")
        return

    # The chart counts screening outputs, not physician-confirmed diagnoses.
    labels = ["Positive", "Negative", "Other / Uncertain"]
    colors = ["#ed6571", "#13a987", "#d5a44c"]
    chart_rows = pd.DataFrame({
        "Finding": labels,
        "Patients": [findings.get(label, 0) for label in labels],
    })
    chart = (
        alt.Chart(chart_rows)
        .mark_arc(innerRadius=70, outerRadius=94, cornerRadius=5)
        .encode(
            theta=alt.Theta("Patients:Q", stack=True),
            color=alt.Color(
                "Finding:N",
                scale=alt.Scale(domain=labels, range=colors),
                legend=None,
            ),
            tooltip=["Finding:N", "Patients:Q"],
        )
        .properties(height=215)
    )
    st.altair_chart(chart, use_container_width=True)

    st.markdown(
        f'<div class="pd-ai-total"><strong>{total}</strong>'
        '<span>Patients with AI screening results</span></div>',
        unsafe_allow_html=True,
    )
    for label, color in zip(labels, colors):
        count = findings.get(label, 0)
        st.markdown(
            f'<div class="pd-ai-legend">'
            f'<span><i style="background:{color}"></i>{safe(label)}</span>'
            f'<strong>{count} <small>({count / total:.0%})</small></strong>'
            '</div>',
            unsafe_allow_html=True,
        )

    st.caption(
        "AI predictions support screening and require physician "
        "interpretation; they are not confirmed diagnoses."
    )


def _followups(rows):
    _section("Upcoming follow-ups", "Scheduled patient returns", "event_upcoming")
    today = datetime.now(MANILA).date()
    upcoming = [
        row for row in rows
        if row.get("status") in ACTIVE_FOLLOW_UPS
        and (_date(row.get("follow_up_date")) or date.min) >= today
    ]
    upcoming.sort(key=lambda r: (str(r.get("follow_up_date") or ""), str(r.get("follow_up_time") or "")))
    if not upcoming:
        st.info("No upcoming follow-up appointments.")
    else:
        for row in upcoming[:4]:
            patient = _patient(row)
            st.markdown(
                f'<div class="pd-followup"><strong>{safe(_name(patient))}</strong>'
                f'<span>{safe(row.get("follow_up_date") or "—")}</span></div>',
                unsafe_allow_html=True,
            )
    if st.button("View all follow-ups", key="pd_all_followups", width="stretch"):
        _go("Follow-Ups")


def _quick_actions():
    _section("Quick Actions", "Your most-used clinical workflows", "bolt")
    actions = [
        ("Patient Queue", "groups", "Patient Queue"),
        ("Review Patient", "radiology", "Review Patient"),
        ("Patient Records", "folder_shared", "Patient Records"),
        ("Follow-Ups", "event_available", "Follow-Ups"),
    ]
    for start in range(0, len(actions), 2):
        columns = st.columns(2, gap="small")
        for col, (label, icon, page) in zip(columns, actions[start:start + 2]):
            with col:
                with st.container(key=f"pd_tile_{start}_{page.lower().replace(' ', '_')}"):
                    if st.button(
                        label,
                        icon=f":material/{icon}:",
                        key=f"pd_action_{page}",
                        width="stretch",
                    ):
                        _go(page)

    with st.container(key="pd_tile_inpatient"):
        if st.button(
            "Inpatient Dashboard",
            icon=":material/bedroom_parent:",
            key="pd_action_Inpatient Dashboard",
            width="stretch",
        ):
            _go("Inpatient Dashboard")


def show():
    # Resolve the stylesheet relative to this Python file.
    # No role-folder search ambiguity and no silent missing CSS.
    css_path = (
        Path(__file__).resolve().parents[3]
        / "shared" / "theme" / "css_content"
        / "physician_css" / "dashboard.css"
    )
    if css_path.is_file():
        st.markdown(
            "<style>" + css_path.read_text(encoding="utf-8") + "</style>",
            unsafe_allow_html=True,
        )
    else:
        st.error(f"Physician dashboard CSS missing: {css_path}")
        return
    user = st.session_state.get("user") or {}
    try:
        role_id = int(user.get("role_id"))
    except (TypeError, ValueError):
        role_id = None
    if role_id != ROLE_RADIOLOGIST:
        st.error("You do not have access to the Physician Dashboard.")
        return
    hospital_id = user.get("hospital_id")
    if not hospital_id:
        st.error("Your account has no assigned hospital. Contact your administrator.")
        return

    header, refresh = st.columns([8, 0.7], vertical_alignment="center")
    with header:
        st.markdown(
            '<div class="pd-heading"><div class="pd-eyebrow">PHYSICIAN WORKSPACE</div>'
            '<h1>Clinical Review Center</h1>'
            '<p>Prioritize clinical reviews, follow imaging requests, and manage patient care.</p>'
            '</div>', unsafe_allow_html=True,
        )
    with refresh:
        refresh_button("physician_dashboard_refresh")

    try:
        with st.spinner("Loading clinical dashboard..."):
            data = _load(hospital_id)
    except Exception:
        st.error("Could not load dashboard information. Please refresh and try again.")
        return

    today = datetime.now(MANILA).date()
    upcoming = sum(
        row.get("status") in ACTIVE_FOLLOW_UPS
        and (_date(row.get("follow_up_date")) or date.min) >= today
        for row in data["followups"]
    )
    unique_review_patients = len({
        _patient(e).get("patient_id") for e in data["ready"]
        if _patient(e).get("patient_id")
    })

    metrics = [
        ("Patients to review", unique_review_patients, "person_search", "teal", "With X-ray ready for review"),
        ("Pending examinations", len(data["pending"]), "pending_actions", "blue", "Awaiting physician action"),
        ("Pending X-ray requests", len(data["requests"]), "radiology", "amber", "Awaiting imaging"),
        ("Upcoming follow-ups", upcoming, "event_available", "green", "Scheduled from today onward"),
    ]
    for col, values in zip(st.columns(4, gap="small"), metrics):
        with col:
            _metric(*values)

    st.write("")
    main, side = st.columns([1.65, 1], gap="medium")
    with main:
        with st.container(border=True):
            _review_queue(data["ready"])
        with st.container(border=True):
            _activity(data["pending"], data["ready"], data["requests"])
    with side:
        with st.container(border=True):
            _ai_summary(data["latest_ai"])
        with st.container(border=True):
            _followups(data["followups"])
        with st.container(border=True):
            _quick_actions()
