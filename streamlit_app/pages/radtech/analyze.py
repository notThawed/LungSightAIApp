from html import escape

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
    save_xray_ai_heatmap,
)

from backend.backend_utils.subscription_usage import can_analyze_xray


from backend.ai.pneumonia_model import (
    predict,
    generate_gradcam,
)


from backend.ai.pneumonia_type_model import predict_type

from backend.ai.ood_validator import is_chest_xray, validator_available

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

# Session keys for the modal analysis flow
ANALYSIS_STATE_KEY = "rx_analysis_state"        # None | "running" | "complete"
ANALYSIS_RESULT_KEY = "radtech_analysis_result" # final result dict


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


def current_user_name():
    user = current_user()
    return full_name(
        user.get("first_name"),
        user.get("middle_name"),
        user.get("last_name"),
        user.get("suffix"),
    ) or "—"


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
    st.session_state.pop(ANALYSIS_RESULT_KEY, None)
    st.session_state.pop(ANALYSIS_STATE_KEY, None)


def go_back_to_queue():
    clear_active_examination()
    st.session_state.current_page = "X-ray Queue"
    st.rerun()


def timestamp_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def reset_analysis_state():
    """Clear the analysis flow state."""
    st.session_state[ANALYSIS_STATE_KEY] = None
    st.session_state.pop(ANALYSIS_RESULT_KEY, None)


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
# CONTEXT CARD
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
# EMPTY RIGHT PANEL
# ============================================================

