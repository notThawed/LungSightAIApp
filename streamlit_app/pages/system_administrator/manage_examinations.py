import streamlit as st

from datetime import date, datetime, timezone
from streamlit_drawable_canvas import st_canvas

from backend.fetches import (
    get_all_patients,
    get_examinations_by_patient,
    get_examination_consents,
    get_examination_vitals,
    get_medical_records_by_patient,
    get_all_hospitals,
    get_consent_signature_url,
)

from backend.crud import (
    create_examination,
    update_examination,
    add_examination_vitals,
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
    pill,
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

WIDTHS = [1.3, 3, 1.5, 0.9, 1.8, 1.4]
WIDTHS_SUPERADMIN = [1.6, 1.3, 2.6, 1.3, 0.8, 1.5, 1.2]
HEADERS = ["Patient ID", "Name", "Date of birth", "Sex", "Contact", ""]
HEADERS_SUPERADMIN = ["Hospital", "Patient ID", "Name", "Date of birth", "Sex", "Contact", ""]

HISTORY_WIDTHS = [1.5, 2, 1.4, 0.8, 0.8]
HISTORY_HEADERS = ["Date", "Type", "Status", "", ""]

STATUS_TONES = {
    "Completed": "green",
    "Pending": "amber",
    "In Progress": "blue",
    "Cancelled": "red",
}

ROLE_SUPERADMIN = 1
ROLE_RADIOLOGIST = 3
ROLE_RADTECH = 4
ROLE_HOSPITAL_ADMIN = 6
ROLE_STAFF = 7

ADMIN_ROLES = [ROLE_SUPERADMIN, ROLE_HOSPITAL_ADMIN]
NURSE_ROLES = [ROLE_STAFF]

FIXED_EXAM_TYPE = "General Consult"

DISPOSITION_OPTIONS = [
    "Discharged",
    "Admitted",
    "Referred",
    "Transferred",
    "Sent Home",
]


# ============================================================
# HELPERS
# ============================================================

def load_patients():
    try:
        return get_all_patients() or []
    except Exception as error:
        st.error(f"Unable to load patients: {error}")
        return []


def patient_name(patient):
    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )


def patient_code(patient):
    return patient.get("patient_code") or patient.get("patient_id")


def patient_hospital_name(patient):
    hospitals = patient.get("hospitals")
    if isinstance(hospitals, dict):
        return hospitals.get("hospital_name") or "—"
    if isinstance(hospitals, list) and hospitals:
        return hospitals[0].get("hospital_name") or "—"
    return "—"


def patient_summary_rows(patient):
    return [
        ("Patient", patient_name(patient)),
        ("Patient ID", patient_code(patient)),
        ("Date of birth", format_date(patient.get("date_of_birth"))),
        ("Sex", patient.get("sex")),
        ("Hospital", patient_hospital_name(patient)),
    ]


def open_dialog(name, **state):
    st.session_state["examination_dialog"] = name
    for key, value in state.items():
        st.session_state[key] = value
    st.rerun()


def current_user():
    return st.session_state.get("user") or {}


def current_role_id():
    return (st.session_state.get("user") or {}).get("role_id")


def current_hospital_id():
    return (st.session_state.get("user") or {}).get("hospital_id")


def is_superadmin():
    return current_role_id() == ROLE_SUPERADMIN


def is_hospital_admin():
    return current_role_id() == ROLE_HOSPITAL_ADMIN


def is_admin_role():
    return current_role_id() in ADMIN_ROLES


def is_nurse_role():
    return current_role_id() in NURSE_ROLES


def is_minor(date_of_birth):
    if not date_of_birth:
        return False
    try:
        dob = date.fromisoformat(str(date_of_birth)[:10])
    except (ValueError, TypeError):
        return False

    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age < 18


def _get_vitals_value(vitals_list, field_name):
    for v in vitals_list:
        if v.get(field_name) is not None:
            return v[field_name]
    return None


def render_medical_history_inline(patient):
    """
    Inline medical history section (used inside dialogs).
    Streamlit blocks nested dialogs, so we render inline instead.
    """

    with st.expander("📁 View medical history", expanded=False):

        records = get_medical_records_by_patient(patient.get("patient_id"))

        if not records:
            st.caption("No past medical records found.")
            return

        for record in records:
            st.markdown(
                f"**{record.get('record_type') or 'Record'}** — "
                f"{format_date(record.get('record_date'))}"
            )
            st.caption(
                f"{record.get('facility_name') or '—'} • "
                f"{record.get('diagnosis') or 'No diagnosis'}"
            )
            st.divider()


