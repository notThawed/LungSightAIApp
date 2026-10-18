# streamlit_app/components/dialogs/follow_up_dialogs.py

"""
Shared follow-up dialogs used by:
  - physician/followups.py
  - physician_patient_queue.py (kept minimal)

Includes:
  - show_follow_up_dialog(follow_up, patient)      (Details + actions)
  - show_details_dialog(follow_up, patient)        (Parent + Previous combined)
  - show_reschedule_dialog(follow_up)
  - show_cancel_dialog(follow_up)
  - show_missed_dialog(follow_up)

The "Start Follow-Up Examination" action has been removed.
Staff is responsible for arrival check-in.
"""

import streamlit as st

from datetime import date, datetime, time

from backend.backend_utils.followup_utils import (
    get_follow_up,
    reschedule_follow_up,
    cancel_follow_up,
    update_follow_up_status,
    complete_follow_up,
)

from streamlit_app.components.ui import (
    show_rows,
    full_name,
    pill,
    section_title,
    remember,
)


ACTIVE_FOLLOW_UP_STATUSES = ["Scheduled", "Rescheduled"]


# ============================================================
# HELPERS
# ============================================================

def _patient_name(patient):
    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )


def _patient_code(patient):
    return patient.get("patient_code") or patient.get("patient_id")


def _status_tone(status):
    s = str(status or "").strip().lower()
    return {
        "scheduled": "blue",
        "completed": "green",
        "missed": "red",
        "cancelled": "red",
        "rescheduled": "amber",
    }.get(s, "grey")


def _format_datetime(date_value, time_value=None):
    if not date_value:
        return "—"
    try:
        date_text = str(date_value)
        if date_text.endswith("Z"):
            date_text = date_text.replace("Z", "+00:00")
        if "T" in date_text:
            dt = datetime.fromisoformat(date_text)
            if dt.tzinfo is not None:
                dt = dt.astimezone()
            return dt.strftime("%B %d, %Y at %I:%M %p")

        date_obj = datetime.strptime(date_text[:10], "%Y-%m-%d")
        formatted_date = date_obj.strftime("%B %d, %Y")

        if time_value:
            time_text = str(time_value)
            try:
                t = datetime.strptime(time_text[:8], "%H:%M:%S")
                return f"{formatted_date} at {t.strftime('%I:%M %p')}"
            except Exception:
                try:
                    t = datetime.strptime(time_text[:5], "%H:%M")
                    return f"{formatted_date} at {t.strftime('%I:%M %p')}"
                except Exception:
                    return f"{formatted_date} at {time_text}"

        return formatted_date
    except Exception:
        return str(date_value)


def _follow_up_when(follow_up):
    return _format_datetime(
        follow_up.get("follow_up_date"),
        follow_up.get("follow_up_time"),
    )


def _source_exam(follow_up):
    ex = follow_up.get("source_examination") or {}
    if isinstance(ex, list):
        return ex[0] if ex else {}
    return ex


def _follow_up_exam(follow_up):
    ex = follow_up.get("follow_up_examination") or {}
    if isinstance(ex, list):
        return ex[0] if ex else {}
    return ex


# ============================================================
# DETAILS DIALOG (Parent + Previous combined)
# ============================================================

@st.dialog("Follow-Up Details", width="medium")
def show_details_dialog(follow_up, patient):

    fu_code = follow_up.get("follow_up_code") or "—"
    status = follow_up.get("status") or "Scheduled"
    source = _source_exam(follow_up)
    previous_id = follow_up.get("previous_follow_up_id")

    previous_fu = None
    if previous_id:
        try:
            previous_fu = get_follow_up(previous_id)
        except Exception:
            previous_fu = None

    section_title(f"Follow-Up {fu_code}")

    show_rows([
        ("Patient", _patient_name(patient)),
        ("Patient ID", _patient_code(patient)),
        ("Scheduled", _follow_up_when(follow_up)),
        ("Status", pill(status, _status_tone(status))),
        ("Notes", follow_up.get("notes") or "—"),
    ])

    # --------------------------------------------------------
    # Parent General Consult
    # --------------------------------------------------------

    st.divider()
    section_title("Parent General Consult")

    if source:
        show_rows([
            ("Examination", source.get("examination_type") or "—"),
            ("Date", _format_datetime(source.get("examination_date"))),
            ("Chief Complaint", source.get("chief_complaint") or "—"),
            ("Diagnosis", source.get("diagnosis") or "—"),
            ("Plans / Orders", source.get("plans_orders") or "—"),
            ("Disposition", source.get("disposition") or "—"),
        ])
    else:
        st.caption("No parent consultation linked.")

    # --------------------------------------------------------
    # Previous Follow-Up
    # --------------------------------------------------------

    st.divider()
    section_title("Previous Follow-Up")

    if previous_fu:
        prev_status = previous_fu.get("status") or "—"
        prev_exam = _follow_up_exam(previous_fu)

        show_rows([
            ("Code", previous_fu.get("follow_up_code") or "—"),
            ("Scheduled", _follow_up_when(previous_fu)),
            ("Status", pill(prev_status, _status_tone(prev_status))),
            ("Notes", previous_fu.get("notes") or "—"),
        ])

        if prev_exam:
            st.markdown("**Examination**")
            show_rows([
                ("Type", prev_exam.get("examination_type") or "—"),
                ("Date", _format_datetime(prev_exam.get("examination_date"))),
                ("Diagnosis", prev_exam.get("diagnosis") or "—"),
            ])
    else:
        st.caption("No previous follow-up — this is the first.")

    st.divider()

    if st.button(
        "Close",
        key=f"fu_details_close_{follow_up.get('follow_up_id')}",
        width="stretch",
    ):
        st.session_state.pop("physician_details_fu", None)
        st.rerun()


