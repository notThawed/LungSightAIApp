# streamlit_app/pages/physician_patient_queue.py

"""
Physician — Patient Queue.

Work queue ONLY:
    Section 1 — Pending Examinations (patients awaiting review)
    Section 2 — Pending X-Ray Requests

All follow-up logic lives in:
    streamlit_app/pages/physician/followups.py

Follow-up examinations are created by reception staff
via mark_follow_up_arrived() — not by physicians.
"""

import streamlit as st

from streamlit_app.components.lab_requests_ui import (
    lab_request_selector,
    render_follow_up_lab_documents,
    show_lab_result_dialog,
)
from backend.backend_utils.lab_request_utils import save_requested_labs, get_follow_up_for_examination

from datetime import datetime, date, time, timezone
from zoneinfo import ZoneInfo

from backend.fetches import (
    get_pending_examinations,
    get_pending_xray_requests,
    get_examinations_by_patient,
    get_examination_consents,
    get_examination_vitals,
    get_consent_signature_url,
    get_xray_request_by_examination,
    get_xray_images_by_request,
    get_xray_image_url,
    get_xray_ai_result,
    get_xray_ai_heatmap,
)

from backend.crud import (
    update_examination,
    add_examination_vitals,
    create_xray_request,
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

from backend.backend_utils.followup_utils import (
    finalize_follow_up_for_examination,
    create_follow_up,
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

DOCTOR_ROLES = [ROLE_RADIOLOGIST]
ADMIN_ROLES = [ROLE_SUPERADMIN, ROLE_HOSPITAL_ADMIN]


# ============================================================
# PAGE / DIALOG KEYS
# ============================================================

PAGE_KEY = "sa_page"
DIALOG_KEY = "sa_dialog"


# ============================================================
# TABLE CONFIGURATION
# ============================================================

QUEUE_WIDTHS = [2.0, 2.0, 2.0, 1, 1]
# QUEUE_HEADERS = ["Patient", "Examination Type", "Examination Date", "Waiting", "History", "Actions"]

QUEUE_HEADERS = ["Patient", "Examination Type", "Examination Date", "History", "Actions"]
XRAY_QUEUE_WIDTHS = [2.4, 1.4, 1.6, 1.3, 1.2]
XRAY_QUEUE_HEADERS = ["Patient", "Requested", "Requested At", "Status", "View"]


# ============================================================
# SESSION / USER HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}


def current_role_id():
    return current_user().get("role_id")


def current_user_id():
    return current_user().get("user_id")


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


# ============================================================
# DATE / TIME HELPERS
# ============================================================

PH_TIMEZONE = ZoneInfo("Asia/Manila")


def parse_datetime(value):
    """Parse a Supabase timestamptz value into an aware datetime."""
    if value is None or value == "":
        return None

    try:
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, date):
            return None
        else:
            raw = str(value).strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(raw)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt

    except (TypeError, ValueError):
        return None


def format_datetime(value):
    """Show timezone-aware timestamps in Philippine Standard Time."""
    dt = parse_datetime(value)

    if dt is None:
        return "—"

    return dt.astimezone(PH_TIMEZONE).strftime(
        "%B %d, %Y at %I:%M %p"
    )


def examination_datetime(examination):
    """Prefer the actual check-in timestamp over a date-only midnight value."""
    return (
        examination.get("time_in")
        or examination.get("created_at")
        or examination.get("examination_date")
    )


def examination_wait_start(examination):
    """Use the examination queue entry time for elapsed waiting."""
    return (
        examination.get("time_in")
        or examination.get("created_at")
    )


def medical_record_datetime(record):
    return record.get("record_date") or record.get("created_at")


def xray_request_datetime(request):
    """Only use an actual request timestamp, never examination creation/update."""
    return (
        request.get("xray_requested_at")
        or request.get("requested_at")
    )


# ============================================================
# WAITING TIME
# ============================================================

def waiting_minutes(value):
    """Calculate elapsed minutes using UTC instants."""
    dt = parse_datetime(value)

    if dt is None:
        return None

    delta = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
    return max(0, int(delta.total_seconds() // 60))



def waiting_tone(minutes):
    if minutes is None:
        return "grey"
    if minutes < 10:
        return "green"
    if minutes < 30:
        return "amber"
    return "red"


def format_waiting(minutes):
    """
    Format waiting time into days, hours, and minutes.
    """

    if minutes is None:
        return "—"

    minutes = max(0, int(minutes))

    days, remainder = divmod(minutes, 1440)

    hours, remaining_minutes = divmod(remainder, 60)

    if days > 0:
        return f"{days}d {hours}h {remaining_minutes}m"

    if hours > 0:
        return f"{hours}h {remaining_minutes}m"

    return f"{remaining_minutes}m"

def format_queue_waiting(minutes):
    """Show elapsed wait in days and time, including shorter waits."""
    if minutes is None:
        return "—"
    minutes = max(0, int(minutes))
    days, remainder = divmod(minutes, 24 * 60)
    hours, mins = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h {mins}m"
    return f"{hours}h {mins}m"


# ============================================================
# BMI
# ============================================================

def calculate_bmi(weight_kg, height_cm):
    try:
        weight = float(weight_kg)
        height = float(height_cm) / 100
        if weight <= 0 or height <= 0:
            return None
        return round(weight / (height * height), 2)
    except (TypeError, ValueError):
        return None


def bmi_tone(bmi_value):
    if bmi_value is None:
        return ("—", "grey")
    if bmi_value < 18.5:
        return ("Underweight", "blue")
    if bmi_value < 25:
        return ("Normal", "green")
    if bmi_value < 30:
        return ("Overweight", "amber")
    return ("Obese", "red")


def get_vitals_value(vitals_list, field_name):
    for vital in vitals_list:
        if vital.get(field_name) is not None:
            return vital[field_name]
    return None


# ============================================================
# DIALOG STATE
# ============================================================

# ============================================================
# LAB RESULT DIALOG NAVIGATION / DRAFT PRESERVATION
# ============================================================

LAB_PREVIEW_KEY = "pq_active_lab_preview"
LAB_DRAFTS_KEY = "pq_exam_draft_snapshots"


def _exam_widget_prefix(examination_id):
    return f"pq_exam_{examination_id}_"


def _exam_draft_key_allowed(key, examination_id):
    """Only persist editable widget values, never button or action states."""
    prefix = _exam_widget_prefix(examination_id)
    if not isinstance(key, str) or not key.startswith(prefix):
        return False

    suffix = key[len(prefix):]
    # Buttons cannot be assigned through st.session_state.
    if suffix in {"cancel", "save"}:
        return False
    if suffix.startswith(("view_", "delete_", "confirm_", "yes_", "no_")):
        return False
    if suffix.endswith(("_cancel", "_save")):
        return False
    return True


def _save_exam_draft(examination_id):
    """Preserve only editable examination fields before switching dialogs."""
    snapshot = {
        key: value
        for key, value in st.session_state.items()
        if _exam_draft_key_allowed(key, examination_id)
    }
    st.session_state.setdefault(LAB_DRAFTS_KEY, {})[str(examination_id)] = snapshot


def _restore_exam_draft(examination_id):
    """Restore editable fields before their widgets are constructed."""
    snapshots = st.session_state.get(LAB_DRAFTS_KEY) or {}
    snapshot = snapshots.get(str(examination_id)) or {}
    for key, value in snapshot.items():
        # Filter older snapshots too, in case they contain button keys.
        if not _exam_draft_key_allowed(key, examination_id):
            continue
        if key not in st.session_state:
            st.session_state[key] = value


def _open_physician_lab_preview(follow_up_id, request_id, examination_id):
    _save_exam_draft(examination_id)
    st.session_state[LAB_PREVIEW_KEY] = {
        "follow_up_id": str(follow_up_id),
        "lab_request_id": str(request_id),
        "examination_id": str(examination_id),
    }
    st.rerun(scope="app")


def _back_to_examination():
    st.session_state.pop(LAB_PREVIEW_KEY, None)
    st.rerun(scope="app")


def clear_dialog_state():
    st.session_state.pop(LAB_PREVIEW_KEY, None)
    st.session_state.pop(LAB_DRAFTS_KEY, None)
    for key in (
        "selected_examination",
        "edit_patient",
        "history_patient",
        "pending_exams_patient",
        "xray_request_patient",
        "previous_examinations_patient",
        "previous_medical_records_patient",
    ):
        st.session_state.pop(key, None)


# ============================================================
# GROUP PENDING EXAMINATIONS BY PATIENT
# ============================================================

def group_pending_by_patient(pending_exams):
    by_patient = {}

    for examination in pending_exams:
        patient = examination.get("patients") or {}
        patient_id = patient.get("patient_id")
        if not patient_id:
            continue

        if patient_id not in by_patient:
            by_patient[patient_id] = {
                "patient": patient,
                "exams": [],
                "oldest_waiting": None,
            }

        by_patient[patient_id]["exams"].append(examination)

        waiting = waiting_minutes(examination_wait_start(examination))
        if waiting is not None and (
            by_patient[patient_id]["oldest_waiting"] is None
            or waiting > by_patient[patient_id]["oldest_waiting"]
        ):
            by_patient[patient_id]["oldest_waiting"] = waiting

    grouped = list(by_patient.values())
    grouped.sort(
        key=lambda item: item["oldest_waiting"] if item["oldest_waiting"] is not None else -1,
        reverse=True,
    )
    return grouped


# ============================================================
# PATIENT HISTORY DIALOG
# ============================================================

@st.dialog("Patient History", width="large")
def show_patient_history_dialog(patient):

    patient_id = patient.get("patient_id")

    def display_field(label, value):
        """Display a clinical field without hiding empty values."""
        st.markdown(f"**{label}**")
        st.write(
            str(value)
            if value is not None and str(value).strip()
            else "Not recorded"
        )

    def display_ai_percent(value):
        if value is None:
            return "Not recorded"

        try:
            number = float(value)
            if number <= 1:
                number *= 100
            return f"{number:.1f}%"
        except (TypeError, ValueError):
            return "Not recorded"

    def display_exam_type(examination):
        exam_type = (
            examination.get("examination_type")
            or "Examination"
        )

        normalized = (
            str(exam_type)
            .lower()
            .replace("-", " ")
            .replace("_", " ")
        )

        sequence = examination.get("follow_up_sequence")

        if "follow up" in normalized or "followup" in normalized:
            if sequence is not None:
                try:
                    return (
                        f"Follow-Up Examination "
                        f"{int(sequence):03d}"
                    )
                except (TypeError, ValueError):
                    pass

            return "Follow-Up Examination"

        return exam_type

    with st.container(key=DIALOG_KEY):

        # ====================================================
        # PATIENT INFORMATION
        # ====================================================

        section_title("Patient Information")

        show_rows([
            ("Patient", patient_name(patient)),
            ("Patient ID", patient_code(patient)),
            (
                "Date of Birth",
                format_date(patient.get("date_of_birth")),
            ),
            ("Sex", patient.get("sex") or "—"),
        ])

        st.divider()

        # ====================================================
        # EXAMINATION HISTORY
        # ====================================================

        section_title("Examination History")

        try:
            examinations = (
                get_examinations_by_patient(patient_id)
                or []
            )
        except Exception as error:
            examinations = []
            st.error(
                f"Failed to load examination history: {error}"
            )

        eligible_statuses = {
            "Completed",
            "Admitted",
            "Discharged",
        }

        previous_examinations = [
            examination
            for examination in examinations
            if examination.get("status") in eligible_statuses
            and str(
                examination.get("examination_type") or ""
            ).strip().lower() != "inpatient round"
        ]

        previous_examinations.sort(
            key=lambda examination: (
                str(
                    examination.get("examination_date")
                    or examination.get("created_at")
                    or ""
                ),
                str(examination.get("created_at") or ""),
            ),
            reverse=True,
        )

        if not previous_examinations:
            empty_state(
                "No previous finalized examinations found."
            )

        else:
            st.caption(
                f"{len(previous_examinations)} examination(s) "
                "found. Expand an examination to view its "
                "complete clinical and X-ray records."
            )

            for index, examination in enumerate(
                previous_examinations
            ):

                exam_id = examination.get("examination_id")
                exam_type = display_exam_type(examination)

                exam_date = (
                    examination.get("examination_date")
                    or examination.get("created_at")
                )

                status = (
                    examination.get("status")
                    or "Unknown"
                )

                date_label = format_datetime(exam_date)

                expander_title = (
                    f"{exam_type} | {date_label} | {status}"
                )

                with st.expander(
                    expander_title,
                    expanded=(index == 0),
                ):

                    # ========================================
                    # EXAMINATION DETAILS
                    # ========================================

                    st.markdown("#### Examination Details")

                    show_rows([
                        ("Examination Type", exam_type),
                        ("Date & Time", date_label),
                        ("Status", status),
                        (
                            "Follow-Up Number",
                            (
                                f"{int(examination['follow_up_sequence']):03d}"
                                if str(
                                    examination.get(
                                        "follow_up_sequence"
                                    ) or ""
                                ).isdigit()
                                else "Not applicable"
                            ),
                        ),
                    ])

                    st.divider()

                    # ========================================
                    # CLINICAL NOTES
                    # ========================================

                    st.markdown("#### Clinical Notes")

                    display_field(
                        "Chief Complaint",
                        examination.get("chief_complaint"),
                    )

                    display_field(
                        "History of Present Illness",
                        examination.get(
                            "history_of_present_illness"
                        ),
                    )

                    display_field(
                        "Physical Examination",
                        examination.get(
                            "physical_examination"
                        ),
                    )

                    st.divider()

                    # ========================================
                    # DIAGNOSIS AND MANAGEMENT
                    # ========================================

                    st.markdown(
                        "#### Diagnosis and Management"
                    )

                    display_field(
                        "Diagnosis / Assessment",
                        examination.get("diagnosis"),
                    )

                    display_field(
                        "Plans / Orders",
                        examination.get("plans_orders"),
                    )

                    display_field(
                        "Disposition",
                        examination.get("disposition"),
                    )

                    st.divider()

                    # ========================================
                    # SEVERITY ASSESSMENT
                    # ========================================

                    st.markdown("#### Severity Assessment")

                    curb_score = examination.get(
                        "curb65_score"
                    )

                    if curb_score is not None:
                        try:
                            score = int(curb_score)

                            if score <= 1:
                                risk_label = "Low Risk"
                            elif score == 2:
                                risk_label = "Moderate Risk"
                            else:
                                risk_label = "High Risk"

                            curb_text = (
                                f"{score}/5 — {risk_label}"
                            )

                        except (ValueError, TypeError):
                            curb_text = "Not assessed"
                    else:
                        curb_text = "Not assessed"

                    show_rows([
                        ("CURB-65", curb_text),
                        (
                            "Physician Manual Severity",
                            examination.get(
                                "severity_status"
                            ) or "Not assessed",
                        ),
                    ])

                    st.divider()

                    # ========================================
                    # X-RAY HISTORY
                    # ========================================

                    st.markdown("#### Chest X-Ray")

                    try:
                        request = (
                            get_xray_request_by_examination(
                                exam_id
                            )
                        )
                    except Exception as error:
                        request = None
                        st.warning(
                            f"Unable to retrieve X-ray "
                            f"request: {error}"
                        )

                    if not request:
                        st.info(
                            "No X-ray request found for "
                            "this examination."
                        )

                    else:
                        show_rows([
                            (
                                "Request Status",
                                request.get("status")
                                or "Not recorded",
                            ),
                            (
                                "Clinical Indication",
                                request.get(
                                    "clinical_indication"
                                )
                                or request.get("reason")
                                or "Not recorded",
                            ),
                        ])

                        try:
                            images = (
                                get_xray_images_by_request(
                                    request.get("request_id")
                                )
                                or []
                            )
                        except Exception as error:
                            images = []
                            st.warning(
                                f"Unable to retrieve X-ray "
                                f"images: {error}"
                            )

                        if not images:
                            st.info(
                                "X-ray requested, but no "
                                "uploaded image was found."
                            )

                        else:
                            for image_index, xray in enumerate(
                                images,
                                start=1,
                            ):

                                st.markdown(
                                    f"**X-Ray Image "
                                    f"{image_index}**"
                                )

                                image_url = (
                                    get_xray_image_url(
                                        xray.get("image_path")
                                    )
                                )

                                ai = (
                                    get_xray_ai_result(
                                        xray.get("image_id")
                                    )
                                    or {}
                                )

                                original_col, heatmap_col = (
                                    st.columns(2)
                                )

                                with original_col:
                                    st.markdown(
                                        "**Original X-Ray**"
                                    )

                                    if image_url:
                                        st.image(
                                            image_url,
                                            width="stretch",
                                        )
                                    else:
                                        st.warning(
                                            "Original X-ray "
                                            "image unavailable."
                                        )

                                with heatmap_col:
                                    st.markdown(
                                        "**AI Heatmap Overlay**"
                                    )

                                    heatmap_bytes = None

                                    if ai.get("ai_result_id"):
                                        heatmap_bytes = (
                                            get_xray_ai_heatmap(
                                                ai.get(
                                                    "ai_result_id"
                                                )
                                            )
                                        )

                                    if heatmap_bytes:
                                        st.image(
                                            heatmap_bytes,
                                            width="stretch",
                                        )
                                        st.caption(
                                            "Grad-CAM visualization "
                                            "is an explanatory aid, "
                                            "not a diagnosis."
                                        )
                                    else:
                                        st.info(
                                            "No saved AI heatmap "
                                            "available."
                                        )

                                # ============================
                                # AI ANALYSIS
                                # ============================

                                st.markdown(
                                    "##### AI Analysis Result"
                                )

                                if ai:
                                    ai_findings = (
                                        ai.get("ai_findings")
                                        or "Not recorded"
                                    )

                                    pneumonia_type = (
                                        ai.get("pneumonia_type")
                                        or "Not recorded"
                                    )

                                    pneumonia_type = (
                                        str(pneumonia_type)
                                        .replace("_", " ")
                                        .title()
                                    )

                                    show_rows([
                                        (
                                            "AI Findings",
                                            ai_findings,
                                        ),
                                        (
                                            "Pneumonia Classification",
                                            pneumonia_type,
                                        ),
                                        (
                                            "AI Confidence",
                                            display_ai_percent(
                                                ai.get(
                                                    "ai_confidence"
                                                )
                                            ),
                                        ),
                                        (
                                            "Classification Confidence",
                                            display_ai_percent(
                                                ai.get(
                                                    "classification_confidence"
                                                )
                                            ),
                                        ),
                                    ])

                                    st.caption(
                                        "AI results require "
                                        "physician interpretation "
                                        "and clinical correlation."
                                    )

                                else:
                                    st.info(
                                        "No AI analysis result "
                                        "available for this X-ray."
                                    )

                                if image_index < len(images):
                                    st.divider()

                    st.divider()

                    # ========================================
                    # OTHER SAVED EXAMINATION FIELDS
                    # ========================================
                    #
                    # Show additional populated examination
                    # fields that were not already rendered.
                    # This helps preserve visibility when
                    # more clinical columns are added.
                    # ========================================

                    excluded_fields = {
                        "examination_id",
                        "patient_id",
                        "hospital_id",
                        "created_by",
                        "updated_by",
                        "patients",
                        "examination_type",
                        "examination_date",
                        "created_at",
                        "updated_at",
                        "status",
                        "follow_up_sequence",
                        "chief_complaint",
                        "history_of_present_illness",
                        "physical_examination",
                        "diagnosis",
                        "plans_orders",
                        "disposition",
                        "curb65_score",
                        "severity_status",
                    }

                    additional_fields = {
                        key: value
                        for key, value in examination.items()
                        if key not in excluded_fields
                        and value is not None
                        and not isinstance(
                            value,
                            (dict, list, bytes),
                        )
                        and str(value).strip()
                    }

                    if additional_fields:
                        with st.expander(
                            "Additional Examination Information"
                        ):
                            for key, value in (
                                additional_fields.items()
                            ):
                                label = (
                                    key.replace("_", " ")
                                    .title()
                                )

                                display_field(
                                    label,
                                    value,
                                )

        # ====================================================
        # PREVIOUS MEDICAL / EXTERNAL RECORDS
        # ====================================================

        st.divider()

        section_title(
            "Previous Medical / External Records"
        )

        try:
            from backend.fetches import (
                get_medical_records_by_patient,
            )

            records = (
                get_medical_records_by_patient(
                    patient_id
                )
                or []
            )

        except Exception as error:
            records = []
            st.error(
                f"Failed to load medical records: {error}"
            )

        if not records:
            empty_state(
                "No previous external medical records found."
            )

        else:
            records.sort(
                key=lambda record: (
                    str(
                        record.get("record_date")
                        or record.get("created_at")
                        or ""
                    )
                ),
                reverse=True,
            )

            for index, record in enumerate(records):

                record_type = (
                    record.get("record_type")
                    or "Medical Record"
                )

                record_date = (
                    record.get("record_date")
                    or record.get("created_at")
                )

                with st.expander(
                    f"{record_type} | "
                    f"{format_datetime(record_date)}",
                    expanded=False,
                ):

                    fields = [
                        ("Facility", "facility_name"),
                        ("Department", "department"),
                        (
                            "Attending Physician",
                            "attending_physician",
                        ),
                        (
                            "Chief Complaint",
                            "chief_complaint",
                        ),
                        (
                            "Clinical History",
                            "clinical_history",
                        ),
                        ("Diagnosis", "diagnosis"),
                        (
                            "Procedure",
                            "procedure_name",
                        ),
                        ("Findings", "findings"),
                        ("Impression", "impression"),
                        ("Treatment", "treatment"),
                        ("Follow-Up", "follow_up"),
                        ("Notes", "notes"),
                    ]

                    for label, field in fields:
                        display_field(
                            label,
                            record.get(field),
                        )

        # ====================================================
        # CLOSE DIALOG
        # ====================================================

        st.divider()

        if st.button(
            "Close",
            key="pq_history_close",
            width="stretch",
        ):
            st.session_state.pop(
                "history_patient",
                None,
            )
            st.rerun()


# ============================================================
# PREVIOUS EXAMINATIONS DIALOG
# ============================================================

@st.dialog("Previous Examination History", width="large")
def show_previous_examinations_dialog(patient):

    patient_id = patient.get("patient_id")
    examinations = get_examinations_by_patient(patient_id)

    previous = [
        e for e in examinations
        if e.get("status") in ("Completed", "Cancelled")
    ]

    with st.container(key=DIALOG_KEY):

        section_title(f"Previous Examinations ({len(previous)})")

        if not previous:
            empty_state("No previous examinations found.")
        else:
            for examination in sorted(
                previous,
                key=lambda item: examination_datetime(item) or "",
                reverse=True,
            ):
                status = examination.get("status") or "Unknown"
                tone = "green" if status == "Completed" else "red"

                st.markdown(
                    f"### {examination.get('examination_type') or 'Examination'}"
                )
                st.markdown(
                    f"**Date & Time:** {format_datetime(examination_datetime(examination))}"
                )
                st.markdown(
                    f"**Status:** {pill(status, tone)}",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**Chief Complaint:** {examination.get('chief_complaint') or '—'}"
                )
                st.markdown(
                    f"**Diagnosis:** {examination.get('diagnosis') or '—'}"
                )
                st.markdown(
                    f"**Plans / Orders:** {examination.get('plans_orders') or '—'}"
                )
                st.markdown(
                    f"**Disposition:** {examination.get('disposition') or '—'}"
                )
                st.divider()

        if st.button(
            "Close",
            key="pq_prev_exam_close",
            width="stretch",
        ):
            st.session_state.pop("previous_examinations_patient", None)
            st.rerun()


# ============================================================
# PREVIOUS MEDICAL RECORDS DIALOG
# ============================================================

@st.dialog("Previous Medical Histories", width="large")
def show_previous_medical_records_dialog(patient):

    patient_id = patient.get("patient_id")

    try:
        from backend.fetches import get_medical_records_by_patient
        records = get_medical_records_by_patient(patient_id)
    except Exception as error:
        records = []
        st.error(f"Failed to load medical records: {error}")

    with st.container(key=DIALOG_KEY):

        section_title(f"Previous Medical Records ({len(records)})")

        if not records:
            empty_state("No previous external medical records found.")
        else:
            for record in sorted(
                records,
                key=lambda item: medical_record_datetime(item) or "",
                reverse=True,
            ):
                st.markdown(
                    f"### {record.get('record_type') or 'Medical Record'}"
                )
                st.markdown(
                    f"**Date & Time:** {format_datetime(medical_record_datetime(record))}"
                )
                st.markdown(f"**Facility:** {record.get('facility_name') or '—'}")
                st.markdown(f"**Diagnosis:** {record.get('diagnosis') or '—'}")
                st.markdown(f"**Treatment:** {record.get('treatment') or '—'}")
                st.markdown(f"**Notes:** {record.get('notes') or '—'}")
                st.divider()

        if st.button(
            "Close",
            key="pq_prev_med_close",
            width="stretch",
        ):
            st.session_state.pop("previous_medical_records_patient", None)
            st.rerun()


# ============================================================
# HISTORY BUTTONS
# ============================================================

def render_history_buttons(patient, key_prefix):

    st.divider()
    section_title("Patient History")
    st.caption("Review previous examinations and medical histories separately.")

    col1, col2 = st.columns(2)

    if col1.button(
        "View Examination Histories",
        key=f"{key_prefix}_view_exam_history",
        icon=":material/history:",
        width="stretch",
    ):
        st.session_state["previous_examinations_patient"] = patient
        st.rerun()

    if col2.button(
        "View Previous Medical Histories",
        key=f"{key_prefix}_view_medical_history",
        icon=":material/medical_information:",
        width="stretch",
    ):
        st.session_state["previous_medical_records_patient"] = patient
        st.rerun()


# ============================================================
# X-RAY REQUEST DIALOG
# ============================================================

@st.dialog("X-Ray Request Details", width="medium")
def show_xray_request_dialog(examination):

    patient = examination.get("patients") or {}
    requested_at = xray_request_datetime(examination)
    waiting = waiting_minutes(requested_at)

    with st.container(key=DIALOG_KEY):

        section_title("Patient Information")
        show_rows([
            ("Patient", patient_name(patient)),
            ("Patient ID", patient_code(patient)),
        ])

        st.divider()
        section_title("X-Ray Request")

        show_rows([
            ("Requested Examination", "Chest X-Ray"),
            ("Requested At", format_datetime(requested_at)),
            ("Time Since Request", format_waiting(waiting)),
        ])

        st.markdown(
            f"""
            <div class="sa-row">
                <span>Status</span>
                <b>{pill("Pending", "amber")}</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()
        st.info(
            "This request is view-only. The Radiologic Technologist "
            "will process the requested X-Ray."
        )

        if st.button(
            "Close",
            key="pq_xray_close",
            width="stretch",
        ):
            st.session_state.pop("xray_request_patient", None)
            st.rerun()


# ============================================================
# MULTIPLE EXAMINATIONS DIALOG
# ============================================================

@st.dialog("Patient Examinations", width="medium")
def show_pending_exams_dialog(patient, examinations):

    with st.container(key=DIALOG_KEY):

        show_rows([
            ("Patient", patient_name(patient)),
            ("Patient ID", patient_code(patient)),
        ])

        section_title(f"{len(examinations)} Examination(s)")

        for examination in sorted(
            examinations,
            key=lambda item: item.get("created_at") or "",
        ):
            waiting = waiting_minutes(examination_wait_start(examination))

            st.markdown(
                f"**{examination.get('examination_type') or 'Examination'}**"
            )
            st.caption(format_datetime(examination_datetime(examination)))
            st.markdown(
                pill(format_waiting(waiting), waiting_tone(waiting)),
                unsafe_allow_html=True,
            )

            if st.button(
                "Examine Patient",
                key=f"pq_open_pending_{examination['examination_id']}",
                type="primary",
                width="stretch",
            ):
                st.session_state.pop("pending_exams_patient", None)
                st.session_state["selected_examination"] = examination
                st.session_state["edit_patient"] = patient
                st.rerun()

            st.divider()

        if st.button(
            "Close",
            key="pq_pending_exams_close",
            width="stretch",
        ):
            st.session_state.pop("pending_exams_patient", None)
            st.rerun()


# ============================================================
# EXAMINATION DIALOG
# ============================================================

@st.dialog("Examine Patient", width="large")
def show_complete_exam_dialog(patient, examination):

    user_id = current_user_id()
    examination_id = examination["examination_id"]

    with st.container(key=DIALOG_KEY):

        section_title("Patient Information")
        show_rows([
            ("Patient", patient_name(patient)),
            ("Patient ID", patient_code(patient)),
            ("Date of Birth", format_date(patient.get("date_of_birth"))),
            ("Sex", patient.get("sex") or "—"),
            (
                "Examination Type",
                examination.get("examination_type") or "Examination",
            ),
        ])

        exam_type = str(examination.get("examination_type") or "").strip().lower().replace("-", " ")
        if exam_type.startswith("follow up examination"):
            try:
                linked_fu_id = get_follow_up_for_examination(examination_id, user_id)
                if linked_fu_id:
                    render_follow_up_lab_documents(
                        linked_fu_id, user_id, allow_upload=False,
                        key_prefix=f"pq_labs_{examination_id}",
                        on_view_result=lambda request_id: _open_physician_lab_preview(
                            linked_fu_id, request_id, examination_id
                        ),
                    )
                else:
                    st.caption("No follow-up appointment is linked to this examination.")
            except Exception as error:
                st.warning(f"Could not load requested laboratory results: {error}")

        st.divider()
        section_title("Clinical Data")

        consents = get_examination_consents(examination_id)
        consent = consents[0] if consents else None
        vitals = get_examination_vitals(examination_id)

        if consent and consent.get("given"):
            st.markdown(
                f"**Consent signed by:** {consent.get('signed_by_name') or '—'}"
            )
            signature_path = consent.get("signature_path")
            if signature_path:
                signature_url = get_consent_signature_url(signature_path)
                if signature_url:
                    st.image(signature_url, width=200, caption="Patient signature")
        else:
            st.warning("No consent on file for this examination.")

        section_title("Vitals")

        v1, v2, v3 = st.columns(3)

        bp_sys = v1.number_input(
            "BP systolic (mmHg)",
            min_value=0, max_value=300, step=1,
            value=int(get_vitals_value(vitals, "bp_systolic") or 0),
            key=f"pq_exam_{examination_id}_bp_sys",
        )
        bp_dia = v2.number_input(
            "BP diastolic (mmHg)",
            min_value=0, max_value=200, step=1,
            value=int(get_vitals_value(vitals, "bp_diastolic") or 0),
            key=f"pq_exam_{examination_id}_bp_dia",
        )
        temperature = v3.number_input(
            "Temperature (°C)",
            min_value=0.0, max_value=50.0, step=0.1,
            value=float(get_vitals_value(vitals, "temperature") or 0.0),
            key=f"pq_exam_{examination_id}_temp",
        )

        v4, v5, v6 = st.columns(3)

        pulse_rate = v4.number_input(
            "Pulse rate (bpm)",
            min_value=0, max_value=300, step=1,
            value=int(get_vitals_value(vitals, "pulse_rate") or 0),
            key=f"pq_exam_{examination_id}_pulse",
        )
        respiratory_rate = v5.number_input(
            "Respiratory rate (/min)",
            min_value=0, max_value=100, step=1,
            value=int(get_vitals_value(vitals, "respiratory_rate") or 0),
            key=f"pq_exam_{examination_id}_rr",
        )
        weight = v6.number_input(
            "Weight (kg)",
            min_value=0.0, max_value=500.0, step=0.1,
            value=float(get_vitals_value(vitals, "weight_kg") or 0.0),
            key=f"pq_exam_{examination_id}_weight",
        )

        v7, v8, v9 = st.columns(3)

        height = v7.number_input(
            "Height (cm)",
            min_value=0.0, max_value=300.0, step=0.1,
            value=float(get_vitals_value(vitals, "height_cm") or 0.0),
            key=f"pq_exam_{examination_id}_height",
        )
        spo2 = v8.number_input(
            "SpO2 (%)",
            min_value=0, max_value=100, step=1,
            value=int(get_vitals_value(vitals, "spo2") or 0),
            key=f"pq_exam_{examination_id}_spo2",
        )
        heart_rate = v9.number_input(
            "Heart rate (bpm)",
            min_value=0, max_value=300, step=1,
            value=int(get_vitals_value(vitals, "heart_rate") or 0),
            key=f"pq_exam_{examination_id}_heart_rate",
        )

        bmi = calculate_bmi(weight, height)
        if bmi:
            label, tone = bmi_tone(bmi)
            st.markdown(
                f"**BMI:** {bmi} {pill(label, tone)}",
                unsafe_allow_html=True,
            )

        st.divider()
        section_title("Clinical Notes")

        chief_complaint = st.text_area(
            "Chief complaint",
            value=examination.get("chief_complaint") or "",
            height=80,
            key=f"pq_exam_{examination_id}_chief",
        )
        hpi = st.text_area(
            "History of present illness",
            value=examination.get("history_of_present_illness") or "",
            height=120,
            key=f"pq_exam_{examination_id}_hpi",
        )
        physical_exam = st.text_area(
            "Physical examination",
            value=examination.get("physical_examination") or "",
            height=120,
            key=f"pq_exam_{examination_id}_physical",
        )

        st.divider()
        section_title("Doctor Orders")

        order = st.radio(
            "Select next step",
            ["No Request", "Chest X-Ray"],
            key=f"pq_exam_{examination_id}_order",
            horizontal=True,
        )

        diagnosis = None
        plans = None
        lab_requests = []
        disposition = None
        disposition_notes = None

        if order == "No Request":
            diagnosis = st.text_area(
                "Diagnosis / Assessment",
                value=examination.get("diagnosis") or "",
                height=100,
                key=f"pq_exam_{examination_id}_diagnosis",
            )
            plans = st.text_area(
                "Plans / Orders",
                value=examination.get("plans_orders") or "",
                height=100,
                key=f"pq_exam_{examination_id}_plans",
            )
            lab_requests = lab_request_selector(
                examination_id, user_id, f"pq_exam_{examination_id}"
            )

            st.divider()
            section_title("Disposition")

            disposition_options = [
                "Admission",
                "Treated and Sent Home",
                "Referred",
                "Refused Admission",
                "Nowhere When Called",
            ]
            current_disposition = examination.get("disposition")
            disposition_index = (
                disposition_options.index(current_disposition)
                if current_disposition in disposition_options
                else 0
            )

            disposition = st.selectbox(
                "Disposition",
                disposition_options,
                index=disposition_index,
                key=f"pq_exam_{examination_id}_disposition",
            )
            disposition_notes = st.text_area(
                "Disposition notes",
                value=examination.get("disposition_notes") or "",
                height=100,
                key=f"pq_exam_{examination_id}_disposition_notes",
            )
            # Optional appointment for BOTH General Consult and Follow-Up Examination.
            # A follow-up does not require a Chest X-Ray request.
            exam_type_normalized = (
                str(examination.get("examination_type") or "")
                .strip().lower().replace("_", " ").replace("-", " ")
            )
            followup_eligible = (
                exam_type_normalized in ("general consult", "general consultation")
                or exam_type_normalized.startswith("follow up examination")
            )
            schedule_follow_up = False
            follow_up_date = None
            follow_up_time = None
            follow_up_notes = None

            if followup_eligible:
                st.divider()
                section_title("Follow-Up Appointment")
                if disposition == "Admission":
                    st.info(
                        "Follow-up scheduling is available after discharge. "
                        "Complete the inpatient workflow first."
                    )
                else:
                    schedule_follow_up = st.checkbox(
                        "Schedule a follow-up appointment",
                        value=False,
                        key=f"pq_exam_{examination_id}_schedule_fu",
                    )
                    if schedule_follow_up:
                        local_today = datetime.now(PH_TIMEZONE).date()
                        follow_up_date = st.date_input(
                            "Follow-Up Date *",
                            value=local_today,
                            min_value=local_today,
                            key=f"pq_exam_{examination_id}_fu_date",
                        )
                        st.markdown("**Follow-Up Time * (Philippine Time)**")
                        hour_col, minute_col, period_col = st.columns(3)
                        hour = hour_col.selectbox(
                            "", list(range(1, 13)), index=8,
                            key=f"pq_exam_{examination_id}_fu_hour",
                        )
                        minute = minute_col.selectbox(
                            "", list(range(60)), index=0,
                            format_func=lambda n: f"{n:02d}",
                            key=f"pq_exam_{examination_id}_fu_minute",
                        )
                        am_pm = period_col.selectbox(
                            "AM / PM", ["AM", "PM"],
                            key=f"pq_exam_{examination_id}_fu_period",
                        )
                        hour_24 = hour % 12 + (12 if am_pm == "PM" else 0)
                        follow_up_time = time(hour_24, minute)
                        follow_up_notes = st.text_area(
                            "Follow-Up Notes",
                            placeholder="Reason for follow-up and instructions",
                            key=f"pq_exam_{examination_id}_fu_notes",
                        )
                        st.caption(
                            "Appointment: "
                            f"{follow_up_date.strftime('%B %d, %Y')} at "
                            f"{follow_up_time.strftime('%I:%M %p')} (PHT)"
                        )

        else:
            st.info(
                "A Chest X-Ray request will be created for the "
                "Radiologic Technologist."
            )

            clinical_indication = st.text_area(
                "Clinical Indication / Reason for X-Ray",
                value="",
                placeholder=(
                    "Enter the clinical reason for requesting the X-Ray. "
                    "Example: Evaluate for suspected pneumonia."
                ),
                height=100,
                key=f"pq_exam_{examination_id}_clinical_indication",
                help=(
                    "Describe the clinical question or suspected condition "
                    "that the requested X-Ray should help evaluate."
                ),
            )

        st.divider()
        cancel_col, save_col = st.columns(2)

        cancel_clicked = cancel_col.button(
            "Cancel",
            key=f"pq_exam_{examination_id}_cancel",
            width="stretch",
        )
        save_clicked = save_col.button(
            "Request X-Ray" if order == "Chest X-Ray" else "Complete Examination",
            key=f"pq_exam_{examination_id}_save",
            type="primary",
            width="stretch",
        )

    if cancel_clicked:
        clear_dialog_state()
        st.rerun()

    if not save_clicked:
        return

    if not chief_complaint.strip():
        st.error("Chief complaint is required.")
        return

    if order == "No Request" and not diagnosis.strip():
        st.error("Diagnosis is required.")
        return

    if order == "No Request" and lab_requests is None:
        st.error("Laboratory requests are unavailable. Please apply the SQL migration and refresh.")
        return

    if order == "No Request" and schedule_follow_up:
        local_now = datetime.now(PH_TIMEZONE)
        appointment_at = datetime.combine(
            follow_up_date, follow_up_time, tzinfo=PH_TIMEZONE
        )
        if appointment_at <= local_now:
            st.error("Follow-up date and time must be in the future (Philippine Time).")
            return

    if order == "Chest X-Ray" and not clinical_indication.strip():
        st.error(
            "Please provide a clinical indication before "
            "requesting the X-Ray."
        )
        return

    try:
        original_vitals = vitals[0] if vitals else {}

        if (
            (bp_sys or None) != original_vitals.get("bp_systolic")
            or (bp_dia or None) != original_vitals.get("bp_diastolic")
            or (temperature or None) != original_vitals.get("temperature")
        ):
            add_examination_vitals(
                examination_id=examination_id,
                recorded_by=user_id,
                recorded_by_role="doctor",
                bp_systolic=(bp_sys or None),
                bp_diastolic=(bp_dia or None),
                temperature=(temperature or None),
            )

        if any([pulse_rate, respiratory_rate, weight, height, spo2, heart_rate]):
            add_examination_vitals(
                examination_id=examination_id,
                recorded_by=user_id,
                recorded_by_role="doctor",
                pulse_rate=(pulse_rate or None),
                respiratory_rate=(respiratory_rate or None),
                weight_kg=(weight or None),
                height_cm=(height or None),
                spo2=(spo2 or None),
                heart_rate=(heart_rate or None),
                bmi=bmi,
            )

        if order == "No Request":
            try:
                save_requested_labs(examination_id, user_id, lab_requests)
            except Exception as lab_error:
                st.error(f"Could not save laboratory requests: {lab_error}. The examination was not finalized.")
                return

            update_examination(
                examination_id=examination_id,
                status="Completed",
                reviewed_by=user_id,
                chief_complaint=(chief_complaint.strip() or None),
                history_of_present_illness=(hpi.strip() or None),
                physical_examination=(physical_exam.strip() or None),
                diagnosis=(diagnosis.strip() or None),
                plans_orders=(plans.strip() or None),
                disposition=disposition,
                disposition_notes=(
                    disposition_notes.strip() if disposition_notes else None
                ),
            )

            follow_up_result = finalize_follow_up_for_examination(examination_id)
            if not follow_up_result.get("success"):
                st.error("Examination saved, but linked follow-up could not be completed: "
                         + follow_up_result.get("message", "Unknown error"))
                return

            if schedule_follow_up:
                follow_up_created = create_follow_up(
                    patient_id=patient.get("patient_id"),
                    examination_id=examination_id,
                    follow_up_date=follow_up_date,
                    follow_up_time=follow_up_time,
                    notes=(follow_up_notes or "").strip() or None,
                    created_by=user_id,
                )
                if not follow_up_created.get("success"):
                    st.error(
                        "Examination was completed, but follow-up scheduling failed: "
                        + follow_up_created.get("message", "Unknown error")
                        + ". Please schedule the appointment from Review Patient "
                          "or Follow-Ups; do not submit this examination again."
                    )
                    return

            clear_dialog_state()
            remember(
                "Examination completed and follow-up scheduled successfully."
                if schedule_follow_up else "Examination completed successfully."
            )
            st.rerun()

        update_examination(
            examination_id=examination_id,
            status="Awaiting X-Ray",
            reviewed_by=user_id,
            chief_complaint=(chief_complaint.strip() or None),
            history_of_present_illness=(hpi.strip() or None),
            physical_examination=(physical_exam.strip() or None),
        )

        create_xray_request(
            examination_id=examination_id,
            hospital_id=current_hospital_id(),
            requested_by=user_id,
            body_part="Chest",
            priority="Routine",
            clinical_indication=(
                clinical_indication.strip() or None
            ),
        )

        clear_dialog_state()
        remember(
            "Chest X-Ray requested. Patient is now awaiting X-Ray processing."
        )
        st.rerun()

    except Exception as error:
        st.error(f"Failed to save examination: {error}")


# ============================================================
# METRICS
# ============================================================

def render_metrics(grouped, xray_requests):

    total_patients = len(grouped)
    total_exams = sum(len(item["exams"]) for item in grouped)
    xray_count = len(xray_requests)

    m1, m2, m3 = st.columns(3)

    with m1:
        metric_card("Patients waiting", total_patients, "groups", tone="blue")
    with m2:
        metric_card(
            "Pending examinations",
            total_exams,
            "pending_actions",
            tone="amber",
        )
    with m3:
        metric_card(
            "Pending X-Ray requests",
            xray_count,
            "radiology",
            tone="blue",
        )


# ============================================================
# PATIENT QUEUE TABLE
# ============================================================

def render_queue_table(grouped, key_prefix="queue"):

    if not grouped:
        empty_state("No examinations are currently waiting for physician review.")
        return

    with st.container(key=f"pq_queue_{key_prefix}"):

        table_header(QUEUE_HEADERS, QUEUE_WIDTHS, key_prefix)

        for item in grouped:
            patient = item["patient"]
            examinations = item["exams"]
            waiting = item["oldest_waiting"]
            patient_id = patient.get("patient_id")

            with table_row(f"{key_prefix}_row_{patient_id}", QUEUE_WIDTHS) as columns:

                name_cell(
                    columns[0],
                    patient_name(patient),
                    sub=patient_code(patient),
                )
                types = [
                    examination.get("examination_type") or "Examination"
                    for examination in examinations
                ]
                dates = [
                    format_datetime(examination_datetime(examination))
                    for examination in examinations
                ]
                text_cell(columns[1], " · ".join(types))
                text_cell(columns[2], " · ".join(dates))

                # The waiting logic is completely skipped visually.

                if columns[3].button( # Changed from 4 to 3
                    "History",
                    key=f"{key_prefix}_history_{patient_id}",
                    icon=":material/folder_open:",
                    width="stretch",
                ):
                    clear_dialog_state()
                    st.session_state["history_patient"] = patient
                    st.rerun()

                if len(examinations) == 1:
                    if columns[4].button( # Changed from 5 to 4
                        "Examine",
                        key=f"{key_prefix}_examine_{patient_id}",
                        icon=":material/clinical_notes:",
                        type="primary",
                        width="stretch",
                    ):
                        clear_dialog_state()
                        st.session_state["selected_examination"] = examinations[0]
                        st.session_state["edit_patient"] = patient
                        st.rerun()
                else:
                    if columns[4].button( # Changed from 5 to 4
                        "View Exams",
                        key=f"{key_prefix}_view_{patient_id}",
                        icon=":material/list:",
                        type="primary",
                        width="stretch",
                    ):
                        clear_dialog_state()
                        st.session_state["pending_exams_patient"] = {
                            "patient": patient,
                            "exams": examinations,
                        }
                        st.rerun()


# ============================================================
# X-RAY REQUEST TABLE
# ============================================================

def render_xray_request_table(xray_requests, key_prefix="xray"):

    if not xray_requests:
        empty_state("You have no pending X-Ray requests.")
        return

    with st.container(key=f"pq_xray_{key_prefix}"):

        table_header(XRAY_QUEUE_HEADERS, XRAY_QUEUE_WIDTHS, key_prefix)

        for request in xray_requests:
            patient = request.get("patients") or {}
            request_id = request.get("request_id")
            requested_at = xray_request_datetime(request)
            waiting = waiting_minutes(requested_at)

            with table_row(
                f"{key_prefix}_row_{request_id}",
                XRAY_QUEUE_WIDTHS,
            ) as columns:

                name_cell(
                    columns[0],
                    patient_name(patient),
                    sub=patient_code(patient),
                )
                pill_cell(
                    columns[1],
                    format_waiting(waiting),
                    waiting_tone(waiting),
                )
                text_cell(columns[2], format_datetime(requested_at))
                pill_cell(columns[3], "Pending", "amber")

                if columns[4].button(
                    "View",
                    key=f"{key_prefix}_view_{request_id}",
                    icon=":material/visibility:",
                    width="stretch",
                ):
                    clear_dialog_state()
                    st.session_state["xray_request_patient"] = request
                    st.rerun()


# ============================================================
# PAGE
# ============================================================

def show():

    load_css("patient_queue.css")
    show_flash_message()

    role_id = current_role_id()
    hospital_id = current_hospital_id()

    if role_id == ROLE_SUPERADMIN:
        filter_hospital = None
    elif role_id in DOCTOR_ROLES:
        filter_hospital = hospital_id
    elif role_id == ROLE_HOSPITAL_ADMIN:
        filter_hospital = hospital_id
    else:
        st.error("You don't have access to the patient queue.")
        return

    with st.container(key=PAGE_KEY):

        page_header(
            "Patient Queue",
            "Review patients awaiting physician care and pending X-Ray requests.",
        )

        try:
            pending = get_pending_examinations(hospital_id=filter_hospital)
        except Exception as error:
            st.error(f"Failed to load patient queue: {error}")
            pending = []

        try:
            xray_requests = get_pending_xray_requests(hospital_id=filter_hospital)
        except Exception as error:
            st.error(f"Failed to load X-Ray requests: {error}")
            xray_requests = []

        if role_id in DOCTOR_ROLES:
            user_id = current_user_id()
            xray_requests = [
                r for r in xray_requests
                if str(r.get("requested_by")) == str(user_id)
            ]

        grouped = group_pending_by_patient(pending)

        render_metrics(grouped, xray_requests)

        st.divider()

        section_title("Patients Awaiting Physician Review")
        st.caption(
            "Patients who currently have an examination waiting for physician review."
        )
        render_queue_table(grouped, key_prefix="pending")

        st.divider()

        section_title("Pending X-Ray Requests")
        st.caption(
            "Chest X-Ray requests that are currently waiting for "
            "Radiologic Technologist processing."
        )
        render_xray_request_table(xray_requests, key_prefix="xray")

    # ----- Dialogs -----
    # Preview takes precedence: never call two @st.dialog functions in one run.
    preview = st.session_state.get(LAB_PREVIEW_KEY)
    if preview:
        show_lab_result_dialog(
            follow_up_id=preview["follow_up_id"],
            lab_request_id=preview["lab_request_id"],
            actor_id=current_user_id(),
            allow_upload=False,
            key_prefix=f"pq_labs_{preview['examination_id']}",
            on_back=_back_to_examination,
        )

    elif st.session_state.get("selected_examination"):
        _restore_exam_draft(st.session_state["selected_examination"]["examination_id"])
        examination = st.session_state["selected_examination"]
        patient = st.session_state.get("edit_patient")
        if patient:
            show_complete_exam_dialog(patient, examination)

    elif st.session_state.get("pending_exams_patient"):
        data = st.session_state["pending_exams_patient"]
        show_pending_exams_dialog(data["patient"], data["exams"])

    elif st.session_state.get("xray_request_patient"):
        show_xray_request_dialog(st.session_state["xray_request_patient"])

    elif st.session_state.get("history_patient"):
        show_patient_history_dialog(st.session_state["history_patient"])

    elif st.session_state.get("previous_examinations_patient"):
        show_previous_examinations_dialog(
            st.session_state["previous_examinations_patient"]
        )

    elif st.session_state.get("previous_medical_records_patient"):
        show_previous_medical_records_dialog(
            st.session_state["previous_medical_records_patient"]
        )
