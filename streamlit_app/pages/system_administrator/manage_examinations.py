import io

from datetime import date

import streamlit as st

from streamlit_drawable_canvas import st_canvas

from backend.fetches import (
    get_all_patients,
    get_all_hospitals,
    get_examinations_by_patient,
    get_examination_consents,
    get_examination_vitals,
    get_medical_records_by_patient,
    get_medical_record_images,
    get_consent_signature_url,
    get_medical_record_file_url,
)

from backend.crud import (
    create_examination,
    update_examination,
    update_examination_vitals,
    update_examination_consent,
    upload_consent_signature,
    delete_examination,
)

from streamlit_app.components.ui import (
    load_css,
    page_header,
    empty_state,
    section_title,
    show_rows,
    full_name,
    format_date,
    table_header,
    table_row,
    name_cell,
    text_cell,
    pill_cell,
    remember,
    show_flash_message,
    confirm_buttons,
)


# ============================================================
# CONFIG
# ============================================================

WIDTHS = [
    1.3,
    3,
    1.5,
    0.9,
    1.8,
    1.4,
]

WIDTHS_SUPERADMIN = [
    1.6,
    1.3,
    2.6,
    1.3,
    0.8,
    1.5,
    1.2,
]

HEADERS = [
    "Patient ID",
    "Name",
    "Date of birth",
    "Sex",
    "Contact",
    "",
]

HEADERS_SUPERADMIN = [
    "Hospital",
    "Patient ID",
    "Name",
    "Date of birth",
    "Sex",
    "Contact",
    "",
]


HISTORY_WIDTHS = [
    1.5,
    2,
    1.4,
    1,
]

HISTORY_HEADERS = [
    "Date",
    "Type",
    "Status",
    "View",
]


MEDICAL_HISTORY_WIDTHS = [
    1.4,
    1.7,
    2.4,
    1,
]

MEDICAL_HISTORY_HEADERS = [
    "Date",
    "Record type",
    "Facility",
    "View",
]


STATUS_TONES = {
    "Completed": "green",
    "Pending": "amber",
    "In Progress": "blue",
    "Awaiting X-Ray": "amber",
    "X-Ray Ready": "blue",
    "Cancelled": "red",
}


# ============================================================
# ROLE IDs
# ============================================================

ROLE_SUPERADMIN = 1
ROLE_RADIOLOGIST = 3
ROLE_RADTECH = 4
ROLE_HOSPITAL_ADMIN = 6
ROLE_STAFF = 7

ADMIN_ROLES = [
    ROLE_SUPERADMIN,
    ROLE_HOSPITAL_ADMIN,
]

NURSE_ROLES = [
    ROLE_STAFF,
]


FIXED_EXAM_TYPE = "General Consult"


# ============================================================
# HELPERS
# ============================================================

def load_patients():

    try:
        return get_all_patients() or []

    except Exception as error:

        st.error(
            f"Unable to load patients: {error}"
        )

        return []


def patient_name(patient):

    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )


def patient_code(patient):

    return (
        patient.get(
            "patient_code"
        )
        or patient.get(
            "patient_id"
        )
    )


def patient_hospital_name(patient):

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


def patient_summary_rows(
    patient
):

    return [
        (
            "Patient",
            patient_name(
                patient
            ),
        ),
        (
            "Patient ID",
            patient_code(
                patient
            ),
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
            ),
        ),
        (
            "Contact",
            patient.get(
                "contact_number"
            ),
        ),
        (
            "Hospital",
            patient_hospital_name(
                patient
            ),
        ),
    ]


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


def is_superadmin():

    return (
        current_role_id()
        == ROLE_SUPERADMIN
    )


def is_admin_role():

    return (
        current_role_id()
        in ADMIN_ROLES
    )


def is_nurse_role():

    return (
        current_role_id()
        in NURSE_ROLES
    )


def is_minor(
    date_of_birth
):

    if not date_of_birth:
        return False

    try:

        dob = date.fromisoformat(
            str(
                date_of_birth
            )[:10]
        )

    except (
        ValueError,
        TypeError,
    ):

        return False

    today = date.today()

    age = (
        today.year
        - dob.year
        - (
            (
                today.month,
                today.day,
            )
            <
            (
                dob.month,
                dob.day,
            )
        )
    )

    return age < 18


def _get_vitals_value(
    vitals,
    field_name,
):

    for vital in vitals:

        if vital.get(
            field_name
        ) is not None:

            return vital[
                field_name
            ]

    return None


# ============================================================
# DIALOG STATE
# ============================================================