# ============================================================
# MANAGE DIALOG (reschedule / cancel / mark missed / mark completed)
# ============================================================

@st.dialog("Manage Follow-Up", width="medium")
def show_follow_up_dialog(follow_up, patient):

    fu_id = follow_up.get("follow_up_id")
    fu_code = follow_up.get("follow_up_code") or "—"
    status = follow_up.get("status") or "Scheduled"
    linked_exam = _follow_up_exam(follow_up)
    linked_status = linked_exam.get("status") if linked_exam else None
    exam_completed = (linked_status == "Completed")
    is_active = status in ACTIVE_FOLLOW_UP_STATUSES

    section_title(f"Manage Follow-Up {fu_code}")

    show_rows([
        ("Patient", _patient_name(patient)),
        ("Scheduled", _follow_up_when(follow_up)),
        ("Status", pill(status, _status_tone(status))),
    ])

    st.divider()

    # Terminal states
    if status in ("Completed", "Cancelled", "Missed"):
        st.info(f"This follow-up is {status.lower()}. No further actions available.")
        if st.button(
            "Close",
            key=f"fu_manage_close_{fu_id}",
            width="stretch",
        ):
            st.session_state.pop("physician_manage_fu", None)
            st.rerun()
        return

    # Active + exam already done
    if is_active and exam_completed:
        st.success("Examination completed. You may formally close this follow-up.")

        if st.button(
            "Mark Follow-Up Completed",
            key=f"fu_manage_complete_{fu_id}",
            icon=":material/check_circle:",
            type="primary",
            width="stretch",
        ):
            result = complete_follow_up(fu_id)
            if result.get("success"):
                remember("Follow-up marked as completed.")
                st.session_state.pop("physician_manage_fu", None)
                st.rerun()
            else:
                st.error(result.get("message", "Failed to complete."))

        st.divider()
        if st.button(
            "Close",
            key=f"fu_manage_close2_{fu_id}",
            width="stretch",
        ):
            st.session_state.pop("physician_manage_fu", None)
            st.rerun()
        return

    # Active + no exam yet
    if is_active and not linked_exam:
        st.info(
            "The patient has not yet been checked in. Reception "
            "staff will create the follow-up examination when the "
            "patient arrives. Once created, it will appear in the "
            "Patient Queue for you to examine."
        )

        st.divider()

        col1, col2 = st.columns(2)

        if col1.button(
            "Reschedule",
            key=f"fu_manage_resched_{fu_id}",
            icon=":material/event_repeat:",
            width="stretch",
        ):
            st.session_state["physician_reschedule_fu"] = follow_up
            st.session_state.pop("physician_manage_fu", None)
            st.rerun()

        if col2.button(
            "Cancel Follow-Up",
            key=f"fu_manage_cancel_{fu_id}",
            icon=":material/cancel:",
            width="stretch",
        ):
            st.session_state["physician_cancel_fu"] = follow_up
            st.session_state.pop("physician_manage_fu", None)
            st.rerun()

        st.divider()

        if st.button(
            "Mark Follow-Up Missed",
            key=f"fu_manage_missed_{fu_id}",
            width="stretch",
        ):
            st.session_state["physician_missed_fu"] = follow_up
            st.session_state.pop("physician_manage_fu", None)
            st.rerun()

    # Active + exam pending (already created by staff)
    elif is_active and linked_status == "Pending":
        st.info(
            "The follow-up examination is waiting in the Patient "
            "Queue for physician review."
        )

        st.divider()

        col1, col2 = st.columns(2)

        if col1.button(
            "Reschedule",
            key=f"fu_manage_resched2_{fu_id}",
            icon=":material/event_repeat:",
            width="stretch",
        ):
            st.session_state["physician_reschedule_fu"] = follow_up
            st.session_state.pop("physician_manage_fu", None)
            st.rerun()

        if col2.button(
            "Cancel Follow-Up",
            key=f"fu_manage_cancel2_{fu_id}",
            icon=":material/cancel:",
            width="stretch",
        ):
            st.session_state["physician_cancel_fu"] = follow_up
            st.session_state.pop("physician_manage_fu", None)
            st.rerun()

    st.divider()

    if st.button(
        "Close",
        key=f"fu_manage_close3_{fu_id}",
        width="stretch",
    ):
        st.session_state.pop("physician_manage_fu", None)
        st.rerun()


