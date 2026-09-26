import streamlit as st

from backend.fetches import (
    get_all_patients,
    get_all_hospitals,
    get_examinations_by_patient,
    get_medical_records_by_patient,
    get_medical_record_images,
    get_medical_record_file_url,
)

from backend.crud import (
    create_medical_record,
    upload_medical_record_file,
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
)

from datetime import date


# ============================================================
# CONFIG
# ============================================================

WIDTHS = [
    1.3,
    3,
    1.5,
    0.9,
    1.8,
    2,
    1,
]

WIDTHS_SUPERADMIN = [
    1.6,
    1.3,
    2.7,
    1.4,
    0.9,
    1.5,
    1,
]

HEADERS = [
    "Patient ID",
    "Name",
    "Date of birth",
    "Sex",
    "Contact",
    "Hospital",
    "Records",
]

HEADERS_SUPERADMIN = [
    "Hospital",
    "Patient ID",
    "Name",
    "Date of birth",
    "Sex",
    "Contact",
    "Records",
]


EXAM_WIDTHS = [
    1.5,
    2,
    1.5,
    1,
]

EXAM_HEADERS = [
    "Date",
    "Examination",
    "Status",
    "View",
]


MEDICAL_WIDTHS = [
    1.4,
    1.8,
    2.5,
    1,
]

