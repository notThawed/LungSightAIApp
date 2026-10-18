# streamlit_app/pages/physician/followups.py

"""
Physician — Follow-Ups.

Single source of truth for all physician follow-up logic.

Landing view (GROUPED BY PATIENT):
    - KPI strip (Total · Scheduled · Completed · Missed)
    - Search by FU code OR patient name
    - Status filter (default = Scheduled = active only)
    - Paginated table: FU ID | Patient | Next Follow-Up | Status | Action
      One row per PATIENT (not per follow-up).
      Shows the patient's next active follow-up, plus a
      "N follow-ups" badge if the patient has more.

Drill-in view (click patient name):
    - Patient summary card
    - Upcoming follow-ups
    - Follow-up history

Actions route through shared dialogs in:
    streamlit_app/components/dialogs/follow_up_dialogs.py
"""

import streamlit as st

from datetime import date, datetime, time as time_cls

from backend.backend_utils.followup_utils import (
    get_hospital_follow_ups,
    get_follow_up,
    get_follow_up_counts,
    get_upcoming_follow_ups_by_patient,
    get_follow_up_history,
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
    kpi_strip,
    patient_summary_card,
    table_header,
    table_row,
    name_cell,
    text_cell,
    pill_cell,
)

from streamlit_app.components.dialogs.follow_up_dialogs import (
    show_follow_up_details_dialog,
    show_reschedule_dialog,
    show_cancel_dialog,
    show_missed_dialog,
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

ACTIVE_STATUSES = ["Scheduled", "Rescheduled"]
STATUS_FILTER_OPTIONS = [
    "Scheduled",
    "Rescheduled",
    "Completed",
    "Missed",
    "Cancelled",
    "All",
]
DEFAULT_STATUS_FILTER = "Scheduled"

PAGE_SIZE = 10


# ============================================================
# TABLE CONFIG
# ============================================================

FOLLOWUP_WIDTHS = [1.8, 2.6, 2, 1.2, 1]
FOLLOWUP_HEADERS = ["FU ID", "Patient", "Next Follow-Up", "Status", "Action"]


# ============================================================
# HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}


def current_role_id():
    return current_user().get("role_id")


def current_hospital_id():
    return current_user().get("hospital_id")


def patient_of(fu):
    patient = (fu or {}).get("patients") or {}
    if isinstance(patient, list):
        return patient[0] if patient else {}
    return patient


def patient_name(patient):
    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )


def patient_code(patient):
    return patient.get("patient_code") or patient.get("patient_id") or "—"


def format_date_only(value):
    if not value:
        return "—"
    try:
        if isinstance(value, datetime):
            return value.strftime("%B %d, %Y")
        if isinstance(value, date):
            return value.strftime("%B %d, %Y")
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime("%B %d, %Y")
    except Exception:
        return str(value)


def format_time_only(value):
    if not value:
        return "—"
    try:
        if isinstance(value, time_cls):
            return value.strftime("%I:%M %p")
        return datetime.strptime(str(value)[:8], "%H:%M:%S").strftime("%I:%M %p")
    except Exception:
        return str(value)


def format_appointment(fu):
    return (
        f"{format_date_only(fu.get('follow_up_date'))} · "
        f"{format_time_only(fu.get('follow_up_time'))}"
    )


def status_tone(status):
    return {
        "Scheduled": "blue",
        "Rescheduled": "amber",
        "Completed": "green",
        "Missed": "red",
        "Cancelled": "red",
    }.get(status or "", "grey")


def sort_key_follow_up(fu):
    d = fu.get("follow_up_date")
    t = fu.get("follow_up_time")
    try:
        d_str = str(d)[:10] if d else "9999-12-31"
    except Exception:
        d_str = "9999-12-31"
    try:
        t_str = str(t)[:8] if t else "00:00:00"
    except Exception:
        t_str = "00:00:00"
    return (d_str, t_str)


def reset_pagination():
    st.session_state["pf_fu_page"] = 1


def clear_follow_up_state():
    for key in (
        "pf_fu_selected_patient_id",
        "follow_up_details_id",
        "reschedule_follow_up_id",
        "cancel_follow_up_id",
        "missed_follow_up_id",
        "physician_parent_view",
        "physician_prev_fu_view",
        "pf_fu_page",
        "pf_fu_query",
        "pf_fu_status_filter",
    ):
        st.session_state.pop(key, None)