# ============================================================
# RESCHEDULE DIALOG
# ============================================================

@st.dialog("Reschedule Follow-Up", width="medium")
def show_reschedule_dialog(follow_up):

    fu_id = follow_up.get("follow_up_id")

    default_date = follow_up.get("follow_up_date")
    if isinstance(default_date, str):
        try:
            default_date = date.fromisoformat(default_date[:10])
        except Exception:
            default_date = date.today()
    if not isinstance(default_date, date):
        default_date = date.today()
    if default_date < date.today():
        default_date = date.today()

    default_time = follow_up.get("follow_up_time")
    if isinstance(default_time, str):
        try:
            default_time = time.fromisoformat(default_time[:8])
        except Exception:
            default_time = time(9, 0)
    if not isinstance(default_time, time):
        default_time = time(9, 0)

    section_title(
        f"Reschedule {follow_up.get('follow_up_code') or 'Follow-Up'}"
    )

    new_date = st.date_input(
        "New Follow-Up Date",
        value=default_date,
        min_value=date.today(),
        key=f"fu_resched_date_{fu_id}",
    )

    new_time = st.time_input(
        "New Follow-Up Time",
        value=default_time,
        key=f"fu_resched_time_{fu_id}",
    )

    st.divider()

    col1, col2 = st.columns(2)

    if col1.button(
        "Cancel",
        key=f"fu_resched_cancel_{fu_id}",
        width="stretch",
    ):
        st.session_state.pop("physician_reschedule_fu", None)
        st.rerun()

    if col2.button(
        "Save Schedule",
        key=f"fu_resched_save_{fu_id}",
        type="primary",
        width="stretch",
    ):
        result = reschedule_follow_up(
            fu_id,
            new_date,
            new_time.strftime("%H:%M:%S"),
        )
        if result.get("success"):
            remember("Follow-up rescheduled successfully.")
            st.session_state.pop("physician_reschedule_fu", None)
            st.rerun()
        else:
            st.error(result.get("message", "Failed to reschedule."))


# ============================================================
# CANCEL DIALOG
# ============================================================

@st.dialog("Cancel Follow-Up", width="small")
def show_cancel_dialog(follow_up):

    fu_id = follow_up.get("follow_up_id")

    st.warning(
        f"Cancel follow-up **{follow_up.get('follow_up_code') or ''}**?"
    )
    st.caption(
        "This cannot be undone from here. A new follow-up can be "
        "scheduled by the physician if needed."
    )

    st.divider()

    keep_col, cancel_col = st.columns(2)

    if keep_col.button(
        "Keep Follow-Up",
        key=f"fu_cancel_keep_{fu_id}",
        width="stretch",
    ):
        st.session_state.pop("physician_cancel_fu", None)
        st.rerun()

    if cancel_col.button(
        "Yes, Cancel",
        key=f"fu_cancel_confirm_{fu_id}",
        type="primary",
        width="stretch",
    ):
        result = cancel_follow_up(fu_id)
        if result.get("success"):
            remember("Follow-up cancelled.")
            st.session_state.pop("physician_cancel_fu", None)
            st.rerun()
        else:
            st.error(result.get("message", "Failed to cancel."))


# ============================================================
# MISSED DIALOG
# ============================================================

@st.dialog("Mark Follow-Up Missed", width="small")
def show_missed_dialog(follow_up):

    fu_id = follow_up.get("follow_up_id")

    st.warning(
        f"Mark **{follow_up.get('follow_up_code') or 'this follow-up'}** as missed?"
    )
    st.caption(
        "Use this when the patient did not arrive for their "
        "scheduled visit."
    )

    st.divider()

    cancel_col, missed_col = st.columns(2)

    if cancel_col.button(
        "Cancel",
        key=f"fu_missed_cancel_{fu_id}",
        width="stretch",
    ):
        st.session_state.pop("physician_missed_fu", None)
        st.rerun()

    if missed_col.button(
        "Mark Missed",
        key=f"fu_missed_confirm_{fu_id}",
        type="primary",
        width="stretch",
    ):
        result = update_follow_up_status(fu_id, "Missed")
        if result.get("success"):
            remember("Follow-up marked as missed.")
            st.session_state.pop("physician_missed_fu", None)
            st.rerun()
        else:
            st.error(result.get("message", "Failed to update."))