import streamlit as st

from pathlib import Path

from backend.backend_utils.hospital_utils import (
    get_hospital_by_id,
    get_user_profile_by_id,
    update_hospital_information,
    update_hospital_logo_url,
    update_profile_picture_url,
    complete_hospital_setup,
)
from backend.backend_utils.subscription_utils import get_hospital_subscription_details
from backend.backend_utils.storage_utils import upload_hospital_logo, upload_profile_picture

from backend.geospatial_backend.geocode_utils import (
    geocode_address,
    REQUEST_INTERVAL_SECONDS,
)

from streamlit_app.components.map import (
    render_hospital_map,
)
from streamlit_app.components.ui import refresh_button

from datetime import datetime, timezone
import time
import html
import calendar
import re
import requests
from datetime import date

from backend.supabase_client import admin_supabase


# ============================================================
# CSS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SETUP_WIZARD_CSS_PATH = (
    PROJECT_ROOT / "shared" / "theme" / "css_content" / "setup_wizard.css"
)


def load_setup_wizard_css():
    if SETUP_WIZARD_CSS_PATH.exists():
        css = SETUP_WIZARD_CSS_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ============================================================
# STEPS
# ============================================================

SETUP_STEPS = [
    (
        "Hospital",
        "Hospital Profile",
        "Review your hospital's information and upload your hospital logo.",
        "local_hospital",
    ),
    (
        "Administrator",
        "Your Administrator Account",
        "Review your administrator information and upload your profile picture.",
        "manage_accounts",
    ),
    (
        "Subscription",
        "Your Subscription",
        "Here's the LungSight plan your hospital is subscribed to.",
        "credit_card",
    ),
    (
        "Review",
        "Review & Confirm",
        "Review your setup information and agree to the Data Processing terms to activate your account.",
        "fact_check",
    ),
]

HOSPITAL_TYPES = [
    "Government Hospital",
    "Private Hospital",
    "Medical Center",
    "Other",
]


# ============================================================
# SMALL HELPERS
# ============================================================

def safe(value):
    return html.escape(str(value).strip()) if value is not None and str(value).strip() else "—"


def peso(amount):
    return f"₱{float(amount or 0):,.2f}"


def limit_text(value):
    if value is None:
        return "Unlimited"
    return f"{int(value):,}" if str(value).isdigit() else safe(value)


def full_name_of(person):
    parts = [
        person.get("first_name") or person.get("user_fname"),
        person.get("middle_name") or person.get("user_mname"),
        person.get("last_name") or person.get("user_lname"),
    ]
    return " ".join(part for part in parts if part) or person.get("name") or "—"


def rows_html(rows):
    items = "".join(
        f"<div class='ls-row'><span>{label}</span><b>{safe(value)}</b></div>"
        for label, value in rows
    )
    return f"<div class='ls-rows'>{items}</div>"


def note(text):
    st.markdown(
        f"<div class='ls-note'><span class='ls-note-icon material-symbols-rounded'>info</span>"
        f"<span class='ls-note-text'>{text}</span></div>",
        unsafe_allow_html=True,
    )


def step_header(title, caption, icon):
    st.markdown(
        "<div class='ls-step-header'>"
        "<div class='ls-step-header-icon'>"
        f"<span class='material-symbols-rounded'>{icon}</span>"
        "</div>"
        "<div class='ls-step-header-text'>"
        f"<p class='ls-step-title'>{title}</p>"
        f"<p class='ls-step-caption'>{caption}</p>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def initials_for(name):
    """Return initials for the circular placeholder."""
    words = str(name or "").split()
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][0].upper()
    return (words[0][0] + words[-1][0]).upper()


# ============================================================
# ADMINISTRATOR PROFILE AND PSGC ADDRESS HELPERS
# ============================================================

PSGC_API = "https://psgc.cloud/api/v2"


def _profile_value(profile, *names):
    for name in names:
        value = profile.get(name)
        if value is not None and str(value).strip():
            return value
    return ""


@st.cache_data(ttl=86400, show_spinner=False)
def _psgc_fetch(resource):
    """Public PSGC service; no local geographic tables required."""
    try:
        response = requests.get(f"{PSGC_API}/{resource}", timeout=12)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload
        return payload.get("data", []) if isinstance(payload, dict) else []
    except (requests.RequestException, ValueError):
        return []


def _psgc_options(items):
    options = {}

    for item in items:
        name = item.get("name")
        code = item.get("code")
        if name and code:
            options[f"{name} ({code})"] = item

    return options


def _psgc_select(label, items, selected_code, key):
    options = _psgc_options(items)
    labels = ["Select a location..."] + list(options)

    index = next(
        (
            i
            for i, text in enumerate(labels)
            if selected_code and text.endswith(f"({selected_code})")
        ),
        0,
    )

    choice = st.selectbox(label, labels, index=index, key=key)
    return options.get(choice, {})


def _date_value(raw):
    try:
        return date.fromisoformat(str(raw)[:10])
    except (ValueError, TypeError):
        return date(1990, 1, 1)


def _save_administrator_profile(user_id, values):
    """Update only columns actually present in user_profiles."""
    try:
        current = (admin_supabase.table("user_profiles")
                   .select("*").eq("user_id", user_id).single().execute().data or {})
        mapping = {
            "employee_id": ("employee_id",),
            "first_name": ("user_fname", "first_name"),
            "middle_name": ("user_mname", "middle_name"),
            "last_name": ("user_lname", "last_name"),
            "date_of_birth": ("date_of_birth", "birthdate", "user_birthdate"),
            "sex": ("sex", "user_sex"),
            "contact_number": ("user_contact_number", "contact_number"),
            "address": ("user_address", "address", "residential_address"),
            "region": ("user_region", "region"),
            "province": ("user_province", "province"),
            "city": ("user_city", "city"),
            "barangay": ("user_barangay", "barangay"),
            "purok": ("user_purok", "purok"),
            "street": ("user_street", "street"),
            "address_details": ("user_address_details", "address_details"),
            "psgc_region_code": ("user_psgc_region_code", "psgc_region_code"),
            "psgc_province_code": ("user_psgc_province_code", "psgc_province_code"),
            "psgc_city_code": ("user_psgc_city_code", "psgc_city_code"),
            "psgc_barangay_code": ("user_psgc_barangay_code", "psgc_barangay_code"),
        }
        payload = {}
        for source, candidates in mapping.items():
            for column in candidates:
                if column in current:
                    payload[column] = values.get(source) if values.get(source) is not None else None
                    break
        if not payload:
            return False, "No supported administrator profile columns were found."
        (admin_supabase.table("user_profiles").update(payload)
         .eq("user_id", user_id).execute())
        return True, "Administrator profile saved."
    except Exception as exc:
        return False, f"Unable to save administrator details: {exc}"


