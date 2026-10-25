"""
Unit tests for backend/audit.py against an in-memory fake of the Supabase
query builder. No network, no Streamlit runtime.
"""

import csv
import io
import itertools
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from backend import audit


HOSP_A = "aaaaaaaa-0000-0000-0000-000000000001"
HOSP_B = "bbbbbbbb-0000-0000-0000-000000000002"
ADMIN_A = "00000000-0000-0000-0000-00000000000a"
ADMIN_B = "00000000-0000-0000-0000-00000000000b"
RAD_A = "00000000-0000-0000-0000-0000000000ca"
SUPER = "00000000-0000-0000-0000-0000000000ff"
INACTIVE_A = "00000000-0000-0000-0000-0000000000ee"
PATIENT_A = "11111111-0000-0000-0000-00000000000a"
PATIENT_B = "11111111-0000-0000-0000-00000000000b"


# ============================================================
# FAKE SUPABASE
# ============================================================

class FakeAPIError(Exception):
    def __init__(self, code, message=""):
        super().__init__({"code": code, "message": message})
        self.code = code


class Result:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class Query:
    def __init__(self, db, table):
        self.db = db
        self.table = table
        self.filters = []
        self.ops = None
        self.payload = None
        self.count = None
        self.order_keys = []
        self.range_ = None
        self.limit_ = None

    # ---- builders ----
    def select(self, *_cols, count=None):
        self.ops = "select"
        self.count = count
        return self

    def insert(self, payload):
        self.ops = "insert"
        self.payload = payload
        return self

    def eq(self, col, val):
        self.filters.append(lambda r: str(r.get(col)) == str(val))
        return self

    def is_(self, col, val):
        assert val == "null"
        self.filters.append(lambda r: r.get(col) is None)
        return self

    def in_(self, col, vals):
        vals = {str(v) for v in vals}
        self.filters.append(lambda r: str(r.get(col)) in vals)
        return self

    def gte(self, col, val):
        self.filters.append(lambda r: r.get(col) >= val)
        return self

    def lt(self, col, val):
        self.filters.append(lambda r: r.get(col) < val)
        return self

    def or_(self, expr):
        self.db.or_exprs.append(expr)
        clauses = []
        for part in expr.split(","):
            col, op, val = part.split(".", 2)
            clauses.append((col, op, val))

        def match(r):
            for col, op, val in clauses:
                value = str(r.get(col) or "")
                if op == "eq" and value == val:
                    return True
                if op == "ilike" and val.strip("*").lower() in value.lower():
                    return True
            return False

        self.filters.append(match)
        return self

    def order(self, col, desc=False):
        self.order_keys.append((col, desc))
        return self

    def range(self, start, end):
        self.range_ = (start, end)
        return self

    def limit(self, n):
        self.limit_ = n
        return self

    # ---- execution ----
    def execute(self):
        if self.db.fail_tables and self.table in self.db.fail_tables:
            raise RuntimeError("simulated outage")

        rows = self.db.tables.setdefault(self.table, [])

        if self.ops == "insert":
            row = dict(self.payload)
            key = row.get("idempotency_key")
            if key and any(r.get("idempotency_key") == key for r in rows):
                raise FakeAPIError("23505", "duplicate key")
            row.setdefault("audit_log_id", str(uuid.uuid4()))
            row.setdefault("created_at", self.db.next_time())
            if self.table == "audit_logs":
                row["event_category"] = row["event_type"].split(".", 1)[0]
            rows.append(row)
            return Result([row])

        matched = [r for r in rows if all(f(r) for f in self.filters)]

        for col, desc in reversed(self.order_keys):
            matched.sort(key=lambda r: str(r.get(col)), reverse=desc)

        total = len(matched)

        if self.range_:
            matched = matched[self.range_[0]: self.range_[1] + 1]
        if self.limit_:
            matched = matched[: self.limit_]

        return Result([dict(r) for r in matched], total if self.count else None)


