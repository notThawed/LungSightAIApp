"""
Notification history: scope, isolation, masking, manual retry (no network).
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import test_audit as A
from backend import audit, notifications


ROOT = Path(__file__).resolve().parents[1]
E = {f"e{i}": f"eeeeeeee-0000-0000-0000-00000000000{i}" for i in range(1, 7)}


def seed_outbox(db):
    def row(key, hospital, kind, status, event="subscription.renewed", email="admin.a@example.com", **extra):
        return {
            "email_id": E[key], "created_at": f"2026-10-2{key[-1]}T00:00:00+00:00", "updated_at": None,
            "event_type": event, "hospital_id": hospital, "recipient_kind": kind, "recipient_email": email,
            "status": status, "attempts": 1, "max_attempts": 6, "sent_at": None, "delivered_at": None,
            "last_error": None, "skip_reason": None, "provider_message_id": None, **extra,
        }

    db.tables["email_outbox"] = [
        row("e1", A.HOSP_A, "hospital_admin", "sent", provider_message_id="log-x"),
        row("e2", A.HOSP_A, "hospital_admin", "failed", attempts=6, last_error="HTTP 422 invalid_request"),
        row("e3", A.HOSP_A, "hospital_admin", "expanded", email=None),
        row("e4", A.HOSP_B, "hospital_admin", "delivered", email="admin.b@example.com"),
        row("e5", None, "applicant_receipt", "sent", event="application.received", email="applicant@example.com"),
        row("e6", None, "platform_admin", "failed", event="ops.alert", email="super@example.com"),
    ]


@pytest.fixture
def env(monkeypatch):
    db = A.build_fake_db()
    seed_outbox(db)
    session = {}
    monkeypatch.setattr(audit, "_get_client", lambda: db)
    monkeypatch.setattr(audit, "_streamlit_session", lambda: session)
    monkeypatch.setattr(audit, "streamlit_session_id", lambda: "s")
    audit._PROFILE_CACHE.clear()
    return db, session


def sign_in(session, user_id, **extra):
    session["logged_in"] = True
    session["user"] = {"user_id": user_id, **extra}


def ids(result):
    return {r["email_id"] for r in result["rows"]}


# ============================================================
# SCOPE
# ============================================================

def test_hospital_admin_sees_only_own_hospital_admin_emails(env):
    _db, session = env
    sign_in(session, A.ADMIN_A)

    result = notifications.list_notifications({})

    assert ids(result) == {E["e1"], E["e2"]}          # no B, no receipts, no alerts, no fan-out parents
    assert all("@" in r["recipient"] and "***" in r["recipient"] for r in result["rows"])


def test_hospital_admin_cannot_widen_scope(env):
    _db, session = env
    sign_in(session, A.ADMIN_A, role="Superadmin", hospital_id=A.HOSP_B)

    assert ids(notifications.list_notifications({"hospital_id": A.HOSP_B})) == {E["e1"], E["e2"]}


def test_hospital_b_isolated_from_a(env):
    _db, session = env
    sign_in(session, A.ADMIN_B)

    assert ids(notifications.list_notifications({})) == {E["e4"]}


def test_superadmin_sees_everything_except_fanout_parents(env):
    _db, session = env
    sign_in(session, A.SUPER)

    assert ids(notifications.list_notifications({})) == {E["e1"], E["e2"], E["e4"], E["e5"], E["e6"]}
    assert ids(notifications.list_notifications({"hospital_id": A.HOSP_B})) == {E["e4"]}
    assert ids(notifications.list_notifications({"status": "failed"})) == {E["e2"], E["e6"]}


@pytest.mark.parametrize("user_id", [A.RAD_A, A.INACTIVE_A, None])
def test_other_roles_are_denied(env, user_id):
    _db, session = env
    if user_id:
        sign_in(session, user_id)

    with pytest.raises(audit.AuditAccessDenied):
        notifications.list_notifications({})


def test_rows_never_expose_full_addresses(env):
    _db, session = env
    sign_in(session, A.SUPER)

    flat = str(notifications.list_notifications({})["rows"])

    for address in ("admin.a@example.com", "applicant@example.com", "super@example.com"):
        assert address not in flat
    simulated = {r["email_id"]: r["simulated"] for r in notifications.list_notifications({})["rows"]}
    assert simulated[E["e1"]] is True and simulated[E["e4"]] is False


def test_invalid_filters_are_ignored(env):
    _db, session = env
    sign_in(session, A.SUPER)

    result = notifications.list_notifications({"status": "'; drop", "event_type": "x", "hospital_id": "nope",
                                               "created_from": datetime(2026, 10, 1)})  # naive datetime ignored
    assert len(result["rows"]) == 5


def test_date_filters(env):
    _db, session = env
    sign_in(session, A.SUPER)

    result = notifications.list_notifications({
        "created_from": datetime(2026, 10, 24, tzinfo=timezone.utc),
        "created_before": datetime(2026, 10, 26, tzinfo=timezone.utc),
    })
    assert ids(result) == {E["e4"], E["e5"]}


# ============================================================
# RETRY
# ============================================================

def test_superadmin_can_retry_a_failed_email_once(env):
    db, session = env
    sign_in(session, A.SUPER)

    assert notifications.request_retry(E["e2"]) is True

    row = next(r for r in db.tables["email_outbox"] if r["email_id"] == E["e2"])
    assert row["status"] == "queued" and row["max_attempts"] == 9 and row["last_error"] is None

    events = [r for r in db.audit_rows if r["event_type"] == "email.retry_requested"]
    assert len(events) == 1
    assert events[0]["actor_user_id"] == A.SUPER and events[0]["hospital_id"] == A.HOSP_A
    assert events[0]["metadata"] == {"notification_event": "subscription.renewed", "attempts": 6}

    with pytest.raises(ValueError):
        notifications.request_retry(E["e2"])     # no longer failed


def test_hospital_admin_cannot_retry(env):
    db, session = env
    sign_in(session, A.ADMIN_A)

    with pytest.raises(audit.AuditAccessDenied):
        notifications.request_retry(E["e2"])

    row = next(r for r in db.tables["email_outbox"] if r["email_id"] == E["e2"])
    assert row["status"] == "failed"
    denied = [r for r in db.audit_rows if r["event_type"] == "auth.permission_denied"]
    assert denied[-1]["metadata"] == {"resource": "notifications.retry"}


@pytest.mark.parametrize("email_id", [None, "not-a-uuid", "ffffffff-0000-0000-0000-000000000000"])
def test_retry_rejects_unknown_ids(env, email_id):
    _db, session = env
    sign_in(session, A.SUPER)

    with pytest.raises(ValueError):
        notifications.request_retry(email_id)


def test_retry_only_for_failed_rows(env):
    _db, session = env
    sign_in(session, A.SUPER)

    for key in ("e1", "e4", "e5"):
        with pytest.raises(ValueError):
            notifications.request_retry(E[key])


def test_mask_email():
    assert notifications.mask_email("admin.a@example.com") == "a***@example.com"
    assert notifications.mask_email(None) == "—"
    assert notifications.mask_email("garbage") == "—"


# ============================================================
# PAGE
# ============================================================

def page_script():
    import sys
    from pathlib import Path

    import streamlit as st

    root = Path(st.session_state["root"])
    for extra in (root, root / "streamlit_app", root / "tests"):
        if str(extra) not in sys.path:
            sys.path.insert(0, str(extra))

    import test_audit as A
    import test_notifications as N
    from backend import audit
    import backend.fetches as fetches
    import pages.notification_history as page

    if "fake_db" not in st.session_state:
        db = A.build_fake_db()
        N.seed_outbox(db)
        st.session_state["fake_db"] = db

    db = st.session_state["fake_db"]
    audit._get_client = lambda: db
    audit._PROFILE_CACHE.clear()
    fetches.get_all_hospitals = lambda: [
        {"hospital_id": A.HOSP_A, "hospital_name": "Hospital A"},
        {"hospital_id": A.HOSP_B, "hospital_name": "Hospital B"},
    ]

    st.session_state["logged_in"] = True
    st.session_state["user"] = st.session_state["as_user"]
    page.show()


def run_as(user):
    at = AppTest.from_function(page_script, default_timeout=60)
    at.session_state["root"] = str(ROOT)
    at.session_state["as_user"] = user
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def widen_dates(at):
    at.date_input(key="notif_from").set_value(datetime(2026, 10, 1).date()).run()
    return at


def test_page_hospital_admin_view():
    at = widen_dates(run_as({"user_id": A.ADMIN_A}))

    frame = at.dataframe[0].value
    assert len(frame) == 2
    assert set(frame["Recipient"]) == {"a***@example.com"}
    assert "sent (simulated)" in set(frame["Status"])
    assert not [s for s in at.selectbox if s.label == "Hospital"]


def test_page_superadmin_view_and_filter():
    at = widen_dates(run_as({"user_id": A.SUPER}))

    assert len(at.dataframe[0].value) == 5
    at.selectbox(key="notif_status").set_value("failed").run()
    assert len(at.dataframe[0].value) == 2


def test_page_denies_other_roles():
    at = run_as({"user_id": A.RAD_A})

    assert any("do not have access" in e.value for e in at.error)
    assert not at.dataframe


def test_page_empty_state():
    at = run_as({"user_id": A.ADMIN_B})   # default 30-day window excludes the seeded rows? e4 is 2026-10-24

    at.selectbox(key="notif_status").set_value("bounced").run()
    assert any("No emails match" in m.value for m in at.markdown)
