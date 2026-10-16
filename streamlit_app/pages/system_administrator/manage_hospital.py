# streamlit_app/pages/system_administrator/manage_hospital.py

"""
System Administrator — Manage Hospitals

Layout: Pattern A (list + map split, detail card below).

    Search + filters
    ┌───────────────┬──────────────────────────────┐
    │ Hospital List │        Hospital Map          │
    └───────────────┴──────────────────────────────┘
    ┌─────────────── Detail Card (selected) ───────┐
    │ Subscription · Usage · Timeline · Actions    │
    └──────────────────────────────────────────────┘

Clicking a hospital in the list OR a pin on the map
selects it, and its detail card appears below.
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
    section_title,
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
    """
    Toggle hospital selection.

    Clicking the same hospital twice deselects it.
    """

    current = st.session_state.get(SELECTED_HOSPITAL_KEY)

    current_id = (
        current.get("hospital_id")
        if isinstance(current, dict)
        else None
    )

    if current_id == hospital_id:
        st.session_state[SELECTED_HOSPITAL_KEY] = None
    else:
        st.session_state[SELECTED_HOSPITAL_KEY] = hospital_id

    st.rerun()


# ============================================================
# CACHED DETAIL LOADER (Enhancement D)
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def load_hospital_detail(hospital_id):
    """
    Load subscription + usage for one hospital.

    Cached for 60 seconds. Cleared by refresh_hospital_cache()
    after any mutation (register / edit / deactivate / reactivate).
    """

    if not hospital_id:
        return {
            "subscription": None,
            "usage": None,
            "context": None,
        }

    try:

        subscription = get_subscription_context(hospital_id)

        usage = get_remaining_usage(hospital_id)

        return {
            "subscription": subscription,
            "usage": usage,
            "context": None,
        }

    except Exception as exc:

        print(f"Failed to load hospital detail: {exc}")

        return {
            "subscription": None,
            "usage": None,
            "context": None,
        }


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
    """
    Load the list of subscription plans for the
    Plan filter dropdown. Cached for 5 minutes.
    """

    try:
        return get_all_subscription_plans() or []

    except Exception as exc:

        print(f"Failed to load plans: {exc}")
        return []


def load_hospital_plan_map():
    """
    Build a lookup { hospital_id: plan_name } by
    reading every hospital's subscription context.

    NOTE: This is O(n) Supabase calls on page load.
    Acceptable for a capstone-sized database.
    """

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

            plans_by_hospital[hospital_id] = (
                plan_name or "No Plan"
            )

        except Exception:
            plans_by_hospital[hospital_id] = "No Plan"

    return plans_by_hospital


# ============================================================
# PAGE ENTRY
# ============================================================

def show():

    initialize_state()

    load_css("manage_hospital.css")

    with st.container(key="sa_page"):

        show_flash_message()

        # --------------------------------------------------
        # PAGE HEADER
        # --------------------------------------------------

        register_clicked = page_header(
            "Manage Hospitals",
            "View registered hospitals and manage their staff.",
            action_label="Register Hospital",
            action_key="register_hospital",
            action_icon="add_business",
        )

        if register_clicked:
            open_dialog("register_hospital")

        # --------------------------------------------------
        # LOAD HOSPITALS
        # --------------------------------------------------

        hospitals = load_hospitals()

        # --------------------------------------------------
        # SEARCH + FILTERS
        # --------------------------------------------------

        search, status_filter, plan_filter = show_search_and_filters(
            hospitals
        )

        filtered = filter_hospitals(
            hospitals,
            search,
            status_filter,
            plan_filter,
        )

        # --------------------------------------------------
        # SPLIT VIEW
        # --------------------------------------------------

        render_split_view(
            filtered,
            all_hospitals=hospitals,
        )

        # --------------------------------------------------
        # DETAIL CARD
        # --------------------------------------------------

        render_detail_card(hospitals)

    # ------------------------------------------------------
    # DIALOG DISPATCHER
    # ------------------------------------------------------

    render_active_dialog()


# ============================================================
# SEARCH + FILTERS
# ============================================================

def show_search_and_filters(hospitals):

    col_search, col_status, col_plan = st.columns(
        [3, 1, 1.4]
    )

    with col_search:

        search = st.text_input(
            "Search hospitals",
            placeholder="Search by name, code, or email...",
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

    return search, status_filter, plan_filter


def filter_hospitals(
    hospitals,
    search,
    status_filter,
    plan_filter,
):

    search = (search or "").strip().lower()

    plan_map = {}

    if plan_filter != "All":
        plan_map = load_hospital_plan_map()

    filtered = []

    for hospital in hospitals:

        # ------------------------------------------------
        # SEARCH
        # ------------------------------------------------

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

        # ------------------------------------------------
        # STATUS
        # ------------------------------------------------

        if status_filter == "Active":

            if not hospital.get("is_active", True):
                continue

        elif status_filter == "Inactive":

            if hospital.get("is_active", True):
                continue

        # ------------------------------------------------
        # PLAN
        # ------------------------------------------------

        if plan_filter != "All":

            hospital_id = hospital.get("hospital_id")

            plan_name = plan_map.get(
                hospital_id,
                "No Plan",
            )

            if plan_name != plan_filter:
                continue

        filtered.append(hospital)

    return filtered


# ============================================================
# SPLIT VIEW (LIST + MAP)
# ============================================================

def render_split_view(filtered_hospitals, all_hospitals=None):
    """
    Render the two-column layout.

    The map shows every hospital in `all_hospitals`
    (so pins don't disappear when the list is filtered),
    but the selected pin is highlighted.

    If `all_hospitals` is None, falls back to
    `filtered_hospitals`.
    """

    list_col, map_col = st.columns(
        [2.4, 7.6],
        gap="medium",
    )

    # --------------------------------------------------
    # LIST PANE
    # --------------------------------------------------

    with list_col:

        section_title(
            "Hospitals",
            (
                f"{len(filtered_hospitals)} result"
                f"{'' if len(filtered_hospitals) == 1 else 's'}"
            ),
        )

        render_hospital_list(filtered_hospitals)

    # --------------------------------------------------
    # MAP PANE
    # --------------------------------------------------

    with map_col:

        render_hospital_map_pane(
            all_hospitals or filtered_hospitals
        )


# ============================================================
# HOSPITAL LIST PANE
# ============================================================

def render_hospital_list(hospitals):

    if not hospitals:

        empty_state("No hospitals match your filters.")
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

            # --------------------------------------------
            # CARD
            # --------------------------------------------

            with st.container(
                key=f"mh_list_item_{hospital_id}"
            ):

                card_left, card_right = st.columns(
                    [5, 1],
                    vertical_alignment="center",
                )

                with card_left:

                    st.markdown(
                        (
                            f'<div class="mh-list-name">'
                            f'{safe(name)}'
                            f'</div>'
                            f'<div class="mh-list-meta">'
                            f'{safe(code)} &middot; '
                            f'{safe(address[:48])}'
                            f'{"…" if len(address) > 48 else ""}'
                            f'</div>'
                        ),
                        unsafe_allow_html=True,
                    )

                with card_right:

                    # Status + verified dots
                    dots = ""

                    if is_active:
                        dots += (
                            '<span class="mh-dot mh-dot-active" '
                            'title="Active"></span>'
                        )
                    else:
                        dots += (
                            '<span class="mh-dot mh-dot-inactive" '
                            'title="Inactive"></span>'
                        )

                    if is_verified:
                        dots += (
                            '<span class="mh-dot mh-dot-verified" '
                            'title="Setup complete"></span>'
                        )

                    st.markdown(
                        f'<div class="mh-list-dots">{dots}</div>',
                        unsafe_allow_html=True,
                    )

                # ----------------------------------------
                # SELECT BUTTON (invisible overlay-style)
                # ----------------------------------------

                if st.button(
                    "Select",
                    key=f"mh_select_{hospital_id}",
                    width="stretch",
                    type=(
                        "primary"
                        if is_selected
                        else "secondary"
                    ),
                ):
                    select_hospital(hospital_id)


# ============================================================
# MAP PANE
# ============================================================

def render_hospital_map_pane(hospitals):

    # --------------------------------------------------
    # Separate hospitals with and without coordinates
    # --------------------------------------------------

    mappable = [
        h for h in hospitals
        if h.get("latitude") is not None
        and h.get("longitude") is not None
    ]

    if not mappable:

        empty_state(
            "No hospitals have coordinates yet. "
            "Register a new hospital or run the "
            "geocoding backfill script."
        )

        return

    # --------------------------------------------------
    # Currently selected hospital id
    # --------------------------------------------------

    selected = st.session_state.get(SELECTED_HOSPITAL_KEY)

    if isinstance(selected, dict):
        selected_id = selected.get("hospital_id")
    else:
        selected_id = selected

    # --------------------------------------------------
    # Render the map
    # --------------------------------------------------

    output = render_hospital_map(
        mappable,
        selected_id=selected_id,
        height=560,
        key="sa_hospital_map",
    )

    # --------------------------------------------------
    # Handle map clicks
    #
    # st_folium returns the tooltip of the last
    # clicked marker. We map that tooltip back to a
    # hospital id and update the selection state —
    # but only if the click actually changed.
    # --------------------------------------------------

    if not output:
        return

    clicked_tooltip = output.get("last_object_clicked_tooltip")

    if not clicked_tooltip:
        return

    if clicked_tooltip == st.session_state.get("mh_last_map_click"):
        return

    st.session_state["mh_last_map_click"] = clicked_tooltip

    # ------------------------------------------------
    # Resolve tooltip -> hospital id
    # ------------------------------------------------

    clicked_hospital = next(
        (
            h for h in mappable
            if (h.get("hospital_name") or "") == clicked_tooltip
        ),
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
    """
    Show the detail card for the currently selected hospital.

    The full hospital dict is stored in session state on
    selection, but we re-resolve it against `all_hospitals`
    so the card always reflects the latest data.
    """

    selected = st.session_state.get(SELECTED_HOSPITAL_KEY)

    if not selected:
        return

    selected_id = (
        selected.get("hospital_id")
        if isinstance(selected, dict)
        else selected
    )

    # --------------------------------------------------
    # Resolve full hospital record
    # --------------------------------------------------

    hospital = next(
        (
            h for h in all_hospitals
            if h.get("hospital_id") == selected_id
        ),
        selected if isinstance(selected, dict) else None,
    )

    if not hospital:
        return

    # --------------------------------------------------
    # Cache the detail payload
    # --------------------------------------------------

    detail = load_hospital_detail(hospital["hospital_id"])

    context = detail.get("subscription") or {}
    usage = detail.get("usage") or {}

    # --------------------------------------------------
    # Render
    # --------------------------------------------------

    with st.container(key="mh_detail_card"):

        render_detail_header(hospital)

        render_detail_metrics(context, usage)

        render_detail_actions(hospital)


def render_detail_header(hospital):

    name = hospital.get("hospital_name") or "Unnamed Hospital"
    code = hospital.get("hospital_code") or "—"
    hospital_type = hospital.get("hospital_type") or "—"
    address = hospital.get("address") or "—"
    contact = hospital.get("contact_number") or "—"
    email = hospital.get("email") or "—"
    website = hospital.get("website") or ""

    is_active = hospital.get("is_active", True)
    is_verified = hospital.get("setup_completed", False)

    status_label = "Active" if is_active else "Inactive"
    status_color = "green" if is_active else "red"

    verified_label = "Verified" if is_verified else "Setup Pending"
    verified_color = "green" if is_verified else "amber"

    st.markdown(
        f'<div class="mh-detail-header">'
        f'<div class="mh-detail-title">{safe(name)}</div>'
        f'<div class="mh-detail-pills">'
        f'<span class="mh-pill mh-pill-{status_color}">{safe(status_label)}</span>'
        f'<span class="mh-pill mh-pill-{verified_color}">{safe(verified_label)}</span>'
        f'</div>'
        f'</div>'
        f'<div class="mh-detail-subline">{safe(code)} &middot; {safe(hospital_type)}</div>'
        f'<div class="mh-detail-contact">'
        f'<span>📍 {safe(address)}</span>'
        f'<span>📞 {safe(contact)}</span>'
        f'<span>✉️ {safe(email)}</span>'
        + (f'<span>🌐 {safe(website)}</span>' if website else '')
        + f'</div>',
        unsafe_allow_html=True,
    )



def render_detail_metrics(context, usage):
    """
    Render subscription, usage, and timeline metrics.

    `context` comes from get_subscription_context().
    `usage`   comes from get_remaining_usage().
    """

    subscription_col, usage_col, timeline_col = st.columns(3)

    # --------------------------------------------------
    # SUBSCRIPTION
    # --------------------------------------------------

    with subscription_col:

        section_title("Subscription")

        plan_name = context.get("plan_name") or "No Plan"
        billing = context.get("billing_cycle") or "—"
        amount = context.get("amount")

        if amount:

            amount_text = f"₱{amount:,.0f}"

        else:

            amount_text = "—"

        st.markdown(
            f'<div class="mh-metric-block">'
            f'<div class="mh-metric-primary">{safe(plan_name)}</div>'
            f'<div class="mh-metric-secondary">{safe(billing)} &middot; {safe(amount_text)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


    # --------------------------------------------------
    # USAGE
    # --------------------------------------------------

    with usage_col:

        section_title("Usage")

        if usage:

            for key, label in (
                ("users", "users"),
                ("patients", "patients"),
                ("xrays", "x-rays / mo"),
            ):

                block = usage.get(key) or {}

                used = block.get("used", 0)
                limit = block.get("limit")
                unlimited = block.get("unlimited", False)

                if unlimited or limit is None:

                    value_text = f"{used} / ∞"

                else:

                    value_text = f"{used} / {limit}"

                st.markdown(
                    f'<div class="mh-usage-row">'
                    f'<span class="mh-usage-label">{safe(label)}</span>'
                    f'<span class="mh-usage-value">{safe(value_text)}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


        else:

            st.caption("No usage data available.")

    # --------------------------------------------------
    # TIMELINE
    # --------------------------------------------------

    with timeline_col:

        section_title("Timeline")

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

        st.markdown(
            f"""
            <div class="mh-metric-block">
                <div class="mh-metric-primary">
                    {safe(state_label)}
                </div>
                <div class="mh-metric-secondary">
                    {safe(str(days_left)) if days_left is not None else "—"}
                    {" days left" if days_left is not None else ""}
                </div>
                <div class="mh-metric-tertiary">
                    Ends {safe(str(end_date))}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_detail_actions(hospital):

    hospital_id = hospital["hospital_id"]
    is_active = hospital.get("is_active", True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        if st.button(
            "View Staff",
            key=f"mh_view_staff_{hospital_id}",
            icon=":material/groups:",
            width="stretch",
        ):

            open_dialog("hospital_staff", hospital=hospital)

    with col2:

        if st.button(
            "Edit",
            key=f"mh_edit_{hospital_id}",
            icon=":material/edit:",
            width="stretch",
        ):

            open_dialog("edit_hospital", hospital=hospital)

    with col3:

        if st.button(
            "Manage Subscription",
            key=f"mh_manage_sub_{hospital_id}",
            icon=":material/credit_card:",
            width="stretch",
        ):

            # Navigate to the Manage Subscriptions page
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
            ):

                open_dialog("deactivate_hospital", hospital=hospital)

        else:

            if st.button(
                "Reactivate",
                key=f"mh_reactivate_{hospital_id}",
                icon=":material/check_circle:",
                width="stretch",
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

            # Selected may be just an id — resolve it
            hospitals = load_hospitals()
            hospital = next(
                (h for h in hospitals if h.get("hospital_id") == hospital),
                None,
            )

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
            hospital = next(
                (h for h in hospitals if h.get("hospital_id") == hospital),
                None,
            )

        if hospital:
            show_edit_hospital_dialog(hospital)

    elif dialog_name == "deactivate_hospital":

        hospital = st.session_state.get(SELECTED_HOSPITAL_KEY)

        if isinstance(hospital, str):

            hospitals = load_hospitals()
            hospital = next(
                (h for h in hospitals if h.get("hospital_id") == hospital),
                None,
            )

        if hospital:
            show_deactivate_hospital_dialog(hospital)

    elif dialog_name == "reactivate_hospital":

        hospital = st.session_state.get(SELECTED_HOSPITAL_KEY)

        if isinstance(hospital, str):

            hospitals = load_hospitals()
            hospital = next(
                (h for h in hospitals if h.get("hospital_id") == hospital),
                None,
            )

        if hospital:
            show_reactivate_hospital_dialog(hospital)