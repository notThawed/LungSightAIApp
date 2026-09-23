import streamlit as st

from datetime import datetime, timezone

from backend.fetches import (
    get_pending_xray_examinations,
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
    show_flash_message,
)


# ============================================================
# CONFIG
# ============================================================

ROLE_SUPERADMIN = 1
ROLE_RADIOLOGIST = 3
ROLE_RADTECH = 4
ROLE_HOSPITAL_ADMIN = 6
ROLE_STAFF = 7

RADTECH_ROLES = [ROLE_RADTECH]

QUEUE_WIDTHS = [2.5, 1.2, 1.2, 1.2, 1.5]
QUEUE_HEADERS = ["Patient", "Body part", "Priority", "Waiting", ""]


# ============================================================
# HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}


def current_role_id():
    return (st.session_state.get("user") or {}).get("role_id")


def current_hospital_id():
    return (st.session_state.get("user") or {}).get("hospital_id")


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
        return int((now - created).total_seconds() // 60)
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
# DIALOG — Perform X-Ray (upload + quality + AI)
# ============================================================

@st.dialog("Perform X-Ray", width="large")
def show_perform_xray_dialog(patient, examination):

    from backend.crud import (
        upload_xray_image,
        update_xray_request_status,
        update_xray_image_quality,
        update_examination,
        save_ai_result,
    )
    from backend.fetches import get_xray_request_by_examination
    from backend.ai.pneumonia_model import predict

    user_id = current_user().get("user_id")
    exam_id = examination["examination_id"]

    with st.container(key="sa_dialog"):

        show_rows([
            ("Patient", patient_name(patient)),
            ("Patient ID", patient_code(patient)),
            ("Date of birth", format_date(patient.get("date_of_birth"))),
            ("Sex", patient.get("sex")),
        ])

        section_title("X-Ray Request")

        request = get_xray_request_by_examination(exam_id)

        if not request:
            st.error("No X-ray request found for this examination.")
            if st.button("Close", key="close_no_request", width="stretch"):
                st.session_state.pop("xray_selected_examination", None)
                st.session_state.pop("xray_edit_patient", None)
                st.rerun()
            return

        st.markdown(f"**Chief complaint:** {examination.get('chief_complaint') or '—'}")
        st.markdown(f"**Body part:** {request.get('body_part') or 'Chest'}")
        st.markdown(f"**Priority:** {request.get('priority') or 'Routine'}")
        st.markdown(f"**Indication:** {request.get('clinical_indication') or '—'}")

        st.divider()
        section_title("Upload X-Ray")

        uploaded_file = st.file_uploader(
            "Select X-ray image",
            type=["png", "jpg", "jpeg"],
            key=f"xray_upload_{exam_id}",
        )

        if uploaded_file:
            st.image(uploaded_file, caption="Preview", width=300)

        quality_status = None

        if uploaded_file:
            st.divider()
            section_title("Quality Check")

            quality_status = st.radio(
                "Is the image clear and usable?",
                ["Passed", "Failed"],
                key=f"quality_{exam_id}",
                horizontal=True,
            )

            if quality_status == "Failed":
                st.warning(
                    "❌ Image failed quality check. "
                    "Please retake the X-ray before saving."
                )

        st.divider()
        cancel_col, save_col = st.columns(2)

        cancel_clicked = cancel_col.button(
            "Cancel", key="cancel_xray_upload", width="stretch"
        )

        save_disabled = (
            uploaded_file is not None and quality_status == "Failed"
        )

        save_clicked = save_col.button(
            "Save & Mark Ready",
            key="save_xray_upload",
            type="primary",
            width="stretch",
            icon=":material/radiology:",
            disabled=save_disabled,
        )

    # ---------- Cancel ----------
    if cancel_clicked:
        st.session_state.pop("xray_selected_examination", None)
        st.session_state.pop("xray_edit_patient", None)
        st.rerun()

    if not save_clicked:
        return

    # ---------- Validation ----------
    if not uploaded_file:
        st.error("Please upload an X-ray image first.")
        return

    if quality_status == "Failed":
        st.error("Image failed quality check. Please retake.")
        return

    if quality_status is None:
        st.error("Please mark the quality check.")
        return

    # ---------- Save ----------
    try:
        # 1. Upload image
        result = upload_xray_image(
            request_id=request["request_id"],
            file_bytes=uploaded_file.getvalue(),
            filename=uploaded_file.name,
            uploaded_by=user_id,
        )

        if not result:
            st.error("Failed to upload X-ray image.")
            return

        image_id = result["image_id"]

        # 2. Mark quality
        update_xray_image_quality(
            image_id=image_id,
            quality_status="Passed",
            quality_checked_by=user_id,
        )

        # 3. Run AI
        try:
            prediction = predict(uploaded_file.getvalue())
        except Exception as ai_error:
            st.error(f"AI prediction failed: {ai_error}")
            return

        # 4. Save AI result silently
        save_ai_result(
            image_id=image_id,
            ai_findings=prediction["label"],
            ai_confidence=prediction["confidence"],
            ai_model_version="pneumonia_resnet50_v1",
        )

        # 5. Mark xray_request as Completed
        update_xray_request_status(
            request["request_id"],
            status="Completed",
        )

        # 6. Update examination status
        update_examination(
            examination_id=exam_id,
            status="X-Ray Ready",
        )

        st.session_state.pop("xray_selected_examination", None)
        st.session_state.pop("xray_edit_patient", None)
        st.success("X-Ray saved. Status: X-Ray Ready.")
        st.rerun()

    except Exception as error:
        st.error(f"Failed to save X-ray: {error}")


# ============================================================
# TABLE
# ============================================================

def render_xray_queue(grouped):

    if not grouped:
        empty_state("No X-ray requests at the moment.")
        return

    with st.container(key="sa_table_xray_queue"):

        table_header(QUEUE_HEADERS, QUEUE_WIDTHS, "xray_queue")

        for item in grouped:

            patient = item["patient"]
            exam = item["exam"]
            waiting = item["waiting"]
            patient_id = patient.get("patient_id")
            exam_id = exam["examination_id"]

            with table_row(f"xray_{exam_id}", QUEUE_WIDTHS) as cols:

                name_cell(cols[0], patient_name(patient), sub=patient_code(patient))
                text_cell(cols[1], "Chest")
                pill_cell(cols[2], "Routine", "blue")
                pill_cell(cols[3], format_waiting(waiting), waiting_tone(waiting))

                if cols[4].button(
                    "Perform X-Ray",
                    key=f"perform_xray_{exam_id}",
                    icon=":material/radiology:",
                    type="primary",
                    width="stretch",
                ):
                    st.session_state["xray_selected_examination"] = exam
                    st.session_state["xray_edit_patient"] = patient
                    st.rerun()


# ============================================================
# GROUPING
# ============================================================

def group_xray_by_patient(pending):

    grouped = []

    for exam in pending:
        patient = exam.get("patients") or {}
        if not patient.get("patient_id"):
            continue
        grouped.append({
            "patient": patient,
            "exam": exam,
            "waiting": waiting_minutes(exam.get("created_at")),
        })

    grouped.sort(key=lambda x: x["waiting"], reverse=True)
    return grouped


# ============================================================
# METRICS
# ============================================================

def render_metrics(grouped):

    total = len(grouped)
    if grouped:
        longest = max(g["waiting"] for g in grouped)
        average = sum(g["waiting"] for g in grouped) // total
    else:
        longest = 0
        average = 0

    m1, m2, m3 = st.columns(3)

    with m1:
        metric_card("X-Rays waiting", total, "radiology", tone="blue")
    with m2:
        metric_card("Longest wait", format_waiting(longest), "schedule", tone="red")
    with m3:
        metric_card("Average wait", format_waiting(average), "timer", tone="green")


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
    elif role_id in RADTECH_ROLES:
        filter_hospital = hospital_id
    else:
        st.error("You don't have access to the X-ray queue.")
        return

    with st.container(key="sa_page"):

        page_header(
            "X-Ray Queue",
            "Pending X-ray requests awaiting imaging.",
        )

        if st.button(
            "Refresh",
            icon=":material/refresh:",
            key="xray_queue_refresh",
            width="stretch",
        ):
            st.rerun()

        try:
            pending = get_pending_xray_examinations(hospital_id=filter_hospital)
        except Exception as error:
            st.error(f"Failed to load X-ray queue: {error}")
            pending = []

        grouped = group_xray_by_patient(pending)

        render_metrics(grouped)
        st.divider()
        render_xray_queue(grouped)

    # Dialog router
    if st.session_state.get("xray_selected_examination"):
        show_perform_xray_dialog(
            st.session_state.get("xray_edit_patient"),
            st.session_state["xray_selected_examination"],
        )