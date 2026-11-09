# streamlit_app/pages/staff/followups.py

"""
Staff — Follow-Ups.

Landing: search + filter + active follow-ups list + KPIs
Detail: patient + appointment + parent + previous + actions
"""
import io
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import streamlit as st
from datetime import date, datetime, time as time_cls, timedelta
from zoneinfo import ZoneInfo

from backend.backend_utils.followup_utils import (
    get_hospital_follow_ups,
    get_follow_up,
    mark_follow_up_arrived,
    get_follow_up_counts,
    cancel_follow_up,
    reschedule_follow_up,
    save_follow_up_consent,
)

from backend.fetches import get_examination_consents

from streamlit_app.components.ui import (
    page_header,
    empty_state,
    section_title,
    show_rows,
    full_name,
    pill,
    metric_card,
    remember,
    safe,
    show_flash_message,
)

from shared.assets import load_css


ROLE_SUPERADMIN = 1
ROLE_STAFF = 7
ROLE_HOSPITAL_ADMIN = 6

MANILA_TZ = ZoneInfo("Asia/Manila")
KEY_SELECTED_FU = "staff_selected_fu"

ACTIVE_STATUSES = ["Scheduled", "Rescheduled"]
STATUS_OPTIONS = ["All", "Scheduled", "Rescheduled", "Completed", "Missed", "Cancelled"]

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

def patient_age(dob):
    if not dob:
        return "—"
    try:
        if isinstance(dob, str):
            d = date.fromisoformat(str(dob)[:10])
        elif isinstance(dob, date):
            d = dob
        else:
            return "—"
        today = date.today()
        age = today.year - d.year
        if (today.month, today.day) < (d.month, d.day):
            age -= 1
        return age
    except Exception:
        return "—"

# ============================================================
# DATE / TIME
# ============================================================

def format_time(value):
    if not value:
        return "—"
    try:
        if isinstance(value, time_cls):
            return value.strftime("%I:%M %p")
        return datetime.strptime(str(value)[:8], "%H:%M:%S").strftime("%I:%M %p")
    except Exception:
        return str(value)

def format_date_only(value):
    if not value:
        return "—"
    try:
        if isinstance(value, date):
            return value.strftime("%B %d, %Y")
        return date.fromisoformat(str(value)[:10]).strftime("%B %d, %Y")
    except Exception:
        return str(value)

def format_appointment(fu):
    return f"{format_date_only(fu.get('follow_up_date'))} · {format_time(fu.get('follow_up_time'))}"

def fu_date_obj(fu):
    try:
        return date.fromisoformat(str(fu.get("follow_up_date"))[:10])
    except Exception:
        return None

def is_today(fu):
    return fu_date_obj(fu) == date.today()

def is_upcoming(fu):
    d = fu_date_obj(fu)
    return d is not None and d >= date.today()

def is_overdue(fu):
    d = fu_date_obj(fu)
    return d is not None and d < date.today()

def follow_up_progress_message(fu):
    if not fu.get("follow_up_examination_id"):
        return None
    exam = fu.get("follow_up_examination") or {}
    if isinstance(exam, list):
        exam = exam[0] if exam else {}
    return {
        "Pending": "Checked in · Awaiting Physician",
        "In Progress": "Follow-Up Examination in Progress",
        "Awaiting X-Ray": "Awaiting X-Ray",
        "X-Ray Ready": "Awaiting Physician X-Ray Review",
        "Completed": "Follow-Up Examination Completed",
        "Admitted": "Follow-Up Visit Completed · Patient Admitted",
        "Discharged": "Follow-Up Visit Completed · Patient Discharged",
        "Cancelled": "Examination Cancelled · Review Required",
    }.get(exam.get("status"), "Follow-Up Examination Linked")


# ============================================================
# STATUS
# ============================================================

