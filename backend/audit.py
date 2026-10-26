"""
Audit log service — the only code that reads or writes public.audit_logs.

Writes
    record_event() is the single entry point. The actor is taken from the
    server-side Streamlit session (never from arguments), the hospital is
    resolved from the target row in the database, and metadata is filtered
    through a per-event allowlist. A failed audit write never raises into the
    business operation: it is logged server-side and surfaced to the user as a
    one-time warning.

Reads
    query_audit_logs() / export_audit_logs_csv() re-load the viewer's role and
    hospital from the database on every call. The Streamlit app uses the
    service-role client (RLS bypassed), so this scoping IS the isolation
    boundary for the page and the CSV export.
"""

import csv
import io
import json
import logging
import re
import time
from datetime import date, datetime, time as dtime, timedelta, timezone


logger = logging.getLogger("lungsight.audit")


# ============================================================
# EVENT CATALOGUE
# ============================================================

ID = "id"
STR = "str"
INT = "int"
BOOL = "bool"
FIELDS = "fields"

OUTCOMES = ("success", "failure", "denied")

# Keys any event may carry.
COMMON_METADATA = {
    "error_class": STR,
    "reason": STR,
    "cross_hospital": BOOL,
}

EVENTS = {
    # ---- auth ------------------------------------------------
    "auth.login": ("user_profile", {"role_id": INT}),
    "auth.login_failed": (None, {}),
    "auth.login_denied": ("user_profile", {}),
    "auth.logout": ("user_profile", {}),
    "auth.permission_denied": (None, {"resource": STR}),

    # ---- user ------------------------------------------------
    "user.created": ("user_profile", {"role_id": INT, "source": STR}),
    "user.updated": ("user_profile", {"changed_fields": FIELDS}),
    "user.role_changed": ("user_profile", {"old_role_id": INT, "new_role_id": INT}),
    "user.deactivated": ("user_profile", {}),
    "user.activated": ("user_profile", {}),
    "user.invite_accepted": ("user_profile", {"source": STR}),

    # ---- patient / examination -------------------------------
    "patient.created": ("patient", {}),
    "patient.updated": ("patient", {}),
    "patient.deleted": ("patient", {}),
    "examination.created": ("examination", {"patient_id": ID, "examination_type": STR}),
    "examination.updated": ("examination", {"changed_fields": FIELDS}),
    "examination.status_changed": ("examination", {"from_status": STR, "to_status": STR}),
    "examination.cancelled": ("examination", {}),
    "examination.deleted": ("examination", {}),
    "inpatient.round_logged": ("examination", {"parent_examination_id": ID}),
    "inpatient.discharged": ("examination", {}),

    # ---- x-ray / AI / review ---------------------------------
    "xray.request_created": ("xray_request", {"examination_id": ID, "priority": STR}),
    "xray.request_status_changed": ("xray_request", {"from_status": STR, "to_status": STR}),
    "xray.image_uploaded": ("xray_image", {"request_id": ID, "file_type": STR, "file_size": INT}),
    "xray.quality_checked": ("xray_image", {"quality_status": STR}),
    "xray.quality_rejected": ("xray_request", {"check": STR}),
    "xray.quality_overridden": ("xray_request", {"check": STR}),
    "ai.analysis_completed": ("ai_result", {
        "image_id": ID,
        "model_version": STR,
        "classification_model_version": STR,
    }),
    "ai.analysis_failed": ("xray_request", {"model_version": STR, "stage": STR}),
    "ai.result_corrected": ("ai_result", {"examination_id": ID}),
    "ai.training_candidate_reviewed": ("training_candidate", {"status": STR}),
    "review.completed": ("xray_review", {"request_id": ID}),
    "review.diagnosis_confirmed": ("examination", {"overrode_ai": BOOL, "ai_result_id": ID}),

    # ---- hospital / subscription -----------------------------
    "hospital_application.submitted": ("hospital_application", {"plan_id": INT, "billing_cycle": STR}),
    "hospital_application.approved": ("hospital_application", {"hospital_id": ID}),
    "hospital_application.rejected": ("hospital_application", {}),
    "hospital_application.deleted": ("hospital_application", {}),
    "hospital_application.payment_received": ("hospital_application", {"payment_id": ID}),
    "hospital.created": ("hospital", {"source": STR}),
    "hospital.updated": ("hospital", {"changed_fields": FIELDS}),
    "hospital.deactivated": ("hospital", {}),
    "hospital.reactivated": ("hospital", {}),
    "hospital.setup_completed": ("hospital", {}),
    "subscription.created": ("hospital_subscription", {"plan_id": INT, "billing_cycle": STR, "status": STR}),
    "subscription.activated": ("hospital_subscription", {"end_date": STR}),
    "subscription.cancel_requested": ("hospital_subscription", {}),
    "subscription.reactivated": ("hospital_subscription", {}),
    "subscription.downgrade_scheduled": ("hospital_subscription", {"plan_id": INT, "pending_plan_id": INT}),
    "subscription.downgrade_undone": ("hospital_subscription", {}),
    "subscription.downgraded": ("hospital_subscription", {"plan_id": INT, "previous_plan_id": INT}),
    "subscription.cancelled": ("hospital_subscription", {}),
    "subscription.renewed": ("hospital_subscription", {"payment_id": ID, "end_date": STR}),

    # ---- reports ---------------------------------------------
    "report.generated": ("report", {
        "report_type": STR,
        "period_kind": STR,
        "period_start": STR,
        "period_end": STR,
    }),
    "report.exported": ("report", {
        "report_type": STR,
        "period_kind": STR,
        "period_start": STR,
        "period_end": STR,
        "format": STR,
    }),

    # ---- export ----------------------------------------------
    "audit.exported": (None, {
        "row_count": INT,
        "scope": STR,
        "category": STR,
        "outcome": STR,
        "date_from": STR,
        "date_to": STR,
    }),
}

