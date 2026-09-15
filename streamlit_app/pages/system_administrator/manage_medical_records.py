import streamlit as st

from backend.fetches import (
    get_all_patients,
    get_medical_records_by_patient,
    get_medical_record_images,
    get_medical_record_file_url
)

from backend.crud import(
    create_medical_record,
    upload_medical_record_file
)

# ==========================================================
# MAIN PAGE
# ==========================================================

def show():

    st.title(
        "Medical Records"
    )

    st.caption(
        "View and manage patient medical history."
    )

    # ======================================================
    # LOAD PATIENTS
    # ======================================================

    patients = load_patients()

    # ======================================================
    # FILTER PATIENTS
    # ======================================================

    filtered_patients = show_patient_filters(
        patients
    )

    # ======================================================
    # PATIENT TABLE
    # ======================================================

    show_patient_table(
        filtered_patients
    )

    # ======================================================
    # FORM 2
    # PATIENT MEDICAL HISTORY
    # ======================================================

    selected_patient = (
        st.session_state.get(
            "selected_medical_patient"
        )
    )

    if selected_patient:

        show_medical_history_dialog(
            selected_patient
        )

# ==========================================================
# LOAD PATIENTS
# ==========================================================

def load_patients():

    try:

        patients = get_all_patients()

        if not patients:
            return []

        return patients

    except Exception as e:

        st.error(
            f"Failed to load patients: {e}"
        )

        return []

# ==========================================================
# FORM 1 - PATIENT TABLE
# ==========================================================

def show_patient_table(patients):

    if not patients:

        st.info("No patients found.")

        return

    # ------------------------------------------------------
    # Table Header
    # ------------------------------------------------------

    header = st.columns(
        [3, 2, 2, 1]
    )

    header[0].markdown(
        "**Patient Name**"
    )

    header[1].markdown(
        "**Date of Birth**"
    )

    header[2].markdown(
        "**Sex**"
    )

    header[3].markdown(
        "**Action**"
    )

    st.divider()

    # ------------------------------------------------------
    # Patient Rows
    # ------------------------------------------------------

    for patient in patients:

        patient_id = patient.get(
            "patient_id"
        )

        first_name = patient.get(
            "first_name",
            ""
        )

        middle_name = patient.get(
            "middle_name",
            ""
        )

        last_name = patient.get(
            "last_name",
            ""
        )

        # --------------------------------------------------
        # Full Name
        # --------------------------------------------------

        full_name = " ".join(
            part
            for part in [
                first_name,
                middle_name,
                last_name
            ]
            if part
        )

        date_of_birth = patient.get(
            "date_of_birth",
            ""
        )

        sex = patient.get(
            "sex",
            ""
        )

        # --------------------------------------------------
        # Row
        # --------------------------------------------------

        row = st.columns(
            [3, 2, 2, 1]
        )

        row[0].write(
            full_name
        )

        row[1].write(
            date_of_birth
        )

        row[2].write(
            sex
        )

        # --------------------------------------------------
        # View Button
        # --------------------------------------------------

        if row[3].button(
            "View",
            key=f"view_medical_records_{patient_id}",
            width="stretch"
        ):

            st.session_state[
                "selected_medical_patient"
            ] = patient

            st.rerun()

        # --------------------------------------------------
        # Horizontal Line
        # --------------------------------------------------

        st.divider()

# ==========================================================
# FORM 2 - PATIENT MEDICAL HISTORY
# ==========================================================