def status_tone(status):
    s = str(status or "").strip().lower()
    return {
        "scheduled": "blue",
        "completed": "green",
        "missed": "red",
        "cancelled": "red",
        "rescheduled": "amber",
    }.get(s, "slate")

# ============================================================
# NAVIGATION
# ============================================================

def go_to_fu_detail(fu):
    st.session_state[KEY_SELECTED_FU] = fu
    st.rerun()

def back_to_landing():
    st.session_state.pop(KEY_SELECTED_FU, None)
    st.rerun()

# ============================================================
# DIALOG — CONFIRM ARRIVAL
# ============================================================

def render_follow_up_consent_form(key_prefix, patient):
    """Follow-Up consent, using the same registered signer details as General Examination."""
    st.divider()
    section_title("Treatment Consent")

    patient = patient or {}
    registered_patient_name = patient_name(patient).strip()
    registered_guardian_name = (patient.get("emergency_contact_name") or "").strip()
    registered_number = (
        patient.get("emergency_contact_no")
        or patient.get("emergency_contact_number")
        or ""
    ).strip()
    registered_relation = (patient.get("emergency_contact_relationship") or "").strip()

    dob = patient.get("date_of_birth")
    minor = False
    try:
        birthday = date.fromisoformat(str(dob)[:10])
        today = date.today()
        minor = (today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))) < 18
    except (TypeError, ValueError):
        pass

    signer_type = st.radio(
        "Who is signing the consent?",
        options=["patient", "guardian"],
        index=1 if minor else 0,
        format_func=lambda v: "Patient" if v == "patient" else "Guardian / Authorized Representative",
        horizontal=True,
        key=f"{key_prefix}_signer_type",
    )

    guardian_name = None
    guardian_relation = None
    if signer_type == "guardian":
        guardian_name = st.text_input(
            "Guardian / Representative Name",
            value=registered_guardian_name,
            placeholder="Enter full name",
            key=f"{key_prefix}_guardian_name",
        ).strip()
        relationships = [
            "Not specified", "Mother", "Father", "Spouse", "Son", "Daughter",
            "Brother", "Sister", "Grandparent", "Legal Guardian", "Other",
        ]
        if registered_relation and registered_relation not in relationships:
            relationships.append(registered_relation)
        guardian_relation = st.selectbox(
            "Relationship to Patient",
            options=relationships,
            index=relationships.index(registered_relation) if registered_relation in relationships else 0,
            key=f"{key_prefix}_guardian_relation",
        )
        if guardian_relation == "Not specified":
            guardian_relation = None
        signed_by_name = guardian_name
    else:
        signed_by_name = registered_patient_name
        st.text_input(
            "Patient Full Name",
            value=registered_patient_name,
            disabled=True,
            key=f"{key_prefix}_patient_name",
        )
        if minor:
            st.warning("The registered patient is a minor. Select an appropriately authorized guardian or representative.")

    st.text_input(
        "Registered Emergency Contact Number",
        value=registered_number,
        disabled=True,
        key=f"{key_prefix}_emergency_contact_number",
    )

    st.markdown("**Digital Signature (Draw below)**")
    st.caption("The patient or authorized representative must sign personally.")
    canvas = st_canvas(
        stroke_width=2,
        stroke_color="#0F172A",
        background_color="#FFFFFF",
        height=140,
        width=500,
        drawing_mode="freedraw",
        return_image_data=True,
        key=f"{key_prefix}_signature",
    )

    signature_bytes = None
    if canvas is not None and canvas.image_data is not None:
        import numpy as np
        pixels = canvas.image_data.astype("uint8")
        # Detect non-white strokes in the returned canvas image.
        rgb = pixels[:, :, :3]
        has_strokes = bool(np.any(rgb < 230))
        if has_strokes:
            image = Image.fromarray(pixels, "RGBA")
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            signature_bytes = buffer.getvalue()

    confirmed = st.checkbox(
        "I confirm that the patient or authorized representative was informed, "
        "had the opportunity to ask questions, and voluntarily consented to this examination.",
        key=f"{key_prefix}_confirmed",
    )

    return {
        "confirmed": confirmed,
        "signed_by_name": signed_by_name.strip(),
        "signed_by_type": signer_type,
        "guardian_name": guardian_name,
        "guardian_relation": guardian_relation,
        "signature_bytes": signature_bytes,
        "minor_patient_signing": minor and signer_type == "patient",
    }

