# LUNGSIGHT_AUTO_COORDS_PATCH_20261126
"""PSGC-first approximate barangay geocoding for LungSightAI.

Only public geographic names are transmitted to Geoapify.
Coordinates represent approximate barangay references, never patient homes.
"""
from __future__ import annotations

import logging
import math
import os
import re
import unicodedata
from pathlib import Path
from threading import Lock

import requests
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)

LOGGER = logging.getLogger(__name__)
GEOAPIFY_URL = "https://api.geoapify.com/v1/geocode/search"
_SUCCESS_CACHE = {}
_CACHE_LOCK = Lock()


def _normalize(value):
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def _norm_city(value):
    value = _normalize(value)
    if value.startswith("city of "):
        value = value[8:]
    if value.endswith(" city"):
        value = value[:-5]
    return value


def _norm_barangay(value):
    return re.sub(r"^(?:barangay|brgy|brg)\s+", "", _normalize(value))


def _valid_coords(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    return (math.isfinite(lat) and math.isfinite(lon)
            and 4.0 <= lat <= 22.0 and 116.0 <= lon <= 127.0)


def _api_key():
    key = (os.getenv("LUNGSIGHT_GEOAPIFY_API_KEY") or os.getenv("GEOAPIFY_API_KEY") or "").strip()
    if key:
        return key
    try:
        import streamlit as st
        return str(st.secrets.get("LUNGSIGHT_GEOAPIFY_API_KEY") or st.secrets.get("GEOAPIFY_API_KEY") or "").strip()
    except Exception:
        return ""


def geocoding_configured():
    return bool(_api_key())


def _candidate_matches(props, barangay, city, province):
    if _normalize(props.get("country_code")) not in ("ph", "philippines"):
        return False
    result_type = _normalize(props.get("result_type"))
    expected_barangay = _norm_barangay(barangay)
    expected_city = _norm_city(city)
    if not expected_barangay or not expected_city:
        return False
    barangay_types = {"suburb", "district", "city district", "neighbourhood",
                      "quarter", "locality", "village", "hamlet"}
    if result_type in barangay_types:
        barangay_terms = {_norm_barangay(props.get(field)) for field in (
            "name", "suburb", "district", "city_district", "neighbourhood",
            "quarter", "locality", "village", "hamlet")}
        city_terms = {_norm_city(props.get(field)) for field in ("city", "town", "municipality")}
        if expected_barangay not in barangay_terms or expected_city not in city_terms:
            return False
    elif result_type == "city":
        if _norm_barangay(props.get("name")) != expected_barangay:
            return False
        if _norm_barangay(props.get("city")) != expected_barangay:
            return False
        if _norm_city(props.get("county")) != expected_city:
            return False
        if _norm_city(barangay) == expected_city:
            return False
        if not province or _normalize(props.get("state")) != _normalize(province):
            return False
    else:
        return False
    explicit_province = props.get("province")
    if explicit_province and province and _normalize(explicit_province) != _normalize(province):
        return False
    return _valid_coords(props.get("lat"), props.get("lon"))


def _reference_codes(result):
    """Extract possible 10-digit PSGC references, preserving leading zeros."""
    refs = [result.get("ref")]
    other_names = result.get("other_names")
    if isinstance(other_names, dict):
        refs.append(other_names.get("ref"))
    return {str(ref).strip() for ref in refs
            if re.fullmatch(r"[0-9]{10}", str(ref or "").strip())}


def _geocode_api_cached(barangay, city, province, api_key, psgc_barangay_code=None):
    """Prefer exact PSGC references; cache only successful resolutions."""
    if not all((barangay, city, api_key)):
        return None
    expected_code = str(psgc_barangay_code or "").strip()
    if expected_code and not re.fullmatch(r"[0-9]{10}", expected_code):
        return None
    cache_key = (barangay, city, province, api_key, expected_code)
    with _CACHE_LOCK:
        if cache_key in _SUCCESS_CACHE:
            return dict(_SUCCESS_CACHE[cache_key])
    city_name = str(city).strip()
    city_base = _norm_city(city_name)
    # Prefer the PSGC name; then try bare city name (e.g., "Mandaue"),
    # followed by "Mandaue City" for Geoapify's differing naming conventions.
    variants = [city_name, city_base.title(), city_base.title() + " City"]
    city_variants = list(dict.fromkeys(v for v in variants if v))
    try:
        # Do not allow any one failing query to silence another unambiguous
        # geographic match. Query ONLY the public barangay/city/province.
        for variant in city_variants:
            query = ", ".join(part for part in (
                barangay, variant, province, "Philippines") if part)
            response = requests.get(
                GEOAPIFY_URL,
                params={"text": query, "filter": "countrycode:ph", "format": "json",
                        "limit": 8, "apiKey": api_key},
                timeout=(5, 15),
            )
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results", []) if isinstance(payload, dict) else []
            if not isinstance(results, list):
                continue
            valid = [r for r in results if isinstance(r, dict)
                     and _candidate_matches(r, barangay, city, province)]
            if expected_code:
                valid = [r for r in valid if not _reference_codes(r)
                         or _reference_codes(r) == {expected_code}]
                exact = [r for r in valid if _reference_codes(r) == {expected_code}]
                if exact:
                    valid = exact
            unique = {(round(float(r["lat"]), 5), round(float(r["lon"]), 5))
                      for r in valid}
            # Multiple plausible points are ambiguous: do not guess, and do
            # not turn an amenity, school or road into a barangay point.
            if len(unique) > 1:
                LOGGER.warning("Ambiguous barangay geocoding: %s, %s, PSGC=%s, candidates=%s",
                               barangay, city, expected_code, len(unique))
                return None
            if len(unique) == 1:
                lat, lon = next(iter(unique))
                point = {"latitude": lat, "longitude": lon,
                         "location_precision": "barangay", "source": "geoapify"}
                with _CACHE_LOCK:
                    if len(_SUCCESS_CACHE) >= 1024:
                        _SUCCESS_CACHE.pop(next(iter(_SUCCESS_CACHE)), None)
                    _SUCCESS_CACHE[cache_key] = point
                return dict(point)
        LOGGER.warning("Unresolved barangay geocoding: %s, %s, PSGC=%s",
                       barangay, city, expected_code)
        return None
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        LOGGER.warning("Geocoding unavailable for %s, %s: %s", barangay, city, type(exc).__name__)
        return None


def geocode_barangay(barangay, city, province, psgc_barangay_code=None):
    """Geocode a barangay with an optional PSGC code (legacy calls supported)."""
    key = _api_key()
    if not key:
        return None
    return _geocode_api_cached(str(barangay or "").strip(), str(city or "").strip(),
                               str(province or "").strip(), key, psgc_barangay_code)


def lookup_existing_coordinates(psgc_barangay_code, db=None):
    """Reuse a single consistent stored barangay reference by PSGC code."""
    code = str(psgc_barangay_code or "").strip()
    if not re.fullmatch(r"[0-9]{10}", code):
        return None
    if db is None:
        from backend.supabase_client import admin_supabase
        db = admin_supabase
    values = set()
    offset = 0
    while True:
        batch = (db.table("patients")
                 .select("latitude,longitude,location_precision")
                 .eq("psgc_barangay_code", code)
                 .order("patient_id")
                 .range(offset, offset + 999).execute().data or [])
        for row in batch:
            if row.get("location_precision") == "barangay" and _valid_coords(row.get("latitude"), row.get("longitude")):
                values.add((round(float(row["latitude"]), 5), round(float(row["longitude"]), 5)))
        if len(batch) < 1000:
            break
        offset += len(batch)
    if len(values) > 1:
        raise ValueError(f"Conflicting stored barangay reference points for PSGC {code}")
    if not values:
        return None
    lat, lon = next(iter(values))
    return {"latitude": lat, "longitude": lon, "location_precision": "barangay", "source": "existing_psgc"}


def resolve_barangay_coordinates(psgc_barangay_code, barangay, city, province,
                                 *, db=None, allow_api=True):
    """Reuse a PSGC-matched point or request a PSGC-aware provider lookup."""
    code = str(psgc_barangay_code or "").strip()
    if not re.fullmatch(r"[0-9]{10}", code) or not all((barangay, city)):
        return None
    existing = lookup_existing_coordinates(code, db=db)
    if existing:
        return existing
    if allow_api:
        return geocode_barangay(barangay, city, province, psgc_barangay_code=code)
    return None


def prepare_patient_coordinates(patient_data, previous=None, *, db=None):
    """Keep valid same-barangay points; clear stale points on relocation."""
    data = dict(patient_data)
    current_code = str(data.get("psgc_barangay_code") or "").strip()
    former_code = str((previous or {}).get("psgc_barangay_code") or "").strip()
    if not re.fullmatch(r"[0-9]{10}", current_code):
        data.update(latitude=None, longitude=None, location_precision=None)
        return data
    if previous is not None and former_code == current_code:
        if (previous.get("location_precision") == "barangay"
                and _valid_coords(previous.get("latitude"), previous.get("longitude"))):
            data.update(latitude=float(previous["latitude"]), longitude=float(previous["longitude"]),
                        location_precision="barangay")
            return data
    data.update(latitude=None, longitude=None, location_precision=None)
    return enrich_patient_coordinates(data, db=db)


def enrich_patient_coordinates(patient_data, *, db=None):
    """Failure-tolerant synchronous enrichment at patient save time."""
    data = dict(patient_data)
    if not data.get("psgc_barangay_code"):
        return data
    if (data.get("location_precision") == "barangay"
            and _valid_coords(data.get("latitude"), data.get("longitude"))):
        return data
    data.update(latitude=None, longitude=None, location_precision=None)
    try:
        point = resolve_barangay_coordinates(
            data.get("psgc_barangay_code"), data.get("barangay"),
            data.get("city"), data.get("province"), db=db)
        if point:
            data.update({k: point[k] for k in ("latitude", "longitude", "location_precision")})
    except Exception as exc:
        LOGGER.warning("Nonfatal barangay location enrichment failure: %s", type(exc).__name__)
    return data