def _administrator_address_form(profile):
    """Use the same PSGC Cloud v2 hierarchy as Manage Users.

    The address selections are shown in a compact grid. Parent selections
    automatically reset invalid child selections when changed.
    """
    section_heading("location_on", "Residential Address", "Philippine Standard Geographic Code (PSGC)")

    old_address = _profile_value(profile, "user_address", "address", "residential_address")
    if old_address:
        st.caption(f"Previously saved: {old_address}")

    try:
        regions = _psgc_fetch("regions")
    except Exception:
        regions = []

    if not regions:
        st.warning("The PSGC service is unavailable. Your saved address remains unchanged.")
        return {"address": old_address} if old_address else None

    def select_place(label, rows, key, previous_code="", disabled=False):
        choices = [None] + rows
        valid = {str(r.get("code")) for r in rows}
        if key in st.session_state:
            previous = st.session_state[key]
            if previous is not None and str(previous.get("code")) not in valid:
                del st.session_state[key]
        index = next(
            (idx for idx, item in enumerate(choices) if item and
             str(item.get("code")) == str(previous_code)), 0
        )
        return st.selectbox(
            label,
            choices,
            key=key,
            index=index,
            disabled=disabled,
            format_func=lambda item: item.get("name", "") if item else "Select a location...",
        )

    r_col, p_col = st.columns(2, gap="small")
    with r_col:
        region = select_place(
            "Region *", regions, "setup_admin_region",
            _profile_value(profile, "user_psgc_region_code", "psgc_region_code"),
        )

    region_code = region["code"] if region else None
    provinces = _psgc_fetch(f"regions/{region_code}/provinces") if region else []
    independent = {"code": "__independent__", "name": "Independent city / NCR (no province)"}

    with p_col:
        province = select_place(
            "Province / Administrative area *",
            [*provinces, independent] if region else [],
            "setup_admin_province",
            _profile_value(profile, "user_psgc_province_code", "psgc_province_code")
            or ("__independent__" if region and not provinces else ""),
            disabled=not bool(region),
        )

    cities = []
    if region and province:
        if province["code"] == "__independent__":
            cities = _psgc_fetch(f"regions/{region_code}/cities-municipalities")
        else:
            cities = _psgc_fetch(f"provinces/{province['code']}/cities-municipalities")

    c_col, b_col = st.columns(2, gap="small")
    with c_col:
        city = select_place(
            "City / Municipality *", cities, "setup_admin_city",
            _profile_value(profile, "user_psgc_city_code", "psgc_city_code"),
            disabled=not bool(province),
        )

    barangays = _psgc_fetch(f"cities-municipalities/{city['code']}/barangays") if city else []
    with b_col:
        barangay = select_place(
            "Barangay *", barangays, "setup_admin_barangay",
            _profile_value(profile, "user_psgc_barangay_code", "psgc_barangay_code"),
            disabled=not bool(city),
        )

    a, b, c = st.columns(3, gap="small")
    with a:
        purok = st.text_input(
            "Purok / Sitio", value=_profile_value(profile, "user_purok", "purok"),
            key="setup_admin_purok", placeholder="Optional",
        ).strip()
    with b:
        street = st.text_input(
            "Street", value=_profile_value(profile, "user_street", "street"),
            key="setup_admin_street", placeholder="Optional",
        ).strip()
    with c:
        details = st.text_input(
            "House No. / Landmark",
            value=_profile_value(profile, "user_address_details", "address_details"),
            key="setup_admin_details", placeholder="Optional",
        ).strip()

    if not all((region, province, city, barangay)):
        st.caption("Complete all four location selections to preview your address.")
        return None

    province_name = "" if province["code"] == "__independent__" else province["name"]
    parts = [details, street, purok, barangay["name"], city["name"],
             province_name, region["name"], "Philippines"]
    address = ", ".join(part for part in parts if part)
    st.markdown(
        "<div class='ls-address-preview'>"
        "<span class='material-symbols-rounded'>location_on</span>"
        f"<span>{html.escape(address)}</span></div>",
        unsafe_allow_html=True,
    )

    return {
        "address": address,
        "region": region["name"],
        "province": province_name,
        "city": city["name"],
        "barangay": barangay["name"],
        "purok": purok or None,
        "street": street or None,
        "address_details": details or None,
        "psgc_region_code": str(region["code"]),
        "psgc_province_code": (
            str(province["code"]) if province["code"] != "__independent__" else None
        ),
        "psgc_city_code": str(city["code"]),
        "psgc_barangay_code": str(barangay["code"]),
    }

def section_heading(icon, title, subtitle=""):
    """Render one line of HTML; never indent the string in Markdown."""
    st.markdown(
        "<div class='ls-ui-section'>"
        f"<span class='material-symbols-rounded'>{html.escape(icon)}</span>"
        "<div class='ls-ui-section-copy'>"
        f"<strong>{html.escape(title)}</strong>"
        f"<small>{html.escape(subtitle)}</small>"
        "</div></div>",
        unsafe_allow_html=True,
    )


def information_rows_html(rows):
    parts = []
    for label, value in rows:
        parts.append(
            "<div class='ls-info-line'>"
            f"<span>{html.escape(str(label))}</span>"
            f"<strong>{safe(value)}</strong>"
            "</div>"
        )
    return "<div class='ls-info-list'>" + "".join(parts) + "</div>"


def wizard_date_parts(value, prefix="setup_admin_birth"):
    """Birthdate selectors cover 1900-current year without a limited picker."""
    initial = _date_value(value)
    today = date.today()
    if initial > today or initial.year < 1900:
        initial = date(1990, 1, 1)

    months = list(range(1, 13))
    years = list(range(today.year, 1899, -1))
    cols = st.columns([1.3, 0.8, 1], gap="small")

    with cols[0]:
        month = st.selectbox(
            "Birth month *", months,
            index=initial.month - 1,
            format_func=lambda m: calendar.month_name[m],
            key=f"{prefix}_month",
        )
    with cols[2]:
        year = st.selectbox(
            "Birth year *", years,
            index=years.index(initial.year),
            key=f"{prefix}_year",
        )

    days = calendar.monthrange(year, month)[1]
    with cols[1]:
        day = st.selectbox(
            "Day *", list(range(1, days + 1)),
            index=min(initial.day, days) - 1,
            key=f"{prefix}_day",
        )

    birthday = date(year, month, day)
    if birthday > today:
        st.warning("Birthdate cannot be in the future.")
        return None
    return birthday


# ============================================================
# IMAGE PREVIEWS
# ============================================================

