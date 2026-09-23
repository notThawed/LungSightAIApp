import streamlit as st

from datetime import datetime, timezone

from backend.fetches import (
    get_pending_examinations,
    get_medical_records_by_patient,
    get_examinations_by_patient,
    get_examination_consents,
    get_examination_vitals,
    get_consent_signature_url,
    get_xray_ready_examinations,
    get_medications_by_examination,
    get_referral_by_examination,
)

from backend.crud import (
    update_examination,
    add_examination_vitals,
    create_xray_request,
    add_medication,
    add_referral,
    delete_medications_by_examination,
    delete_referrals_by_examination,
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
    pill,
    metric_card,
    table_header,
    table_row,
    name_cell,
    text_cell,
    pill_cell,
    remember,
    show_flash_message,
    confirm_buttons,
    safe,
)


# ============================================================
# CONFIG
# ============================================================

ROLE_SUPERADMIN = 1
ROLE_RADIOLOGIST = 3       # Doctor
ROLE_RADTECH = 4
ROLE_HOSPITAL_ADMIN = 6
ROLE_STAFF = 7

DOCTOR_ROLES = [ROLE_RADIOLOGIST]
ADMIN_ROLES = [ROLE_SUPERADMIN, ROLE_HOSPITAL_ADMIN]

DISPOSITION_OPTIONS = [
    "Admission",
    "Treated and Sent Home",
    "Referred",
    "Refused Admission",
    "Nowhere When Called",
]

FOLLOW_UP_DISPOSITIONS = [
    "Treated and Sent Home",
    "Referred",
    "Refused Admission",
]

QUEUE_WIDTHS = [2.5, 1, 1, 1.2, 1.2, 1.2]
QUEUE_HEADERS = ["Patient", "Pending", "Waiting", "History", "Actions", ""]


# ============================================================
# HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}


def current_role_id():
    return (st.session_state.get("user") or {}).get("role_id")


def current_hospital_id():
    return (st.session_state.get("user") or {}).get("hospital_id")


def is_doctor_role():
    return current_role_id() in DOCTOR_ROLES


def is_admin_role():
    return current_role_id() in ADMIN_ROLES


def patient_name(patient):
    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )


def patient_code(patient):
    return patient.get("patient_code") or patient.get("patient_id")