class FakeDB:
    def __init__(self):
        self.tables = {}
        self.fail_tables = set()
        self.or_exprs = []
        self._clock = itertools.count()

    def next_time(self):
        base = datetime(2026, 10, 1, tzinfo=timezone.utc)
        return (base + timedelta(minutes=next(self._clock))).isoformat()

    def table(self, name):
        return Query(self, name)

    @property
    def audit_rows(self):
        return self.tables.get("audit_logs", [])


def build_fake_db():
    fake = FakeDB()

    def profile(user_id, role, hospital, active=True):
        return {
            "user_id": user_id,
            "hospital_id": hospital,
            "is_active": active,
            "role_id": {"Superadmin": 1, "Radiologist": 3, "Hospital Admin": 6}[role],
            "roles": {"role_name": role},
            "user_fname": role.split()[0],
            "user_lname": user_id[-2:],
        }

    fake.tables["user_profiles"] = [
        profile(ADMIN_A, "Hospital Admin", HOSP_A),
        profile(ADMIN_B, "Hospital Admin", HOSP_B),
        profile(RAD_A, "Radiologist", HOSP_A),
        profile(SUPER, "Superadmin", None),
        profile(INACTIVE_A, "Hospital Admin", HOSP_A, active=False),
    ]
    fake.tables["patients"] = [
        {"patient_id": PATIENT_A, "hospital_id": HOSP_A},
        {"patient_id": PATIENT_B, "hospital_id": HOSP_B},
    ]

    return fake


@pytest.fixture
def db(monkeypatch):
    fake = build_fake_db()
    monkeypatch.setattr(audit, "_get_client", lambda: fake)
    audit._PROFILE_CACHE.clear()
    return fake


@pytest.fixture
def session(monkeypatch):
    state = {}
    monkeypatch.setattr(audit, "_streamlit_session", lambda: state)
    monkeypatch.setattr(audit, "streamlit_session_id", lambda: "sess-1")
    return state


def sign_in(session, user_id, **overrides):
    session["logged_in"] = True
    session["user"] = {"user_id": user_id, **overrides}


# ============================================================
# WRITES
# ============================================================

def test_success_event_has_trusted_actor_hospital_type_target_outcome(db, session):
    sign_in(session, RAD_A)

    assert audit.record_event("patient.created", target_id=PATIENT_A)

    row = db.audit_rows[-1]
    assert row["actor_user_id"] == RAD_A
    assert row["hospital_id"] == HOSP_A
    assert row["event_type"] == "patient.created"
    assert row["target_type"] == "patient"
    assert row["target_id"] == PATIENT_A
    assert row["outcome"] == "success"
    assert "cross_hospital" not in row["metadata"]
    assert datetime.fromisoformat(row["created_at"]).tzinfo is not None


def test_failure_event_records_error_class(db, session):
    sign_in(session, RAD_A)

    audit.record_event(
        "examination.created",
        "failure",
        metadata={"error_class": "APIError", "patient_id": PATIENT_A},
    )

    row = db.audit_rows[-1]
    assert row["outcome"] == "failure"
    assert row["metadata"] == {"error_class": "APIError", "patient_id": PATIENT_A}
    assert row["hospital_id"] == HOSP_A  # falls back to the actor's DB hospital


def test_session_user_wins_over_verified_actor_argument(db, session):
    sign_in(session, RAD_A)

    audit.record_event("patient.updated", target_id=PATIENT_A, verified_actor_id=SUPER)

    assert db.audit_rows[-1]["actor_user_id"] == RAD_A


def test_session_hospital_value_is_not_trusted(db, session):
    sign_in(session, RAD_A, hospital_id=HOSP_B, role="Superadmin")

    audit.record_event("examination.created", "failure")

    assert db.audit_rows[-1]["hospital_id"] == HOSP_A


def test_cross_hospital_access_is_flagged(db, session):
    sign_in(session, RAD_A)

    audit.record_event("patient.updated", target_id=PATIENT_B)

    row = db.audit_rows[-1]
    assert row["hospital_id"] == HOSP_B
    assert row["metadata"]["cross_hospital"] is True