def render_image_preview(
    key,
    image_url=None,
    shape="square",
    placeholder_icon=None,
    placeholder_initials=None,
    caption=None,
):
    wrapper_class = (
        "ls-preview-square"
        if shape == "square"
        else "ls-preview-circle"
    )

    with st.container(key=key):

        if image_url:
            st.image(image_url, use_container_width=True)

        elif placeholder_icon:
            st.markdown(
                f"<div class='ls-preview-empty {wrapper_class}--empty'>"
                f"<span class='material-symbols-rounded'>{placeholder_icon}</span>"
                "</div>",
                unsafe_allow_html=True,
            )

        elif placeholder_initials:
            st.markdown(
                f"<div class='ls-preview-empty {wrapper_class}--empty'>"
                f"<span class='ls-preview-initials'>{safe(placeholder_initials)}</span>"
                "</div>",
                unsafe_allow_html=True,
            )

    if caption:
        st.markdown(
            f"<p class='ls-preview-caption'>{caption}</p>",
            unsafe_allow_html=True,
        )


def render_uploaded_preview(key, uploaded_file, shape="square", caption=None):
    with st.container(key=key):
        st.image(uploaded_file, use_container_width=True)

    if caption:
        st.markdown(
            f"<p class='ls-preview-caption'>{caption}</p>",
            unsafe_allow_html=True,
        )


def render_review_avatar(key, image_url, shape="square"):
    with st.container(key=key):
        if image_url:
            st.image(image_url, use_container_width=True)
        else:
            st.markdown(
                "<div class='ls-empty-review-avatar'>"
                "<span class='material-symbols-rounded'>account_circle</span>"
                "</div>",
                unsafe_allow_html=True,
            )

# ============================================================
# GEOCODING
# ============================================================

def _geocode_candidates(address):
    if not address:
        return []

    cleaned = address.strip()
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]

    candidates = [cleaned]

    if len(parts) >= 2:
        candidates.append(", ".join(parts[1:]))

    if len(parts) >= 2:
        candidates.append(", ".join(parts[-2:]))

    if len(parts) >= 1:
        candidates.append(parts[-1])

    if len(parts) == 1:
        candidates.append(f"{parts[0]}, Philippines")

    seen = set()
    unique = []
    for c in candidates:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return unique


def _geocode_once(hospital_id, address, force=False):
    if not hospital_id or not address:
        return None

    cache_key = f"setup_geocode_{hospital_id}"

    if not force and cache_key in st.session_state:
        cached = st.session_state[cache_key]
        if cached is False:
            return None
        return cached

    for index, candidate in enumerate(_geocode_candidates(address)):

        if index > 0:
            time.sleep(REQUEST_INTERVAL_SECONDS)

        try:
            coords = geocode_address(candidate)

            if coords:
                st.session_state[cache_key] = coords
                st.session_state[
                    f"setup_geocode_source_{hospital_id}"
                ] = candidate
                return coords

        except Exception as exc:
            print(
                f"Geocode candidate failed "
                f"('{candidate}'): {exc}"
            )

    st.session_state[cache_key] = False
    return None


# ============================================================
# ADDRESS CONFIRMATION STATE
# ============================================================

def _confirmed_key(hospital_id):
    return f"setup_address_confirmed_{hospital_id}"


def _address_snapshot_key(hospital_id):
    return f"setup_address_snapshot_{hospital_id}"


def _is_address_confirmed(hospital_id):
    return bool(
        st.session_state.get(_confirmed_key(hospital_id), False)
    )


def _set_address_confirmed(hospital_id, value):
    st.session_state[_confirmed_key(hospital_id)] = bool(value)


def _save_address_confirmation(
    hospital_id,
    lat,
    lon,
    confirmed,
    address_text=None,
):
    if not hospital_id:
        return False

    try:
        payload = {
            "address_confirmed": bool(confirmed),
            "address_confirmed_at": (
                datetime.now(timezone.utc).isoformat()
                if confirmed
                else None
            ),
        }

        if lat is not None and lon is not None:
            payload["latitude"] = float(lat)
            payload["longitude"] = float(lon)

        if address_text is not None:
            payload["address"] = address_text.strip()

        (
            admin_supabase
            .table("hospitals")
            .update(payload)
            .eq("hospital_id", hospital_id)
            .execute()
        )

        return True

    except Exception as exc:
        print(
            f"Failed to save address confirmation for "
            f"{hospital_id}: {exc}"
        )
        return False


def _resolve_current_coords(hospital, address_text):
    hospital_id = hospital.get("hospital_id")

    address_changed = bool(
        st.session_state.get(
            f"setup_address_changed_{hospital_id}",
            False,
        )
    )

    if address_changed:
        coords = _geocode_once(hospital_id, address_text)
        if coords:
            return coords
        return None, None

    if hospital.get("address_confirmed", False):
        lat = hospital.get("latitude")
        lon = hospital.get("longitude")
        if lat is not None and lon is not None:
            return lat, lon

    coords = _geocode_once(hospital_id, address_text)
    if coords:
        return coords

    return None, None


# ============================================================
# WIZARD STATE CLEANUP
# ============================================================

def clear_wizard_map_state(hospital_id=None):
    keys_to_clear = [
        "setup_step",
        "setup_final_confirmation",
        "setup_policy_agreement",
        "subscription_context",
        "grace_info",
    ]

    for k in keys_to_clear:
        st.session_state.pop(k, None)

    if hospital_id:
        keys_to_clear_for_hospital = [
            f"setup_geocode_{hospital_id}",
            f"setup_geocode_source_{hospital_id}",
            f"setup_address_confirmed_{hospital_id}",
            f"setup_address_snapshot_{hospital_id}",
            f"setup_address_changed_{hospital_id}",
            f"setup_map_{hospital_id}",
            f"setup_fix_hint_{hospital_id}",
        ]

        for k in keys_to_clear_for_hospital:
            st.session_state.pop(k, None)

    else:
        prefixes = (
            "setup_geocode_",
            "setup_geocode_source_",
            "setup_address_confirmed_",
            "setup_address_snapshot_",
            "setup_address_changed_",
            "setup_fix_hint_",
            "setup_map_",
        )

        for key in list(st.session_state.keys()):
            if key.startswith(prefixes):
                st.session_state.pop(key, None)


# ============================================================
# ADDRESS MAP PREVIEW
# ============================================================

