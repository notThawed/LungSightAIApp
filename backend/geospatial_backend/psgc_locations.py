# LUNGSIGHT_PSGC_NO_MANUAL_GEO_V2
"""LungSight Philippine Standard Geographic Code (PSGC) address selectors.

PSGC Cloud is a third-party public reference service. No patient or user
information is sent to it: requests contain only geographic admin codes.
"""
from __future__ import annotations

from urllib.parse import quote
import requests
import streamlit as st

BASE = "https://psgc.cloud/api/v2"


@st.cache_data(ttl=86400, show_spinner=False)
def _fetch(path: str):
    url = f"{BASE}/{path}"
    response = requests.get(url, timeout=(5, 25), headers={"Accept": "application/json"})
    response.raise_for_status()
    payload = response.json()
    records = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError(f"Unexpected PSGC response from {path}")
    return [row for row in records if isinstance(row, dict) and row.get("code") and row.get("name")]


def _pathcode(code):
    return quote(str(code), safe="")


def _select(label, rows, key, previous=None):
    values = [None, *rows]
    selected = next((i for i, row in enumerate(values) if row is not None and str(row["code"]) == str(previous)), 0)
    return st.selectbox(
        label, values, index=selected, key=key,
        format_func=lambda row: row["name"] if row is not None else "Select a location...",
    )


def choose_psgc_location(prefix: str, existing: dict | None = None):
    """Show all address inputs immediately; populate cascading choices as selected."""
    existing = existing or {}
    user = "user_address" in existing or "user_psgc_region_code" in existing
    def old(field):
        return existing.get(("user_" if user else "") + field)

    region_code = existing.get("user_psgc_region_code" if user else "psgc_region_code")
    province_code = existing.get("user_psgc_province_code" if user else "psgc_province_code")
    city_code = existing.get("user_psgc_city_code" if user else "psgc_city_code")
    barangay_code = existing.get("user_psgc_barangay_code" if user else "psgc_barangay_code")
    current_address = existing.get("user_address" if user else "address")
    if current_address:
        st.caption("Previously saved address: " + str(current_address))

    def pick(label, rows, key, previous=None, disabled=False, placeholder="Select a location..."):
        options = [None, *rows]
        # Reset descendants when a parent changes, avoiding stale PSGC codes.
        valid_codes = {str(row["code"]) for row in rows}
        if key in st.session_state and st.session_state[key] is not None:
            if str(st.session_state[key].get("code")) not in valid_codes:
                del st.session_state[key]
        index = next((i for i, row in enumerate(options) if row is not None and str(row["code"]) == str(previous)), 0)
        return st.selectbox(label, options, index=index, key=key, disabled=disabled,
            format_func=lambda row: row["name"] if row else placeholder)

    try:
        regions = _fetch("regions")
        region = pick("Region *", regions, prefix + "region", region_code)
        provinces = _fetch(f"regions/{_pathcode(region['code'])}/provinces") if region else []
        independent = {"code": "__independent__", "name": "Independent city / NCR (no province)"}
        province = pick("Province / Administrative area *", [*provinces, independent] if region else [],
                        prefix + "province", province_code, disabled=not bool(region),
                        placeholder="Select a region first...")
        cities = []
        if region and province:
            if province["code"] == "__independent__":
                cities = _fetch(f"regions/{_pathcode(region['code'])}/cities-municipalities")
                def no_province(c):
                    p = c.get("province")
                    return not (p.get("code") or p.get("name")) if isinstance(p, dict) else not bool(p)
                cities = [c for c in cities if no_province(c)] or cities
            else:
                cities = _fetch(f"provinces/{_pathcode(province['code'])}/cities-municipalities")
        city = pick("City / Municipality *", cities, prefix + "city", city_code,
                    disabled=not bool(province), placeholder="Select a province first...")
        barangays = _fetch(f"cities-municipalities/{_pathcode(city['code'])}/barangays") if city else []
        barangay = pick("Barangay *", barangays, prefix + "barangay", barangay_code,
                        disabled=not bool(city), placeholder="Select a city first...")
    except (requests.RequestException, ValueError) as exc:
        st.error(f"Could not load Philippine locations: {exc}")
        region = province = city = barangay = None

    # These fields must always be visible, including before Region is chosen.
    purok = st.text_input("Purok / Sitio (optional)", value=old("purok") or "",
                          key=prefix + "purok", placeholder="Enter purok or sitio").strip()
    street = st.text_input("Street (optional)", value=old("street") or "",
                           key=prefix + "street", placeholder="Enter street name").strip()
    details = st.text_input("House number / Building / Landmark (optional)",
                            value=old("address_details") or "", key=prefix + "details",
                            placeholder="House no., unit, building, landmark").strip()
    if not all((region, province, city, barangay)):
        st.caption("Complete Region, Province, City/Municipality, and Barangay to preview and save the address.")
        return None

    province_name = "" if province["code"] == "__independent__" else province["name"]
    parts = [details, street, purok, barangay["name"], city["name"], province_name, region["name"], "Philippines"]
    address = ", ".join(part for part in parts if part)
    st.caption("Address preview: " + address)
    return {
        "region": region["name"], "province": province_name,
        "city": city["name"], "barangay": barangay["name"],
        "psgc_region_code": str(region["code"]),
        "psgc_province_code": None if province["code"] == "__independent__" else str(province["code"]),
        "psgc_city_code": str(city["code"]), "psgc_barangay_code": str(barangay["code"]),
        "purok": purok or None, "street": street or None,
        "address_details": details or None, "address": address,
    }

def patient_location_payload(location, existing=None):
    """Preserve validated existing approximate coordinates only if same barangay."""
    existing = existing or {}
    same = str(existing.get("psgc_barangay_code") or "") == str(location["psgc_barangay_code"])
    coordinates_ok = same and existing.get("location_precision") == "barangay"
    return {
        **location,
        "latitude": existing.get("latitude") if coordinates_ok else None,
        "longitude": existing.get("longitude") if coordinates_ok else None,
        "location_precision": "barangay" if coordinates_ok and existing.get("latitude") is not None and existing.get("longitude") is not None else None,
    }


def user_location_payload(location):
    return {
        "user_region": location["region"],
        "user_province": location["province"],
        "user_city": location["city"],
        "user_barangay": location["barangay"],
        "user_psgc_region_code": location["psgc_region_code"],
        "user_psgc_province_code": location["psgc_province_code"],
        "user_psgc_city_code": location["psgc_city_code"],
        "user_psgc_barangay_code": location["psgc_barangay_code"],
        "user_purok": location["purok"],
        "user_street": location["street"],
        "user_address_details": location["address_details"],
    }
