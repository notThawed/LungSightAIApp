import streamlit as st

from backend.fetches import (
    get_xray_ready_examinations,
    get_xray_request_by_examination,
    get_xray_images_by_request,
    get_xray_image_url,
    get_xray_ai_result,
    get_examinations_by_patient,
    get_medical_records_by_patient,
)

from backend.crud import (
    save_xray_review,
    update_examination,
)

from streamlit_app.components.ui import (
    load_css,
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


# ============================================================
# CONFIG
# ============================================================

ROLE_SUPERADMIN = 1
ROLE_RADIOLOGIST = 3
ROLE_HOSPITAL_ADMIN = 6

DOCTOR_ROLES = [
    ROLE_RADIOLOGIST,
]

ADMIN_ROLES = [
    ROLE_SUPERADMIN,
    ROLE_HOSPITAL_ADMIN,
]

QUEUE_WIDTHS = [
    2.5,
    1.2,
    1.5,
    1.5,
]

QUEUE_HEADERS = [
    "Patient",
    "Requested",
    "Status",
    "Action",
]


# ============================================================
# USER HELPERS
# ============================================================

def current_user():

    return (
        st.session_state.get("user")
        or {}
    )


def current_role_id():

    return current_user().get(
        "role_id"
    )


def current_hospital_id():

    return current_user().get(
        "hospital_id"
    )


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
# DATE / TIME
# ============================================================

def format_datetime(value):

    if not value:
        return "—"

    try:

        from datetime import datetime

        if isinstance(value, datetime):

            dt = value

        else:

            value = str(value)

            if value.endswith("Z"):

                value = value.replace(
                    "Z",
                    "+00:00",
                )

            dt = datetime.fromisoformat(
                value
            )

        if dt.tzinfo is not None:

            return dt.astimezone().strftime(
                "%B %d, %Y at %I:%M %p"
            )

        return dt.strftime(
            "%B %d, %Y at %I:%M %p"
        )

    except Exception:

        return str(value)


def examination_datetime(examination):

    return (
        examination.get(
            "examination_date"
        )
        or examination.get(
            "created_at"
        )
    )


# ============================================================
# STATE
# ============================================================

def clear_review_state():

    for key in (
        "review_examination",
        "review_patient",
        "review_history_patient",
        "review_previous_examinations",
        "review_previous_medical_records",
    ):

        st.session_state.pop(
            key,
            None,
        )


# ============================================================
# PREVIOUS EXAMINATIONS
# ============================================================

@st.dialog(
    "Examination Histories",
    width="large",
)
def show_previous_examinations(
    patient,
):

    patient_id = patient.get(
        "patient_id"
    )

    examinations = (
        get_examinations_by_patient(
            patient_id
        )
    )

    previous = [
        examination
        for examination in examinations
        if examination.get("status")
        in (
            "Completed",
            "Cancelled",
        )
    ]

    section_title(
        f"Previous Examinations ({len(previous)})"
    )

    if not previous:

        empty_state(
            "No previous examinations found."
        )

    else:

        for examination in sorted(
            previous,
            key=lambda item: (
                examination_datetime(item)
                or ""
            ),
            reverse=True,
        ):

            status = (
                examination.get(
                    "status"
                )
                or "Unknown"
            )

            status_tone = (
                "green"
                if status == "Completed"
                else "red"
            )

            st.markdown(
                f"### "
                f"{examination.get('examination_type') or 'Examination'}"
            )

            st.markdown(
                f"**Date & Time:** "
                f"{format_datetime(
                    examination_datetime(
                        examination
                    )
                )}"
            )

            st.markdown(
                f"**Status:** "
                f"{pill(
                    status,
                    status_tone
                )}",
                unsafe_allow_html=True,
            )

            st.markdown(
                f"**Chief Complaint:** "
                f"{examination.get('chief_complaint') or '—'}"
            )

            st.markdown(
                f"**Diagnosis:** "
                f"{examination.get('diagnosis') or '—'}"
            )

            st.markdown(
                f"**Plans / Orders:** "
                f"{examination.get('plans_orders') or '—'}"
            )

            st.markdown(
                f"**Disposition:** "
                f"{examination.get('disposition') or '—'}"
            )

            st.divider()

    if st.button(
        "Close",
        key="review_previous_exams_close",
        width="stretch",
    ):

        st.session_state.pop(
            "review_previous_examinations",
            None,
        )

        st.rerun()


# ============================================================
# PREVIOUS MEDICAL RECORDS
# ============================================================

