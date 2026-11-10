
# backend/backend_utils/severity_utils.py

from datetime import date, datetime

OUTDATED_THRESHOLD_DAYS = 90

ELIGIBLE_STATUSES = (
    "Completed",
    "Admitted",
    "Discharged",
)


def _parse_date(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        ).date()
    except (TypeError, ValueError):
        return None


def _severity_exam_sort_key(exam):
    """
    Sort examinations by their actual examination date.

    created_at and examination_id are used as
    secondary sorting values.
    """
    return (
        str(
            exam.get("examination_date")
            or exam.get("created_at")
            or ""
        ),
        str(exam.get("created_at") or ""),
        str(exam.get("examination_id") or ""),
    )


def get_latest_severity(examinations):
    """
    Return the latest finalized General Consultation
    or Follow-Up Examination.

    IMPORTANT:
    - Do not require an existing severity score.
    - Do not fall back to an older examination.
    - Exclude inpatient rounds.
    - Return None if no eligible examination exists.

    If the latest examination has no severity values,
    the UI will display 'Not Assessed'.
    """

    eligible = []

    for exam in examinations or []:
        status = (exam.get("status") or "").strip()

        if status not in ELIGIBLE_STATUSES:
            continue

        exam_type = (
            exam.get("examination_type") or ""
        ).strip().lower().replace("_", " ").replace("-", " ")

        if exam_type == "inpatient round":
            continue

        eligible.append(exam)

    if not eligible:
        return None

    return max(
        eligible,
        key=_severity_exam_sort_key,
    )


def get_severity_alert(examinations, latest):
    """
    Return severity warnings based on the latest
    eligible examination and previous assessments.
    """

    if not latest:
        return (
            "warning",
            "No completed examination on record. "
            "Please evaluate this patient.",
        )

    has_curb = latest.get("curb65_score") is not None

    manual = (
        latest.get("severity_status") or ""
    ).strip()

    has_manual = (
        bool(manual)
        and manual.lower() != "not assessed"
    )

    if not has_curb and not has_manual:
        return (
            "warning",
            "The latest examination has no recorded "
            "severity assessment.",
        )

    exam_date = _parse_date(
        latest.get("examination_date")
        or latest.get("created_at")
    )

    if exam_date:
        days_old = (date.today() - exam_date).days

        if days_old > OUTDATED_THRESHOLD_DAYS:
            return (
                "warning",
                f"Latest assessment is {days_old} days old. "
                "Consider re-evaluating.",
            )

    eligible = []

    for exam in examinations or []:
        status = (exam.get("status") or "").strip()

        if status not in ELIGIBLE_STATUSES:
            continue

        exam_type = (
            exam.get("examination_type") or ""
        ).strip().lower().replace("_", " ").replace("-", " ")

        if exam_type == "inpatient round":
            continue

        eligible.append(exam)

    eligible.sort(
        key=_severity_exam_sort_key,
        reverse=True,
    )

    # Find the examination immediately preceding
    # the latest examination.
    latest_id = latest.get("examination_id")

    previous = None

    for exam in eligible:
        if latest_id is not None:
            if exam.get("examination_id") == latest_id:
                continue
        elif exam is latest:
            continue

        previous = exam
        break

    if previous:
        prev_curb = previous.get("curb65_score")
        prev_manual = (
            previous.get("severity_status") or ""
        ).strip().lower()

        previous_high = (
            (
                prev_curb is not None
                and prev_curb >= 3
            )
            or prev_manual == "high risk"
        )

        if previous_high:
            notes = str(
                latest.get("disposition_notes") or ""
            ).lower()

            plans = str(
                latest.get("plans_orders") or ""
            ).lower()

            keywords = [
                "resolved",
                "improved",
                "stable",
                "cleared",
                "follow-up",
                "monitoring",
            ]

            documented = any(
                keyword in notes or keyword in plans
                for keyword in keywords
            )

            if documented:
                return (
                    "info",
                    "Previous high-risk examination "
                    "documented and addressed.",
                )

            prev_date = _parse_date(
                previous.get("examination_date")
                or previous.get("created_at")
            )

            date_str = (
                prev_date.strftime("%b %d")
                if prev_date
                else "recently"
            )

            return (
                "warning",
                "Previous high severity recorded "
                f"({date_str} - CURB: "
                f"{prev_curb if prev_curb is not None else 'N/A'}/5). "
                "Review documented follow-up.",
            )

    return (None, None)