CATEGORIES = sorted({event.split(".", 1)[0] for event in EVENTS})

# Defence in depth: a key containing any of these fragments is dropped even
# if someone adds it to the allowlist above.
DENIED_KEY_FRAGMENTS = (
    "password", "passwd", "token", "secret", "apikey", "api_key", "credential",
    "name", "birth", "dob", "contact", "phone", "email", "address",
    "diagnos", "finding", "impression", "note", "comment", "payload",
    "signature", "image_bytes", "image_data", "raw",
)

_SAFE_STR = re.compile(r"^[A-Za-z0-9 _.:/+\-]{0,64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")
_SAFE_FIELD = re.compile(r"^[a-z_][a-z0-9_]{0,63}$")
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

MAX_FIELDS = 40


def _key_denied(key):
    lowered = key.lower()
    return any(fragment in lowered for fragment in DENIED_KEY_FRAGMENTS)


def _clean_value(kind, value):
    """Return (ok, value) for one metadata value of the given kind."""

    if value is None:
        return True, None

    if kind == BOOL:
        return isinstance(value, bool), value

    if kind == INT:
        ok = isinstance(value, int) and not isinstance(value, bool)
        return ok, value

    if kind == ID:
        value = str(value)
        return bool(_SAFE_ID.match(value)), value

    if kind == STR:
        if isinstance(value, (date, datetime)):
            value = value.isoformat()
        if not isinstance(value, str):
            return False, None
        return bool(_SAFE_STR.match(value)), value

    if kind == FIELDS:
        if not isinstance(value, (list, tuple, set)):
            return False, None
        fields = sorted({str(f) for f in value})
        ok = len(fields) <= MAX_FIELDS and all(_SAFE_FIELD.match(f) for f in fields)
        return ok, fields

    return False, None


def sanitize_metadata(event_type, metadata):
    """
    Keep only allowlisted, well-typed keys for this event.

    Returns (clean_metadata, dropped_keys).
    """

    allowed = dict(COMMON_METADATA)
    allowed.update(EVENTS[event_type][1])

    clean = {}
    dropped = []

    for key, value in (metadata or {}).items():

        key = str(key)
        kind = allowed.get(key)

        if kind is None or _key_denied(key):
            dropped.append(key)
            continue

        ok, value = _clean_value(kind, value)

        if not ok:
            dropped.append(key)
            continue

        if value is not None:
            clean[key] = value

    return clean, dropped


# ============================================================
# DATABASE CLIENT
# ============================================================

def _get_client():
    from backend.supabase_client import admin_supabase

    return admin_supabase


# ============================================================
# TRUSTED CONTEXT
# ============================================================

def _streamlit_session():
    """Return st.session_state when running inside a Streamlit script, else None."""

    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        if get_script_run_ctx(suppress_warning=True) is None:
            return None

        import streamlit as st

        return st.session_state

    except Exception:
        return None