def waiting_minutes(created_at_str):
    if not created_at_str:
        return 0

    try:
        created = datetime.fromisoformat(
            created_at_str.replace("Z", "+00:00")
        )
        now = datetime.now(timezone.utc)
        delta = now - created
        return int(delta.total_seconds() // 60)
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


def calculate_bmi(weight_kg, height_cm):
    try:
        w = float(weight_kg)
        h = float(height_cm) / 100.0
        if w <= 0 or h <= 0:
            return None
        return round(w / (h * h), 2)
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


def _get_vitals_value(vitals_list, field_name):
    for v in vitals_list:
        if v.get(field_name) is not None:
            return v[field_name]
    return None


def clear_all_dialog_state():
    for key in (
        "history_patient",
        "pending_exams_patient",
        "selected_examination",
        "edit_patient",
    ):
        st.session_state.pop(key, None)


# ============================================================
# GROUP PENDING EXAMS BY PATIENT
# ============================================================

def group_pending_by_patient(pending_exams):
    by_patient = {}

    for exam in pending_exams:
        patient = exam.get("patients") or {}
        pid = patient.get("patient_id")

        if not pid:
            continue

        if pid not in by_patient:
            by_patient[pid] = {
                "patient": patient,
                "exams": [],
                "oldest_waiting": 0,
            }

        by_patient[pid]["exams"].append(exam)

        wait = waiting_minutes(exam.get("created_at"))
        if wait > by_patient[pid]["oldest_waiting"]:
            by_patient[pid]["oldest_waiting"] = wait

    grouped = list(by_patient.values())
    grouped.sort(key=lambda x: x["oldest_waiting"], reverse=True)

    return grouped


# ============================================================
# SHARED: DISPOSITION + FOLLOW-UP + MEDS + REFERRAL BLOCKS
# ============================================================

def render_disposition_block(examination, key_prefix):
    """Renders disposition + conditional follow-up + meds + referral."""

    result = {
        "disposition": None,
        "disp_notes": None,
        "follow_up_date": None,
        "follow_up_notes": None,
        "meds_list": [],
        "referral_data": None,
    }

    st.divider()
    section_title("Disposition")

    current_disp = examination.get("disposition")
    disp_index = (
        DISPOSITION_OPTIONS.index(current_disp)
        if current_disp in DISPOSITION_OPTIONS
        else 0
    )

    disposition = st.selectbox(
        "Disposition",
        DISPOSITION_OPTIONS,
        index=disp_index,
        key=f"{key_prefix}_disposition",
    )

    disp_notes = st.text_area(
        "Disposition notes",
        value=examination.get("disposition_notes") or "",
        height=100,
        key=f"{key_prefix}_disp_notes",
    )

    result["disposition"] = disposition
    result["disp_notes"] = disp_notes

    if disposition in FOLLOW_UP_DISPOSITIONS:
        st.divider()
        section_title("Follow-Up")

        follow_up_date = st.date_input(
            "Follow-up date (optional)",
            value=None,
            key=f"{key_prefix}_follow_up_date",
        )

        follow_up_notes = st.text_area(
            "Follow-up notes (optional)",
            value="",
            height=80,
            key=f"{key_prefix}_follow_up_notes",
        )

        result["follow_up_date"] = follow_up_date
        result["follow_up_notes"] = follow_up_notes

    if disposition in FOLLOW_UP_DISPOSITIONS:
        st.divider()
        section_title("Medications")

        num_meds = st.number_input(
            "Number of medications",
            min_value=0, max_value=10, step=1,
            value=0,
            key=f"{key_prefix}_num_meds",
        )

        for i in range(int(num_meds)):
            st.markdown(f"**Medication #{i + 1}**")
            m1, m2, m3, m4 = st.columns([2, 1, 1, 1])

            drug = m1.text_input(
                "Drug name", key=f"{key_prefix}_med_drug_{i}"
            )
            dose = m2.text_input(
                "Dose", key=f"{key_prefix}_med_dose_{i}"
            )
            freq = m3.text_input(
                "Frequency", key=f"{key_prefix}_med_freq_{i}"
            )
            dur = m4.text_input(
                "Duration", key=f"{key_prefix}_med_dur_{i}"
            )

            if drug.strip():
                result["meds_list"].append({
                    "drug_name": drug.strip(),
                    "dose": dose.strip() or None,
                    "frequency": freq.strip() or None,
                    "duration": dur.strip() or None,
                })

    if disposition == "Referred":
        st.divider()
        section_title("Referral Details")

        r1, r2 = st.columns([2, 1])
        referred_to = r1.text_input(
            "Referred to (specialist / hospital)",
            key=f"{key_prefix}_referral_to",
        )
        urgency = r2.selectbox(
            "Urgency",
            ["Routine", "Urgent", "Emergency"],
            key=f"{key_prefix}_referral_urgency",
        )

        reason = st.text_area(
            "Reason for referral",
            height=80,
            key=f"{key_prefix}_referral_reason",
        )

        ref_notes = st.text_area(
            "Referral notes (optional)",
            height=60,
            key=f"{key_prefix}_referral_notes",
        )

        if referred_to.strip():
            result["referral_data"] = {
                "referred_to": referred_to.strip(),
                "reason": reason.strip() or None,
                "urgency": urgency,
                "notes": ref_notes.strip() or None,
            }

    return result


def save_disposition_extras(exam_id, user_id, result):
    """Saves meds + referral after the examination update."""

    delete_medications_by_examination(exam_id)
    for med in result["meds_list"]:
        add_medication(
            examination_id=exam_id,
            drug_name=med["drug_name"],
            dose=med["dose"],
            frequency=med["frequency"],
            duration=med["duration"],
            prescribed_by=user_id,
        )

    delete_referrals_by_examination(exam_id)
    if result["referral_data"]:
        add_referral(
            examination_id=exam_id,
            referred_to=result["referral_data"]["referred_to"],
            reason=result["referral_data"]["reason"],
            urgency=result["referral_data"]["urgency"],
            notes=result["referral_data"]["notes"],
            referred_by=user_id,
        )


# ============================================================
# PATIENT HISTORY DIALOG
# ============================================================

@st.dialog("Patient history", width="large")
def show_patient_history_dialog(patient):

    with st.container(key="sa_dialog"):

        show_rows([
            ("Patient", patient_name(patient)),
            ("Patient ID", patient_code(patient)),
            ("Date of birth", format_date(patient.get("date_of_birth"))),
            ("Sex", patient.get("sex")),
        ])

        tab1, tab2 = st.tabs(["Past Examinations", "External Records"])

        with tab1:
            exams = get_examinations_by_patient(patient.get("patient_id"))
            past = [e for e in exams if e.get("status") in ("Completed", "Cancelled")]

            if not past:
                empty_state("No completed examinations yet.")
            else:
                for exam in past:
                    status = exam.get("status")
                    st.markdown(
                        f"**{format_date(exam.get('examination_date'))}** — "
                        f"{exam.get('examination_type')}  "
                        f"{pill(status, 'green' if status == 'Completed' else 'red')}",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"**Diagnosis:** {exam.get('diagnosis') or '—'}")
                    st.caption(f"**Chief complaint:** {exam.get('chief_complaint') or '—'}")
                    if exam.get("disposition"):
                        st.caption(f"**Disposition:** {exam.get('disposition')}")
                    st.divider()

        with tab2:
            records = get_medical_records_by_patient(patient.get("patient_id"))

            if not records:
                empty_state("No external medical records found.")
            else:
                for record in records:
                    st.markdown(
                        f"**{record.get('record_type') or 'Record'}** — "
                        f"{format_date(record.get('record_date'))}"
                    )
                    st.caption(f"{record.get('facility_name') or '—'}")
                    if record.get("diagnosis"):
                        st.caption(f"Diagnosis: {record.get('diagnosis')}")
                    st.divider()

        if st.button("Close", key="close_history", width="stretch"):
            st.session_state.pop("history_patient", None)
            st.rerun()


# ============================================================
# VIEW PENDING EXAMS DIALOG
# ============================================================

@st.dialog("Pending examinations", width="medium")
def show_pending_exams_dialog(patient, exams):

    with st.container(key="sa_dialog"):

        show_rows([
            ("Patient", patient_name(patient)),
            ("Patient ID", patient_code(patient)),
        ])

        section_title(f"{len(exams)} pending examination(s)")

        for exam in sorted(exams, key=lambda x: x.get("created_at") or ""):

            wait = waiting_minutes(exam.get("created_at"))

            with st.container():
                st.markdown(
                    f"**{format_date(exam.get('examination_date'))}** — "
                    f"{exam.get('examination_type')}  "
                    f"{pill(format_waiting(wait), waiting_tone(wait))}",
                    unsafe_allow_html=True,
                )

                if st.button(
                    "Open this examination",
                    key=f"open_from_list_{exam['examination_id']}",
                    width="stretch",
                    type="primary",
                ):
                    st.session_state["selected_examination"] = exam
                    st.session_state["edit_patient"] = patient
                    st.session_state.pop("pending_exams_patient", None)
                    st.rerun()

                st.divider()

        if st.button("Close", key="close_pending_list", width="stretch"):
            st.session_state.pop("pending_exams_patient", None)
            st.rerun()


# ============================================================
# COMPLETE EXAMINATION DIALOG (Visit 1)
# ============================================================

@st.dialog("Complete examination", width="large")
def show_complete_exam_dialog(patient, examination):

    user_id = current_user().get("user_id")
    exam_id = examination["examination_id"]

    with st.container(key="sa_dialog"):

        show_rows([
            ("Patient", patient_name(patient)),
            ("Patient ID", patient_code(patient)),
            ("Date of birth", format_date(patient.get("date_of_birth"))),
            ("Sex", patient.get("sex")),
        ])

        errors = st.container()

        consents = get_examination_consents(exam_id)
        consent = consents[0] if consents else None
        vitals = get_examination_vitals(exam_id)

        section_title("Nurse's data")

        if consent and consent.get("given"):
            st.markdown(
                f"**Consent signed by:** {consent.get('signed_by_name') or '—'}"
            )

            sig_path = consent.get("signature_path")
            if sig_path:
                sig_url = get_consent_signature_url(sig_path)
                if sig_url:
                    st.image(sig_url, width=200, caption="Patient signature")
        else:
            st.warning("No consent on file for this examination.")

        st.markdown("**Vitals (editable):**")

        _v1, _v2, _v3 = st.columns(3)

        nurse_bp_sys = _v1.number_input(
            "BP systolic (mmHg)",
            min_value=0, max_value=300, step=1,
            value=int(_get_vitals_value(vitals, "bp_systolic") or 0),
            key="doc_bp_sys",
        )
        nurse_bp_dia = _v2.number_input(
            "BP diastolic (mmHg)",
            min_value=0, max_value=200, step=1,
            value=int(_get_vitals_value(vitals, "bp_diastolic") or 0),
            key="doc_bp_dia",
        )
        nurse_temp = _v3.number_input(
            "Temperature (°C)",
            min_value=0.0, max_value=50.0, step=0.1,
            value=float(_get_vitals_value(vitals, "temperature") or 0.0),
            key="doc_temp",
        )

        st.divider()
        section_title("Additional vitals (optional)")

        v4, v5, v6 = st.columns(3)
        pr = v4.number_input(
            "Pulse rate (bpm)", min_value=0, max_value=300, step=1,
            value=int(_get_vitals_value(vitals, "pulse_rate") or 0),
            key="q_pr",
        )
        rr = v5.number_input(
            "Respiratory rate (/min)", min_value=0, max_value=100, step=1,
            value=int(_get_vitals_value(vitals, "respiratory_rate") or 0),
            key="q_rr",
        )
        wt = v6.number_input(
            "Weight (kg)", min_value=0.0, max_value=500.0, step=0.1,
            value=float(_get_vitals_value(vitals, "weight_kg") or 0.0),
            key="q_wt",
        )

        v7, v8, v9 = st.columns(3)
        ht = v7.number_input(
            "Height (cm)", min_value=0.0, max_value=300.0, step=0.1,
            value=float(_get_vitals_value(vitals, "height_cm") or 0.0),
            key="q_ht",
        )
        spo2 = v8.number_input(
            "SpO2 (%)", min_value=0, max_value=100, step=1,
            value=int(_get_vitals_value(vitals, "spo2") or 0),
            key="q_spo2",
        )
        hr = v9.number_input(
            "Heart rate (bpm)", min_value=0, max_value=300, step=1,
            value=int(_get_vitals_value(vitals, "heart_rate") or 0),
            key="q_hr",
        )

        bmi_value = calculate_bmi(wt, ht)
        if bmi_value:
            label, tone = bmi_tone(bmi_value)
            st.markdown(
                f"**BMI:** {bmi_value} &nbsp; {pill(label, tone)}",
                unsafe_allow_html=True,
            )

        st.divider()
        section_title("Clinical notes")

        chief_complaint = st.text_area(
            "Chief complaint",
            value=examination.get("chief_complaint") or "",
            height=80, key="q_chief",
        )
        hpi = st.text_area(
            "History of present illness",
            value=examination.get("history_of_present_illness") or "",
            height=120, key="q_hpi",
        )
        physical_exam = st.text_area(
            "Physical examination",
            value=examination.get("physical_examination") or "",
            height=120, key="q_phys",
        )

        st.divider()
        section_title("Doctor orders")

        order = st.radio(
            "Select next step:",
            ["No Request", "Chest X-Ray"],
            key="q_order",
            horizontal=True,
        )

        if order == "No Request":

            diagnosis = st.text_area(
                "Diagnosis / assessment",
                value=examination.get("diagnosis") or "",
                height=100, key="q_diag",
            )

            plans = st.text_area(
                "Plans / orders",
                value=examination.get("plans_orders") or "",
                height=100, key="q_plans",
            )

            disposition_result = render_disposition_block(
                examination,
                key_prefix="v1",
            )

            st.divider()
            cancel_col, save_col = st.columns(2)

            cancel_clicked = cancel_col.button(
                "Cancel", key="q_cancel", width="stretch"
            )
            save_clicked = save_col.button(
                "Save & Complete",
                key="q_save",
                type="primary",
                width="stretch",
            )

        else:

            st.info("🩻 X-ray request form will appear here in the next step.")

            diagnosis = None
            plans = None
            disposition_result = None

            st.divider()
            cancel_col, save_col = st.columns(2)

            cancel_clicked = cancel_col.button(
                "Cancel", key="q_cancel", width="stretch"
            )
            save_clicked = save_col.button(
                "Request X-Ray",
                key="q_save",
                type="primary",
                width="stretch",
                icon=":material/radiology:",
            )

    if cancel_clicked:
        st.session_state.pop("selected_examination", None)
        st.session_state.pop("edit_patient", None)
        st.rerun()

    if not save_clicked:
        return

    if not chief_complaint.strip():
        errors.error("Chief complaint is required.")
        return

    if order == "No Request" and not diagnosis.strip():
        errors.error("Diagnosis is required.")
        return

    try:
        original = vitals[0] if vitals else {}

        if (
            (nurse_bp_sys or None) != original.get("bp_systolic")
            or (nurse_bp_dia or None) != original.get("bp_diastolic")
            or (nurse_temp or None) != original.get("temperature")
        ):
            add_examination_vitals(
                examination_id=exam_id,
                recorded_by=user_id,
                recorded_by_role="doctor",
                bp_systolic=nurse_bp_sys or None,
                bp_diastolic=nurse_bp_dia or None,
                temperature=nurse_temp or None,
            )

        if any([pr, rr, wt, ht, spo2, hr]):
            add_examination_vitals(
                examination_id=exam_id,
                recorded_by=user_id,
                recorded_by_role="doctor",
                pulse_rate=pr or None,
                respiratory_rate=rr or None,
                weight_kg=wt or None,
                height_cm=ht or None,
                spo2=spo2 or None,
                heart_rate=hr or None,
                bmi=bmi_value,
            )

        if order == "No Request":
            fu_date = disposition_result["follow_up_date"]
            fu_notes = disposition_result["follow_up_notes"]

            update_examination(
                examination_id=exam_id,
                status="Completed",
                reviewed_by=user_id,
                chief_complaint=chief_complaint.strip() or None,
                history_of_present_illness=hpi.strip() or None,
                physical_examination=physical_exam.strip() or None,
                diagnosis=diagnosis.strip() or None,
                plans_orders=plans.strip() or None,
                disposition=disposition_result["disposition"],
                disposition_notes=(
                    disposition_result["disp_notes"].strip() or None
                ),
                follow_up_date=(
                    fu_date.isoformat() if fu_date else None
                ),
                follow_up_notes=(
                    fu_notes.strip() if fu_notes else None
                ),
            )

            save_disposition_extras(exam_id, user_id, disposition_result)

        else:
            update_examination(
                examination_id=exam_id,
                status="Awaiting X-Ray",
                reviewed_by=user_id,
                chief_complaint=chief_complaint.strip() or None,
                history_of_present_illness=hpi.strip() or None,
                physical_examination=physical_exam.strip() or None,
            )

            create_xray_request(
                examination_id=exam_id,
                hospital_id=current_hospital_id(),
                requested_by=user_id,
                body_part="Chest",
                priority="Routine",
                clinical_indication=None,
            )

        st.session_state.pop("selected_examination", None)
        st.session_state.pop("edit_patient", None)
        remember("Examination saved.")
        st.rerun()

    except Exception as error:
        errors.error(f"Failed to complete examination: {error}")


# ============================================================
# X-RAY REVIEW DIALOG (Visit 2)
# ============================================================

@st.dialog("Review X-Ray & Complete", width="large")
def show_xray_review_dialog(patient, examination):

    from backend.fetches import (
        get_xray_request_by_examination,
        get_xray_images_by_request,
        get_xray_image_url,
        get_xray_ai_result,
    )
    from backend.crud import save_xray_review

    user_id = current_user().get("user_id")
    exam_id = examination["examination_id"]

    with st.container(key="sa_dialog"):

        show_rows([
            ("Patient", patient_name(patient)),
            ("Patient ID", patient_code(patient)),
            ("Date of birth", format_date(patient.get("date_of_birth"))),
            ("Sex", patient.get("sex")),
        ])

        request = get_xray_request_by_examination(exam_id)

        if not request:
            st.error("No X-ray request found for this examination.")
            if st.button("Close", key="close_no_xray_req", width="stretch"):
                st.session_state.pop("selected_examination", None)
                st.session_state.pop("edit_patient", None)
                st.rerun()
            return

        images = get_xray_images_by_request(request["request_id"])

        section_title("X-Ray Image")

        if not images:
            st.warning("No X-ray image uploaded yet.")
        else:
            latest_image = images[0]
            image_url = get_xray_image_url(latest_image["image_path"])

            if image_url:
                st.image(image_url, caption="Chest X-Ray", width=400)
            else:
                st.warning("Could not load X-ray image.")

            ai = get_xray_ai_result(latest_image["image_id"])

            if ai:
                label = (ai.get("ai_findings") or "").lower()
                confidence = ai.get("ai_confidence") or 0

                tone = "red" if label == "positive" else "green"

                st.markdown(
                    f"**AI Result:** "
                    f"{pill(label.upper(), tone)} "
                    f"&nbsp; confidence: {confidence * 100:.1f}%",
                    unsafe_allow_html=True,
                )
                st.caption(
                    "⚠️ AI result is advisory only. "
                    "Use clinical judgment for final diagnosis."
                )
            else:
                st.caption("No AI result found for this image.")

        st.divider()
        section_title("Clinical notes (from Visit 1)")

        st.markdown(f"**Chief complaint:** {examination.get('chief_complaint') or '—'}")
        st.markdown(f"**HPI:** {examination.get('history_of_present_illness') or '—'}")
        st.markdown(f"**Physical exam:** {examination.get('physical_examination') or '—'}")

        st.divider()
        section_title("X-Ray Review")

        findings = st.text_area(
            "Findings (what you see on the film)",
            value="",
            height=100,
            key="xray_findings",
        )

        impression = st.text_area(
            "Impression (what you think it means)",
            value="",
            height=100,
            key="xray_impression",
        )

        st.divider()
        section_title("Final Assessment")

        diagnosis = st.text_area(
            "Diagnosis / assessment",
            value=examination.get("diagnosis") or "",
            height=100,
            key="xray_diagnosis",
        )

        plans = st.text_area(
            "Plans / orders",
            value=examination.get("plans_orders") or "",
            height=100,
            key="xray_plans",
        )

        disposition_result = render_disposition_block(
            examination,
            key_prefix="v2",
        )

        st.divider()
        cancel_col, save_col = st.columns(2)

        cancel_clicked = cancel_col.button(
            "Cancel", key="xray_review_cancel", width="stretch"
        )
        save_clicked = save_col.button(
            "Save & Complete",
            key="xray_review_save",
            type="primary",
            width="stretch",
        )

    if cancel_clicked:
        st.session_state.pop("selected_examination", None)
        st.session_state.pop("edit_patient", None)
        st.rerun()

    if not save_clicked:
        return

    if not diagnosis.strip():
        st.error("Diagnosis is required.")
        return

    try:
        save_xray_review(
            request_id=request["request_id"],
            reviewed_by=user_id,
            findings=findings.strip() or None,
            impression=impression.strip() or None,
        )

        fu_date = disposition_result["follow_up_date"]
        fu_notes = disposition_result["follow_up_notes"]

        update_examination(
            examination_id=exam_id,
            status="Completed",
            reviewed_by=user_id,
            diagnosis=diagnosis.strip() or None,
            plans_orders=plans.strip() or None,
            disposition=disposition_result["disposition"],
            disposition_notes=(
                disposition_result["disp_notes"].strip() or None
            ),
            follow_up_date=(
                fu_date.isoformat() if fu_date else None
            ),
            follow_up_notes=(
                fu_notes.strip() if fu_notes else None
            ),
        )

        save_disposition_extras(exam_id, user_id, disposition_result)

        st.session_state.pop("selected_examination", None)
        st.session_state.pop("edit_patient", None)
        remember("X-Ray reviewed. Examination completed.")
        st.rerun()

    except Exception as error:
        st.error(f"Failed to save X-ray review: {error}")


# ============================================================
# MAIN QUEUE PAGE
# ============================================================

def render_metrics(grouped, key_prefix="metrics"):

    total_patients = len(grouped)
    total_exams = sum(len(g["exams"]) for g in grouped)

    if grouped:
        longest = max(g["oldest_waiting"] for g in grouped)
        average = sum(g["oldest_waiting"] for g in grouped) // total_patients
    else:
        longest = 0
        average = 0

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        metric_card("Patients waiting", total_patients, "groups", tone="blue")
    with m2:
        metric_card("Pending exams", total_exams, "assignment", tone="amber")
    with m3:
        metric_card("Longest wait", format_waiting(longest), "schedule", tone="red")
    with m4:
        metric_card("Average wait", format_waiting(average), "timer", tone="green")


def render_queue_table(grouped, key_prefix="queue"):

    if not grouped:
        empty_state("No pending examinations at the moment.")
        return

    with st.container(key=f"sa_table_{key_prefix}"):

        table_header(QUEUE_HEADERS, QUEUE_WIDTHS, key_prefix)

        for item in grouped:

            patient = item["patient"]
            exams = item["exams"]
            waiting = item["oldest_waiting"]
            patient_id = patient.get("patient_id")

            with table_row(f"{key_prefix}_row_{patient_id}", QUEUE_WIDTHS) as cols:

                name_cell(cols[0], patient_name(patient), sub=patient_code(patient))
                text_cell(cols[1], str(len(exams)))
                pill_cell(cols[2], format_waiting(waiting), waiting_tone(waiting))

                if cols[3].button(
                    "History",
                    key=f"{key_prefix}_history_{patient_id}",
                    icon=":material/folder_open:",
                    width="stretch",
                ):
                    st.session_state.pop("selected_examination", None)
                    st.session_state.pop("pending_exams_patient", None)
                    st.session_state["history_patient"] = patient
                    st.rerun()

                if len(exams) == 1:
                    if cols[4].button(
                        "Open",
                        key=f"{key_prefix}_open_{patient_id}",
                        icon=":material/clinical_notes:",
                        type="primary",
                        width="stretch",
                    ):
                        st.session_state.pop("history_patient", None)
                        st.session_state.pop("pending_exams_patient", None)
                        st.session_state["selected_examination"] = exams[0]
                        st.session_state["edit_patient"] = patient
                        st.rerun()
                else:
                    if cols[4].button(
                        "View Exams",
                        key=f"{key_prefix}_view_{patient_id}",
                        icon=":material/list:",
                        type="primary",
                        width="stretch",
                    ):
                        st.session_state.pop("history_patient", None)
                        st.session_state.pop("selected_examination", None)
                        st.session_state["pending_exams_patient"] = {
                            "patient": patient,
                            "exams": exams,
                        }
                        st.rerun()

                cols[5].empty()


# ============================================================
# PAGE
# ============================================================

def show():

    load_css("manage_examinations.css")
    show_flash_message()

    role_id = current_role_id()
    hospital_id = current_hospital_id()

    if role_id == ROLE_SUPERADMIN:
        filter_hospital = None
    elif role_id in DOCTOR_ROLES or role_id == ROLE_HOSPITAL_ADMIN:
        filter_hospital = hospital_id
    else:
        st.error("You don't have access to the patient queue.")
        return

    with st.container(key="sa_page"):

        page_header(
            "Patient Queue",
            "Examinations awaiting your review.",
        )

        if st.button(
            "Refresh",
            icon=":material/refresh:",
            key="queue_refresh",
            width="stretch",
        ):
            st.rerun()

        try:
            pending = get_pending_examinations(hospital_id=filter_hospital)
        except Exception as error:
            st.error(f"Failed to load pending queue: {error}")
            pending = []

        try:
            xray_ready = get_xray_ready_examinations(hospital_id=filter_hospital)
        except Exception as error:
            st.error(f"Failed to load X-ray-ready queue: {error}")
            xray_ready = []

        tab1, tab2 = st.tabs([
            f"Pending ({len(pending)})",
            f"X-Ray Ready ({len(xray_ready)})",
        ])

        with tab1:
            grouped = group_pending_by_patient(pending)
            render_metrics(grouped)
            st.divider()
            render_queue_table(grouped, key_prefix="pending")

        with tab2:
            grouped_xray = group_pending_by_patient(xray_ready)
            render_metrics(grouped_xray)
            st.divider()
            render_queue_table(grouped_xray, key_prefix="xray_ready")

    if st.session_state.get("selected_examination"):

        exam = st.session_state["selected_examination"]

        if exam.get("status") == "X-Ray Ready":
            show_xray_review_dialog(
                st.session_state.get("edit_patient"),
                exam,
            )
        else:
            show_complete_exam_dialog(
                st.session_state.get("edit_patient"),
                exam,
            )

    elif st.session_state.get("pending_exams_patient"):
        data = st.session_state["pending_exams_patient"]
        show_pending_exams_dialog(data["patient"], data["exams"])

    elif st.session_state.get("history_patient"):
        show_patient_history_dialog(st.session_state["history_patient"])