def go_to_patient(patient_id):
    st.session_state["pf_fu_selected_patient_id"] = patient_id
    st.rerun()


def back_to_landing():
    st.session_state.pop("pf_fu_selected_patient_id", None)
    st.rerun()


# ============================================================
# GROUPING (one row per patient)
# ============================================================

def group_follow_ups_by_patient(follow_ups, status_filter):

    """
    Group follow-ups into one entry per patient.

    - If status_filter is "All", every follow-up counts.
    - Otherwise only follow-ups matching that status count.

    For each patient:
        {
            "patient": {...},
            "follow_ups": [...],        # sorted by date asc
            "next_follow_up": {...},    # earliest in list
            "has_rescheduled": bool,    # any Rescheduled in list
        }

    Patients are sorted by their next_follow_up date (asc),
    so the most imminent follow-up appears first.
    """

    filtered = follow_ups
    if status_filter != "All":
        filtered = [
            fu for fu in follow_ups
            if (fu.get("status") or "Scheduled") == status_filter
        ]

    by_patient = {}

    for fu in filtered:
        patient = patient_of(fu)
        patient_id = patient.get("patient_id")
        if not patient_id:
            continue

        if patient_id not in by_patient:
            by_patient[patient_id] = {
                "patient": patient,
                "follow_ups": [],
                "has_rescheduled": False,
            }

        by_patient[patient_id]["follow_ups"].append(fu)

        if (fu.get("status") or "") == "Rescheduled":
            by_patient[patient_id]["has_rescheduled"] = True

    entries = list(by_patient.values())

    for entry in entries:
        entry["follow_ups"].sort(key=sort_key_follow_up)
        entry["next_follow_up"] = entry["follow_ups"][0]

    entries.sort(key=lambda item: sort_key_follow_up(item["next_follow_up"]))

    return entries


def apply_search(entries, query):
    if not query:
        return entries

    q = query.strip().lower()
    results = []

    for entry in entries:
        patient = entry["patient"]
        name = patient_name(patient).lower()
        # Also match any FU code within this patient's group
        codes = [
            (fu.get("follow_up_code") or "").lower()
            for fu in entry["follow_ups"]
        ]
        if q in name or any(q in code for code in codes):
            results.append(entry)

    return results


# ============================================================
# LANDING — KPI STRIP
# ============================================================

def render_kpi_strip(hospital_id):

    counts = get_follow_up_counts(hospital_id=hospital_id) or {}

    kpi_strip([
        ("Total", counts.get("total", 0), "blue"),
        ("Scheduled", counts.get("scheduled", 0), "amber"),
        ("Completed", counts.get("completed", 0), "green"),
        ("Missed", counts.get("missed", 0), "red"),
    ])


# ============================================================
# LANDING — FILTER BAR
# ============================================================

def render_filter_bar():

    st.markdown("<div class='pf-filter-row'>", unsafe_allow_html=True)

    col_search, col_status = st.columns([3, 1])

    with col_search:
        query = st.text_input(
            "Search",
            value=st.session_state.get("pf_fu_query", ""),
            placeholder="Search by FU ID or patient name",
            label_visibility="collapsed",
            key="pf_fu_query",
        )

    with col_status:
        current = st.session_state.get("pf_fu_status_filter", DEFAULT_STATUS_FILTER)
        if current not in STATUS_FILTER_OPTIONS:
            current = DEFAULT_STATUS_FILTER

        status = st.selectbox(
            "Status",
            STATUS_FILTER_OPTIONS,
            index=STATUS_FILTER_OPTIONS.index(current),
            label_visibility="collapsed",
            key="pf_fu_status_filter",
        )

    st.markdown("</div>", unsafe_allow_html=True)

    return query, status


# ============================================================
# LANDING — TABLE
# ============================================================