@st.dialog(
    "Previous Medical Histories",
    width="large",
)
def show_previous_medical_records(
    patient,
):

    patient_id = patient.get(
        "patient_id"
    )

    records = (
        get_medical_records_by_patient(
            patient_id
        )
    )

    section_title(
        f"Previous Medical Records ({len(records)})"
    )

    if not records:

        empty_state(
            "No previous external medical records found."
        )

    else:

        for record in sorted(
            records,
            key=lambda item: (
                item.get("record_date")
                or item.get("created_at")
                or ""
            ),
            reverse=True,
        ):

            record_date = (
                record.get(
                    "record_date"
                )
                or record.get(
                    "created_at"
                )
            )

            st.markdown(
                f"### "
                f"{record.get('record_type') or 'Medical Record'}"
            )

            st.markdown(
                f"**Date & Time:** "
                f"{format_datetime(record_date)}"
            )

            st.markdown(
                f"**Facility:** "
                f"{record.get('facility_name') or '—'}"
            )

            st.markdown(
                f"**Diagnosis:** "
                f"{record.get('diagnosis') or '—'}"
            )

            st.markdown(
                f"**Treatment:** "
                f"{record.get('treatment') or '—'}"
            )

            st.markdown(
                f"**Notes:** "
                f"{record.get('notes') or '—'}"
            )

            st.divider()

    if st.button(
        "Close",
        key="review_previous_medical_close",
        width="stretch",
    ):

        st.session_state.pop(
            "review_previous_medical_records",
            None,
        )

        st.rerun()


# ============================================================
# PATIENT HISTORY
# ============================================================

def render_patient_history_buttons(
    patient,
    key_prefix,
):

    section_title(
        "Patient History"
    )

    st.caption(
        "Open each history separately to keep the review screen organized."
    )

    col1, col2 = st.columns(2)

    if col1.button(
        "View Examination Histories",
        key=f"{key_prefix}_exam_history",
        icon=":material/history:",
        width="stretch",
    ):

        st.session_state[
            "review_previous_examinations"
        ] = patient

        st.rerun()

    if col2.button(
        "View Previous Medical Histories",
        key=f"{key_prefix}_medical_history",
        icon=":material/medical_information:",
        width="stretch",
    ):

        st.session_state[
            "review_previous_medical_records"
        ] = patient

        st.rerun()


# ============================================================
# X-RAY REVIEW DIALOG
# ============================================================