def open_dialog(
    name,
    **state,
):

    st.session_state[
        "examination_dialog"
    ] = name

    for key, value in state.items():

        st.session_state[
            key
        ] = value

    st.rerun()


def close_dialog():

    st.session_state[
        "examination_dialog"
    ] = None


# ============================================================
# PATIENT EXAMINATION HISTORY
# ============================================================

@st.dialog(
    "Patient Examination History",
    width="large",
)
def show_patient_history(
    patient
):

    examinations = (
        get_examinations_by_patient(
            patient["patient_id"]
        )
    )

    medical_records = (
        get_medical_records_by_patient(
            patient["patient_id"]
        )
    )

    with st.container(
        key="sa_dialog"
    ):

        # ----------------------------------------------------
        # PATIENT INFORMATION
        # ----------------------------------------------------

        section_title(
            "Patient Information"
        )

        show_rows(
            patient_summary_rows(
                patient
            )
        )

        # ----------------------------------------------------
        # EXAMINATION HISTORIES
        # ----------------------------------------------------

        section_title(
            "Examination Histories"
        )

        if not examinations:

            empty_state(
                "No examination records found for this patient."
            )

        else:

            with st.container(
                key="sa_table_exam_history"
            ):

                table_header(
                    HISTORY_HEADERS,
                    HISTORY_WIDTHS,
                    "exam_history",
                )

                for examination in examinations:

                    exam_id = examination[
                        "examination_id"
                    ]

                    status = (
                        examination.get(
                            "status"
                        )
                        or "—"
                    )

                    with table_row(
                        f"exam_history_{exam_id}",
                        HISTORY_WIDTHS,
                    ) as cols:

                        text_cell(
                            cols[0],
                            format_date(
                                examination.get(
                                    "examination_date"
                                )
                            ),
                        )

                        text_cell(
                            cols[1],
                            examination.get(
                                "examination_type"
                            ),
                        )

                        pill_cell(
                            cols[2],
                            status,
                            STATUS_TONES.get(
                                status,
                                "grey",
                            ),
                        )

                        if cols[3].button(
                            "View",
                            key=(
                                f"history_view_"
                                f"{exam_id}"
                            ),
                            width="stretch",
                        ):

                            open_dialog(
                                "view_exam",
                                selected_examination=(
                                    examination
                                ),
                                selected_patient=(
                                    patient
                                ),
                            )

        # ----------------------------------------------------
        # PREVIOUS MEDICAL HISTORIES
        # ----------------------------------------------------

        section_title(
            "Previous Medical Histories"
        )

        if not medical_records:

            empty_state(
                "No previous external medical records found."
            )

        else:

            with st.container(
                key="sa_table_medical_history"
            ):

                table_header(
                    MEDICAL_HISTORY_HEADERS,
                    MEDICAL_HISTORY_WIDTHS,
                    "medical_history",
                )

                for record in medical_records:

                    record_id = record[
                        "medical_record_id"
                    ]

                    with table_row(
                        f"medical_history_{record_id}",
                        MEDICAL_HISTORY_WIDTHS,
                    ) as cols:

                        text_cell(
                            cols[0],
                            format_date(
                                record.get(
                                    "record_date"
                                )
                            ),
                        )

                        text_cell(
                            cols[1],
                            record.get(
                                "record_type"
                            )
                            or "—",
                        )

                        text_cell(
                            cols[2],
                            record.get(
                                "facility_name"
                            )
                            or "—",
                        )

                        if cols[3].button(
                            "View",
                            key=(
                                f"history_medical_"
                                f"{record_id}"
                            ),
                            width="stretch",
                        ):

                            open_dialog(
                                "view_medical_record",
                                selected_medical_record=(
                                    record
                                ),
                                selected_patient=(
                                    patient
                                ),
                            )

        # ----------------------------------------------------
        # EXAMINE PATIENT
        # ----------------------------------------------------

        if is_nurse_role() or is_admin_role():

            st.divider()

            if st.button(
                "Examine Patient",
                key=(
                    "history_examine_patient_"
                    f"{patient['patient_id']}"
                ),
                icon=":material/clinical_notes:",
                type="primary",
                width="stretch",
            ):

                open_dialog(
                    "create",
                    create_examination_patient=(
                        patient
                    ),
                )


# ============================================================
# EXAMINATION DETAILS
# ============================================================