def streamlit_session_id():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        ctx = get_script_run_ctx(suppress_warning=True)
        return ctx.session_id if ctx else None

    except Exception:
        return None


def _session_user_id():
    """
    The signed-in user's id. st.session_state lives on the server and is only
    set by login_user() after Supabase verified the password.
    """

    session = _streamlit_session()

    if session is None or not session.get("logged_in"):
        return None

    user = session.get("user") or {}
    user_id = user.get("user_id")

    return str(user_id) if user_id else None


_PROFILE_CACHE = {}
_PROFILE_TTL_SECONDS = 60


def load_profile(user_id, fresh=False):
    """Role, hospital and active flag for a user, read from the database."""

    if not user_id:
        return None

    cached = _PROFILE_CACHE.get(user_id)

    if cached and not fresh and time.monotonic() - cached[0] < _PROFILE_TTL_SECONDS:
        return cached[1]

    response = (
        _get_client()
        .table("user_profiles")
        .select("user_id, hospital_id, is_active, role_id, roles(role_name)")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    rows = response.data or []
    profile = None

    if rows:
        row = rows[0]
        role = row.get("roles") or {}
        if isinstance(role, list):
            role = role[0] if role else {}
        profile = {
            "user_id": str(row.get("user_id")),
            "hospital_id": row.get("hospital_id"),
            "is_active": bool(row.get("is_active")),
            "role_id": row.get("role_id"),
            "role": role.get("role_name"),
        }

    _PROFILE_CACHE[user_id] = (time.monotonic(), profile)

    return profile


# target_type -> (table, primary key, select, path to hospital_id)
_HOSPITAL_LOOKUPS = {
    "hospital": None,
    "patient": ("patients", "patient_id", "hospital_id", ["hospital_id"]),
    "examination": ("examinations", "examination_id", "patients(hospital_id)", ["patients", "hospital_id"]),
    "xray_request": ("xray_requests", "request_id", "hospital_id", ["hospital_id"]),
    "xray_image": ("xray_images", "image_id", "xray_requests(hospital_id)", ["xray_requests", "hospital_id"]),
    "ai_result": (
        "xray_ai_results", "ai_result_id",
        "xray_images(xray_requests(hospital_id))",
        ["xray_images", "xray_requests", "hospital_id"],
    ),
    "xray_review": ("xray_reviews", "review_id", "xray_requests(hospital_id)", ["xray_requests", "hospital_id"]),
    "training_candidate": (
        "xray_training_candidates", "candidate_id", "patients(hospital_id)", ["patients", "hospital_id"],
    ),
    "user_profile": ("user_profiles", "user_id", "hospital_id", ["hospital_id"]),
    "hospital_subscription": ("hospital_subscriptions", "hospital_subscription_id", "hospital_id", ["hospital_id"]),
    "hospital_application": ("hospital_applications", "application_id", "hospital_id", ["hospital_id"]),
}


def _dig(value, path):
    for key in path:
        if isinstance(value, list):
            value = value[0] if value else None
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def resolve_target_hospital(target_type, target_id):
    """Look up which hospital a target row belongs to. None when unknown."""

    if not target_type or not target_id:
        return None

    if target_type == "hospital":
        return str(target_id)

    lookup = _HOSPITAL_LOOKUPS.get(target_type)

    if not lookup:
        return None

    table, pk, select, path = lookup

    try:
        response = (
            _get_client()
            .table(table)
            .select(select)
            .eq(pk, target_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        value = _dig(rows[0], path) if rows else None
        return str(value) if value else None

    except Exception as exc:
        logger.warning("audit hospital lookup failed for %s: %s", target_type, type(exc).__name__)
        return None


# ============================================================
# FAILURE SURFACING
# ============================================================

_WARNING_KEY = "_audit_write_failures"


def _note_failure():
    session = _streamlit_session()

    if session is not None:
        session[_WARNING_KEY] = session.get(_WARNING_KEY, 0) + 1


def flush_audit_warnings():
    """Show a one-time toast if audit writes failed since the last render."""

    session = _streamlit_session()

    if session is None or not session.get(_WARNING_KEY):
        return

    session[_WARNING_KEY] = 0

    try:
        import streamlit as st

        st.toast(
            "An audit record could not be saved. "
            "The action itself was completed.",
            icon=":material/warning:",
        )

    except Exception:
        pass


# ============================================================
# WRITE
# ============================================================

_SYSTEM = object()


def record_event(
    event_type,
    outcome="success",
    *,
    target_id=None,
    metadata=None,
    idempotency_key=None,
    target_hospital_id=None,
    verified_actor_id=None,
    system=False,
):
    """
    Append one audit event. Returns True when the event is stored (or was
    already stored under the same idempotency key), False otherwise. Never
    raises.

    target_hospital_id
        Only for targets that no longer exist (deletes), pre-read from the
        database by the caller. Otherwise the hospital is looked up from the
        target row.
    verified_actor_id
        Only for flows where Supabase Auth has just verified the user in this
        request (sign-in, invite acceptance) and no session user exists yet.
    system
        The event is not the signed-in user's action (scheduled changes).
    """

    try:

        if event_type not in EVENTS:
            logger.error("audit: unknown event type %r rejected", event_type)
            return False

        if outcome not in OUTCOMES:
            logger.error("audit: invalid outcome %r for %s", outcome, event_type)
            return False

        target_type = EVENTS[event_type][0]

        clean, dropped = sanitize_metadata(event_type, metadata)

        if dropped:
            logger.warning("audit: dropped metadata keys %s for %s", sorted(dropped), event_type)

        if system:
            actor_id = None
        else:
            actor_id = _session_user_id() or (
                str(verified_actor_id) if verified_actor_id else None
            )

        actor_profile = None

        if actor_id:
            try:
                actor_profile = load_profile(actor_id)
            except Exception as exc:
                logger.warning("audit actor lookup failed: %s", type(exc).__name__)

        hospital_id = target_hospital_id or resolve_target_hospital(target_type, target_id)

        if hospital_id is None and actor_profile:
            hospital_id = actor_profile.get("hospital_id")

        if (
            actor_profile
            and actor_profile.get("role") != "Superadmin"
            and actor_profile.get("hospital_id")
            and hospital_id
            and str(actor_profile["hospital_id"]) != str(hospital_id)
        ):
            clean["cross_hospital"] = True

        row = {
            "actor_user_id": actor_id,
            "hospital_id": str(hospital_id) if hospital_id else None,
            "event_type": event_type,
            "target_type": target_type if target_id else None,
            "target_id": str(target_id)[:128] if target_id else None,
            "outcome": outcome,
            "metadata": clean,
            "idempotency_key": idempotency_key[:200] if idempotency_key else None,
        }

        _get_client().table("audit_logs").insert(row).execute()

        return True

    except Exception as exc:

        if _is_duplicate(exc):
            return True

        logger.error("audit write failed for %s: %s", event_type, type(exc).__name__)
        _note_failure()

        return False


def _is_duplicate(exc):
    code = getattr(exc, "code", None)

    if code is None and exc.args and isinstance(exc.args[0], dict):
        code = exc.args[0].get("code")

    return str(code) == "23505"


def error_class(exc):
    return type(exc).__name__


def record_login_once(user):
    """auth.login guarded against Streamlit reruns and duplicate submits."""

    session = _streamlit_session()
    user_id = (user or {}).get("user_id")

    if not user_id:
        return False

    if session is not None and session.get(_LOGIN_FLAG) == user_id:
        return True

    session_id = streamlit_session_id() or "nosession"
    sequence = session.get(_LOGIN_SEQ, 0) if session is not None else 0

    stored = record_event(
        "auth.login",
        target_id=user_id,
        metadata={"role_id": user.get("role_id")},
        idempotency_key=f"auth.login:{user_id}:{session_id}:{sequence}",
        verified_actor_id=user_id,
    )

    if stored and session is not None:
        session[_LOGIN_FLAG] = user_id

    return stored


_LOGIN_FLAG = "_audit_login_recorded"
_LOGIN_SEQ = "_audit_login_seq"


def record_logout():
    """auth.logout for the current session user; call before clearing the session."""

    user_id = _session_user_id()

    session = _streamlit_session()

    if session is not None:
        session.pop(_LOGIN_FLAG, None)
        session[_LOGIN_SEQ] = session.get(_LOGIN_SEQ, 0) + 1

    if not user_id:
        return False

    return record_event("auth.logout", target_id=user_id)


# ============================================================
# READ
# ============================================================

class AuditAccessDenied(Exception):
    pass


PAGE_SIZE_MAX = 100
EXPORT_ROW_LIMIT = 10_000
EXPORT_BATCH = 1_000

_SEARCH = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")


def get_viewer_scope(resource="audit_logs"):
    """
    The admin scope of the signed-in user, derived from the database.

    Returns {"user_id", "role", "hospital_id", "platform"}; raises
    AuditAccessDenied for anyone who is not an active Hospital Admin (with a
    hospital) or Superadmin.
    """

    user_id = _session_user_id()

    if not user_id:
        raise AuditAccessDenied("Not signed in.")

    profile = load_profile(user_id, fresh=True)

    if profile and profile.get("is_active"):

        if profile.get("role") == "Superadmin":
            return {"user_id": user_id, "role": "Superadmin", "hospital_id": None, "platform": True}

        if profile.get("role") == "Hospital Admin" and profile.get("hospital_id"):
            return {
                "user_id": user_id,
                "role": "Hospital Admin",
                "hospital_id": str(profile["hospital_id"]),
                "platform": False,
            }

    record_event(
        "auth.permission_denied",
        "denied",
        metadata={"resource": resource},
    )

    raise AuditAccessDenied(
        "You do not have access to audit logs."
        if resource == "audit_logs"
        else "You do not have access to this page."
    )


def _normalize_filters(filters, scope):
    """Validate client-supplied filters; hospital scope is never taken from them."""

    filters = filters or {}
    clean = {}

    date_from = filters.get("date_from")
    date_to = filters.get("date_to")

    if isinstance(date_from, date):
        clean["date_from"] = date_from
    if isinstance(date_to, date):
        clean["date_to"] = date_to

    for key in ("created_from", "created_before"):
        moment = filters.get(key)
        if isinstance(moment, datetime) and moment.tzinfo is not None:
            clean[key] = moment

    if filters.get("category") in CATEGORIES:
        clean["category"] = filters["category"]

    if filters.get("outcome") in OUTCOMES:
        clean["outcome"] = filters["outcome"]

    actor = filters.get("actor_user_id")
    if actor and _UUID.match(str(actor)):
        clean["actor_user_id"] = str(actor)

    search = (filters.get("search") or "").strip()
    if search:
        if not _SEARCH.match(search):
            raise ValueError("Search may only contain letters, numbers, '.', '_' and '-'.")
        clean["search"] = search

    if scope["platform"]:
        hospital = filters.get("hospital_id")
        if hospital == "platform":
            clean["hospital_id"] = "platform"
        elif hospital and _UUID.match(str(hospital)):
            clean["hospital_id"] = str(hospital)
        clean["scope_hospital_id"] = None
    else:
        clean["scope_hospital_id"] = scope["hospital_id"]

    return clean


def _build_query(filters, count=None, columns="*"):
    query = _get_client().table("audit_logs").select(columns, count=count)

    scope_hospital = filters.get("scope_hospital_id")

    if scope_hospital:
        query = query.eq("hospital_id", scope_hospital)
    elif filters.get("hospital_id") == "platform":
        query = query.is_("hospital_id", "null")
    elif filters.get("hospital_id"):
        query = query.eq("hospital_id", filters["hospital_id"])

    if filters.get("date_from"):
        start = datetime.combine(filters["date_from"], dtime.min, tzinfo=timezone.utc)
        query = query.gte("created_at", start.isoformat())

    if filters.get("date_to"):
        end = datetime.combine(filters["date_to"] + timedelta(days=1), dtime.min, tzinfo=timezone.utc)
        query = query.lt("created_at", end.isoformat())

    if filters.get("created_from"):
        query = query.gte("created_at", filters["created_from"].astimezone(timezone.utc).isoformat())

    if filters.get("created_before"):
        query = query.lt("created_at", filters["created_before"].astimezone(timezone.utc).isoformat())

    if filters.get("category"):
        query = query.eq("event_category", filters["category"])

    if filters.get("outcome"):
        query = query.eq("outcome", filters["outcome"])

    if filters.get("actor_user_id"):
        query = query.eq("actor_user_id", filters["actor_user_id"])

    if filters.get("search"):
        term = filters["search"]
        query = query.or_(f"event_type.ilike.*{term}*,target_id.eq.{term}")

    return query.order("created_at", desc=True).order("audit_log_id", desc=True)


def _enforce_scope(rows, filters):
    """Belt and braces: drop any row outside the viewer's hospital."""

    scope_hospital = filters.get("scope_hospital_id")

    if not scope_hospital:
        return rows

    return [row for row in rows if str(row.get("hospital_id")) == scope_hospital]


def query_audit_logs(filters=None, page=1, page_size=25):
    """One page of audit rows, newest first, within the viewer's scope."""

    scope = get_viewer_scope()
    clean = _normalize_filters(filters, scope)

    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 25), 1), PAGE_SIZE_MAX)
    offset = (page - 1) * page_size

    response = _build_query(clean, count="exact").range(offset, offset + page_size - 1).execute()

    rows = _enforce_scope(response.data or [], clean)

    return {
        "rows": rows,
        "total": response.count or 0,
        "page": page,
        "page_size": page_size,
        "scope": scope,
    }