def test_system_event_has_null_actor(db, session):
    sign_in(session, ADMIN_A)

    assert audit.record_event(
        "subscription.cancelled",
        target_hospital_id=HOSP_A,
        idempotency_key="subscription.cancelled:s1:2026-10-01",
        system=True,
    )

    row = db.audit_rows[-1]
    assert row["actor_user_id"] is None
    assert row["hospital_id"] == HOSP_A


def test_public_event_outside_streamlit_has_null_actor_and_hospital(db, monkeypatch):
    monkeypatch.setattr(audit, "_streamlit_session", lambda: None)

    assert audit.record_event("auth.login_failed", "failure", metadata={"reason": "invalid_credentials"})

    row = db.audit_rows[-1]
    assert row["actor_user_id"] is None
    assert row["hospital_id"] is None


def test_retry_with_same_idempotency_key_does_not_duplicate(db, session):
    for _ in range(3):
        assert audit.record_event(
            "subscription.downgraded",
            target_hospital_id=HOSP_A,
            idempotency_key="subscription.downgraded:s1:2026-10-01",
            system=True,
        )

    assert len(db.audit_rows) == 1


def test_login_is_recorded_once_per_login_across_reruns(db, session):
    user = {"user_id": ADMIN_A, "role_id": 6}
    sign_in(session, ADMIN_A, role_id=6)

    for _ in range(3):
        audit.record_login_once(user)

    assert [r["event_type"] for r in db.audit_rows] == ["auth.login"]

    audit.record_logout()
    sign_in(session, ADMIN_A, role_id=6)
    audit.record_login_once(user)

    assert [r["event_type"] for r in db.audit_rows] == ["auth.login", "auth.logout", "auth.login"]


def test_unknown_event_and_outcome_rejected(db, session):
    assert audit.record_event("patient.exported") is False
    assert audit.record_event("patient.created", "maybe") is False
    assert db.audit_rows == []


def test_write_failure_does_not_raise_and_queues_warning(db, session):
    sign_in(session, ADMIN_A)
    db.fail_tables.add("audit_logs")

    assert audit.record_event("user.deactivated", target_id=RAD_A) is False
    assert session[audit._WARNING_KEY] == 1


def test_duplicate_detection_handles_dict_payload_errors():
    assert audit._is_duplicate(FakeAPIError("23505"))
    assert audit._is_duplicate(Exception({"code": "23505"}))
    assert not audit._is_duplicate(RuntimeError("boom"))


# ============================================================
# METADATA ALLOWLIST
# ============================================================

@pytest.mark.parametrize("key", [
    "password", "access_token", "refresh_token", "api_key", "service_secret",
    "first_name", "patient_name", "date_of_birth", "dob", "contact_number",
    "phone", "email", "address", "diagnosis", "findings", "impression",
    "doctor_notes", "raw_payload", "image_bytes",
])
def test_phi_and_secret_keys_dropped_even_if_allowlisted(monkeypatch, key):
    monkeypatch.setitem(audit.EVENTS, "patient.created", ("patient", {key: audit.STR}))

    clean, dropped = audit.sanitize_metadata("patient.created", {key: "x"})

    assert clean == {}
    assert dropped == [key]


def test_unknown_keys_and_unsafe_values_dropped():
    clean, dropped = audit.sanitize_metadata(
        "examination.status_changed",
        {
            "from_status": "Pending",
            "to_status": "X-Ray Ready",
            "free_text": "Patient complains of cough",
            "reason": "line1\nline2",
        },
    )

    assert clean == {"from_status": "Pending", "to_status": "X-Ray Ready"}
    assert sorted(dropped) == ["free_text", "reason"]


def test_value_types_enforced():
    clean, dropped = audit.sanitize_metadata(
        "user.role_changed",
        {"old_role_id": "3", "new_role_id": 6, "cross_hospital": "yes"},
    )

    assert clean == {"new_role_id": 6}
    assert sorted(dropped) == ["cross_hospital", "old_role_id"]


def test_changed_fields_are_names_only():
    clean, _ = audit.sanitize_metadata("examination.updated", {"changed_fields": ["status", "diagnosis"]})
    assert clean == {"changed_fields": ["diagnosis", "status"]}

    clean, dropped = audit.sanitize_metadata("examination.updated", {"changed_fields": ["Pneumonia, severe"]})
    assert clean == {} and dropped == ["changed_fields"]


