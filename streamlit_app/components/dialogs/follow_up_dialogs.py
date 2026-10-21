# streamlit_app/components/dialogs/follow_up_dialogs.py

"""
Shared physician follow-up dialogs.

Used by:
    streamlit_app/pages/physician/followups.py
    (and any future staff/physician page)

Provides:
    show_follow_up_details_dialog(fu)  -> combined details + actions
    show_reschedule_dialog(fu)
    show_cancel_dialog(fu)
    show_missed_dialog(fu)

The physician does NOT create follow-up examinations here.
Reception staff handle check-in via mark_follow_up_arrived(),
which creates the examination and completes the follow-up.
"""

import streamlit as st

from datetime import date, datetime, time as time_cls

from backend.backend_utils.followup_utils import (
    get_follow_up,
    reschedule_follow_up,
    cancel_follow_up,
    update_follow_up_status,
)

from streamlit_app.components.ui import (
    section_title,
    show_rows,
    full_name,
    pill,
    empty_state,
    remember,
)


ACTIVE_STATUSES = ["Scheduled", "Rescheduled"]


# ============================================================
# HELPERS
# ============================================================

def _patient(fu):
    patient = (fu or {}).get("patients") or {}
    if isinstance(patient, list):
        return patient[0] if patient else {}
    return patient


def _source_exam(fu):
    exam = (fu or {}).get("source_examination") or {}
    if isinstance(exam, list):
        return exam[0] if exam else {}
    return exam


def _follow_up_exam(fu):
    exam = (fu or {}).get("follow_up_examination") or {}
    if isinstance(exam, list):
        return exam[0] if exam else {}
    return exam


def _patient_name(patient):
    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )


def _patient_code(patient):
    return patient.get("patient_code") or patient.get("patient_id") or "—"


def _status(fu):
    return (fu or {}).get("status") or "Scheduled"


def _status_tone(status):
    return {
        "Scheduled": "blue",
        "Rescheduled": "amber",
        "Completed": "green",
        "Missed": "red",
        "Cancelled": "red",
    }.get(status, "grey")


def _format_date(value):
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


def _format_time(value):
    if not value:
        return "—"
    try:
        if isinstance(value, time_cls):
            return value.strftime("%I:%M %p")
        return datetime.strptime(str(value)[:8], "%H:%M:%S").strftime("%I:%M %p")
    except Exception:
        return str(value)


def _format_appointment(fu):
    return (
        f"{_format_date((fu or {}).get('follow_up_date'))} "
        f"at {_format_time((fu or {}).get('follow_up_time'))}"
    )


def _format_exam_date(exam):
    return _format_date((exam or {}).get("examination_date"))


def _show_rows_with_pill(rows, pill_values):
    """
    Render label/value rows, but inject pill HTML for specific rows
    instead of letting show_rows() escape it.

    rows        : list of (label, value)
    pill_values : dict mapping row index -> (pill_text, tone)
    """
    items = []
    for index, (label, value) in enumerate(rows):
        if index in pill_values:
            pill_text, tone = pill_values[index]
            items.append(
                f"<div class='sa-row'><span>{label}</span>"
                f"<b>{pill(pill_text, tone)}</b></div>"
            )
        else:
            safe_value = str(value) if value not in (None, "") else "—"
            items.append(
                f"<div class='sa-row'><span>{label}</span>"
                f"<b>{safe_value}</b></div>"
            )
    st.markdown(f"<div class='sa-rows'>{''.join(items)}</div>", unsafe_allow_html=True)


# ============================================================
# DETAILS DIALOG (combined parent + previous + exam + actions)
# ============================================================

