"""Regression tests for both patient registration and edit geocoding."""
from unittest.mock import patch
import pytest

from backend.geospatial_backend import barangay_geocoding as geo

BAKILID = "0731300002"
TIPOLO = "0731300026"
POINT_A = {"latitude": 10.33, "longitude": 123.94,
           "location_precision": "barangay"}
POINT_B = {"latitude": 10.36, "longitude": 123.95,
           "location_precision": "barangay"}


def place(code=BAKILID, **kwargs):
    data = {"psgc_barangay_code": code, "barangay": "Bakilid",
            "city": "Mandaue City", "province": "Cebu"}
    data.update(kwargs)
    return data


def test_registration_ignores_arbitrary_stale_point():
    data = place(**POINT_B)
    with patch.object(geo, "resolve_barangay_coordinates", return_value=POINT_A) as lookup:
        saved = geo.prepare_patient_coordinates(data)
    assert saved["latitude"] == POINT_A["latitude"]
    assert saved["longitude"] == POINT_A["longitude"]
    lookup.assert_called_once()


def test_unchanged_barangay_retains_verified_db_reference_without_api():
    previous = place(**POINT_A)
    submitted = place(**POINT_B)
    with patch.object(geo, "resolve_barangay_coordinates") as lookup:
        saved = geo.prepare_patient_coordinates(submitted, previous)
    assert saved["latitude"] == POINT_A["latitude"]
    assert saved["longitude"] == POINT_A["longitude"]
    lookup.assert_not_called()


def test_relocation_clears_old_reference_even_when_provider_fails():
    previous = place(**POINT_A)
    submitted = place(TIPOLO, barangay="Tipolo", **POINT_A)
    with patch.object(geo, "resolve_barangay_coordinates", return_value=None):
        saved = geo.prepare_patient_coordinates(submitted, previous)
    assert saved["latitude"] is None
    assert saved["longitude"] is None
    assert saved["location_precision"] is None


def test_relocation_stores_only_new_barangay_point():
    previous = place(**POINT_A)
    submitted = place(TIPOLO, barangay="Tipolo", **POINT_A)
    with patch.object(geo, "resolve_barangay_coordinates", return_value=POINT_B):
        saved = geo.prepare_patient_coordinates(submitted, previous)
    assert (saved["latitude"], saved["longitude"]) == (10.36, 123.95)


def test_incomplete_pair_is_repaired():
    previous = place(latitude=10.33, longitude=None, location_precision="barangay")
    submitted = place(latitude=10.33, longitude=None, location_precision="barangay")
    with patch.object(geo, "resolve_barangay_coordinates", return_value=POINT_A):
        saved = geo.prepare_patient_coordinates(submitted, previous)
    assert saved["longitude"] == 123.94
    assert saved["location_precision"] == "barangay"


def test_unverified_or_missing_location_remains_unmapped():
    submitted = place(**POINT_B)
    with patch.object(geo, "resolve_barangay_coordinates", return_value=None):
        saved = geo.prepare_patient_coordinates(submitted)
    assert saved["latitude"] is None and saved["longitude"] is None
    assert geo.prepare_patient_coordinates(place(code=None, **POINT_A))["location_precision"] is None
