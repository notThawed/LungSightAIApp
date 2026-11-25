"""
Streamlit AppTest for the Hospital Reports page (fake database, golden data).
"""

from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import test_audit as A


ROOT = Path(__file__).resolve().parents[1]


def page_script():
    import sys
    from pathlib import Path

    import streamlit as st

    root = Path(st.session_state["root"])
    for extra in (root, root / "streamlit_app", root / "tests"):
        if str(extra) not in sys.path:
            sys.path.insert(0, str(extra))

    import test_audit as A
    import test_report_calculations as G
    from backend import audit
    from backend.reports import service
    import pages.hospital_reports as page

    if "fake_db" not in st.session_state:
        db = A.build_fake_db()
        db.tables["hospitals"] = [
            {"hospital_id": A.HOSP_A, "hospital_name": "Hospital A"},
            {"hospital_id": A.HOSP_B, "hospital_name": "Hospital B"},
        ]
        st.session_state["fake_db"] = db
        st.session_state["fetch_calls"] = []

    db = st.session_state["fake_db"]
    audit._get_client = lambda: db
    audit._PROFILE_CACHE.clear()

    def fake_fetch(hospital_id, period, include_audit=True):
        st.session_state["fetch_calls"].append(hospital_id)
        inputs = G.golden_inputs()
        inputs.hospital = {"hospital_id": hospital_id, "hospital_name": "Report Hospital", "hospital_code": "RH"}
        for exam in inputs.exams:
            if exam["patients"]["hospital_id"] == G.HOSP:
                exam["patients"] = dict(exam["patients"], hospital_id=hospital_id)
        return inputs

    service.fetch_report_inputs = fake_fetch

    st.session_state["logged_in"] = True
    st.session_state["user"] = st.session_state["as_user"]

    page.show()


def run_as(user):
    at = AppTest.from_function(page_script, default_timeout=120)
    at.session_state["root"] = str(ROOT)
    at.session_state["as_user"] = user
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def generate_golden(at):
    at.radio(key="report_period_kind").set_value("Custom").run()
    at.date_input(key="report_custom_range").set_value((date(2026, 10, 1), date(2026, 10, 7))).run()
    at.button(key="report_generate").click().run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def metric_values(at):
    return {m.label: m.value for m in at.metric}


def test_hospital_admin_generates_report_with_golden_numbers():
    at = generate_golden(run_as({"user_id": A.ADMIN_A}))

    values = metric_values(at)
    assert values["Examinations registered"] == "8"
    assert values["Analyses completed"] == "3"
    assert values["Reviewed by a physician"] == "2"
    assert values["Median time, request to AI result"] == "50 min"
    assert any(c.value == "of 3 · 66.7%" for c in at.caption)
    assert at.session_state["fetch_calls"] == [A.HOSP_A]

    generated = [r for r in at.session_state["fake_db"].audit_rows if r["event_type"] == "report.generated"]
    assert len(generated) == 1

    # A rerun (any widget interaction) must not generate or audit again
    at.run()
    generated = [r for r in at.session_state["fake_db"].audit_rows if r["event_type"] == "report.generated"]
    assert len(generated) == 1


def test_hospital_admin_has_no_hospital_selector():
    at = run_as({"user_id": A.ADMIN_A, "hospital_id": A.HOSP_B})

    assert not [s for s in at.selectbox if s.label == "Hospital"]


def test_changed_options_show_refresh_notice():
    at = generate_golden(run_as({"user_id": A.ADMIN_A}))

    at.radio(key="report_period_kind").set_value("Monthly").run()

    assert any("options changed" in i.value for i in at.info)


def test_export_prepares_download_and_audits_once():
    at = generate_golden(run_as({"user_id": A.ADMIN_A}))

    at.button(key="report_prepare_xlsx").click().run()
    assert not at.exception

    exported = [r for r in at.session_state["fake_db"].audit_rows if r["event_type"] == "report.exported"]
    assert len(exported) == 1 and exported[0]["metadata"]["format"] == "xlsx"
    assert not [b for b in at.button if b.key == "report_prepare_xlsx"]
    assert any("examination-level sheets" in c.value for c in at.caption)


def test_superadmin_selects_hospital_and_gets_aggregates():
    at = run_as({"user_id": A.SUPER})

    at.selectbox(key="report_hospital").set_value("Hospital B").run()
    generate_golden(at)

    assert at.session_state["fetch_calls"] == [A.HOSP_B]
    assert any("aggregate figures only" in c.value for c in at.caption)


@pytest.mark.parametrize("user_id", [A.RAD_A, A.INACTIVE_A])
def test_unauthorised_roles_see_error_only(user_id):
    at = run_as({"user_id": user_id})

    assert any("do not have access" in e.value for e in at.error)
    assert not [b for b in at.button if b.key == "report_generate"]


def test_report_b_and_empty_states_are_explicit():
    at = generate_golden(run_as({"user_id": A.ADMIN_A}))

    text = " ".join(m.value for m in at.markdown)
    assert "Unavailable" in text and "reference set" in text
