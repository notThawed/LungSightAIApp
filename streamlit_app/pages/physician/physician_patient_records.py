import streamlit as st

from datetime import datetime
from zoneinfo import ZoneInfo


from backend.fetches import (
    get_completed_patient_records,
    get_examinations_by_patient,
    get_examination_consents,
    get_examination_vitals,
    get_medical_records_by_patient,
    get_xray_request_by_examination,
    get_xray_images_by_request,
    get_xray_image_url,
    get_xray_ai_result,
    get_xray_review,
    get_medications_by_examination,
    get_referral_by_examination,
)


from streamlit_app.components.ui import (
    page_header,
    empty_state,
    section_title,
    show_rows,
    full_name,
    format_date,
    pill,
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
# CONFIGURATION
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


PATIENT_WIDTHS = [
    1.4,
    2.7,
    1.5,
    0.9,
    1.7,
    1.0,
]


PATIENT_HEADERS = [
    "Patient ID",
    "Patient",
    "Date of birth",
    "Sex",
    "Contact",
    "View",
]


EXAMINATION_WIDTHS = [
    1.8,
    2.0,
    1.8,
    1.5,
]


EXAMINATION_HEADERS = [
    "Completed",
    "Examination",
    "Diagnosis",
    "Status",
]


STATUS_TONES = {
    "Completed": "green",
    "Pending": "amber",
    "In Progress": "blue",
    "Cancelled": "red",
}


MANILA_TZ = ZoneInfo(
    "Asia/Manila"
)


# ============================================================
# USER HELPERS
# ============================================================

def current_user():

    return (
        st.session_state.get(
            "user"
        )
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


def patient_name(
    patient,
):

    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )


def patient_code(
    patient,
):

    return (
        patient.get("patient_code")
        or patient.get("patient_id")
    )


def hospital_name(
    patient,
):

    hospitals = patient.get(
        "hospitals"
    )

    if isinstance(
        hospitals,
        dict,
    ):

        return (
            hospitals.get(
                "hospital_name"
            )
            or "—"
        )

    if isinstance(
        hospitals,
        list,
    ) and hospitals:

        return (
            hospitals[0].get(
                "hospital_name"
            )
            or "—"
        )

    return "—"


# ============================================================
# DATE / TIME HELPERS
# ============================================================

def parse_datetime(
    value,
):

    if not value:

        return None

    if isinstance(
        value,
        datetime,
    ):

        parsed = value

    else:

        try:

            parsed = datetime.fromisoformat(
                str(value).replace(
                    "Z",
                    "+00:00",
                )
            )

        except (
            ValueError,
            TypeError,
        ):

            return None

    if parsed.tzinfo is None:

        parsed = parsed.replace(
            tzinfo=MANILA_TZ
        )

    return parsed.astimezone(
        MANILA_TZ
    )


def get_completion_datetime(
    examination,
):

    return (
        examination.get(
            "time_of_discharge"
        )
        or examination.get(
            "reviewed_at"
        )
    )


def format_completion_datetime(
    examination,
):

    completed_at = get_completion_datetime(
        examination
    )

    parsed = parse_datetime(
        completed_at
    )

    if not parsed:

        return "—"

    return parsed.strftime(
        "%B %d, %Y • %I:%M %p"
    )


def format_completion_date(
    examination,
):

    completed_at = get_completion_datetime(
        examination
    )

    parsed = parse_datetime(
        completed_at
    )

    if not parsed:

        return "—"

    return parsed.strftime(
        "%B %d, %Y"
    )


def format_completion_time(
    examination,
):

    completed_at = get_completion_datetime(
        examination
    )

    parsed = parse_datetime(
        completed_at
    )

    if not parsed:

        return "—"

    return parsed.strftime(
        "%I:%M %p"
    )


# ============================================================
# EXAMINATION TYPE HELPERS
# ============================================================

def is_follow_up_examination(examination):
    """
    Determines whether an examination is a follow-up.
    Priority:
      1. follow_up_sequence is not None  -> follow-up
      2. examination_type contains "follow-up"/"follow up"
    """

    sequence = examination.get("follow_up_sequence")

    if sequence is not None:
        try:
            if int(sequence) > 0:
                return True
        except (TypeError, ValueError):
            # sequence is present but not a usable int — still treat as follow-up
            return True

    examination_type = examination.get("examination_type") or ""

    normalized = (
        str(examination_type)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )

    return (
        "follow up" in normalized
        or "followup" in normalized
    )


def get_follow_up_sequence(examination):
    """
    Safely returns the follow-up sequence number.
    Falls back to deriving it from examination_type
    (e.g. "Follow-Up Examination 003") when the
    database column is missing.
    """

    value = examination.get("follow_up_sequence")

    if value is not None:
        try:
            sequence = int(value)
            if sequence > 0:
                return sequence
        except (TypeError, ValueError):
            pass

    # Fallback: parse trailing digits from examination_type
    examination_type = examination.get("examination_type") or ""

    import re
    match = re.search(r"(\d+)\s*$", str(examination_type))

    if match:
        try:
            sequence = int(match.group(1))
            if sequence > 0:
                return sequence
        except (TypeError, ValueError):
            pass

    return None



def get_display_examination_type(
    examination,
):
    """
    Returns the examination type exactly as it
    should appear in Patient Records.

    Follow-up examinations are displayed using
    their stored follow-up sequence:

        Follow-Up Examination 001
        Follow-Up Examination 002
        Follow-Up Examination 003

    General examinations retain their original
    examination type.
    """

    examination_type = (
        examination.get(
            "examination_type"
        )
        or "General Consultation"
    )

    # --------------------------------------------------------
    # GENERAL EXAMINATION
    # --------------------------------------------------------

    if not is_follow_up_examination(
        examination
    ):

        return examination_type

    # --------------------------------------------------------
    # FOLLOW-UP EXAMINATION
    # --------------------------------------------------------

    sequence = get_follow_up_sequence(
        examination
    )

    if sequence is not None:

        return (
            "Follow-Up Examination "
            f"{sequence:03d}"
        )

    # --------------------------------------------------------
    # FALLBACK FOR OLD RECORDS
    # --------------------------------------------------------

    return "Follow-Up Examination"


def sort_follow_up_examinations(
    examinations,
):
    """
    Sort follow-up examinations by their
    follow-up sequence.

    Example:

        003
        001
        002

    becomes:

        001
        002
        003

    Examinations without a sequence are placed
    after numbered follow-ups.
    """

    def sort_key(
        examination,
    ):

        sequence = get_follow_up_sequence(
            examination
        )

        if sequence is None:

            return (
                1,
                999999,
            )

        return (
            0,
            sequence,
        )

    return sorted(
        examinations,
        key=sort_key,
    )


def split_examination_history(
    examinations,
):

    general_consults = []

    follow_up_examinations = []

    for examination in examinations:

        if is_follow_up_examination(
            examination
        ):

            follow_up_examinations.append(
                examination
            )

        else:

            general_consults.append(
                examination
            )

    # --------------------------------------------------------
    # SORT FOLLOW-UPS BY SEQUENCE
    # --------------------------------------------------------

    follow_up_examinations = (
        sort_follow_up_examinations(
            follow_up_examinations
        )
    )

    return (
        general_consults,
        follow_up_examinations,
    )


# ============================================================
# STATE
# ============================================================

def open_patient_record(
    patient,
):

    st.session_state[
        "physician_selected_patient"
    ] = patient

    st.rerun()


def clear_selected_patient():

    st.session_state.pop(
        "physician_selected_patient",
        None,
    )


# ============================================================
# PATIENT SUMMARY
# ============================================================

def patient_summary_rows(
    patient,
):

    return [

        (
            "Patient",
            patient_name(patient),
        ),

        (
            "Patient ID",
            patient_code(patient),
        ),

        (
            "Date of birth",
            format_date(
                patient.get(
                    "date_of_birth"
                )
            ),
        ),

        (
            "Sex",
            patient.get(
                "sex"
            )
            or "—",
        ),

        (
            "Contact",
            patient.get(
                "contact_number"
            )
            or "—",
        ),

        (
            "Hospital",
            hospital_name(
                patient
            ),
        ),

    ]


# ============================================================
# LOAD PATIENTS
# ============================================================

def load_patients():

    hospital_id = current_hospital_id()

    role_id = current_role_id()

    if role_id == ROLE_SUPERADMIN:

        filter_hospital = None

    elif role_id in DOCTOR_ROLES:

        filter_hospital = hospital_id

    elif role_id == ROLE_HOSPITAL_ADMIN:

        filter_hospital = hospital_id

    else:

        return []

    try:

        return (
            get_completed_patient_records(
                hospital_id=filter_hospital
            )
            or []
        )

    except Exception as error:

        st.error(
            "Failed to load patient records: "
            f"{error}"
        )

        return []


# ============================================================
# FILTER PATIENTS
# ============================================================

def filter_patients(
    patients,
):

    search = st.text_input(
        "Search patient",
        placeholder=(
            "Search by patient ID, name, "
            "or contact number"
        ),
        key="physician_patient_records_search",
    ).strip().lower()

    if not search:

        return patients

    filtered = []

    for patient in patients:

        values = [

            patient_code(
                patient
            ),

            patient_name(
                patient
            ),

            patient.get(
                "contact_number"
            ),

        ]

        searchable = " ".join(
            str(value or "")
            for value in values
        ).lower()

        if search in searchable:

            filtered.append(
                patient
            )

    return filtered


# ============================================================
# PATIENT TABLE
# ============================================================

def render_patient_table(
    patients,
):

    if not patients:

        empty_state(
            "No completed patient records found."
        )

        return

    with st.container(
        key="physician_patient_records_table"
    ):

        table_header(
            PATIENT_HEADERS,
            PATIENT_WIDTHS,
            "physician_records",
        )

        for patient in patients:

            patient_id = patient.get(
                "patient_id"
            )

            with table_row(
                f"patient_record_{patient_id}",
                PATIENT_WIDTHS,
            ) as columns:

                text_cell(
                    columns[0],
                    patient_code(
                        patient
                    ),
                )

                name_cell(
                    columns[1],
                    patient_name(
                        patient
                    ),
                )

                text_cell(
                    columns[2],
                    format_date(
                        patient.get(
                            "date_of_birth"
                        )
                    ),
                )

                text_cell(
                    columns[3],
                    patient.get(
                        "sex"
                    ),
                )

                text_cell(
                    columns[4],
                    patient.get(
                        "contact_number"
                    )
                    or "—",
                )

                if columns[5].button(
                    "View",
                    key=(
                        "view_physician_patient_"
                        f"{patient_id}"
                    ),
                    width="stretch",
                    icon=":material/visibility:",
                ):

                    open_patient_record(
                        patient
                    )


# ============================================================
# EXAMINATION DETAILS
# ============================================================

def render_examination(
    examination,
    index,
):

    examination_id = examination.get(
        "examination_id"
    )

    examination_date = (
        examination.get(
            "examination_date"
        )
        or examination.get(
            "created_at"
        )
    )

    status = (
        examination.get(
            "status"
        )
        or "—"
    )

    completed_datetime = (
        format_completion_datetime(
            examination
        )
    )

    # --------------------------------------------------------
    # DISPLAY EXAMINATION TYPE
    # --------------------------------------------------------

    examination_type = (
        get_display_examination_type(
            examination
        )
    )

    with st.expander(
        (
            f"{examination_type} • "
            f"{status} • "
            f"{completed_datetime}"
        ),
        expanded=(
            index == 1
        ),
    ):

        # ----------------------------------------------------
        # BASIC EXAMINATION INFORMATION
        # ----------------------------------------------------

        section_title(
            "Examination information"
        )

        show_rows([

            (
                "Examination type",
                examination_type,
            ),

            (
                "Status",
                status,
            ),

            (
                "Completed date",
                format_completion_date(
                    examination
                ),
            ),

            (
                "Completed time",
                format_completion_time(
                    examination
                ),
            ),

            (
                "Examination date",
                format_date(
                    examination_date
                ),
            ),

            (
                "Chief complaint",
                examination.get(
                    "chief_complaint"
                )
                or "—",
            ),

            (
                "History of present illness",
                examination.get(
                    "history_of_present_illness"
                )
                or "—",
            ),

            (
                "Physical examination",
                examination.get(
                    "physical_examination"
                )
                or "—",
            ),

            (
                "Diagnosis",
                examination.get(
                    "diagnosis"
                )
                or "—",
            ),

            (
                "Plans / Orders",
                examination.get(
                    "plans_orders"
                )
                or "—",
            ),

            (
                "Disposition",
                examination.get(
                    "disposition"
                )
                or "—",
            ),

            (
                "Disposition notes",
                examination.get(
                    "disposition_notes"
                )
                or "—",
            ),

            (
                "Follow-up date",
                format_date(
                    examination.get(
                        "follow_up_date"
                    )
                ),
            ),

            (
                "Follow-up notes",
                examination.get(
                    "follow_up_notes"
                )
                or "—",
            ),

        ])

        # ----------------------------------------------------
        # VITALS
        # ----------------------------------------------------

        section_title(
            "Vitals"
        )

        vitals = (
            get_examination_vitals(
                examination_id
            )
            or []
        )

        if not vitals:

            st.caption(
                "No vitals recorded."
            )

        else:

            latest_vitals = vitals[0]

            show_rows([

                (
                    "Blood pressure",
                    (
                        f"{latest_vitals.get('bp_systolic') or '—'}"
                        "/"
                        f"{latest_vitals.get('bp_diastolic') or '—'}"
                        " mmHg"
                    ),
                ),

                (
                    "Temperature",
                    (
                        f"{latest_vitals.get('temperature') or '—'}"
                        " °C"
                    ),
                ),

                (
                    "Pulse rate",
                    (
                        f"{latest_vitals.get('pulse_rate') or '—'}"
                        " bpm"
                    ),
                ),

                (
                    "Respiratory rate",
                    (
                        f"{latest_vitals.get('respiratory_rate') or '—'}"
                        " /min"
                    ),
                ),

                (
                    "SpO₂",
                    (
                        f"{latest_vitals.get('spo2') or '—'}"
                        " %"
                    ),
                ),

                (
                    "Heart rate",
                    (
                        f"{latest_vitals.get('heart_rate') or '—'}"
                        " bpm"
                    ),
                ),

                (
                    "Weight",
                    (
                        f"{latest_vitals.get('weight_kg') or '—'}"
                        " kg"
                    ),
                ),

                (
                    "Height",
                    (
                        f"{latest_vitals.get('height_cm') or '—'}"
                        " cm"
                    ),
                ),

                (
                    "BMI",
                    latest_vitals.get(
                        "bmi"
                    )
                    or "—",
                ),

            ])

        # ----------------------------------------------------
        # X-RAY
        # ----------------------------------------------------

        section_title(
            "Chest X-Ray"
        )

        request = (
            get_xray_request_by_examination(
                examination_id
            )
        )

        if not request:

            st.caption(
                "No X-Ray request found for this examination."
            )

        else:

            show_rows([

                (
                    "Body part",
                    request.get(
                        "body_part"
                    )
                    or "—",
                ),

                (
                    "Priority",
                    request.get(
                        "priority"
                    )
                    or "—",
                ),

                (
                    "Clinical indication",
                    request.get(
                        "clinical_indication"
                    )
                    or "—",
                ),

                (
                    "X-Ray status",
                    request.get(
                        "status"
                    )
                    or "—",
                ),

            ])

            images = (
                get_xray_images_by_request(
                    request.get(
                        "request_id"
                    )
                )
                or []
            )

            if images:

                st.markdown(
                    "**X-Ray image**"
                )

                image = images[0]

                image_url = (
                    get_xray_image_url(
                        image.get(
                            "image_path"
                        )
                    )
                )

                if image_url:

                    st.image(
                        image_url,
                        width="stretch",
                    )

                else:

                    st.warning(
                        "Unable to generate the X-Ray image URL."
                    )

                # --------------------------------------------
                # AI RESULT
                # --------------------------------------------

                ai_result = (
                    get_xray_ai_result(
                        image.get(
                            "image_id"
                        )
                    )
                )

                if ai_result:

                    section_title(
                        "AI result"
                    )

                    show_rows([

                        (
                            "Finding",
                            ai_result.get(
                                "ai_findings"
                            )
                            or "—",
                        ),

                        (
                            "Confidence",
                            (
                                f"{ai_result.get('ai_confidence')}"
                                if ai_result.get(
                                    "ai_confidence"
                                )
                                is not None
                                else "—"
                            ),
                        ),

                        (
                            "Model version",
                            ai_result.get(
                                "ai_model_version"
                            )
                            or "—",
                        ),

                    ])

            # ------------------------------------------------
            # PHYSICIAN X-RAY REVIEW
            # ------------------------------------------------

            review = (
                get_xray_review(
                    request.get(
                        "request_id"
                    )
                )
            )

            if review:

                section_title(
                    "Physician X-Ray review"
                )

                show_rows([

                    (
                        "Findings",
                        review.get(
                            "findings"
                        )
                        or "—",
                    ),

                    (
                        "Impression",
                        review.get(
                            "impression"
                        )
                        or "—",
                    ),

                ])

        # ----------------------------------------------------
        # MEDICATIONS
        # ----------------------------------------------------

        section_title(
            "Medications"
        )

        medications = (
            get_medications_by_examination(
                examination_id
            )
            or []
        )

        if not medications:

            st.caption(
                "No medications recorded."
            )

        else:

            for medication in medications:

                st.markdown(
                    f"**{medication.get('drug_name') or 'Medication'}**"
                )

                st.caption(
                    " • ".join([
                        str(
                            medication.get(
                                "dose"
                            )
                            or "No dose"
                        ),
                        str(
                            medication.get(
                                "frequency"
                            )
                            or "No frequency"
                        ),
                        str(
                            medication.get(
                                "duration"
                            )
                            or "No duration"
                        ),
                    ])
                )

                if medication.get(
                    "notes"
                ):

                    st.caption(
                        medication.get(
                            "notes"
                        )
                    )

        # ----------------------------------------------------
        # REFERRAL
        # ----------------------------------------------------

        referral = (
            get_referral_by_examination(
                examination_id
            )
        )

        if referral:

            section_title(
                "Referral"
            )

            show_rows([

                (
                    "Referred to",
                    referral.get(
                        "referred_to"
                    )
                    or "—",
                ),

                (
                    "Reason",
                    referral.get(
                        "reason"
                    )
                    or "—",
                ),

                (
                    "Urgency",
                    referral.get(
                        "urgency"
                    )
                    or "—",
                ),

                (
                    "Notes",
                    referral.get(
                        "notes"
                    )
                    or "—",
                ),

            ])

        # ----------------------------------------------------
        # CONSENT
        # ----------------------------------------------------

        consents = (
            get_examination_consents(
                examination_id
            )
            or []
        )

        if consents:

            section_title(
                "Consent"
            )

            consent = consents[0]

            show_rows([

                (
                    "Consent type",
                    consent.get(
                        "consent_type"
                    )
                    or "—",
                ),

                (
                    "Given",
                    (
                        "Yes"
                        if consent.get(
                            "given"
                        )
                        else "No"
                    ),
                ),

                (
                    "Signed by",
                    consent.get(
                        "signed_by_name"
                    )
                    or "—",
                ),

                (
                    "Signed by type",
                    consent.get(
                        "signed_by_type"
                    )
                    or "—",
                ),

            ])


# ============================================================
# EXAMINATION HISTORY SECTION
# ============================================================

def render_examination_history_section(
    title,
    examinations,
    empty_message,
):

    section_title(
        title
    )

    if not examinations:

        st.caption(
            empty_message
        )

        return

    for index, examination in enumerate(
        examinations,
        start=1,
    ):

        render_examination(
            examination,
            index,
        )


# ============================================================
# EXTERNAL MEDICAL RECORDS
# ============================================================

def render_external_records(
    patient,
):

    section_title(
        "External Medical Records"
    )

    records = (
        get_medical_records_by_patient(
            patient.get(
                "patient_id"
            )
        )
        or []
    )

    if not records:

        st.caption(
            "No external medical records found."
        )

        return

    for record in records:

        with st.expander(
            (
                f"{record.get('record_type') or 'Medical Record'}"
                " • "
                f"{format_date(record.get('record_date'))}"
            ),
            expanded=False,
        ):

            show_rows([

                (
                    "Facility",
                    record.get(
                        "facility_name"
                    )
                    or "—",
                ),

                (
                    "Department",
                    record.get(
                        "department"
                    )
                    or "—",
                ),

                (
                    "Attending physician",
                    record.get(
                        "attending_physician"
                    )
                    or "—",
                ),

                (
                    "Chief complaint",
                    record.get(
                        "chief_complaint"
                    )
                    or "—",
                ),

                (
                    "Clinical history",
                    record.get(
                        "clinical_history"
                    )
                    or "—",
                ),

                (
                    "Diagnosis",
                    record.get(
                        "diagnosis"
                    )
                    or "—",
                ),

                (
                    "Procedure",
                    record.get(
                        "procedure_name"
                    )
                    or "—",
                ),

                (
                    "Findings",
                    record.get(
                        "findings"
                    )
                    or "—",
                ),

                (
                    "Impression",
                    record.get(
                        "impression"
                    )
                    or "—",
                ),

                (
                    "Treatment",
                    record.get(
                        "treatment"
                    )
                    or "—",
                ),

                (
                    "Follow-up",
                    record.get(
                        "follow_up"
                    )
                    or "—",
                ),

            ])


# ============================================================
# PATIENT RECORD VIEW
# ============================================================

def render_patient_record(
    patient,
):

    patient_id = patient.get(
        "patient_id"
    )

    if st.button(
        "Back to Patient Records",
        icon=":material/arrow_back:",
        key="back_to_physician_patient_records",
    ):

        clear_selected_patient()

        st.rerun()

    st.divider()

    page_header(
        patient_name(patient),
        (
            f"Patient ID: {patient_code(patient)}"
        ),
    )

    section_title(
        "Patient information"
    )

    show_rows(
        patient_summary_rows(
            patient
        )
    )

    st.divider()

    examinations = (
        get_examinations_by_patient(
            patient_id
        )
        or []
    )

    completed_examinations = [
        examination
        for examination in examinations
        if examination.get(
            "status"
        ) == "Completed"
    ]

    general_consults, follow_up_examinations = (
        split_examination_history(
            completed_examinations
        )
    )

    # ========================================================
    # GENERAL CONSULT EXAMINATION HISTORY
    # ========================================================

    render_examination_history_section(
        "General Consult Examination History",
        general_consults,
        "No completed general consultation examinations found.",
    )

    st.divider()

    # ========================================================
    # FOLLOW-UP EXAMINATION HISTORY
    # ========================================================

    render_examination_history_section(
        "Follow-Up Examination History",
        follow_up_examinations,
        "No completed follow-up examinations found.",
    )

    st.divider()

    # ========================================================
    # EXTERNAL MEDICAL RECORDS
    # ========================================================

    render_external_records(
        patient
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

    if role_id not in (
        DOCTOR_ROLES
        + ADMIN_ROLES
    ):

        st.error(
            "You don't have access to Patient Records."
        )

        return

    selected_patient = (
        st.session_state.get(
            "physician_selected_patient"
        )
    )

    # ========================================================
    # SELECTED PATIENT
    # ========================================================

    if selected_patient:

        render_patient_record(
            selected_patient
        )

        return

    # ========================================================
    # PATIENT LIST
    # ========================================================

    with st.container(
        key="physician_patient_records_page"
    ):

        page_header(
            "Patient Records",
            (
                "View completed patient examinations, "
                "X-Ray results, physician reviews, "
                "and medical history."
            ),
        )

        if st.button(
            "Refresh",
            icon=":material/refresh:",
            key="physician_patient_records_refresh",
            width="stretch",
        ):

            st.rerun()

        patients = load_patients()

        patients = filter_patients(
            patients
        )

        st.divider()

        section_title(
            "Patients"
        )

        st.caption(
            (
                "Each patient appears only once. "
                "Select a patient to view their complete "
                "examination history."
            )
        )

        render_patient_table(
            patients
        )