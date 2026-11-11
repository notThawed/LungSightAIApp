import streamlit as st

from backend.backend_utils.subscription_utils import (
    get_all_subscription_plans,
    get_inactive_subscription_plans,
    create_subscription,
    edit_subscription,
    deactivate_subscription,
    activate_subscription,
    delete_subscription,
)
from backend.supabase_client import admin_supabase

from streamlit_app.components.ui import (
    page_header,
    metric_card,
    empty_state,
    section_title,
    note,
    show_rows,
    safe,
    peso,
    limit_text,
    pill,
    confirm_buttons,
    remember,
    show_flash_message,
)

from shared.assets import load_css


# ============================================================
# INLINE SVG ICONS
# ============================================================

ICONS = {
    "users": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    "patients": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    "scans": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="m9 15 3-3 3 3"/><path d="m9 9 3 3 3-3"/></svg>',
    "hospital": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16"/><path d="M9 21v-4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v4"/><path d="M10 9h4"/><path d="M12 7v4"/></svg>',
    "shield": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    "crown": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m2 4 3 12h14l3-12-6 7-4-7-4 7-6-7zm3 16h14"/></svg>',
    "badge": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>',
    "infinity": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 12c-2-2.5-4-4-6.5-4A4.5 4.5 0 0 0 1 12.5a4.5 4.5 0 0 0 4.5 4.5c2.5 0 4.5-2 6.5-4.5 2 2.5 4 4.5 6.5 4.5a4.5 4.5 0 0 0 4.5-4.5 4.5 4.5 0 0 0-4.5-4.5c-2.5 0-4.5 1.5-6.5 4Z"/></svg>',
}


# ============================================================
# STATS & SUBSCRIBER FETCHING
# ============================================================

def get_subscription_stats():
    """Fetch count of hospital subscriptions grouped by plan_id."""
    try:
        response = admin_supabase.table("hospital_subscriptions").select("plan_id, status").execute()
        rows = response.data or []
        counts_by_plan = {}
        active_facilities = 0

        for r in rows:
            pid = r.get("plan_id")
            counts_by_plan[pid] = counts_by_plan.get(pid, 0) + 1
            if r.get("status") in ("Active", "Pending Setup", "Trial"):
                active_facilities += 1

        return counts_by_plan, len(rows), active_facilities
    except Exception:
        return {}, 0, 0


# ============================================================
# TIER METADATA HELPER
# ============================================================

def get_tier_info(plan_name):
    """Categorize plan for visual styling and badge display."""
    name_lower = (plan_name or "").lower()

    if "basic" in name_lower or "starter" in name_lower:
        return {
            "tier_label": "Starter Tier",
            "tier_cls": "sa-tier-basic",
            "icon": ICONS["shield"],
        }
    elif "pro" in name_lower or "growth" in name_lower:
        return {
            "tier_label": "Most Popular",
            "tier_cls": "sa-tier-pro",
            "icon": ICONS["crown"],
        }
    elif "enterprise" in name_lower or "corporate" in name_lower or "hospital" in name_lower:
        return {
            "tier_label": "Enterprise",
            "tier_cls": "sa-tier-enterprise",
            "icon": ICONS["badge"],
        }
    else:
        return {
            "tier_label": "Custom Tier",
            "tier_cls": "sa-tier-custom",
            "icon": ICONS["badge"],
        }


# ============================================================
# ACTION RUNNER & INPUT HELPERS
# ============================================================

def run_action(action, plan_id):
    """Run activate / deactivate and show the result."""
    result = action(plan_id)

    if result.get("success"):
        remember(result.get("message", "Action completed successfully."))
        st.rerun()
    else:
        st.error(result.get("message", "An unexpected error occurred."))


def limit_input(label, key, current=None, step=1):
    """'Unlimited' checkbox + number box. Returns None (unlimited) or an integer."""
    unlimited = st.checkbox(
        f"Unlimited {label.lower()}",
        value=current is None,
        key=f"{key}_unlimited",
    )

    number = st.number_input(
        label,
        min_value=1,
        value=int(current) if current else 1,
        step=step,
        disabled=unlimited,
        key=f"{key}_value",
    )

    return None if unlimited else int(number)