@st.dialog("Record Missing Follow-Up Consent", width="large")
def show_missing_consent_dialog(fu):
    examination_id = fu.get("follow_up_examination_id")

    if not examination_id:
        st.error("This follow-up has no linked examination.")
        return

    existing = get_examination_consents(examination_id)

    if existing:
        st.warning(
            "A consent record already exists. "
            "Review it before making changes."
        )
        return

    exam = fu.get("follow_up_examination") or {}
    if isinstance(exam, list):
        exam = exam[0] if exam else {}
    if exam.get("status") in ("Completed", "Admitted", "Discharged", "Cancelled"):
        st.warning(
            "This examination is finalized. A staff member cannot add a new "
            "consent retroactively. Refer it to an authorized records-correction "
            "process; do not backdate or invent a signature."
        )
        return

    st.markdown(
        f"**Follow-Up:** {fu.get('follow_up_code')}"
    )
    st.caption(
        "This records consent for the existing examination. "
        "It does not create another examination or check-in."
    )

    patient = fu.get("patients") or {}
    if isinstance(patient, list):
        patient = patient[0] if patient else {}
    consent_data = render_follow_up_consent_form(
        f"recovery_{examination_id}", patient
    )

    if st.button(
        "Save Consent to Existing Examination",
        type="primary",
        width="stretch",
        key=f"save_recovery_consent_{examination_id}",
    ):
        if consent_data["minor_patient_signing"]:
            st.error("A minor requires an appropriately authorized signer.")
            return
        if (
            not consent_data["confirmed"]
            or not consent_data["signed_by_name"]
            or not consent_data["signature_bytes"]
        ):
            st.error("Complete the consent and signature.")
            return

        result = save_follow_up_consent(
            examination_id=examination_id,
            staff_user_id=current_user_id(),
            signed_by_name=consent_data["signed_by_name"],
            signed_by_type=consent_data["signed_by_type"],
            signature_bytes=consent_data["signature_bytes"],
            guardian_name=consent_data.get("guardian_name"),
            guardian_relation=consent_data.get("guardian_relation"),
        )

        if result.get("success"):
            st.session_state.pop("staff_fu_consent_target", None)
            remember("Follow-Up consent recorded successfully.")
            st.rerun()
        else:
            st.error(result.get("message", "Unable to save consent."))

@st.dialog("Follow-Up Patient Check-In", width="large")
def show_confirm_arrival_dialog(fu):
    fu_id = fu.get("follow_up_id")
    code = fu.get("follow_up_code") or "—"

    patient = fu.get("patients") or {}
    if isinstance(patient, list):
        patient = patient[0] if patient else {}

    st.markdown(f"### Follow-Up {code}")

    show_rows([
        ("Patient", patient_name(patient)),
        ("Patient ID", patient_code(patient)),
        ("Scheduled", format_appointment(fu)),
    ])

    consent_data = render_follow_up_consent_form(
        f"staff_fu_{fu_id}", patient
    )

    st.divider()

    cancel_col, confirm_col = st.columns(2)

    if cancel_col.button(
        "Cancel",
        key=f"staff_fu_cancel_arrival_{fu_id}",
        width="stretch",
    ):
        st.session_state.pop("staff_fu_arrival_target", None)
        st.rerun()

    if confirm_col.button(
        "Confirm Consent & Check In",
        key=f"staff_fu_confirm_arrival_{fu_id}",
        type="primary",
        width="stretch",
    ):
        if consent_data["minor_patient_signing"]:
            st.error("A minor requires an appropriately authorized signer.")
            return
        if not consent_data["confirmed"]:
            st.error("Consent confirmation is required.")
            return

        if not consent_data["signed_by_name"]:
            st.error("Please enter the signer's full name.")
            return

        if not consent_data["signature_bytes"]:
            st.error("Please provide a signature.")
            return

        if consent_data["signed_by_type"] == "Guardian":
            if (
                not consent_data["guardian_name"]
                or not consent_data["guardian_relation"]
            ):
                st.error("Complete the guardian information.")
                return

        result = mark_follow_up_arrived(
            fu_id,
            current_user_id(),
            consent_data=consent_data,
        )

        if result.get("success"):
            remember(
                "Patient checked in. Follow-Up Examination "
                "and consent recorded successfully."
            )
            st.session_state.pop("staff_fu_arrival_target", None)
            back_to_landing()
        else:
            st.error(result.get("message", "Check-in failed."))

            if result.get("recovery_required"):
                st.warning(
                    "An examination already exists. "
                    "Refresh the Follow-Up details and use "
                    "'Record Missing Consent'. Do not check in again."
                )


