from html import escape
from pathlib import Path

import streamlit as st

from backend.backend_utils.application_utils import create_hospital_application
from backend.supabase_client import admin_supabase
from backend.auth import auth_email_exists


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APPLICATION_CSS_PATH = (
    PROJECT_ROOT / "shared" / "theme" / "css_content" / "application.css"
)


# ============================================================
# STEPS
# (short name for the progress tracker, full title for the heading)
# ============================================================

APPLICATION_STEPS = [
    ("Hospital", "Hospital Information"),
    ("Representative", "Authorized Representative"),
    ("Plan", "Selected Subscription"),
    ("Administrator", "Hospital Administrator"),
    ("Agreement", "Service Agreement"),
    ("Review", "Review & Submit"),
    ("Payment", "Payment"),
]

HOSPITAL_TYPES = [
    "Government Hospital",
    "Private Hospital",
    "Medical Center",
    "Other",
]

AGREEMENT_TEXT = """
**LungSight Service Agreement**

By proceeding with this application, the hospital acknowledges that:

- The information provided in this application is accurate and complete.
- The selected subscription will be subject to approval by the LungSight
  system administrator.
- LungSight is intended to support healthcare professionals and does not
  replace professional medical judgment.
- Hospital users are responsible for maintaining the confidentiality of
  their account credentials.
- Patient information must be handled in accordance with applicable
  privacy and security requirements.
"""


# ============================================================
# SMALL HELPERS
# ============================================================

def load_application_css():
    if APPLICATION_CSS_PATH.exists():
        css = APPLICATION_CSS_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def safe(value):
    """Escape text before putting it inside HTML. Empty values show a dash."""
    text = escape(str(value or "").strip())
    return text or "—"


def peso(amount):
    """1500 -> ₱1,500.00"""
    return f"₱{float(amount or 0):,.2f}"


def limit_text(value):
    """None means no limit in the database."""
    if value is None:
        return "Unlimited"
    return f"{value:,}"


def full_name(person):
    parts = [
        person.get("first_name"),
        person.get("middle_name"),
        person.get("last_name"),
    ]
    return " ".join(part for part in parts if part)


def is_valid_email(email):
    name, _, domain = email.partition("@")
    return bool(name) and "." in domain and " " not in email


def find_missing(required):
    """required looks like {"Field label": value}. Returns the empty ones."""
    return [label for label, value in required.items() if not value.strip()]


def get_amount(subscription):
    if subscription.get("billing_cycle") == "Yearly":
        return float(subscription.get("price_yearly") or 0)
    return float(subscription.get("price_monthly") or 0)


def go_to_step(step):
    st.session_state.client_application_step = step
    st.rerun()


def rows_html(rows):
    """Label / value rows, e.g. [("Plan", "Standard"), ("Users", "10")]."""
    items = "".join(
        f"<div class='ls-row'><span>{label}</span><b>{safe(value)}</b></div>"
        for label, value in rows
    )
    return f"<div class='ls-rows'>{items}</div>"


def limits_html(subscription):
    """The three plan limits shown side by side."""
    limits = [
        ("Users", limit_text(subscription.get("max_users"))),
        ("Patients", limit_text(subscription.get("max_patients"))),
        ("X-rays per month", limit_text(subscription.get("max_xrays_per_month"))),
    ]

    items = "".join(
        f"<div class='ls-limit'><b>{value}</b><span>{label}</span></div>"
        for label, value in limits
    )

    return f"<div class='ls-limits'>{items}</div>"


def note(text, kind=""):
    """A small colored message box. kind can be '' or 'success'."""
    st.markdown(
        f"<div class='ls-note ls-note-{kind}'>{text}</div>",
        unsafe_allow_html=True,
    )


def step_header(title, caption, required=False):
    required_text = "<span class='ls-required'>* Required</span>" if required else ""

    st.markdown(
        "<div class='ls-step-header'>"
        f"<div><p class='ls-step-title'>{title}</p>"
        f"<p class='ls-step-caption'>{caption}</p></div>"
        f"{required_text}"
        "</div>",
        unsafe_allow_html=True,
    )


