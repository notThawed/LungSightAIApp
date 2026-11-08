
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.fetches import (
    get_patient_xray_history,
    get_xray_image_url,
    get_xray_ai_result,
)


MANILA_TZ = ZoneInfo("Asia/Manila")


def format_xray_date(value):
    if not value:
        return "Unknown date"

    try:
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if dt.tzinfo is not None:
            dt = dt.astimezone(MANILA_TZ)

        return dt.strftime("%B %d, %Y")
    except (ValueError, TypeError):
        return str(value)


def get_xray_label(record):
    date_label = format_xray_date(
        record.get("examination_date")
        or record.get("created_at")
    )

    exam_type = record.get("examination_type") or "Examination"
    exam_id = str(record.get("examination_id") or "")

    return f"{date_label} | {exam_type} | {exam_id[:8]}"


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

    if isinstance(findings, str) and findings.strip():
        return findings

    if ai.get("pneumonia_type"):
        return str(ai["pneumonia_type"])

    return "Result available; see examination report"


def render_xray_panel(record, title):
    st.markdown(f"#### {title}")

    st.caption(get_xray_label(record))

    image_url = get_xray_image_url(
        record.get("image_path")
    )

    if image_url:
        st.image(image_url, width="stretch")
    else:
        st.warning("Unable to load this X-ray image.")

    ai = get_xray_ai_result(record.get("image_id"))

    st.markdown("**AI Analysis**")
    st.write(get_prediction_label(ai))

    if ai:
        confidence = ai.get("ai_confidence")

        if confidence is not None:
            try:
                value = float(confidence)

                if 0 <= value <= 1:
                    value *= 100

                st.caption(f"Confidence: {value:.1f}%")
            except (ValueError, TypeError):
                pass

    return ai


@st.dialog("Compare Patient X-Rays", width="large")
def show_xray_comparison(
    patient_id,
    hospital_id,
    current_examination_id=None,
):
    """
    Review Patient:
        current_examination_id is supplied.
        The current examination stays fixed.

    Patient Records:
        current_examination_id is None.
        The latest available X-ray stays fixed.
    """

    if not patient_id:
        st.error("No patient was selected.")
        return

    user = st.session_state.get("user") or {}
    role_id = user.get("role_id")

    if role_id not in (1, 3, 6):
        st.error("You do not have permission to view X-rays.")
        return

    # The hospital must come from the authenticated session.
    authorized_hospital = user.get("hospital_id")

    if role_id != 1:
        if not authorized_hospital:
            st.error("Your hospital assignment is missing.")
            return

        if str(hospital_id) != str(authorized_hospital):
            st.error("Access denied.")
            return

        hospital_id = authorized_hospital

    try:
        history = get_patient_xray_history(
            patient_id,
            hospital_id=hospital_id,
        )
    except Exception:
        st.error("Unable to load the patient's X-ray history.")
        return

    if not history:
        st.info("No uploaded X-rays were found.")
        return

    if current_examination_id is not None:
        # Review Patient: fix the examination being reviewed.
        fixed = next(
            (
                record for record in history
                if str(record["examination_id"])
                == str(current_examination_id)
            ),
            None,
        )

        if fixed is None:
            st.warning(
                "The current examination has no available X-ray."
            )
            return

        fixed_index = history.index(fixed)

        # Only allow genuinely earlier examinations.
        previous_records = history[fixed_index + 1:]

        fixed_title = "Current X-Ray"

    else:
        # Patient Records: fix the latest uploaded X-ray.
        fixed = history[0]
        previous_records = history[1:]
        fixed_title = "Latest X-Ray"

    if not previous_records:
        st.info(
            "No earlier X-ray examinations are available "
            "for comparison."
        )
        return

    st.markdown(
        "Select any previous X-ray to compare with "
        "the fixed current/latest X-ray."
    )

    selected_id = st.selectbox(
        "Select Previous X-Ray",
        options=[
            record["examination_id"]
            for record in previous_records
        ],
        format_func=lambda exam_id: get_xray_label(
            next(
                record for record in previous_records
                if record["examination_id"] == exam_id
            )
        ),
        key=(
            "xray_comparison_previous_"
            f"{patient_id}_{current_examination_id or 'latest'}"
        ),
    )

    selected = next(
        record for record in previous_records
        if record["examination_id"] == selected_id
    )

    st.divider()

    previous_col, latest_col = st.columns(
        2,
        gap="medium",
    )

    with previous_col:
        render_xray_panel(
            selected,
            "Previous X-Ray",
        )

    with latest_col:
        render_xray_panel(
            fixed,
            fixed_title,
        )

    st.divider()

    st.caption(
        "X-rays and AI results are displayed for physician "
        "review. Differences in predictions or confidence "
        "do not by themselves establish clinical progression."
    )

    if st.button(
        "Close Comparison",
        width="stretch",
        key="close_xray_comparison",
    ):
        st.rerun()