# ============================================================
# LANDING — KPI + FILTERS + LIST
# ============================================================

def render_kpi_strip(follow_ups):

    today = date.today()
    scheduled_today = [f for f in follow_ups if is_today(f) and f.get("status") in ACTIVE_STATUSES]
    upcoming = [f for f in follow_ups if is_upcoming(f) and f.get("status") in ACTIVE_STATUSES]
    overdue = [f for f in follow_ups if is_overdue(f) and f.get("status") in ACTIVE_STATUSES]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Scheduled Today", len(scheduled_today), "event", tone="blue")
    with col2:
        metric_card("Upcoming", len(upcoming), "calendar_month", tone="green")
    with col3:
        metric_card("Overdue", len(overdue), "warning", tone="amber")
    with col4:
        metric_card("Active Total", len(upcoming) + len(overdue), "schedule", tone="teal")

def render_filter_bar():

    search_col, status_col = st.columns([3, 1.5])

    search = search_col.text_input(
        "Search",
        placeholder="Search by FU ID, patient name, or patient code",
        key="staff_fu_search",
        label_visibility="collapsed",
    ).strip().lower()

    status_filter = status_col.selectbox(
        "Status",
        STATUS_OPTIONS,
        key="staff_fu_status_filter",
        label_visibility="collapsed",
    )

    return search, status_filter

def apply_filters(follow_ups, search, status_filter):

    results = follow_ups

    if status_filter != "All":
        results = [f for f in results if (f.get("status") or "") == status_filter]

    if search:
        filtered = []
        for f in results:
            patient = f.get("patients") or {}
            if isinstance(patient, list):
                patient = patient[0] if patient else {}

            code = (f.get("follow_up_code") or "").lower()
            name = patient_name(patient).lower()
            pc = (patient.get("patient_code") or "").lower()

            if search in code or search in name or search in pc:
                filtered.append(f)
        results = filtered

    return results

# ============================================================
# LANDING — FU CARD
# ============================================================

