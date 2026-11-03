# streamlit_app/pages/hospital_administrator/hospital_info.py

"""
Hospital admin's "My Hospital" page.

Shows the admin their own hospital's profile, a
pinned map of its location, and current activity
counters (users / patients / examinations / x-rays).

Scope is locked to the admin's own hospital —
they can never see another hospital's data.
"""

import streamlit as st

from backend.fetches import (
    get_hospital_locations,
    get_hospital_staff,
    get_all_patients,
    get_examinations_by_patient,
)

from backend.backend_utils.subscription_usage import (
    get_hospital_subscription,
    get_remaining_usage,
)

from streamlit_app.components.ui import (
    page_header,
    section_title,
    show_rows,
    format_date,
    pill,
    show_flash_message,
)

from shared.assets import load_css


from streamlit_app.components.map import render_hospital_map


# ============================================================
# USER HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}


def current_hospital_id():
    return current_user().get("hospital_id")


# ============================================================
# FORMATTERS
# ============================================================

def format_number(value):
    """1234 -> '1,234'. None -> '—'."""
    if value is None:
        return "—"

    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def format_plan_name(subscription):
    """Extract a human-readable plan name."""
    if not subscription:
        return "No active plan"

    plan = subscription.get("plan") or {}
    return plan.get("plan_name") or "Unknown Plan"


def format_billing(subscription):
    if not subscription:
        return "—"

    cycle = subscription.get("billing_cycle") or "—"
    return str(cycle).capitalize()


def format_plan_price(subscription):
    """₱2,500.00"""
    if not subscription:
        return "—"

    plan = subscription.get("plan") or {}
    cycle = (subscription.get("billing_cycle") or "").lower()

    if cycle == "monthly":
        amount = plan.get("price_monthly")
    elif cycle == "yearly":
        amount = plan.get("price_yearly")
    else:
        amount = None

    if amount is None:
        return "—"

    try:
        return f"₱{float(amount):,.2f}"
    except (TypeError, ValueError):
        return "—"


# ============================================================
# ACTIVITY COUNTERS
# ============================================================

def count_hospital_staff(hospital_id):
    """Return number of active staff at this hospital."""
    try:
        staff = get_hospital_staff(
            hospital_id,
            active_only=True,
        ) or []
        return len(staff)
    except Exception:
        return 0


def count_hospital_patients(hospital_id):
    """Return number of patients registered at this hospital."""
    try:
        patients = get_all_patients() or []
        return sum(
            1 for p in patients
            if p.get("hospital_id") == hospital_id
        )
    except Exception:
        return 0


def count_hospital_examinations(hospital_id):
    """
    Return total examinations across all hospital patients.
    Uses get_examinations_by_patient per patient.
    """
    try:
        patients = get_all_patients() or []
        hospital_patients = [
            p for p in patients
            if p.get("hospital_id") == hospital_id
        ]

        total = 0
        for p in hospital_patients:
            exams = get_examinations_by_patient(
                p.get("patient_id")
            ) or []
            total += len(exams)

        return total

    except Exception:
        return 0


# ============================================================
# HOSPITAL INFO CARD
# ============================================================