@st.dialog(
    "Examination Details",
    width="large",
)
def show_examination_details(
    patient,
    examination,
):

    examination_id = (
        examination[
            "examination_id"
        ]
    )

    with st.container(
        key="sa_dialog"
    ):

        section_title(
            "Patient Information"
        )

        show_rows(
            patient_summary_rows(
                patient
            )
        )

        section_title(
            "Examination Information"
        )

        show_rows(
            [
                (
                    "Examination type",
                    examination.get(
                        "examination_type"
                    ),
                ),
                (
                    "Examination date",
                    format_date(
                        examination.get(
                            "examination_date"
                        )
                    ),
                ),
                (
                    "Status",
                    examination.get(
                        "status"
                    ),
                ),
                (
                    "Time in",
                    examination.get(
                        "time_in"
                    ),
                ),
            ]
        )

        # ----------------------------------------------------
        # CONSENT
        # ----------------------------------------------------

        section_title(
            "Consent"
        )

        consents = (
            get_examination_consents(
                examination_id
            )
        )

        consent = (
            consents[0]
            if consents
            else None
        )

        if consent:

            show_rows(
                [
                    (
                        "Consent type",
                        consent.get(
                            "consent_type"
                        ),
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
                        ),
                    ),
                    (
                        "Signed by type",
                        consent.get(
                            "signed_by_type"
                        ),
                    ),
                    (
                        "Guardian",
                        consent.get(
                            "guardian_name"
                        ),
                    ),
                    (
                        "Relationship",
                        consent.get(
                            "guardian_relation"
                        ),
                    ),
                ]
            )

            signature_path = consent.get(
                "signature_path"
            )

            if signature_path:

                signature_url = (
                    get_consent_signature_url(
                        signature_path
                    )
                )

                if signature_url:

                    st.image(
                        signature_url,
                        width=220,
                    )

        else:

            st.caption(
                "No consent recorded."
            )

        # ----------------------------------------------------
        # VITALS
        # ----------------------------------------------------

        section_title(
            "Vital Signs"
        )

        vitals = (
            get_examination_vitals(
                examination_id
            )
        )

        if vitals:

            for vital in vitals:

                show_rows(
                    [
                        (
                            "Blood pressure",
                            (
                                f"{vital.get('bp_systolic') or '—'} / "
                                f"{vital.get('bp_diastolic') or '—'} mmHg"
                            ),
                        ),
                        (
                            "Temperature",
                            vital.get(
                                "temperature"
                            ),
                        ),
                        (
                            "Pulse rate",
                            vital.get(
                                "pulse_rate"
                            ),
                        ),
                        (
                            "Respiratory rate",
                            vital.get(
                                "respiratory_rate"
                            ),
                        ),
                        (
                            "SpO2",
                            vital.get(
                                "spo2"
                            ),
                        ),
                        (
                            "Heart rate",
                            vital.get(
                                "heart_rate"
                            ),
                        ),
                        (
                            "Weight",
                            vital.get(
                                "weight_kg"
                            ),
                        ),
                        (
                            "Height",
                            vital.get(
                                "height_cm"
                            ),
                        ),
                        (
                            "BMI",
                            vital.get(
                                "bmi"
                            ),
                        ),
                    ]
                )

        else:

            st.caption(
                "No vital signs recorded."
            )

        # ----------------------------------------------------
        # CLINICAL INFORMATION
        # ----------------------------------------------------

        section_title(
            "Clinical Information"
        )

        show_rows(
            [
                (
                    "Chief complaint",
                    examination.get(
                        "chief_complaint"
                    ),
                ),
                (
                    "History of present illness",
                    examination.get(
                        "history_of_present_illness"
                    ),
                ),
                (
                    "Physical examination",
                    examination.get(
                        "physical_examination"
                    ),
                ),
                (
                    "Diagnosis",
                    examination.get(
                        "diagnosis"
                    ),
                ),
                (
                    "Plans / orders",
                    examination.get(
                        "plans_orders"
                    ),
                ),
            ]
        )

        # ----------------------------------------------------
        # DISPOSITION
        # ----------------------------------------------------

        section_title(
            "Disposition"
        )

        show_rows(
            [
                (
                    "Disposition",
                    examination.get(
                        "disposition"
                    ),
                ),
                (
                    "Disposition notes",
                    examination.get(
                        "disposition_notes"
                    ),
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
                    ),
                ),
            ]
        )

        # ----------------------------------------------------
        # RETURN
        # ----------------------------------------------------

        if st.button(
            "Back to Patient History",
            key=(
                "back_exam_history_"
                f"{examination_id}"
            ),
            width="stretch",
        ):

            open_dialog(
                "history",
                selected_patient=(
                    patient
                ),
            )