@st.dialog(
    "Review Patient X-Ray",
    width="large",
)
def show_xray_review_dialog(
    patient,
    examination,
):

    user_id = current_user().get(
        "user_id"
    )

    examination_id = examination[
        "examination_id"
    ]

    with st.container(
        key="physician_xray_review_dialog"
    ):

        # ====================================================
        # PATIENT INFORMATION
        # ====================================================

        section_title(
            "Patient Information"
        )

        show_rows([
            (
                "Patient",
                patient_name(patient),
            ),
            (
                "Patient ID",
                patient_code(patient),
            ),
            (
                "Date of Birth",
                format_date(
                    patient.get(
                        "date_of_birth"
                    )
                ),
            ),
            (
                "Sex",
                patient.get("sex") or "—",
            ),
        ])

        st.divider()

        # ====================================================
        # HISTORY BUTTONS
        # ====================================================

        render_patient_history_buttons(
            patient,
            key_prefix=(
                f"xray_{examination_id}"
            ),
        )

        st.divider()

        # ====================================================
        # X-RAY REQUEST
        # ====================================================

        section_title(
            "X-Ray Examination"
        )

        request = (
            get_xray_request_by_examination(
                examination_id
            )
        )

        if not request:

            st.error(
                "No X-Ray request was found for this examination."
            )

            if st.button(
                "Close",
                key="xray_no_request_close",
                width="stretch",
            ):

                clear_review_state()
                st.rerun()

            return

        show_rows([
            (
                "Request Date",
                format_datetime(
                    request.get(
                        "created_at"
                    )
                ),
            ),
            (
                "Body Part",
                request.get(
                    "body_part"
                )
                or "Chest",
            ),
            (
                "Priority",
                request.get(
                    "priority"
                )
                or "Routine",
            ),
            (
                "Clinical Indication",
                request.get(
                    "clinical_indication"
                )
                or "—",
            ),
        ])

        # ====================================================
        # X-RAY IMAGE
        # ====================================================

        st.divider()

        section_title(
            "X-Ray Image"
        )

        images = (
            get_xray_images_by_request(
                request["request_id"]
            )
        )

        if not images:

            st.warning(
                "No X-Ray image has been uploaded yet."
            )

        else:

            latest_image = images[0]

            image_url = (
                get_xray_image_url(
                    latest_image[
                        "image_path"
                    ]
                )
            )

            if image_url:

                st.image(
                    image_url,
                    caption="Chest X-Ray",
                    width=500,
                )

            else:

                st.warning(
                    "The X-Ray image could not be loaded."
                )

            # =================================================
            # AI RESULT
            # =================================================

            ai_result = (
                get_xray_ai_result(
                    latest_image[
                        "image_id"
                    ]
                )
            )

            st.divider()

            section_title(
                "AI-Assisted Result"
            )

            if ai_result:

                findings = (
                    ai_result.get(
                        "ai_findings"
                    )
                    or "—"
                )

                confidence = (
                    ai_result.get(
                        "ai_confidence"
                    )
                    or 0
                )

                try:

                    confidence_value = (
                        float(confidence)
                    )

                    if confidence_value <= 1:

                        confidence_value *= 100

                except Exception:

                    confidence_value = 0

                normalized = (
                    str(findings)
                    .strip()
                    .lower()
                )

                tone = (
                    "red"
                    if normalized
                    in (
                        "positive",
                        "pneumonia",
                    )
                    else "green"
                )

                st.markdown(
                    f"**AI Finding:** "
                    f"{pill(
                        str(findings).upper(),
                        tone,
                    )}",
                    unsafe_allow_html=True,
                )

                st.markdown(
                    f"**Confidence:** "
                    f"{confidence_value:.1f}%"
                )

                st.caption(
                    "AI output is advisory only and "
                    "must be interpreted together with "
                    "the patient's clinical findings and "
                    "the physician's assessment."
                )

            else:

                st.info(
                    "No AI result is available for this image."
                )

        # ====================================================
        # CLINICAL CONTEXT
        # ====================================================

        st.divider()

        section_title(
            "Clinical Context"
        )

        st.markdown(
            f"**Chief Complaint:** "
            f"{examination.get('chief_complaint') or '—'}"
        )

        st.markdown(
            f"**History of Present Illness:** "
            f"{examination.get('history_of_present_illness') or '—'}"
        )

        st.markdown(
            f"**Physical Examination:** "
            f"{examination.get('physical_examination') or '—'}"
        )

        # ====================================================
        # X-RAY INTERPRETATION
        # ====================================================

        st.divider()

        section_title(
            "Physician X-Ray Interpretation"
        )

        findings = st.text_area(
            "Findings",
            value="",
            height=120,
            key=f"xray_{examination_id}_findings",
            help=(
                "Describe the relevant findings seen "
                "on the chest X-Ray."
            ),
        )

        impression = st.text_area(
            "Impression",
            value="",
            height=120,
            key=f"xray_{examination_id}_impression",
            help=(
                "Provide the clinical interpretation "
                "or impression."
            ),
        )

        # ====================================================
        # FINAL ASSESSMENT
        # ====================================================

        st.divider()

        section_title(
            "Final Assessment"
        )

        diagnosis = st.text_area(
            "Diagnosis / Assessment",
            value=(
                examination.get(
                    "diagnosis"
                )
                or ""
            ),
            height=100,
            key=f"xray_{examination_id}_diagnosis",
        )

        plans = st.text_area(
            "Plans / Orders",
            value=(
                examination.get(
                    "plans_orders"
                )
                or ""
            ),
            height=100,
            key=f"xray_{examination_id}_plans",
        )

        # ====================================================
        # DISPOSITION
        # ====================================================

        st.divider()

        section_title(
            "Disposition"
        )

        disposition_options = [
            "Admission",
            "Treated and Sent Home",
            "Referred",
            "Refused Admission",
            "Nowhere When Called",
        ]

        current_disposition = (
            examination.get(
                "disposition"
            )
        )

        disposition_index = (
            disposition_options.index(
                current_disposition
            )
            if current_disposition
            in disposition_options
            else 0
        )

        disposition = st.selectbox(
            "Disposition",
            disposition_options,
            index=disposition_index,
            key=f"xray_{examination_id}_disposition",
        )

        disposition_notes = st.text_area(
            "Disposition Notes",
            value=(
                examination.get(
                    "disposition_notes"
                )
                or ""
            ),
            height=100,
            key=f"xray_{examination_id}_disposition_notes",
        )

        # ====================================================
        # ACTIONS
        # ====================================================

        st.divider()

        cancel_col, save_col = st.columns(2)

        cancel_clicked = cancel_col.button(
            "Cancel",
            key=f"xray_{examination_id}_cancel",
            width="stretch",
        )

        save_clicked = save_col.button(
            "Save & Complete",
            key=f"xray_{examination_id}_save",
            type="primary",
            width="stretch",
        )

    # ========================================================
    # CANCEL
    # ========================================================

    if cancel_clicked:

        clear_review_state()

        st.rerun()

    if not save_clicked:
        return

    # ========================================================
    # VALIDATION
    # ========================================================

    if not diagnosis.strip():

        st.error(
            "Diagnosis / Assessment is required."
        )

        return

    if not findings.strip():

        st.error(
            "X-Ray findings are required."
        )

        return

    # ========================================================
    # SAVE
    # ========================================================

    try:

        save_xray_review(
            request_id=request[
                "request_id"
            ],
            reviewed_by=user_id,
            findings=(
                findings.strip()
                or None
            ),
            impression=(
                impression.strip()
                or None
            ),
        )

        update_examination(
            examination_id=examination_id,
            status="Completed",
            reviewed_by=user_id,
            diagnosis=(
                diagnosis.strip()
                or None
            ),
            plans_orders=(
                plans.strip()
                or None
            ),
            disposition=disposition,
            disposition_notes=(
                disposition_notes.strip()
                or None
            ),
        )

        clear_review_state()

        remember(
            "X-Ray reviewed successfully. "
            "Examination completed."
        )

        st.rerun()

    except Exception as error:

        st.error(
            f"Failed to save X-Ray review: {error}"
        )


