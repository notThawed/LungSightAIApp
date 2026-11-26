"""Offline regression tests for LungSight Geoapify fallback queries.

Copy to tests/test_geocoding_fallback_20261126.py inside LungSightAIApp.
Run: python -m pytest tests/test_geocoding_fallback_20261126.py -v
"""
from unittest.mock import patch

from backend.geospatial_backend import barangay_geocoding as geo


class FakeResponse:
    def __init__(self, results):
        self.results = results

    def raise_for_status(self):
        return None

    def json(self):
        return {"results": self.results}


def test_canduman_resolves_with_bare_city_fallback():
    seen = []

    def fake_get(url, params, timeout):
        seen.append(params["text"])
        if params["text"] == "Canduman, Mandaue, Cebu, Philippines":
            return FakeResponse([{
                "country_code": "ph", "result_type": "suburb",
                "suburb": "Canduman", "city": "Mandaue",
                "lat": 10.36771, "lon": 123.93356,
            }])
        return FakeResponse([])

    with patch.object(geo.requests, "get", side_effect=fake_get):
        result = geo._geocode_api_cached(
            "Canduman", "City of Mandaue", "Cebu", "fake-test-key", "0731300007"
        )
    assert result is not None
    assert result["latitude"] == 10.36771
    assert result["longitude"] == 123.93356
    assert result["location_precision"] == "barangay"
    assert "Canduman, Mandaue, Cebu, Philippines" in seen


def test_amenity_does_not_become_barangay_reference():
    def fake_get(url, params, timeout):
        return FakeResponse([{
            "country_code": "ph", "result_type": "amenity",
            "name": "Bakilid Elementary School", "suburb": "Bakilid",
            "city": "Mandaue", "lat": 10.33878, "lon": 123.93399,
        }])

    with patch.object(geo.requests, "get", side_effect=fake_get):
        result = geo._geocode_api_cached(
            "Bakilid", "City of Mandaue", "Cebu", "fake-test-key", "0731300002"
        )
    assert result is None


def test_unresolved_barangay_stays_null():
    with patch.object(geo.requests, "get", return_value=FakeResponse([])):
        result = geo._geocode_api_cached(
            "Unknownbarangay", "City of Mandaue", "Cebu", "fake-test-key", "0731309999"
        )
    assert result is None
