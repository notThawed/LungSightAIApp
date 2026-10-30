# streamlit_app/pages/system_administrator/manage_hospital.py

"""
System Administrator — Manage Hospitals

Layout: Pattern A (list + map split, detail card below).

    Overview KPI Metrics
    Search + filters toolbar
    ┌───────────────┬──────────────────────────────┐
    │ Hospital List │        Hospital Map          │
    └───────────────┴──────────────────────────────┘
    ┌─────────────── Detail Card (selected) ───────┐
    │ Subscription · Usage · Timeline · Actions    │
    └──────────────────────────────────────────────┘

Clicking a hospital in the list OR a pin on the map
selects it, and its clinical detail card appears below.
"""

import streamlit as st

from backend.fetches import (
    get_all_hospitals,
)

from backend.backend_utils.subscription_utils import (
    get_all_subscription_plans,
    get_subscription_context,
)

from backend.backend_utils.subscription_usage import (
    get_remaining_usage,
)

from streamlit_app.components.ui import (
    page_header,
    metric_card,
    empty_state,
    safe,
    show_flash_message,
)

from streamlit_app.components.map import (
    render_hospital_map,
)

from streamlit_app.components.dialogs.manage_hospital_dialogs import (
    DIALOG_KEY,
    SELECTED_HOSPITAL_KEY,
    SELECTED_STAFF_KEY,
    show_add_hospital_form,
    show_edit_hospital_dialog,
    show_deactivate_hospital_dialog,
    show_reactivate_hospital_dialog,
    show_hospital_staff_dialog,
    show_staff_member_dialog,
)

from shared.assets import load_css


# ============================================================
# INLINE SVG ICONS (Cross-platform, no font ligature issues)
# ============================================================

