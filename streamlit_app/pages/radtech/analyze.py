import streamlit as st
import time

from datetime import datetime, timezone

from backend.fetches import (
    get_xray_request_by_examination,
    get_xray_images_by_request,
    get_xray_image_url,
    get_xray_ai_result,
    get_all_patients,
)

from backend.crud import (
    upload_xray_image,
    update_xray_request_status,
    update_xray_image_quality,
    update_examination,
    save_ai_result,
)

from backend.backend_utils.subscription_usage import can_analyze_xray

from backend.ai.pneumonia_model import predict
from backend.ai.pneumonia_type_model import predict_type

from streamlit_app.components.ui import (
    page_header,
    section_title,
    show_rows,
    full_name,
    format_date,
    pill,
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

RADTECH_ROLES = [ROLE_RADTECH]

AI_MODEL_VERSION = "pneumonia_resnet50_v1"
CLASSIFICATION_MODEL_VERSION = "pneumonia_densenet121_v1"


# ============================================================
# HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}


def current_role_id():
    return current_user().get("role_id")


def current_hospital_id():
    return current_user().get("hospital_id")


def current_user_id():
    return current_user().get("user_id")


def patient_name(patient):
    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )


def patient_code(patient):
    return patient.get("patient_code") or patient.get("patient_id")


def clear_active_examination():
    st.session_state.pop("radtech_active_examination", None)
    st.session_state.pop("radtech_active_patient", None)
    st.session_state.pop("radtech_analysis_result", None)


def go_back_to_queue():
    clear_active_examination()
    st.session_state.current_page = "X-ray Queus"
    st.rerun()


# ============================================================
# SUBSCRIPTION GUARD
# ============================================================

def check_subscription():
    hospital_id = current_hospital_id()

    check = can_analyze_xray(hospital_id)

    if not check.get("allowed"):
        st.error(
            check.get(
                "message",
                "Monthly X-Ray limit reached.",
            )
        )
        return False

    return True


# ============================================================
# CONTEXT CARD (queue mode only)
# ============================================================

def render_context_card(patient, examination, request):

    st.markdown(
        "<div class='rx-context'>"
        "<div class='rx-context-left'>"
        f"<p class='rx-context-name'>{patient_name(patient)}</p>"
        f"<p class='rx-context-code'>{patient_code(patient)}</p>"
        "</div>"
        "<div class='rx-context-right'>"
        f"<p class='rx-context-meta'>{request.get('body_part') or 'Chest'}"
        f" · {request.get('priority') or 'Routine'}</p>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    show_rows([
        ("Chief complaint", examination.get("chief_complaint") or "—"),
        ("Clinical indication", request.get("clinical_indication") or "—"),
    ])


# ============================================================
# EMPTY RESULTS STATE (right panel)
# ============================================================