# ============================================================
# PREVIOUS MEDICAL RECORD DETAILS
# ============================================================

@st.dialog(
    "Previous Medical Record",
    width="large",
)
def show_medical_record_details(
    patient,
    record,
):

    with st.container(
        key="sa_dialog"
    ):

        section_title(
            "Patient Information"
        )

        show_rows(
            patient_summary_rows(
                patient
            )
        )

        section_title(
            "Medical Record"

        )

        show_rows(
            [
                (
                    "Record date",
                    format_date(
                        record.get(
                            "record_date"
                        )
                    ),
                ),
                (
                    "Record type",
                    record.get(
                        "record_type"
                    ),
                ),
                (
                    "Facility",
                    record.get(
                        "facility_name"
                    ),
                ),
                (
                    "Department",
                    record.get(
                        "department"
                    ),
                ),
                (
                    "Attending physician",
                    record.get(
                        "attending_physician"
                    ),
                ),
                (
                    "Chief complaint",
                    record.get(
                        "chief_complaint"
                    ),
                ),
                (
                    "Clinical history",
                    record.get(
                        "clinical_history"
                    ),
                ),
                (
                    "Diagnosis",
                    record.get(
                        "diagnosis"
                    ),
                ),
                (
                    "Procedure",
                    record.get(
                        "procedure_name"
                    ),
                ),
                (
                    "Findings",
                    record.get(
                        "findings"
                    ),
                ),
                (
                    "Impression",
                    record.get(
                        "impression"
                    ),
                ),
                (
                    "Treatment",
                    record.get(
                        "treatment"
                    ),
                ),
                (
                    "Follow-up",
                    record.get(
                        "follow_up"
                    ),
                ),
                (
                    "Status",
                    record.get(
                        "record_status"
                    ),
                ),
            ]
        )

        section_title(
            "Attached Files"
        )

        images = (
            get_medical_record_images(
                record[
                    "medical_record_id"
                ]
            )
        )

        if not images:

            st.caption(
                "No attached files."
            )

        else:

            for image in images:

                file_path = image.get(
                    "image_url"
                )

                st.markdown(
                    f"**{image.get('image_type') or 'File'}**"
                )

                if image.get(
                    "description"
                ):

                    st.caption(
                        image.get(
                            "description"
                        )
                    )

                if file_path:

                    file_url = (
                        get_medical_record_file_url(
                            file_path
                        )
                    )

                    if file_url:

                        st.link_button(
                            "Open file",
                            file_url,
                            width="stretch",
                        )

        if st.button(
            "Back to Patient History",
            key=(
                "back_medical_history_"
                f"{record['medical_record_id']}"
            ),
            width="stretch",
        ):

            open_dialog(
                "history",
                selected_patient=(
                    patient
                ),
            )


# ============================================================
# DELETE EXAMINATION
# ============================================================

@st.dialog(
    "Delete examination",
    width="small",
)
def show_delete_examination_dialog(
    examination
):

    with st.container(
        key="sa_dialog"
    ):

        st.markdown(
            f"<p class='sa-dialog-text'>"
            f"Delete this "
            f"<b>{examination.get('examination_type')}</b> "
            f"examination from "
            f"<b>{format_date(examination.get('examination_date'))}</b>?"
            f"</p>",
            unsafe_allow_html=True,
        )

        st.warning(
            "This permanently removes the examination "
            "and its related consent and vital records."
        )

        if confirm_buttons(
            f"delete_exam_{examination['examination_id']}",
            "Delete permanently",
        ):

            try:

                delete_examination(
                    examination[
                        "examination_id"
                    ]
                )

                remember(
                    "Examination deleted."
                )

                open_dialog(
                    "history",
                    selected_patient=(
                        st.session_state.get(
                            "selected_patient"
                        )
                    ),
                )

            except Exception as error:

                st.error(
                    f"Failed to delete examination: {error}"
                )


# ============================================================
# CREATE / EDIT EXAMINATION
# ============================================================

