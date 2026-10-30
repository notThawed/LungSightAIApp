from datetime import date, datetime

import streamlit as st

from backend.fetches import (
    get_all_users,
    get_all_roles,
    get_user,
    get_user_counts,
    generate_employee_id,
    get_all_hospitals,
)

from backend.crud import (
    create_user,
    update_user,
    delete_user,
    reactivate_user,
)

from streamlit_app.components.ui import (
    page_header,
    metric_card,
    empty_state,
    note,
    full_name,
    format_date,
    table_header,
    table_row,
    close_button,
    confirm_buttons,
    remember,
    show_flash_message,
    initials,
    safe,
    pill,
)

from shared.assets import load_css

from backend.backend_utils.subscription_usage import (
    can_create_user,
)


# Column widths: employee id, user (avatar+name+email), role, hospital, status, last login, actions
WIDTHS = [1.3, 2.7, 1.7, 2.0, 1.1, 1.6, 1.1]
HEADERS = ["Employee ID", "User", "Role", "Hospital", "Status", "Last Login", "Actions"]

SEX_OPTIONS = ["Male", "Female", "Prefer not to say"]

# Inline SVGs for consistent, cross-platform icon rendering (avoids font ligature issues)
ICON_SVGS = {
    "badge": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M16 10h2"/>
        <path d="M16 14h2"/>
        <path d="M6.17 15a3 3 0 0 1 5.66 0"/>
        <circle cx="9" cy="11" r="2"/>
        <rect x="2" y="5" width="20" height="14" rx="2"/>
    </svg>""",
    "history": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
        <path d="M3 3v5h5"/>
        <path d="M12 7v5l4 2"/>
    </svg>""",
    "person": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/>
        <circle cx="12" cy="7" r="4"/>
    </svg>""",
    "call": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
    </svg>""",
    "lock": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect width="18" height="11" x="3" y="11" rx="2" ry="2"/>
        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
    </svg>""",
    "hospital": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 21h18"/>
        <path d="M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16"/>
        <path d="M9 21v-4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v4"/>
        <path d="M10 9h4"/>
        <path d="M12 7v4"/>
    </svg>""",
}


# ============================================================
# SMALL HELPERS
# ============================================================

def validate_birthdate(birthdate):
    """Returns (is_valid, error_message)."""
    if birthdate is None:
        return False, "Birthdate is required."

    today = date.today()
    latest_birthdate = _latest_adult_birthdate(today)

    if birthdate > latest_birthdate:
        return False, "User must be at least 18 years old."

    if birthdate < date(1900, 1, 1):
        return False, "Please enter a valid birthdate."

    age = calculate_age(birthdate)
    if age < 18:
        return False, f"User must be at least 18 years old. Current age: {age}."

    if age > 120:
        return False, "Please enter a valid birthdate. The calculated age is over 120 years."

    return True, ""


def _latest_adult_birthdate(today=None):
    """Latest birthdate that meets the 18-year minimum age."""
    today = today or date.today()
    try:
        return today.replace(year=today.year - 18)
    except ValueError:  # February 29 in a leap year
        return today.replace(year=today.year - 18, day=28)


def calculate_age(birthdate):
    """Accepts a date, datetime or 'YYYY-MM-DD' text. Returns None if unreadable."""
    if not birthdate:
        return None

    try:
        if isinstance(birthdate, datetime):
            birthdate = birthdate.date()
        elif isinstance(birthdate, str):
            birthdate = date.fromisoformat(birthdate[:10])

        today = date.today()
        age = today.year - birthdate.year

        if (today.month, today.day) < (birthdate.month, birthdate.day):
            age -= 1

        return age

    except (ValueError, TypeError, AttributeError):
        return None


def user_name(user):
    return full_name(user.get("user_fname"), user.get("user_mname"), user.get("user_lname"))


def role_name_of(user):
    return (user.get("roles") or {}).get("role_name") or "N/A"