def name_fields(data):
    """First / middle / last name in one row."""
    first_col, middle_col, last_col = st.columns(3)

    first_name = first_col.text_input(
        "First name *", value=data.get("first_name", "")
    )
    middle_name = middle_col.text_input(
        "Middle name", value=data.get("middle_name", "")
    )
    last_name = last_col.text_input(
        "Last name *", value=data.get("last_name", "")
    )

    return first_name, middle_name, last_name


def form_nav_buttons():
    """Back and Next buttons inside an st.form."""
    back_col, next_col = st.columns(2)

    back = back_col.form_submit_button("Back", width="stretch")
    go_next = next_col.form_submit_button("Next", type="primary", width="stretch")

    return back, go_next


def nav_buttons(key, back_step, next_label="Next"):
    """Back and Next buttons for steps without a form. True if Next was clicked."""
    back_col, next_col = st.columns(2)

    if back_col.button("Back", key=f"{key}_back", width="stretch"):
        go_to_step(back_step)

    return next_col.button(
        next_label, key=f"{key}_next", type="primary", width="stretch"
    )


# ============================================================
# INITIALIZE / CLEAR
# ============================================================

def initialize_application(plan):

    current_plan_id = plan.get("plan_id")
    existing_application = st.session_state.get("client_application")

    existing_plan_id = None

    if existing_application:
        existing_plan_id = existing_application.get("subscription", {}).get("plan_id")

    # Start a new application when none exists or a different plan was chosen
    if existing_application is None or existing_plan_id != current_plan_id:

        st.session_state.client_application = {
            "hospital": {},
            "representative": {},
            "subscription": {
                "plan_id": plan.get("plan_id"),
                "plan_name": plan.get("plan_name"),
                "price_monthly": plan.get("price_monthly"),
                "price_yearly": plan.get("price_yearly"),
                "max_users": plan.get("max_users"),
                "max_patients": plan.get("max_patients"),
                "max_xrays_per_month": plan.get("max_xrays_per_month"),
                "billing_cycle": "Monthly",
            },
            "administrator": {},
            "agreement": {},
        }

        st.session_state.client_application_step = 0

    if "client_application_step" not in st.session_state:
        st.session_state.client_application_step = 0

    # Clear leftover payment state on a fresh application
    if existing_application is None:
        for key in ("application_id", "checkout_url", "payment_success"):
            st.session_state.pop(key, None)


def clear_application():

    keys_to_clear = (
        "client_application",
        "client_application_step",
        "selected_plan",
        "show_application_form",
        "application_submitted",
        "application_billing_cycle",
        "application_id",
        "checkout_url",
        "payment_success",
    )

    for key in keys_to_clear:
        st.session_state.pop(key, None)


# ============================================================
# PROGRESS TRACKER
# ============================================================