def render_address_map_preview(hospital, address_text):
    if not hospital:
        return

    hospital_id = hospital.get("hospital_id")

    if not hospital_id:
        return

    if _confirmed_key(hospital_id) not in st.session_state:
        st.session_state[_confirmed_key(hospital_id)] = bool(
            hospital.get("address_confirmed", False)
        )

    snapshot_key = _address_snapshot_key(hospital_id)
    prev_snapshot = st.session_state.get(snapshot_key)

    saved_address = (hospital.get("address") or "").strip()
    current_address = (address_text or "").strip()

    if current_address != saved_address:
        st.session_state[
            f"setup_address_changed_{hospital_id}"
        ] = True

    if prev_snapshot is not None and prev_snapshot != address_text:
        _set_address_confirmed(hospital_id, False)

        st.session_state.pop(
            f"setup_geocode_{hospital_id}",
            None,
        )
        st.session_state.pop(
            f"setup_geocode_source_{hospital_id}",
            None,
        )

    st.session_state[snapshot_key] = address_text

    header_col, button_col = st.columns(
        [5, 1.6],
        vertical_alignment="center",
    )

    with button_col:
        reload_clicked = st.button(
            "Re-locate",
            key=f"setup_relocate_{hospital_id}",
            icon=":material/refresh:",
            width="stretch",
            help="Search for the address again.",
        )

    if reload_clicked:
        _geocode_once(
            hospital_id,
            address_text,
            force=True,
        )
        _set_address_confirmed(hospital_id, False)
        st.rerun()

    lat, lon = _resolve_current_coords(hospital, address_text)

    if lat is None or lon is None:
        with header_col:
            st.markdown(
                "<div class='ls-map-card'>"
                "<p class='ls-map-header'>"
                "<span class='material-symbols-rounded'>location_off</span>"
                "<span>Location preview</span>"
                "</p>"
                "<p class='ls-map-caption'>"
                "We couldn't locate this address automatically. "
                "Edit the address above and click Re-locate. "
                "You must confirm a location before continuing."
                "</p>"
                "</div>",
                unsafe_allow_html=True,
            )
        return

    confirmed = _is_address_confirmed(hospital_id)

    if confirmed:
        icon = "check_circle"
        caption = "Location confirmed. You can continue."
        card_class = "ls-map-card ls-map-card--ok"
    else:
        icon = "location_on"
        caption = (
            "We located this address here. "
            "Click Re-locate if it looks wrong, then confirm below."
        )
        card_class = "ls-map-card"

    with header_col:
        st.markdown(
            f"<div class='{card_class}'>"
            "<p class='ls-map-header'>"
            f"<span class='material-symbols-rounded'>{icon}</span>"
            "<span>Location preview</span>"
            "</p>"
            f"<p class='ls-map-caption'>{caption}</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    hospital_for_map = {
        "hospital_id": hospital_id,
        "hospital_name": (
            hospital.get("hospital_name") or "Your Hospital"
        ),
        "latitude": float(lat),
        "longitude": float(lon),
    }

    render_hospital_map(
        hospitals=[hospital_for_map],
        selected_id=hospital_id,
        height=300,
        key=f"setup_map_{hospital_id}",
    )

    render_confirm_row(
        hospital_id,
        lat,
        lon,
        confirmed,
        address_text,
    )


def render_confirm_row(
    hospital_id,
    lat,
    lon,
    confirmed,
    address_text,
):
    st.markdown(
        "<p class='ls-confirm-prompt'>"
        "<span class='material-symbols-rounded'>help</span>"
        "<span>Is this the correct location for your hospital?</span>"
        "</p>",
        unsafe_allow_html=True,
    )

    confirm_col, fix_col = st.columns(2)

    with confirm_col:
        if confirmed:
            st.button(
                "Location confirmed",
                key=f"setup_confirm_done_{hospital_id}",
                icon=":material/check_circle:",
                width="stretch",
                disabled=True,
            )
        else:
            if st.button(
                "Yes, this is correct",
                key=f"setup_confirm_{hospital_id}",
                icon=":material/check_circle:",
                type="primary",
                width="stretch",
            ):
                _set_address_confirmed(hospital_id, True)
                _save_address_confirmation(
                    hospital_id,
                    lat,
                    lon,
                    confirmed=True,
                    address_text=address_text,
                )
                st.rerun()

    with fix_col:
        if st.button(
            "No, let me fix it",
            key=f"setup_fix_{hospital_id}",
            icon=":material/edit:",
            width="stretch",
        ):
            _set_address_confirmed(hospital_id, False)

            _save_address_confirmation(
                hospital_id,
                lat,
                lon,
                confirmed=False,
                address_text=address_text,
            )

            st.session_state.pop(
                f"setup_geocode_{hospital_id}",
                None,
            )
            st.session_state.pop(
                f"setup_geocode_source_{hospital_id}",
                None,
            )

            st.session_state[
                f"setup_fix_hint_{hospital_id}"
            ] = True

            st.rerun()

    if st.session_state.pop(
        f"setup_fix_hint_{hospital_id}",
        False,
    ):
        st.info(
            "Edit the address above, then click **Re-locate** "
            "to search again. Confirm the new location when "
            "it looks right."
        )


# ============================================================
# NAVIGATION
# ============================================================

def go_to_step(step):
    st.session_state.setup_step = step
    st.rerun()


def nav_buttons(
    key,
    back_step=None,
    next_label="Continue",
    back_label="Back",
    next_icon=":material/arrow_forward:",
    back_icon=":material/arrow_back:",
):
    if back_step is None:
        next_clicked = st.button(
            next_label,
            type="primary",
            width="stretch",
            key=f"{key}_next",
            icon=next_icon,
        )
        return False, next_clicked

    back_col, next_col = st.columns(2)

    back_clicked = back_col.button(
        back_label,
        width="stretch",
        key=f"{key}_back",
        icon=back_icon,
    )

    next_clicked = next_col.button(
        next_label,
        type="primary",
        width="stretch",
        key=f"{key}_next",
        icon=next_icon,
    )

    if back_clicked:
        go_to_step(back_step)

    return back_clicked, next_clicked


def back_to_login():
    user = get_current_user()

    hospital_id = (
        user.get("hospital_id")
        if user
        else None
    )

    clear_wizard_map_state(hospital_id)

    for key in ("user", "logged_in"):
        st.session_state.pop(key, None)

    st.rerun()


# ============================================================
# INITIALIZE
# ============================================================

def initialize_setup():
    if "setup_step" not in st.session_state:
        st.session_state.setup_step = 0


# ============================================================
# CURRENT USER / HOSPITAL
# ============================================================

def get_current_user():
    return st.session_state.get("user")


def refresh_current_user():
    user = get_current_user()
    if not user:
        return None

    user_id = user.get("user_id")
    if not user_id:
        return user

    profile = get_user_profile_by_id(user_id)
    if not profile:
        return user

    updated_user = {**user, **profile}

    if profile.get("user_fname") is not None:
        updated_user["first_name"] = profile.get("user_fname")
    if profile.get("user_mname") is not None:
        updated_user["middle_name"] = profile.get("user_mname")
    if profile.get("user_lname") is not None:
        updated_user["last_name"] = profile.get("user_lname")
    if profile.get("user_contact_number") is not None:
        updated_user["contact_number"] = profile.get("user_contact_number")
    if profile.get("profile_picture_url") is not None:
        updated_user["profile_picture_url"] = profile.get("profile_picture_url")

    st.session_state.user = updated_user
    return updated_user


