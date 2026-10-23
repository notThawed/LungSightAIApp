"""
Dashboard metrics: correct queries, honest failure handling, and the same
definitions on web (dashboard_utils.py) and mobile (lib/dashboard.ts).
"""

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.backend_utils import dashboard_utils

ROOT = Path(__file__).resolve().parents[2]
MOBILE_DASHBOARD = (ROOT / "mobile_app/src/lib/dashboard.ts").read_text(encoding="utf-8")


class FakeQuery:
    """Records PostgREST calls; returns a fixed count."""

    def __init__(self, log, table, count, fail):
        self.log, self.table, self.count, self.fail = log, table, count, fail
        self.calls = []

    def select(self, *args, **kwargs):
        self.calls.append(("select", args, kwargs))
        return self

    def __getattr__(self, method):
        def record(*args, **kwargs):
            self.calls.append((method, args, kwargs))
            return self
        return record

    def execute(self):
        self.log.append((self.table, self.calls))
        if self.fail:
            raise RuntimeError("network down")
        return type("Response", (), {"count": self.count, "data": []})()


class FakeClient:
    def __init__(self, count=3, fail_tables=()):
        self.count, self.fail_tables, self.log = count, set(fail_tables), []

    def table(self, name):
        return FakeQuery(self.log, name, self.count, name in self.fail_tables)


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(dashboard_utils, "admin_supabase", client)
    return client


def test_radiologist_metrics_query_examinations_by_status(fake_client):
    metrics = dashboard_utils.get_dashboard_metrics("Radiologist", "hospital-1")

    assert [m["key"] for m in metrics] == [
        "pending_exams", "xray_ready", "awaiting_xray", "followups_today",
    ]
    assert all(m["value"] == 3 for m in metrics)

    table, calls = fake_client.log[0]
    assert table == "examinations"
    assert ("eq", ("status", "Pending"), {}) in calls
    assert ("eq", ("patients.hospital_id", "hospital-1"), {}) in calls


def test_followups_today_filters_today_and_open_statuses(fake_client, monkeypatch):
    monkeypatch.setattr(dashboard_utils, "today_iso", lambda: "2026-10-21")

    dashboard_utils.get_dashboard_metrics("Staff", "hospital-1")

    table, calls = fake_client.log[0]
    assert table == "follow_ups"
    assert ("in_", ("status", ["Scheduled", "Rescheduled"]), {}) in calls
    assert ("eq", ("follow_up_date", "2026-10-21"), {}) in calls


def test_failed_metric_is_none_not_zero(monkeypatch):
    """A failed query must show as unavailable, never as a misleading 0."""
    monkeypatch.setattr(
        dashboard_utils, "admin_supabase", FakeClient(fail_tables={"follow_ups"})
    )

    metrics = {m["key"]: m["value"] for m in dashboard_utils.get_dashboard_metrics("Staff", "h")}

    assert metrics["followups_today"] is None
    assert metrics["pending_exams"] == 3


def test_unknown_role_has_no_metrics(fake_client):
    assert dashboard_utils.get_dashboard_metrics("Superadmin", "h") == []


def test_manila_today_is_utc_plus_8(monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 21, 17, 30, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(dashboard_utils, "datetime", FixedDatetime)
    assert dashboard_utils.today_iso() == "2026-10-22"


def test_ai_daily_counts_fill_missing_days(monkeypatch):
    class Client(FakeClient):
        def table(self, name):
            query = super().table(name)
            query.execute = lambda: type("R", (), {"data": [
                {"processed_at": datetime.now(timezone.utc).isoformat(), "ai_findings": "positive"},
                {"processed_at": "not-a-date", "ai_findings": "negative"},
            ]})()
            return query

    monkeypatch.setattr(dashboard_utils, "admin_supabase", Client())

    days = dashboard_utils.get_ai_daily_counts(days=7)

    assert len(days) == 7
    assert days[-1]["positive"] == 1
    assert sum(d["negative"] for d in days) == 0


MOBILE_ROLE = {
    "Radiologist": "radiologist",
    "Radiologic Technologist": "radiologic_technologist",
    "Staff": "staff",
}


def mobile_metrics(role):
    block = re.search(rf"\b{role}: \[(.*?)\n  \],", MOBILE_DASHBOARD, re.S).group(1)
    return re.findall(r'key: "(\w+)", label: "([^"]+)", hint: "([^"]+)"', block)


@pytest.mark.parametrize("web_role,mobile_role", MOBILE_ROLE.items())
def test_mobile_metrics_match_web(web_role, mobile_role):
    web = [(key, label, hint) for key, label, hint, *_ in dashboard_utils.ROLE_METRICS[web_role]]
    assert mobile_metrics(mobile_role) == web


@pytest.mark.parametrize("status", ["Pending", "X-Ray Ready", "Awaiting X-Ray", "Completed"])
def test_mobile_uses_same_examination_statuses(status):
    assert f'status: "{status}"' in MOBILE_DASHBOARD