# ============================================================
# DIALOG 1: EXAMINATION HISTORY (per patient)
# ============================================================

@st.dialog("Patient examinations", width="medium")
def show_examination_dialog(patient):

    role_id = current_role_id()
    can_delete = is_admin_role()
    can_create = is_nurse_role() or is_admin_role()

    with st.container(key="sa_dialog"):

        show_rows(patient_summary_rows(patient))

        section_title("Examination history")

        examinations = get_examinations_by_patient(patient["patient_id"])

        if not examinations:
            empty_state("No examination history found for this patient.")

        else:
            with st.container(key="sa_table_history"):

                table_header(HISTORY_HEADERS, HISTORY_WIDTHS, "history")

                for examination in examinations:

                    exam_id = examination["examination_id"]
                    status = examination.get("status") or "—"

                    with table_row(f"history_{exam_id}", HISTORY_WIDTHS) as cols:

                        text_cell(cols[0], format_date(examination.get("examination_date")))
                        text_cell(cols[1], examination.get("examination_type"))
                        pill_cell(cols[2], status, STATUS_TONES.get(status, "grey"))

                        # Pending → Edit | Completed/Cancelled → View
                        if status == "Pending":
                            if cols[3].button(
                                "Edit", key=f"edit_exam_{exam_id}", width="stretch",
                            ):
                                open_dialog(
                                    "create",
                                    selected_examination=examination,
                                    create_examination_patient=patient,
                                )
                        else:
                            if cols[3].button(
                                "View", key=f"view_exam_{exam_id}", width="stretch",
                            ):
                                open_dialog(
                                    "view",
                                    selected_examination=examination,
                                    edit_patient=patient,
                                )

                        if can_delete:
                            if cols[4].button(
                                "", key=f"delete_exam_{exam_id}",
                                icon=":material/delete:", help="Delete examination",
                            ):
                                open_dialog("delete", delete_examination_target=examination)

        # Inline medical history (no nested dialog)
        render_medical_history_inline(patient)

        if can_create:
            if st.button(
                "New examination", key="new_examination", icon=":material/add:",
                type="primary", width="stretch",
            ):
                open_dialog("create", create_examination_patient=patient)


# ============================================================
# DIALOG 2: CONFIRM DELETE
# ============================================================

@st.dialog("Delete examination", width="small")
def show_delete_examination_dialog(examination):

    with st.container(key="sa_dialog"):

        st.markdown(
            f"<p class='sa-dialog-text'>Delete this <b>{examination.get('examination_type')}</b> "
            f"examination from <b>{format_date(examination.get('examination_date'))}</b>?</p>",
            unsafe_allow_html=True,
        )

        st.warning("This permanently removes the examination, its consent, and its vitals. Cannot be undone.")

        if confirm_buttons(f"delete_exam_{examination['examination_id']}", "Delete permanently"):
            try:
                delete_examination(examination["examination_id"])
                st.session_state.pop("delete_examination_target", None)
                st.session_state["examination_dialog"] = None
                remember("Examination deleted.")
                st.rerun()
            except Exception as error:
                st.error(f"Failed to delete examination: {error}")


# ============================================================
# DIALOG 3: NURSE - CREATE / EDIT EXAMINATION
# ============================================================