def render_table(entries, page):

    if not entries:
        empty_state("No patients match the current filters.")
        return

    total = len(entries)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(page, 1), total_pages)

    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_entries = entries[start:end]

    with st.container(key="pf_fu_table"):

        table_header(FOLLOWUP_HEADERS, FOLLOWUP_WIDTHS, "pf_fu")

        for entry in page_entries:

            patient = entry["patient"]
            patient_id = patient.get("patient_id")
            next_fu = entry["next_follow_up"]
            fu_count = len(entry["follow_ups"])

            next_code = next_fu.get("follow_up_code") or "—"
            next_status = next_fu.get("status") or "Scheduled"

            if entry["has_rescheduled"]:
                status_label = "Rescheduled"
                tone = "amber"
            else:
                status_label = next_status
                tone = status_tone(next_status)

            if fu_count > 1:
                code_display = f"{next_code} (+{fu_count - 1})"
            else:
                code_display = next_code

            patient_sub = patient_code(patient)
            if fu_count > 1:
                patient_sub = f"{patient_sub} · {fu_count} follow-ups"

            with table_row(f"pf_fu_row_{patient_id}", FOLLOWUP_WIDTHS) as columns:

                text_cell(columns[0], code_display, strong=True)

                # Patient name — clickable link styled via CSS
                with columns[1]:
                    st.markdown("<div class='pf-link-cell'>", unsafe_allow_html=True)
                    if st.button(
                        patient_name(patient) or "—",
                        key=f"pf_fu_patient_{patient_id}",
                        type="tertiary",
                    ):
                        go_to_patient(patient_id)
                    st.markdown(
                        f"<small class='sa-cell-sub'>{patient_sub}</small>",
                        unsafe_allow_html=True,
                    )
                    st.markdown("</div>", unsafe_allow_html=True)

                text_cell(columns[2], format_appointment(next_fu))
                pill_cell(columns[3], status_label, tone)

                if columns[4].button(
                    "View",
                    key=f"pf_fu_view_{patient_id}",
                    icon=":material/visibility:",
                    type="primary",
                    width="stretch",
                ):
                    st.session_state["follow_up_details_id"] = next_fu.get(
                        "follow_up_id"
                    )
                    st.rerun()

    render_pagination(page, total_pages, total, start, end)


def render_pagination(page, total_pages, total, start, end):

    st.markdown("<div class='pf-pagination-row'>", unsafe_allow_html=True)

    col_prev, col_info, col_next = st.columns([1, 3, 1])

    with col_prev:
        if st.button(
            "Previous",
            icon=":material/arrow_back:",
            key="pf_fu_prev",
            disabled=(page <= 1),
            width="stretch",
        ):
            st.session_state["pf_fu_page"] = page - 1
            st.rerun()

    with col_info:
        st.markdown(
            f"<div class='pf-pagination-info'>"
            f"Showing {start + 1}–{min(end, total)} of {total} patients"
            f" · Page {page} of {total_pages}"
            f"</div>",
            unsafe_allow_html=True,
        )

    with col_next:
        if st.button(
            "Next",
            icon=":material/arrow_forward:",
            key="pf_fu_next",
            disabled=(page >= total_pages),
            width="stretch",
        ):
            st.session_state["pf_fu_page"] = page + 1
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# LANDING VIEW
# ============================================================

def render_landing(hospital_id):

    render_kpi_strip(hospital_id)

    query, status = render_filter_bar()

    try:
        all_follow_ups = get_hospital_follow_ups(hospital_id=hospital_id) or []
    except Exception as error:
        st.error(f"Failed to load follow-ups: {error}")
        all_follow_ups = []

    entries = group_follow_ups_by_patient(all_follow_ups, status)
    entries = apply_search(entries, query)

    # Reset page when filter/search changes
    last_query = st.session_state.get("_pf_fu_last_query", "")
    last_status = st.session_state.get("_pf_fu_last_status", DEFAULT_STATUS_FILTER)

    if last_query != query or last_status != status:
        reset_pagination()
        st.session_state["_pf_fu_last_query"] = query
        st.session_state["_pf_fu_last_status"] = status

    page = st.session_state.get("pf_fu_page", 1)
    render_table(entries, page)


# ============================================================
# DRILL-IN VIEW
# ============================================================