@st.dialog("Follow-Up Details", width="large")
def show_follow_up_details_dialog(fu):

    if not fu:
        st.error("Follow-up not found.")
        return

    fu_id = fu.get("follow_up_id")
    patient = _patient(fu)
    source = _source_exam(fu)
    linked = _follow_up_exam(fu)
    status = _status(fu)
    linked_status = (linked or {}).get("status") if linked else None
    is_active = status in ACTIVE_STATUSES
    has_linked_exam = bool(linked and linked.get("examination_id"))

    # ---------- Follow-Up summary ----------
    section_title("Follow-Up")

    _show_rows_with_pill(
        rows=[
            ("Code", fu.get("follow_up_code") or "—"),
            ("Patient", _patient_name(patient)),
            ("Patient ID", _patient_code(patient)),
            ("Scheduled", _format_appointment(fu)),
            ("Status", status),
            ("Notes", fu.get("notes") or "—"),
        ],
        pill_values={
            4: (status, _status_tone(status)),
        },
    )

    # ---------- Parent consult ----------
    st.divider()
    section_title("Parent Consult")

    if source and source.get("examination_id"):
        source_status = source.get("status") or "—"
        _show_rows_with_pill(
            rows=[
                ("Type", source.get("examination_type") or "General Consult"),
                ("Date", _format_exam_date(source)),
                ("Diagnosis", source.get("diagnosis") or "—"),
                ("Status", source_status),
            ],
            pill_values={
                3: (
                    source_status,
                    "green" if source_status == "Completed" else "amber",
                ),
            },
        )
    else:
        empty_state("No parent consultation linked to this follow-up.")

    # ---------- Previous follow-up ----------
    st.divider()
    section_title("Previous Follow-Up")

    prev_id = fu.get("previous_follow_up_id")
    prev_fu = None

    if prev_id:
        try:
            prev_fu = get_follow_up(prev_id)
        except Exception:
            prev_fu = None

    if prev_fu:
        prev_status = _status(prev_fu)
        _show_rows_with_pill(
            rows=[
                ("Code", prev_fu.get("follow_up_code") or "—"),
                ("Scheduled", _format_appointment(prev_fu)),
                ("Status", prev_status),
            ],
            pill_values={
                2: (prev_status, _status_tone(prev_status)),
            },
        )
    else:
        empty_state("This is the first follow-up in the chain.")

    # ---------- Follow-up examination ----------
    st.divider()
    section_title("Follow-Up Examination")

    if has_linked_exam:
        linked_label = linked_status or "Pending"
        linked_tone = "green" if linked_status == "Completed" else "amber"
        _show_rows_with_pill(
            rows=[
                ("Type", linked.get("examination_type") or "Follow-Up Examination"),
                ("Date", _format_exam_date(linked)),
                ("Diagnosis", linked.get("diagnosis") or "—"),
                ("Status", linked_label),
            ],
            pill_values={
                3: (linked_label, linked_tone),
            },
        )
    else:
        st.info(
            "No follow-up examination has been created yet. "
            "Reception staff will create the examination when "
            "the patient arrives at the hospital."
        )

    # ---------- Actions ----------
    st.divider()

    if not is_active:
        st.caption("This follow-up is closed. Only details are available.")
        if st.button(
            "Close",
            key=f"pf_fu_close_{fu_id}",
            width="stretch",
        ):
            st.session_state.pop("follow_up_details_id", None)
            st.rerun()
        return

    can_mark_missed = not has_linked_exam

    col_resched, col_cancel, col_missed = st.columns(3)

    if col_resched.button(
        "Reschedule",
        key=f"pf_fu_resched_open_{fu_id}",
        icon=":material/event_repeat:",
        width="stretch",
    ):
        st.session_state["follow_up_details_id"] = None
        st.session_state["reschedule_follow_up_id"] = fu_id
        st.rerun()

    if col_cancel.button(
        "Cancel",
        key=f"pf_fu_cancel_open_{fu_id}",
        icon=":material/cancel:",
        width="stretch",
    ):
        st.session_state["follow_up_details_id"] = None
        st.session_state["cancel_follow_up_id"] = fu_id
        st.rerun()

    if col_missed.button(
        "Mark Missed",
        key=f"pf_fu_missed_open_{fu_id}",
        icon=":material/schedule:",
        width="stretch",
        disabled=not can_mark_missed,
    ):
        st.session_state["follow_up_details_id"] = None
        st.session_state["missed_follow_up_id"] = fu_id
        st.rerun()

    if not can_mark_missed:
        st.caption(
            "Mark Missed is unavailable because an examination "
            "has already been created for this follow-up."
        )

    st.divider()

    if st.button(
        "Close",
        key=f"pf_fu_close_active_{fu_id}",
        width="stretch",
    ):
        st.session_state.pop("follow_up_details_id", None)
        st.rerun()


# ============================================================
# RESCHEDULE DIALOG
# ============================================================