def get_current_hospital():
    user = get_current_user()
    if not user:
        return None
    hospital_id = user.get("hospital_id")
    if not hospital_id:
        return None
    return get_hospital_by_id(hospital_id)


def refresh_current_hospital():
    user = get_current_user()
    if not user:
        return None
    hospital_id = user.get("hospital_id")
    if not hospital_id:
        return None
    return get_hospital_by_id(hospital_id)


# ============================================================
# PROGRESS TRACKER
# ============================================================

def render_progress():
    current = st.session_state.setup_step
    total = len(SETUP_STEPS)
    percent = round((current + 1) / total * 100)

    if current + 1 < total:
        up_next = f"Next: {SETUP_STEPS[current + 1][1]}"
    else:
        up_next = "Final step"

    steps_html = ""
    for number, (short_name, _, _, icon) in enumerate(SETUP_STEPS):
        if number < current:
            state, mark = "done", "check"
        elif number == current:
            state, mark = "current", icon
        else:
            state, mark = "todo", icon

        steps_html += (
            f"<div class='ls-step ls-step-{state}'>"
            f"<span class='ls-dot material-symbols-rounded'>{mark}</span>"
            f"<span class='ls-step-name'>{short_name}</span>"
            "</div>"
        )

    st.markdown(
        "<div class='ls-progress'>"
        "<div class='ls-progress-top'>"
        "<div>"
        f"<p class='ls-progress-title'>Step {current + 1} of {total}</p>"
        f"<p class='ls-progress-meta'>{up_next}</p>"
        "</div>"
        f"<div class='ls-progress-percent'>{percent}%"
        "<small>complete</small></div>"
        "</div>"
        f"<div class='ls-bar'><div class='ls-bar-fill' style='width:{percent}%'></div></div>"
        f"<div class='ls-steps'>{steps_html}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# STEP 1 — HOSPITAL PROFILE
# ============================================================

def render_hospital_profile(hospital):
    step_header(*SETUP_STEPS[0][1:])

    current_logo_url = hospital.get("hospital_logo_url")
    logo_col, info_col = st.columns([1, 1.75], gap="medium")

    with logo_col:
        with st.container(key="setup_hospital_logo_card", border=True):
            section_heading("add_photo_alternate", "Hospital Logo", "Shown across LungSight")
            render_image_preview(
                key="setup_logo_preview_current",
                image_url=current_logo_url,
                shape="square",
                placeholder_icon="local_hospital",
            )
            hospital_logo = st.file_uploader(
                "Upload hospital logo",
                type=["png", "jpg", "jpeg", "webp"],
                key="setup_hospital_logo",
                help="PNG, JPG or WEBP, maximum 5 MB.",
            )
            if hospital_logo:
                render_uploaded_preview(
                    key="setup_logo_preview_pending",
                    uploaded_file=hospital_logo,
                    shape="square",
                    caption="New hospital logo (saved when you continue)",
                )

    with info_col:
        with st.container(key="setup_hospital_info_card", border=True):
            section_heading("local_hospital", "Hospital Information", "Verify facility details")
            hospital_name = st.text_input(
                "Hospital name *",
                value=hospital.get("hospital_name", ""),
                key="setup_hospital_name",
            )
            current_type = hospital.get("hospital_type")
            if current_type not in HOSPITAL_TYPES:
                current_type = HOSPITAL_TYPES[0]

            hospital_type = st.selectbox(
                "Hospital type *",
                HOSPITAL_TYPES,
                index=HOSPITAL_TYPES.index(current_type),
                key="setup_hospital_type",
            )
            contact_number = st.text_input(
                "Contact number",
                value=hospital.get("contact_number", "") or "",
                key="setup_hospital_contact",
            )
            email = st.text_input(
                "Hospital email",
                value=hospital.get("email", "") or "",
                key="setup_hospital_email",
            )
            website = st.text_input(
                "Website (optional)",
                value=hospital.get("website", "") or "",
                key="setup_hospital_website",
            )

    address_col, map_col = st.columns([1, 1.2], gap="medium")
    with address_col:
        with st.container(key="setup_hospital_address_card", border=True):
            section_heading("location_on", "Hospital Address", "Verify the address for your facility")
            address = st.text_area(
                "Complete address *",
                value=hospital.get("address", "") or "",
                key="setup_hospital_address",
                height=110,
                help="Include street, barangay, city, province, and Philippines for more accurate mapping.",
            )
            st.caption("Confirm the location on the map before continuing.")

    with map_col:
        with st.container(key="setup_hospital_map_card", border=True):
            section_heading("map", "Location Preview", "Check the exact hospital pin")
            render_address_map_preview(hospital, address)

    note("Please verify the hospital details and map location before continuing.")

    _, next_clicked = nav_buttons(
        "hospital",
        next_label="Save & Continue",
    )

    if not next_clicked:
        return

    hospital_id = hospital.get("hospital_id")

    if not hospital_id:
        st.error("Hospital ID could not be found.")
        return

    if not _is_address_confirmed(hospital_id):
        st.error(
            "Please confirm your hospital's location on the "
            "map before continuing."
        )
        return

    if not hospital_name.strip():
        st.error("Hospital name is required.")
        return

    if not address.strip():
        st.error("Hospital address is required.")
        return

    result = update_hospital_information(
        hospital_id=hospital_id,
        hospital_name=hospital_name,
        hospital_type=hospital_type,
        address=address,
        contact_number=contact_number,
        email=email,
        website=website,
    )

    if not result["success"]:
        st.error(result["message"])
        return

    lat, lon = _resolve_current_coords(hospital, address)

    if lat is None or lon is None:
        st.error(
            "Coordinates could not be determined. "
            "Please locate your hospital on the map first."
        )
        return

    save_ok = _save_address_confirmation(
        hospital_id,
        lat,
        lon,
        confirmed=True,
        address_text=address,
    )

    if not save_ok:
        st.error(
            "Hospital information was saved, but the location "
            "could not be stored. Please try again."
        )
        return

    st.session_state.pop(
        f"setup_address_changed_{hospital_id}",
        None,
    )

    if hospital_logo:
        upload_result = upload_hospital_logo(
            hospital_id=hospital_id,
            file_bytes=hospital_logo.getvalue(),
            file_name=hospital_logo.name,
        )

        if not upload_result["success"]:
            st.error(
                "Hospital information was saved, but the hospital logo "
                f"could not be uploaded: {upload_result['message']}"
            )
            return

        logo_url = upload_result.get("url")
        if not logo_url:
            st.error("Hospital logo was uploaded, but Supabase did not return a public URL.")
            return

        logo_result = update_hospital_logo_url(hospital_id=hospital_id, logo_url=logo_url)
        if not logo_result["success"]:
            st.error(
                "The hospital logo was uploaded, but its database URL "
                f"could not be saved: {logo_result['message']}"
            )
            return

    if not refresh_current_hospital():
        st.error(
            "Hospital information was saved, but the updated "
            "hospital information could not be loaded."
        )
        return

    go_to_step(1)


# ============================================================
# STEP 2 — ADMINISTRATOR ACCOUNT
# ============================================================

def render_administrator_profile():
    user = refresh_current_user()
    step_header(*SETUP_STEPS[1][1:])

    if not user or not user.get("user_id"):
        st.error("Administrator information could not be found.")
        return

    user_id = user["user_id"]
    try:
        response = (
            admin_supabase.table("user_profiles")
            .select("*").eq("user_id", user_id).single().execute()
        )
        profile = response.data or {}
    except Exception as exc:
        st.error(f"Unable to fetch administrator profile: {exc}")
        return

    merged = {**user, **profile}
    picture = _profile_value(
        merged, "profile_picture_url", "profile_picture", "avatar_url"
    )
    hospital = get_current_hospital() or {}

    photo_col, details_col = st.columns([1, 1.75], gap="medium")

    with photo_col:
        with st.container(key="setup_admin_photo_card", border=True):
            section_heading("account_circle", "Profile Picture", "Your hospital administrator profile")
            render_image_preview(
                key="setup_profile_preview_current",
                image_url=picture,
                shape="circle",
                placeholder_initials=initials_for(full_name_of(merged)),
            )
            st.markdown(
                "<div class='ls-admin-mini-name'>"
                f"<strong>{safe(full_name_of(merged))}</strong>"
                "<span>Hospital Administrator</span></div>",
                unsafe_allow_html=True,
            )
            profile_picture = st.file_uploader(
                "Upload profile picture",
                type=["png", "jpg", "jpeg", "webp"],
                key="setup_profile_picture",
                help="PNG, JPG or WEBP; maximum 5 MB.",
            )
            if profile_picture:
                render_uploaded_preview(
                    key="setup_profile_preview_pending",
                    uploaded_file=profile_picture,
                    shape="circle",
                    caption="New photo (saved when you continue)",
                )

    with details_col:
        with st.container(key="setup_admin_personal_card", border=True):
            section_heading("badge", "Personal Information", "Complete your account details")

            account_left, account_right = st.columns(2, gap="small")
            with account_left:
                employee_id = st.text_input(
                    "Employee ID",
                    value=str(_profile_value(merged, "employee_id")),
                    key="setup_admin_employee",
                )
            with account_right:
                st.text_input(
                    "Email address",
                    value=str(_profile_value(merged, "email")),
                    disabled=True,
                    key="setup_admin_email_readonly",
                )

            name_a, name_b, name_c = st.columns(3, gap="small")
            with name_a:
                first = st.text_input(
                    "First name *",
                    value=str(_profile_value(merged, "user_fname", "first_name")),
                    key="setup_admin_first",
                )
            with name_b:
                middle = st.text_input(
                    "Middle name",
                    value=str(_profile_value(merged, "user_mname", "middle_name")),
                    key="setup_admin_middle",
                )
            with name_c:
                last = st.text_input(
                    "Last name *",
                    value=str(_profile_value(merged, "user_lname", "last_name")),
                    key="setup_admin_last",
                )

            section_heading("cake", "Date of Birth", "Select any birth year from 1900 onward")
            birth = wizard_date_parts(
                _profile_value(merged, "user_birthdate", "date_of_birth", "birthdate")
            )

            sex_col, contact_col = st.columns(2, gap="small")
            with sex_col:
                sex_options = ["Select sex", "Male", "Female"]
                old_sex = str(_profile_value(merged, "user_sex", "sex"))
                sex = st.selectbox(
                    "Sex *", sex_options,
                    index=sex_options.index(old_sex) if old_sex in sex_options else 0,
                    key="setup_admin_sex",
                )
            with contact_col:
                contact = st.text_input(
                    "Contact number",
                    value=str(_profile_value(merged, "user_contact_number", "contact_number")),
                    key="setup_admin_contact",
                )

            st.markdown(
                information_rows_html([
                    ("Role", "Hospital Administrator"),
                    ("Assigned hospital", hospital.get("hospital_name")),
                ]),
                unsafe_allow_html=True,
            )

    with st.container(key="setup_admin_address_card", border=True):
        address_values = _administrator_address_form(merged)

    note("Review your personal information and residential address before continuing.")
    _, next_clicked = nav_buttons(
        "administrator", back_step=0, next_label="Save & Continue"
    )
    if not next_clicked:
        return

    if not first.strip() or not last.strip():
        st.error("First name and last name are required.")
        return
    if not birth:
        st.error("Select a valid birthdate that is not in the future.")
        return
    if sex == "Select sex":
        st.error("Please select your sex.")
        return
    if not address_values:
        st.error("Complete the region, province, city, and barangay to continue.")
        return
    if profile_picture and len(profile_picture.getvalue()) > 5 * 1024 * 1024:
        st.error("Profile picture must be 5 MB or smaller.")
        return

    values = {
        **address_values,
        "employee_id": employee_id,
        "first_name": first.strip(),
        "middle_name": middle.strip(),
        "last_name": last.strip(),
        "date_of_birth": birth.isoformat(),
        "sex": sex,
        "contact_number": contact.strip(),
    }
    ok, message = _save_administrator_profile(user_id, values)
    if not ok:
        st.error(message)
        return

    if profile_picture:
        uploaded = upload_profile_picture(
            user_id=user_id,
            file_bytes=profile_picture.getvalue(),
            file_name=profile_picture.name,
        )
        if not uploaded.get("success") or not uploaded.get("url"):
            st.error(
                "Profile information saved, but the photo upload failed: "
                + uploaded.get("message", "No image URL returned")
            )
            return

        saved = update_profile_picture_url(
            user_id=user_id,
            profile_picture_url=uploaded["url"],
        )
        if not saved.get("success"):
            st.error("Photo uploaded, but its URL could not be stored.")
            return

    refresh_current_user()
    go_to_step(2)

# ============================================================
# STEP 3 — SUBSCRIPTION SUMMARY
# ============================================================

def render_subscription_summary(hospital):
    step_header(*SETUP_STEPS[2][1:])

    subscription = get_hospital_subscription_details(
        hospital.get("hospital_id")
    )

    if not subscription:
        st.warning(
            "No subscription information could be found for your "
            "hospital. Please contact support."
        )
        st.divider()
        if st.button("Back to Administrator", key="subscription_missing_back", icon=":material/arrow_back:"):
            go_to_step(1)
        return

    billing_cycle = subscription.get("billing_cycle", "Monthly")

    if billing_cycle == "Yearly":
        amount, period = float(subscription.get("price_yearly") or 0), "year"
    else:
        amount, period = float(subscription.get("price_monthly") or 0), "month"

    with st.container(key="setup_plan"):

        st.markdown(
            "<p class='ls-plan-label'>"
            "<span class='material-symbols-rounded'>workspace_premium</span>"
            "<span>Your subscription plan</span>"
            "</p>"
            f"<p class='ls-plan-name'>{safe(subscription.get('plan_name'))}</p>",
            unsafe_allow_html=True,
        )

        description = subscription.get("description")
        if description:
            st.markdown(
                f"<p class='ls-plan-desc'>{safe(description)}</p>",
                unsafe_allow_html=True,
            )

        st.markdown(
            f"<p class='ls-plan-price'>{peso(amount)}"
            f"<small> / {period}</small></p>",
            unsafe_allow_html=True,
        )

        limits = [
            ("Users", limit_text(subscription.get("max_users"))),
            ("Patients", limit_text(subscription.get("max_patients"))),
            ("X-rays per month", limit_text(subscription.get("max_xrays_per_month"))),
        ]
        limits_html = "".join(
            f"<div class='ls-limit'><b>{value}</b><span>{label}</span></div>"
            for label, value in limits
        )
        st.markdown(
            f"<div class='ls-limits'>{limits_html}</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div class='ls-plan-dates'>"
            "<span>"
            "<span class='material-symbols-rounded'>event</span>"
            f" Start: <b>{safe(subscription.get('start_date'))}</b>"
            "</span>"
            "<span>"
            "<span class='material-symbols-rounded'>event_available</span>"
            f" End: <b>{safe(subscription.get('end_date'))}</b>"
            "</span>"
            "</div>",
            unsafe_allow_html=True,
        )

    note(
        "Your subscription is already active — this step is here "
        "for you to confirm the details before continuing."
    )

    back_clicked, next_clicked = nav_buttons(
        "subscription",
        back_step=1,
        next_label="Continue",
    )

    if next_clicked:
        go_to_step(3)


# ============================================================
# STEP 4 — REVIEW & CONFIRM
# ============================================================

def review_section(key, icon_title, rows, avatar_url=None, avatar_shape="square"):
    icons = {
        "hospital": "local_hospital",
        "administrator": "manage_accounts",
        "subscription": "workspace_premium",
    }
    with st.container(key=f"setup_section_{key}", border=True):
        if avatar_url:
            picture_col, title_col = st.columns([1, 3.1], vertical_alignment="center")
            with picture_col:
                render_review_avatar(
                    key=f"setup_review_avatar_{key}",
                    image_url=avatar_url,
                    shape=avatar_shape,
                )
            with title_col:
                section_heading(icons.get(key, "fact_check"), icon_title)
        else:
            section_heading(icons.get(key, "fact_check"), icon_title)

        st.markdown(information_rows_html(rows), unsafe_allow_html=True)

def render_data_policy():
    st.markdown(
        "<p class='ls-section-title' style='font-weight:bold; font-size:16px; margin-bottom:10px;'>"
        "LUNGSIGHT SERVICE AND DATA PROCESSING AGREEMENT</p>",
        unsafe_allow_html=True,
    )
    
    # Exact text from your PDF
    policy_text = """
    <div style="font-family: Arial, sans-serif; font-size: 12px; line-height: 1.6; text-align: justify; color: #333; padding-right: 15px;">
    
    <b>1. DEFINITIONS AND ROLES</b><br>
    For purposes of compliance with the Philippine Data Privacy Act of 2012 (DPA):<br>
    1. "Personal Information Controller" (PIC) refers to the Hospital, which retains sole control over the purpose, scope, and use of the patient health information processed by the Software Service.<br>
    2. "Personal Information Processor" (PIP) refers to LungSight AI, which processes patient diagnostic data strictly on behalf of and under the documented instructions of the Hospital.<br>
    3. "Hospital Data" includes all patient profiles, clinical management logs, radiologic scans, internal and external hospital examination reports, and presumptive pneumonia detection outputs generated by or inputted into the system.<br><br>

    <b>2. RETENTION OF DATA OWNERSHIP</b><br>
    2.1 Hospital Ownership: The Hospital retains absolute and exclusive ownership, intellectual property rights, and title to all Hospital Data. Under no circumstances shall the subscription to the LungSight AI software service be construed as a transfer of ownership or proprietary rights over any patient records or clinical outcomes to the vendor.<br>
    2.2 Vendor Restrictions: LungSight AI is strictly prohibited from selling, leasing, disclosing, or commercially exploiting any Hospital Data. The software system shall not use the Hospital's clinical examination information to train, retrain, or improve its underlying machine learning models unless the data is explicitly subject to a separate, mutually signed de-identification and anonymization protocol that completely removes all Personal Identifiable Information (PII) in compliance with National Privacy Commission (NPC) standards.<br><br>

    <b>3. CLOUD DEPLOYMENT & SECURITY MEASURES (SUPABASE CLOUD)</b><br>
    3.1 Infrastructure Security: The Software Service utilizes Supabase Cloud infrastructure. LungSight AI warrants that the Supabase instance is configured with industry-standard security protocols, including Advanced Encryption Standard (AES) 256-bit encryption for data-at-rest and TLS 1.3 encryption for data-in-transit.<br>
    3.2 Access Management: Role-Based Access Controls (RBAC) shall be configured within the system to ensure that only authorized Hospital clinicians and technical staff possess permission to view patient diagnostic data and internal/external examination information.<br>
    3.3 Data Jurisdiction: Notwithstanding the use of cloud architecture, all processing must adhere to the data privacy principles of the Philippines. Data sovereignty regarding patient medical histories remains under the jurisdiction of the Republic of the Philippines.<br><br>

    <b>4. DATA RETURNING AND TERMINATION (EXIT CLAUSE)</b><br>
    4.1 Data Portability: Upon expiration, cancellation, or termination of the software subscription for any reason, LungSight AI is legally and contractually obligated to provide the Hospital with a complete, secure, and structured export of all Hospital Data (including Supabase schema logs, examination results, and history structures) within thirty (30) calendar days from termination notice.<br>
    4.2 Certified Destruction: Following the successful transfer and validation of the exported data by the Hospital, LungSight AI shall securely delete, purge, and overwrite all redundant copies of the Hospital Data residing on its Supabase cloud databases. A formal Certificate of Destruction must be issued to the Hospital within fifteen (15) days of erasure.<br><br>

    <b>5. BREACH NOTIFICATION AND LIABILITY</b><br>
    5.1 Notification Protocol: In the event of an actual or reasonably suspected security incident, unauthorized access, or data breach affecting the Supabase Cloud instance housing Hospital Data, LungSight AI shall notify the Hospital's Data Protection Officer (DPO) via written notice within twenty-four (24) hours of detection.<br>
    5.2 Mandatory Cooperation: LungSight AI shall assist the Hospital in complying with the mandatory 72-hour breach notification requirement imposed by the National Privacy Commission (NPC).<br><br>

    <b>6. GOVERNING LAW AND JURISDICTION</b><br>
    This Agreement shall be governed by, interpreted, and construed in accordance with the laws of the Republic of the Philippines. Any legal action arising from disputes regarding data ownership, privacy violations, or contractual breach shall be filed exclusively before the proper courts of the city where the Hospital's primary facility is located.
    
    </div>
    """
    
    # Render inside a scrollable container
    with st.container(height=300, border=True):
        st.markdown(
            "".join(line.strip() for line in policy_text.splitlines()),
            unsafe_allow_html=True,
        )


def render_review(hospital):
    step_header(*SETUP_STEPS[3][1:])

    hospital = refresh_current_hospital() or hospital
    user = refresh_current_user() or get_current_user() or {}
    try:
        fresh = (
            admin_supabase.table("user_profiles").select("*")
            .eq("user_id", user.get("user_id")).single().execute().data or {}
        )
        user = {**user, **fresh}
    except Exception:
        pass

    profile_picture_url = _profile_value(
        user, "profile_picture_url", "profile_picture", "avatar_url"
    )
    subscription = get_hospital_subscription_details(hospital.get("hospital_id"))

    hospital_rows = [
        ("Hospital name", hospital.get("hospital_name")),
        ("Hospital type", hospital.get("hospital_type")),
        ("Address", hospital.get("address")),
        ("Contact number", hospital.get("contact_number")),
        ("Email", hospital.get("email")),
        ("Website", hospital.get("website")),
    ]
    administrator_rows = [
        ("Name", full_name_of(user)),
        ("Employee ID", _profile_value(user, "employee_id")),
        ("Date of birth", _profile_value(user, "user_birthdate", "date_of_birth", "birthdate")),
        ("Sex", _profile_value(user, "user_sex", "sex")),
        ("Email", _profile_value(user, "email")),
        ("Contact", _profile_value(user, "user_contact_number", "contact_number")),
        ("Address", _profile_value(user, "user_address", "address", "residential_address")),
        ("Role", "Hospital Administrator"),
    ]

    c1, c2, c3 = st.columns([1.05, 1.15, 0.95], gap="small")
    with c1:
        review_section(
            "hospital", "Hospital Profile", hospital_rows,
            avatar_url=hospital.get("hospital_logo_url"),
            avatar_shape="square",
        )
    with c2:
        review_section(
            "administrator", "Administrator Account", administrator_rows,
            avatar_url=profile_picture_url,
            avatar_shape="circle",
        )
    with c3:
        if subscription:
            billing_cycle = subscription.get("billing_cycle") or "Monthly"
            amount = (
                subscription.get("price_yearly") if billing_cycle == "Yearly"
                else subscription.get("price_monthly")
            )
            review_section(
                "subscription", "Subscription", [
                    ("Plan", subscription.get("plan_name")),
                    ("Billing cycle", billing_cycle),
                    ("Price", peso(amount)),
                    ("Users", limit_text(subscription.get("max_users"))),
                    ("Patients", limit_text(subscription.get("max_patients"))),
                    ("X-rays / month", limit_text(subscription.get("max_xrays_per_month"))),
                ],
            )
        else:
            st.warning("Subscription information not available.")

    st.divider()
    
    # --------------------------------------------------------
    # DATA POLICY AGREEMENT
    # --------------------------------------------------------
    render_data_policy()
    
    st.write("")
    
    confirmation = st.checkbox(
        "I have reviewed the information above and confirm that it is correct.",
        key="setup_final_confirmation",
    )

    # Updated based on Section 2.2 of the PDF
    agree_policy = st.checkbox(
        "I am an authorized representative of this hospital and agree to the Service and Data Processing Agreement.",
        key="setup_policy_agreement",
    )

    st.divider()

    back_clicked, complete_clicked = nav_buttons(
        "review",
        back_step=2,
        next_label="Complete Setup",
        next_icon=":material/check_circle:",
    )

    if not complete_clicked:
        return

    if not confirmation:
        st.error(
            "Please confirm that the information is correct "
            "before completing setup."
        )
        return
        
    if not agree_policy:
        st.error(
            "You must agree to the Service and Data Processing Agreement "
            "to complete the setup."
        )
        return

    hospital_id = hospital.get("hospital_id")
    if not hospital_id:
        st.error("Hospital ID could not be found.")
        return

    result = complete_hospital_setup(hospital_id)
    if not result["success"]:
        st.error(result["message"])
        return

    # Save the agreement timestamp to the database
    try:
        admin_supabase.table("hospitals").update({
            "data_policy_agreed_at": datetime.now(timezone.utc).isoformat()
        }).eq("hospital_id", hospital_id).execute()
    except Exception as e:
        print(f"Failed to log policy agreement: {e}")

    st.session_state.setup_completed = True

    clear_wizard_map_state(hospital_id)

    st.success("Hospital setup completed successfully!")
    st.info("Your LungSight subscription is now active.")
    st.rerun()


# ============================================================
# MAIN SETUP WIZARD
# ============================================================

STEP_RENDERERS = [
    render_hospital_profile,
    lambda hospital: render_administrator_profile(),
    render_subscription_summary,
    render_review,
]


def show():
    load_setup_wizard_css()

    initialize_setup()

    hospital = get_current_hospital()

    if not hospital:
        st.error("Hospital information could not be found.")
        return

    if hospital.get("setup_completed", False):
        st.success("Hospital setup has already been completed.")
        return

    outer_left, outer_center, outer_right = st.columns([0.35, 11, 0.35])

    with outer_center:
        with st.container(key="setup_wizard"):

            top_left, top_right = st.columns([4, 1.7])

            with top_left:
                st.markdown(
                    "<div class='ls-brand'>"
                    "<div class='ls-brand-mark material-symbols-rounded'>pulmonology</div>"
                    "<div class='ls-brand-text'>"
                    "<p class='ls-brand-name'>LungSight</p>"
                    "<p class='ls-brand-sub'>Hospital Setup</p>"
                    "</div>"
                    "</div>",
                    unsafe_allow_html=True,
                )

            with top_right:
                refresh_col, signout_col = st.columns([0.65, 1.1])
                with refresh_col:
                    refresh_button(key="setup_wizard_refresh")

                with signout_col:
                    if st.button(
                        "Sign out",
                        key="setup_back_to_login",
                        icon=":material/logout:",
                        width="stretch",
                    ):
                        back_to_login()

            st.markdown(
                "<div class='ls-page-title'>"
                "<h1>Complete your hospital setup</h1>"
                "<p>Let's complete your hospital setup before you "
                "start using the LungSight system.</p>"
                "</div>",
                unsafe_allow_html=True,
            )

            render_progress()

            current_step = st.session_state.setup_step
            STEP_RENDERERS[current_step](hospital)