"""
Role dashboard metrics.

The same metrics (keys, labels and queries) are used by the mobile app in
mobile_app/src/lib/dashboard.ts — keep the two in sync so a clinician sees
the same numbers on web and mobile.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.supabase_client import admin_supabase


MANILA_TZ = ZoneInfo("Asia/Manila")


# ============================================================
# METRIC DEFINITIONS
# ============================================================
#
# Each metric: key, label, hint, kind, filter value.
#   kind = "exam_status"     -> examinations.status == value
#   kind = "followups_today" -> follow_ups due today (Scheduled/Rescheduled)
#   kind = "followup_status" -> follow_ups.status in value
# ============================================================

ROLE_METRICS = {
    "Radiologist": [
        ("pending_exams", "Pending examinations", "Waiting in your patient queue", "exam_status", "Pending"),
        ("xray_ready", "X-ray results to review", "AI analysis finished", "exam_status", "X-Ray Ready"),
        ("awaiting_xray", "Awaiting X-ray", "Requested, not yet imaged", "exam_status", "Awaiting X-Ray"),
        ("followups_today", "Follow-ups today", "Scheduled for today", "followups_today", None),
    ],
    "Radiologic Technologist": [
        ("awaiting_xray", "Awaiting X-ray", "In your X-ray queue", "exam_status", "Awaiting X-Ray"),
        ("xray_ready", "Sent for review", "Analyzed, awaiting physician", "exam_status", "X-Ray Ready"),
        ("pending_exams", "Pending examinations", "Not yet requested for X-ray", "exam_status", "Pending"),
        ("completed_exams", "Completed examinations", "Reviewed by a physician", "exam_status", "Completed"),
    ],
    "Staff": [
        ("followups_today", "Follow-ups today", "Scheduled for today", "followups_today", None),
        ("followups_upcoming", "Upcoming follow-ups", "Scheduled or rescheduled", "followup_status", ["Scheduled", "Rescheduled"]),
        ("followups_missed", "Missed follow-ups", "Need rescheduling", "followup_status", ["Missed"]),
        ("pending_exams", "Pending examinations", "Registered, awaiting physician", "exam_status", "Pending"),
    ],
    "Hospital Admin": [
        ("pending_exams", "Pending examinations", "Awaiting physician", "exam_status", "Pending"),
        ("awaiting_xray", "Awaiting X-ray", "Requested, not yet imaged", "exam_status", "Awaiting X-Ray"),
        ("xray_ready", "X-ray results to review", "AI analysis finished", "exam_status", "X-Ray Ready"),
        ("completed_exams", "Completed examinations", "Reviewed by a physician", "exam_status", "Completed"),
    ],
}


# ============================================================
# COUNT QUERIES
# ============================================================

def today_iso():
    """Today's date in the hospital timezone (Asia/Manila)."""
    return datetime.now(MANILA_TZ).date().isoformat()


def count_examinations(hospital_id, status):
    response = (
        admin_supabase
        .table("examinations")
        .select("examination_id, patients!inner(hospital_id)", count="exact", head=True)
        .eq("status", status)
        .eq("patients.hospital_id", hospital_id)
        .execute()
    )
    return response.count or 0


def count_follow_ups(hospital_id, statuses, follow_up_date=None):
    query = (
        admin_supabase
        .table("follow_ups")
        .select("follow_up_id, patients!inner(hospital_id)", count="exact", head=True)
        .in_("status", statuses)
        .eq("patients.hospital_id", hospital_id)
    )

    if follow_up_date:
        query = query.eq("follow_up_date", follow_up_date)

    return query.execute().count or 0


def get_dashboard_metrics(role, hospital_id):
    """
    Return [{key, label, hint, value}] for a role.

    value is None when that metric could not be loaded, so the UI can show
    an honest "unavailable" state instead of a misleading zero.
    """

    metrics = []

    for key, label, hint, kind, arg in ROLE_METRICS.get(role, []):

        try:

            if kind == "exam_status":
                value = count_examinations(hospital_id, arg)

            elif kind == "followups_today":
                value = count_follow_ups(hospital_id, ["Scheduled", "Rescheduled"], today_iso())

            else:
                value = count_follow_ups(hospital_id, arg)

        except Exception as exc:

            print(f"[dashboard] {key} failed: {exc}")
            value = None

        metrics.append({"key": key, "label": label, "hint": hint, "value": value})

    return metrics


# ============================================================
# SYSTEM ADMINISTRATOR
# ============================================================

def start_of_today_iso():
    """Midnight today in Asia/Manila, as an ISO timestamp with offset."""
    now = datetime.now(MANILA_TZ)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _count(table, column, **filters):
    query = admin_supabase.table(table).select(column, count="exact", head=True)

    for name, value in filters.items():
        if name.endswith("__gte"):
            query = query.gte(name[:-5], value)
        else:
            query = query.eq(name, value)

    return query.execute().count or 0


def get_system_metrics():
    """
    Return [{key, label, hint, value}] for the system administrator.
    value is None when a metric could not be loaded.
    """

    today = start_of_today_iso()

    definitions = [
        ("ai_today", "AI analyses today", "Chest X-rays processed",
         lambda: _count("xray_ai_results", "ai_result_id", processed_at__gte=today)),
        ("ai_positive_today", "AI-flagged positive today", "Requires physician review",
         lambda: _count("xray_ai_results", "ai_result_id", processed_at__gte=today, ai_findings="positive")),
        ("active_hospitals", "Active hospitals", "Hospitals with access",
         lambda: _count("hospitals", "hospital_id", is_active=True)),
        ("active_users", "Active users", "Across all hospitals",
         lambda: _count("user_profiles", "user_id", is_active=True)),
    ]

    metrics = []

    for key, label, hint, load in definitions:

        try:
            value = load()
        except Exception as exc:
            print(f"[dashboard] {key} failed: {exc}")
            value = None

        metrics.append({"key": key, "label": label, "hint": hint, "value": value})

    return metrics


def get_ai_daily_counts(days=14):
    """
    AI results per day for the last `days` days (Asia/Manila dates).

    Returns [{"date": "YYYY-MM-DD", "positive": n, "negative": n}], oldest
    first, including days with no analyses.
    """

    today = datetime.now(MANILA_TZ).date()
    first_day = today - timedelta(days=days - 1)
    since = datetime(first_day.year, first_day.month, first_day.day, tzinfo=MANILA_TZ)

    rows = (
        admin_supabase
        .table("xray_ai_results")
        .select("processed_at, ai_findings")
        .gte("processed_at", since.isoformat())
        .execute()
        .data
        or []
    )

    buckets = {
        (first_day + timedelta(days=offset)).isoformat(): {"positive": 0, "negative": 0}
        for offset in range(days)
    }

    for row in rows:

        try:
            moment = datetime.fromisoformat(str(row.get("processed_at")).replace("Z", "+00:00"))
        except ValueError:
            continue

        day = moment.astimezone(MANILA_TZ).date().isoformat()
        finding = str(row.get("ai_findings") or "").lower()

        if day in buckets and finding in ("positive", "negative"):
            buckets[day][finding] += 1

    return [{"date": day, **counts} for day, counts in buckets.items()]


def get_hospital_overview():
    """Hospitals with name, active flag and coordinates (for the admin map)."""

    return (
        admin_supabase
        .table("hospitals")
        .select("hospital_id, hospital_name, is_active, latitude, longitude")
        .order("hospital_name")
        .execute()
        .data
        or []
    )