MEDICAL_HEADERS = [
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


ROLE_SUPERADMIN = 1


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


def patient_name(
    patient
):

    return full_name(
        patient.get(
            "first_name"
        ),
        patient.get(
            "middle_name"
        ),
        patient.get(
            "last_name"
        ),
        patient.get(
            "suffix"
        ),
    )


def patient_code(
    patient
):

    return (
        patient.get(
            "patient_code"
        )
        or patient.get(
            "patient_id"
        )
    )


def patient_hospital_name(
    patient
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


def open_dialog(
    name,
    **state,
):

    st.session_state[
        "patient_records_dialog"
    ] = name

    for key, value in state.items():

        st.session_state[
            key
        ] = value

    st.rerun()


# ============================================================
# PATIENT RECORDS DIALOG
# ============================================================

@st.dialog(
    "Patient Records",
    width="large",
)
def show_patient_records(
    patient
):

    patient_id = patient[
        "patient_id"
    ]

    examinations = (
        get_examinations_by_patient(
            patient_id
        )
    )

    medical_records = (
        get_medical_records_by_patient(
            patient_id
        )
    )

    with st.container(
        key="sa_dialog"
    ):

        # ====================================================
        # PATIENT INFORMATION
        # ====================================================

        section_title(
            "Patient Information"
        )

        show_rows(
            [
                (
                    "Patient ID",
                    patient_code(
                        patient
                    ),
                ),
                (
                    "Full name",
                    patient_name(
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
                    "Civil status",
                    patient.get(
                        "civil_status"
                    ),
                ),
                (
                    "Contact",
                    patient.get(
                        "contact_number"
                    ),
                ),
                (
                    "Address",
                    patient.get(
                        "address"
                    ),
                ),
                (
                    "Hospital",
                    patient_hospital_name(
                        patient
                    ),
                ),
            ]
        )

        # ====================================================
        # INTERNAL EXAMINATION RECORDS
        # ====================================================

        section_title(
            "Examination Records"
        )

        if not examinations:

            empty_state(
                "No examination records found for this patient."
            )

            if st.button(
                "Examine Patient",
                key=(
                    "records_examine_"
                    f"{patient_id}"
                ),
                icon=":material/clinical_notes:",
                type="primary",
                width="stretch",
            ):

                # ------------------------------------------------
                # MOVE TO EXAMINATIONS PAGE
                # ------------------------------------------------

                st.session_state[
                    "current_page"
                ] = "Examinations"

                st.session_state[
                    "examination_dialog"
                ] = "history"

                st.session_state[
                    "selected_patient"
                ] = patient

                st.session_state[
                    "patient_records_dialog"
                ] = None

                st.rerun()

        else:

            with st.container(
                key="patient_exam_records"
            ):

                table_header(
                    EXAM_HEADERS,
                    EXAM_WIDTHS,
                    "patient_exams",
                )

                for examination in examinations:

                    examination_id = (
                        examination[
                            "examination_id"
                        ]
                    )

                    status = (
                        examination.get(
                            "status"
                        )
                        or "—"
                    )

                    with table_row(
                        f"patient_exam_{examination_id}",
                        EXAM_WIDTHS,
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
                                f"record_exam_view_"
                                f"{examination_id}"
                            ),
                            width="stretch",
                        ):

                            # ------------------------------------
                            # IMPORTANT:
                            # Go to Examinations page
                            # ------------------------------------

                            st.session_state[
                                "current_page"
                            ] = "Examinations"

                            st.session_state[
                                "examination_dialog"
                            ] = "view_exam"

                            st.session_state[
                                "selected_patient"
                            ] = patient

                            st.session_state[
                                "selected_examination"
                            ] = examination

                            st.session_state[
                                "patient_records_dialog"
                            ] = None

                            st.rerun()

        # ====================================================
        # PREVIOUS EXTERNAL MEDICAL HISTORIES
        # ====================================================

        section_title(
            "Previous Medical Histories"
        )

        if not medical_records:

            empty_state(
                "No previous external medical records found."
            )

            if st.button(
                "Add External Medical Record",
                key=(
                    "add_external_record_"
                    f"{patient_id}"
                ),
                icon=":material/add:",
                width="stretch",
            ):

                open_dialog(
                    "add_medical_record",
                    selected_patient=patient,
                )

        else:

            with st.container(
                key="patient_medical_records"
            ):

                table_header(
                    MEDICAL_HEADERS,
                    MEDICAL_WIDTHS,
                    "patient_medical",
                )

                for record in medical_records:

                    record_id = record[
                        "medical_record_id"
                    ]

                    with table_row(
                        f"patient_medical_{record_id}",
                        MEDICAL_WIDTHS,
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
                                f"medical_view_"
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

            st.divider()

            if st.button(
                "Add External Medical Record",
                key=(
                    "add_external_record_existing_"
                    f"{patient_id}"
                ),
                icon=":material/add:",
                width="stretch",
            ):

                open_dialog(
                    "add_medical_record",
                    selected_patient=patient,
                )


# ============================================================
# EXTERNAL MEDICAL RECORD DETAILS
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
            [
                (
                    "Patient ID",
                    patient_code(
                        patient
                    ),
                ),
                (
                    "Patient",
                    patient_name(
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
            ]
        )

        section_title(
            "External Medical Record"
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
                "No files attached."
            )

        else:

            for image in images:

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

                file_path = image.get(
                    "image_url"
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
            "Back to Patient Records",
            key=(
                "back_patient_records_"
                f"{record['medical_record_id']}"
            ),
            width="stretch",
        ):

            open_dialog(
                "records",
                selected_patient=(
                    patient
                ),
            )


# ============================================================
# ADD EXTERNAL MEDICAL RECORD
# ============================================================

@st.dialog(
    "Add External Medical Record",
    width="large",
)
def show_add_medical_record(
    patient
):

    with st.container(
        key="sa_dialog"
    ):

        section_title(
            "Patient"
        )

        show_rows(
            [
                (
                    "Patient ID",
                    patient_code(
                        patient
                    ),
                ),
                (
                    "Patient",
                    patient_name(
                        patient
                    ),
                ),
            ]
        )

        with st.form(
            "external_medical_record_form"
        ):

            record_date = st.date_input(
                "Record date",
                value=date.today(),
                format="YYYY-MM-DD",
            )

            record_type = st.selectbox(
                "Record type",
                [
                    "Consultation",
                    "Hospitalization",
                    "Laboratory",
                    "Imaging",
                    "Treatment",
                    "Discharge Summary",
                    "Other",
                ],
            )

            facility_name = st.text_input(
                "Facility / Hospital"
            )

            department = st.text_input(
                "Department"
            )

            attending_physician = st.text_input(
                "Attending physician"
            )

            chief_complaint = st.text_area(
                "Chief complaint"
            )

            clinical_history = st.text_area(
                "Clinical history"
            )

            diagnosis = st.text_area(
                "Diagnosis"
            )

            procedure_name = st.text_input(
                "Procedure"
            )

            findings = st.text_area(
                "Findings"
            )

            impression = st.text_area(
                "Impression"
            )

            treatment = st.text_area(
                "Treatment"
            )

            follow_up = st.text_area(
                "Follow-up"
            )

            uploaded_files = st.file_uploader(
                "Attach supporting files",
                type=[
                    "png",
                    "jpg",
                    "jpeg",
                    "pdf",
                ],
                accept_multiple_files=True,
            )

            cancel_col, save_col = st.columns(
                2
            )

            cancel = cancel_col.form_submit_button(
                "Cancel",
                width="stretch",
            )

            submitted = save_col.form_submit_button(
                "Save Medical Record",
                type="primary",
                width="stretch",
            )

        if cancel:

            st.session_state[
                "patient_records_dialog"
            ] = "records"

            st.rerun()

        if not submitted:
            return

        if not facility_name.strip():

            st.error(
                "Facility / Hospital is required."
            )

            return

        try:

            result = create_medical_record(
                patient_id=(
                    patient[
                        "patient_id"
                    ]
                ),
                record_date=(
                    record_date
                ),
                record_type=(
                    record_type
                ),
                facility_name=(
                    facility_name.strip()
                ),
                department=(
                    department.strip()
                    or None
                ),
                attending_physician=(
                    attending_physician.strip()
                    or None
                ),
                chief_complaint=(
                    chief_complaint.strip()
                    or None
                ),
                clinical_history=(
                    clinical_history.strip()
                    or None
                ),
                diagnosis=(
                    diagnosis.strip()
                    or None
                ),
                procedure_name=(
                    procedure_name.strip()
                    or None
                ),
                findings=(
                    findings.strip()
                    or None
                ),
                impression=(
                    impression.strip()
                    or None
                ),
                treatment=(
                    treatment.strip()
                    or None
                ),
                follow_up=(
                    follow_up.strip()
                    or None
                ),
                created_by=(
                    current_user().get(
                        "user_id"
                    )
                ),
            )

            if not result.get(
                "success"
            ):

                st.error(
                    result.get(
                        "message"
                    )
                    or
                    "Unable to create medical record."
                )

                return

            medical_record_id = (
                result[
                    "data"
                ][
                    "medical_record_id"
                ]
            )

            for uploaded_file in (
                uploaded_files
                or []
            ):

                upload_medical_record_file(
                    medical_record_id=(
                        medical_record_id
                    ),
                    uploaded_file=(
                        uploaded_file
                    ),
                    image_type=(
                        uploaded_file.type
                        or "File"
                    ),
                    description=(
                        uploaded_file.name
                    ),
                )

            remember(
                "External medical record added."
            )

            open_dialog(
                "records",
                selected_patient=(
                    patient
                ),
            )

        except Exception as error:

            st.error(
                f"Failed to save medical record: {error}"
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

        hospital_col, search_col, sex_col, reset_col = st.columns(
            [
                1.5,
                3,
                1.2,
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
                key="records_hospital_filter",
            )
        )

        search = search_col.text_input(
            "Search",
            placeholder="Search by patient name or contact number",
            label_visibility="collapsed",
            key="records_search",
        ).strip().lower()

        sex = sex_col.selectbox(
            "Sex",
            [
                "All sexes",
                "Male",
                "Female",
            ],
            label_visibility="collapsed",
            key="records_sex",
        )

        if reset_col.button(
            "Refresh",
            icon=":material/refresh:",
            width="stretch",
            key="records_refresh",
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

            matches.append(
                patient
            )

        return matches

    search_col, sex_col, reset_col = st.columns(
        [
            3,
            1.2,
            1,
        ]
    )

    search = search_col.text_input(
        "Search",
        placeholder="Search by patient name or contact number",
        label_visibility="collapsed",
        key="records_search",
    ).strip().lower()

    sex = sex_col.selectbox(
        "Sex",
        [
            "All sexes",
            "Male",
            "Female",
        ],
        label_visibility="collapsed",
        key="records_sex",
    )

    if reset_col.button(
        "Refresh",
        icon=":material/refresh:",
        width="stretch",
        key="records_refresh",
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
            key="sa_table_patient_records"
        ):

            table_header(
                HEADERS_SUPERADMIN,
                WIDTHS_SUPERADMIN,
                "patient_records",
            )

            for patient in patients:

                patient_id = patient[
                    "patient_id"
                ]

                with table_row(
                    f"records_{patient_id}",
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
                        "Records",
                        key=(
                            f"records_"
                            f"{patient_id}"
                        ),
                        icon=":material/folder_shared:",
                        width="stretch",
                    ):

                        open_dialog(
                            "records",
                            selected_patient=(
                                patient
                            ),
                        )

    else:

        with st.container(
            key="sa_table_patient_records"
        ):

            table_header(
                HEADERS,
                WIDTHS,
                "patient_records",
            )

            for patient in patients:

                patient_id = patient[
                    "patient_id"
                ]

                with table_row(
                    f"records_{patient_id}",
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

                    text_cell(
                        cols[5],
                        patient_hospital_name(
                            patient
                        ),
                    )

                    if cols[6].button(
                        "Records",
                        key=(
                            f"records_"
                            f"{patient_id}"
                        ),
                        icon=":material/folder_shared:",
                        width="stretch",
                    ):

                        open_dialog(
                            "records",
                            selected_patient=(
                                patient
                            ),
                        )


# ============================================================
# PAGE
# ============================================================

def show():

    load_css(
        "manage_medical_records.css"
    )

    show_flash_message()

    hospital_id = (
        current_hospital_id()
    )

    with st.container(
        key="sa_page"
    ):

        page_header(
            "Patient Records",
            "View the complete patient record, including examinations and previous medical histories.",
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
        "patient_records_dialog"
    )

    if (
        dialog == "records"
        and st.session_state.get(
            "selected_patient"
        )
    ):

        show_patient_records(
            st.session_state[
                "selected_patient"
            ]
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
        dialog == "add_medical_record"
        and st.session_state.get(
            "selected_patient"
        )
    ):

        show_add_medical_record(
            st.session_state[
                "selected_patient"
            ]
        )