@st.dialog(
    "Examine Patient",
    width="large",
)
def show_examination_form(
    patient,
    examination=None,
):

    user_id = current_user().get(
        "user_id"
    )

    is_edit = (
        examination
        is not None
    )

    examination_id = (
        examination.get(
            "examination_id"
        )
        if examination
        else None
    )

    existing_consent = None
    existing_vitals = []

    if is_edit:

        consents = (
            get_examination_consents(
                examination_id
            )
        )

        existing_consent = (
            consents[0]
            if consents
            else None
        )

        existing_vitals = (
            get_examination_vitals(
                examination_id
            )
        )

    with st.container(
        key="sa_dialog"
    ):

        # ----------------------------------------------------
        # PATIENT INFORMATION
        # ----------------------------------------------------

        section_title(
            "Patient Information"
        )

        show_rows(
            patient_summary_rows(
                patient
            )
        )

        # ----------------------------------------------------
        # EXISTING HISTORIES
        # ----------------------------------------------------

        section_title(
            "Examination Histories"
        )

        examinations = (
            get_examinations_by_patient(
                patient[
                    "patient_id"
                ]
            )
        )

        if examinations:

            for old_exam in examinations:

                old_exam_id = old_exam[
                    "examination_id"
                ]

                with st.container(
                    key=(
                        f"form_exam_"
                        f"{old_exam_id}"
                    )
                ):

                    c1, c2, c3, c4 = st.columns(
                        [1.3, 2, 1.4, 1]
                    )

                    text_cell(
                        c1,
                        format_date(
                            old_exam.get(
                                "examination_date"
                            )
                        ),
                    )

                    text_cell(
                        c2,
                        old_exam.get(
                            "examination_type"
                        ),
                    )

                    pill_cell(
                        c3,
                        old_exam.get(
                            "status"
                        ),
                        STATUS_TONES.get(
                            old_exam.get(
                                "status"
                            ),
                            "grey",
                        ),
                    )

                    if c4.button(
                        "View",
                        key=(
                            f"form_view_exam_"
                            f"{old_exam_id}"
                        ),
                        width="stretch",
                    ):

                        open_dialog(
                            "view_exam",
                            selected_examination=(
                                old_exam
                            ),
                            selected_patient=(
                                patient
                            ),
                        )

        else:

            st.caption(
                "No previous examinations."
            )

        # ----------------------------------------------------
        # PREVIOUS MEDICAL HISTORIES
        # ----------------------------------------------------

        section_title(
            "Previous Medical Histories"
        )

        previous_records = (
            get_medical_records_by_patient(
                patient[
                    "patient_id"
                ]
            )
        )

        if previous_records:

            for record in previous_records:

                record_id = record[
                    "medical_record_id"
                ]

                c1, c2, c3, c4 = st.columns(
                    [1.3, 1.8, 2.4, 1]
                )

                text_cell(
                    c1,
                    format_date(
                        record.get(
                            "record_date"
                        )
                    ),
                )

                text_cell(
                    c2,
                    record.get(
                        "record_type"
                    ),
                )

                text_cell(
                    c3,
                    record.get(
                        "facility_name"
                    )
                    or "—",
                )

                if c4.button(
                    "View",
                    key=(
                        f"form_view_medical_"
                        f"{record_id}"
                    ),
                    width="stretch",
                ):

                    open_dialog(
                        "view_medical_record",
                        selected_medical_record=(
                            record
                        ),
                        selected_patient=(
                            patient
                        ),
                    )

        else:

            st.caption(
                "No previous external medical histories."
            )

        st.divider()

        # ----------------------------------------------------
        # CONSENT
        # ----------------------------------------------------

        section_title(
            "Consent"
        )

        signed_by_name = st.text_input(
            "Patient / Guardian name",
            value=(
                (
                    existing_consent
                    or {}
                ).get(
                    "signed_by_name"
                )
                or patient_name(
                    patient
                )
            ),
            key=(
                "exam_consent_name"
            ),
        )

        guardian_name = None
        guardian_relation = None
        signed_by_type = "patient"

        if is_minor(
            patient.get(
                "date_of_birth"
            )
        ):

            signed_by_type = "guardian"

            guardian_col, relation_col = st.columns(
                2
            )

            guardian_name = guardian_col.text_input(
                "Guardian name",
                value=(
                    (
                        existing_consent
                        or {}
                    ).get(
                        "guardian_name"
                    )
                    or ""
                ),
                key=(
                    "exam_guardian_name"
                ),
            )

            relation_options = [
                "Parent",
                "Guardian",
                "Spouse",
                "Sibling",
                "Other",
            ]

            current_relation = (
                (
                    existing_consent
                    or {}
                ).get(
                    "guardian_relation"
                )
                or "Parent"
            )

            guardian_relation = relation_col.selectbox(
                "Guardian relationship",
                relation_options,
                index=(
                    relation_options.index(
                        current_relation
                    )
                    if current_relation
                    in relation_options
                    else 0
                ),
                key=(
                    "exam_guardian_relation"
                ),
            )

        st.markdown(
            "**Signature** — patient or guardian:"
        )

        canvas_result = st_canvas(
            stroke_width=2,
            stroke_color="#000000",
            background_color="#FFFFFF",
            height=150,
            width=500,
            drawing_mode="freedraw",
            return_image_data=True,
            key=(
                f"signature_canvas_"
                f"{examination_id or 'new'}"
            ),
        )

        consent_confirmed = st.checkbox(
            "I confirm the patient/guardian signed the consent above.",
            key=(
                "exam_consent_confirm"
            ),
        )

        # ----------------------------------------------------
        # VITALS
        # ----------------------------------------------------

        section_title(
            "Vital Signs"
        )

        v1, v2, v3 = st.columns(
            3
        )

        bp_sys = v1.number_input(
            "BP systolic",
            min_value=0,
            max_value=300,
            step=1,
            value=int(
                _get_vitals_value(
                    existing_vitals,
                    "bp_systolic",
                )
                or 0
            ),
            key="exam_bp_sys",
        )

        bp_dia = v2.number_input(
            "BP diastolic",
            min_value=0,
            max_value=200,
            step=1,
            value=int(
                _get_vitals_value(
                    existing_vitals,
                    "bp_diastolic",
                )
                or 0
            ),
            key="exam_bp_dia",
        )

        temperature = v3.number_input(
            "Temperature",
            min_value=0.0,
            max_value=50.0,
            step=0.1,
            value=float(
                _get_vitals_value(
                    existing_vitals,
                    "temperature",
                )
                or 0
            ),
            key="exam_temperature",
        )

        errors = st.container()

        cancel_col, save_col = st.columns(
            2
        )

        cancel = cancel_col.button(
            "Cancel",
            key="exam_cancel",
            width="stretch",
        )

        save = save_col.button(
            "Save Examination",
            key="exam_save",
            type="primary",
            width="stretch",
        )

    if cancel:

        close_dialog()
        st.rerun()

    if not save:
        return

    if not signed_by_name.strip():

        errors.error(
            "Patient/Guardian name is required."
        )

        return

    if not consent_confirmed:

        errors.error(
            "Please confirm the consent."
        )

        return

    has_signature = (
        canvas_result.image_data
        is not None
        and canvas_result.image_data[
            :,
            :,
            3
        ].sum()
        > 0
    )

    if (
        not has_signature
        and not (
            existing_consent
            and existing_consent.get(
                "signature_path"
            )
        )
    ):

        errors.error(
            "Please draw the patient/guardian signature."
        )

        return

    try:

        if not is_edit:

            rows = create_examination(
                patient_id=patient[
                    "patient_id"
                ],
                examination_type=FIXED_EXAM_TYPE,
                examination_date=date.today(),
                created_by=user_id,
                consent_given=True,
                consent_signed_by_name=(
                    signed_by_name.strip()
                ),
                consent_signed_by_type=(
                    signed_by_type
                ),
                consent_guardian_name=(
                    guardian_name
                    or ""
                ).strip()
                or None,
                consent_guardian_relation=(
                    guardian_relation
                ),
                consent_witnessed_by=(
                    user_id
                ),
                bp_systolic=(
                    bp_sys
                    or None
                ),
                bp_diastolic=(
                    bp_dia
                    or None
                ),
                temperature=(
                    temperature
                    or None
                ),
            )

            if not rows:

                errors.error(
                    "Failed to create examination."
                )

                return

            exam_id = rows[0][
                "examination_id"
            ]

            if has_signature:

                from PIL import Image

                image = Image.fromarray(
                    canvas_result.image_data.astype(
                        "uint8"
                    ),
                    "RGBA",
                )

                buffer = io.BytesIO()

                image.save(
                    buffer,
                    format="PNG",
                )

                signature_path = (
                    upload_consent_signature(
                        exam_id,
                        buffer.getvalue(),
                    )
                )

                if signature_path:

                    consents = (
                        get_examination_consents(
                            exam_id
                        )
                    )

                    if consents:

                        update_examination_consent(
                            consents[0][
                                "consent_id"
                            ],
                            signature_path=(
                                signature_path
                            ),
                        )

        else:

            if existing_consent:

                consent_updates = {
                    "given": True,
                    "signed_by_name": (
                        signed_by_name.strip()
                    ),
                    "signed_by_type": (
                        signed_by_type
                    ),
                    "guardian_name": (
                        guardian_name
                        or ""
                    ).strip()
                    or None,
                    "guardian_relation": (
                        guardian_relation
                    ),
                }

                update_examination_consent(
                    existing_consent[
                        "consent_id"
                    ],
                    **consent_updates,
                )

            if existing_vitals:

                update_examination_vitals(
                    existing_vitals[0][
                        "vitals_id"
                    ],
                    bp_systolic=(
                        bp_sys
                        or None
                    ),
                    bp_diastolic=(
                        bp_dia
                        or None
                    ),
                    temperature=(
                        temperature
                        or None
                    ),
                )

            update_examination(
                examination_id=(
                    examination_id
                ),
                status="Pending",
            )

        remember(
            "Examination saved."
        )

        close_dialog()

        st.rerun()

    except Exception as error:

        errors.error(
            f"Failed to save examination: {error}"
        )