# ============================================================
# REVIEW TABLE
# ============================================================

def render_review_table(
    examinations,
    key_prefix="review",
):

    if not examinations:

        empty_state(
            "No patients are currently waiting for X-Ray review."
        )

        return

    with st.container(
        key="physician_review_table"
    ):

        table_header(
            QUEUE_HEADERS,
            QUEUE_WIDTHS,
            key_prefix,
        )

        for examination in examinations:

            patient = (
                examination.get(
                    "patients"
                )
                or {}
            )

            patient_id = patient.get(
                "patient_id"
            )

            examination_id = examination.get(
                "examination_id"
            )

            request_time = (
                examination.get(
                    "updated_at"
                )
                or examination.get(
                    "created_at"
                )
            )

            with table_row(
                f"review_row_{examination_id}",
                QUEUE_WIDTHS,
            ) as columns:

                name_cell(
                    columns[0],
                    patient_name(patient),
                    sub=patient_code(patient),
                )

                text_cell(
                    columns[1],
                    format_datetime(
                        request_time
                    ),
                )

                pill_cell(
                    columns[2],
                    "X-Ray Ready",
                    "green",
                )

                if columns[3].button(
                    "Review",
                    key=(
                        f"{key_prefix}_review_"
                        f"{examination_id}"
                    ),
                    icon=":material/radiology:",
                    type="primary",
                    width="stretch",
                ):

                    clear_review_state()

                    st.session_state[
                        "review_examination"
                    ] = examination

                    st.session_state[
                        "review_patient"
                    ] = patient

                    st.rerun()


# ============================================================
# METRICS
# ============================================================

def render_metrics(
    examinations,
):

    total = len(examinations)

    patients = len({
        (
            examination.get(
                "patients",
                {}
            ).get(
                "patient_id"
            )
        )
        for examination in examinations
    })

    m1, m2 = st.columns(2)

    with m1:

        metric_card(
            "X-Ray ready",
            total,
            "examinations",
            tone="blue",
        )

    with m2:

        metric_card(
            "Patients to review",
            patients,
            "patients",
            tone="amber",
        )


# ============================================================
# PAGE
# ============================================================

def show():

    load_css(
        "manage_examinations.css"
    )

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

        st.error(
            "You don't have access to Review Patient."
        )

        return

    with st.container(
        key="physician_review_patient_page"
    ):

        page_header(
            "Review Patient",
            "Review completed chest X-Rays and finalize the patient's examination.",
        )

        if st.button(
            "Refresh",
            icon=":material/refresh:",
            key="review_patient_refresh",
            width="stretch",
        ):

            st.rerun()

        try:

            xray_ready = (
                get_xray_ready_examinations(
                    hospital_id=filter_hospital
                )
            )

        except Exception as error:

            st.error(
                f"Failed to load X-Ray ready examinations: {error}"
            )

            xray_ready = []

        render_metrics(
            xray_ready
        )

        st.divider()

        section_title(
            "X-Ray Ready for Review"
        )

        st.caption(
            "Patients appear here after their requested "
            "chest X-Ray has been uploaded and marked ready."
        )

        render_review_table(
            xray_ready,
            key_prefix="review",
        )

    # ========================================================
    # DIALOGS
    # ========================================================

    if st.session_state.get(
        "review_examination"
    ):

        examination = (
            st.session_state[
                "review_examination"
            ]
        )

        patient = (
            st.session_state.get(
                "review_patient"
            )
        )

        if patient:

            show_xray_review_dialog(
                patient,
                examination,
            )

    elif st.session_state.get(
        "review_previous_examinations"
    ):

        show_previous_examinations(
            st.session_state[
                "review_previous_examinations"
            ]
        )

    elif st.session_state.get(
        "review_previous_medical_records"
    ):

        show_previous_medical_records(
            st.session_state[
                "review_previous_medical_records"
            ]
        )