def limits_html(plan):
    """Render quota limits as medical-grade metric badges."""
    limits = [
        ("User Accounts", plan.get("max_users"), "users"),
        ("Patient Records", plan.get("max_patients"), "patients"),
        ("Monthly AI Scans", plan.get("max_xrays_per_month"), "scans"),
    ]

    items = []
    for label, value, icon_key in limits:
        icon_svg = ICONS.get(icon_key, "")
        if value is None:
            val_html = f"<span class='sa-limit-val unlimited'>{ICONS['infinity']} Unlimited</span>"
        else:
            val_html = f"<span class='sa-limit-val'>{value:,}</span>"

        items.append(
            f"<div class='sa-limit-item'>"
            f"<div class='sa-limit-top'>"
            f"<span class='sa-limit-icon'>{icon_svg}</span>"
            f"{val_html}"
            f"</div>"
            f"<span class='sa-limit-label'>{label}</span>"
            f"</div>"
        )

    return f"<div class='sa-limits-grid'>{''.join(items)}</div>"


# ============================================================
# PLAN CARD RENDERING
# ============================================================

def render_plan_card(plan, inactive=False, counts_by_plan=None):
    """Render a single modern subscription plan card."""
    counts_by_plan = counts_by_plan or {}
    plan_id = plan["plan_id"]
    is_active = plan.get("is_active", not inactive)
    plan_name = plan.get("plan_name") or "Unnamed Plan"
    description = safe(plan.get("description")) if plan.get("description") else "No tier description provided."

    tier_info = get_tier_info(plan_name)
    tier_cls = "sa-tier-inactive" if not is_active else tier_info["tier_cls"]
    tier_label = "Archived" if not is_active else tier_info["tier_label"]
    tier_icon = ICONS["shield"] if not is_active else tier_info["icon"]

    # Subscriber count
    sub_count = counts_by_plan.get(plan_id, 0)
    if sub_count > 0:
        sub_label = f"{sub_count} {'facility' if sub_count == 1 else 'facilities'} enrolled"
        sub_tag = f"<span class='sa-plan-sub-tag active'>{ICONS['hospital']} {sub_label}</span>"
    else:
        sub_tag = f"<span class='sa-plan-sub-tag empty'>{ICONS['hospital']} No subscribers</span>"

    # Pricing calculations
    monthly_price = float(plan.get("price_monthly") or 0)
    yearly_price = float(plan.get("price_yearly") or 0)

    if monthly_price == 0:
        pricing_html = (
            f"<div class='sa-plan-pricing-box'>"
            f"<div class='sa-plan-price-main'>"
            f"<span class='sa-plan-amount'>Free</span>"
            f"<span class='sa-plan-period'>/ unlimited access</span>"
            f"</div>"
            f"<div class='sa-plan-yearly-row'>"
            f"<span>Complimentary Institutional Tier</span>"
            f"<span class='sa-plan-badge-savings'>Included</span>"
            f"</div>"
            f"</div>"
        )
    else:
        yearly_discount_badge = ""
        if monthly_price > 0 and yearly_price > 0:
            twelve_months = monthly_price * 12
            if yearly_price < twelve_months:
                savings_pct = round(((twelve_months - yearly_price) / twelve_months) * 100)
                yearly_discount_badge = f"<span class='sa-plan-badge-savings'>Save {savings_pct}%</span>"
            elif yearly_price == twelve_months:
                yearly_discount_badge = "<span class='sa-plan-badge-annual'>Annual Billing</span>"

        pricing_html = (
            f"<div class='sa-plan-pricing-box'>"
            f"<div class='sa-plan-price-main'>"
            f"<span class='sa-plan-currency'>₱</span>"
            f"<span class='sa-plan-amount'>{monthly_price:,.2f}</span>"
            f"<span class='sa-plan-period'>/ month</span>"
            f"</div>"
            f"<div class='sa-plan-yearly-row'>"
            f"<span>₱{yearly_price:,.2f} billed annually</span>"
            f"{yearly_discount_badge}"
            f"</div>"
            f"</div>"
        )

    with st.container(key=f"sa_card_plan_{plan_id}"):
        st.markdown(
            f"<div class='sa-plan-accent-bar {tier_cls}'></div>"
            f"<div class='sa-plan-head'>"
            f"<span class='sa-tier-pill {tier_cls}'>{tier_icon} {tier_label}</span>"
            f"<div class='sa-plan-head-right'>"
            f"{sub_tag}"
            f"{pill('Active', 'green') if is_active else pill('Inactive', 'grey')}"
            f"</div>"
            f"</div>"
            f"<h3 class='sa-plan-name'>{safe(plan_name)}</h3>"
            f"<p class='sa-plan-desc'>{description}</p>"
            f"{pricing_html}"
            f"<div class='sa-plan-section-label'>Resource Quotas &amp; Limits</div>"
            f"{limits_html(plan)}",
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)

        if inactive:
            if c1.button("Reactivate", key=f"activate_inactive_{plan_id}", icon=":material/play_circle:", width="stretch", type="primary"):
                run_action(activate_subscription, plan_id)

            if c2.button("Delete", key=f"delete_inactive_{plan_id}", icon=":material/delete:", width="stretch"):
                show_delete_plan_dialog(plan, sub_count)
        else:
            if c1.button("Edit Plan", key=f"edit_plan_{plan_id}", icon=":material/edit:", width="stretch"):
                show_edit_plan_dialog(plan)

            if is_active:
                if c2.button("Deactivate", key=f"deactivate_plan_{plan_id}", icon=":material/pause_circle:", width="stretch"):
                    run_action(deactivate_subscription, plan_id)
            else:
                if c2.button("Activate", key=f"activate_plan_{plan_id}", icon=":material/play_circle:", width="stretch", type="primary"):
                    run_action(activate_subscription, plan_id)