SVG_ICONS = {
    "hospital": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 21h18"/>
        <path d="M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16"/>
        <path d="M9 21v-4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v4"/>
        <path d="M10 9h4"/>
        <path d="M12 7v4"/>
    </svg>""",
    "pin": """<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/>
        <circle cx="12" cy="10" r="3"/>
    </svg>""",
    "phone": """<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
    </svg>""",
    "mail": """<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect width="20" height="16" x="2" y="4" rx="2"/>
        <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
    </svg>""",
    "globe": """<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/>
        <path d="M2 12h20"/>
    </svg>""",
    "card": """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect width="20" height="14" x="2" y="5" rx="2"/>
        <line x1="2" x2="22" y1="10" y2="10"/>
    </svg>""",
    "chart": """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 3v18h18"/>
        <path d="m19 9-5 5-4-4-3 3"/>
    </svg>""",
    "calendar": """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M8 2v4"/>
        <path d="M16 2v4"/>
        <rect width="18" height="18" x="3" y="4" rx="2"/>
        <path d="M3 10h18"/>
    </svg>""",
}


# ============================================================
# SESSION STATE
# ============================================================

def initialize_state():
    st.session_state.setdefault(DIALOG_KEY, None)
    st.session_state.setdefault(SELECTED_HOSPITAL_KEY, None)
    st.session_state.setdefault(SELECTED_STAFF_KEY, None)

    st.session_state.setdefault("mh_status_filter", "All")
    st.session_state.setdefault("mh_plan_filter", "All")
    st.session_state.setdefault("mh_last_map_click", None)
    st.session_state.setdefault("sa_flash", None)


def open_dialog(dialog_name, hospital=None, user_id=None):
    st.session_state[DIALOG_KEY] = dialog_name
    st.session_state[SELECTED_HOSPITAL_KEY] = hospital
    st.session_state[SELECTED_STAFF_KEY] = user_id
    st.rerun()


def select_hospital(hospital_id):
    """Toggle hospital selection. Clicking the same hospital twice deselects it."""
    current = st.session_state.get(SELECTED_HOSPITAL_KEY)
    current_id = (
        current.get("hospital_id")
        if isinstance(current, dict)
        else current
    )

    if current_id == hospital_id:
        st.session_state[SELECTED_HOSPITAL_KEY] = None
    else:
        st.session_state[SELECTED_HOSPITAL_KEY] = hospital_id

    st.rerun()


# ============================================================
# CACHED DETAIL LOADER
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def load_hospital_detail(hospital_id):
    """Load subscription + usage for one hospital."""
    if not hospital_id:
        return {"subscription": None, "usage": None, "context": None}

    try:
        subscription = get_subscription_context(hospital_id)
        usage = get_remaining_usage(hospital_id)
        return {"subscription": subscription, "usage": usage, "context": None}
    except Exception as exc:
        print(f"Failed to load hospital detail: {exc}")
        return {"subscription": None, "usage": None, "context": None}


def refresh_hospital_cache():
    """Clear cached detail data after a mutation."""
    try:
        load_hospital_detail.clear()
    except Exception:
        pass

    try:
        st.cache_data.clear()
    except Exception:
        pass


# ============================================================
# DATA LOADING
# ============================================================

def load_hospitals():
    try:
        return get_all_hospitals() or []
    except Exception as exc:
        st.error(f"Unable to load hospitals: {exc}")
        return []


@st.cache_data(ttl=300, show_spinner=False)
def load_plans():
    """Load subscription plans for filter dropdown."""
    try:
        return get_all_subscription_plans() or []
    except Exception as exc:
        print(f"Failed to load plans: {exc}")
        return []


def load_hospital_plan_map():
    """Build a lookup { hospital_id: plan_name }."""
    plans_by_hospital = {}
    for hospital in load_hospitals():
        hospital_id = hospital.get("hospital_id")
        if not hospital_id:
            continue
        try:
            context = get_subscription_context(hospital_id)
            plan_name = (
                context.get("plan_name")
                if isinstance(context, dict)
                else None
            )
            plans_by_hospital[hospital_id] = plan_name or "No Plan"
        except Exception:
            plans_by_hospital[hospital_id] = "No Plan"

    return plans_by_hospital


# ============================================================
# PAGE ENTRYPOINT
# ============================================================

def show():
    initialize_state()
    load_css("manage_hospital.css")

    with st.container(key="sa_page"):
        show_flash_message()

        # ---------------- Page Header ----------------
        register_clicked = page_header(
            "Manage Hospitals",
            "View registered facilities, oversee subscription allocations, and supervise hospital staff.",
            action_label="Register Hospital",
            action_key="register_hospital",
            action_icon="add_business",
        )

        if register_clicked:
            open_dialog("register_hospital")

        # ---------------- Load Hospitals ----------------
        hospitals = load_hospitals()
        plan_map = load_hospital_plan_map()

        # ---------------- Overview KPI Metrics ----------------
        total_h = len(hospitals)
        active_h = sum(1 for h in hospitals if h.get("is_active", True))
        verified_h = sum(1 for h in hospitals if h.get("setup_completed", False))
        sub_h = sum(1 for h in hospitals if plan_map.get(h.get("hospital_id")) not in (None, "No Plan"))

        metrics = [
            ("Registered Facilities", total_h, "domain", ""),
            ("Active Hospitals", active_h, "check_circle", "green"),
            ("Setup Completed", verified_h, "verified", "blue"),
            ("Active Subscriptions", sub_h, "credit_card", "amber"),
        ]

        for column, (title, value, icon, tone) in zip(st.columns(4), metrics):
            with column:
                metric_card(title, value, icon, tone)

        # ---------------- Search + Filters ----------------
        search, status_filter, plan_filter = show_search_and_filters(hospitals)

        filtered = filter_hospitals(
            hospitals,
            search,
            status_filter,
            plan_filter,
            plan_map=plan_map,
        )

        # ---------------- Split View (List + Map) ----------------
        render_split_view(
            filtered,
            all_hospitals=hospitals,
        )

        # ---------------- Detail Card ----------------
        render_detail_card(hospitals)

    # ---------------- Dialog Dispatcher ----------------
    render_active_dialog()


# ============================================================
# SEARCH + FILTERS
# ============================================================

def show_search_and_filters(hospitals):
    with st.container(key="sa_hospital_filters"):
        col_search, col_status, col_plan, col_reset = st.columns(
            [3.2, 1.3, 1.5, 0.9],
            vertical_alignment="center",
        )

        with col_search:
            search = st.text_input(
                "Search hospitals",
                placeholder="Search by hospital name, code, or email...",
                label_visibility="collapsed",
                key="hospital_search",
            )

        with col_status:
            status_filter = st.selectbox(
                "Status",
                ["All", "Active", "Inactive"],
                key="mh_status_filter",
                label_visibility="collapsed",
            )

        with col_plan:
            plan_names = ["All"]
            for plan in load_plans():
                name = plan.get("plan_name")
                if name and name not in plan_names:
                    plan_names.append(name)
            plan_names.append("No Plan")

            plan_filter = st.selectbox(
                "Plan",
                plan_names,
                key="mh_plan_filter",
                label_visibility="collapsed",
            )

        def _reset_filters():
            st.session_state["hospital_search"] = ""
            st.session_state["mh_status_filter"] = "All"
            st.session_state["mh_plan_filter"] = "All"
            st.cache_data.clear()

        with col_reset:
            st.button(
                "Reset",
                icon=":material/refresh:",
                width="stretch",
                key="mh_reset_filters",
                on_click=_reset_filters,
                help="Reset search and filters",
            )

    return search, status_filter, plan_filter


def filter_hospitals(
    hospitals,
    search,
    status_filter,
    plan_filter,
    plan_map=None,
):
    search = (search or "").strip().lower()

    if plan_map is None and plan_filter != "All":
        plan_map = load_hospital_plan_map()

    filtered = []

    for hospital in hospitals:
        # Search
        if search:
            name = (hospital.get("hospital_name") or "").lower()
            code = (hospital.get("hospital_code") or "").lower()
            email = (hospital.get("email") or "").lower()
            if (
                search not in name
                and search not in code
                and search not in email
            ):
                continue

        # Status
        if status_filter == "Active":
            if not hospital.get("is_active", True):
                continue
        elif status_filter == "Inactive":
            if hospital.get("is_active", True):
                continue

        # Plan
        if plan_filter != "All":
            hospital_id = hospital.get("hospital_id")
            plan_name = (plan_map or {}).get(hospital_id, "No Plan")
            if plan_name != plan_filter:
                continue

        filtered.append(hospital)

    return filtered


# ============================================================
# SPLIT VIEW (LIST + MAP)
# ============================================================

def render_split_view(filtered_hospitals, all_hospitals=None):
    list_col, map_col = st.columns(
        [3.4, 6.6],
        gap="medium",
    )

    # ---------------- List Pane ----------------
    with list_col:
        st.markdown(
            f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:0.45rem;'>"
            f"  <span style='font-size:0.95rem; font-weight:700; color:var(--sa-ink);'>Facilities Directory</span>"
            f"  <span class='sa-table-count-badge'>{len(filtered_hospitals)} hospital{'s' if len(filtered_hospitals) != 1 else ''}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        render_hospital_list(filtered_hospitals)

    # ---------------- Map Pane ----------------
    with map_col:
        render_hospital_map_pane(
            all_hospitals or filtered_hospitals
        )


# ============================================================
# HOSPITAL LIST PANE
# ============================================================

def render_hospital_list(hospitals):
    if not hospitals:
        empty_state("No facilities match your search or filter criteria.")
        return

    selected = st.session_state.get(SELECTED_HOSPITAL_KEY)
    selected_id = (
        selected.get("hospital_id")
        if isinstance(selected, dict)
        else selected
    )

    with st.container(key="mh_hospital_list"):
        for hospital in hospitals:
            hospital_id = hospital.get("hospital_id")
            is_selected = (hospital_id == selected_id)
            is_active = hospital.get("is_active", True)
            is_verified = hospital.get("setup_completed", False)

            name = hospital.get("hospital_name") or "Unnamed Hospital"
            code = hospital.get("hospital_code") or "—"
            address = hospital.get("address") or "—"
            facility_type = hospital.get("hospital_type") or "General Hospital"

            status_cls = "mh-badge-active" if is_active else "mh-badge-inactive"
            status_txt = "Active" if is_active else "Inactive"

            setup_cls = "mh-badge-verified" if is_verified else "mh-badge-pending"
            setup_txt = "Verified" if is_verified else "Setup Pending"

            with st.container(key=f"mh_list_item_{hospital_id}"):
                card_html = (
                    f'<div class="mh-list-card-content">'
                    f'<div class="mh-list-head">'
                    f'<div class="mh-list-icon">{SVG_ICONS["hospital"]}</div>'
                    f'<div style="min-width:0; flex-grow:1;">'
                    f'<div class="mh-list-name" title="{safe(name)}">{safe(name)}</div>'
                    f'<div class="mh-list-meta"><span>{safe(facility_type)}</span></div>'
                    f'</div>'
                    f'</div>'
                    f'<div class="mh-list-badges">'
                    f'<span class="mh-badge mh-badge-code">#{safe(code)}</span>'
                    f'<span class="mh-badge {status_cls}">{status_txt}</span>'
                    f'<span class="mh-badge {setup_cls}">{setup_txt}</span>'
                    f'</div>'
                    f'<div style="font-size:0.75rem; color:var(--sa-slate); margin-top:0.3rem; display:flex; align-items:center; gap:0.3rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">'
                    f'{SVG_ICONS["pin"]} <span>{safe(address[:52])}{"…" if len(address) > 52 else ""}</span>'
                    f'</div>'
                    f'</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)

                if st.button(
                    "Selected ✓" if is_selected else "Select Facility",
                    key=f"mh_select_{hospital_id}",
                    width="stretch",
                    type="primary" if is_selected else "secondary",
                    icon=":material/check_circle:" if is_selected else ":material/arrow_forward:",
                ):
                    select_hospital(hospital_id)


# ============================================================
# MAP PANE
# ============================================================

def render_hospital_map_pane(hospitals):
    mappable = [
        h for h in hospitals
        if h.get("latitude") is not None
        and h.get("longitude") is not None
    ]

    if not mappable:
        empty_state(
            "No hospital coordinates registered yet. "
            "Add coordinates or use the geocoding service to plot facilities on the map."
        )
        return

    selected = st.session_state.get(SELECTED_HOSPITAL_KEY)
    selected_id = (
        selected.get("hospital_id")
        if isinstance(selected, dict)
        else selected
    )

    output = render_hospital_map(
        mappable,
        selected_id=selected_id,
        height=560,
        key="sa_hospital_map",
    )

    if not output:
        return

    clicked_tooltip = output.get("last_object_clicked_tooltip")
    if not clicked_tooltip:
        return

    if clicked_tooltip == st.session_state.get("mh_last_map_click"):
        return

    st.session_state["mh_last_map_click"] = clicked_tooltip

    clicked_hospital = next(
        (h for h in mappable if (h.get("hospital_name") or "") == clicked_tooltip),
        None,
    )

    if not clicked_hospital:
        return

    clicked_id = clicked_hospital.get("hospital_id")
    if clicked_id != selected_id:
        st.session_state[SELECTED_HOSPITAL_KEY] = clicked_hospital
        st.rerun()


# ============================================================
# DETAIL CARD
# ============================================================

def render_detail_card(all_hospitals):
    selected = st.session_state.get(SELECTED_HOSPITAL_KEY)

    if not selected:
        empty_card_html = (
            f'<div class="mh-empty-selection">'
            f'<div class="mh-empty-icon">{SVG_ICONS["hospital"]}</div>'
            f'<div class="mh-empty-title">No Facility Selected</div>'
            f'<div class="mh-empty-desc">'
            f'Select a hospital from the directory list on the left or click any pin on the map to inspect its real-time subscription status, resource utilization, and staff roster.'
            f'</div>'
            f'</div>'
        )
        st.markdown(empty_card_html, unsafe_allow_html=True)
        return

    selected_id = (
        selected.get("hospital_id")
        if isinstance(selected, dict)
        else selected
    )

    hospital = next(
        (h for h in all_hospitals if h.get("hospital_id") == selected_id),
        selected if isinstance(selected, dict) else None,
    )

    if not hospital:
        return

    detail = load_hospital_detail(hospital["hospital_id"])
    context = detail.get("subscription") or {}
    usage = detail.get("usage") or {}

    with st.container(key="mh_detail_card"):
        render_detail_header(hospital)
        render_detail_metrics(context, usage)
        st.write("")
        render_detail_actions(hospital)


def render_detail_header(hospital):
    name = hospital.get("hospital_name") or "Unnamed Hospital"
    code = hospital.get("hospital_code") or "—"
    hospital_type = hospital.get("hospital_type") or "General Hospital"
    address = hospital.get("address") or "—"
    contact = hospital.get("contact_number") or "—"
    email = hospital.get("email") or "—"
    website = hospital.get("website") or ""

    is_active = hospital.get("is_active", True)
    is_verified = hospital.get("setup_completed", False)

    status_cls = "mh-badge-active" if is_active else "mh-badge-inactive"
    status_txt = "Active Facility" if is_active else "Inactive Facility"

    setup_cls = "mh-badge-verified" if is_verified else "mh-badge-pending"
    setup_txt = "Setup Verified" if is_verified else "Setup Pending"

    website_chip = (
        f'<div class="mh-contact-chip">'
        f'{SVG_ICONS["globe"]} <span>{safe(website)}</span>'
        f'</div>'
        if website else ''
    )

    header_html = (
        f'<div class="mh-detail-hero">'
        f'<div class="mh-detail-avatar">{SVG_ICONS["hospital"]}</div>'
        f'<div class="mh-detail-info">'
        f'<div class="mh-detail-title">{safe(name)}</div>'
        f'<div class="mh-detail-badges">'
        f'<span class="mh-badge mh-badge-code">#{safe(code)}</span>'
        f'<span class="mh-badge" style="background:#F1F5F9; color:#475569; border:1px solid #E2E8F0;">{safe(hospital_type)}</span>'
        f'<span class="mh-badge {status_cls}">{status_txt}</span>'
        f'<span class="mh-badge {setup_cls}">{setup_txt}</span>'
        f'</div>'
        f'</div>'
        f'</div>'
        f'<div class="mh-contact-bar">'
        f'<div class="mh-contact-chip">{SVG_ICONS["pin"]} <span>{safe(address)}</span></div>'
        f'<div class="mh-contact-chip">{SVG_ICONS["phone"]} <span>{safe(contact)}</span></div>'
        f'<div class="mh-contact-chip">{SVG_ICONS["mail"]} <span>{safe(email)}</span></div>'
        f'{website_chip}'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)


def render_detail_metrics(context, usage):
    subscription_col, usage_col, timeline_col = st.columns(3, gap="medium")

    # ---------------- 1. Subscription Panel ----------------
    with subscription_col:
        plan_name = context.get("plan_name") or "No Plan"
        billing = (context.get("billing_cycle") or "None").capitalize()
        amount = context.get("amount")
        amount_text = f"₱{amount:,.2f}" if amount else "Free Tier / No Charge"

        sub_html = (
            f'<div class="mh-card-panel">'
            f'<div class="mh-panel-head">{SVG_ICONS["card"]} <span>Subscription Plan</span></div>'
            f'<div class="mh-plan-name">{safe(plan_name)}</div>'
            f'<div class="mh-plan-price">{safe(amount_text)} &bull; {safe(billing)}</div>'
            f'<div style="font-size:0.75rem; color:var(--sa-slate); line-height:1.35; margin-top:0.25rem;">'
            f'Allocated limits and feature entitlements are active for this hospital.'
            f'</div>'
            f'</div>'
        )
        st.markdown(sub_html, unsafe_allow_html=True)

    # ---------------- 2. Usage Panel ----------------
    with usage_col:
        usage_items_html = ""
        if usage:
            for key, label in (
                ("users", "User Accounts"),
                ("patients", "Patient Records"),
                ("xrays", "Monthly AI Scans"),
            ):
                block = usage.get(key) or {}
                used = block.get("used", 0)
                limit = block.get("limit")
                unlimited = block.get("unlimited", False)

                if unlimited or limit is None:
                    val_str = f"{used} / ∞"
                    fill_pct = 100
                    fill_cls = ""
                else:
                    val_str = f"{used} / {limit}"
                    fill_pct = min(100, int((used / limit) * 100)) if limit > 0 else 0
                    if fill_pct >= 90:
                        fill_cls = "mh-progress-fill-danger"
                    elif fill_pct >= 75:
                        fill_cls = "mh-progress-fill-warning"
                    else:
                        fill_cls = ""

                usage_items_html += (
                    f'<div class="mh-usage-item">'
                    f'<div class="mh-usage-header">'
                    f'<span class="mh-usage-label">{label}</span>'
                    f'<span class="mh-usage-val">{val_str}</span>'
                    f'</div>'
                    f'<div class="mh-progress-track">'
                    f'<div class="mh-progress-fill {fill_cls}" style="width: {fill_pct}%;"></div>'
                    f'</div>'
                    f'</div>'
                )
        else:
            usage_items_html = "<div style='font-size:0.8rem; color:var(--sa-slate);'>No usage metrics recorded.</div>"

        usage_panel_html = (
            f'<div class="mh-card-panel">'
            f'<div class="mh-panel-head">{SVG_ICONS["chart"]} <span>Resource Utilization</span></div>'
            f'<div class="mh-usage-group">{usage_items_html}</div>'
            f'</div>'
        )
        st.markdown(usage_panel_html, unsafe_allow_html=True)

    # ---------------- 3. Timeline Panel ----------------
    with timeline_col:
        state = context.get("state") or "none"
        days_left = context.get("days_left")
        end_date = context.get("end_date") or "—"

        state_labels = {
            "active": "Active",
            "grace": "Grace Period",
            "expired": "Expired",
            "setup_pending": "Setup Pending",
            "cancelled": "Cancelled",
            "none": "No Subscription",
        }
        state_label = state_labels.get(state, state.title())

        days_text = f"{days_left} days remaining" if days_left is not None else "No expiration set"

        timeline_html = (
            f'<div class="mh-card-panel">'
            f'<div class="mh-panel-head">{SVG_ICONS["calendar"]} <span>Subscription Timeline</span></div>'
            f'<div class="mh-timeline-row"><span>Status</span><b>{safe(state_label)}</b></div>'
            f'<div class="mh-timeline-row"><span>Validity</span><b>{safe(days_text)}</b></div>'
            f'<div class="mh-timeline-row"><span>Cycle Ends</span><b>{safe(str(end_date))}</b></div>'
            f'</div>'
        )
        st.markdown(timeline_html, unsafe_allow_html=True)


def render_detail_actions(hospital):
    hospital_id = hospital["hospital_id"]
    is_active = hospital.get("is_active", True)

    col1, col2, col3, col4 = st.columns(4, gap="small")

    with col1:
        if st.button(
            "View Staff",
            key=f"mh_view_staff_{hospital_id}",
            icon=":material/groups:",
            width="stretch",
            type="secondary",
        ):
            open_dialog("hospital_staff", hospital=hospital)

    with col2:
        if st.button(
            "Edit Facility",
            key=f"mh_edit_{hospital_id}",
            icon=":material/edit:",
            width="stretch",
            type="secondary",
        ):
            open_dialog("edit_hospital", hospital=hospital)

    with col3:
        if st.button(
            "Manage Subscription",
            key=f"mh_manage_sub_{hospital_id}",
            icon=":material/credit_card:",
            width="stretch",
            type="secondary",
        ):
            st.session_state.current_page = "Manage Subscriptions"
            st.session_state[SELECTED_HOSPITAL_KEY] = hospital
            st.rerun()

    with col4:
        if is_active:
            if st.button(
                "Deactivate",
                key=f"mh_deactivate_{hospital_id}",
                icon=":material/block:",
                width="stretch",
                type="secondary",
            ):
                open_dialog("deactivate_hospital", hospital=hospital)
        else:
            if st.button(
                "Reactivate",
                key=f"mh_reactivate_{hospital_id}",
                icon=":material/check_circle:",
                width="stretch",
                type="primary",
            ):
                open_dialog("reactivate_hospital", hospital=hospital)


# ============================================================
# DIALOG DISPATCHER
# ============================================================

def render_active_dialog():
    dialog_name = st.session_state.get(DIALOG_KEY)
    if not dialog_name:
        return

    if dialog_name == "hospital_staff":
        hospital = st.session_state.get(SELECTED_HOSPITAL_KEY)
        if isinstance(hospital, str):
            hospitals = load_hospitals()
            hospital = next((h for h in hospitals if h.get("hospital_id") == hospital), None)
        if hospital:
            show_hospital_staff_dialog(hospital)

    elif dialog_name == "staff_profile":
        user_id = st.session_state.get(SELECTED_STAFF_KEY)
        if user_id:
            show_staff_member_dialog(user_id)

    elif dialog_name == "register_hospital":
        show_add_hospital_form()

    elif dialog_name == "edit_hospital":
        hospital = st.session_state.get(SELECTED_HOSPITAL_KEY)
        if isinstance(hospital, str):
            hospitals = load_hospitals()
            hospital = next((h for h in hospitals if h.get("hospital_id") == hospital), None)
        if hospital:
            show_edit_hospital_dialog(hospital)

    elif dialog_name == "deactivate_hospital":
        hospital = st.session_state.get(SELECTED_HOSPITAL_KEY)
        if isinstance(hospital, str):
            hospitals = load_hospitals()
            hospital = next((h for h in hospitals if h.get("hospital_id") == hospital), None)
        if hospital:
            show_deactivate_hospital_dialog(hospital)

    elif dialog_name == "reactivate_hospital":
        hospital = st.session_state.get(SELECTED_HOSPITAL_KEY)
        if isinstance(hospital, str):
            hospitals = load_hospitals()
            hospital = next((h for h in hospitals if h.get("hospital_id") == hospital), None)
        if hospital:
            show_reactivate_hospital_dialog(hospital)