def render_hospital_card(hospital):
    """
    Left-side card: logo, name, address, contact,
    activity counters.
    """

    logo_url = hospital.get("hospital_logo_url")
    name = hospital.get("hospital_name") or "Unnamed Hospital"
    address = hospital.get("address") or "—"
    contact = hospital.get("contact_number") or "—"
    email = hospital.get("email") or "—"
    website = (hospital.get("website") or "").strip()
    hospital_type = hospital.get("hospital_type") or "Hospital"

    # --------------------------------------------------------
    # Brand Header (Logo + Meta + Verified Badge)
    # --------------------------------------------------------

    if logo_url:
        logo_html = f"<div class='geo-logo-wrap'><img class='geo-logo' src='{logo_url}' alt='{name} logo'></div>"
    else:
        logo_html = (
            "<div class='geo-logo-wrap geo-logo-fallback'>"
            "<span class='material-symbols-rounded'>local_hospital</span>"
            "</div>"
        )

    st.markdown(
        f"<div class='geo-brand-header'>"
        f"{logo_html}"
        f"<div class='geo-brand-meta'>"
        f"<span class='geo-type'>{hospital_type.upper()}</span>"
        f"<h2 class='geo-name'>{name}</h2>"
        f"<div class='geo-badge-row'>{pill('Verified Facility', 'green')}</div>"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # Contact details
    # --------------------------------------------------------

    website_row = ""
    if website:
        web_url = website if website.startswith(("http://", "https://")) else f"https://{website}"
        website_row = (
            f"<a href='{web_url}' target='_blank' rel='noopener noreferrer' class='geo-contact-row geo-contact-link'>"
            f"<span class='material-symbols-rounded'>language</span>"
            f"<span>{website}</span>"
            f"<span class='material-symbols-rounded geo-external-icon'>open_in_new</span>"
            f"</a>"
        )

    st.markdown(
        "<div class='geo-contact'>"
        f"<div class='geo-contact-row'>"
        f"<span class='material-symbols-rounded'>location_on</span>"
        f"<span>{address}</span>"
        f"</div>"
        f"<div class='geo-contact-row'>"
        f"<span class='material-symbols-rounded'>call</span>"
        f"<span>{contact}</span>"
        f"</div>"
        f"<div class='geo-contact-row'>"
        f"<span class='material-symbols-rounded'>mail</span>"
        f"<span>{email}</span>"
        f"</div>"
        f"{website_row}"
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# ACTIVITY STATS
# ============================================================

def render_activity_stats(hospital_id, usage):

    users_used = 0
    patients_used = 0
    xrays_used = 0
    exams_used = 0

    try:
        usage_users = (usage or {}).get("users") or {}
        usage_patients = (usage or {}).get("patients") or {}
        usage_xrays = (usage or {}).get("xrays") or {}

        users_used = usage_users.get("used", 0)
        patients_used = usage_patients.get("used", 0)
        xrays_used = usage_xrays.get("used", 0)
    except Exception:
        pass

    # Total examinations (heavier query)
    try:
        exams_used = count_hospital_examinations(hospital_id)
    except Exception:
        exams_used = 0

    st.markdown(
        "<p class='geo-section-label'>Activity Overview</p>"
        "<div class='geo-stats'>"
        f"<div class='geo-stat geo-stat-users'>"
        f"<div class='geo-stat-top'>"
        f"<span class='geo-stat-icon material-symbols-rounded'>groups</span>"
        f"<div class='geo-stat-value'>{format_number(users_used)}</div>"
        f"</div>"
        f"<div class='geo-stat-label'>Staff Accounts</div>"
        "</div>"
        f"<div class='geo-stat geo-stat-patients'>"
        f"<div class='geo-stat-top'>"
        f"<span class='geo-stat-icon material-symbols-rounded'>personal_injury</span>"
        f"<div class='geo-stat-value'>{format_number(patients_used)}</div>"
        f"</div>"
        f"<div class='geo-stat-label'>Registered Patients</div>"
        "</div>"
        f"<div class='geo-stat geo-stat-exams'>"
        f"<div class='geo-stat-top'>"
        f"<span class='geo-stat-icon material-symbols-rounded'>radiology</span>"
        f"<div class='geo-stat-value'>{format_number(exams_used)}</div>"
        f"</div>"
        f"<div class='geo-stat-label'>Examinations</div>"
        "</div>"
        f"<div class='geo-stat geo-stat-xrays'>"
        f"<div class='geo-stat-top'>"
        f"<span class='geo-stat-icon material-symbols-rounded'>instant_mix</span>"
        f"<div class='geo-stat-value'>{format_number(xrays_used)}</div>"
        f"</div>"
        f"<div class='geo-stat-label'>AI Scans / Mo.</div>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# SUBSCRIPTION SUMMARY
# ============================================================

def render_subscription_summary(subscription):

    plan_name = format_plan_name(subscription)
    billing = format_billing(subscription)
    price = format_plan_price(subscription)

    st.markdown(
        "<p class='geo-section-label'>Subscription Tier</p>"
        f"<div class='geo-sub-card'>"
        f"<div class='geo-sub-left'>"
        f"<div class='geo-sub-plan'><span class='material-symbols-rounded'>verified</span>{plan_name}</div>"
        f"<div class='geo-sub-meta'><span>{billing} Billing</span><span>•</span><span>{price}</span></div>"
        f"</div>"
        f"<span class='geo-sub-badge'>Active Plan</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# PAGE
# ============================================================

def show():

    load_css("hospital_info.css")
    show_flash_message()

    hospital_id = current_hospital_id()

    with st.container(key="sa_page"):

        page_header(
            "My Hospital",
            "View your hospital's profile, location, and current activity.",
        )

        # ----------------------------------------------------
        # Hospital must be assigned
        # ----------------------------------------------------

        if not hospital_id:
            st.error(
                "Your account is not assigned to a hospital. "
                "Please contact your Superadmin."
            )
            return

        # ----------------------------------------------------
        # Load hospital with coordinates
        # ----------------------------------------------------

        try:
            hospital_list = get_hospital_locations(
                hospital_id=hospital_id
            )
        except Exception as error:
            st.error(f"Failed to load hospital data: {error}")
            return

        if not hospital_list:
            st.warning(
                "Your hospital's location has not been set up yet. "
                "Please contact your Superadmin."
            )
            return

        hospital = hospital_list[0]

        # ----------------------------------------------------
        # Load subscription + usage
        # ----------------------------------------------------

        try:
            subscription = get_hospital_subscription(hospital_id)
        except Exception:
            subscription = None

        try:
            usage = get_remaining_usage(hospital_id)
        except Exception:
            usage = {}

        # ====================================================
        # TWO-COLUMN LAYOUT
        # ====================================================

        left, right = st.columns([1, 1.6], gap="large")

        # ----------------------------------------------------
        # LEFT — Info card
        # ----------------------------------------------------

        with left:

            with st.container(key="geo_info_card"):

                render_hospital_card(hospital)

                render_activity_stats(hospital_id, usage)

                render_subscription_summary(subscription)

        # ----------------------------------------------------
        # RIGHT — Map
        # ----------------------------------------------------

        with right:

            with st.container(key="geo_map_panel"):

                st.markdown(
                    "<div class='geo-map-header'>"
                    "<div class='geo-map-title'>"
                    "<span class='material-symbols-rounded'>pin_drop</span>"
                    "<span>Facility Geo-Location &amp; Perimeter</span>"
                    "</div>"
                    "<span class='geo-map-badge'>Live GPS Pinned</span>"
                    "</div>",
                    unsafe_allow_html=True,
                )

                render_hospital_map(
                    hospitals=[hospital],
                    selected_id=hospital_id,
                    height=520,
                    key="my_hospital_map",
                )