AGGREGATE_ROW_LIMIT = 50_000


def fetch_scoped_event_rows(filters=None, resource="audit_logs"):
    """
    event_type / outcome / created_at of every row matching the filters, within
    the viewer's scope (same scope as the page and CSV export). Used for
    aggregate reports. Raises ValueError past AGGREGATE_ROW_LIMIT.
    """

    scope = get_viewer_scope(resource)
    clean = _normalize_filters(filters, scope)

    rows = []
    offset = 0

    while True:
        batch = (
            _build_query(clean, columns="event_type, outcome, created_at, hospital_id")
            .range(offset, offset + EXPORT_BATCH - 1)
            .execute()
            .data
            or []
        )
        rows.extend(_enforce_scope(batch, clean))
        if len(batch) < EXPORT_BATCH:
            break
        offset += EXPORT_BATCH
        if len(rows) > AGGREGATE_ROW_LIMIT:
            raise ValueError("Too many audit events in this period; choose a shorter period.")

    return rows


_CSV_COLUMNS = [
    "created_at", "event_type", "outcome", "actor_user_id", "actor_name",
    "hospital_id", "target_type", "target_id", "metadata",
]


def _csv_safe(value):
    if value is None:
        return ""

    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)

    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        text = "'" + text

    return text


def get_actor_names(actor_ids):
    """Display names for staff ids that appear in already-scoped rows."""

    ids = sorted({str(a) for a in actor_ids if a})

    if not ids:
        return {}

    response = (
        _get_client()
        .table("user_profiles")
        .select("user_id, user_fname, user_lname")
        .in_("user_id", ids)
        .execute()
    )

    names = {}

    for row in response.data or []:
        name = " ".join(p for p in [row.get("user_fname"), row.get("user_lname")] if p).strip()
        names[str(row["user_id"])] = name or "User"

    return names


