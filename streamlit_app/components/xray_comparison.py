
# streamlit_app/components/xray_comparison.py

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from backend.fetches import (
    get_patient_xray_history,
    get_xray_image_url,
    get_xray_ai_result,
)


MANILA_TZ = ZoneInfo("Asia/Manila")


# ============================================================
# FORMATTING HELPERS
# ============================================================

def format_xray_date(value, include_time=False):
    if not value:
        return "Not recorded"

    try:
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if dt.tzinfo is not None:
            dt = dt.astimezone(MANILA_TZ)

        fmt = (
            "%B %d, %Y at %I:%M %p"
            if include_time
            else "%B %d, %Y"
        )

        return dt.strftime(fmt)

    except (ValueError, TypeError):
        return str(value)


def display_value(value):
    if value is None:
        return "Not recorded"

    text = str(value).strip()
    return text if text else "Not recorded"


def format_exam_type(record):
    exam_type = display_value(
        record.get("examination_type")
    )

    sequence = record.get("follow_up_sequence")

    normalized = exam_type.lower().replace(
        "-", " "
    ).replace("_", " ")

    if "follow up" in normalized or "followup" in normalized:
        if sequence is not None:
            try:
                return (
                    "Follow-Up Examination "
                    f"{int(sequence):03d}"
                )
            except (ValueError, TypeError):
                pass

        return "Follow-Up Examination"

    return exam_type


def get_xray_label(record):
    exam_date = format_xray_date(
        record.get("examination_date")
        or record.get("created_at")
    )

    exam_type = format_exam_type(record)

    exam_id = str(
        record.get("examination_id") or ""
    )[:8]

    return f"{exam_date} | {exam_type} | {exam_id}"


def confidence_percent(value):
    if value is None:
        return "Not recorded"

    try:
        number = float(value)

        if 0 <= number <= 1:
            number *= 100

        return f"{number:.1f}%"

    except (ValueError, TypeError):
        return "Not recorded"


def get_prediction_label(ai):
    if not ai:
        return "No AI result"

    findings = ai.get("ai_findings")

    if isinstance(findings, dict):
        for key in (
            "prediction",
            "predicted_class",
            "classification",
            "label",
        ):
            if findings.get(key):
                return str(findings[key])

    if findings is not None:
        return display_value(findings).title()

    return "Not recorded"


def get_pneumonia_label(ai):
    if not ai:
        return "No AI result"

    value = ai.get("pneumonia_type")

    if not value:
        return "None detected / Not classified"

    return str(value).replace("_", " ").title()


def get_ai(record):
    # New history function already supplies the AI result.
    ai = record.get("ai_result")

    if isinstance(ai, dict) and ai:
        return ai

    # Compatibility with older history data.
    return (
        get_xray_ai_result(record.get("image_id"))
        or {}
    )


# ============================================================
# DISPLAY HELPERS
# ============================================================

def detail_row(label, value):
    with st.container():
        col_label, col_value = st.columns(
            [1, 2],
            gap="small",
        )

        with col_label:
            st.caption(label)

        with col_value:
            st.write(display_value(value))


def comparison_row(label, previous, current):
    col_label, col_previous, col_current = (
        st.columns([1.2, 2, 2], gap="medium")
    )

    with col_label:
        st.markdown(f"**{label}**")

    with col_previous:
        st.write(display_value(previous))

    with col_current:
        st.write(display_value(current))


def comparison_heading(previous, current):
    col_label, col_previous, col_current = (
        st.columns([1.2, 2, 2], gap="medium")
    )

    with col_label:
        st.markdown("**Field**")

    with col_previous:
        st.markdown("**Previous Examination**")
        st.caption(get_xray_label(previous))

    with col_current:
        st.markdown("**Current / Latest Examination**")
        st.caption(get_xray_label(current))


# ============================================================
# X-RAY PANEL
# ============================================================

def render_xray_panel(record, title):
    st.markdown(f"### {title}")

    st.caption(get_xray_label(record))

    image_url = get_xray_image_url(
        record.get("image_path")
    )

    if image_url:
        st.image(image_url, width="stretch")
    else:
        st.warning("Unable to load this X-ray image.")

    ai = get_ai(record)

    st.markdown("**AI Analysis**")

    detail_row(
        "AI Findings",
        get_prediction_label(ai),
    )

    detail_row(
        "Pneumonia Classification",
        get_pneumonia_label(ai),
    )

    detail_row(
        "AI Confidence",
        confidence_percent(
            ai.get("ai_confidence")
        ),
    )

    detail_row(
        "Classification Confidence",
        confidence_percent(
            ai.get("classification_confidence")
        ),
    )

    with st.expander("Image and examination identifiers"):
        st.caption(
            "Use these identifiers to verify that "
            "two different X-ray records were loaded."
        )

        st.code(
            f"Examination ID: {record.get('examination_id')}\n"
            f"Image ID: {record.get('image_id')}\n"
            f"Request ID: {record.get('request_id')}",
            language="text",
        )

    return ai


