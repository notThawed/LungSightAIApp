import streamlit as st

from datetime import datetime, timezone

from backend.fetches import (
    get_pending_xray_examinations,
)

from streamlit_app.components.ui import (
    page_header,
    empty_state,
    full_name,
    format_date,
    pill,
    metric_card,
    table_header,
    table_row,
    name_cell,
    text_cell,
    pill_cell,
    show_flash_message,
)

from shared.assets import load_css


# ============================================================
# CONFIG
# ============================================================

ROLE_SUPERADMIN = 1
ROLE_RADIOLOGIST = 3
ROLE_RADTECH = 4
ROLE_HOSPITAL_ADMIN = 6
ROLE_STAFF = 7

RADTECH_ROLES = [ROLE_RADTECH]

QUEUE_WIDTHS = [2.5, 1.2, 1.2, 1.2, 1.5]
QUEUE_HEADERS = ["Patient", "Body part", "Priority", "Waiting", ""]

# ------------------------------------------------------------
# Navigation: sidebar reads st.session_state.current_page
# and stores the page LABEL (as used in radtech_layout.py).
# ------------------------------------------------------------

ANALYZE_PAGE_LABEL = "Analyze X-Ray"


# ============================================================
# HELPERS
# ============================================================

def current_role_id():
    return (st.session_state.get("user") or {}).get("role_id")


def current_hospital_id():
    return (st.session_state.get("user") or {}).get("hospital_id")


def patient_name(patient):
    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )


def patient_code(patient):
    return patient.get("patient_code") or patient.get("patient_id")


def waiting_minutes(created_at_str):
    if not created_at_str:
        return 0

    try:
        created = datetime.fromisoformat(
            str(created_at_str).replace("Z", "+00:00")
        )

        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)

        return max(0, int((now - created).total_seconds() // 60))

    except Exception:
        return 0


def waiting_tone(minutes):
    if minutes < 10:
        return "green"
    if minutes < 30:
        return "amber"
    return "red"


def format_waiting(minutes):
    if minutes < 60:
        return f"{minutes} min"

    hours = minutes // 60

    return f"{hours}h {minutes % 60}m"


# ============================================================
# NAVIGATION HANDOFF
# ============================================================

def open_analyze_for(examination, patient):
    """
    Store the selected examination + patient, then switch
    the sidebar's current page to 'Analyze X-Ray'.
    """

    # Selected patient context
    st.session_state["radtech_active_examination"] = examination
    st.session_state["radtech_active_patient"] = patient

    # Clear stale analysis state
    st.session_state.pop("radtech_analysis_result", None)
    st.session_state.pop("rx_upload", None)

    # Tell the sidebar/layout to render the analyze page
    st.session_state.current_page = ANALYZE_PAGE_LABEL

    st.rerun()


# ============================================================
# TABLE
# ============================================================

def render_xray_queue(grouped):

    if not grouped:
        empty_state("No X-ray requests at the moment.")
        return

    with st.container(key="sa_table_xray_queue"):

        table_header(QUEUE_HEADERS, QUEUE_WIDTHS, "xray_queue")

        for item in grouped:

            patient = item["patient"]
            exam = item["exam"]
            waiting = item["waiting"]
            patient_id = patient.get("patient_id")
            exam_id = exam["examination_id"]

            with table_row(f"xray_{exam_id}", QUEUE_WIDTHS) as cols:

                name_cell(
                    cols[0],
                    patient_name(patient),
                    sub=patient_code(patient),
                )

                text_cell(cols[1], "Chest")

                pill_cell(cols[2], "Routine", "blue")

                pill_cell(
                    cols[3],
                    format_waiting(waiting),
                    waiting_tone(waiting),
                )

                # ------------------------------------------------
                # SINGLE ACTION — hand off to analyze.py
                # ------------------------------------------------

                if cols[4].button(
                    "Analyze",
                    key=f"analyze_{exam_id}",
                    icon=":material/radiology:",
                    type="primary",
                    width="stretch",
                ):

                    open_analyze_for(exam, patient)


# ============================================================
# GROUPING
# ============================================================

def group_xray_by_patient(pending):

    grouped = []

    for exam in pending:

        patient = exam.get("patients") or {}

        if not patient.get("patient_id"):
            continue

        grouped.append({
            "patient": patient,
            "exam": exam,
            "waiting": waiting_minutes(exam.get("created_at")),
        })

    grouped.sort(key=lambda x: x["waiting"], reverse=True)

    return grouped


# ============================================================
# METRICS
# ============================================================

def render_metrics(grouped):

    total = len(grouped)

    if grouped:
        longest = max(g["waiting"] for g in grouped)
        average = sum(g["waiting"] for g in grouped) // total
    else:
        longest = 0
        average = 0

    m1, m2, m3 = st.columns(3)

    with m1:
        metric_card("X-Rays waiting", total, "radiology", tone="blue")

    with m2:
        metric_card("Longest wait", format_waiting(longest), "schedule", tone="red")

    with m3:
        metric_card("Average wait", format_waiting(average), "timer", tone="green")


# ============================================================
# PAGE
# ============================================================

def show():

    load_css("manage_examinations.css")
    show_flash_message()

    role_id = current_role_id()
    hospital_id = current_hospital_id()

    if role_id == ROLE_SUPERADMIN:
        filter_hospital = None
    elif role_id in RADTECH_ROLES:
        filter_hospital = hospital_id
    else:
        st.error("You don't have access to the X-ray queue.")
        return

    with st.container(key="sa_page"):

        page_header(
            "X-Ray Queue",
            "Pending X-ray requests awaiting imaging. "
            "Pick a patient to analyze their X-Ray.",
        )

        if st.button(
            "Refresh",
            icon=":material/refresh:",
            key="xray_queue_refresh",
            width="stretch",
        ):
            st.rerun()

        try:
            pending = get_pending_xray_examinations(
                hospital_id=filter_hospital
            )
        except Exception as error:
            st.error(f"Failed to load X-ray queue: {error}")
            pending = []

        grouped = group_xray_by_patient(pending)

        render_metrics(grouped)

        st.divider()

        render_xray_queue(grouped)