@st.dialog("Parent General Consult", width="medium")
def show_parent_consult_dialog(exam):

    if not exam:
        st.error("No consultation data.")
        return

    section_title(exam.get("examination_type") or "General Consult")

    show_rows([
        ("Date", format_date_only(exam.get("examination_date"))),
        ("Status", exam.get("status") or "—"),
        ("Chief Complaint", exam.get("chief_complaint") or "—"),
        ("HPI", exam.get("history_of_present_illness") or "—"),
        ("Physical Exam", exam.get("physical_examination") or "—"),
        ("Diagnosis", exam.get("diagnosis") or "—"),
        ("Plans / Orders", exam.get("plans_orders") or "—"),
        ("Disposition", exam.get("disposition") or "—"),
    ])

    st.divider()

    if st.button(
        "Close",
        key="pf_parent_close",
        width="stretch",
    ):
        st.session_state.pop("physician_parent_view", None)
        st.rerun()


@st.dialog("Previous Follow-Up", width="medium")
def show_previous_follow_up_dialog(fu):

    if not fu:
        st.error("No previous follow-up data.")
        return

    section_title(fu.get("follow_up_code") or "Previous Follow-Up")

    show_rows([
        ("Scheduled", format_appointment(fu)),
        ("Status", fu.get("status") or "—"),
        ("Notes", fu.get("notes") or "—"),
    ])

    linked = (fu.get("follow_up_examination") or {})
    if isinstance(linked, list):
        linked = linked[0] if linked else {}

    if linked and linked.get("examination_id"):
        st.divider()
        section_title("Examination")
        show_rows([
            ("Examination", linked.get("examination_type") or "—"),
            ("Date", format_date_only(linked.get("examination_date"))),
            ("Diagnosis", linked.get("diagnosis") or "—"),
            ("Status", linked.get("status") or "—"),
        ])

    st.divider()

    if st.button(
        "Close",
        key="pf_prev_fu_close",
        width="stretch",
    ):
        st.session_state.pop("physician_prev_fu_view", None)
        st.rerun()


def render_follow_up_card(fu, patient):

    fu_id = fu.get("follow_up_id")
    code = fu.get("follow_up_code") or "—"
    status = fu.get("status") or "Scheduled"

    prev_id = fu.get("previous_follow_up_id")
    prev_fu = None
    if prev_id:
        try:
            prev_fu = get_follow_up(prev_id)
        except Exception:
            prev_fu = None

    source_exam = fu.get("source_examination") or {}
    if isinstance(source_exam, list):
        source_exam = source_exam[0] if source_exam else {}

    with st.container(key=f"physician_fu_card_{fu_id}"):

        col_code, col_when, col_status = st.columns([1.4, 3, 1.2])

        with col_code:
            st.markdown(
                f"<div class='pf-fu-code'>{code}</div>",
                unsafe_allow_html=True,
            )

        with col_when:
            st.markdown(
                f"<div class='pf-fu-when'>{format_appointment(fu)}</div>",
                unsafe_allow_html=True,
            )

        with col_status:
            st.markdown(pill(status, status_tone(status)), unsafe_allow_html=True)

        if fu.get("notes"):
            st.markdown(
                f"<p class='pf-fu-notes'>{fu.get('notes')}</p>",
                unsafe_allow_html=True,
            )

        col_parent, col_prev, col_manage = st.columns([1, 1, 1])

        with col_parent:
            if source_exam:
                if st.button(
                    "See Parent Consult",
                    key=f"pf_fu_parent_{fu_id}",
                    icon=":material/arrow_forward:",
                    width="stretch",
                ):
                    st.session_state["physician_parent_view"] = source_exam
                    st.rerun()
            else:
                st.caption("No parent")

        with col_prev:
            if prev_fu:
                if st.button(
                    "See Previous Follow-Up",
                    key=f"pf_fu_prev_{fu_id}",
                    icon=":material/arrow_forward:",
                    width="stretch",
                ):
                    st.session_state["physician_prev_fu_view"] = prev_fu
                    st.rerun()
            else:
                st.caption("First follow-up")

        with col_manage:
            if st.button(
                "View",
                key=f"pf_fu_manage_{fu_id}",
                icon=":material/visibility:",
                type="primary",
                width="stretch",
            ):
                st.session_state["follow_up_details_id"] = fu_id
                st.rerun()