@st.dialog("Create examination", width="large")
def show_nurse_create_dialog(patient, examination=None):

    user_id = current_user().get("user_id")
    is_edit = examination is not None

    with st.container(key="sa_dialog"):

        show_rows(patient_summary_rows(patient))

        # Inline medical history (no nested dialog)
        render_medical_history_inline(patient)

        errors = st.container()

        existing_consent = None
        existing_vitals = []
        if is_edit:
            consents = get_examination_consents(examination["examination_id"])
            existing_consent = consents[0] if consents else None
            existing_vitals = get_examination_vitals(examination["examination_id"])

        guardian_needed = is_minor(patient.get("date_of_birth"))

        section_title("Consent")

        signed_by_name = st.text_input(
            "Patient/Guardian name",
            value=(existing_consent or {}).get("signed_by_name") or patient_name(patient),
            key="nurse_consent_name",
        )

        guardian_name = None
        guardian_relation = None
        signed_by_type = "patient"

        if guardian_needed:
            signed_by_type = "guardian"
            gcol1, gcol2 = st.columns(2)
            guardian_name = gcol1.text_input(
                "Guardian name",
                value=(existing_consent or {}).get("guardian_name") or "",
                key="nurse_guardian_name",
            )
            relation_options = ["Parent", "Guardian", "Spouse", "Sibling", "Other"]
            current_relation = (existing_consent or {}).get("guardian_relation") or "Parent"
            guardian_relation = gcol2.selectbox(
                "Guardian relationship",
                relation_options,
                index=relation_options.index(current_relation) if current_relation in relation_options else 0,
                key="nurse_guardian_relation",
            )

        st.markdown("**Signature** — ask the patient/guardian to sign below:")

        canvas_result = st_canvas(
            stroke_width=2,
            stroke_color="#000000",
            background_color="#FFFFFF",
            height=150,
            width=500,
            drawing_mode="freedraw",
            return_image_data=True,     # ← ADD THIS LINE
            key=f"signature_canvas_{examination['examination_id'] if is_edit else 'new'}",
        )

        consent_confirmed = st.checkbox(
            "I confirm the patient/guardian signed the consent above.",
            key="nurse_consent_confirm",
        )

        st.divider()
        section_title("Vital signs")

        v1, v2, v3 = st.columns(3)

        bp_sys = v1.number_input(
            "BP systolic (mmHg)",
            min_value=0, max_value=300, step=1,
            value=int(_get_vitals_value(existing_vitals, "bp_systolic") or 0),
            key="nurse_bp_sys",
        )
        bp_dia = v2.number_input(
            "BP diastolic (mmHg)",
            min_value=0, max_value=200, step=1,
            value=int(_get_vitals_value(existing_vitals, "bp_diastolic") or 0),
            key="nurse_bp_dia",
        )
        temp = v3.number_input(
            "Temperature (°C)",
            min_value=0.0, max_value=50.0, step=0.1,
            value=float(_get_vitals_value(existing_vitals, "temperature") or 0.0),
            key="nurse_temp",
        )

        st.divider()
        cancel_col, save_col = st.columns(2)

        cancel_clicked = cancel_col.button("Cancel", key="nurse_cancel", width="stretch")
        save_clicked = save_col.button(
            "Save Changes" if is_edit else "Create Examination",
            key="nurse_save", type="primary", width="stretch",
        )

    if cancel_clicked:
        st.session_state.pop("create_examination_patient", None)
        st.session_state.pop("selected_examination", None)
        st.session_state["examination_dialog"] = None
        st.rerun()

    if not save_clicked:
        return

    if not signed_by_name.strip():
        errors.error("Patient/Guardian name is required.")
        return

    if not consent_confirmed:
        errors.error("Please confirm the consent was signed.")
        return

    has_signature = (
        canvas_result.image_data is not None
        and canvas_result.image_data[:, :, 3].sum() > 0
    )

    if not has_signature and not (existing_consent and existing_consent.get("signature_path")):
        errors.error("Please draw the patient/guardian signature in the box.")
        return

    try:
        if not is_edit:

            new_rows = create_examination(
                patient_id=patient["patient_id"],
                examination_type=FIXED_EXAM_TYPE,
                examination_date=date.today(),
                created_by=user_id,
                consent_given=True,
                consent_signed_by_name=signed_by_name.strip(),
                consent_signed_by_type=signed_by_type,
                consent_guardian_name=(guardian_name or "").strip() or None,
                consent_guardian_relation=guardian_relation,
                consent_witnessed_by=user_id,
                bp_systolic=bp_sys or None,
                bp_diastolic=bp_dia or None,
                temperature=temp or None,
            )

            if not new_rows:
                errors.error("Failed to create examination.")
                return

            exam_id = new_rows[0]["examination_id"]

            if has_signature:
                import io
                from PIL import Image

                img = Image.fromarray(canvas_result.image_data.astype("uint8"), "RGBA")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                signature_bytes = buf.getvalue()

                sig_path = upload_consent_signature(exam_id, signature_bytes)

                if sig_path:
                    consents = get_examination_consents(exam_id)
                    if consents:
                        update_examination_consent(
                            consents[0]["consent_id"],
                            signature_path=sig_path,
                        )

            st.session_state.pop("create_examination_patient", None)

        else:
            exam_id = examination["examination_id"]

            if existing_consent:
                consent_updates = {
                    "given": True,
                    "signed_by_name": signed_by_name.strip(),
                    "signed_by_type": signed_by_type,
                    "guardian_name": (guardian_name or "").strip() or None,
                    "guardian_relation": guardian_relation,
                }

                if has_signature:
                    import io
                    from PIL import Image

                    img = Image.fromarray(canvas_result.image_data.astype("uint8"), "RGBA")
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    signature_bytes = buf.getvalue()

                    sig_path = upload_consent_signature(exam_id, signature_bytes)
                    if sig_path:
                        consent_updates["signature_path"] = sig_path

                update_examination_consent(existing_consent["consent_id"], **consent_updates)

            if existing_vitals:
                update_examination_vitals(
                    existing_vitals[0]["vitals_id"],
                    bp_systolic=bp_sys or None,
                    bp_diastolic=bp_dia or None,
                    temperature=temp or None,
                )

            update_examination(examination_id=exam_id, status="Pending")

            st.session_state.pop("selected_examination", None)

        st.session_state["examination_dialog"] = None
        remember("Examination saved.")
        st.rerun()

    except Exception as error:
        errors.error(f"Failed to save examination: {error}")


