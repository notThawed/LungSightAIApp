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


# ============================================================
# CSS
# ============================================================

# streamlit_app/pages/hospital_administrator/setup_wizard.py
#   parents[0] -> hospital_administrator
#   parents[1] -> pages
#   parents[2] -> streamlit_app
#   parents[3] -> LungSightApp (project root)
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
# (short name for the tracker, full title + caption for the heading)
# ============================================================

SETUP_STEPS = [
    ("Hospital", "Hospital Profile", "Review your hospital's information and upload your hospital logo."),
    ("Administrator", "Your Administrator Account", "Review your administrator information and upload your profile picture."),
    ("Subscription", "Your Subscription", "Here's the LungSight plan your hospital is subscribed to."),
    ("Review", "Review & Confirm", "Review your setup information before activating your LungSight hospital account."),
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
    return str(value).strip() if value else "—"


def peso(amount):
    return f"₱{float(amount or 0):,.2f}"


def limit_text(value):
    if value is None:
        return "Unlimited"
    return f"{value:,}"


def full_name_of(person):
    parts = [person.get("first_name"), person.get("middle_name"), person.get("last_name")]
    return " ".join(part for part in parts if part) or person.get("name") or "—"


def rows_html(rows):
    items = "".join(
        f"<div class='ls-row'><span>{label}</span><b>{safe(value)}</b></div>"
        for label, value in rows
    )
    return f"<div class='ls-rows'>{items}</div>"


def note(text):
    st.markdown(f"<div class='ls-note'>{text}</div>", unsafe_allow_html=True)


def step_header(title, caption):
    st.markdown(
        "<div class='ls-step-header'>"
        f"<p class='ls-step-title'>{title}</p>"
        f"<p class='ls-step-caption'>{caption}</p>"
        "</div>",
        unsafe_allow_html=True,
    )


def upload_card(current_image_url, label, caption):
    """A small preview + caption shown above the file_uploader widget."""
    if not current_image_url:
        return
    col_img, col_text = st.columns([1, 4], vertical_alignment="center")
    with col_img:
        st.image(current_image_url, width=72)
    with col_text:
        st.markdown(
            f"<p class='ls-upload-label'>{label}</p>"
            f"<p class='ls-upload-caption'>{caption}</p>",
            unsafe_allow_html=True,
        )


def go_to_step(step):
    st.session_state.setup_step = step
    st.rerun()


def nav_buttons(key, back_step=None, next_label="Continue", back_label="Back"):
    """Returns (back_clicked, next_clicked). If back_step is given, Back navigates directly."""
    if back_step is None:
        next_clicked = st.button(next_label, type="primary", width="stretch", key=f"{key}_next")
        return False, next_clicked

    back_col, next_col = st.columns(2)
    back_clicked = back_col.button(back_label, width="stretch", key=f"{key}_back")
    next_clicked = next_col.button(next_label, type="primary", width="stretch", key=f"{key}_next")

    if back_clicked:
        go_to_step(back_step)

    return back_clicked, next_clicked


def back_to_login():
    """Sign the user out and send them back to the login screen."""

    # If you have a dedicated sign-out function (e.g. backend.auth.sign_out),
    # call it here to properly invalidate the Supabase session:
    #
    # from backend.auth import sign_out
    # sign_out()

    for key in (
        "user",
        "logged_in",
        "setup_step",
        "setup_completed",
        "setup_final_confirmation",
        "subscription_context",
        "grace_info",
    ):
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
        up_next = "Last step"

    steps_html = ""
    for number, (short_name, _, _) in enumerate(SETUP_STEPS):
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
# STEP 1 — HOSPITAL PROFILE
# ============================================================

def render_hospital_profile(hospital):

    step_header(*SETUP_STEPS[0][1:])

    current_logo_url = hospital.get("hospital_logo_url")

    upload_card(current_logo_url, "Current hospital logo", "Upload a new image below to replace it.")

    hospital_logo = st.file_uploader(
        "Hospital logo",
        type=["png", "jpg", "jpeg", "webp"],
        help="Maximum file size: 5 MB.",
        key="setup_hospital_logo",
    )

    if hospital_logo:
        col_img, col_text = st.columns([1, 4], vertical_alignment="center")
        with col_img:
            st.image(hospital_logo, width=72)
        with col_text:
            st.caption("New hospital logo — saved when you continue.")

    st.divider()

    hospital_name = st.text_input(
        "Hospital name *",
        value=hospital.get("hospital_name", ""),
        key="setup_hospital_name",
    )

    type_col, contact_col = st.columns(2)

    current_type = hospital.get("hospital_type")
    if current_type not in HOSPITAL_TYPES:
        current_type = HOSPITAL_TYPES[0]

    hospital_type = type_col.selectbox(
        "Hospital type *",
        HOSPITAL_TYPES,
        index=HOSPITAL_TYPES.index(current_type),
        key="setup_hospital_type",
    )

    contact_number = contact_col.text_input(
        "Contact number",
        value=hospital.get("contact_number", "") or "",
        key="setup_hospital_contact",
    )

    address = st.text_area(
        "Complete address *",
        value=hospital.get("address", ""),
        key="setup_hospital_address",
        height=80,
    )

    email_col, website_col = st.columns(2)

    email = email_col.text_input(
        "Hospital email",
        value=hospital.get("email", "") or "",
        key="setup_hospital_email",
    )

    website = website_col.text_input(
        "Hospital website",
        value=hospital.get("website", "") or "",
        key="setup_hospital_website",
    )

    st.divider()

    _, next_clicked = nav_buttons("hospital", next_label="Save & Continue")

    if not next_clicked:
        return

    if not hospital_name.strip():
        st.error("Hospital name is required.")
        return

    if not address.strip():
        st.error("Hospital address is required.")
        return

    hospital_id = hospital.get("hospital_id")
    if not hospital_id:
        st.error("Hospital ID could not be found.")
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
        st.error("Hospital information was saved, but the updated hospital information could not be loaded.")
        return

    go_to_step(1)


# ============================================================
# STEP 2 — ADMINISTRATOR ACCOUNT
# ============================================================

def render_administrator_profile():

    user = refresh_current_user()

    step_header(*SETUP_STEPS[1][1:])

    if not user:
        st.error("Administrator information could not be found.")
        return

    user_id = user.get("user_id")
    if not user_id:
        st.error("Your user ID could not be found.")
        return

    current_profile_picture = (
        user.get("profile_picture_url")
        or user.get("profile_picture")
        or user.get("avatar_url")
    )

    upload_card(current_profile_picture, "Current profile picture", "Upload a new image below to replace it.")

    profile_picture = st.file_uploader(
        "Profile picture",
        type=["png", "jpg", "jpeg", "webp"],
        help="Maximum file size: 5 MB.",
        key="setup_profile_picture",
    )

    if profile_picture:
        col_img, col_text = st.columns([1, 4], vertical_alignment="center")
        with col_img:
            st.image(profile_picture, width=72)
        with col_text:
            st.caption("New profile picture — saved when you continue.")

    st.divider()

    st.markdown(rows_html([
        ("Name", full_name_of(user)),
        ("Email", user.get("email")),
        ("Contact number", user.get("contact_number")),
    ]), unsafe_allow_html=True)

    st.caption(
        "Your account information is managed by the LungSight system. "
        "Contact your system administrator if any details are incorrect."
    )

    st.divider()

    back_clicked, next_clicked = nav_buttons("administrator", back_step=0, next_label="Continue")

    if not next_clicked:
        return

    if profile_picture:
        upload_result = upload_profile_picture(
            user_id=user_id,
            file_bytes=profile_picture.getvalue(),
            file_name=profile_picture.name,
        )

        if not upload_result["success"]:
            st.error(f"Profile picture could not be uploaded: {upload_result['message']}")
            return

        profile_url = upload_result.get("url")
        if not profile_url:
            st.error("Profile picture was uploaded, but Supabase did not return a public URL.")
            return

        profile_result = update_profile_picture_url(user_id=user_id, profile_picture_url=profile_url)
        if not profile_result["success"]:
            st.error(
                "The profile picture was uploaded, but its database URL "
                f"could not be saved: {profile_result['message']}"
            )
            return

        if refresh_current_user():
            st.session_state.user["profile_picture_url"] = profile_url

    go_to_step(2)


# ============================================================
# STEP 3 — SUBSCRIPTION SUMMARY
# ============================================================

def render_subscription_summary(hospital):

    step_header(*SETUP_STEPS[2][1:])

    subscription = get_hospital_subscription_details(hospital.get("hospital_id"))

    if not subscription:
        st.warning("No subscription information could be found for your hospital. Please contact support.")
        st.divider()
        nav_buttons("subscription_missing", back_step=1, next_label="Back to Administrator")
        return

    billing_cycle = subscription.get("billing_cycle", "Monthly")

    if billing_cycle == "Yearly":
        amount, period = float(subscription.get("price_yearly") or 0), "year"
    else:
        amount, period = float(subscription.get("price_monthly") or 0), "month"

    with st.container(key="setup_plan"):

        st.markdown(
            "<p class='ls-plan-label'>Your subscription plan</p>"
            f"<p class='ls-plan-name'>{safe(subscription.get('plan_name'))}</p>",
            unsafe_allow_html=True,
        )

        description = subscription.get("description")
        if description:
            st.markdown(f"<p class='ls-plan-desc'>{safe(description)}</p>", unsafe_allow_html=True)

        st.markdown(
            f"<p class='ls-plan-price'>{peso(amount)}<small> / {period}</small></p>",
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
        st.markdown(f"<div class='ls-limits'>{limits_html}</div>", unsafe_allow_html=True)

        st.markdown(
            "<div class='ls-plan-dates'>"
            f"<span>Start: <b>{safe(subscription.get('start_date'))}</b></span>"
            f"<span>End: <b>{safe(subscription.get('end_date'))}</b></span>"
            "</div>",
            unsafe_allow_html=True,
        )

    note("Your subscription is already active — this step is here for you to confirm the details before continuing.")

    back_clicked, next_clicked = nav_buttons("subscription", back_step=1, next_label="Continue")

    if next_clicked:
        go_to_step(3)


# ============================================================
# STEP 4 — REVIEW & CONFIRM
# ============================================================

def review_section(key, icon_title, rows, avatar_url=None):
    with st.container(key=f"setup_section_{key}"):
        if avatar_url:
            col_img, col_title = st.columns([1, 5], vertical_alignment="center")
            with col_img:
                st.markdown("<div class='ls-review-avatar'>", unsafe_allow_html=True)
                st.image(avatar_url, width=56)
                st.markdown("</div>", unsafe_allow_html=True)
            with col_title:
                st.markdown(f"<p class='ls-review-title'>{icon_title}</p>", unsafe_allow_html=True)
        else:
            st.markdown(f"<p class='ls-review-title'>{icon_title}</p>", unsafe_allow_html=True)

        st.markdown(rows_html(rows), unsafe_allow_html=True)


def render_review(hospital):

    step_header(*SETUP_STEPS[3][1:])

    hospital = refresh_current_hospital() or hospital
    user = refresh_current_user() or get_current_user() or {}

    review_section(
        "hospital",
        "Hospital profile",
        [
            ("Hospital name", hospital.get("hospital_name")),
            ("Hospital type", hospital.get("hospital_type")),
            ("Address", hospital.get("address")),
            ("Contact number", hospital.get("contact_number")),
            ("Email", hospital.get("email")),
            ("Website", hospital.get("website")),
        ],
        avatar_url=hospital.get("hospital_logo_url"),
    )

    profile_picture_url = (
        user.get("profile_picture_url")
        or user.get("profile_picture")
        or user.get("avatar_url")
    )

    review_section(
        "administrator",
        "Your administrator account",
        [
            ("Name", full_name_of(user)),
            ("Email", user.get("email")),
            ("Contact number", user.get("contact_number")),
        ],
        avatar_url=profile_picture_url,
    )

    subscription = get_hospital_subscription_details(hospital.get("hospital_id"))

    if subscription:
        billing_cycle = subscription.get("billing_cycle")
        amount = float(
            (subscription.get("price_yearly") if billing_cycle == "Yearly" else subscription.get("price_monthly"))
            or 0
        )
        review_section("subscription", "Your subscription", [
            ("Plan", subscription.get("plan_name")),
            ("Billing cycle", billing_cycle),
            ("Price", peso(amount)),
        ])
    else:
        st.warning("Subscription information not available.")

    st.divider()

    confirmation = st.checkbox(
        "I have reviewed the information above and confirm that it is correct.",
        key="setup_final_confirmation",
    )

    st.divider()

    back_clicked, complete_clicked = nav_buttons("review", back_step=2, next_label="Complete Setup")

    if not complete_clicked:
        return

    if not confirmation:
        st.error("Please confirm that the information is correct before completing setup.")
        return

    hospital_id = hospital.get("hospital_id")
    if not hospital_id:
        st.error("Hospital ID could not be found.")
        return

    result = complete_hospital_setup(hospital_id)
    if not result["success"]:
        st.error(result["message"])
        return

    st.session_state.setup_completed = True
    st.session_state.pop("setup_step", None)
    st.session_state.pop("setup_final_confirmation", None)

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

    with st.container(key="setup_wizard"):

        if st.button(
            "Back to Login",
            key="setup_back_to_login",
            icon=":material/logout:",
        ):
            back_to_login()

        st.title("Welcome to LungSight")
        st.caption("Let's complete your hospital setup before you start using the LungSight system.")

        st.divider()

        render_progress()

        current_step = st.session_state.setup_step
        STEP_RENDERERS[current_step](hospital)