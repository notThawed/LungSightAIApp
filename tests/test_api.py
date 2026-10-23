"""The FastAPI stub in backend/api.py (health endpoint only)."""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from backend.api import app  # noqa: E402


def test_root_reports_running():
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "LungSight API running"}
