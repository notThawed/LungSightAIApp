import hashlib

import streamlit as st
import time

from datetime import datetime, timezone

from backend.fetches import (
    get_xray_request_by_examination,
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
from backend.ai.covid_type_model import predict_covid_type

from backend.ai.ood_validator import is_chest_xray
from backend.ai.image_loader import load_image, is_dicom
from backend import audit

from streamlit_app.components.ui import (
    page_header,
    show_rows,
    full_name,
    initials,
    safe,
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
COVID_MODEL_VERSION = "covid_resnet50_v1"

CONFIDENCE_THRESHOLD = 0.65

ANALYSIS_STATE_KEY = "rx_analysis_state"
ANALYSIS_RESULT_KEY = "radtech_analysis_result"
OVERRIDE_OOD_KEY = "radtech_override_ood"


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
    st.session_state.pop(OVERRIDE_OOD_KEY, None)


def go_back_to_queue():
    clear_active_examination()
    st.session_state.current_page = "X-ray Queus"
    st.rerun()


def timestamp_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def reset_analysis_state():
    """Clear the analysis flow state."""
    st.session_state[ANALYSIS_STATE_KEY] = None
    st.session_state.pop(ANALYSIS_RESULT_KEY, None)
    st.session_state.pop(OVERRIDE_OOD_KEY, None)


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
        "<div class='rx-empty-icon-wrap'>"
        "<span class='material-symbols-rounded rx-empty-icon'>radiology</span>"
        "</div>"
        "<p class='rx-empty-title'>Diagnostic Workstation</p>"
        "<p class='rx-empty-text'>"
        "Upload a chest radiograph on the left to begin AI pathology screening and generate attention heatmaps."
        "</p>"
        "<div class='rx-empty-steps'>"
        "<div class='rx-empty-step-item'><span class='rx-step-num'>1</span><span>Upload DICOM, PNG, or JPEG X-Ray</span></div>"
        "<div class='rx-empty-step-item'><span class='rx-step-num'>2</span><span>Execute AI Multi-Stage Classification</span></div>"
        "<div class='rx-empty-step-item'><span class='rx-step-num'>3</span><span>Verify Heatmap & Commit for Physician</span></div>"
        "</div>"
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
        "Running COVID vs Viral classification...",
        "Preparing diagnostic summary...",
    ]

    rows = []

    for index, label in enumerate(steps):

        if index < current_step:
            cls = "rx-step-done"
            status_glyph = "<span class='material-symbols-rounded'>check_circle</span>"
        elif index == current_step:
            cls = "rx-step-active"
            status_glyph = "<span class='material-symbols-rounded rx-step-spin'>sync</span>"
        else:
            cls = "rx-step-pending"
            status_glyph = "<span class='material-symbols-rounded'>radio_button_unchecked</span>"

        rows.append(
            f"<div class='rx-step {cls}'>"
            f"<span class='rx-step-icon'>{status_glyph}</span>"
            f"<span class='rx-step-label'>{label}</span>"
            "</div>"
        )

    return (
        "<div class='rx-progress-card'>"
        "<div class='rx-progress-header'>"
        "<span class='material-symbols-rounded rx-progress-head-icon'>smart_toy</span>"
        "<span>AI Diagnostic Pipeline</span>"
        "</div>"
        + "".join(rows)
        + "</div>"
    )


# ============================================================
# DIALOG — OOD Warning (Override)
# ============================================================

@st.dialog("⚠️ Image Validation Warning", width="small")
def show_ood_warning_dialog(uploaded_file, active_exam, active_patient, request):
    st.warning(
        "The AI validator detected that this image does **not** look like a standard chest X-ray. "
        "This could be due to lighting, cropping, or a different body part."
    )
    
    st.write("")
    st.markdown("**Do you want to force the system to analyze it anyway?**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Cancel", width="stretch"):
            st.session_state[ANALYSIS_STATE_KEY] = None
            st.session_state.pop(OVERRIDE_OOD_KEY, None)
            st.rerun()
            
    with col2:
        if st.button("Force Proceed", type="primary", width="stretch", icon=":material/warning:"):
            st.session_state[OVERRIDE_OOD_KEY] = True
            st.session_state[ANALYSIS_STATE_KEY] = "running"
            st.session_state["show_ood_warning"] = False
            st.rerun()


# ============================================================
# MODAL — Analysis in progress
# ============================================================

def _audit_analysis_event(event_type, outcome, request, image_bytes, metadata):
    """Keyed on request + image so dialog reruns do not duplicate the event."""

    request_id = (request or {}).get("request_id")
    image_hash = hashlib.sha256(image_bytes).hexdigest()[:16]
    stage = metadata.get("stage") or metadata.get("check") or ""

    audit.record_event(
        event_type,
        outcome,
        target_id=request_id,
        metadata=metadata,
        idempotency_key=f"{event_type}:{request_id}:{image_hash}:{stage}",
    )


@st.dialog("Analyzing X-Ray", width="small")
def show_analysis_progress_dialog(uploaded_file, examination, patient, request):

    status = st.empty()
    image_bytes = uploaded_file.getvalue()
    is_overridden = st.session_state.get(OVERRIDE_OOD_KEY, False)

    status.markdown(
        _progress_steps_html(0),
        unsafe_allow_html=True,
    )

    print("\n" + "="*60)
    print("🔬 STARTING ANALYSIS PIPELINE")
    print("="*60)

    if not is_overridden:
        if not is_chest_xray(image_bytes):
            print("❌ OOD VALIDATOR: Image rejected. Triggering warning dialog.")
            _audit_analysis_event(
                "xray.quality_rejected", "failure", request, image_bytes,
                {"check": "chest_xray_validator"},
            )
            st.session_state[ANALYSIS_STATE_KEY] = None
            st.session_state["show_ood_warning"] = True
            st.rerun()
            return

        print("✅ OOD VALIDATOR: Image is a chest X-ray. Proceeding...")
    else:
        print("⚠️ OOD VALIDATOR: Manual override activated. Proceeding anyway...")
        _audit_analysis_event(
            "xray.quality_overridden", "success", request, image_bytes,
            {"check": "chest_xray_validator"},
        )

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

        print(f"🧠 RESNET-50: {result.get('label')} "
              f"(confidence: {result.get('confidence'):.4f})")

        gradcam_result = None
        gradcam_error = None

        try:
            gradcam_result = generate_gradcam(image_bytes)
            print("🔥 GRAD-CAM: Heatmap generated successfully.")
        except Exception as exc:
            gradcam_error = str(exc)
            print(f"⚠️ GRAD-CAM FAILED: {exc}")

        label = str(result.get("label", "")).strip().lower()
        confidence = result.get("confidence", 0.0)

        if label not in ("positive", "negative"):
            raise ValueError(
                f"Unexpected ResNet-50 prediction label: {label!r}"
            )

        result["label"] = label
        result["pneumonia_type"] = None
        result["classification_confidence"] = None
        result["classification_model_version"] = None

        # --- CONFIDENCE GATE: STEP 1 ---
        if confidence < CONFIDENCE_THRESHOLD:
            print(f"⚠️ LOW CONFIDENCE ({confidence:.2f}). Flagging as inconclusive.")
            result["label"] = "inconclusive"
            
            status.markdown(_progress_steps_html(4), unsafe_allow_html=True)
            time.sleep(0.4)
            st.session_state[ANALYSIS_RESULT_KEY] = result
            st.session_state["gradcam_result"] = gradcam_result
            st.session_state["gradcam_error"] = gradcam_error
            st.session_state.pop(OVERRIDE_OOD_KEY, None)
            st.session_state[ANALYSIS_STATE_KEY] = "complete"
            st.rerun()
            return

    except Exception as error:
        print(f"❌ RESNET-50 FAILED: {error}")
        _audit_analysis_event(
            "ai.analysis_failed", "failure", request, image_bytes,
            {
                "stage": "detection",
                "model_version": AI_MODEL_VERSION,
                "error_class": audit.error_class(error),
            },
        )
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

            print(f"🦠 DENSENET-121 (Type): {type_result.get('label')} "
                  f"(confidence: {type_result.get('confidence'):.4f})")

            type_label = str(type_result.get("label", "")).strip().lower()
            type_conf = float(type_result.get("confidence", 0.0))

            if type_label not in ("bacterial_pneumonia", "viral_pneumonia"):
                raise ValueError(
                    f"Unexpected DenseNet-121 prediction label: {type_label!r}"
                )

            result["pneumonia_type"] = type_label
            result["classification_confidence"] = type_conf
            result["classification_model_version"] = CLASSIFICATION_MODEL_VERSION

            # --- CONFIDENCE GATE: STEP 2 ---
            if type_conf < CONFIDENCE_THRESHOLD:
                print(f"⚠️ LOW TYPE CONFIDENCE ({type_conf:.2f}). Flagging type as inconclusive.")
                result["pneumonia_type"] = "inconclusive"
                
                status.markdown(_progress_steps_html(4), unsafe_allow_html=True)
                time.sleep(0.4)
                st.session_state[ANALYSIS_RESULT_KEY] = result
                st.session_state["gradcam_result"] = gradcam_result
                st.session_state["gradcam_error"] = gradcam_error
                st.session_state.pop(OVERRIDE_OOD_KEY, None)
                st.session_state[ANALYSIS_STATE_KEY] = "complete"
                st.rerun()
                return

        except Exception as error:
            print(f"❌ DENSENET-121 (Type) FAILED: {error}")
            _audit_analysis_event(
                "ai.analysis_failed", "failure", request, image_bytes,
                {
                    "stage": "type_classification",
                    "model_version": CLASSIFICATION_MODEL_VERSION,
                    "error_class": audit.error_class(error),
                },
            )
            st.error(f"AI classification failed: {error}")
            return

        # --------------------------------------------------------
        # Step 3 — COVID vs Viral (only for VIRAL cases)
        # --------------------------------------------------------

        if type_label == "viral_pneumonia":

            status.markdown(
                _progress_steps_html(3),
                unsafe_allow_html=True,
            )

            try:
                covid_result = predict_covid_type(image_bytes)

                print(f"🦠 COVID MODEL: {covid_result.get('label')} "
                      f"(confidence: {covid_result.get('confidence'):.4f})")

                covid_label = str(covid_result.get("label", "")).strip().lower()
                covid_conf = float(covid_result.get("confidence", 0.0))

                if covid_label not in ("viral_pneumonia", "covid_pneumonia"):
                    raise ValueError(
                        f"Unexpected COVID model label: {covid_label!r}"
                    )

                result["pneumonia_type"] = covid_label
                result["classification_confidence"] = covid_conf
                result["classification_model_version"] = COVID_MODEL_VERSION

                # --- CONFIDENCE GATE: STEP 3 ---
                if covid_conf < CONFIDENCE_THRESHOLD:
                    print(f"⚠️ LOW COVID CONFIDENCE ({covid_conf:.2f}). Flagging as inconclusive.")
                    result["pneumonia_type"] = "inconclusive"

            except Exception as error:
                print(f"⚠️ COVID MODEL FAILED (non-fatal): {error}")

        else:
            print("⏭️ COVID MODEL: Skipped (not viral pneumonia).")

    else:
        print("⏭️ DENSENET-121: Skipped (image is negative).")

    # --------------------------------------------------------
    # Final step — Preparing summary
    # --------------------------------------------------------

    status.markdown(
        _progress_steps_html(4),
        unsafe_allow_html=True,
    )
    time.sleep(0.4)

    print("\n" + "="*60)
    print("✅ PIPELINE COMPLETE")
    print(f"   Findings:      {result.get('label')}")
    print(f"   Pneumonia:     {result.get('pneumonia_type')}")
    print("="*60 + "\n")

    st.session_state[ANALYSIS_RESULT_KEY] = result
    st.session_state["gradcam_result"] = gradcam_result
    st.session_state["gradcam_error"] = gradcam_error

    st.session_state.pop(OVERRIDE_OOD_KEY, None) 

    st.session_state[ANALYSIS_STATE_KEY] = "complete"
    st.rerun()


# ============================================================
# MODAL — Analysis complete
# ============================================================

@st.dialog("Analysis Complete", width="small")
def show_analysis_complete_dialog():

    st.markdown(
        "<div class='rx-dialog-done'>"
        "<span class='material-symbols-rounded rx-dialog-check'>check_circle</span>"
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
        "<span class='material-symbols-rounded rx-submission-icon'>check_circle</span>"
        "<div>"
        "<p class='rx-submission-title'>AI Analysis Complete</p>"
        "<p class='rx-submission-text'>"
        "The radiograph has been evaluated and is ready for physician verification."
        "</p>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    pneu_type = result.get("pneumonia_type")
    if pneu_type == "inconclusive":
        pneu_display = "Inconclusive"
        pneu_tag_class = "rx-tag-amber"
    elif pneu_type:
        pneu_display = pneu_type.replace("_", " ").title()
        pneu_tag_class = "rx-tag-red" if any(w in pneu_type for w in ["covid", "viral", "bacterial"]) else "rx-tag-blue"
    else:
        pneu_display = "None Detected"
        pneu_tag_class = "rx-tag-green"

    main_label = str(result.get("label", "—")).strip().lower()
    if main_label == "inconclusive":
        main_display = "Inconclusive (Low Confidence)"
        main_tag_class = "rx-tag-amber"
    elif main_label == "positive":
        main_display = "Positive for Infiltration"
        main_tag_class = "rx-tag-red"
    elif main_label == "negative":
        main_display = "Negative / Normal"
        main_tag_class = "rx-tag-green"
    else:
        main_display = main_label.title()
        main_tag_class = "rx-tag-slate"

    req_id = str(request.get("request_id") or "—")
    req_code = f"#{req_id[:8]}" if req_id != "—" else "—"

    st.markdown(
        "<div class='rx-summary-card'>"

        "<div class='rx-summary-row'>"
        "<span>Request ID</span>"
        f"<b class='rx-mono-val'>{safe(req_code)}</b>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>Patient Name</span>"
        f"<b>{safe(patient_name(patient))}</b>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>Patient Code</span>"
        f"<span class='rx-ref-pill'>{safe(patient_code(patient))}</span>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>Body Part & Priority</span>"
        f"<b>{safe(request.get('body_part') or 'Chest')} · {safe(request.get('priority') or 'Routine')}</b>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>Source File</span>"
        f"<b class='rx-file-val'>{safe(uploaded_file.name)}</b>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>Quality Status</span>"
        "<span class='rx-tag rx-tag-green'><span class='material-symbols-rounded'>verified</span> Passed Check</span>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>AI Findings</span>"
        f"<span class='rx-tag {main_tag_class}'>{safe(main_display)}</span>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>Pneumonia Classification</span>"
        f"<span class='rx-tag {pneu_tag_class}'>{safe(pneu_display)}</span>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>AI Engine</span>"
        "<span class='rx-tag rx-tag-teal'>Complete · Multi-Model v1</span>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>Timestamp</span>"
        f"<b>{timestamp_now()}</b>"
        "</div>"

        "<div class='rx-summary-row'>"
        "<span>Technologist</span>"
        f"<b>{safe(current_user_name())}</b>"
        "</div>"

        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<p class='rx-summary-note'>"
        "<span class='material-symbols-rounded'>info</span>"
        "The X-ray and Grad-CAM heatmap will be committed to the physician review queue upon saving."
        "</p>",
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown(
        "<div class='rx-heatmap-header'>"
        "<span class='material-symbols-rounded'>blur_on</span>"
        "<span>AI Attention Heatmap (Grad-CAM)</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    gradcam_result = st.session_state.get("gradcam_result")

    if (
        gradcam_result
        and gradcam_result.get("overlay") is not None
    ):
        with st.container(key="rx_heatmap_box"):
            st.image(
                gradcam_result["overlay"],
                caption=(
                    "Grad-CAM Heatmap Visualization: Highlighted regions "
                    "indicate features that influenced the neural network prediction. "
                    "This is an interpretability aid and not a clinical diagnosis."
                ),
                width="stretch",
            )
    else:
        st.info(
            "Heatmap unavailable for this study. The primary AI "
            "prediction was recorded successfully."
        )


# ============================================================
# SAVE WORKFLOW
# ============================================================

def save_analysis(uploaded_file, result, examination, request, patient):
    user_id = current_user_id()

    import io

    file_bytes = uploaded_file.getvalue()
    file_name = uploaded_file.name

    if is_dicom(file_bytes):
        print(f"🗂️ DICOM detected: {file_name}. Converting to PNG...")
        img = load_image(file_bytes)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        file_bytes = buffer.getvalue()
        file_name = file_name.rsplit(".", 1)[0] + ".png"
        print(f"✅ Converted to PNG: {file_name}")

    upload_result = upload_xray_image(
        request_id=request["request_id"],
        file_bytes=file_bytes,
        filename=file_name,
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
        classification_confidence=result.get("classification_confidence"),
        classification_model_version=result.get("classification_model_version"),
    )

    if not saved_result:
        st.error(
            "The X-ray image was uploaded, but saving the AI results "
            "failed. The examination has not been marked as completed."
        )
        return False

    gradcam_result = st.session_state.get("gradcam_result")

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
            print(f"Grad-CAM saving failed: {exc}")

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

    if not (active_exam and active_patient):

        page_header(
            "Analyze X-Ray",
            "Upload a chest X-ray image and submit it for physician review.",
        )

        st.markdown(
            "<div class='rx-guard'>"
            "<div class='rx-guard-icon'>"
            "<span class='material-symbols-rounded'>person_search</span>"
            "</div>"
            "<p class='rx-guard-title'>No Patient Selected</p>"
            "<p class='rx-guard-text'>"
            "Pick a patient from the X-Ray Queue to analyze their chest X-ray and generate AI diagnostics."
            "</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        _, center_col, _ = st.columns([1, 1.2, 1])
        with center_col:
            if st.button(
                "Back to X-Ray Queue",
                key="rx_guard_back",
                icon=":material/arrow_back:",
                type="primary",
                width="stretch",
            ):
                reset_analysis_state()
                st.session_state.pop("rx_upload", None)
                st.session_state.current_page = "X-ray Queus"
                st.rerun()

        return

    page_header(
        "Analyze X-Ray",
        "Upload a chest X-ray image and submit it for physician review.",
    )

    if st.button(
        "Back to X-Ray Queue",
        key="rx_back_to_queue",
        icon=":material/arrow_back:",
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

    left, right = st.columns([1, 1], gap="large")

    with left:
        with st.container(key="rx_panel_input"):
            st.markdown(
                "<p class='rx-panel-title'>Upload X-Ray Image</p>",
                unsafe_allow_html=True,
            )

            uploaded_file = st.file_uploader(
                "Select X-ray image",
                type=["png", "jpg", "jpeg", "dcm"],
                key="rx_upload",
                label_visibility="collapsed",
            )

            if uploaded_file is None:
                st.markdown(
                    "<p class='rx-dropzone-sub'>"
                    "Supports JPEG, PNG, and DICOM (.dcm) formats"
                    "</p>",
                    unsafe_allow_html=True,
                )
            else:
                with st.container(key="rx_preview"):
                    raw_bytes = uploaded_file.getvalue()

                    if is_dicom(raw_bytes):
                        print(f"🗂️ DICOM preview: rendering {uploaded_file.name} as PNG")
                        preview_img = load_image(raw_bytes)
                        st.image(
                            preview_img,
                            caption=f"DICOM preview: {uploaded_file.name}",
                            width="stretch",
                        )
                    else:
                        st.image(uploaded_file, width="stretch")

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

    if st.session_state.get("show_ood_warning"):
        st.session_state["show_ood_warning"] = False
        show_ood_warning_dialog(uploaded_file, active_exam, active_patient, request)

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
            st.session_state.pop(OVERRIDE_OOD_KEY, None)
            st.rerun()

        return

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