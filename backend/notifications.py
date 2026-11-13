"""
Notification history (email outbox) — scoped reads and manual retry.

The outbox has no client grants; Streamlit reads it through the service role,
so the scoping here is the isolation boundary:

    Hospital Admin -> rows for their own hospital's admin accounts only
    Superadmin     -> every row, plus manual retry of failed emails
    anyone else    -> AuditAccessDenied (and an auth.permission_denied event)

Recipient addresses are masked before they leave this module.
"""

import re
from datetime import datetime, timezone

from backend import audit


RESOURCE = "notifications"

STATUSES = (
    "queued", "sending", "sent", "delivered", "failed", "bounced",
    "complained", "suppressed", "skipped", "cancelled",
)

EVENT_LABELS = {
    "application.received": "Application received (receipt)",
    "application.approved": "Application approved",
    "application.rejected": "Application rejected (notice)",
    "subscription.activated": "Subscription activated",
    "subscription.renewed": "Subscription renewed",
    "subscription.expiry_reminder": "Subscription expiry reminder",
    "ops.alert": "Operations alert",
}

PAGE_SIZE_MAX = 100
MAX_ATTEMPTS_CAP = 20

_COLUMNS = (
    "email_id, created_at, updated_at, event_type, hospital_id, recipient_kind, recipient_email, "
    "status, attempts, max_attempts, sent_at, delivered_at, last_error, skip_reason, provider_message_id"
)

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def mask_email(email):
    if not email or "@" not in str(email):
        return "—"
    local, domain = str(email).split("@", 1)
    return f"{local[:1]}***@{domain}"


def _client():
    return audit._get_client()


def _public_row(row):
    message_id = row.get("provider_message_id") or ""
    return {
        "email_id": row.get("email_id"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "event_type": row.get("event_type"),
        "event_label": EVENT_LABELS.get(row.get("event_type"), row.get("event_type")),
        "hospital_id": row.get("hospital_id"),
        "recipient": mask_email(row.get("recipient_email")),
        "recipient_kind": row.get("recipient_kind"),
        "status": row.get("status"),
        "attempts": row.get("attempts"),
        "max_attempts": row.get("max_attempts"),
        "sent_at": row.get("sent_at"),
        "delivered_at": row.get("delivered_at"),
        "last_error": row.get("last_error"),
        "skip_reason": row.get("skip_reason"),
        "simulated": message_id.startswith("log-"),
    }


def _normalize(filters, scope):
    filters = filters or {}
    clean = {}

    if filters.get("status") in STATUSES:
        clean["status"] = filters["status"]

    if filters.get("event_type") in EVENT_LABELS:
        clean["event_type"] = filters["event_type"]

    for key in ("created_from", "created_before"):
        moment = filters.get(key)
        if isinstance(moment, datetime) and moment.tzinfo is not None:
            clean[key] = moment.astimezone(timezone.utc).isoformat()

    if scope["platform"]:
        hospital = filters.get("hospital_id")
        if hospital and _UUID.match(str(hospital)):
            clean["hospital_id"] = str(hospital)
    else:
        clean["scope_hospital_id"] = scope["hospital_id"]

    return clean


def _query(clean, count=None):
    query = (
        _client()
        .table("email_outbox")
        .select(_COLUMNS, count=count)
        .neq("status", "expanded")
    )

    if clean.get("scope_hospital_id"):
        query = query.eq("hospital_id", clean["scope_hospital_id"]).eq("recipient_kind", "hospital_admin")
    elif clean.get("hospital_id"):
        query = query.eq("hospital_id", clean["hospital_id"])

    if clean.get("status"):
        query = query.eq("status", clean["status"])
    if clean.get("event_type"):
        query = query.eq("event_type", clean["event_type"])
    if clean.get("created_from"):
        query = query.gte("created_at", clean["created_from"])
    if clean.get("created_before"):
        query = query.lt("created_at", clean["created_before"])

    return query.order("created_at", desc=True).order("email_id", desc=True)


def list_notifications(filters=None, page=1, page_size=25):
    scope = audit.get_viewer_scope(RESOURCE)
    clean = _normalize(filters, scope)

    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 25), 1), PAGE_SIZE_MAX)
    offset = (page - 1) * page_size

    response = _query(clean, count="exact").range(offset, offset + page_size - 1).execute()
    rows = response.data or []

    if clean.get("scope_hospital_id"):
        rows = [
            r for r in rows
            if str(r.get("hospital_id")) == clean["scope_hospital_id"] and r.get("recipient_kind") == "hospital_admin"
        ]

    return {
        "rows": [_public_row(r) for r in rows],
        "total": response.count or 0,
        "page": page,
        "page_size": page_size,
        "scope": scope,
    }


def request_retry(email_id):
    """Superadmin only: put one failed email back in the queue."""

    scope = audit.get_viewer_scope(RESOURCE)

    if not scope["platform"]:
        audit.record_event("auth.permission_denied", "denied", metadata={"resource": "notifications.retry"})
        raise audit.AuditAccessDenied("Only a System Administrator can retry emails.")

    if not email_id or not _UUID.match(str(email_id)):
        raise ValueError("Unknown email.")

    current = (
        _client()
        .table("email_outbox")
        .select("email_id, status, attempts, hospital_id, event_type")
        .eq("email_id", str(email_id))
        .limit(1)
        .execute()
        .data
        or []
    )

    if not current:
        raise ValueError("Unknown email.")

    row = current[0]

    if row.get("status") != "failed":
        raise ValueError("Only failed emails can be retried.")

    attempts = int(row.get("attempts") or 0)
    now = datetime.now(timezone.utc).isoformat()

    updated = (
        _client()
        .table("email_outbox")
        .update({
            "status": "queued",
            "next_attempt_at": now,
            "max_attempts": min(attempts + 3, MAX_ATTEMPTS_CAP),
            "last_error": None,
            "skip_reason": None,
            "updated_at": now,
        })
        .eq("email_id", str(email_id))
        .eq("status", "failed")
        .execute()
        .data
        or []
    )

    if not updated:
        raise ValueError("The email changed in the meantime; refresh and try again.")

    audit.record_event(
        "email.retry_requested",
        target_id=str(email_id),
        target_hospital_id=row.get("hospital_id"),
        metadata={"notification_event": row.get("event_type"), "attempts": attempts},
        idempotency_key=f"email.retry_requested:{email_id}:{attempts}",
    )

    return True
