
import streamlit as st

from datetime import datetime, timezone

from backend.fetches import (
    get_pending_xray_examinations,
    get_xray_request_by_examination,
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
QUEUE_HEADERS = [
    "Patient",
    "Body part",
    "Priority",
    "Waiting",
    "",
]

# ------------------------------------------------------------
# Navigation
# ------------------------------------------------------------

ANALYZE_PAGE_LABEL = "Analyze X-Ray"


# ============================================================
# USER HELPERS
# ============================================================

def current_role_id():
    return (
        st.session_state.get("user") or {}
    ).get("role_id")


def current_hospital_id():
    return (
        st.session_state.get("user") or {}
    ).get("hospital_id")


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
    )


# ============================================================
# DATE / TIME HELPERS
# ============================================================

def waiting_minutes(requested_at):
    """
    Calculate elapsed minutes since the X-ray
    request was created.

    IMPORTANT:
    This uses xray_requests.requested_at,
    not examinations.created_at.
    """

    if not requested_at:
        return None

    try:
        if isinstance(requested_at, datetime):
            requested = requested_at
        else:
            requested = datetime.fromisoformat(
                str(requested_at).replace(
                    "Z",
                    "+00:00",
                )
            )

        if requested.tzinfo is None:
            requested = requested.replace(
                tzinfo=timezone.utc
            )

        now = datetime.now(timezone.utc)

        elapsed = (
            now - requested.astimezone(timezone.utc)
        ).total_seconds()

        return max(
            0,
            int(elapsed // 60),
        )

    except (ValueError, TypeError):
        return None


def waiting_tone(minutes):
    """
    Determine the color of the waiting badge.
    """

    if minutes is None:
        return "slate"

    if minutes < 10:
        return "green"

    if minutes < 30:
        return "amber"

    return "red"


def format_waiting(minutes):
    """
    Format elapsed waiting time.

    Examples:
        5 min
        45 min
        1h 30m
        23h 15m
        1d 3h 20m
        2d 5h 10m
    """

    if minutes is None:
        return "—"

    minutes = max(0, int(minutes))

    days = minutes // 1440
    hours = (minutes % 1440) // 60
    remaining_minutes = minutes % 60

    if days > 0:
        return (
            f"{days}d "
            f"{hours}h "
            f"{remaining_minutes}m"
        )

    if hours > 0:
        return (
            f"{hours}h "
            f"{remaining_minutes}m"
        )

    return f"{remaining_minutes} min"


# ============================================================
# X-RAY REQUEST HELPERS
# ============================================================

def get_request_for_examination(examination_id):
    """
    Retrieve the latest X-ray request associated
    with the given examination.

    The existing backend function retrieves
    requests ordered by requested_at DESC.
    """

    if not examination_id:
        return None

    try:
        return get_xray_request_by_examination(
            examination_id
        )

    except Exception as error:
        print(
            "Failed to retrieve X-ray request "
            f"for examination {examination_id}: "
            f"{error}"
        )

        return None


# ============================================================
# NAVIGATION HANDOFF
# ============================================================

def open_analyze_for(examination, patient):
    """
    Store the selected examination and patient,
    then navigate to the Analyze X-Ray page.

    Preserve the existing navigation behavior.
    """

    # Selected patient context
    st.session_state[
        "radtech_active_examination"
    ] = examination

    st.session_state[
        "radtech_active_patient"
    ] = patient

    # Clear stale analysis state
    st.session_state.pop(
        "radtech_analysis_result",
        None,
    )

    st.session_state.pop(
        "rx_upload",
        None,
    )

    # Navigate to Analyze X-Ray
    st.session_state.current_page = (
        ANALYZE_PAGE_LABEL
    )

    st.rerun()


# ============================================================
# GROUPING — USE X-RAY REQUEST TIMESTAMP
# ============================================================

def group_xray_by_patient(pending):
    """
    Prepare X-ray queue records.

    Waiting time is calculated using the actual
    X-ray request timestamp rather than the
    initial examination creation timestamp.
    """

    grouped = []

    for exam in pending:

        patient = exam.get("patients") or {}

        if isinstance(patient, list):
            patient = (
                patient[0]
                if patient
                else {}
            )

        if not patient.get("patient_id"):
            continue

        examination_id = exam.get(
            "examination_id"
        )

        if not examination_id:
            continue

        # ----------------------------------------
        # Retrieve associated X-ray request
        # ----------------------------------------

        request = get_request_for_examination(
            examination_id
        )

        # ----------------------------------------
        # Actual X-ray request timestamp
        # ----------------------------------------

        requested_at = (
            request.get("requested_at")
            if request
            else None
        )

        # Do not fall back to examination.created_at.
        # It represents a different clinical event.

        waiting = waiting_minutes(
            requested_at
        )

        # ----------------------------------------
        # Prepare queue entry
        # ----------------------------------------

        grouped.append({
            "patient": patient,
            "exam": exam,
            "request": request,
            "requested_at": requested_at,
            "waiting": waiting,
        })

    # --------------------------------------------
    # Sort by longest waiting first
    # Missing timestamps go to the bottom.
    # --------------------------------------------

    grouped.sort(
        key=lambda item: (
            item["waiting"] is not None,
            item["waiting"]
            if item["waiting"] is not None
            else -1,
        ),
        reverse=True,
    )

    return grouped


# ============================================================
# TABLE
# ============================================================

def render_xray_queue(grouped):

    if not grouped:
        empty_state(
            "No X-ray requests at the moment."
        )
        return

    with st.container(
        key="sa_table_xray_queue"
    ):

        table_header(
            QUEUE_HEADERS,
            QUEUE_WIDTHS,
            "xray_queue",
        )

        for item in grouped:

            patient = item["patient"]
            exam = item["exam"]
            request = item.get("request")
            waiting = item.get("waiting")

            exam_id = exam.get(
                "examination_id"
            )

            with table_row(
                f"xray_{exam_id}",
                QUEUE_WIDTHS,
            ) as cols:

                # --------------------------------
                # Patient
                # --------------------------------

                name_cell(
                    cols[0],
                    patient_name(patient),
                    sub=patient_code(patient),
                )

                # --------------------------------
                # Body part
                # --------------------------------

                body_part = (
                    request.get("body_part")
                    if request
                    else None
                ) or "Chest"

                text_cell(
                    cols[1],
                    body_part,
                )

                # --------------------------------
                # Priority
                # --------------------------------

                priority = (
                    request.get("priority")
                    if request
                    else None
                ) or "Routine"

                priority_normalized = (
                    str(priority).strip().lower()
                )

                if priority_normalized in (
                    "urgent",
                    "stat",
                    "emergency",
                ):
                    priority_tone = "red"

                elif priority_normalized in (
                    "high",
                    "priority",
                ):
                    priority_tone = "amber"

                else:
                    priority_tone = "blue"

                pill_cell(
                    cols[2],
                    str(priority),
                    priority_tone,
                )

                # --------------------------------
                # Waiting
                # --------------------------------

                if waiting is not None:

                    pill_cell(
                        cols[3],
                        format_waiting(waiting),
                        waiting_tone(waiting),
                    )

                else:

                    text_cell(
                        cols[3],
                        "—",
                    )

                # --------------------------------
                # Analyze action
                # --------------------------------

                if cols[4].button(
                    "Analyze",
                    key=f"analyze_{exam_id}",
                    icon=":material/radiology:",
                    type="primary",
                    width="stretch",
                ):

                    open_analyze_for(
                        exam,
                        patient,
                    )


# ============================================================
# METRICS
# ============================================================

def render_metrics(grouped):
    """
    Display X-ray queue metrics.

    All waiting durations use the X-ray
    request timestamp.
    """

    total = len(grouped)

    # Exclude records with missing timestamps.
    valid_waits = [
        item["waiting"]
        for item in grouped
        if item["waiting"] is not None
    ]

    if valid_waits:

        longest = max(
            valid_waits
        )

        average = (
            sum(valid_waits)
            // len(valid_waits)
        )

    else:

        longest = None
        average = None

    m1, m2, m3 = st.columns(3)

    # --------------------------------------------
    # X-rays waiting
    # --------------------------------------------

    with m1:

        metric_card(
            "X-Rays waiting",
            total,
            "radiology",
            tone="blue",
        )

    # --------------------------------------------
    # Longest wait
    # --------------------------------------------

    with m2:

        metric_card(
            "Longest wait",
            format_waiting(longest),
            "schedule",
            tone="red",
        )

    # --------------------------------------------
    # Average wait
    # --------------------------------------------

    with m3:

        metric_card(
            "Average wait",
            format_waiting(average),
            "timer",
            tone="green",
        )


# ============================================================
# PAGE
# ============================================================

def show():

    # Preserve existing page styling
    load_css(
        "manage_examinations.css"
    )

    show_flash_message()

    role_id = current_role_id()
    hospital_id = current_hospital_id()

    # --------------------------------------------
    # Role-based hospital filtering
    # --------------------------------------------

    if role_id == ROLE_SUPERADMIN:

        filter_hospital = None

    elif role_id in RADTECH_ROLES:

        filter_hospital = hospital_id

    else:

        st.error(
            "You don't have access to "
            "the X-ray queue."
        )
        return

    # --------------------------------------------
    # Main page
    # --------------------------------------------

    with st.container(
        key="sa_page"
    ):

        page_header(
            "X-Ray Queue",
            "Pending X-ray requests awaiting imaging. "
            "Pick a patient to analyze their X-Ray.",
        )

        # ----------------------------------------
        # Fetch pending examinations
        # ----------------------------------------

        try:

            pending = (
                get_pending_xray_examinations(
                    hospital_id=filter_hospital
                )
            )

        except Exception as error:

            st.error(
                "Failed to load X-ray queue: "
                f"{error}"
            )

            pending = []

        # ----------------------------------------
        # Build queue using request timestamps
        # ----------------------------------------

        grouped = group_xray_by_patient(
            pending
        )

        # ----------------------------------------
        # Metrics
        # ----------------------------------------

        render_metrics(
            grouped
        )

        st.divider()

        # ----------------------------------------
        # X-ray queue table
        # ----------------------------------------

        render_xray_queue(
            grouped
        )