def render_empty_results():

    st.markdown(
        "<div class='rx-empty'>"
        "<div class='rx-empty-icon'>crop_free</div>"
        "<p class='rx-empty-title'>Submission Summary</p>"
        "<p class='rx-empty-text'>"
        "Upload an X-ray image and click "
        "\"Analyze Image\" to submit it for "
        "physician review."
        "</p>"
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# PROGRESS STEP HTML
# ============================================================

def _progress_steps_html(current_step):

    steps = [
        "Validating image (X-ray check)...",
        "Running AI detection model...",
        "Running pneumonia classification...",
        "Preparing summary",
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
        + "".join(rows)
        + "</div>"
    )


# ============================================================
# MODAL — Analysis in progress
# ============================================================
#
# Runs the whole analysis in a SINGLE script run, updating
# a placeholder between steps. Only ONE st.rerun() at the
# very end to transition to the "complete" state.
#
# This avoids the flicker caused by multiple mid-flow reruns.
# ============================================================

@st.dialog("Analyzing X-Ray", width="small")
def show_analysis_progress_dialog(uploaded_file, examination, patient, request):

    status = st.empty()
    image_bytes = uploaded_file.getvalue()

    # --------------------------------------------------------
    # Step 0 — Preprocessing (OOD validation)
    # --------------------------------------------------------

    status.markdown(
        _progress_steps_html(0),
        unsafe_allow_html=True,
    )

    # Validate that the image is actually a chest X-ray
    # before running the pneumonia model.
    if not is_chest_xray(image_bytes):
        st.error(
            "⚠️ This image does not appear to be a chest X-ray. "
            "Please upload a valid chest radiograph."
        )
        st.session_state[ANALYSIS_STATE_KEY] = None
        return

    time.sleep(0.4)

    # --------------------------------------------------------
    # Step 1 — ResNet-50 detection
    # --------------------------------------------------------

    status.markdown(
        _progress_steps_html(1),
        unsafe_allow_html=True,
    )

    try:
        result = predict(image_bytes)

        
        # Generate Grad-CAM explanation for this prediction.
        # If it fails, keep the original AI prediction.

        gradcam_result = None
        gradcam_error = None

        try:
            gradcam_result = generate_gradcam(image_bytes)

        except Exception as exc:
            gradcam_error = str(exc)

            print(
                f"Grad-CAM generation failed: {exc}"
            )


        label = str(result.get("label", "")).strip().lower()

        if label not in ("positive", "negative"):
            raise ValueError(
                f"Unexpected ResNet-50 prediction label: {label!r}"
            )

        result["label"] = label
        result["pneumonia_type"] = None
        result["classification_confidence"] = None
        result["classification_model_version"] = None

    except Exception as error:
        st.error(f"AI prediction failed: {error}")
        return

    # --------------------------------------------------------
    # Step 2 — DenseNet-121 (only for positive cases)
    # --------------------------------------------------------

    if label == "positive":

        status.markdown(
            _progress_steps_html(2),
            unsafe_allow_html=True,
        )

        try:
            type_result = predict_type(image_bytes)

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

        except Exception as error:
            st.error(f"AI classification failed: {error}")
            return

    # --------------------------------------------------------
    # Step 3 — Preparing summary
    # --------------------------------------------------------

    status.markdown(
        _progress_steps_html(3),
        unsafe_allow_html=True,
    )
    time.sleep(0.4)

    # --------------------------------------------------------
    # Analysis done → switch to "complete" state
    # --------------------------------------------------------

    st.session_state[ANALYSIS_RESULT_KEY] = result

    # Keep the Grad-CAM result separately.
    st.session_state["gradcam_result"] = gradcam_result
    st.session_state["gradcam_error"] = gradcam_error

    st.session_state[ANALYSIS_STATE_KEY] = "complete"
    st.rerun()


# ============================================================
# MODAL — Analysis complete
# ============================================================

@st.dialog("Analysis Complete", width="small")
def show_analysis_complete_dialog():

    st.markdown(
        "<div class='rx-dialog-done'>"
        "<span class='rx-dialog-check'>check_circle</span>"
        "<p class='rx-dialog-done-title'>Analysis Successful</p>"
        "<p class='rx-dialog-done-text'>"
        "The X-ray has been processed and is ready "
        "to be submitted for physician review."
        "</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    if st.button(
        "Continue to Summary",
        key="rx_dialog_continue",
        type="primary",
        width="stretch",
        icon=":material/arrow_forward:",
    ):
        st.session_state[ANALYSIS_STATE_KEY] = None
        st.rerun()


# ============================================================
# SUBMISSION SUMMARY PANEL
# ============================================================

def render_submission_summary(request, patient, uploaded_file, result):

    st.markdown(
        "<p class='rx-panel-title'>Submission Summary</p>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='rx-submission-banner'>"
        "<span class='rx-submission-icon'>check_circle</span>"
        "<div>"
        "<p class='rx-submission-title'>Analysis Complete</p>"
        "<p class='rx-submission-text'>"
        "The X-ray has been processed and is ready "
        "for physician review."
        "</p>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='rx-summary-card'>"

        "<div class='rx-summary-row'>"
        "<span>Request ID</span>"
        f"<b>{escape(str(request.get('request_id') or '—'))}</b>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>Patient</span>"
        f"<b>{escape(patient_name(patient))}</b>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>Patient Code</span>"
        f"<b>{escape(str(patient_code(patient)))}</b>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>Body Part</span>"
        f"<b>{escape(request.get('body_part') or 'Chest')}</b>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>Priority</span>"
        f"<b>{escape(request.get('priority') or 'Routine')}</b>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>Image File</span>"
        f"<b>{escape(uploaded_file.name)}</b>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>Chest X-ray check</span>"
        f"<b>{'Passed' if validator_available() else 'Not run (validator unavailable)'}</b>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>AI Processing</span>"
        "<b>Complete</b>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>Submitted</span>"
        f"<b>{timestamp_now()}</b>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>Submitted By</span>"
        f"<b>{escape(current_user_name())}</b>"
        "</div>"

        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<p class='rx-summary-note'>"
        "The X-ray has been submitted to the physician's "
        "queue for review and interpretation."
        "</p>",
        unsafe_allow_html=True,
    )

    
    # ------------------------------------------
    # GRAD-CAM HEATMAP
    # ------------------------------------------

    st.divider()

    st.markdown(
        "<p class='rx-panel-title'>AI attention heatmap</p>",
        unsafe_allow_html=True,
    )

    gradcam_result = st.session_state.get(
        "gradcam_result"
    )

    if (
        gradcam_result
        and gradcam_result.get("overlay") is not None
    ):
        st.image(
            gradcam_result["overlay"],
            caption=(
                "Grad-CAM visualization. "
                "Highlighted areas show image regions "
                "that influenced the model's prediction. "
                "This visualization is not a diagnosis."
            ),
            width="stretch",
        )

    else:
        st.info(
            "Heatmap unavailable. The original AI "
            "prediction is still available."
        )



# ============================================================
# SAVE WORKFLOW
# ============================================================

def save_analysis(uploaded_file, result, examination, request, patient):

    user_id = current_user_id()

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

    quality_updated = update_xray_image_quality(
        image_id=image_id,
        quality_status="Passed",
        quality_checked_by=user_id,
    )

    if quality_updated is False:
        st.error("Failed to save the X-ray quality-check status.")
        return False

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

    
    # ------------------------------------------
    # SAVE GRAD-CAM HEATMAP
    # ------------------------------------------

    gradcam_result = st.session_state.get(
        "gradcam_result"
    )

    if gradcam_result and gradcam_result.get("overlay") is not None:

        try:
            import io

            heatmap_buffer = io.BytesIO()

            gradcam_result["overlay"].save(
                heatmap_buffer,
                format="PNG",
            )

            heatmap_bytes = heatmap_buffer.getvalue()

            heatmap_save_result = save_xray_ai_heatmap(
                ai_result_id=saved_result["ai_result_id"],
                heatmap_bytes=heatmap_bytes,
                model_version=AI_MODEL_VERSION,
                target_class=result["label"],
            )

            if not heatmap_save_result.get("success"):
                print(
                    "Grad-CAM storage warning: "
                    f"{heatmap_save_result.get('message')}"
                )

        except Exception as exc:
            print(
                f"Grad-CAM saving failed: {exc}"
            )

    else:
        print(
            "Grad-CAM heatmap unavailable; "
            "continuing without saving it."
        )


    update_xray_request_status(
        request["request_id"],
        status="Completed",
    )

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

    active_exam = st.session_state.get("radtech_active_examination")
    active_patient = st.session_state.get("radtech_active_patient")

    # ========================================================
    # GUARD — no patient selected
    # ========================================================

    if not (active_exam and active_patient):

        page_header(
            "Analyze X-Ray",
            "Upload a chest X-ray image and submit it for physician review.",
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
            reset_analysis_state()
            st.session_state.pop("rx_upload", None)
            st.session_state.current_page = "X-ray Queue"
            st.rerun()

        return

    # ========================================================
    # QUEUE MODE
    # ========================================================

    page_header(
        "Analyze X-Ray",
        "Upload a chest X-ray image and submit it for physician review.",
    )

    if st.button(
        "← Back to X-Ray Queue",
        key="rx_back_to_queue",
    ):
        go_back_to_queue()

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

    if not check_subscription():
        return

    # ========================================================
    # TWO-COLUMN WORKSPACE
    # ========================================================

    left, right = st.columns([1, 1], gap="large")

    # --------------------------------------------------------
    # LEFT — Upload
    # --------------------------------------------------------

    with left:

        with st.container(key="rx_panel_input"):

            st.markdown(
                "<p class='rx-panel-title'>Upload X-Ray Image</p>",
                unsafe_allow_html=True,
            )

            uploaded_file = st.file_uploader(
                "Select X-ray image",
                type=["png", "jpg", "jpeg"],
                key="rx_upload",
                label_visibility="collapsed",
            )

            if uploaded_file is None:
                st.markdown(
                    "<p class='rx-dropzone-sub'>"
                    "Supports JPEG, PNG formats"
                    "</p>",
                    unsafe_allow_html=True,
                )
            else:
                with st.container(key="rx_preview"):
                    st.image(uploaded_file, width="stretch")

    # --------------------------------------------------------
    # RIGHT — Submission Summary
    # --------------------------------------------------------

    with right:

        with st.container(key="rx_panel_output"):

            result = st.session_state.get(ANALYSIS_RESULT_KEY)

            if result and uploaded_file:
                render_submission_summary(
                    request,
                    active_patient,
                    uploaded_file,
                    result,
                )
            else:
                st.markdown(
                    "<p class='rx-panel-title'>&nbsp;</p>",
                    unsafe_allow_html=True,
                )
                render_empty_results()

    # ========================================================
    # DIALOG DISPATCHER
    # ========================================================

    analysis_state = st.session_state.get(ANALYSIS_STATE_KEY)

    if analysis_state == "running" and uploaded_file:
        show_analysis_progress_dialog(
            uploaded_file,
            active_exam,
            active_patient,
            request,
        )

    elif analysis_state == "complete":
        show_analysis_complete_dialog()

    # ========================================================
    # ACTION BUTTONS
    # ========================================================

    if uploaded_file is None:
        return

    result = st.session_state.get(ANALYSIS_RESULT_KEY)

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
            reset_analysis_state()
            st.session_state.pop("rx_upload", None)
            st.rerun()

        if analyze_clicked:
            st.session_state[ANALYSIS_STATE_KEY] = "running"
            st.rerun()

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
            reset_analysis_state()
            st.session_state.pop("rx_upload", None)
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