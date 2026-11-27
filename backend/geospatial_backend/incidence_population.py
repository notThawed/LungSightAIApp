"""PSA-derived population lookup and LungSightAI relative incidence classification.

Place in backend/backend_utils/incidence_population.py.

Numerator: physician-confirmed unique newly recorded pneumonia patients, from
LungSightAI (hospital-scoped). Denominator: 2024 PSA census barangay population.
This is a hospital-recorded notification incidence indicator, NOT an unbiased
community disease incidence estimate or a clinical-severity assessment.

Data API (third-party, based on PSA PSGC 2026-Q3 publication):
https://psgc.billyjamesramos.com/api/v1/
Reference: https://psa.gov.ph/classification/psgc/
"""
from __future__ import annotations

import os
import re
from typing import Any

import requests
import streamlit as st

PSGC_POPULATION_API = os.getenv(
    "LUNGSIGHT_POPULATION_API",
    "https://psgc.billyjamesramos.com/api/v1",
).rstrip("/")

# PSGC 2024 population API is based on PSA 2026-Q3 publication, which is the
# most recent official census data available as of 2024-06-01. The API
CENSUS_YEAR = 2024
LOW_UPPER = 0.85
MODERATE_UPPER = 1.76


def _psgc_digits(value: Any) -> str | None:
    """Accept 9-digit correspondence codes and canonical 10-digit PSGC codes."""
    code = str(value or "").strip()
    return code if re.fullmatch(r"\d{9,10}", code) else None


@st.cache_data(ttl=86_400, show_spinner=False)
def population_api_release() -> dict:
    """Return exact source publication and API release (metadata only)."""
    response = requests.get(f"{PSGC_POPULATION_API}/meta", timeout=(4, 12))
    response.raise_for_status()
    result = response.json()
    data = result.get("data", {}) if isinstance(result, dict) else {}
    if not isinstance(data, dict) or not data.get("version"):
        raise ValueError("Population API metadata is incomplete")
    return {"version": data["version"], "source_file": data.get("sourceFile"),
            "release_date": data.get("releaseDate")}


@st.cache_data(ttl=86_400, show_spinner=False)
def get_barangay_population(code: str) -> dict | None:
    """Fetch PSA-derived census population using PSGC; never send patient data.

    Return None for an unmapped historical code. Transport errors propagate so
    temporary outages aren't cached as valid missing population values.
    """
    digits = _psgc_digits(code)
    if digits is None:
        return None
    response = requests.get(
        f"{PSGC_POPULATION_API}/codes/{digits}", timeout=(4, 12),
        headers={"Accept": "application/json"},
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise ValueError("Unexpected barangay population API response")
    item = payload["data"]
    resolved_code = str(item.get("code") or "").strip()
    if item.get("level") != "barangay" or not re.fullmatch(r"\d{10}", resolved_code):
        raise ValueError("PSGC code resolved to a non-barangay location")
    if digits != resolved_code and len(digits) == 10:
        raise ValueError("API returned a different barangay PSGC code")
    raw = item.get("population")
    try:
        population = int(str(raw).replace(",", ""))
    except (TypeError, ValueError) as exc:
        raise ValueError("API returned an invalid census population") from exc
    if population <= 0:
        return None
    return {"code": resolved_code, "population": population,
            "census_year": CENSUS_YEAR, "name": item.get("name") or ""}


def classify_relative_incidence(cases: int, incidence: float | None,
                                reference: float | None) -> tuple[str, float | None]:
    """Adapted Bohol pneumonia rate-ratio bands (Thomas et al., 2015).

    These are visualization thresholds, NOT validated clinical, DOH or WHO
    thresholds; values depend on the reference population and reporting quality.
    """
    if incidence is None:
        return "Unavailable", None
    if cases == 0:
        return "No cases", 0.0 if reference and reference > 0 else None
    if reference is None or reference <= 0:
        return "Unavailable", None
    ratio = incidence / reference
    if ratio < LOW_UPPER:
        level = "Low"
    elif ratio < MODERATE_UPPER:
        level = "Moderate"
    else:
        level = "High"
    return level, ratio


def build_incidence_rows(catalog: dict, chosen: list[str],
                         current: dict, previous: dict) -> tuple[list[dict], dict]:
    """Make map rows and a pooled reference based on valid observed barangays.

    The reference is calculated using the sum of covered population denominators
    and matching numerator counts, NOT the arithmetic mean of barangay rates.
    Only areas with valid, unique PSGC codes and 2024 populations qualify.
    """
    populations: dict[str, dict | None] = {}
    problems: list[str] = []
    for code in chosen:
        try:
            populations[code] = get_barangay_population(code)
        except (requests.RequestException, ValueError) as exc:
            populations[code] = None
            problems.append(f"{catalog[code].get('barangay') or code}: {exc}")

    good = {code: pop for code, pop in populations.items() if pop is not None}
    # Prevent one historical code mapping and current code mapping to same barangay.
    canonical_seen: set[str] = set()
    for key, info in list(good.items()):
        canonical = info["code"]
        if canonical in canonical_seen:
            del good[key]
            populations[key] = None
            problems.append(f"{key}: duplicate canonical PSGC barangay mapping")
        else:
            canonical_seen.add(canonical)

    total_population = sum(info["population"] for info in good.values())
    counted_cases = sum(int(current.get(key, 0)) for key in good)
    reference = (counted_cases / total_population * 100_000) if total_population else None

    rows = []
    for key in chosen:
        item = catalog[key]
        cases, prior = int(current.get(key, 0)), int(previous.get(key, 0))
        pop_record = good.get(key)
        pop = pop_record["population"] if pop_record else None
        incidence = (cases / pop * 100_000) if pop else None # Formula: (Confirmed Pneumonia Cases / Barangay Population ) x 100,000
        label, ratio = classify_relative_incidence(cases, incidence, reference)
        barangay_name = f"{item.get('barangay','')} — {item.get('city','')}, {item.get('province','')}"
        rows.append({
            "Barangay": barangay_name,
            "Recorded cases": cases,
            "Population (2024)": pop,
            "Incidence / 100k": round(incidence, 2) if incidence is not None else None,
            "Relative rate ratio": round(ratio, 3) if ratio is not None else None,
            "Incidence level": label,
            "Previous month": prior,
            "Change (%)": round((cases - prior) * 100 / prior, 1) if prior else None,
            "Latitude (approx.)": item.get("latitude"),
            "Longitude (approx.)": item.get("longitude"),
            "Barangay ID": key,
        })
    rows.sort(key=lambda x: (x["Incidence / 100k"] is None,
                             -(x["Incidence / 100k"] or 0), x["Barangay"]))
    metadata = {
        "reference_incidence": reference,
        "covered_population": total_population,
        "covered_cases": counted_cases,
        "covered_barangays": len(good),
        "unavailable_barangays": len(chosen) - len(good),
        "errors": problems,
        "census_year": CENSUS_YEAR,
    }
    return rows, metadata