@st.dialog("Patient Medical History")
def show_medical_history_dialog(patient):

    st.markdown(
        """
        <style>
        div[data-testid="stDialog"] > div {
            width: 90vw;
            max-width: 1400px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # ======================================================
    # FORM 3-A / FORM 3-B NAVIGATION
    # ======================================================

    selected_record = (
        st.session_state.get(
            "selected_medical_record"
        )
    )

    # ------------------------------------------------------
    # FORM 3-A
    # View Medical Record
    # ------------------------------------------------------

    if selected_record:

        show_medical_record_details(
            selected_record
        )

        return

    # ------------------------------------------------------
    # FORM 3-B
    # Create External Medical Record
    # ------------------------------------------------------

    if st.session_state.get(
        "adding_medical_record",
        False
    ):

        show_create_external_record_form(
            patient
        )

        return

    # ======================================================
    # PATIENT INFORMATION
    # ======================================================

    st.markdown(
        "### Patient Information"
    )

    patient_id = patient.get(
        "patient_id"
    )

    first_name = patient.get(
        "first_name",
        ""
    )

    middle_name = patient.get(
        "middle_name",
        ""
    )

    last_name = patient.get(
        "last_name",
        ""
    )

    full_name = " ".join(
        part
        for part in [
            first_name,
            middle_name,
            last_name
        ]
        if part
    )

    date_of_birth = patient.get(
        "date_of_birth",
        ""
    )

    sex = patient.get(
        "sex",
        ""
    )

    # ======================================================
    # PATIENT INFORMATION LAYOUT
    # ======================================================

    col1, col2, col3 = st.columns(3)

    with col1:

        st.markdown(
            "**Patient Name**"
        )

        st.write(
            full_name
        )

    with col2:

        st.markdown(
            "**Date of Birth**"
        )

        st.write(
            date_of_birth
        )

    with col3:

        st.markdown(
            "**Sex**"
        )

        st.write(
            sex
        )

    st.divider()

    # ======================================================
    # MEDICAL HISTORY HEADER
    # ======================================================

    col1, col2 = st.columns(
        [4, 1]
    )

    with col1:

        st.markdown(
            "### Medical History"
        )

    with col2:

        if st.button(
            "＋ Add External Record",
            width="stretch",
            key=f"add_external_record_{patient_id}"
        ):

            st.session_state[
                "adding_medical_record"
            ] = True

            st.rerun()

    # ======================================================
    # RETRIEVE MEDICAL RECORDS
    # ======================================================

    medical_records = (
        get_medical_records_by_patient(
            patient_id
        )
    )

    # ======================================================
    # NO RECORDS
    # ======================================================

    if not medical_records:

        st.info(
            "No external medical records found."
        )

    # ======================================================
    # RECORDS FOUND
    # ======================================================

    else:

        st.write(
            f"{len(medical_records)} "
            "medical record(s) found."
        )

        header = st.columns(
            [2, 2, 3, 3, 1]
        )

        header[0].markdown(
            "**Date**"
        )

        header[1].markdown(
            "**Record Type**"
        )

        header[2].markdown(
            "**Diagnosis / Procedure**"
        )

        header[3].markdown(
            "**Facility**"
        )

        header[4].markdown(
            "**Action**"
        )

        st.divider()

        # ==================================================
        # RECORD ROWS
        # ==================================================

        for record in medical_records:

            record_id = record.get(
                "medical_record_id"
            )

            record_date = record.get(
                "record_date",
                ""
            )

            record_type = record.get(
                "record_type",
                ""
            )

            diagnosis = record.get(
                "diagnosis",
                ""
            )

            procedure_name = record.get(
                "procedure_name",
                ""
            )

            facility_name = record.get(
                "facility_name",
                ""
            )

            diagnosis_display = (
                diagnosis
                if diagnosis
                else procedure_name
            )

            row = st.columns(
                [2, 2, 3, 3, 1]
            )

            row[0].write(
                record_date
            )

            row[1].write(
                record_type
            )

            row[2].write(
                diagnosis_display
            )

            row[3].write(
                facility_name
            )

            if row[4].button(
                "View",
                key=f"view_medical_record_{record_id}",
                width="stretch"
            ):

                st.session_state[
                    "selected_medical_record"
                ] = record

                st.rerun()

            st.divider()

    # ======================================================
    # BACK BUTTON
    # ======================================================

    if st.button(
        "Back",
        width="stretch",
        key=f"medical_history_back_{patient_id}"
    ):

        st.session_state.pop(
            "selected_medical_patient",
            None
        )

        st.session_state.pop(
            "selected_medical_record",
            None
        )

        st.session_state.pop(
            "adding_medical_record",
            None
        )

        st.rerun()

def show_medical_record_details(record):

    medical_record_id = record.get(
        "medical_record_id"
    )
    # ======================================================
    # FORM 3-A
    # VIEW MEDICAL RECORD
    # ======================================================

    st.markdown(
        "### Medical Record Details"
    )

    # ======================================================
    # RECORD INFORMATION
    # ======================================================

    st.markdown(
        "#### Record Information"
    )

    record_date = record.get(
        "record_date",
        ""
    )

    record_type = record.get(
        "record_type",
        ""
    )

    facility_name = record.get(
        "facility_name",
        ""
    )

    department = record.get(
        "department",
        ""
    )

    attending_physician = record.get(
        "attending_physician",
        ""
    )

    record_source = record.get(
        "record_source",
        "External"
    )

    col1, col2 = st.columns(2)

    with col1:

        st.markdown(
            "**Record Date**"
        )

        st.write(
            record_date
        )

    with col2:

        st.markdown(
            "**Record Type**"
        )

        st.write(
            record_type
        )

    col1, col2 = st.columns(2)

    with col1:

        st.markdown(
            "**Healthcare Facility**"
        )

        st.write(
            facility_name or "N/A"
        )

    with col2:

        st.markdown(
            "**Department**"
        )

        st.write(
            department or "N/A"
        )

    st.markdown(
        "**Attending Physician**"
    )

    st.write(
        attending_physician or "N/A"
    )

    st.markdown(
        "**Record Source**"
    )

    st.write(
        record_source
    )

    st.divider()

    # ======================================================
    # CLINICAL INFORMATION
    # ======================================================

    st.markdown(
        "#### Clinical Information"
    )

    fields = [
        (
            "Chief Complaint",
            record.get(
                "chief_complaint"
            )
        ),
        (
            "Clinical History",
            record.get(
                "clinical_history"
            )
        ),
        (
            "Diagnosis",
            record.get(
                "diagnosis"
            )
        ),
        (
            "Procedure",
            record.get(
                "procedure_name"
            )
        ),
        (
            "Findings",
            record.get(
                "findings"
            )
        ),
        (
            "Impression",
            record.get(
                "impression"
            )
        ),
        (
            "Treatment",
            record.get(
                "treatment"
            )
        ),
        (
            "Follow-up / Recommendations",
            record.get(
                "follow_up"
            )
        )
    ]

    for label, value in fields:

        st.markdown(
            f"**{label}**"
        )

        st.write(
            value or "N/A"
        )

    st.divider()

    st.markdown("#### Medical Documents")

    images = get_medical_record_images(
        medical_record_id
    )

    if not images:

        st.info(
            "No medical documents attached to this record."
        )

    else:

        for image in images:

            image_url = image.get(
                "image_url"
            )

            image_type = image.get(
                "image_type",
                "Medical Document"
            )

            if not image_url:
                continue

            signed_url = get_medical_record_file_url(
                image_url
            )

            if not signed_url:
                st.error(
                    f"Unable to load {image_type}."
                )
                continue

            st.markdown(
                f"**{image_type}**"
            )

            # Display images
            if image_url.lower().endswith(
                (".jpg", ".jpeg", ".png", ".webp")
            ):
                st.image(
                    signed_url,
                    width="stretch"
                )

            # Display PDFs
            elif image_url.lower().endswith(
                ".pdf"
            ):
                st.markdown(
                    f"[Open medical document]({signed_url})"
                )

    # ======================================================
    # BACK
    # ======================================================

    if st.button(
        "Back to Medical History",
        width="stretch",
        key="back_to_medical_history"
    ):

        st.session_state.pop(
            "selected_medical_record",
            None
        )

        st.rerun()

def show_create_external_record_form(patient):

    st.markdown("### Add External Medical Record")

    st.caption(
        "Enter a medical record from a previous healthcare facility."
    )

    # ==========================================================
    # PATIENT INFORMATION
    # ==========================================================

    patient_id = patient.get("patient_id")

    first_name = patient.get("first_name", "")
    middle_name = patient.get("middle_name", "")
    last_name = patient.get("last_name", "")

    full_name = " ".join(
        part
        for part in [
            first_name,
            middle_name,
            last_name
        ]
        if part
    )

    st.markdown("#### Patient Information")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Patient Name**")
        st.write(full_name)

    with col2:
        st.markdown("**Date of Birth**")
        st.write(
            patient.get(
                "date_of_birth",
                "N/A"
            )
        )

    with col3:
        st.markdown("**Sex**")
        st.write(
            patient.get(
                "sex",
                "N/A"
            )
        )

    st.divider()

    # ==========================================================
    # RECORD INFORMATION
    # ==========================================================

    st.markdown("#### Record Information")

    col1, col2 = st.columns(2)

    with col1:

        record_date = st.date_input(
            "Record Date",
            key="external_record_date"
        )

    with col2:

        record_type = st.selectbox(
            "Record Type",
            [
                "X-Ray",
                "CT Scan",
                "MRI",
                "Laboratory Result",
                "Diagnosis",
                "Medical Report",
                "Other"
            ],
            key="external_record_type"
        )

    st.divider()

    # ==========================================================
    # FACILITY INFORMATION
    # ==========================================================

    st.markdown("#### Healthcare Facility")

    facility_name = st.text_input(
        "Healthcare Facility *",
        placeholder="e.g. Chong Hua Hospital",
        key="external_facility_name"
    )

    col1, col2 = st.columns(2)

    with col1:

        department = st.text_input(
            "Department",
            placeholder="e.g. Radiology",
            key="external_department"
        )

    with col2:

        attending_physician = st.text_input(
            "Attending Physician",
            placeholder="e.g. Dr. Juan Dela Cruz",
            key="external_attending_physician"
        )

    st.divider()

    # ==========================================================
    # CLINICAL INFORMATION
    # ==========================================================

    st.markdown("#### Clinical Information")

    chief_complaint = st.text_area(
        "Chief Complaint",
        placeholder="Enter the patient's main complaint...",
        key="external_chief_complaint"
    )

    clinical_history = st.text_area(
        "Clinical History",
        placeholder="Enter relevant clinical history...",
        key="external_clinical_history"
    )

    diagnosis = st.text_area(
        "Diagnosis",
        placeholder="Enter the diagnosis...",
        key="external_diagnosis"
    )

    procedure_name = st.text_input(
        "Procedure",
        placeholder="e.g. Chest PA and Lateral",
        key="external_procedure"
    )

    findings = st.text_area(
        "Findings",
        placeholder="Enter the findings from the previous examination...",
        key="external_findings"
    )

    impression = st.text_area(
        "Impression",
        placeholder="Enter the final impression...",
        key="external_impression"
    )

    treatment = st.text_area(
        "Treatment",
        placeholder="Enter treatment provided, if available...",
        key="external_treatment"
    )

    follow_up = st.text_area(
        "Follow-up / Recommendations",
        placeholder="Enter follow-up instructions or recommendations...",
        key="external_follow_up"
    )

    st.divider()

    # ==========================================================
    # MEDICAL DOCUMENTS
    # ==========================================================

    st.markdown("#### Medical Documents")

    st.caption(
        "Upload previous X-rays, medical reports, laboratory "
        "results, or other supporting documents."
    )

    uploaded_files = st.file_uploader(
        "Upload Medical Images or Documents",
        type=[
            "jpg",
            "jpeg",
            "png",
            "webp",
            "pdf"
        ],
        accept_multiple_files=True,
        key="external_medical_files"
    )

    if uploaded_files:

        st.write(
            f"{len(uploaded_files)} file(s) selected."
        )

        for uploaded_file in uploaded_files:

            file_size_mb = (
                uploaded_file.size / (1024 * 1024)
            )

            st.write(
                f"📎 **{uploaded_file.name}** "
                f"({file_size_mb:.2f} MB)"
            )

    st.divider()

    # ==========================================================
    # CURRENT LOGGED-IN USER
    # ==========================================================

    current_user = st.session_state.get(
        "user",
        {}
    )

    created_by = current_user.get(
        "user_id"
    )

    # ==========================================================
    # ACTION BUTTONS
    # ==========================================================

    col1, col2 = st.columns(2)

    # ==========================================================
    # CANCEL
    # ==========================================================

    with col1:

        if st.button(
            "Cancel",
            width="stretch",
            key="cancel_external_record"
        ):

            st.session_state.pop(
                "adding_medical_record",
                None
            )

            st.session_state.pop(
                "external_medical_files",
                None
            )

            st.rerun()

    # ==========================================================
    # SAVE
    # ==========================================================

    with col2:

        if st.button(
            "Save Medical Record",
            width="stretch",
            type="primary",
            key="save_external_record"
        ):

            # ==================================================
            # VALIDATION
            # ==================================================

            if not facility_name.strip():

                st.error(
                    "Healthcare Facility is required."
                )

                return

            if not created_by:

                st.error(
                    "Unable to identify the current user. "
                    "Please log in again."
                )

                return

            # ==================================================
            # CREATE MEDICAL RECORD
            # ==================================================

            with st.spinner(
                "Saving medical record..."
            ):

                result = create_medical_record(
                    patient_id=patient_id,
                    record_date=record_date,
                    record_type=record_type,
                    facility_name=facility_name,
                    department=department,
                    attending_physician=attending_physician,
                    chief_complaint=chief_complaint,
                    clinical_history=clinical_history,
                    diagnosis=diagnosis,
                    procedure_name=procedure_name,
                    findings=findings,
                    impression=impression,
                    treatment=treatment,
                    follow_up=follow_up,
                    created_by=created_by
                )

            # ==================================================
            # CHECK MEDICAL RECORD CREATION
            # ==================================================

            if not result.get("success"):

                st.error(
                    result.get(
                        "message",
                        "Failed to create medical record."
                    )
                )

                return

            # ==================================================
            # GET CREATED MEDICAL RECORD
            # ==================================================

            medical_record = result.get(
                "data"
            )

            if not medical_record:

                st.error(
                    "Medical record was created, "
                    "but its ID could not be retrieved."
                )

                return

            medical_record_id = medical_record.get(
                "medical_record_id"
            )

            if not medical_record_id:

                st.error(
                    "Medical record ID is missing."
                )

                return

            # ==================================================
            # UPLOAD MEDICAL DOCUMENTS
            # ==================================================

            upload_failed = False

            if uploaded_files:

                progress_text = st.empty()

                for index, uploaded_file in enumerate(
                    uploaded_files,
                    start=1
                ):

                    progress_text.write(
                        f"Uploading file {index} "
                        f"of {len(uploaded_files)}: "
                        f"**{uploaded_file.name}**"
                    )

                    upload_result = (
                        upload_medical_record_file(
                            medical_record_id=medical_record_id,
                            uploaded_file=uploaded_file,
                            image_type=record_type
                        )
                    )

                    if not upload_result.get(
                        "success"
                    ):

                        upload_message = (
                            upload_result.get(
                                "message",
                                "Unknown error."
                            )
                        )

                        st.error(
                            f"Failed to upload "
                            f"**{uploaded_file.name}**: "
                            f"{upload_message}"
                        )

                        upload_failed = True

                        break

                progress_text.empty()

            # ==================================================
            # UPLOAD FAILURE
            # ==================================================

            if upload_failed:

                st.warning(
                    "The medical record was created, "
                    "but one or more files could not "
                    "be uploaded."
                )

                return

            # ==================================================
            # SUCCESS
            # ==================================================

            st.session_state.pop(
                "adding_medical_record",
                None
            )

            st.session_state.pop(
                "external_medical_files",
                None
            )

            st.session_state[
                "medical_record_created_success"
            ] = True

            st.rerun()

def show_patient_filters(patients):

    col1, col2 = st.columns([3, 1])

    # ------------------------------------------------------
    # Search
    # ------------------------------------------------------

    with col1:

        search = st.text_input(
            "Search Patient",
            placeholder="Search by patient name...",
            key="medical_records_patient_search"
        )

    # ------------------------------------------------------
    # Sex Filter
    # ------------------------------------------------------

    with col2:

        sex_filter = st.selectbox(
            "Sex",
            [
                "All",
                "Male",
                "Female"
            ],
            key="medical_records_sex_filter"
        )

    # ------------------------------------------------------
    # Apply Filters
    # ------------------------------------------------------

    filtered_patients = []

    search = search.strip().lower()

    for patient in patients:

        first_name = patient.get(
            "first_name",
            ""
        )

        middle_name = patient.get(
            "middle_name",
            ""
        )

        last_name = patient.get(
            "last_name",
            ""
        )

        full_name = " ".join(
            part
            for part in [
                first_name,
                middle_name,
                last_name
            ]
            if part
        )

        patient_sex = patient.get(
            "sex",
            ""
        )

        # --------------------------------------------------
        # Search Match
        # --------------------------------------------------

        search_match = (
            not search
            or search in full_name.lower()
        )

        # --------------------------------------------------
        # Sex Match
        # --------------------------------------------------

        sex_match = (
            sex_filter == "All"
            or patient_sex.lower() == sex_filter.lower()
        )

        # --------------------------------------------------
        # Add Patient
        # --------------------------------------------------

        if search_match and sex_match:

            filtered_patients.append(
                patient
            )

    return filtered_patients
