"""
Streamlit AppTest for the Audit Logs page, backed by the in-memory fake
database from test_audit.py (no network).
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import test_audit as T


ROOT = Path(__file__).resolve().parents[1]


def page_script():
    import sys
    from pathlib import Path

    import streamlit as st

    root = Path(st.session_state["root"])
    for extra in (root, root / "streamlit_app", root / "tests"):
        if str(extra) not in sys.path:
            sys.path.insert(0, str(extra))

    import test_audit as T
    from backend import audit
    import pages.audit_logs as page

    if "fake_db" not in st.session_state:
        db = T.build_fake_db()
        T.seed_logs(db)
        st.session_state["fake_db"] = db

    db = st.session_state["fake_db"]
    audit._get_client = lambda: db
    audit._PROFILE_CACHE.clear()

    page.get_all_hospitals = lambda: [
        {"hospital_id": T.HOSP_A, "hospital_name": "Hospital A"},
        {"hospital_id": T.HOSP_B, "hospital_name": "Hospital B"},
    ]
    page.get_hospital_staff = lambda hospital_id, active_only=False: [
        p for p in db.tables["user_profiles"] if p["hospital_id"] == hospital_id
    ]
    page._hospital_options.clear()
    page._actor_options.clear()

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


def table(at):
    return at.dataframe[0].value


def test_hospital_admin_sees_only_own_hospital_rows():
    at = run_as({"user_id": T.ADMIN_A, "role": "Hospital Admin", "hospital_id": T.HOSP_A})

    frame = table(at)
    assert len(frame) == 3
    assert "Hospital" not in frame.columns
    assert set(frame["Event"]) == {"user.created", "patient.created", "ai.analysis_failed"}
    assert [s.label for s in at.selectbox] == ["Category", "Outcome", "Actor"]


def test_tampered_session_does_not_widen_scope():
    at = run_as({"user_id": T.ADMIN_A, "role": "Superadmin", "hospital_id": T.HOSP_B})

    frame = table(at)
    assert len(frame) == 3
    assert "Hospital" not in frame.columns


def test_superadmin_sees_platform_view_with_hospital_filter():
    at = run_as({"user_id": T.SUPER, "role": "Superadmin", "hospital_id": None})

    assert len(table(at)) == 5
    assert "Hospital" in table(at).columns

    at.selectbox(key="audit_hospital").set_value("Hospital B").run()
    assert set(table(at)["Hospital"]) == {"Hospital B"}


@pytest.mark.parametrize("user_id", [T.RAD_A, T.INACTIVE_A])
def test_non_admins_get_access_error_and_no_table(user_id):
    at = run_as({"user_id": user_id, "role": "Hospital Admin", "hospital_id": T.HOSP_A})

    assert not at.dataframe
    assert any("do not have access" in e.value for e in at.error)


def test_outcome_filter_and_empty_state():
    at = run_as({"user_id": T.ADMIN_A, "role": "Hospital Admin", "hospital_id": T.HOSP_A})

    at.selectbox(key="audit_outcome").set_value("failure").run()
    assert set(table(at)["Outcome"]) == {"failure"}

    at.selectbox(key="audit_outcome").set_value("denied").run()
    assert not at.dataframe
    assert any("No audit events" in m.value for m in at.markdown)


def test_invalid_search_shows_warning():
    at = run_as({"user_id": T.ADMIN_A, "role": "Hospital Admin", "hospital_id": T.HOSP_A})

    at.text_input(key="audit_search").input("a,b").run()

    assert any("Search may only contain" in w.value for w in at.warning)


def test_export_is_scoped_and_audited():
    at = run_as({"user_id": T.ADMIN_A, "role": "Hospital Admin", "hospital_id": T.HOSP_A})

    at.button(key="audit_export_prepare").click().run()

    db = at.session_state["fake_db"]
    exported = [r for r in db.audit_rows if r["event_type"] == "audit.exported"]
    assert len(exported) == 1
    assert exported[0]["hospital_id"] == T.HOSP_A
    assert exported[0]["metadata"]["row_count"] == 3
    assert any("rows ready" in c.value for c in at.caption)