def render_progress():

    current = st.session_state.client_application_step
    total = len(APPLICATION_STEPS)

    percent = round(current / total * 100)

    if current + 1 < total:
        up_next = f"Next: {APPLICATION_STEPS[current + 1][1]}"
    else:
        up_next = "Last step"

    # One dot per step: a check mark when done, a number otherwise
    steps_html = ""

    for number, (short_name, _) in enumerate(APPLICATION_STEPS):
        if number < current:
            state, mark = "done", "✓"
        elif number == current:
            state, mark = "current", number + 1
        else:
            state, mark = "todo", number + 1

        steps_html += (
            f"<div class='ls-step ls-step-{state}'>"
            f"<span class='ls-dot'>{mark}</span>"
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
        f"<div class='ls-progress-percent'>{percent}%<small>complete</small></div>"
        "</div>"
        f"<div class='ls-bar'><div class='ls-bar-fill' style='width:{percent}%'></div></div>"
        f"<div class='ls-steps'>{steps_html}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# STEP 1 - HOSPITAL INFORMATION
# ============================================================

def render_hospital_information():

    step_header(
        "Hospital information",
        "Provide the official details of the hospital or healthcare facility.",
        required=True,
    )

    # error messages show up here, above the form, so they are easy to see
    errors = st.container()

    data = st.session_state.client_application["hospital"]

    current_type = data.get("hospital_type", HOSPITAL_TYPES[0])
    if current_type not in HOSPITAL_TYPES:
        current_type = HOSPITAL_TYPES[0]

    with st.form("hospital_information_form"):

        hospital_name = st.text_input(
            "Hospital name *",
            value=data.get("hospital_name", ""),
            placeholder="e.g. Mandaue City Hospital",
        )

        type_col, contact_col = st.columns(2)

        hospital_type = type_col.selectbox(
            "Hospital type *",
            HOSPITAL_TYPES,
            index=HOSPITAL_TYPES.index(current_type),
        )

        contact_number = contact_col.text_input(
            "Contact number *",
            value=data.get("contact_number", ""),
            placeholder="+63 9XX XXX XXXX",
        )

        address = st.text_area(
            "Complete address *",
            value=data.get("address", ""),
            placeholder="Street / Barangay / City / Province",
            height=80,
        )

        email_col, website_col = st.columns(2)

        hospital_email = email_col.text_input(
            "Official hospital email *",
            value=data.get("hospital_email", ""),
            placeholder="hospital@example.com",
        )

        website = website_col.text_input(
            "Website",
            value=data.get("website", ""),
            placeholder="https://example.com",
        )

        submitted = st.form_submit_button("Next", type="primary", width="stretch")

    if not submitted:
        return

    missing = find_missing({
        "Hospital name": hospital_name,
        "Complete address": address,
        "Contact number": contact_number,
        "Official hospital email": hospital_email,
    })

    if missing:
        errors.error("Please complete: " + ", ".join(missing) + ".")
        return

    hospital_email = hospital_email.strip().lower()

    if not is_valid_email(hospital_email):
        errors.error("Please enter a valid hospital email address.")
        return

    # Make sure this hospital email is not already registered
    try:
        response = (
            admin_supabase
            .table("hospitals")
            .select("hospital_id")
            .eq("email", hospital_email)
            .limit(1)
            .execute()
        )

        if response.data:
            errors.error("This hospital email already exists.")
            return

    except Exception as e:
        errors.error(f"Unable to verify the hospital email: {e}")
        return

    st.session_state.client_application["hospital"] = {
        "hospital_name": hospital_name.strip(),
        "hospital_type": hospital_type,
        "address": address.strip(),
        "contact_number": contact_number.strip(),
        "hospital_email": hospital_email,
        "website": website.strip(),
    }

    go_to_step(1)


# ============================================================
# STEP 2 - AUTHORIZED REPRESENTATIVE
# ============================================================

def render_authorized_representative():

    step_header(
        "Authorized representative",
        "The person authorized to submit this application for the hospital.",
        required=True,
    )

    # error messages show up here, above the form, so they are easy to see
    errors = st.container()

    data = st.session_state.client_application["representative"]

    with st.form("authorized_representative_form"):

        first_name, middle_name, last_name = name_fields(data)

        position = st.text_input(
            "Position / designation *",
            value=data.get("position", ""),
            placeholder="e.g. Hospital Director",
        )

        contact_col, email_col = st.columns(2)

        contact_number = contact_col.text_input(
            "Contact number *",
            value=data.get("contact_number", ""),
            placeholder="+63 9XX XXX XXXX",
        )

        email = email_col.text_input(
            "Email address *",
            value=data.get("email", ""),
            placeholder="representative@hospital.org",
        )

        back, go_next = form_nav_buttons()

    if back:
        go_to_step(0)

    if not go_next:
        return

    missing = find_missing({
        "First name": first_name,
        "Last name": last_name,
        "Position": position,
        "Contact number": contact_number,
        "Email address": email,
    })

    if missing:
        errors.error("Please complete: " + ", ".join(missing) + ".")
        return

    email = email.strip().lower()

    if not is_valid_email(email):
        errors.error("Please enter a valid email address.")
        return

    st.session_state.client_application["representative"] = {
        "first_name": first_name.strip(),
        "middle_name": middle_name.strip(),
        "last_name": last_name.strip(),
        "position": position.strip(),
        "contact_number": contact_number.strip(),
        "email": email,
    }

    go_to_step(2)


# ============================================================
# STEP 3 - SELECTED SUBSCRIPTION
# Shown as a box so the person can double-check their choice.
# ============================================================

def render_subscription_confirmation():

    step_header(
        "Selected subscription",
        "Confirm the plan you chose and how you would like to be billed.",
    )

    subscription = st.session_state.client_application["subscription"]

    monthly = float(subscription.get("price_monthly") or 0)
    yearly = float(subscription.get("price_yearly") or 0)

    with st.container(key="plan_summary"):

        st.markdown(
            "<p class='ls-plan-label'>Your selected plan</p>"
            f"<p class='ls-plan-name'>{safe(subscription.get('plan_name'))}</p>",
            unsafe_allow_html=True,
        )

        billing_cycle = st.radio(
            "Billing cycle",
            ["Monthly", "Yearly"],
            index=0 if subscription.get("billing_cycle") == "Monthly" else 1,
            horizontal=True,
            key="application_billing_cycle",
        )

        subscription["billing_cycle"] = billing_cycle

        if billing_cycle == "Yearly":
            price, period = yearly, "year"
        else:
            price, period = monthly, "month"

        st.markdown(
            f"<p class='ls-plan-price'>{peso(price)}<small> / {period}</small></p>",
            unsafe_allow_html=True,
        )

        # Show how much a yearly plan saves compared with 12 monthly payments
        savings = monthly * 12 - yearly

        if billing_cycle == "Yearly" and yearly > 0 and savings > 0:
            st.markdown(
                f"<p class='ls-plan-savings'>You save {peso(savings)} "
                "compared with paying monthly.</p>",
                unsafe_allow_html=True,
            )

        st.markdown(limits_html(subscription), unsafe_allow_html=True)

    note(
        "Your subscription will be activated once the LungSight team "
        "approves this application."
    )

    if nav_buttons("subscription", 1):
        go_to_step(3)


# ============================================================
# STEP 4 - HOSPITAL ADMINISTRATOR
# ============================================================

def render_hospital_administrator():

    step_header(
        "Hospital administrator",
        "The person who will manage the LungSight account for the hospital.",
        required=True,
    )

    # error messages show up here, above the form, so they are easy to see
    errors = st.container()

    data = st.session_state.client_application["administrator"]

    with st.form("hospital_administrator_form"):

        first_name, middle_name, last_name = name_fields(data)

        email_col, contact_col = st.columns(2)

        email = email_col.text_input(
            "Administrator email *",
            value=data.get("email", ""),
            placeholder="admin@hospital.org",
        )

        contact_number = contact_col.text_input(
            "Contact number *",
            value=data.get("contact_number", ""),
            placeholder="+63 9XX XXX XXXX",
        )

        st.caption(
            "This email will be used to create the hospital administrator account."
        )

        back, go_next = form_nav_buttons()

    if back:
        go_to_step(2)

    if not go_next:
        return

    missing = find_missing({
        "First name": first_name,
        "Last name": last_name,
        "Administrator email": email,
        "Contact number": contact_number,
    })

    if missing:
        errors.error("Please complete: " + ", ".join(missing) + ".")
        return

    email = email.strip().lower()

    if not is_valid_email(email):
        errors.error("Please enter a valid email address.")
        return

    try:
        email_exists = auth_email_exists(email)
    except Exception as e:
        errors.error(f"Unable to verify the administrator email: {e}")
        return

    if email_exists:
        errors.error("This administrator email already exists in the system.")
        return

    st.session_state.client_application["administrator"] = {
        "first_name": first_name.strip(),
        "middle_name": middle_name.strip(),
        "last_name": last_name.strip(),
        "email": email,
        "contact_number": contact_number.strip(),
    }

    go_to_step(4)


# ============================================================
# STEP 5 - AGREEMENT
# ============================================================

def render_agreement():

    step_header(
        "Service agreement",
        "Please read and acknowledge the LungSight terms of service.",
    )

    # A fixed-height box keeps the step short; the text scrolls inside it
    with st.container(height=240, border=True):
        st.markdown(AGREEMENT_TEXT)

    agreed = st.checkbox(
        "I have read and agree to the LungSight Service Agreement.",
        value=st.session_state.client_application["agreement"].get("agreed", False),
    )

    errors = st.container()

    if nav_buttons("agreement", 3):

        if not agreed:
            errors.error("You must agree to the service agreement before continuing.")
            return

        st.session_state.client_application["agreement"] = {"agreed": True}

        go_to_step(5)


# ============================================================
# STEP 6 - REVIEW & SUBMIT
# ============================================================

def show_review_section(key, title, rows, edit_step):
    """One box in the review list, with an Edit button that jumps to that step."""
    with st.container(key=f"section_{key}"):

        title_col, edit_col = st.columns([5, 1], vertical_alignment="center")

        title_col.markdown(
            f"<p class='ls-review-title'>{title}</p>",
            unsafe_allow_html=True,
        )

        if edit_col.button("Edit", key=f"edit_{key}", width="stretch"):
            go_to_step(edit_step)

        st.markdown(rows_html(rows), unsafe_allow_html=True)


def render_review_submit():

    step_header(
        "Review application",
        "Check the details below. Use Edit to change anything before payment.",
    )

    application = st.session_state.client_application

    hospital = application["hospital"]
    representative = application["representative"]
    subscription = application["subscription"]
    administrator = application["administrator"]
    agreed = application["agreement"].get("agreed")

    # Scrolls inside a fixed-height box so the buttons stay visible
    with st.container(height=360, border=False):

        hospital_rows = [
            ("Hospital name", hospital.get("hospital_name")),
            ("Type", hospital.get("hospital_type")),
            ("Address", hospital.get("address")),
            ("Contact number", hospital.get("contact_number")),
            ("Email", hospital.get("hospital_email")),
        ]

        # the website is optional, so only list it when it was filled in
        if hospital.get("website"):
            hospital_rows.append(("Website", hospital.get("website")))

        show_review_section("hospital", "Hospital information", hospital_rows, edit_step=0)

        show_review_section("representative", "Authorized representative", [
            ("Name", full_name(representative)),
            ("Position", representative.get("position")),
            ("Contact number", representative.get("contact_number")),
            ("Email", representative.get("email")),
        ], edit_step=1)

        show_review_section("plan", "Subscription", [
            ("Plan", subscription.get("plan_name")),
            ("Billing cycle", subscription.get("billing_cycle", "Monthly")),
            ("Amount due", peso(get_amount(subscription))),
        ], edit_step=2)

        show_review_section("administrator", "Hospital administrator", [
            ("Name", full_name(administrator)),
            ("Email", administrator.get("email")),
            ("Contact number", administrator.get("contact_number")),
        ], edit_step=3)

        show_review_section("agreement", "Service agreement", [
            ("Status", "Accepted" if agreed else "Not accepted"),
        ], edit_step=4)

    if nav_buttons("review", 4, "Continue to payment"):
        go_to_step(6)


# ============================================================
# STEP 7 - PAYMENT
# ============================================================

def save_application():
    """Save the application as an unpaid draft. Returns its id, or None."""
    application = st.session_state.client_application

    hospital = application["hospital"]
    representative = application["representative"]
    subscription = application["subscription"]
    administrator = application["administrator"]
    agreement = application["agreement"]

    result = create_hospital_application(
        hospital_name=hospital.get("hospital_name"),
        hospital_type=hospital.get("hospital_type"),
        hospital_address=hospital.get("address"),
        hospital_contact_number=hospital.get("contact_number"),
        hospital_email=hospital.get("hospital_email"),
        hospital_website=hospital.get("website"),
        applicant_first_name=representative.get("first_name"),
        applicant_middle_name=representative.get("middle_name"),
        applicant_last_name=representative.get("last_name"),
        applicant_email=representative.get("email"),
        applicant_contact_number=representative.get("contact_number"),
        applicant_position=representative.get("position"),
        selected_plan_id=subscription.get("plan_id"),
        billing_cycle=subscription.get("billing_cycle", "Monthly"),
        admin_first_name=administrator.get("first_name"),
        admin_middle_name=administrator.get("middle_name"),
        admin_last_name=administrator.get("last_name"),
        admin_email=administrator.get("email"),
        admin_contact_number=administrator.get("contact_number"),
        agreement_accepted=agreement.get("agreed", False),
        application_status="Draft",
        payment_status="unpaid",
    )

    if not result.get("success"):
        st.error(result.get("message", "Failed to create application."))
        return None

    return result["application_id"]


def start_checkout():
    """Create the application (once) and then the PayMongo checkout session."""
    from backend.payments import create_checkout_session

    application_id = st.session_state.get("application_id")

    if not application_id:

        with st.spinner("Preparing your application..."):
            application_id = save_application()

        if not application_id:
            return

        st.session_state.application_id = application_id

    with st.spinner("Creating checkout session..."):
        result = create_checkout_session(application_id)

    if not result.get("success"):
        st.error(result.get("message", "Failed to create checkout session."))
        return

    st.session_state.checkout_url = result["checkout_url"]

    st.rerun()


def show_checkout(application_id, checkout_url):
    from backend.payments import get_payment_status

    note(
        "Checkout is ready. Complete your payment in the new tab, then come "
        "back here and refresh the status. Your application is submitted once "
        "PayMongo confirms the payment.",
        kind="success",
    )

    link_col, refresh_col = st.columns(2)

    link_col.link_button(
        "Open PayMongo checkout", checkout_url, type="primary", width="stretch"
    )

    if refresh_col.button(
        "Refresh status", key="refresh_payment_status", width="stretch"
    ):
        status = get_payment_status(application_id)

        if status.get("paid"):
            st.session_state.payment_success = True
            st.rerun()
        else:
            st.warning(
                f"Payment status: {status.get('status')}. "
                "Please wait a moment and try again."
            )


def render_payment_step():

    step_header(
        "Payment",
        "Pay securely through PayMongo to submit your application.",
    )

    application = st.session_state.client_application
    subscription = application["subscription"]

    amount = get_amount(subscription)
    application_id = st.session_state.get("application_id")
    checkout_url = st.session_state.get("checkout_url")

    with st.container(key="payment_summary"):
        st.markdown(
            rows_html([
                ("Hospital", application["hospital"].get("hospital_name")),
                ("Plan", subscription.get("plan_name")),
                ("Billing cycle", subscription.get("billing_cycle", "Monthly")),
            ])
            + f"<div class='ls-total'><span>Amount due</span><b>{peso(amount)}</b></div>",
            unsafe_allow_html=True,
        )

    if checkout_url:
        show_checkout(application_id, checkout_url)
        return

    pay_label = f"Pay {peso(amount)} with PayMongo"

    # Once a draft application exists there is no going back (no duplicates)
    if application_id:
        pay_clicked = st.button(
            pay_label, key="start_checkout", type="primary", width="stretch"
        )
    else:
        pay_clicked = nav_buttons("payment", 5, pay_label)

    if pay_clicked:
        start_checkout()


# ============================================================
# AFTER PAYMENT
# ============================================================

def render_payment_success():

    st.success("Application submitted — payment received.")

    st.markdown(
        """
**What happens next?**

1. Your application is now in the review queue.
2. The LungSight team will verify your hospital details.
3. Once approved, an invitation will be sent to the
   hospital administrator's email address.
4. The administrator clicks the link, sets a password,
   and can start using LungSight.
"""
    )

    if st.button("Close", key="success_close", width="stretch"):
        clear_application()
        st.rerun()


def render_application_submitted():

    st.success("Application submitted successfully.")

    st.markdown(
        """
**What happens next?**

Your hospital application will be reviewed by the LungSight
system administrator. Once approved:

1. Your hospital record will be created.
2. The selected subscription will be assigned.
3. The hospital administrator account will be created.
4. Login credentials will be sent to the administrator's
   registered email address.
"""
    )

    if st.button("Close", key="submitted_close", width="stretch"):
        clear_application()
        st.rerun()


# ============================================================
# THE DIALOG
# ============================================================

# Step number -> function that draws it
STEP_RENDERERS = [
    render_hospital_information,
    render_authorized_representative,
    render_subscription_confirmation,
    render_hospital_administrator,
    render_agreement,
    render_review_submit,
    render_payment_step,
]


@st.dialog("LungSight Hospital Application", width="medium")
def application_dialog(plan):

    initialize_application(plan)

    with st.container(key="application"):

        if st.session_state.get("payment_success", False):
            render_payment_success()
            return

        if st.session_state.get("application_submitted", False):
            render_application_submitted()
            return

        render_progress()

        STEP_RENDERERS[st.session_state.client_application_step]()


def show_client_application(plan):
    """Call this from the login page. It loads the styles, then opens the dialog."""
    load_application_css()
    application_dialog(plan)