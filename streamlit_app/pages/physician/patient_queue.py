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

from datetime import datetime, date, time, timezone

from backend.fetches import (
    get_pending_examinations,
    get_pending_xray_requests,
    get_examinations_by_patient,
    get_examination_consents,
    get_examination_vitals,
    get_consent_signature_url,
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

QUEUE_WIDTHS = [2.5, 1, 1.2, 1.2, 1.2]
QUEUE_HEADERS = ["Patient", "Pending", "Waiting", "History", "Actions"]

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

def parse_datetime(value):
    if not value:
        return None
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            value = str(value)
            if value.endswith("Z"):
                value = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(value)
        return dt
    except Exception:
        return None


def format_datetime(value):
    if not value:
        return "—"
    try:
        dt = parse_datetime(value)
        if not dt:
            return str(value)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt.strftime("%B %d, %Y at %I:%M %p")
    except Exception:
        return str(value)


def examination_datetime(examination):
    return examination.get("examination_date") or examination.get("created_at")


def medical_record_datetime(record):
    return record.get("record_date") or record.get("created_at")


def xray_request_datetime(examination):
    return (
        examination.get("xray_requested_at")
        or examination.get("requested_at")
        or examination.get("created_at")
    )


# ============================================================
# WAITING TIME
# ============================================================

def waiting_minutes(created_at_str):
    if not created_at_str:
        return 0
    try:
        created = datetime.fromisoformat(str(created_at_str).replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - created
        return max(0, int(delta.total_seconds() // 60))
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

def clear_dialog_state():
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
                "oldest_waiting": 0,
            }

        by_patient[patient_id]["exams"].append(examination)

        waiting = waiting_minutes(examination.get("created_at"))
        if waiting > by_patient[patient_id]["oldest_waiting"]:
            by_patient[patient_id]["oldest_waiting"] = waiting

    grouped = list(by_patient.values())
    grouped.sort(key=lambda item: item["oldest_waiting"], reverse=True)
    return grouped


# ============================================================
# PATIENT HISTORY DIALOG
# ============================================================

@st.dialog("Patient History", width="large")
def show_patient_history_dialog(patient):

    patient_id = patient.get("patient_id")

    with st.container(key=DIALOG_KEY):

        section_title("Patient Information")
        show_rows([
            ("Patient", patient_name(patient)),
            ("Patient ID", patient_code(patient)),
            ("Date of Birth", format_date(patient.get("date_of_birth"))),
            ("Sex", patient.get("sex") or "—"),
        ])

        st.divider()
        section_title("Examination History")

        try:
            examinations = get_examinations_by_patient(patient_id)
        except Exception as error:
            examinations = []
            st.error(f"Failed to load examination history: {error}")

        completed = [
            e for e in examinations
            if e.get("status") in ("Completed", "Cancelled")
        ]

        if not completed:
            empty_state("No previous examinations found.")
        else:
            for examination in sorted(
                completed,
                key=lambda item: examination_datetime(item) or "",
                reverse=True,
            ):
                status = examination.get("status") or "Unknown"
                tone = "green" if status == "Completed" else "red"

                st.markdown(
                    f"**{examination.get('examination_type') or 'Examination'}**"
                )
                st.caption(format_datetime(examination_datetime(examination)))
                st.markdown(
                    f"Status: {pill(status, tone)}",
                    unsafe_allow_html=True,
                )

                if examination.get("diagnosis"):
                    st.caption(f"Diagnosis: {examination.get('diagnosis')}")
                if examination.get("chief_complaint"):
                    st.caption(f"Chief Complaint: {examination.get('chief_complaint')}")
                if examination.get("disposition"):
                    st.caption(f"Disposition: {examination.get('disposition')}")

                st.divider()

        section_title("Previous Medical / External Records")

        try:
            from backend.fetches import get_medical_records_by_patient
            records = get_medical_records_by_patient(patient_id)
        except Exception as error:
            records = []
            st.error(f"Failed to load medical records: {error}")

        if not records:
            empty_state("No previous external medical records found.")
        else:
            for record in sorted(
                records,
                key=lambda item: medical_record_datetime(item) or "",
                reverse=True,
            ):
                st.markdown(
                    f"**{record.get('record_type') or 'Medical Record'}**"
                )
                st.caption(format_datetime(medical_record_datetime(record)))
                st.markdown(f"**Facility:** {record.get('facility_name') or '—'}")
                if record.get("diagnosis"):
                    st.markdown(f"**Diagnosis:** {record.get('diagnosis')}")
                if record.get("treatment"):
                    st.markdown(f"**Treatment:** {record.get('treatment')}")
                if record.get("notes"):
                    st.markdown(f"**Notes:** {record.get('notes')}")
                st.divider()

        if st.button(
            "Close",
            key="pq_history_close",
            width="stretch",
        ):
            st.session_state.pop("history_patient", None)
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
            ("Status", pill("Pending", "amber")),
        ])

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
            waiting = waiting_minutes(examination.get("created_at"))

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

        render_history_buttons(patient, key_prefix=f"pq_exam_{examination_id}")

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
        else:
            st.info(
                "A Chest X-Ray request will be created for the "
                "Radiologic Technologist."
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

            clear_dialog_state()
            remember("Examination completed successfully.")
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
            clinical_indication=(chief_complaint.strip() or None),
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
                text_cell(columns[1], str(len(examinations)))
                pill_cell(
                    columns[2],
                    format_waiting(waiting),
                    waiting_tone(waiting),
                )

                if columns[3].button(
                    "History",
                    key=f"{key_prefix}_history_{patient_id}",
                    icon=":material/folder_open:",
                    width="stretch",
                ):
                    clear_dialog_state()
                    st.session_state["history_patient"] = patient
                    st.rerun()

                if len(examinations) == 1:
                    if columns[4].button(
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
                    if columns[4].button(
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

        if st.button(
            "Refresh",
            icon=":material/refresh:",
            key="pq_refresh",
            width="stretch",
        ):
            st.rerun()

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
    if st.session_state.get("selected_examination"):
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