# ============================================================
# DIALOG 4: VIEW (read-only) for completed exams
# ============================================================

@st.dialog("Examination details", width="medium")
def show_view_dialog(patient, examination):

    with st.container(key="sa_dialog"):

        show_rows(patient_summary_rows(patient))

        st.caption(
            f"**Type:** {examination.get('examination_type')}  •  "
            f"**Status:** {examination.get('status')}"
        )

        section_title("Consent")
        consents = get_examination_consents(examination["examination_id"])
        consent = consents[0] if consents else None

        if consent and consent.get("given"):
            st.markdown(f"**Signed by:** {consent.get('signed_by_name') or '—'}")
            sig_path = consent.get("signature_path")
            if sig_path:
                sig_url = get_consent_signature_url(sig_path)
                if sig_url:
                    st.image(sig_url, width=200)
        else:
            st.caption("No consent recorded.")

        section_title("Vitals")
        vitals = get_examination_vitals(examination["examination_id"])
        if vitals:
            for v in vitals:
                st.caption(
                    f"BP {v.get('bp_systolic') or '—'}/{v.get('bp_diastolic') or '—'} • "
                    f"Temp {v.get('temperature') or '—'} • "
                    f"PR {v.get('pulse_rate') or '—'} • "
                    f"SpO2 {v.get('spo2') or '—'}"
                )
        else:
            st.caption("No vitals recorded.")

        section_title("Clinical notes")
        for label, key in [
            ("Chief complaint", "chief_complaint"),
            ("HPI", "history_of_present_illness"),
            ("Physical exam", "physical_examination"),
            ("Diagnosis", "diagnosis"),
            ("Plans / orders", "plans_orders"),
        ]:
            st.markdown(f"**{label}:** {examination.get(key) or '—'}")

        section_title("Disposition")
        st.markdown(f"**Disposition:** {examination.get('disposition') or '—'}")
        st.markdown(f"**Notes:** {examination.get('disposition_notes') or '—'}")

        if st.button("Close", key="close_view", width="stretch"):
            st.session_state.pop("selected_examination", None)
            st.session_state["examination_dialog"] = None
            st.rerun()


# ============================================================
# FILTERS + TABLE
# ============================================================

def show_filters(patients, hospitals=None):

    if is_superadmin() and hospitals is not None:

        hospital_col, search_col, sex_col, status_col, reset_col = st.columns([1.5, 2.5, 1, 1, 0.8])

        hospital_names = ["All hospitals"] + sorted({h.get("hospital_name") for h in hospitals if h.get("hospital_name")})
        hospital_filter = hospital_col.selectbox(
            "Hospital", hospital_names, label_visibility="collapsed", key="exam_hospital_filter",
        )

        search = search_col.text_input(
            "Search", placeholder="Search by name or contact",
            label_visibility="collapsed", key="exam_search",
        ).strip().lower()

        sex = sex_col.selectbox("Sex", ["All sexes", "Male", "Female"], label_visibility="collapsed", key="exam_sex")
        status = status_col.selectbox("Status", ["All status", "Active", "Inactive"], label_visibility="collapsed", key="exam_status")

        if reset_col.button("Refresh", icon=":material/refresh:", width="stretch", key="exam_refresh"):
            st.rerun()

        matches = []
        for patient in patients:
            text = f"{patient_name(patient)} {patient.get('contact_number') or ''}".lower()

            if hospital_filter != "All hospitals" and patient_hospital_name(patient) != hospital_filter:
                continue
            if search and search not in text:
                continue
            if sex != "All sexes" and patient.get("sex") != sex:
                continue
            if status != "All status" and patient.get("status") != status:
                continue

            matches.append(patient)

        return matches

    search_col, sex_col, status_col, reset_col = st.columns([3, 1.2, 1.2, 1])

    search = search_col.text_input(
        "Search", placeholder="Search by patient name or contact number",
        label_visibility="collapsed", key="exam_search",
    ).strip().lower()

    sex = sex_col.selectbox("Sex", ["All sexes", "Male", "Female"], label_visibility="collapsed", key="exam_sex")
    status = status_col.selectbox("Status", ["All status", "Active", "Inactive"], label_visibility="collapsed", key="exam_status")

    if reset_col.button("Refresh", icon=":material/refresh:", width="stretch", key="exam_refresh"):
        st.rerun()

    matches = []
    for patient in patients:
        text = f"{patient_name(patient)} {patient.get('contact_number') or ''}".lower()

        if search and search not in text:
            continue
        if sex != "All sexes" and patient.get("sex") != sex:
            continue
        if status != "All status" and patient.get("status") != status:
            continue

        matches.append(patient)

    return matches