def render_fu_card(fu, show_arrived=True):

    fu_id = fu.get("follow_up_id")
    code = fu.get("follow_up_code") or "—"
    status = fu.get("status") or "Scheduled"
    patient = fu.get("patients") or {}
    if isinstance(patient, list):
        patient = patient[0] if patient else {}

    source = fu.get("source_examination") or {}
    if isinstance(source, list):
        source = source[0] if source else {}

    parent_summary = (
        f"{source.get('examination_type') or 'General Consult'} · "
        f"{format_date_only(source.get('examination_date'))}"
    )

    with st.container(key=f"sf_fu_card_{fu_id}"):

        cols = st.columns([1.6, 2.5, 2.2, 2.2, 1.2], vertical_alignment="center")

        with cols[0]:
            st.markdown(
                f"<div class='sf-fu-code-badge'>"
                f"<span class='material-symbols-rounded sf-code-icon'>tag</span>"
                f"<span>{safe(code)}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with cols[1]:
            st.markdown(
                f"<div class='sf-fu-patient'>{safe(patient_name(patient))}</div>"
                f"<div class='sf-fu-sub'><span class='material-symbols-rounded sf-sub-icon'>badge</span>{safe(patient_code(patient))}</div>",
                unsafe_allow_html=True,
            )

        with cols[2]:
            st.markdown(
                f"<div class='sf-fu-schedule'>"
                f"<span class='material-symbols-rounded sf-sched-icon'>calendar_today</span>"
                f"<span class='sf-sched-text'>{safe(format_appointment(fu))}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with cols[3]:
            st.markdown(
                f"<div class='sf-fu-parent'>"
                f"<span class='material-symbols-rounded sf-parent-icon'>medical_information</span>"
                f"<span class='sf-parent-text'>{safe(parent_summary)}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with cols[4]:
            pill(status, status_tone(status))
            progress = follow_up_progress_message(fu)
            if progress:
                st.caption(progress)

        btn_cols = st.columns([1, 1, 1, 4, 1], vertical_alignment="center")

        with btn_cols[0]:
            if st.button("View", key=f"sf_fu_view_{fu_id}", icon=":material/visibility:", use_container_width=True):
                go_to_fu_detail(fu)

        with btn_cols[1]:
            if (
                show_arrived
                and status in ACTIVE_STATUSES
                and not fu.get("follow_up_examination_id")
            ):
                if st.button("Arrived", key=f"sf_fu_arrived_{fu_id}", icon=":material/check_circle:", type="primary", use_container_width=True):
                    st.session_state["staff_fu_arrival_target"] = fu
                    st.rerun()

# ============================================================
# LANDING — MAIN
# ============================================================

def render_landing():

    hospital_id = current_hospital_id()

    # Pull all follow-ups for the hospital (single query).
    try:
        all_fus = get_hospital_follow_ups(hospital_id=hospital_id) or []
    except Exception as e:
        st.error(f"Failed to load follow-ups: {e}")
        all_fus = []

    render_kpi_strip(all_fus)
    st.divider()

    search, status_filter = render_filter_bar()
    st.divider()

    filtered = apply_filters(all_fus, search, status_filter)

    section_title(
        "Follow-Ups",
        f"{len(filtered)} record(s) match your filters",
    )

    if not filtered:
        empty_state("No follow-ups match the current filters.")
        return

    # Sort: scheduled/rescheduled first by date, then by date descending.
    def sort_key(f):
        status_priority = 0 if f.get("status") in ACTIVE_STATUSES else 1
        d = fu_date_obj(f) or date.max
        return (status_priority, d)

    filtered = sorted(filtered, key=sort_key)

    for fu in filtered:
        render_fu_card(fu)

# ============================================================
# DETAIL VIEW (unchanged from your current version)
# ============================================================

@st.dialog("Parent General Consult", width="medium")
def show_parent_consult_dialog(exam):

    if not exam:
        st.error("No consultation data.")
        return

    st.markdown(
        "<div class='sf-detail-header'>"
        f"<p class='sf-detail-title'>{exam.get('examination_type') or 'General Consult'}</p>"
        f"<p class='sf-detail-sub'>{format_date_only(exam.get('examination_date'))}</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    show_rows([
        ("Status", exam.get("status") or "—"),
        ("Chief Complaint", exam.get("chief_complaint") or "—"),
        ("HPI", exam.get("history_of_present_illness") or "—"),
        ("Physical Exam", exam.get("physical_examination") or "—"),
        ("Diagnosis", exam.get("diagnosis") or "—"),
        ("Plans / Orders", exam.get("plans_orders") or "—"),
        ("Disposition", exam.get("disposition") or "—"),
    ])

    st.divider()

    if st.button("Close", key="staff_parent_consult_close", use_container_width=True):
        st.session_state.pop("staff_fu_parent_view", None)
        st.rerun()

def render_fu_detail():

    fu = st.session_state.get(KEY_SELECTED_FU)
    if not fu:
        back_to_landing()
        return

    try:
        refreshed = get_follow_up(fu.get("follow_up_id"))
        if refreshed:
            fu = refreshed
            st.session_state[KEY_SELECTED_FU] = refreshed
    except Exception:
        pass

    code = fu.get("follow_up_code") or "—"
    status = fu.get("status") or "Scheduled"
    patient = fu.get("patients") or {}
    if isinstance(patient, list):
        patient = patient[0] if patient else {}

    source = fu.get("source_examination") or {}
    if isinstance(source, list):
        source = source[0] if source else {}

    prev_id = fu.get("previous_follow_up_id")
    prev_fu = None
    if prev_id:
        try:
            prev_fu = get_follow_up(prev_id)
        except Exception:
            prev_fu = None

    if st.button(
        "Back to Follow-Ups",
        key="staff_fu_detail_back",
        icon=":material/arrow_back:",
    ):
        back_to_landing()

    st.markdown(
        "<div class='sf-detail-header'>"
        "<div class='sf-detail-eyebrow'>"
        "<span class='material-symbols-rounded sf-eyebrow-icon'>medical_services</span>"
        "<span>Patient Follow-Up Dossier</span>"
        "</div>"
        "<div class='sf-detail-title-row'>"
        f"<p class='sf-detail-title'>Follow-Up {safe(code)}</p>"
        f"<span class='sf-detail-pill'><span class='material-symbols-rounded'>event_available</span>{safe(format_appointment(fu))}</span>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)

    with left:
        st.markdown(
            "<div class='sf-card'>"
            "<div class='sf-card-header-bar'>"
            "<span class='material-symbols-rounded sf-card-icon'>person</span>"
            "<span class='sf-card-eyebrow'>Patient Demographics</span>"
            "</div>"
            f"<p class='sf-card-title'>{safe(patient_name(patient))}</p>"
            "<div class='sf-card-row'>"
            f"<span>Patient ID</span><b class='sf-mono-code'>{safe(patient_code(patient))}</b>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Age / Gender</span>"
            f"<b>{safe(str(patient_age(patient.get('date_of_birth'))))} yrs / "
            f"{safe(patient.get('sex') or '—')}</b>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Contact</span>"
            f"<b>{safe(patient.get('contact_number') or '—')}</b>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            "<div class='sf-card'>"
            "<div class='sf-card-header-bar'>"
            "<span class='material-symbols-rounded sf-card-icon'>calendar_month</span>"
            "<span class='sf-card-eyebrow'>Appointment Schedule</span>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Status</span><b>{pill(status, status_tone(status))}</b>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Scheduled Date</span>"
            f"<b>{safe(format_date_only(fu.get('follow_up_date')))}</b>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Scheduled Time</span>"
            f"<b>{safe(format_time(fu.get('follow_up_time')))}</b>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Clinical Notes</span>"
            f"<b>{safe(fu.get('notes') or 'None recorded')}</b>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    section_title("Parent General Consult")

    if source:
        st.markdown(
            "<div class='sf-card sf-card--info'>"
            "<div class='sf-card-header-bar'>"
            "<span class='material-symbols-rounded sf-card-icon sf-card-icon-blue'>clinical_notes</span>"
            "<span class='sf-card-eyebrow'>Initial Clinical Encounter</span>"
            "</div>"
            f"<p class='sf-card-title'>"
            f"{safe(source.get('examination_type') or 'General Consult')}</p>"
            "<div class='sf-card-row'>"
            f"<span>Consult Date</span>"
            f"<b>{safe(format_date_only(source.get('examination_date')))}</b>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Chief Complaint</span>"
            f"<b>{safe(source.get('chief_complaint') or '—')}</b>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Working Diagnosis</span>"
            f"<b>{safe(source.get('diagnosis') or '—')}</b>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        # NEW: explicit button to open the full parent dialog
        if st.button(
            "See Full Parent Consult",
            key=f"staff_fu_detail_view_parent_{fu.get('follow_up_id')}",
            icon=":material/open_in_new:",
            width="stretch",
        ):
            st.session_state["staff_fu_parent_view"] = source
            st.rerun()
    else:
        st.caption("No parent consultation linked.")


    section_title("Previous Follow-Up")

    if prev_fu:
        st.markdown(
            "<div class='sf-card sf-card--info'>"
            "<div class='sf-card-header-bar'>"
            "<span class='material-symbols-rounded sf-card-icon sf-card-icon-teal'>history</span>"
            "<span class='sf-card-eyebrow'>Prior Follow-Up History</span>"
            "</div>"
            f"<p class='sf-card-title'>"
            f"{safe(prev_fu.get('follow_up_code') or 'Previous Follow-Up')}</p>"
            "<div class='sf-card-row'>"
            f"<span>Scheduled</span>"
            f"<b>{safe(format_appointment(prev_fu))}</b>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Status</span><b>{pill(prev_fu.get('status') or '—', status_tone(prev_fu.get('status')))}</b>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption("No previous follow-up — this is the first.")

    st.divider()

    col_arrive, col_resched, col_cancel = st.columns(3)

    if status in ACTIVE_STATUSES and not fu.get("follow_up_examination_id"):
        if col_arrive.button(
            "Mark as Arrived",
            key=f"staff_fu_arrive_detail_{fu.get('follow_up_id')}",
            icon=":material/check_circle:",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["staff_fu_arrival_target"] = fu
            st.rerun()
    elif fu.get("follow_up_examination_id"):
        examination_id = fu["follow_up_examination_id"]

        try:
            existing_consents = get_examination_consents(
                examination_id
            )
        except Exception as exc:
            st.error(f"Unable to verify consent: {exc}")
            existing_consents = None

        with col_arrive:
            if existing_consents is None:
                st.warning("Consent verification unavailable.")

            elif not existing_consents:
                linked_exam = fu.get("follow_up_examination") or {}
                if isinstance(linked_exam, list):
                    linked_exam = linked_exam[0] if linked_exam else {}
                if linked_exam.get("status") in ("Completed", "Admitted", "Discharged", "Cancelled"):
                    st.caption("Missing consent · finalized examination; authorized correction required")
                elif st.button(
                    "Record Missing Consent",
                    key=f"recover_consent_{examination_id}",
                    icon=":material/draw:",
                    width="stretch",
                ):
                    st.session_state["staff_fu_consent_target"] = fu
                    st.rerun()

            else:
                st.caption("Consent record available")

    if col_resched.button(
        "Reschedule",
        key=f"staff_fu_resched_{fu.get('follow_up_id')}",
        icon=":material/event_repeat:",
        use_container_width=True,
        disabled=(status not in ACTIVE_STATUSES or bool(fu.get("follow_up_examination_id"))),
    ):
        st.session_state["staff_fu_reschedule_target"] = fu
        st.rerun()

    if col_cancel.button(
        "Cancel",
        key=f"staff_fu_cancel_{fu.get('follow_up_id')}",
        icon=":material/cancel:",
        use_container_width=True,
        disabled=(status not in ACTIVE_STATUSES or bool(fu.get("follow_up_examination_id"))),
    ):
        st.session_state["staff_fu_cancel_target"] = fu
        st.rerun()


# ============================================================
# DIALOG — RESCHEDULE
# ============================================================

@st.dialog("Reschedule Follow-Up", width="small")
def show_reschedule_dialog(fu):

    fu_id = fu.get("follow_up_id")

    try:
        default_date = date.fromisoformat(str(fu.get("follow_up_date"))[:10])
    except Exception:
        default_date = date.today()

    if default_date < date.today():
        default_date = date.today()

    st.markdown(f"Reschedule **{fu.get('follow_up_code') or 'this follow-up'}**.")

    new_date = st.date_input(
        "New Date",
        value=default_date,
        min_value=date.today(),
        key=f"staff_fu_resched_date_{fu_id}",
    )

    try:
        default_time = time_cls.fromisoformat(str(fu.get("follow_up_time"))[:8])
    except Exception:
        default_time = time_cls(9, 0)

    new_time = st.time_input("New Time", value=default_time, key=f"staff_fu_resched_time_{fu_id}")

    st.divider()

    cancel_col, save_col = st.columns(2)

    if cancel_col.button("Cancel", key=f"staff_fu_resched_cancel_{fu_id}", use_container_width=True):
        st.session_state.pop("staff_fu_reschedule_target", None)
        st.rerun()

    if save_col.button("Save", key=f"staff_fu_resched_save_{fu_id}", type="primary", use_container_width=True):
        result = reschedule_follow_up(fu_id, new_date, new_time.strftime("%H:%M:%S"))
        if result.get("success"):
            remember("Follow-up rescheduled.")
            st.session_state.pop("staff_fu_reschedule_target", None)
            st.rerun()
        else:
            st.error(result.get("message", "Failed to reschedule."))

# ============================================================
# DIALOG — CANCEL
# ============================================================

@st.dialog("Cancel Follow-Up", width="small")
def show_cancel_dialog(fu):

    fu_id = fu.get("follow_up_id")

    st.warning(f"Cancel follow-up **{fu.get('follow_up_code') or ''}**?")
    st.caption("This cannot be undone from here. A new follow-up can be scheduled by the physician if needed.")

    st.divider()

    keep_col, cancel_col = st.columns(2)

    if keep_col.button("Keep Follow-Up", key=f"staff_fu_cancel_keep_{fu_id}", use_container_width=True):
        st.session_state.pop("staff_fu_cancel_target", None)
        st.rerun()

    if cancel_col.button("Yes, Cancel", key=f"staff_fu_cancel_confirm_{fu_id}", type="primary", use_container_width=True):
        result = cancel_follow_up(fu_id)
        if result.get("success"):
            remember("Follow-up cancelled.")
            st.session_state.pop("staff_fu_cancel_target", None)
            st.rerun()
        else:
            st.error(result.get("message", "Failed to cancel."))

# ============================================================
# PAGE
# ============================================================

def show():

    load_css("staff_css/followup.css")
    show_flash_message()

    role_id = current_role_id()
    if role_id not in (ROLE_STAFF, ROLE_HOSPITAL_ADMIN, ROLE_SUPERADMIN):
        st.error("You don't have access to Follow-Ups.")
        return

    with st.container(key="staff_followups_root"):
        page_header("Follow-Ups", "Search and manage patient follow-up appointments.")
        if st.session_state.get(KEY_SELECTED_FU):
            render_fu_detail()
        else:
            render_landing()

    # Exactly one Streamlit dialog can be opened in a single run.
    if st.session_state.get("staff_fu_consent_target"):
        show_missing_consent_dialog(st.session_state["staff_fu_consent_target"])
    elif st.session_state.get("staff_fu_arrival_target"):
        show_confirm_arrival_dialog(st.session_state["staff_fu_arrival_target"])
    elif st.session_state.get("staff_fu_parent_view"):
        show_parent_consult_dialog(st.session_state["staff_fu_parent_view"])
    elif st.session_state.get("staff_fu_reschedule_target"):
        show_reschedule_dialog(st.session_state["staff_fu_reschedule_target"])
    elif st.session_state.get("staff_fu_cancel_target"):
        show_cancel_dialog(st.session_state["staff_fu_cancel_target"])