def export_audit_logs_csv(filters=None):
    """
    CSV of every row matching the filters (up to EXPORT_ROW_LIMIT), using the
    same scope as the page. Returns (csv_bytes, row_count, truncated).
    """

    scope = get_viewer_scope()
    clean = _normalize_filters(filters, scope)

    rows = []
    offset = 0

    while len(rows) <= EXPORT_ROW_LIMIT:
        batch = (
            _build_query(clean)
            .range(offset, offset + EXPORT_BATCH - 1)
            .execute()
            .data
            or []
        )
        rows.extend(_enforce_scope(batch, clean))
        if len(batch) < EXPORT_BATCH:
            break
        offset += EXPORT_BATCH

    truncated = len(rows) > EXPORT_ROW_LIMIT
    rows = rows[:EXPORT_ROW_LIMIT]

    names = get_actor_names(row.get("actor_user_id") for row in rows)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_CSV_COLUMNS)

    for row in rows:
        actor = row.get("actor_user_id")
        writer.writerow([
            _csv_safe(row.get("created_at")),
            _csv_safe(row.get("event_type")),
            _csv_safe(row.get("outcome")),
            _csv_safe(actor),
            _csv_safe(names.get(str(actor), "System") if actor else "System"),
            _csv_safe(row.get("hospital_id")),
            _csv_safe(row.get("target_type")),
            _csv_safe(row.get("target_id")),
            _csv_safe(row.get("metadata") or {}),
        ])

    record_event(
        "audit.exported",
        metadata={
            "row_count": len(rows),
            "scope": "platform" if scope["platform"] else "hospital",
            "category": clean.get("category"),
            "outcome": clean.get("outcome"),
            "date_from": clean.get("date_from"),
            "date_to": clean.get("date_to"),
        },
    )

    return buffer.getvalue().encode("utf-8"), len(rows), truncated
