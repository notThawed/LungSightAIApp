"""
Report scope, isolation, audit events and export behaviour (no network).
"""

from datetime import date

import pytest

import test_audit as A
import test_report_calculations as G
from backend import audit
from backend.reports import data as report_data
from backend.reports import service
from backend.reports.periods import custom_period


PERIOD = custom_period(date(2026, 10, 1), date(2026, 10, 7))


@pytest.fixture
def env(monkeypatch):
    db = A.build_fake_db()
    db.tables["hospitals"] = [
        {"hospital_id": A.HOSP_A, "hospital_name": "Hospital A"},
        {"hospital_id": A.HOSP_B, "hospital_name": "Hospital B"},
    ]
    session = {}
    calls = []

    monkeypatch.setattr(audit, "_get_client", lambda: db)
    monkeypatch.setattr(audit, "_streamlit_session", lambda: session)
    monkeypatch.setattr(audit, "streamlit_session_id", lambda: "sess-1")
    audit._PROFILE_CACHE.clear()

    def fake_fetch(hospital_id, period, include_audit=True):
        calls.append(hospital_id)
        inputs = G.golden_inputs()
        inputs.hospital = {"hospital_id": hospital_id, "hospital_name": "H", "hospital_code": "H-1"}
        for exam in inputs.exams:
            exam["patients"] = dict(exam["patients"], hospital_id=hospital_id
                                    if exam["patients"]["hospital_id"] == G.HOSP else "other")
        return inputs

    monkeypatch.setattr(service, "fetch_report_inputs", fake_fetch)

    class Env:
        pass

    e = Env()
    e.db, e.session, e.calls = db, session, calls
    return e


def sign_in(env, user_id, **extra):
    env.session["logged_in"] = True
    env.session["user"] = {"user_id": user_id, **extra}


def events(env, event_type):
    return [r for r in env.db.audit_rows if r["event_type"] == event_type]


# ============================================================
# SCOPE / ISOLATION
# ============================================================

def test_hospital_admin_is_pinned_to_own_hospital(env):
    sign_in(env, A.ADMIN_A)

    report = service.generate_hospital_report(PERIOD, requested_hospital_id=A.HOSP_B)

    assert env.calls == [A.HOSP_A]
    assert report.hospital_id == A.HOSP_A
    assert report.patient_level is True
    assert report.metric("exams_registered").value == 8


def test_session_tampering_does_not_change_scope(env):
    sign_in(env, A.ADMIN_A, role="Superadmin", hospital_id=A.HOSP_B)

    report = service.generate_hospital_report(PERIOD, requested_hospital_id=A.HOSP_B)

    assert env.calls == [A.HOSP_A]
    assert report.hospital_id == A.HOSP_A


def test_superadmin_gets_selected_hospital_aggregates_only(env):
    sign_in(env, A.SUPER)

    report = service.generate_hospital_report(PERIOD, requested_hospital_id=A.HOSP_B)

    assert env.calls == [A.HOSP_B]
    assert report.patient_level is False
    assert report.exam_rows == ()


@pytest.mark.parametrize("requested", [None, "not-a-uuid", "cccccccc-0000-0000-0000-000000000003"])
def test_superadmin_needs_a_real_hospital(env, requested):
    sign_in(env, A.SUPER)

    with pytest.raises(ValueError):
        service.generate_hospital_report(PERIOD, requested_hospital_id=requested)
    assert env.calls == []


@pytest.mark.parametrize("user_id", [A.RAD_A, A.INACTIVE_A, None])
def test_unauthorised_roles_are_blocked(env, user_id):
    if user_id:
        sign_in(env, user_id)

    with pytest.raises(audit.AuditAccessDenied):
        service.generate_hospital_report(PERIOD, requested_hospital_id=A.HOSP_A)

    assert env.calls == []
    denied = events(env, "auth.permission_denied")
    if user_id:
        assert denied and denied[-1]["metadata"] == {"resource": "hospital_reports"}


def test_export_rechecks_scope_against_report_hospital(env):
    sign_in(env, A.ADMIN_B)
    foreign = G.build()   # report for HOSP (== HOSP_A), held by Hospital B's admin

    with pytest.raises(audit.AuditAccessDenied):
        service.export_hospital_report(foreign, "pdf")
    assert not events(env, "report.exported")


def test_superadmin_cannot_export_patient_level_report(env):
    sign_in(env, A.SUPER)
    patient_level = G.build(patient_level=True)

    with pytest.raises(audit.AuditAccessDenied):
        service.export_hospital_report(patient_level, "xlsx")


# ============================================================
# AUDIT EVENTS
# ============================================================