# ============================================================
# FILTERS
# ============================================================

def show_filters(
    patients,
    hospitals=None,
):

    if (
        is_superadmin()
        and hospitals is not None
    ):

        hospital_col, search_col, sex_col, status_col, reset_col = st.columns(
            [
                1.5,
                2.5,
                1,
                1,
                0.8,
            ]
        )

        hospital_names = [
            "All hospitals"
        ] + sorted(
            {
                hospital.get(
                    "hospital_name"
                )
                for hospital in hospitals
                if hospital.get(
                    "hospital_name"
                )
            }
        )

        hospital_filter = (
            hospital_col.selectbox(
                "Hospital",
                hospital_names,
                label_visibility="collapsed",
                key="exam_hospital_filter",
            )
        )

        search = search_col.text_input(
            "Search",
            placeholder="Search by name or contact",
            label_visibility="collapsed",
            key="exam_search",
        ).strip().lower()

        sex = sex_col.selectbox(
            "Sex",
            [
                "All sexes",
                "Male",
                "Female",
            ],
            label_visibility="collapsed",
            key="exam_sex",
        )

        status = status_col.selectbox(
            "Status",
            [
                "All status",
                "Active",
                "Inactive",
            ],
            label_visibility="collapsed",
            key="exam_status",
        )

        if reset_col.button(
            "Refresh",
            icon=":material/refresh:",
            width="stretch",
            key="exam_refresh",
        ):

            st.rerun()

        matches = []

        for patient in patients:

            text = (
                f"{patient_name(patient)} "
                f"{patient.get('contact_number') or ''}"
            ).lower()

            if (
                hospital_filter
                != "All hospitals"
                and patient_hospital_name(
                    patient
                )
                != hospital_filter
            ):
                continue

            if (
                search
                and search not in text
            ):
                continue

            if (
                sex != "All sexes"
                and patient.get(
                    "sex"
                )
                != sex
            ):
                continue

            if (
                status != "All status"
                and patient.get(
                    "status"
                )
                != status
            ):
                continue

            matches.append(
                patient
            )

        return matches

    search_col, sex_col, status_col, reset_col = st.columns(
        [3, 1.2, 1.2, 1]
    )

    search = search_col.text_input(
        "Search",
        placeholder="Search by patient name or contact number",
        label_visibility="collapsed",
        key="exam_search",
    ).strip().lower()

    sex = sex_col.selectbox(
        "Sex",
        [
            "All sexes",
            "Male",
            "Female",
        ],
        label_visibility="collapsed",
        key="exam_sex",
    )

    status = status_col.selectbox(
        "Status",
        [
            "All status",
            "Active",
            "Inactive",
        ],
        label_visibility="collapsed",
        key="exam_status",
    )

    if reset_col.button(
        "Refresh",
        icon=":material/refresh:",
        width="stretch",
        key="exam_refresh",
    ):

        st.rerun()

    matches = []

    for patient in patients:

        text = (
            f"{patient_name(patient)} "
            f"{patient.get('contact_number') or ''}"
        ).lower()

        if (
            search
            and search not in text
        ):
            continue

        if (
            sex != "All sexes"
            and patient.get(
                "sex"
            )
            != sex
        ):
            continue

        if (
            status != "All status"
            and patient.get(
                "status"
            )
            != status
        ):
            continue

        matches.append(
            patient
        )

    return matches


