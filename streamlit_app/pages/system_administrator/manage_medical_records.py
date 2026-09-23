import streamlit as st

from backend.fetches import (
    get_all_patients,
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
    field,
    full_name,
    format_date,
    table_header,
    table_row,
    name_cell,
    text_cell,
    remember,
    show_flash_message,
)


# Column widths: name, date of birth, sex, view button
WIDTHS = [3.5, 1.8, 1, 1.2]
HEADERS = ["Patient", "Date of birth", "Sex", ""]

# Column widths in the history dialog: date, type, diagnosis, facility, view
RECORD_WIDTHS = [1.4, 1.4, 2.4, 2, 0.9]

RECORD_TYPES = ["X-Ray", "CT Scan", "MRI", "Laboratory Result", "Diagnosis", "Medical Report", "Other"]


def load_patients():
    """Load all patients. Shows an error and returns [] if it fails."""

    try:
        return get_all_patients() or []

    except Exception as error:
        st.error(f"Failed to load patients: {error}")
        return []


def patient_name(patient):
    return full_name(patient.get("first_name"), patient.get("middle_name"), patient.get("last_name"))


def clear_medical_state(*keys):
    for key in keys:
        st.session_state.pop(key, None)


# ============================================================
# VIEW ONE MEDICAL RECORD
# ============================================================

def show_medical_record_details(record):

    record_id = record.get("medical_record_id")

    record_tab, clinical_tab, documents_tab = st.tabs(["Record", "Clinical", "Documents"])

    with record_tab:
        show_rows([
            ("Record date", format_date(record.get("record_date"))),
            ("Record type", record.get("record_type")),
            ("Healthcare facility", record.get("facility_name")),
            ("Department", record.get("department")),
            ("Attending physician", record.get("attending_physician")),
            ("Record source", record.get("record_source") or "External"),
        ])

    with clinical_tab:
        for label, key in [
            ("Chief complaint", "chief_complaint"),
            ("Clinical history", "clinical_history"),
            ("Diagnosis", "diagnosis"),
            ("Procedure", "procedure_name"),
            ("Findings", "findings"),
            ("Impression", "impression"),
            ("Treatment", "treatment"),
            ("Follow-up / recommendations", "follow_up"),
        ]:
            field(label, record.get(key))

    with documents_tab:
        images = get_medical_record_images(record_id)

        if not images:
            empty_state("No medical documents attached to this record.")

        for image in images or []:

            image_url = image.get("image_url")
            image_type = image.get("image_type", "Medical document")

            if not image_url:
                continue

            signed_url = get_medical_record_file_url(image_url)

            if not signed_url:
                st.error(f"Unable to load {image_type}.")
                continue

            st.markdown(f"<p class='sa-subtitle'>{image_type}</p>", unsafe_allow_html=True)

            if image_url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                st.image(signed_url, width="stretch")
            elif image_url.lower().endswith(".pdf"):
                st.markdown(f"[Open medical document]({signed_url})")

    if st.button("Back to medical history", key="back_to_history", width="stretch"):
        clear_medical_state("selected_medical_record")
        st.rerun()


# ============================================================
# ADD AN EXTERNAL MEDICAL RECORD
# ============================================================

def show_create_external_record_form(patient):

    section_title(
        "Add external medical record",
        "Enter a record from a previous healthcare facility.",
    )

    errors = st.container()

    with st.form("external_record_form", clear_on_submit=False):

        date_col, type_col = st.columns(2)

        record_date = date_col.date_input("Record date")
        record_type = type_col.selectbox("Record type", RECORD_TYPES)

        facility_col, department_col, physician_col = st.columns(3)

        facility_name = facility_col.text_input("Healthcare facility *", placeholder="e.g. Chong Hua Hospital")
        department = department_col.text_input("Department", placeholder="e.g. Radiology")
        attending_physician = physician_col.text_input("Attending physician", placeholder="e.g. Dr. Juan Dela Cruz")

        complaint_col, history_col = st.columns(2)

        chief_complaint = complaint_col.text_area("Chief complaint", height=90)
        clinical_history = history_col.text_area("Clinical history", height=90)

        diagnosis_col, procedure_col = st.columns(2)

        diagnosis = diagnosis_col.text_area("Diagnosis", height=90)
        procedure_name = procedure_col.text_area("Procedure", height=90, placeholder="e.g. Chest PA and Lateral")

        findings_col, impression_col = st.columns(2)

        findings = findings_col.text_area("Findings", height=90)
        impression = impression_col.text_area("Impression", height=90)

        treatment_col, follow_up_col = st.columns(2)

        treatment = treatment_col.text_area("Treatment", height=90)
        follow_up = follow_up_col.text_area("Follow-up / recommendations", height=90)

        uploaded_files = st.file_uploader(
            "Medical images or documents",
            type=["jpg", "jpeg", "png", "webp", "pdf"],
            accept_multiple_files=True,
        )

        cancel_col, save_col = st.columns(2)

        cancel = cancel_col.form_submit_button("Cancel", width="stretch")
        save = save_col.form_submit_button("Save medical record", type="primary", width="stretch")

    if cancel:
        clear_medical_state("adding_medical_record")
        st.rerun()

    if not save:
        return

    created_by = (st.session_state.get("user") or {}).get("user_id")

    if not facility_name.strip():
        errors.error("Healthcare facility is required.")
        return

    if not created_by:
        errors.error("Unable to identify the current user. Please log in again.")
        return

    with st.spinner("Saving medical record..."):
        result = create_medical_record(
            patient_id=patient.get("patient_id"),
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
            created_by=created_by,
        )

    if not result.get("success"):
        errors.error(result.get("message", "Failed to create medical record."))
        return

    medical_record_id = (result.get("data") or {}).get("medical_record_id")

    if not medical_record_id:
        errors.error("The record was created, but its ID could not be retrieved.")
        return

    # ---- upload the files, one by one ----

    for index, uploaded_file in enumerate(uploaded_files or [], start=1):

        with st.spinner(f"Uploading file {index} of {len(uploaded_files)}: {uploaded_file.name}"):
            upload_result = upload_medical_record_file(
                medical_record_id=medical_record_id,
                uploaded_file=uploaded_file,
                image_type=record_type,
            )

        if not upload_result.get("success"):
            errors.warning(
                "The record was created, but a file could not be uploaded: "
                f"{uploaded_file.name} ({upload_result.get('message', 'Unknown error.')})"
            )
            return

    clear_medical_state("adding_medical_record")
    remember("Medical record saved.")
    st.rerun()