def hospital_name_of(user):
    hospital = user.get("hospitals")
    if hospital:
        return hospital.get("hospital_name") or "—"

    is_superadmin = role_name_of(user).replace(" ", "").lower() == "superadmin"
    return "Global (All Hospitals)" if is_superadmin else "—"


def get_current_user_info():
    """(current_user, is_hospital_admin, hospital_id, hospital_name)"""
    current_user = st.session_state.get("user") or {}
    is_hospital_admin = (current_user.get("role") or "").strip().lower() == "hospital admin"
    hospital_name = current_user.get("hospital_name") or current_user.get("hospital")
    return current_user, is_hospital_admin, current_user.get("hospital_id"), hospital_name


# ============================================================
# CUSTOM TABLE CELL RENDERERS
# ============================================================

def user_code_cell(column, employee_id):
    code = safe(employee_id or "—")
    column.markdown(
        f"<div class='sa-code-cell'><span class='sa-emp-badge'>#{code}</span></div>",
        unsafe_allow_html=True,
    )


def user_profile_cell(column, user):
    name = user_name(user)
    initial_text = initials(name)
    sex = (user.get("user_sex") or "").lower()
    email = safe(user.get("email") or "—")

    avatar_class = "sa-user-avatar"
    if sex == "female":
        avatar_class += " sa-user-avatar-female"
    elif sex == "male":
        avatar_class += " sa-user-avatar-male"

    column.markdown(
        f"<div class='sa-user-cell'>"
        f"  <div class='{avatar_class}'>{initial_text}</div>"
        f"  <div class='sa-user-info'>"
        f"    <span class='sa-user-name'>{safe(name)}</span>"
        f"    <span class='sa-user-email'>"
        f"      <svg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><rect x='2' y='4' width='20' height='16' rx='2'/><path d='m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7'/></svg>"
        f"      {email}"
        f"    </span>"
        f"  </div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def user_role_cell(column, role_name):
    norm_role = (role_name or "").strip().lower()
    if "superadmin" in norm_role:
        badge_cls = "sa-role-superadmin"
    elif "hospital admin" in norm_role:
        badge_cls = "sa-role-hospadmin"
    elif "radiologist" in norm_role:
        badge_cls = "sa-role-radiologist"
    elif "radiologic technologist" in norm_role or "rad tech" in norm_role:
        badge_cls = "sa-role-radtech"
    elif "physician" in norm_role or "doctor" in norm_role:
        badge_cls = "sa-role-physician"
    else:
        badge_cls = "sa-role-staff"

    column.markdown(
        f"<span class='sa-role-badge {badge_cls}'>{safe(role_name)}</span>",
        unsafe_allow_html=True,
    )


def user_hospital_cell(column, hospital_name):
    hosp = safe(hospital_name or "—")
    column.markdown(
        f"<div class='sa-hospital-cell'>"
        f"  <svg width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M3 21h18'/><path d='M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16'/><path d='M9 21v-4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v4'/><path d='M10 9h4'/><path d='M12 7v4'/></svg>"
        f"  <span>{hosp}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


def user_status_cell(column, is_active):
    if is_active:
        column.markdown(
            f"<span class='sa-status-pill sa-status-pill-active'>"
            f"  <span class='sa-status-dot sa-status-dot-active'></span>"
            f"  Active"
            f"</span>",
            unsafe_allow_html=True,
        )
    else:
        column.markdown(
            f"<span class='sa-status-pill sa-status-pill-inactive'>"
            f"  <span class='sa-status-dot sa-status-dot-inactive'></span>"
            f"  Inactive"
            f"</span>",
            unsafe_allow_html=True,
        )


def user_last_login_cell(column, last_login):
    if not last_login:
        column.markdown("<div class='sa-login-cell'><span class='sa-login-never'>Never logged in</span></div>", unsafe_allow_html=True)
        return

    formatted_date = format_date(last_login)
    try:
        if isinstance(last_login, str):
            dt = datetime.fromisoformat(last_login.replace("Z", "+00:00"))
        elif isinstance(last_login, datetime):
            dt = last_login
        else:
            dt = None
        time_str = dt.strftime("%I:%M %p").lstrip("0") if dt else ""
    except Exception:
        time_str = ""

    column.markdown(
        f"<div class='sa-login-cell'>"
        f"  <span class='sa-login-date'>{formatted_date}</span>"
        f"  <span class='sa-login-time'>{time_str}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# ADD / EDIT USER FORM
# ============================================================

def render_user_form(user=None):
    """user=None adds a new user; otherwise edits that user."""
    is_edit = user is not None
    form_prefix = "edit_" if is_edit else "new_"

    current_user, is_hospital_admin, editor_hospital_id, editor_hospital_name = get_current_user_info()

    # ---- Assignable roles ----
    blocked_roles = {"superadmin"}
    if is_hospital_admin:
        blocked_roles.add("hospital admin")

    role_options = {
        role["role_name"]: role["role_id"]
        for role in (get_all_roles() or [])
        if role
        and role.get("role_name")
        and role["role_name"].strip().lower() not in blocked_roles
    }

    if not role_options:
        st.error("No assignable roles found.")
        return

    hospital_options = {
        hospital["hospital_name"]: hospital["hospital_id"]
        for hospital in (get_all_hospitals() or [])
        if hospital
    }

    # ---- Starting values ----
    user = user or {}

    role_names = list(role_options.keys())
    role_by_id = {role_id: name for name, role_id in role_options.items()}
    role_index = role_names.index(role_by_id[user["role_id"]]) if user.get("role_id") in role_by_id else 0

    hospital_names = list(hospital_options.keys())
    hospital_by_id = {hospital_id: name for name, hospital_id in hospital_options.items()}
    hospital_index = (
        hospital_names.index(hospital_by_id[user["hospital_id"]])
        if user.get("hospital_id") in hospital_by_id
        else 0
    )

    # DOB parsing
    try:
        existing_dob = date.fromisoformat(str(user.get("user_birthdate"))[:10])
        dob_day = existing_dob.day
        dob_month = existing_dob.month
        dob_year = existing_dob.year
    except (ValueError, TypeError):
        dob_day = 1
        dob_month = 1
        dob_year = 1990

    employee_id = user.get("employee_id") if is_edit else generate_employee_id()

    errors = st.container()

    # ---- Form structure ----
    with st.form(f"user_form_{form_prefix}", clear_on_submit=False):

        st.markdown(
            f"<div class='sa-form-section-title'>"
            f"{ICON_SVGS['lock']} <span>Account Credentials</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        id_col, email_col = st.columns([1, 2])
        id_col.text_input("Employee ID", value=employee_id or "", disabled=True, key=f"{form_prefix}employee_id")
        email = email_col.text_input(
            "Email address *", value=user.get("email") or "", placeholder="user@hospital.com", key=f"{form_prefix}email"
        )

        password = ""
        if is_edit:
            password = st.text_input(
                "New password",
                type="password",
                placeholder="Leave blank to keep the current password",
                key=f"{form_prefix}password",
            )

        st.markdown(
            f"<div class='sa-form-section-title' style='margin-top:1.25rem;'>"
            f"{ICON_SVGS['person']} <span>Personal Information</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        first_col, middle_col, last_col = st.columns(3)
        first_name = first_col.text_input("First name *", value=user.get("user_fname") or "", key=f"{form_prefix}first_name")
        middle_name = middle_col.text_input("Middle name", value=user.get("user_mname") or "", key=f"{form_prefix}middle_name")
        last_name = last_col.text_input("Last name *", value=user.get("user_lname") or "", key=f"{form_prefix}last_name")

        # Birthdate & Sex
        st.markdown(
            "<label style='font-size:0.85rem; font-weight:600; color:var(--sa-ink); display:block; margin-bottom:0.25rem;'>Birthdate *</label>",
            unsafe_allow_html=True,
        )

        birth_col1, birth_col2, birth_col3, sex_col = st.columns([1, 1.2, 1, 1.5])
        days = list(range(1, 32))
        months = list(range(1, 13))
        years = list(range(date.today().year, 1899, -1))

        selected_day = birth_col1.selectbox(
            "Day",
            days,
            index=days.index(dob_day) if dob_day in days else 0,
            key=f"{form_prefix}dob_day",
        )

        selected_month = birth_col2.selectbox(
            "Month",
            months,
            index=months.index(dob_month) if dob_month in months else 0,
            format_func=lambda m: date(2000, m, 1).strftime("%B"),
            key=f"{form_prefix}dob_month",
        )

        selected_year = birth_col3.selectbox(
            "Year",
            years,
            index=years.index(dob_year) if dob_year in years else years.index(1990),
            key=f"{form_prefix}dob_year",
        )

        current_sex = user.get("user_sex")
        sex = sex_col.selectbox(
            "Sex",
            SEX_OPTIONS,
            index=SEX_OPTIONS.index(current_sex) if current_sex in SEX_OPTIONS else 0,
            key=f"{form_prefix}sex",
        )

        try:
            birthdate = date(selected_year, selected_month, selected_day)
        except ValueError:
            errors.error("Invalid date selected.")
            birthdate = None

        contact_col, addr_col = st.columns([1, 1.5])
        contact_number = contact_col.text_input(
            "Contact number",
            value=user.get("user_contact_number") or "",
            placeholder="+63 912 345 6789",
            key=f"{form_prefix}contact",
        )
        address = addr_col.text_input(
            "Address",
            value=user.get("user_address") or "",
            placeholder="City / Province",
            key=f"{form_prefix}address",
        )

        st.markdown(
            f"<div class='sa-form-section-title' style='margin-top:1.25rem;'>"
            f"{ICON_SVGS['hospital']} <span>Role & Hospital Assignment</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        role_col, hospital_col = st.columns(2)
        selected_role = role_col.selectbox("Role *", role_names, index=role_index, key=f"{form_prefix}role")

        selected_hospital = None
        with hospital_col:
            if is_hospital_admin:
                st.text_input(
                    "Hospital",
                    value=editor_hospital_name or str(editor_hospital_id or "—"),
                    disabled=True,
                    key=f"{form_prefix}hospital_disabled",
                )
            elif hospital_names:
                selected_hospital = st.selectbox("Hospital *", hospital_names, index=hospital_index, key=f"{form_prefix}hospital")
            else:
                st.warning("No hospitals registered yet.")

        st.write("")
        cancel_col, save_col = st.columns(2)
        cancel = cancel_col.form_submit_button("Cancel", width="stretch")
        submitted = save_col.form_submit_button(
            "Save changes" if is_edit else "Create user", type="primary", width="stretch"
        )

    if cancel:
        st.rerun()

    if not submitted:
        return

    # ---- Validation ----
    if birthdate is None:
        return

    if not is_edit and not email.strip():
        errors.error("Email address is required.")
        return

    if not first_name.strip() or not last_name.strip():
        errors.error("First name and last name are required.")
        return

    is_valid, birthdate_error = validate_birthdate(birthdate)
    if not is_valid:
        errors.error(birthdate_error)
        return

    if is_hospital_admin:
        if editor_hospital_id is None:
            errors.error("Your account is not assigned to a hospital. Please contact your Superadmin.")
            return
        hospital_id = editor_hospital_id
    elif selected_hospital:
        hospital_id = hospital_options[selected_hospital]
    elif is_edit:
        hospital_id = None
    else:
        errors.error("Please select a hospital for this user.")
        return

    # ---- Save / Update ----
    if is_edit:
        with st.spinner("Saving changes..."):
            result = update_user(
                user_id=user["user_id"],
                email=email.strip(),
                password=password.strip(),
                first_name=first_name.strip(),
                middle_name=middle_name.strip(),
                last_name=last_name.strip(),
                birth_date=birthdate,
                role_id=role_options[selected_role],
                sex=sex,
                contact_number=contact_number.strip(),
                address=address.strip(),
                hospital_id=hospital_id,
            )
        done_message, fail_message = "User updated successfully.", "Failed to update user."

    else:
        subscription_check = can_create_user(hospital_id)
        if not subscription_check.get("allowed"):
            errors.error(
                subscription_check.get(
                    "message",
                    "User limit reached for this hospital subscription.",
                )
            )
            return

        with st.spinner("Creating user..."):
            result = create_user(
                email=email.strip(),
                first_name=first_name.strip(),
                middle_name=middle_name.strip(),
                last_name=last_name.strip(),
                birth_date=birthdate,
                employee_id=employee_id,
                role_id=role_options[selected_role],
                sex=sex,
                contact_number=contact_number.strip(),
                address=address.strip(),
                hospital_id=hospital_id,
            )
        done_message, fail_message = "User registered successfully.", "Failed to create user."

    if result.get("success"):
        remember(done_message)
        st.rerun()
    else:
        errors.error(result.get("message", fail_message))


@st.dialog("Register User", width="large")
def show_add_user_form():
    with st.container(key="sa_dialog"):
        render_user_form()


@st.dialog("Edit User Profile", width="large")
def show_edit_user_form(user_id):
    user = get_user(user_id)
    with st.container(key="sa_dialog"):
        if not user:
            st.error("User not found.")
            return
        render_user_form(user)


# ============================================================
# VIEW / DEACTIVATE / REACTIVATE DIALOGS
# ============================================================

@st.dialog("User Profile", width="large")
def show_view_user(user_id):
    user = get_user(user_id)
    with st.container(key="sa_dialog"):
        if not user:
            st.error("User not found.")
            return

        name = user_name(user)
        init = initials(name)
        emp_id = user.get("employee_id") or "Not assigned"
        role = role_name_of(user)
        hospital = hospital_name_of(user)
        is_active = user.get("is_active")
        status_text = "Active" if is_active else "Inactive"
        status_tone = "green" if is_active else "grey"

        sex = user.get("user_sex")
        sex_pill = ""
        if sex and sex.strip() and sex != "—":
            sex_tone = "blue" if sex.lower() == "male" else ("teal" if sex.lower() == "female" else "grey")
            sex_pill = pill(sex, sex_tone)

        age = calculate_age(user.get("user_birthdate"))
        dob = user.get("user_birthdate")
        age_str = ""
        if age is not None and dob:
            age_str = f"<span style='font-size:0.8rem; color:var(--sa-slate); font-weight:600;'>{age} yrs old • {format_date(dob)}</span>"
        elif dob:
            age_str = f"<span style='font-size:0.8rem; color:var(--sa-slate); font-weight:600;'>{format_date(dob)}</span>"

        avatar_class = "sa-dialog-avatar"
        if sex and sex.lower() == "female":
            avatar_class += " sa-dialog-avatar-female"

        hero_html = (
            f"<div class='sa-dialog-hero'>"
            f"<div class='{avatar_class}'>{init}</div>"
            f"<div class='sa-dialog-info'>"
            f"<div class='sa-dialog-name'>{safe(name)}</div>"
            f"<div class='sa-dialog-badges'>"
            f"<span class='sa-emp-badge'>#{safe(emp_id)}</span>"
            f"{pill(role, 'teal')}"
            f"{pill(status_text, status_tone)}"
            f"{sex_pill}"
            f"{age_str}"
            f"</div>"
            f"</div>"
            f"</div>"
        )
        st.markdown(hero_html, unsafe_allow_html=True)

        left_col, right_col = st.columns(2)

        with left_col:
            st.markdown(
                f"<div class='sa-view-card'>"
                f"<div class='sa-view-card-header'>"
                f"{ICON_SVGS['badge']} <span>Account & System Access</span>"
                f"</div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Employee ID</span><span class='sa-view-value'>{safe(emp_id)}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Email address</span><span class='sa-view-value'>{safe(user.get('email'))}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>System role</span><span class='sa-view-value'>{safe(role)}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Assigned hospital</span><span class='sa-view-value'>{safe(hospital)}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Account status</span><span class='sa-view-value'>{status_text}</span></div>"
                f"</div>"
                f"<div class='sa-view-card'>"
                f"<div class='sa-view-card-header'>"
                f"{ICON_SVGS['history']} <span>Activity & Timestamps</span>"
                f"</div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Last login</span><span class='sa-view-value'>{format_date(user.get('last_login'), with_time=True) if user.get('last_login') else 'Never logged in'}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Account created</span><span class='sa-view-value'>{format_date(user.get('created_at'), with_time=True)}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Last updated</span><span class='sa-view-value'>{format_date(user.get('updated_at'), with_time=True)}</span></div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with right_col:
            st.markdown(
                f"<div class='sa-view-card'>"
                f"<div class='sa-view-card-header'>"
                f"{ICON_SVGS['person']} <span>Personal Information</span>"
                f"</div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>First name</span><span class='sa-view-value'>{safe(user.get('user_fname'))}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Middle name</span><span class='sa-view-value'>{safe(user.get('user_mname'))}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Last name</span><span class='sa-view-value'>{safe(user.get('user_lname'))}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Sex</span><span class='sa-view-value'>{safe(sex or '—')}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Date of birth</span><span class='sa-view-value'>{format_date(dob)}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Calculated age</span><span class='sa-view-value'>{f'{age} years old' if age is not None else '—'}</span></div>"
                f"</div>"
                f"<div class='sa-view-card'>"
                f"<div class='sa-view-card-header'>"
                f"{ICON_SVGS['call']} <span>Contact Details</span>"
                f"</div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Contact number</span><span class='sa-view-value'>{safe(user.get('user_contact_number'))}</span></div>"
                f"<div class='sa-view-row'><span class='sa-view-label'>Residential address</span><span class='sa-view-value'>{safe(user.get('user_address'))}</span></div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        close_button(f"close_user_{user_id}")


@st.dialog("Deactivate User", width="small")
def show_delete_confirm(user_id, name):
    with st.container(key="sa_dialog"):
        st.markdown(f"<p class='sa-dialog-text'>Deactivate <b>{safe(name)}</b>?</p>", unsafe_allow_html=True)
        note(
            "This deactivates the user's account and prevents them from logging in. "
            "All historical medical examinations, reports, and audit logs will be safely preserved.",
            "amber",
        )
        if confirm_buttons(f"delete_user_{user_id}", "Deactivate user"):
            with st.spinner("Deactivating user..."):
                result = delete_user(user_id)
            if result.get("success"):
                remember("User deactivated successfully.")
                st.rerun()
            else:
                st.error(result.get("message", "Failed to deactivate user."))


@st.dialog("Reactivate User", width="small")
def show_reactivate_confirm(user_id, name):
    with st.container(key="sa_dialog"):
        st.markdown(f"<p class='sa-dialog-text'>Reactivate <b>{safe(name)}</b>?</p>", unsafe_allow_html=True)
        note(
            "This restores login and system access for this user.",
            "green",
        )
        if confirm_buttons(f"reactivate_user_{user_id}", "Reactivate user"):
            with st.spinner("Reactivating user..."):
                result = reactivate_user(user_id)
            if result.get("success"):
                remember("User reactivated successfully.")
                st.rerun()
            else:
                st.error(result.get("message", "Failed to reactivate user."))


# ============================================================
# FILTERS + PAGINATION + TABLE
# ============================================================

def show_filters(users, hospital_names, show_hospital_filter):
    """Search plus dropdown filters. Returns matching users."""
    with st.container(key="sa_user_filters"):
        if show_hospital_filter and hospital_names:
            search_col, role_col, status_col, hosp_col, reset_col = st.columns(
                [2.8, 1.4, 1.2, 1.8, 0.9],
                vertical_alignment="center",
            )
            hospital_filter = hosp_col.selectbox(
                "Hospital",
                ["All hospitals"] + hospital_names,
                label_visibility="collapsed",
                key="users_hospital",
            )
        else:
            search_col, role_col, status_col, reset_col = st.columns(
                [3.2, 1.5, 1.3, 1],
                vertical_alignment="center",
            )
            hospital_filter = "All hospitals"

        search = search_col.text_input(
            "Search",
            placeholder="Search by name, email, or employee ID...",
            label_visibility="collapsed",
            key="users_search",
        ).strip().lower()

        role_names = sorted({role_name_of(u) for u in users if role_name_of(u) and role_name_of(u) != "N/A"})
        role = role_col.selectbox(
            "Role",
            ["All roles"] + role_names,
            label_visibility="collapsed",
            key="users_role",
        )

        status = status_col.selectbox(
            "Status",
            ["All status", "Active", "Inactive"],
            label_visibility="collapsed",
            key="users_status",
        )

        def _reset_filters():
            st.session_state["users_page"] = 1
            st.session_state["users_search"] = ""
            st.session_state["users_role"] = "All roles"
            st.session_state["users_status"] = "All status"
            if "users_hospital" in st.session_state:
                st.session_state["users_hospital"] = "All hospitals"
            st.cache_data.clear()

        reset_col.button(
            "Reset",
            icon=":material/refresh:",
            width="stretch",
            key="users_refresh",
            on_click=_reset_filters,
            help="Reset filters and refresh list",
        )

    # Track filter changes to reset pagination to page 1
    curr_filter_key = (search, role, status, hospital_filter)
    prev_filter_key = (
        st.session_state.get("_prev_users_search"),
        st.session_state.get("_prev_users_role"),
        st.session_state.get("_prev_users_status"),
        st.session_state.get("_prev_users_hospital"),
    )
    if curr_filter_key != prev_filter_key:
        st.session_state["users_page"] = 1
        st.session_state["_prev_users_search"] = search
        st.session_state["_prev_users_role"] = role
        st.session_state["_prev_users_status"] = status
        st.session_state["_prev_users_hospital"] = hospital_filter

    matches = []
    for user in users:
        text = f"{user_name(user)} {user.get('email', '')} {user.get('employee_id', '')}".lower()
        if search and search not in text:
            continue
        if role != "All roles" and role_name_of(user) != role:
            continue
        if status != "All status":
            is_active_str = "Active" if user.get("is_active") else "Inactive"
            if is_active_str != status:
                continue
        if hospital_filter != "All hospitals" and hospital_name_of(user) != hospital_filter:
            continue
        matches.append(user)

    return matches


def render_table_pagination(current_page, total_pages, total_items, start_idx, end_idx):
    st.markdown("<div class='sa-pagination-bar'>", unsafe_allow_html=True)
    if total_pages > 1:
        col_prev, col_info, col_next = st.columns([1, 2.5, 1], vertical_alignment="center")

        with col_prev:
            if st.button(
                "Previous",
                icon=":material/chevron_left:",
                key="users_page_prev",
                disabled=(current_page <= 1),
                width="stretch",
            ):
                st.session_state["users_page"] = current_page - 1
                st.rerun()

        with col_info:
            st.markdown(
                f"<div class='sa-pagination-info'>"
                f"Showing <b>{start_idx + 1}–{end_idx}</b> of <b>{total_items}</b> • Page <b>{current_page}</b> of <b>{total_pages}</b>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with col_next:
            if st.button(
                "Next",
                icon=":material/chevron_right:",
                key="users_page_next",
                disabled=(current_page >= total_pages),
                width="stretch",
            ):
                st.session_state["users_page"] = current_page + 1
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_users_table(users, current_user=None):
    if not users:
        empty_state("No users found matching your search or filter criteria.")
        return

    PAGE_SIZE = 15
    total_items = len(users)
    total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)
    current_page = st.session_state.get("users_page", 1)
    if current_page > total_pages:
        current_page = total_pages
        st.session_state["users_page"] = current_page
    elif current_page < 1:
        current_page = 1
        st.session_state["users_page"] = current_page

    start_idx = (current_page - 1) * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, total_items)
    page_users = users[start_idx:end_idx]

    current_user_id = (current_user or {}).get("user_id")

    # Toolbar with user count
    st.markdown(
        f"<div class='sa-table-toolbar'>"
        f"<div class='sa-table-count-badge'>"
        f"Showing <b>{start_idx + 1}–{end_idx}</b> of <b>{total_items}</b> users"
        f"</div>"
        f"<span style='font-size:0.78rem; color:var(--sa-slate);'>Page {current_page} of {total_pages}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    with st.container(key="sa_table_users"):
        table_header(HEADERS, WIDTHS, "users")

        for user in page_users:
            user_id = user.get("user_id")
            name = user_name(user)
            is_active = user.get("is_active")
            is_self = (user_id == current_user_id)

            with table_row(f"users_{user_id}", WIDTHS) as cols:
                user_code_cell(cols[0], user.get("employee_id"))
                user_profile_cell(cols[1], user)
                user_role_cell(cols[2], role_name_of(user))
                user_hospital_cell(cols[3], hospital_name_of(user))
                user_status_cell(cols[4], is_active)
                user_last_login_cell(cols[5], user.get("last_login"))

                with cols[6]:
                    act_cols = st.columns(3, gap="small", vertical_alignment="center")

                    with act_cols[0]:
                        if st.button("", key=f"view_{user_id}", icon=":material/visibility:", help="View user details", width="stretch"):
                            show_view_user(user_id)

                    with act_cols[1]:
                        if st.button("", key=f"edit_{user_id}", icon=":material/edit:", help="Edit user profile", width="stretch"):
                            show_edit_user_form(user_id)

                    with act_cols[2]:
                        if is_active:
                            if is_self:
                                st.button("", key=f"delete_disabled_{user_id}", icon=":material/person_off:", help="You cannot deactivate your own account", disabled=True, width="stretch")
                            else:
                                if st.button("", key=f"delete_{user_id}", icon=":material/person_off:", help="Deactivate user", width="stretch"):
                                    show_delete_confirm(user_id, name)
                        else:
                            if st.button("", key=f"reactivate_{user_id}", icon=":material/restore:", help="Reactivate user", width="stretch"):
                                show_reactivate_confirm(user_id, name)

    render_table_pagination(current_page, total_pages, total_items, start_idx, end_idx)


# ============================================================
# PAGE ENTRYPOINT
# ============================================================

def show():
    load_css("manage_users.css")
    show_flash_message()

    current_user, is_hospital_admin, current_hospital_id, _ = get_current_user_info()

    with st.container(key="sa_page"):

        if page_header(
            "Manage users",
            "View and manage user accounts, clinical roles, and hospital permissions.",
            "Register user",
            "add_user_button",
            "person_add",
        ):
            show_add_user_form()

        # ---------------- Users the person may see ----------------
        users = get_all_users() or []

        if is_hospital_admin:
            if current_hospital_id is None:
                st.error("Your account is not assigned to a hospital. Please contact your Superadmin.")
                st.stop()

            users = [
                user for user in users
                if user.get("hospital_id") == current_hospital_id
                and user.get("user_id") != current_user.get("user_id")
                and role_name_of(user).strip().lower() != "superadmin"
            ]

        # ---------------- Metrics ----------------
        total_users = len(users)
        active_users = sum(1 for u in users if u.get("is_active"))
        radiologists = sum(1 for u in users if "radiologist" == role_name_of(u).strip().lower())
        rad_techs = sum(1 for u in users if "radiologic technologist" in role_name_of(u).strip().lower())

        metrics = [
            ("Total staff", total_users, "groups", ""),
            ("Active accounts", active_users, "how_to_reg", "green"),
            ("Radiologists", radiologists, "radiology", "blue"),
            ("Rad technologists", rad_techs, "medical_services", "amber"),
        ]

        for column, (title, value, icon, tone) in zip(st.columns(4), metrics):
            with column:
                metric_card(title, value, icon, tone)

        hospital_names = sorted({h["hospital_name"] for h in (get_all_hospitals() or []) if h and h.get("hospital_name")})

        matches = show_filters(users, hospital_names, show_hospital_filter=not is_hospital_admin)

        render_users_table(matches, current_user=current_user)