# ============================================================
# PATIENT TABLE
# ============================================================

def render_patient_table(
    patients
):

    if not patients:

        empty_state(
            "No patients found."
        )

        return

    if is_superadmin():

        with st.container(
            key="sa_table_exam_patients"
        ):

            table_header(
                HEADERS_SUPERADMIN,
                WIDTHS_SUPERADMIN,
                "exam_patients",
            )

            for patient in patients:

                patient_id = patient[
                    "patient_id"
                ]

                with table_row(
                    f"exam_patients_{patient_id}",
                    WIDTHS_SUPERADMIN,
                ) as cols:

                    text_cell(
                        cols[0],
                        patient_hospital_name(
                            patient
                        ),
                        muted=True,
                    )

                    text_cell(
                        cols[1],
                        patient_code(
                            patient
                        ),
                        muted=True,
                    )

                    name_cell(
                        cols[2],
                        patient_name(
                            patient
                        ),
                    )

                    text_cell(
                        cols[3],
                        format_date(
                            patient.get(
                                "date_of_birth"
                            )
                        ),
                    )

                    text_cell(
                        cols[4],
                        patient.get(
                            "sex"
                        ),
                    )

                    text_cell(
                        cols[5],
                        patient.get(
                            "contact_number"
                        ),
                    )

                    if cols[6].button(
                        "Examine",
                        key=(
                            f"examine_"
                            f"{patient_id}"
                        ),
                        icon=":material/clinical_notes:",
                        width="stretch",
                    ):

                        open_dialog(
                            "history",
                            selected_patient=(
                                patient
                            ),
                        )

    else:

        with st.container(
            key="sa_table_exam_patients"
        ):

            table_header(
                HEADERS,
                WIDTHS,
                "exam_patients",
            )

            for patient in patients:

                patient_id = patient[
                    "patient_id"
                ]

                with table_row(
                    f"exam_patients_{patient_id}",
                    WIDTHS,
                ) as cols:

                    text_cell(
                        cols[0],
                        patient_code(
                            patient
                        ),
                        muted=True,
                    )

                    name_cell(
                        cols[1],
                        patient_name(
                            patient
                        ),
                    )

                    text_cell(
                        cols[2],
                        format_date(
                            patient.get(
                                "date_of_birth"
                            )
                        ),
                    )

                    text_cell(
                        cols[3],
                        patient.get(
                            "sex"
                        ),
                    )

                    text_cell(
                        cols[4],
                        patient.get(
                            "contact_number"
                        ),
                    )

                    if cols[5].button(
                        "Examine",
                        key=(
                            f"examine_"
                            f"{patient_id}"
                        ),
                        icon=":material/clinical_notes:",
                        width="stretch",
                    ):

                        open_dialog(
                            "history",
                            selected_patient=(
                                patient
                            ),
                        )