def test_catalogue_keys_do_not_trip_denylist():
    for event, (_target, keys) in audit.EVENTS.items():
        for key in list(keys) + list(audit.COMMON_METADATA):
            assert not audit._key_denied(key), (event, key)


def test_metadata_stored_is_sanitized(db, session):
    sign_in(session, RAD_A)

    audit.record_event(
        "ai.analysis_completed",
        target_id="r1",
        metadata={
            "model_version": "pneumonia_resnet50_v1",
            "ai_findings": "positive",
            "ai_confidence": 0.97,
        },
    )

    assert db.audit_rows[-1]["metadata"] == {"model_version": "pneumonia_resnet50_v1"}


# ============================================================
# READ SCOPE
# ============================================================

def seed_logs(db):
    rows = [
        (HOSP_A, ADMIN_A, "user.created", "success"),
        (HOSP_A, RAD_A, "patient.created", "success"),
        (HOSP_A, RAD_A, "ai.analysis_failed", "failure"),
        (HOSP_B, ADMIN_B, "patient.created", "success"),
        (None, None, "auth.login_failed", "failure"),
    ]
    for hospital, actor, event, outcome in rows:
        db.table("audit_logs").insert({
            "hospital_id": hospital,
            "actor_user_id": actor,
            "event_type": event,
            "target_type": None,
            "target_id": "=HYPERLINK(\"x\")" if event == "ai.analysis_failed" else "t-1",
            "outcome": outcome,
            "metadata": {},
            "idempotency_key": None,
        }).execute()


def visible_hospitals(result):
    return {r["hospital_id"] for r in result["rows"]}


def test_hospital_admin_sees_only_own_hospital(db, session):
    seed_logs(db)
    sign_in(session, ADMIN_A)

    result = audit.query_audit_logs({})

    assert visible_hospitals(result) == {HOSP_A}
    assert result["total"] == 3


def test_hospital_admin_cannot_tamper_with_hospital_filter(db, session):
    seed_logs(db)
    sign_in(session, ADMIN_A)

    for tampered in (HOSP_B, "platform", None):
        result = audit.query_audit_logs({"hospital_id": tampered})
        assert visible_hospitals(result) == {HOSP_A}


def test_hospital_admin_cannot_escalate_via_session_state(db, session):
    seed_logs(db)
    sign_in(session, ADMIN_A, role="Superadmin", hospital_id=HOSP_B)

    result = audit.query_audit_logs({"hospital_id": HOSP_B})

    assert visible_hospitals(result) == {HOSP_A}
    assert result["scope"]["platform"] is False


def test_hospital_b_admin_isolated_from_a(db, session):
    seed_logs(db)
    sign_in(session, ADMIN_B)

    assert visible_hospitals(audit.query_audit_logs({})) == {HOSP_B}


def test_superadmin_sees_platform_and_can_filter(db, session):
    seed_logs(db)
    sign_in(session, SUPER)

    assert audit.query_audit_logs({})["total"] == 5
    assert visible_hospitals(audit.query_audit_logs({"hospital_id": HOSP_B})) == {HOSP_B}
    assert visible_hospitals(audit.query_audit_logs({"hospital_id": "platform"})) == {None}


@pytest.mark.parametrize("user_id", [RAD_A, INACTIVE_A, "99999999-9999-9999-9999-999999999999"])
def test_non_admins_are_denied_and_attempt_is_logged(db, session, user_id):
    seed_logs(db)
    sign_in(session, user_id)
    before = len(db.audit_rows)

    with pytest.raises(audit.AuditAccessDenied):
        audit.query_audit_logs({})

    with pytest.raises(audit.AuditAccessDenied):
        audit.export_audit_logs_csv({})

    denied = db.audit_rows[before:]
    assert [r["event_type"] for r in denied] == ["auth.permission_denied"] * 2
    assert all(r["outcome"] == "denied" for r in denied)


def test_signed_out_is_denied(db, session):
    with pytest.raises(audit.AuditAccessDenied):
        audit.query_audit_logs({})