# ============================================================
# CLINICAL COMPARISON
# ============================================================

def render_clinical_comparison(previous, current):
    st.markdown("### Clinical Comparison")

    comparison_heading(previous, current)

    st.divider()

    comparison_row(
        "Examination Type",
        format_exam_type(previous),
        format_exam_type(current),
    )

    comparison_row(
        "Examination Status",
        previous.get("status"),
        current.get("status"),
    )

    comparison_row(
        "Chief Complaint",
        previous.get("chief_complaint"),
        current.get("chief_complaint"),
    )

    comparison_row(
        "History of Present Illness",
        previous.get("history_of_present_illness"),
        current.get("history_of_present_illness"),
    )

    comparison_row(
        "Physical Examination",
        previous.get("physical_examination"),
        current.get("physical_examination"),
    )

    comparison_row(
        "Clinical Indication",
        previous.get("clinical_indication"),
        current.get("clinical_indication"),
    )

    st.divider()

    st.markdown("#### Physician Assessment")

    comparison_row(
        "Diagnosis",
        previous.get("diagnosis"),
        current.get("diagnosis"),
    )

    comparison_row(
        "Plans / Orders",
        previous.get("plans_orders"),
        current.get("plans_orders"),
    )

    comparison_row(
        "Disposition",
        previous.get("disposition"),
        current.get("disposition"),
    )

    comparison_row(
        "CURB-65 Score",
        (
            f"{previous['curb65_score']}/5"
            if previous.get("curb65_score") is not None
            else None
        ),
        (
            f"{current['curb65_score']}/5"
            if current.get("curb65_score") is not None
            else None
        ),
    )

    comparison_row(
        "Physician Severity",
        previous.get("severity_status"),
        current.get("severity_status"),
    )


# ============================================================
# RADIOLOGY COMPARISON
# ============================================================

def render_radiology_comparison(
    previous,
    current,
    previous_ai,
    current_ai,
):
    st.markdown("### Radiology and AI Comparison")

    comparison_heading(previous, current)

    st.divider()

    comparison_row(
        "AI Findings",
        get_prediction_label(previous_ai),
        get_prediction_label(current_ai),
    )

    comparison_row(
        "Pneumonia Classification",
        get_pneumonia_label(previous_ai),
        get_pneumonia_label(current_ai),
    )

    comparison_row(
        "AI Confidence",
        confidence_percent(
            previous_ai.get("ai_confidence")
        ),
        confidence_percent(
            current_ai.get("ai_confidence")
        ),
    )

    comparison_row(
        "Classification Confidence",
        confidence_percent(
            previous_ai.get("classification_confidence")
        ),
        confidence_percent(
            current_ai.get("classification_confidence")
        ),
    )

    comparison_row(
        "Physician X-Ray Findings",
        previous.get("xray_findings"),
        current.get("xray_findings"),
    )

    comparison_row(
        "Physician X-Ray Impression",
        previous.get("xray_impression"),
        current.get("xray_impression"),
    )


# ============================================================
# MEDICAL PERSONNEL
# ============================================================

def render_personnel_comparison(previous, current):
    st.markdown("### Medical Personnel")

    comparison_heading(previous, current)

    st.divider()

    comparison_row(
        "Requesting Physician",
        previous.get("requesting_physician"),
        current.get("requesting_physician"),
    )

    comparison_row(
        "Radiology Technologist",
        previous.get("radiology_technologist"),
        current.get("radiology_technologist"),
    )

    comparison_row(
        "Reviewing Physician",
        previous.get("reviewing_physician"),
        current.get("reviewing_physician"),
    )

    comparison_row(
        "X-Ray Uploaded",
        format_xray_date(
            previous.get("uploaded_at"),
            include_time=True,
        ),
        format_xray_date(
            current.get("uploaded_at"),
            include_time=True,
        ),
    )

    comparison_row(
        "X-Ray Reviewed",
        format_xray_date(
            previous.get("reviewed_at"),
            include_time=True,
        ) if previous.get("reviewed_at") else None,
        format_xray_date(
            current.get("reviewed_at"),
            include_time=True,
        ) if current.get("reviewed_at") else None,
    )