# ============================================================
# PAGE
# ============================================================

def show():

    load_css(
        "manage_examinations.css"
    )

    show_flash_message()

    hospital_id = (
        current_hospital_id()
    )

    with st.container(
        key="sa_page"
    ):

        page_header(
            "Examinations",
            "Review patient examination history and examine patients.",
        )

        patients = load_patients()

        if is_superadmin():

            hospitals = (
                get_all_hospitals()
                or []
            )

            matches = show_filters(
                patients,
                hospitals=hospitals,
            )

        else:

            if hospital_id is None:

                st.error(
                    "Your account is not assigned "
                    "to a hospital. Please contact "
                    "your Superadmin."
                )

                st.stop()

            patients = [
                patient
                for patient in patients
                if patient.get(
                    "hospital_id"
                )
                == hospital_id
            ]

            matches = show_filters(
                patients
            )

        render_patient_table(
            matches
        )

    # ========================================================
    # DIALOG ROUTER
    # ========================================================

    dialog = st.session_state.get(
        "examination_dialog"
    )

    if (
        dialog == "history"
        and st.session_state.get(
            "selected_patient"
        )
    ):

        show_patient_history(
            st.session_state[
                "selected_patient"
            ]
        )

    elif (
        dialog == "view_exam"
        and st.session_state.get(
            "selected_examination"
        )
    ):

        show_examination_details(
            st.session_state[
                "selected_patient"
            ],
            st.session_state[
                "selected_examination"
            ],
        )

    elif (
        dialog == "view_medical_record"
        and st.session_state.get(
            "selected_medical_record"
        )
    ):

        show_medical_record_details(
            st.session_state[
                "selected_patient"
            ],
            st.session_state[
                "selected_medical_record"
            ],
        )

    elif (
        dialog == "create"
        and st.session_state.get(
            "create_examination_patient"
        )
    ):

        show_examination_form(
            st.session_state[
                "create_examination_patient"
            ],
            st.session_state.get(
                "selected_examination"
            ),
        )

    elif (
        dialog == "delete"
        and st.session_state.get(
            "delete_examination_target"
        )
    ):

        show_delete_examination_dialog(
            st.session_state[
                "delete_examination_target"
            ]
        )