def test_report_generated_event_written_once_with_safe_metadata(env):
    sign_in(env, A.ADMIN_A)

    report = service.generate_hospital_report(PERIOD)

    rows = events(env, "report.generated")
    assert len(rows) == 1
    row = rows[0]
    assert row["actor_user_id"] == A.ADMIN_A
    assert row["hospital_id"] == A.HOSP_A
    assert row["target_type"] == "report" and row["target_id"] == report.report_id
    assert row["outcome"] == "success"
    assert row["metadata"] == {
        "report_type": "hospital_activity",
        "period_kind": "custom",
        "period_start": "2026-10-01",
        "period_end": "2026-10-07",
    }


def test_superadmin_report_event_is_attributed_to_selected_hospital(env):
    sign_in(env, A.SUPER)

    service.generate_hospital_report(PERIOD, requested_hospital_id=A.HOSP_B)

    assert events(env, "report.generated")[0]["hospital_id"] == A.HOSP_B


def test_generation_failure_is_audited_and_raised(env, monkeypatch):
    sign_in(env, A.ADMIN_A)

    def boom(*_args, **_kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(service, "fetch_report_inputs", boom)

    with pytest.raises(RuntimeError):
        service.generate_hospital_report(PERIOD)

    rows = events(env, "report.generated")
    assert len(rows) == 1 and rows[0]["outcome"] == "failure"
    assert rows[0]["metadata"]["error_class"] == "RuntimeError"


@pytest.mark.parametrize("fmt,magic", [("pdf", b"%PDF-"), ("xlsx", b"PK")])
def test_export_returns_file_and_audits_once(env, fmt, magic):
    sign_in(env, A.ADMIN_A)
    report = service.generate_hospital_report(PERIOD)

    for _ in range(3):   # reruns / repeated clicks
        data, filename, mime = service.export_hospital_report(report, fmt)

    assert data.startswith(magic)
    assert filename == f"lungsight_report_H-1_2026-10-01_2026-10-07.{fmt}"
    assert mime

    rows = events(env, "report.exported")
    assert len(rows) == 1
    assert rows[0]["metadata"]["format"] == fmt
    assert rows[0]["target_id"] == report.report_id
    assert rows[0]["hospital_id"] == A.HOSP_A


def test_export_failure_gives_no_file_and_failure_event(env, monkeypatch):
    sign_in(env, A.ADMIN_A)
    report = service.generate_hospital_report(PERIOD)

    def broken(_report):
        raise OSError("disk full")

    monkeypatch.setattr(service, "_renderers", lambda: {"pdf": (broken, "application/pdf")})

    with pytest.raises(service.ReportExportError):
        service.export_hospital_report(report, "pdf")

    rows = events(env, "report.exported")
    assert [r["outcome"] for r in rows] == ["failure"]


def test_unknown_export_format_rejected(env):
    sign_in(env, A.ADMIN_A)
    report = service.generate_hospital_report(PERIOD)

    with pytest.raises(ValueError):
        service.export_hospital_report(report, "csv")


def test_filename_is_sanitised(env):
    report = G.build()
    object.__setattr__(report, "hospital", (("Hospital", "x"), ("Hospital code", "../evil code=1"), ("Type", None),
                                             ("Address", None)))

    assert service.export_filename(report, "pdf") == "lungsight_report_evil-code-1_2026-10-01_2026-10-07.pdf"


# ============================================================
# DATA LAYER QUERY SCOPING
# ============================================================

class RecordingClient:
    """Records every query's table and filters; returns no rows."""

    def __init__(self):
        self.queries = []

    def table(self, name):
        query = _RecordingQuery(name)
        self.queries.append(query)
        return query


class _RecordingQuery:
    def __init__(self, table):
        self.table = table
        self.filters = []

    def __getattr__(self, name):
        def method(*args, **_kwargs):
            if name in ("eq", "gte", "lt", "in_", "is_"):
                self.filters.append((name, args[0], args[1]))
            return self
        return method

    def execute(self):
        class R:
            data = []
            count = 0
        return R()


def test_every_hospital_level_query_filters_by_scoped_hospital(monkeypatch):
    client = RecordingClient()
    monkeypatch.setattr(report_data, "_client", lambda: client)

    report_data.fetch_report_inputs(A.HOSP_A, PERIOD, include_audit=False)

    by_table = {}
    for query in client.queries:
        by_table.setdefault(query.table, []).append(query.filters)

    def has(filters, column):
        return ("eq", column, A.HOSP_A) in filters

    assert all(has(f, "hospital_id") for f in by_table["hospitals"])
    assert all(has(f, "patients.hospital_id") for f in by_table["examinations"])
    assert all(has(f, "xray_requests.hospital_id") for f in by_table["xray_images"])
    assert all(has(f, "hospital_id") for f in by_table["patients"])
    assert all(has(f, "hospital_id") for f in by_table["user_profiles"])

    exam_query = by_table["examinations"][0]
    assert ("gte", "created_at", PERIOD.start_utc.isoformat()) in exam_query
    assert ("lt", "created_at", PERIOD.end_utc.isoformat()) in exam_query
