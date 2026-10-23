"""
Render tests for the Streamlit app using streamlit.testing (no browser,
no real database: every data function the rendered pages touch is patched).
"""

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("torch", reason="the app imports the AI models at start-up")

import streamlit as st  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
APP = str(ROOT / "streamlit_app" / "app.py")

FAKE_METRICS = [
    {"key": "pending_exams", "label": "Pending examinations", "hint": "Waiting", "value": 7},
    {"key": "xray_ready", "label": "X-ray results to review", "hint": "Done", "value": None},
]


@pytest.fixture
def offline_backend(monkeypatch):
    """Patch the gate checks and dashboard queries that run on every page load."""
    from backend.backend_utils import dashboard_utils, hospital_utils, subscription_utils
    from streamlit_app.components import role_dashboard

    monkeypatch.setattr(hospital_utils, "is_hospital_active", lambda hospital_id: True)
    monkeypatch.setattr(hospital_utils, "is_hospital_setup_completed", lambda hospital_id: True)
    monkeypatch.setattr(subscription_utils, "apply_scheduled_changes", lambda hospital_id: {})
    monkeypatch.setattr(
        subscription_utils,
        "get_subscription_context",
        lambda hospital_id: {"state": "active", "hospital_id": hospital_id},
    )
    monkeypatch.setattr(role_dashboard, "get_dashboard_metrics", lambda role, hospital_id: FAKE_METRICS)
    monkeypatch.setattr(dashboard_utils, "get_system_metrics", lambda: FAKE_METRICS)
    monkeypatch.setattr(dashboard_utils, "get_ai_daily_counts", lambda days=14: [])
    monkeypatch.setattr(dashboard_utils, "get_hospital_overview", lambda: [])

    # The layouts import pages both as "pages.*" and "streamlit_app.pages.*",
    # so the admin dashboard module exists under two names.
    for name in (
        "pages.system_administrator.dashboard",
        "streamlit_app.pages.system_administrator.dashboard",
    ):
        admin_dashboard = importlib.import_module(name)
        monkeypatch.setattr(admin_dashboard, "get_system_metrics", lambda: FAKE_METRICS)
        monkeypatch.setattr(admin_dashboard, "get_ai_daily_counts", lambda days=14: [])
        monkeypatch.setattr(admin_dashboard, "get_hospital_overview", lambda: [])

    st.cache_data.clear()
    yield
    st.cache_data.clear()


def signed_in(role, hospital_id="hospital-1"):
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["logged_in"] = True
    at.session_state["current_page"] = "Dashboard"
    at.session_state["user"] = {
        "user_id": "user-1",
        "name": "Test User",
        "email": "test@example.org",
        "role": role,
        "hospital_id": hospital_id,
        "theme_preference": "light",
    }
    return at


def page_text(at):
    return " ".join(str(block.value) for block in at.markdown)


def test_login_screen_renders():
    at = AppTest.from_file(APP, default_timeout=120).run()

    assert not at.exception
    assert any("Email" in field.label for field in at.text_input)


@pytest.mark.parametrize(
    "role,title",
    [
        ("Radiologist", "Radiologist dashboard"),
        ("Radiologic Technologist", "Radiologic technologist dashboard"),
        ("Staff", "Staff dashboard"),
        ("Hospital Admin", "Hospital dashboard"),
    ],
)
def test_role_dashboards_render_real_metrics(offline_backend, role, title):
    at = signed_in(role).run()

    assert not at.exception, at.exception
    text = page_text(at)
    assert title in text
    assert "Pending examinations" in text and ">7<" in text
    # A metric that failed to load is shown as unavailable, not as 0.
    assert "—" in text


def test_system_admin_dashboard_has_no_sample_data(offline_backend):
    at = signed_in("Superadmin", hospital_id=None).run()

    assert not at.exception, at.exception
    text = page_text(at)
    assert "Administrator dashboard" in text
    assert "Hospital A" not in text
    assert "No chest X-rays were analyzed" in text


def test_dashboard_quick_action_navigates(offline_backend):
    at = signed_in("Radiologic Technologist").run()

    next(b for b in at.button if b.label == "X-ray queue").click()
    at.run()

    assert at.session_state["current_page"] == "X-ray Queue"


@pytest.mark.skipif((ROOT / ".env").exists(), reason="a local .env provides credentials")
def test_missing_configuration_shows_setup_screen():
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPABASE")}
    script = (
        "from streamlit.testing.v1 import AppTest;"
        f"at = AppTest.from_file(r'{APP}', default_timeout=120).run();"
        "print(at.title[0].value)"
    )

    result = subprocess.run(
        [sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=300
    )

    assert "LungSightAI is not configured" in result.stdout, result.stderr[-2000:]