def render_patient_followups(patient, hospital_id):

    patient_id = patient.get("patient_id")

    if st.button(
        "Back to All Follow-Ups",
        icon=":material/arrow_back:",
        key="pf_fu_back",
    ):
        back_to_landing()

    patient_summary_card(
        patient,
        meta_rows=[
            ("Date of Birth", format_date(patient.get("date_of_birth"))),
            ("Sex", patient.get("sex") or "—"),
            ("Contact", patient.get("contact_number") or "—"),
        ],
    )

    upcoming = get_upcoming_follow_ups_by_patient(patient_id) or []

    section_title(
        "Upcoming Follow-Ups",
        caption=f"{len(upcoming)} active",
    )

    if not upcoming:
        empty_state("This patient has no upcoming follow-up visits.")
    else:
        for fu in upcoming:
            render_follow_up_card(fu, patient)

    history = get_follow_up_history(patient_id) or []

    section_title(
        "Follow-Up History",
        caption=f"{len(history)} record(s)",
    )

    if not history:
        empty_state("No previous follow-up history found for this patient.")
    else:
        for fu in history:
            render_follow_up_card(fu, patient)


# ============================================================
# PAGE
# ============================================================

def show():

    load_css("followups.css")
    show_flash_message()

    role_id = current_role_id()
    hospital_id = current_hospital_id()

    if role_id not in (DOCTOR_ROLES + ADMIN_ROLES):
        st.error("You don't have access to Follow-Ups.")
        return

    effective_hospital_id = None if role_id == ROLE_SUPERADMIN else hospital_id

    page_header(
        "Follow-Ups",
        "Manage patient follow-up visits across every stage of care.",
    )

    if st.button(
        "Refresh",
        icon=":material/refresh:",
        key="pf_fu_refresh",
        width="stretch",
    ):
        st.rerun()

    selected_patient_id = st.session_state.get("pf_fu_selected_patient_id")

    if selected_patient_id:
        try:
            all_follow_ups = get_hospital_follow_ups(hospital_id=effective_hospital_id) or []
            patient = None
            for fu in all_follow_ups:
                p = patient_of(fu)
                if p.get("patient_id") == selected_patient_id:
                    patient = p
                    break
            if patient:
                render_patient_followups(patient, effective_hospital_id)
            else:
                back_to_landing()
        except Exception as error:
            st.error(f"Failed to load patient: {error}")
            back_to_landing()
    else:
        render_landing(effective_hospital_id)

    # ----- Dialog dispatch -----
    if st.session_state.get("physician_parent_view"):
        show_parent_consult_dialog(st.session_state["physician_parent_view"])
        return

    if st.session_state.get("physician_prev_fu_view"):
        show_previous_follow_up_dialog(st.session_state["physician_prev_fu_view"])
        return

    if st.session_state.get("follow_up_details_id"):
        fu_id = st.session_state["follow_up_details_id"]
        try:
            fu = get_follow_up(fu_id)
            if fu:
                show_follow_up_details_dialog(fu)
            else:
                st.session_state.pop("follow_up_details_id", None)
                st.error("Follow-up not found.")
        except Exception as error:
            st.session_state.pop("follow_up_details_id", None)
            st.error(f"Failed to load follow-up: {error}")

    elif st.session_state.get("reschedule_follow_up_id"):
        fu_id = st.session_state["reschedule_follow_up_id"]
        try:
            fu = get_follow_up(fu_id)
            if fu:
                show_reschedule_dialog(fu)
            else:
                st.session_state.pop("reschedule_follow_up_id", None)
        except Exception as error:
            st.session_state.pop("reschedule_follow_up_id", None)
            st.error(f"Failed to load follow-up: {error}")

    elif st.session_state.get("cancel_follow_up_id"):
        fu_id = st.session_state["cancel_follow_up_id"]
        try:
            fu = get_follow_up(fu_id)
            if fu:
                show_cancel_dialog(fu)
            else:
                st.session_state.pop("cancel_follow_up_id", None)
        except Exception as error:
            st.session_state.pop("cancel_follow_up_id", None)
            st.error(f"Failed to load follow-up: {error}")

    elif st.session_state.get("missed_follow_up_id"):
        fu_id = st.session_state["missed_follow_up_id"]
        try:
            fu = get_follow_up(fu_id)
            if fu:
                show_missed_dialog(fu)
            else:
                st.session_state.pop("missed_follow_up_id", None)
        except Exception as error:
            st.session_state.pop("missed_follow_up_id", None)
            st.error(f"Failed to load follow-up: {error}")