# ============================================================
# MAIN COMPARISON DIALOG
# ============================================================

@st.dialog("Compare Patient X-Rays", width="large")
def show_xray_comparison(
    patient_id,
    hospital_id,
    current_examination_id=None,
):
    """
    Review Patient:
        The current examination remains fixed.

    Patient Records:
        The latest available X-ray remains fixed.
    """

    if not patient_id:
        st.error("No patient was selected.")
        return

    user = st.session_state.get("user") or {}

    try:
        role_id = int(user.get("role_id"))
    except (TypeError, ValueError):
        st.error("Invalid user role.")
        return

    if role_id not in (1, 3, 6):
        st.error(
            "You do not have permission to view X-rays."
        )
        return

    authorized_hospital = user.get("hospital_id")

    if role_id != 1:
        if not authorized_hospital:
            st.error(
                "Your hospital assignment is missing."
            )
            return

        if str(hospital_id) != str(
            authorized_hospital
        ):
            st.error("Access denied.")
            return

        hospital_id = authorized_hospital

    try:
        history = get_patient_xray_history(
            patient_id,
            hospital_id=hospital_id,
        ) or []

    except Exception as exc:
        st.error(
            "Unable to load the patient's X-ray history."
        )
        print(f"X-ray comparison error: {exc}")
        return

    if not history:
        st.info("No uploaded X-rays were found.")
        return

    # Determine which examination must remain fixed.
    if current_examination_id is not None:
        fixed = next(
            (
                record for record in history
                if str(record.get("examination_id"))
                == str(current_examination_id)
            ),
            None,
        )

        if fixed is None:
            st.warning(
                "The current examination has no "
                "available X-ray."
            )
            return

        fixed_index = history.index(fixed)

        previous_records = history[
            fixed_index + 1:
        ]

        fixed_title = "Current X-Ray"

    else:
        fixed = history[0]
        previous_records = history[1:]
        fixed_title = "Latest X-Ray"

    if not previous_records:
        st.info(
            "No earlier X-ray examinations are "
            "available for comparison."
        )
        return

    st.write(
        "Compare the selected previous examination "
        "with the fixed current/latest examination."
    )

    # Use image IDs rather than examination IDs so
    # each selection identifies the actual image.
    options = [
        str(record["image_id"])
        for record in previous_records
    ]

    selected_image_id = st.selectbox(
        "Select Previous X-Ray",
        options=options,
        format_func=lambda image_id: get_xray_label(
            next(
                record for record in previous_records
                if str(record.get("image_id"))
                == str(image_id)
            )
        ),
        key=(
            "xray_comparison_previous_"
            f"{patient_id}_"
            f"{current_examination_id or 'latest'}"
        ),
    )

    selected = next(
        record for record in previous_records
        if str(record.get("image_id"))
        == str(selected_image_id)
    )

    # Detect accidental same-image comparisons.
    if str(selected.get("image_id")) == str(
        fixed.get("image_id")
    ):
        st.error(
            "The selected images have the same "
            "image ID. Choose another record."
        )
        return

    st.divider()

    # --------------------------------------------------------
    # ORIGINAL X-RAYS
    # --------------------------------------------------------

    previous_col, current_col = st.columns(
        2,
        gap="medium",
    )

    with previous_col:
        previous_ai = render_xray_panel(
            selected,
            "Previous X-Ray",
        )

    with current_col:
        current_ai = render_xray_panel(
            fixed,
            fixed_title,
        )

    st.divider()

    # --------------------------------------------------------
    # EXPANDED COMPARISON
    # --------------------------------------------------------

    tabs = st.tabs([
        "Clinical Comparison",
        "Radiology / AI",
        "Medical Personnel",
    ])

    with tabs[0]:
        render_clinical_comparison(
            selected,
            fixed,
        )

    with tabs[1]:
        render_radiology_comparison(
            selected,
            fixed,
            previous_ai,
            current_ai,
        )

    with tabs[2]:
        render_personnel_comparison(
            selected,
            fixed,
        )

    st.divider()

    st.info(
        "AI predictions and confidence scores are "
        "decision-support information, not proof of "
        "clinical improvement or deterioration. "
        "The physician should interpret the actual "
        "radiographs together with the patient's "
        "clinical history."
    )

    if st.button(
        "Close Comparison",
        key="close_xray_comparison",
        width="stretch",
    ):
        st.rerun()