@st.dialog("Reschedule Follow-Up", width="medium")
def show_reschedule_dialog(fu):

    if not fu:
        st.error("Follow-up not found.")
        return

    fu_id = fu.get("follow_up_id")
    patient = _patient(fu)

    try:
        default_date = date.fromisoformat(str(fu.get("follow_up_date"))[:10])
    except Exception:
        default_date = date.today()

    if default_date < date.today():
        default_date = date.today()

    try:
        default_time = time_cls.fromisoformat(str(fu.get("follow_up_time"))[:8])
    except Exception:
        default_time = time_cls(9, 0)

    st.markdown(
        f"**{fu.get('follow_up_code') or 'Follow-Up'}** • "
        f"{_patient_name(patient)}"
    )

    st.divider()

    new_date = st.date_input(
        "New Follow-Up Date",
        value=default_date,
        min_value=date.today(),
        key=f"pf_fu_resched_date_{fu_id}",
    )

    new_time = st.time_input(
        "New Follow-Up Time",
        value=default_time,
        key=f"pf_fu_resched_time_{fu_id}",
    )

    st.divider()

    col_cancel, col_save = st.columns(2)

    if col_cancel.button(
        "Cancel",
        key=f"pf_fu_resched_cancel_{fu_id}",
        width="stretch",
    ):
        st.session_state.pop("reschedule_follow_up_id", None)
        st.rerun()

    if col_save.button(
        "Save Schedule",
        key=f"pf_fu_resched_save_{fu_id}",
        type="primary",
        width="stretch",
    ):
        result = reschedule_follow_up(
            fu_id,
            new_date,
            new_time.strftime("%H:%M:%S"),
        )
        if result.get("success"):
            st.session_state.pop("reschedule_follow_up_id", None)
            remember("Follow-up rescheduled.")
            st.rerun()
        else:
            st.error(result.get("message", "Failed to reschedule."))


# ============================================================
# CANCEL DIALOG
# ============================================================

@st.dialog("Cancel Follow-Up", width="small")
def show_cancel_dialog(fu):

    if not fu:
        st.error("Follow-up not found.")
        return

    fu_id = fu.get("follow_up_id")
    patient = _patient(fu)

    st.warning("Cancel this follow-up? This cannot be undone from here.")

    show_rows([
        ("Patient", _patient_name(patient)),
        ("Scheduled", _format_appointment(fu)),
    ])

    st.divider()

    col_keep, col_cancel = st.columns(2)

    if col_keep.button(
        "Keep Follow-Up",
        key=f"pf_fu_cancel_keep_{fu_id}",
        width="stretch",
    ):
        st.session_state.pop("cancel_follow_up_id", None)
        st.rerun()

    if col_cancel.button(
        "Yes, Cancel",
        key=f"pf_fu_cancel_confirm_{fu_id}",
        type="primary",
        width="stretch",
    ):
        result = cancel_follow_up(fu_id)
        if result.get("success"):
            st.session_state.pop("cancel_follow_up_id", None)
            remember("Follow-up cancelled.")
            st.rerun()
        else:
            st.error(result.get("message", "Failed to cancel."))


# ============================================================
# MARK MISSED DIALOG
# ============================================================

@st.dialog("Mark Follow-Up Missed", width="small")
def show_missed_dialog(fu):

    if not fu:
        st.error("Follow-up not found.")
        return

    fu_id = fu.get("follow_up_id")
    patient = _patient(fu)

    st.warning("Mark this follow-up as missed?")

    show_rows([
        ("Patient", _patient_name(patient)),
        ("Scheduled", _format_appointment(fu)),
    ])

    st.divider()

    col_cancel, col_missed = st.columns(2)

    if col_cancel.button(
        "Cancel",
        key=f"pf_fu_missed_cancel_{fu_id}",
        width="stretch",
    ):
        st.session_state.pop("missed_follow_up_id", None)
        st.rerun()

    if col_missed.button(
        "Mark Missed",
        key=f"pf_fu_missed_confirm_{fu_id}",
        type="primary",
        width="stretch",
    ):
        result = update_follow_up_status(fu_id, "Missed")
        if result.get("success"):
            st.session_state.pop("missed_follow_up_id", None)
            remember("Follow-up marked as missed.")
            st.rerun()
        else:
            st.error(result.get("message", "Failed to update follow-up."))