def test_filters_category_outcome_actor_and_dates(db, session):
    seed_logs(db)
    sign_in(session, ADMIN_A)

    assert {r["event_type"] for r in audit.query_audit_logs({"category": "patient"})["rows"]} == {"patient.created"}
    assert {r["outcome"] for r in audit.query_audit_logs({"outcome": "failure"})["rows"]} == {"failure"}
    assert {r["actor_user_id"] for r in audit.query_audit_logs({"actor_user_id": RAD_A})["rows"]} == {RAD_A}
    assert audit.query_audit_logs({"date_from": date(2026, 10, 2)})["total"] == 0
    assert audit.query_audit_logs({"date_from": date(2026, 10, 1), "date_to": date(2026, 10, 1)})["total"] == 3


def test_invalid_filter_values_are_ignored(db, session):
    seed_logs(db)
    sign_in(session, ADMIN_A)

    result = audit.query_audit_logs({"category": "'; drop", "outcome": "x", "actor_user_id": "not-a-uuid"})

    assert result["total"] == 3


def test_search_cannot_inject_postgrest_filters(db, session):
    seed_logs(db)
    sign_in(session, ADMIN_A)

    with pytest.raises(ValueError):
        audit.query_audit_logs({"search": f"x,hospital_id.eq.{HOSP_B}"})

    result = audit.query_audit_logs({"search": "patient"})
    assert {r["event_type"] for r in result["rows"]} == {"patient.created"}
    assert visible_hospitals(result) == {HOSP_A}


def test_pagination_is_server_side_and_capped(db, session):
    seed_logs(db)
    sign_in(session, ADMIN_A)

    page1 = audit.query_audit_logs({}, page=1, page_size=2)
    page2 = audit.query_audit_logs({}, page=2, page_size=2)

    assert len(page1["rows"]) == 2 and len(page2["rows"]) == 1
    assert page1["total"] == 3
    assert audit.query_audit_logs({}, page_size=10_000)["page_size"] == audit.PAGE_SIZE_MAX
    assert page1["rows"][0]["created_at"] > page1["rows"][1]["created_at"]


# ============================================================
# CSV EXPORT
# ============================================================

def read_csv(data):
    return list(csv.DictReader(io.StringIO(data.decode("utf-8"))))


def test_csv_export_uses_same_scope_and_is_audited(db, session):
    seed_logs(db)
    sign_in(session, ADMIN_A)

    data, count, truncated = audit.export_audit_logs_csv({"hospital_id": HOSP_B})

    rows = read_csv(data)
    assert count == 3 and not truncated
    assert {r["hospital_id"] for r in rows} == {HOSP_A}

    exported = db.audit_rows[-1]
    assert exported["event_type"] == "audit.exported"
    assert exported["actor_user_id"] == ADMIN_A
    assert exported["hospital_id"] == HOSP_A
    assert exported["metadata"]["row_count"] == 3
    assert exported["metadata"]["scope"] == "hospital"


def test_csv_export_escapes_formulas(db, session):
    seed_logs(db)
    sign_in(session, ADMIN_A)

    rows = read_csv(audit.export_audit_logs_csv({})[0])

    assert any(r["target_id"].startswith("'=") for r in rows)
    assert not any(r["target_id"].startswith("=") for r in rows)


def test_export_does_not_log_reads_recursively(db, session):
    seed_logs(db)
    sign_in(session, ADMIN_A)
    before = len(db.audit_rows)

    audit.query_audit_logs({})
    audit.query_audit_logs({}, page=2)
    assert len(db.audit_rows) == before

    audit.export_audit_logs_csv({})
    assert len(db.audit_rows) == before + 1


def test_export_truncates_at_limit(db, session, monkeypatch):
    monkeypatch.setattr(audit, "EXPORT_ROW_LIMIT", 2)
    monkeypatch.setattr(audit, "EXPORT_BATCH", 1)
    seed_logs(db)
    sign_in(session, ADMIN_A)

    _data, count, truncated = audit.export_audit_logs_csv({})

    assert count == 2 and truncated