def render_plan_grid(plans, inactive=False, counts_by_plan=None):
    """Render plan cards in a clean 2-column grid."""
    for start in range(0, len(plans), 2):
        for column, plan in zip(st.columns(2, gap="medium"), plans[start:start + 2]):
            with column:
                render_plan_card(plan, inactive=inactive, counts_by_plan=counts_by_plan)


# ============================================================
# LIVE CARD PREVIEW (Used during Plan Creation)
# ============================================================

def render_live_preview_card(preview_data):
    """Render a live preview card that dynamically reflects form input."""
    plan_name = preview_data.get("plan_name") or "New Tier Preview"
    description = preview_data.get("description") or "Tier description will appear here as you type."
    monthly_price = float(preview_data.get("price_monthly") or 0)
    yearly_price = float(preview_data.get("price_yearly") or 0)

    tier_info = get_tier_info(plan_name)

    if monthly_price == 0:
        pricing_html = (
            f"<div class='sa-plan-pricing-box'>"
            f"<div class='sa-plan-price-main'>"
            f"<span class='sa-plan-amount'>Free</span>"
            f"<span class='sa-plan-period'>/ unlimited access</span>"
            f"</div>"
            f"<div class='sa-plan-yearly-row'>"
            f"<span>Complimentary Institutional Tier</span>"
            f"<span class='sa-plan-badge-savings'>Included</span>"
            f"</div>"
            f"</div>"
        )
    else:
        yearly_discount_badge = ""
        if monthly_price > 0 and yearly_price > 0:
            twelve_months = monthly_price * 12
            if yearly_price < twelve_months:
                savings_pct = round(((twelve_months - yearly_price) / twelve_months) * 100)
                yearly_discount_badge = f"<span class='sa-plan-badge-savings'>Save {savings_pct}%</span>"
            elif yearly_price == twelve_months:
                yearly_discount_badge = "<span class='sa-plan-badge-annual'>Annual Billing</span>"

        pricing_html = (
            f"<div class='sa-plan-pricing-box'>"
            f"<div class='sa-plan-price-main'>"
            f"<span class='sa-plan-currency'>₱</span>"
            f"<span class='sa-plan-amount'>{monthly_price:,.2f}</span>"
            f"<span class='sa-plan-period'>/ month</span>"
            f"</div>"
            f"<div class='sa-plan-yearly-row'>"
            f"<span>₱{yearly_price:,.2f} billed annually</span>"
            f"{yearly_discount_badge}"
            f"</div>"
            f"</div>"
        )

    st.markdown(
        f"<div class='sa-preview-shell'>"
        f"<div class='sa-plan-accent-bar {tier_info['tier_cls']}'></div>"
        f"<div class='sa-preview-ribbon'>Live Card Preview</div>"
        f"<div class='sa-plan-head'>"
        f"<span class='sa-tier-pill {tier_info['tier_cls']}'>{tier_info['icon']} {tier_info['tier_label']}</span>"
        f"<div class='sa-plan-head-right'>"
        f"<span class='sa-plan-sub-tag empty'>{ICONS['hospital']} New Plan</span>"
        f"{pill('Active', 'green')}"
        f"</div>"
        f"</div>"
        f"<h3 class='sa-plan-name'>{safe(plan_name)}</h3>"
        f"<p class='sa-plan-desc'>{safe(description)}</p>"
        f"{pricing_html}"
        f"<div class='sa-plan-section-label'>Resource Quotas &amp; Limits</div>"
        f"{limits_html(preview_data)}"
        f"</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# EDIT PLAN DIALOG
# ============================================================

@st.dialog("Edit subscription plan", width="medium")
def show_edit_plan_dialog(plan):
    plan_id = plan["plan_id"]

    with st.container(key="sa_dialog"):
        section_title(
            f"Edit Plan: {safe(plan['plan_name'])}",
            "Update pricing, feature descriptions, and resource allowances for this tier.",
        )

        note("Price updates apply to upcoming hospital subscription renewals and new subscriptions.", "teal")

        errors = st.container()

        plan_name = st.text_input(
            "Plan name *",
            value=plan["plan_name"],
            key=f"edit_{plan_id}_name",
        )

        description = st.text_area(
            "Description",
            value=plan.get("description") or "",
            height=75,
            key=f"edit_{plan_id}_desc",
        )

        monthly_col, yearly_col = st.columns(2)

        price_monthly = monthly_col.number_input(
            "Monthly price (₱)",
            min_value=0.0,
            value=float(plan.get("price_monthly") or 0),
            step=500.0,
            format="%.2f",
            key=f"edit_{plan_id}_monthly",
        )

        price_yearly = yearly_col.number_input(
            "Yearly price (₱)",
            min_value=0.0,
            value=float(plan.get("price_yearly") or 0),
            step=1000.0,
            format="%.2f",
            key=f"edit_{plan_id}_yearly",
        )

        st.caption("Resource Quotas & System Limits")
        users_col, patients_col, xrays_col = st.columns(3)

        with users_col:
            max_users = limit_input("Users", f"edit_{plan_id}_users", plan.get("max_users"), 1)

        with patients_col:
            max_patients = limit_input("Patients", f"edit_{plan_id}_patients", plan.get("max_patients"), 100)

        with xrays_col:
            max_xrays = limit_input("X-rays / mo", f"edit_{plan_id}_xrays", plan.get("max_xrays_per_month"), 100)

        st.divider()
        cancel_col, save_col = st.columns(2)

        if cancel_col.button("Cancel", key=f"cancel_edit_{plan_id}", width="stretch"):
            st.rerun()

        if save_col.button("Save Changes", key=f"save_edit_{plan_id}", type="primary", icon=":material/save:", width="stretch"):
            if not plan_name.strip():
                errors.error("Plan name is required.")
                return

            result = edit_subscription(
                plan_id=plan_id,
                plan_name=plan_name.strip(),
                description=description.strip(),
                price_monthly=price_monthly,
                price_yearly=price_yearly,
                max_users=max_users,
                max_patients=max_patients,
                max_xrays_per_month=max_xrays,
            )

            if result.get("success"):
                remember(result.get("message", "Subscription plan updated successfully."))
                st.rerun()
            else:
                errors.error(result.get("message", "Failed to update subscription plan."))


# ============================================================
# CONFIRM NEW PLAN CREATION
# ============================================================

@st.dialog("Confirm New Subscription Plan", width="medium")
def show_confirm_plan_dialog(plan):
    with st.container(key="sa_dialog"):
        note("Review the subscription tier details before publishing it to hospital registrations.", "amber")

        show_rows([
            ("Plan Name", plan["plan_name"]),
            ("Description", plan["description"] or "None"),
            ("Monthly Price", peso(plan["price_monthly"])),
            ("Yearly Price", peso(plan["price_yearly"])),
        ])

        st.markdown(
            f"<div class='sa-dialog-plan-summary'>"
            f"<div class='sa-dialog-quota-row'><span>{ICONS['users']} Staff Accounts</span><b>{limit_text(plan['max_users'])}</b></div>"
            f"<div class='sa-dialog-quota-row'><span>{ICONS['patients']} Patient Records</span><b>{limit_text(plan['max_patients'])}</b></div>"
            f"<div class='sa-dialog-quota-row'><span>{ICONS['scans']} Monthly AI Scans</span><b>{limit_text(plan['max_xrays_per_month'])}</b></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        st.caption("Once created, this tier will immediately become active for all hospital onboarding registrations.")

        if confirm_buttons("create_plan", "Confirm and Publish Plan"):
            result = create_subscription(
                plan_name=plan["plan_name"],
                description=plan["description"],
                price_monthly=plan["price_monthly"],
                price_yearly=plan["price_yearly"],
                max_users=plan["max_users"],
                max_xrays_per_month=plan["max_xrays_per_month"],
                max_patients=plan["max_patients"],
            )

            if result.get("success"):
                remember(result.get("message", "Subscription plan published successfully."))
                st.rerun()
            else:
                st.error(result.get("message", "Failed to create subscription plan."))


# ============================================================
# ADD PLAN FORM (2-Column Form + Live Preview)
# ============================================================

def render_add_plan_form():
    """Form to create a plan with real-time interactive preview card."""
    with st.container(key="sa_card_add_plan"):
        form_col, preview_col = st.columns([1.1, 0.9], gap="large")

        with form_col:
            section_title(
                "Plan Configuration",
                "Define tier pricing, descriptions, and hospital capacity limits.",
            )

            name_col, price_col = st.columns([1.4, 1])
            plan_name = name_col.text_input(
                "Plan Name *",
                placeholder="e.g. Professional Care",
                key="add_plan_name",
            )

            price_monthly = price_col.number_input(
                "Monthly Price (₱)",
                min_value=0.0,
                step=500.0,
                value=2999.0,
                format="%.2f",
                key="add_plan_price",
            )

            # Auto calculate annual discount (10 months pricing for 12 months = ~17% off)
            default_yearly = price_monthly * 10
            custom_yearly = st.checkbox(
                "Custom yearly price (defaults to 2 months free)",
                value=False,
                key="add_custom_yearly",
            )

            if custom_yearly:
                price_yearly = st.number_input(
                    "Yearly Price (₱)",
                    min_value=0.0,
                    value=float(default_yearly),
                    step=1000.0,
                    format="%.2f",
                    key="add_plan_price_yearly",
                )
            else:
                price_yearly = default_yearly
                st.caption(f"⚡ Annual price automatically set to **{peso(price_yearly)} / year** (Save ~17%)")

            description = st.text_area(
                "Description",
                placeholder="Describe which hospitals or clinics this tier is ideal for...",
                height=80,
                key="add_plan_desc",
            )

            st.caption("Resource Quotas & System Limits")
            users_col, patients_col, xrays_col = st.columns(3)

            with users_col:
                max_users = limit_input("Users", "add_users", current=15, step=1)

            with patients_col:
                max_patients = limit_input("Patients", "add_patients", current=2000, step=100)

            with xrays_col:
                max_xrays = limit_input("AI Scans / mo", "add_xrays", current=500, step=50)

            st.divider()

            if st.button("Review & Publish Plan", key="review_plan", type="primary", icon=":material/fact_check:"):
                if not plan_name.strip():
                    st.error("Plan name is required.")
                    return

                show_confirm_plan_dialog({
                    "plan_name": plan_name.strip(),
                    "description": description.strip(),
                    "price_monthly": price_monthly,
                    "price_yearly": price_yearly,
                    "max_users": max_users,
                    "max_patients": max_patients,
                    "max_xrays_per_month": max_xrays,
                })

        with preview_col:
            # Build preview dict from current form values
            preview_data = {
                "plan_name": plan_name.strip() if plan_name else "Tier Name",
                "description": description.strip() if description else "Plan description will appear here as you type.",
                "price_monthly": price_monthly,
                "price_yearly": price_yearly,
                "max_users": max_users,
                "max_patients": max_patients,
                "max_xrays_per_month": max_xrays,
                "is_active": True,
            }
            render_live_preview_card(preview_data)
            st.caption("ℹ️ Live card preview reflects how this tier displays to hospital representatives and on administrative reports.")


# ============================================================
# DELETE INACTIVE PLAN DIALOG
# ============================================================

@st.dialog("Delete subscription plan", width="small")
def show_delete_plan_dialog(plan, enrolled_count=0):
    plan_id = plan["plan_id"]
    plan_name = plan.get("plan_name") or f"Plan #{plan_id}"

    with st.container(key="sa_dialog"):
        st.markdown(
            f"<p class='sa-dialog-text'>Permanently delete <b>{safe(plan_name)}</b>?</p>",
            unsafe_allow_html=True,
        )

        if enrolled_count > 0:
            note(
                f"⚠️ {enrolled_count} hospital facility record(s) reference this subscription plan. "
                "Deleting it may cause data inconsistencies. Keeping it deactivated is strongly recommended instead.",
                "amber",
            )
        else:
            note("This tier has no enrolled hospitals. Deletion is permanent and cannot be undone.", "red")

        show_rows([
            ("Monthly price", peso(plan.get("price_monthly"))),
            ("Yearly price", peso(plan.get("price_yearly"))),
            ("Subscribed facilities", f"{enrolled_count} facilities"),
        ])

        if confirm_buttons(f"delete_plan_{plan_id}", "Delete Permanently"):
            result = delete_subscription(plan_id)

            if result.get("success"):
                remember(result.get("message", "Subscription plan deleted successfully."))
                st.rerun()
            else:
                st.error(result.get("message", "Failed to delete subscription plan."))


# ============================================================
# MAIN PAGE
# ============================================================

def show():
    load_css("manage_subscriptions.css")
    show_flash_message()

    with st.container(key="sa_page"):
        page_header(
            "Manage subscriptions",
            "Configure LungSight subscription plans, pricing tiers, and hospital capacity limits.",
        )

        # ---------------- Load Plans & Stats ----------------
        all_plans = get_all_subscription_plans() or []
        counts_by_plan, total_subs, active_facilities = get_subscription_stats()

        active_plans = [p for p in all_plans if p.get("is_active")]
        inactive_plans = [p for p in all_plans if not p.get("is_active")]

        # ---------------- Top KPI Metrics Bar ----------------
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            metric_card("Total Plans", len(all_plans), "layers", "teal")

        with c2:
            metric_card("Active Plans", len(active_plans), "verified", "green")

        with c3:
            metric_card("Active Hospitals", active_facilities, "domain", "blue")

        with c4:
            metric_card("Archived Plans", len(inactive_plans), "archive", "amber" if inactive_plans else "teal")

        st.markdown("<div style='margin-bottom: 0.5rem;'></div>", unsafe_allow_html=True)

        # ---------------- Modern Tabs ----------------
        plans_tab, add_tab, inactive_tab = st.tabs([
            f"Active Plans ({len(active_plans)})",
            "Add New Plan",
            f"Archived Plans ({len(inactive_plans)})",
        ])

        # ---------------- Tab 1: Active Plans ----------------
        with plans_tab:
            if active_plans:
                # Search & Filter Toolbar
                with st.container(key="sa_subs_toolbar_container"):
                    t1, t2, t3 = st.columns([2.5, 1.2, 1.5], vertical_alignment="center")

                    with t1:
                        search_query = st.text_input(
                            "Search active plans...",
                            placeholder="Search by plan name or description...",
                            key="sub_search_active",
                            label_visibility="collapsed",
                        )

                    with t2:
                        sort_option = st.selectbox(
                            "Sort plans",
                            ["Tier (Default)", "Price: Low to High", "Price: High to Low", "Most Subscribed"],
                            key="sub_sort_active",
                            label_visibility="collapsed",
                        )

                    with t3:
                        st.markdown(
                            f"<div style='text-align: right;'>"
                            f"<span class='sa-subs-count-badge'><b>{len(active_plans)}</b> active tiers</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                # Filter by search
                filtered = active_plans
                if search_query.strip():
                    q = search_query.strip().lower()
                    filtered = [
                        p for p in filtered
                        if q in (p.get("plan_name") or "").lower()
                        or q in (p.get("description") or "").lower()
                    ]

                # Sort
                if sort_option == "Price: Low to High":
                    filtered = sorted(filtered, key=lambda x: float(x.get("price_monthly") or 0))
                elif sort_option == "Price: High to Low":
                    filtered = sorted(filtered, key=lambda x: float(x.get("price_monthly") or 0), reverse=True)
                elif sort_option == "Most Subscribed":
                    filtered = sorted(filtered, key=lambda x: counts_by_plan.get(x.get("plan_id"), 0), reverse=True)

                if filtered:
                    render_plan_grid(filtered, inactive=False, counts_by_plan=counts_by_plan)
                else:
                    empty_state(f"No subscription plans matched '{search_query}'.")
            else:
                empty_state("No active subscription plans found. Publish a plan using the 'Add New Plan' tab.")

        # ---------------- Tab 2: Add Plan Form ----------------
        with add_tab:
            render_add_plan_form()

        # ---------------- Tab 3: Archived Plans ----------------
        with inactive_tab:
            if inactive_plans:
                st.caption("Archived tiers are preserved for historical audit trails but cannot be selected for new hospital subscriptions.")
                render_plan_grid(inactive_plans, inactive=True, counts_by_plan=counts_by_plan)
            else:
                empty_state("There are no archived subscription plans. All configured tiers are currently active.")