def render_empty_results():

    st.markdown(
        "<div class='rx-empty'>"
        "<div class='rx-empty-icon'>crop_free</div>"
        "<p class='rx-empty-title'>Results Will Appear Here</p>"
        "<p class='rx-empty-text'>"
        "Upload an X-ray image and click \"Analyze\" to see "
        "the AI detection results with heatmap visualization."
        "</p>"
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# PROGRESS HTML BUILDER
# Pure HTML string — no keyed containers, no stacking issues
# ============================================================

def _progress_html(current_step):

    steps = [
        "Image preprocessed",
        "Running AI detection model...",
        "Generating heatmap",
        "Preparing report",
    ]

    rows = []

    for index, label in enumerate(steps):

        if index < current_step:
            cls = "rx-step-done"
            icon = "✓"
        elif index == current_step:
            cls = "rx-step-active"
            icon = "⟳"
        else:
            cls = "rx-step-pending"
            icon = "·"

        rows.append(
            f"<div class='rx-step {cls}'>"
            f"<span class='rx-step-icon'>{icon}</span>"
            f"<span class='rx-step-label'>{label}</span>"
            "</div>"
        )

    return (
        "<div class='rx-progress-card'>"
        "<p class='rx-progress-title'>Analysis in Progress</p>"
        + "".join(rows)
        + "</div>"
    )


# ============================================================
# RESULT PANEL
# ============================================================

def render_result_panel(result, image_bytes):

    st.markdown(
        "<p class='rx-panel-title'>Analysis Result - Heatmap</p>",
        unsafe_allow_html=True,
    )

    with st.container(key="rx_preview_result"):
        st.image(image_bytes, width="stretch")

    st.markdown(
        "<p class='rx-result-caption'>"
        "Red/yellow areas indicate regions of concern detected by AI"
        "</p>",
        unsafe_allow_html=True,
    )

    # ----------------------------------------------------
    # DIAGNOSIS SUMMARY
    # ----------------------------------------------------

    st.markdown(
        "<p class='rx-summary-title'>Diagnosis Summary</p>",
        unsafe_allow_html=True,
    )

    label = result.get("label", "unknown")
    confidence = result.get("confidence", 0.0)

    is_positive = str(label).lower() == "positive"

    risk_label = "High Risk" if is_positive else "Low Risk"
    risk_tone = "red" if is_positive else "green"
    confidence_pct = f"{confidence * 100:.1f}%"

    # Risk row
    st.markdown(
        "<div class='rx-summary-row'>"
        "<span>Risk Level</span>"
        f"<div>{pill(risk_label, risk_tone)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Confidence row
    st.markdown(
        "<div class='rx-summary-row'>"
        "<span>Confidence Score</span>"
        f"<b>{confidence_pct}</b>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Pneumonia type classification
    pneumonia_type = result.get("pneumonia_type")
    classification_confidence = result.get(
        "classification_confidence"
    )

    if pneumonia_type:
        type_label = {
            "bacterial_pneumonia": "Bacterial Pneumonia",
            "viral_pneumonia": "Viral Pneumonia",
        }.get(pneumonia_type, pneumonia_type.replace("_", " ").title())

        st.markdown(
            "<div class='rx-summary-row'>"
            "<span>Pneumonia Classification</span>"
            f"<b>{type_label}</b>"
            "</div>",
            unsafe_allow_html=True,
        )

        if classification_confidence is not None:
            type_confidence_pct = (
                f"{classification_confidence * 100:.1f}%"
            )

            st.markdown(
                "<div class='rx-summary-row'>"
                "<span>Classification Confidence</span>"
                f"<b>{type_confidence_pct}</b>"
                "</div>",
                unsafe_allow_html=True,
            )
    elif str(result.get("label", "")).lower() == "negative":
        st.markdown(
            "<div class='rx-summary-row'>"
            "<span>Pneumonia Classification</span>"
            "<b>Not applicable — negative screening result</b>"
            "</div>",
            unsafe_allow_html=True,
        )

    # Findings box
    if is_positive:

        finding_text = (
            "The AI model has detected patterns consistent "
            "with <b>pneumonia</b>. Recommend clinical "
            "correlation and follow-up with the treating "
            "physician."
        )

        st.markdown(
            "<div class='rx-findings rx-findings-positive'>"
            "<p class='rx-findings-title'>AI Findings</p>"
            f"<p class='rx-findings-text'>{finding_text}</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    else:

        finding_text = (
            "The AI model has <b>not</b> detected patterns "
            "consistent with pneumonia. Continue standard "
            "clinical evaluation."
        )

        st.markdown(
            "<div class='rx-findings rx-findings-negative'>"
            "<p class='rx-findings-title'>AI Findings</p>"
            f"<p class='rx-findings-text'>{finding_text}</p>"
            "</div>",
            unsafe_allow_html=True,
        )


# ============================================================
# ANALYSIS RUNNER
# ============================================================


def run_analysis(uploaded_file, examination, patient, request):

    progress_placeholder = st.empty()
    image_bytes = uploaded_file.getvalue()

    # Step 0 — Image preprocessing status
    progress_placeholder.markdown(
        _progress_html(0),
        unsafe_allow_html=True,
    )

    time.sleep(0.4)

    # Step 1 — ResNet-50 pneumonia detection
    progress_placeholder.markdown(
        _progress_html(1),
        unsafe_allow_html=True,
    )

    try:
        result = predict(image_bytes)

        # Normalize and validate the first model's label.
        label = str(result.get("label", "")).strip().lower()

        if label not in ("positive", "negative"):
            raise ValueError(
                f"Unexpected ResNet-50 prediction label: {label!r}"
            )

        result["label"] = label
        result["pneumonia_type"] = None
        result["classification_confidence"] = None
        result["classification_model_version"] = None

        # Step 2 — Run DenseNet-121 only for positive cases.
        if label == "positive":
            progress_placeholder.markdown(
                "<div class='rx-progress-card'>"
                "<p class='rx-progress-title'>Analysis in Progress</p>"
                "<div class='rx-step rx-step-done'>"
                "<span class='rx-step-icon'>✓</span>"
                "<span class='rx-step-label'>ResNet-50 detection complete</span>"
                "</div>"
                "<div class='rx-step rx-step-active'>"
                "<span class='rx-step-icon'>⟳</span>"
                "<span class='rx-step-label'>Running DenseNet-121 pneumonia classification...</span>"
                "</div>"
                "</div>",
                unsafe_allow_html=True,
            )

            type_result = predict_type(image_bytes)
            print("DEBUG - Full DenseNet result:", type_result)

            type_label = str(
                type_result.get("label", "")
            ).strip().lower()

            if type_label not in (
                "bacterial_pneumonia",
                "viral_pneumonia",
            ):
                raise ValueError(
                    f"Unexpected DenseNet-121 prediction label: {type_label!r}"
                )

            result["pneumonia_type"] = type_label

            result["classification_confidence"] = float(
                type_result["confidence"]
            )
            result["classification_model_version"] = (
                CLASSIFICATION_MODEL_VERSION
            )

            print("DEBUG - Pneumonia type:", result["pneumonia_type"])
            print(
                "DEBUG - Classification confidence:",
                result["classification_confidence"],
            )

    except Exception as error:
        progress_placeholder.empty()
        st.error(f"AI prediction failed: {error}")
        return

    # Step 3 — Prepare report
    progress_placeholder.markdown(
        _progress_html(3),
        unsafe_allow_html=True,
    )

    time.sleep(0.4)

    # Store both model outputs for the save step.
    progress_placeholder.empty()
    st.session_state["radtech_analysis_result"] = result

    st.rerun()



# ============================================================
# SAVE WORKFLOW
# ============================================================


def save_analysis(uploaded_file, result, examination, request, patient):

    user_id = current_user_id()

    # 1. Upload the X-ray image.
    upload_result = upload_xray_image(
        request_id=request["request_id"],
        file_bytes=uploaded_file.getvalue(),
        filename=uploaded_file.name,
        uploaded_by=user_id,
    )

    if not upload_result:
        st.error("Failed to upload X-ray image.")
        return False

    image_id = upload_result["image_id"]

    # 2. Mark the image quality check.
    quality_updated = update_xray_image_quality(
        image_id=image_id,
        quality_status="Passed",
        quality_checked_by=user_id,
    )

    if quality_updated is False:
        st.error("Failed to save the X-ray quality-check status.")
        return False

    # 3. Save both AI outputs in one database row.
    saved_result = save_ai_result(
        image_id=image_id,
        ai_findings=result["label"],
        ai_confidence=result["confidence"],
        ai_model_version=AI_MODEL_VERSION,
        pneumonia_type=result.get("pneumonia_type"),
        classification_confidence=result.get(
            "classification_confidence"
        ),
        classification_model_version=result.get(
            "classification_model_version"
        ),
    )

    if not saved_result:
        st.error(
            "The X-ray image was uploaded, but saving the AI results "
            "failed. The examination has not been marked as completed."
        )
        return False

    # 4. Mark the X-ray request completed.
    update_xray_request_status(
        request["request_id"],
        status="Completed",
    )

    # 5. Move the examination to X-Ray Ready.
    update_examination(
        examination_id=examination["examination_id"],
        status="X-Ray Ready",
    )

    return True



# ============================================================
# MAIN PAGE
# ============================================================

def show():

    load_css("analyze.css")
    show_flash_message()

    role_id = current_role_id()

    if role_id not in RADTECH_ROLES and role_id != ROLE_SUPERADMIN:
        st.error("You don't have access to this page.")
        return

    # ========================================================
    # MODE DETECTION
    # ========================================================

    active_exam = st.session_state.get("radtech_active_examination")
    active_patient = st.session_state.get("radtech_active_patient")

    # ========================================================
    # GUARD — no patient selected
    # ========================================================

    if not (active_exam and active_patient):

        page_header(
            "Analyze X-Ray",
            "Upload a chest X-ray image for AI-powered pneumonia detection.",
        )

        st.markdown(
            "<div class='rx-guard'>"
            "<div class='rx-guard-icon'>person_search</div>"
            "<p class='rx-guard-title'>No Patient Selected</p>"
            "<p class='rx-guard-text'>"
            "Pick a patient from the X-Ray Queue to analyze their X-Ray."
            "</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        if st.button(
            "Go Back to Queue",
            key="rx_guard_back",
            icon=":material/arrow_back:",
            type="primary",
            width="stretch",
        ):

            st.session_state.pop("radtech_analysis_result", None)
            st.session_state.pop("rx_upload", None)

            st.session_state.current_page = "X-ray Queus"

            st.rerun()

        return

    # ========================================================
    # QUEUE MODE — patient is selected
    # ========================================================

    queue_mode = True

    # ========================================================
    # PAGE HEADER
    # ========================================================

    page_header(
        "Analyze X-Ray",
        "Upload a chest X-ray image for AI-powered pneumonia detection.",
    )

    # ========================================================
    # BACK TO QUEUE
    # ========================================================

    if st.button(
        "← Back to X-Ray Queue",
        key="rx_back_to_queue",
    ):
        go_back_to_queue()

    # ========================================================
    # LOAD REQUEST
    # ========================================================

    request = get_xray_request_by_examination(
        active_exam["examination_id"]
    )

    if not request:
        st.error(
            "No X-ray request found for this examination. "
            "It may have already been processed."
        )
        return

    render_context_card(active_patient, active_exam, request)

    # ========================================================
    # SUBSCRIPTION GUARD
    # ========================================================

    if not check_subscription():
        return

    # ========================================================
    # TWO-COLUMN WORKSPACE
    # ========================================================

    left, right = st.columns([1, 1], gap="large")

    # ========================================================
    # LEFT — UPLOAD
    # ========================================================

    with left:

        with st.container(key="rx_panel_input"):

            st.markdown(
                "<p class='rx-panel-title'>Upload X-Ray Image</p>",
                unsafe_allow_html=True,
            )

            # ------------------------------------------------
            # REAL FILE UPLOADER
            # The dropzone itself becomes our custom UI via CSS.
            # Clicking it opens the file picker as normal.
            # ------------------------------------------------

            uploaded_file = st.file_uploader(
                "Select X-ray image",
                type=["png", "jpg", "jpeg"],
                key="rx_upload",
                label_visibility="collapsed",
            )

            # ------------------------------------------------
            # SUBTITLE (only when no file is uploaded yet)
            # ------------------------------------------------

            if uploaded_file is None:

                st.markdown(
                    "<p class='rx-dropzone-sub'>"
                    "Supports JPEG, PNG, DICOM formats"
                    "</p>",
                    unsafe_allow_html=True,
                )

            # ------------------------------------------------
            # PREVIEW
            # ------------------------------------------------

            else:

                with st.container(key="rx_preview"):
                    st.image(uploaded_file, width="stretch")

    # ========================================================
    # RIGHT — RESULTS
    # ========================================================

    with right:

        with st.container(key="rx_panel_output"):

            result = st.session_state.get("radtech_analysis_result")

            if result and uploaded_file:

                render_result_panel(result, uploaded_file.getvalue())

            else:

                st.markdown(
                    "<p class='rx-panel-title'>&nbsp;</p>",
                    unsafe_allow_html=True,
                )

                render_empty_results()

    # ========================================================
    # ACTION BUTTONS
    # ========================================================

    if uploaded_file is None:
        return

    result = st.session_state.get("radtech_analysis_result")

    # --------------------------------------------------------
    # IDLE — Analyze / Reset
    # --------------------------------------------------------

    if result is None:

        with left:

            col1, col2 = st.columns([4, 1])

            with col1:

                analyze_clicked = st.button(
                    "Analyze Image",
                    key="rx_run_analysis",
                    icon=":material/autorenew:",
                    type="primary",
                    width="stretch",
                )

            with col2:

                reset_clicked = st.button(
                    "Reset",
                    key="rx_reset",
                    width="stretch",
                )

        if reset_clicked:

            st.session_state.pop("rx_upload", None)
            st.session_state.pop("radtech_analysis_result", None)

            st.rerun()

        if analyze_clicked:

            run_analysis(
                uploaded_file,
                active_exam,
                active_patient,
                request,
            )

        return

    # --------------------------------------------------------
    # DONE — New Analysis + Save
    # --------------------------------------------------------

    with left:

        if st.button(
            "New Analysis",
            key="rx_new_analysis",
            icon=":material/restart_alt:",
            width="stretch",
        ):

            st.session_state.pop("rx_upload", None)
            st.session_state.pop("radtech_analysis_result", None)

            st.rerun()

        st.divider()

        if st.button(
            "Save as Patient Record",
            key="rx_save",
            icon=":material/save:",
            type="primary",
            width="stretch",
        ):

            ok = save_analysis(
                uploaded_file,
                result,
                active_exam,
                request,
                active_patient,
            )

            if ok:

                st.success("X-Ray saved. Status: X-Ray Ready.")

                go_back_to_queue()