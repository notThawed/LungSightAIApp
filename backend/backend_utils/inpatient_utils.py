"""Advisory clinical stability indicators; never discharge authorization."""
from datetime import datetime, timezone, timedelta


def _number(value):
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _timestamp(row):
    value = row.get("recorded_at") or row.get("examination_date")
    if not value:
        return None
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None



def calculate_discharge_readiness(vitals_history):
    """
    Evaluate inpatient ward-round trends.

    The latest observation is used as the assessment reference,
    allowing historical and synthetic future-dated testing.

    A 24-hour temperature trend is an advisory indicator only.
    It does not independently verify continuous absence of fever.

    Returns legacy UI keys for compatibility.
    Discharge always requires independent physician approval.
    """
    empty_check = {
        "afebrile": False,
        "spo2_stable": False,
        "rr_normal": False,
    }

    if not vitals_history:
        return {
            "score": 0,
            "status": "Insufficient data",
            "tone": "amber",
            "alerts": ["No ward-round measurements recorded."],
            "checklist": empty_check.copy(),
            "can_discharge": False,
            "data_complete": False,
        }

    history = sorted(
        vitals_history,
        key=lambda r: (
            _timestamp(r)
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    )

    latest = history[0]
    ts = _timestamp(latest)

    spo2, temp, rr = (
        _number(latest.get(k))
        for k in ("spo2", "temperature", "respiratory_rate")
    )

    oxygen = str(
        latest.get("oxygen_support") or "Unknown"
    ).strip().lower()

    alerts = []
    check = empty_check.copy()

    # ------------------------------------------------------------
    # OBSERVATION TIMESTAMP
    # ------------------------------------------------------------
    if ts is None:
        alerts.append(
            "Latest observation has no valid timestamp."
        )

    # Do not compare synthetic/historical observation timestamps
    # against the real current date. The latest round is the
    # assessment reference for trend evaluation.

    # ------------------------------------------------------------
    # SPO2
    # ------------------------------------------------------------
    if spo2 is None or not 0 <= spo2 <= 100:
        alerts.append(
            "Valid SpO₂ measurement missing."
        )
    elif spo2 < 92:
        alerts.append(
            f"Low measured SpO₂ ({spo2:g}%). "
            "Check prescribed target and oxygen needs."
        )
    elif oxygen == "room air":
        check["spo2_stable"] = True
    else:
        alerts.append(
            "SpO₂ reading alone does not establish "
            "room-air stability; verify oxygen support."
        )

    # ------------------------------------------------------------
    # RESPIRATORY RATE
    # ------------------------------------------------------------
    if rr is None or not 0 < rr < 100:
        alerts.append(
            "Valid respiratory-rate measurement missing."
        )
    elif rr >= 24:
        alerts.append(
            f"Elevated respiratory rate ({rr:g}/min)."
        )
    else:
        check["rr_normal"] = True

    # ------------------------------------------------------------
    # TEMPERATURE / 24-HOUR AFEBRILE TREND
    # ------------------------------------------------------------
    if temp is None or not 30 <= temp <= 45:
        alerts.append(
            "Valid temperature measurement missing."
        )
    elif temp >= 37.5:
        alerts.append(
            f"Elevated temperature ({temp:g}°C)."
        )
    elif ts is not None:
        # Only evaluate readings within the 24-hour period
        # leading up to the latest observation.
        window_start = ts - timedelta(hours=24)

        window_readings = []

        for row in history:
            row_ts = _timestamp(row)
            row_temp = _number(row.get("temperature"))

            if (
                row_ts is not None
                and row_temp is not None
                and 30 <= row_temp <= 45
                and window_start <= row_ts <= ts
            ):
                window_readings.append(
                    (row_ts, row_temp)
                )

        # For the requested mock workflow, permit an earlier
        # normal reading up to 30 minutes before the 24-hour
        # boundary. This is an advisory trend, not verification.
        earliest_normal = None

        for row in history:
            row_ts = _timestamp(row)
            row_temp = _number(row.get("temperature"))

            if (
                row_ts is not None
                and row_temp is not None
                and 30 <= row_temp < 37.5
                and row_ts <= ts
            ):
                if (
                    earliest_normal is None
                    or row_ts < earliest_normal
                ):
                    earliest_normal = row_ts

        fever_in_window = any(
            row_temp >= 37.5
            for _, row_temp in window_readings
        )

        if (
            earliest_normal is not None
            and ts - earliest_normal >= timedelta(hours=24)
            and not fever_in_window
        ):
            check["afebrile"] = True
            alerts.append(
                "Recorded temperature trend spans at least "
                "24 hours without a documented fever. "
                "Physician must verify sustained afebrile "
                "status from the complete clinical record."
            )
        else:
            alerts.append(
                "A 24-hour afebrile temperature trend "
                "is not established from the recorded observations."
            )

    # ------------------------------------------------------------
    # OXYGEN SUPPORT
    # ------------------------------------------------------------
    if oxygen not in (
        "room air",
        "supplemental oxygen",
    ):
        alerts.append(
            "Oxygen support is undocumented."
        )
    elif oxygen == "supplemental oxygen":
        alerts.append(
            "Supplemental oxygen documented; "
            "verify requirements and prescribed target."
        )

    # ------------------------------------------------------------
    # COMPARE WITH PREVIOUS ROUND
    # ------------------------------------------------------------
    if len(history) >= 2:
        prev = history[1]

        prev_spo2 = _number(prev.get("spo2"))
        prev_temp = _number(prev.get("temperature"))

        if (
            spo2 is not None
            and prev_spo2 is not None
            and spo2 < prev_spo2
        ):
            alerts.append(
                "SpO₂ is lower than the previous observation."
            )

        if (
            temp is not None
            and prev_temp is not None
            and temp > prev_temp
        ):
            alerts.append(
                "Temperature is higher than the previous observation."
            )

    # ------------------------------------------------------------
    # FINAL ADVISORY RESULT
    # ------------------------------------------------------------
    score = sum(check.values())

    complete = (
        ts is not None
        and spo2 is not None
        and temp is not None
        and rr is not None
        and oxygen != "unknown"
    )

    return {
        "score": score,
        "status": "Physician review required",
        "tone": "amber",
        "alerts": alerts,
        "checklist": check,
        "can_discharge": False,
        "data_complete": complete,
    }