# ============================================================
# MEDICAL HISTORY DIALOG (history list, one record, or the add form)
# ============================================================

@st.dialog("Medical history", width="medium")
def show_medical_history_dialog(patient):

    with st.container(key="sa_dialog"):

        selected_record = st.session_state.get("selected_medical_record")

        if selected_record:
            show_medical_record_details(selected_record)
            return

        if st.session_state.get("adding_medical_record", False):
            show_create_external_record_form(patient)
            return

        patient_id = patient.get("patient_id")

        show_rows([
            ("Patient", patient_name(patient)),
            ("Date of birth", format_date(patient.get("date_of_birth"))),
            ("Sex", patient.get("sex")),
        ])

        if st.button(
            "Add external record", key=f"add_external_{patient_id}",
            icon=":material/add:", type="primary", width="stretch",
        ):
            st.session_state["adding_medical_record"] = True
            st.rerun()

        records = get_medical_records_by_patient(patient_id)

        if not records:
            empty_state("No external medical records found.")

        else:
            section_title(f"{len(records)} medical record(s)")

            with st.container(key="sa_table_records"):

                table_header(["Date", "Type", "Diagnosis / procedure", "Facility", ""], RECORD_WIDTHS, "records")

                for record in records:

                    record_id = record.get("medical_record_id")

                    with table_row(f"records_{record_id}", RECORD_WIDTHS) as cols:

                        text_cell(cols[0], format_date(record.get("record_date")))
                        text_cell(cols[1], record.get("record_type"))
                        text_cell(cols[2], record.get("diagnosis") or record.get("procedure_name"))
                        text_cell(cols[3], record.get("facility_name"))

                        if cols[4].button("View", key=f"view_record_{record_id}", width="stretch"):
                            st.session_state["selected_medical_record"] = record
                            st.rerun()

        if st.button("Close", key=f"close_history_{patient_id}", width="stretch"):
            clear_medical_state("selected_medical_patient", "selected_medical_record", "adding_medical_record")
            st.rerun()


# ============================================================
# PATIENT LIST
# ============================================================

def show_filters(patients):
    """Search and sex filter. Returns the matching patients."""

    search_col, sex_col = st.columns([3, 1])

    search = search_col.text_input(
        "Search", placeholder="Search by patient name",
        label_visibility="collapsed", key="medical_records_patient_search",
    ).strip().lower()

    sex = sex_col.selectbox(
        "Sex", ["All sexes", "Male", "Female"],
        label_visibility="collapsed", key="medical_records_sex_filter",
    )

    return [
        patient for patient in patients
        if (not search or search in patient_name(patient).lower())
        and (sex == "All sexes" or (patient.get("sex") or "").lower() == sex.lower())
    ]


def render_patient_table(patients):

    if not patients:
        empty_state("No patients found.")
        return

    with st.container(key="sa_table_medical"):

        table_header(HEADERS, WIDTHS, "medical")

        for patient in patients:

            patient_id = patient.get("patient_id")

            with table_row(f"medical_{patient_id}", WIDTHS) as cols:

                name_cell(cols[0], patient_name(patient))
                text_cell(cols[1], format_date(patient.get("date_of_birth")))
                text_cell(cols[2], patient.get("sex"))

                if cols[3].button(
                    "Records", key=f"view_medical_records_{patient_id}",
                    icon=":material/folder_open:", width="stretch",
                ):
                    st.session_state["selected_medical_patient"] = patient
                    st.rerun()


# ============================================================
# PAGE
# ============================================================

def show():

    load_css("manage_medical_records.css")
    show_flash_message()

    with st.container(key="sa_page"):

        page_header("Medical records", "View and manage patient medical history.")

        render_patient_table(show_filters(load_patients()))

    selected_patient = st.session_state.get("selected_medical_patient")

    if selected_patient:
        show_medical_history_dialog(selected_patient)