def render_patient_table(patients):

    if not patients:
        empty_state("No patients found.")
        return

    superadmin = is_superadmin()

    with st.container(key="sa_table_exam_patients"):

        if superadmin:
            table_header(HEADERS_SUPERADMIN, WIDTHS_SUPERADMIN, "exam_patients")

            for patient in patients:
                patient_id = patient.get("patient_id")

                with table_row(f"exam_patients_{patient_id}", WIDTHS_SUPERADMIN) as cols:
                    text_cell(cols[0], patient_hospital_name(patient), muted=True)
                    text_cell(cols[1], patient_code(patient), muted=True)
                    name_cell(cols[2], patient_name(patient))
                    text_cell(cols[3], format_date(patient.get("date_of_birth")))
                    text_cell(cols[4], patient.get("sex"))
                    text_cell(cols[5], patient.get("contact_number"))

                    if cols[6].button(
                        "Examine", key=f"examine_{patient_id}",
                        icon=":material/clinical_notes:", width="stretch",
                    ):
                        open_dialog("history", selected_patient=patient)
        else:
            table_header(HEADERS, WIDTHS, "exam_patients")

            for patient in patients:
                patient_id = patient.get("patient_id")

                with table_row(f"exam_patients_{patient_id}", WIDTHS) as cols:
                    text_cell(cols[0], patient_code(patient), muted=True)
                    name_cell(cols[1], patient_name(patient))
                    text_cell(cols[2], format_date(patient.get("date_of_birth")))
                    text_cell(cols[3], patient.get("sex"))
                    text_cell(cols[4], patient.get("contact_number"))

                    if cols[5].button(
                        "Examine", key=f"examine_{patient_id}",
                        icon=":material/clinical_notes:", width="stretch",
                    ):
                        open_dialog("history", selected_patient=patient)


# ============================================================
# PAGE
# ============================================================

def show():

    load_css("manage_examinations.css")
    show_flash_message()

    role_id = current_role_id()
    hospital_id = current_hospital_id()

    with st.container(key="sa_page"):

        page_header(
            "Manage examinations",
            "Select a patient to create and manage examinations.",
        )

        patients = load_patients()

        if is_superadmin():
            hospitals = get_all_hospitals() or []
            matches = show_filters(patients, hospitals=hospitals)
        else:
            if hospital_id is None:
                st.error("Your account is not assigned to a hospital. Please contact your Superadmin.")
                st.stop()

            patients = [p for p in patients if p.get("hospital_id") == hospital_id]
            matches = show_filters(patients)

        render_patient_table(matches)

    # ---- Dialog router ----

    dialog = st.session_state.get("examination_dialog")

    if dialog == "history" and st.session_state.get("selected_patient"):
        show_examination_dialog(st.session_state["selected_patient"])

    elif dialog == "delete" and st.session_state.get("delete_examination_target"):
        show_delete_examination_dialog(st.session_state["delete_examination_target"])

    elif dialog == "create" and st.session_state.get("create_examination_patient"):
        show_nurse_create_dialog(
            st.session_state["create_examination_patient"],
            st.session_state.get("selected_examination"),
        )

    elif dialog == "view" and st.session_state.get("selected_examination"):
        show_view_dialog(
            st.session_state.get("edit_patient"),
            st.session_state["selected_examination"],
        )