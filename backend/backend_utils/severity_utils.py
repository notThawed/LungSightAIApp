from datetime import date, datetime

# Threshold for outdated assessments (in days)
OUTDATED_THRESHOLD_DAYS = 90

def _parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except Exception:
        return None

def get_latest_severity(examinations):
    """Returns the most recent completed exam that has a valid score."""
    completed = sorted(
        [e for e in examinations if e.get("status") == "Completed"],
        key=lambda e: e.get("examination_date") or "",
        reverse=True,
    )
    for exam in completed:
        has_curb = exam.get("curb65_score") is not None
        has_manual = (exam.get("severity_status") or "Not Assessed") != "Not Assessed"
        if has_curb or has_manual:
            return exam
    return None

def get_severity_alert(examinations, latest):
    """
    Returns a tuple (level, message).
    level: 'warning' | 'info' | None
    """
    if not latest:
        return ("warning", "No severity assessment on record. Please evaluate this patient.")

    exam_date = _parse_date(latest.get("examination_date"))
    if exam_date:
        days_old = (date.today() - exam_date).days
        if days_old > OUTDATED_THRESHOLD_DAYS:
            return ("warning", f"Latest assessment is {days_old} days old. Consider re-evaluating.")

    # Check for previous high scores
    completed = sorted(
        [e for e in examinations if e.get("status") == "Completed"],
        key=lambda e: e.get("examination_date") or "",
        reverse=True,
    )
    
    if len(completed) >= 2:
        prev = completed[1]
        prev_curb = prev.get("curb65_score")
        prev_man = prev.get("severity_status")
        
        prev_high = (prev_curb is not None and prev_curb >= 3) or (prev_man == "High Risk")
        
        if prev_high:
            # Was it resolved? Check if the new exam has notes documenting resolution.
            notes = str(latest.get("disposition_notes") or "").lower()
            plans = str(latest.get("plans_orders") or "").lower()
            keywords = ["resolved", "improved", "stable", "cleared", "follow-up", "monitoring"]
            documented = any(k in notes or k in plans for k in keywords)
            
            if documented:
                return ("info", "Previous high-risk exam documented and addressed.")
            else:
                prev_date = _parse_date(prev.get("examination_date"))
                date_str = prev_date.strftime("%b %d") if prev_date else "recently"
                return ("warning", f"Previous high score recorded ({date_str} - CURB: {prev_curb}/5). Review documented follow-up.")

    return (None, None)