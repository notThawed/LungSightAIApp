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
    load_css,
    page_header,
    metric_card,
    empty_state,
    note,
    show_rows,
    full_name,
    format_date,
    table_header,
    table_row,
    name_cell,
    text_cell,
    pill_cell,
    close_button,
    confirm_buttons,
    remember,
    show_flash_message,
)


# Column widths: employee id, name, role, hospital, status, last login, 3 buttons
WIDTHS = [1.2, 2.9, 1.7, 2, 1.1, 1.8, 0.5, 0.5, 0.5]
HEADERS = ["Employee ID", "Name", "Role", "Hospital", "Status", "Last login", "Actions", "", ""]

SEX_OPTIONS = ["Male", "Female", "Prefer not to say"]


# ============================================================
# SMALL HELPERS
# ============================================================

def validate_birthdate(birthdate):
    """Returns (is_valid, error_message)."""

    if birthdate is None:
        return False, "Birthdate is required."

    today = date.today()

    if birthdate > today:
        return False, "Birthdate cannot be in the future."

    if birthdate < date(1900, 1, 1):
        return False, "Please enter a valid birthdate."

    age = calculate_age(birthdate)

    if age < 18:
        return False, f"User must be at least 18 years old. Current age: {age}."

    if age > 120:
        return False, "Please enter a valid birthdate. The calculated age is over 120 years."

    return True, ""


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

    return "Global" if is_superadmin else "—"


def get_current_user_info():
    """(current_user, is_hospital_admin, hospital_id, hospital_name)"""

    current_user = st.session_state.get("user") or {}

    is_hospital_admin = (current_user.get("role") or "").strip().lower() == "hospital admin"

    hospital_name = current_user.get("hospital_name") or current_user.get("hospital")

    return current_user, is_hospital_admin, current_user.get("hospital_id"), hospital_name


# ============================================================
# ADD / EDIT USER FORM (one form for both)
# ============================================================

def render_user_form(user=None):
    """user=None adds a new user; otherwise edits that user."""

    is_edit = user is not None

    current_user, is_hospital_admin, editor_hospital_id, editor_hospital_name = get_current_user_info()

    # ---- what the person is allowed to choose ----

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

    # ---- starting values ----

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

    birthdate_start = None

    if is_edit:
        try:
            birthdate_start = date.fromisoformat(str(user.get("user_birthdate"))[:10])
        except ValueError:
            birthdate_start = date(1990, 1, 1)

    employee_id = user.get("employee_id") if is_edit else generate_employee_id()

    errors = st.container()

    # ---- the form ----

    with st.form("user_form", clear_on_submit=False):

        id_col, email_col = st.columns([1, 2])

        id_col.text_input("Employee ID", value=employee_id or "", disabled=True)
        email = email_col.text_input(
            "Email *", value=user.get("email") or "", placeholder="user@hospital.com"
        )

        password = ""

        if is_edit:
            password = st.text_input(
                "New password",
                type="password",
                placeholder="Leave blank to keep the current password",
            )

        first_col, middle_col, last_col = st.columns(3)

        first_name = first_col.text_input("First name *", value=user.get("user_fname") or "")
        middle_name = middle_col.text_input("Middle name", value=user.get("user_mname") or "")
        last_name = last_col.text_input("Last name *", value=user.get("user_lname") or "")

        birth_col, sex_col, contact_col = st.columns(3)

        birthdate = birth_col.date_input(
            "Birthdate *",
            value=birthdate_start,
            min_value=date(1900, 1, 1),
            max_value=date.today(),
            format="YYYY-MM-DD",
        )

        current_sex = user.get("user_sex")

        sex = sex_col.selectbox(
            "Sex",
            SEX_OPTIONS,
            index=SEX_OPTIONS.index(current_sex) if current_sex in SEX_OPTIONS else 0,
        )

        contact_number = contact_col.text_input(
            "Contact number",
            value=user.get("user_contact_number") or "",
            placeholder="+63 912 345 6789",
        )

        address = st.text_area("Address", value=user.get("user_address") or "", height=80)

        role_col, hospital_col = st.columns(2)

        selected_role = role_col.selectbox("Role *", role_names, index=role_index)

        selected_hospital = None

        with hospital_col:
            if is_hospital_admin:
                st.text_input(
                    "Hospital",
                    value=editor_hospital_name or str(editor_hospital_id or "—"),
                    disabled=True,
                )
            elif hospital_names:
                selected_hospital = st.selectbox("Hospital *", hospital_names, index=hospital_index)
            else:
                st.warning("No hospitals registered yet.")

        cancel_col, save_col = st.columns(2)

        cancel = cancel_col.form_submit_button("Cancel", width="stretch")
        submitted = save_col.form_submit_button(
            "Save changes" if is_edit else "Create user", type="primary", width="stretch"
        )

    if cancel:
        st.rerun()

    if not submitted:
        return

    # ---- validation ----

    if not is_edit and not email.strip():
        errors.error("Email is required.")
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

    # ---- save ----

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
        done_message, fail_message = "User updated.", "Failed to update user."

    else:
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
        done_message, fail_message = "User created.", "Failed to create user."

    if result.get("success"):
        remember(done_message)
        st.rerun()
    else:
        errors.error(result.get("message", fail_message))


@st.dialog("Add user", width="medium")
def show_add_user_form():
    with st.container(key="sa_dialog"):
        render_user_form()


@st.dialog("Edit user", width="medium")
def show_edit_user_form(user_id):
    user = get_user(user_id)

    with st.container(key="sa_dialog"):
        if not user:
            st.error("User not found.")
            return

        render_user_form(user)


# ============================================================
# VIEW / DELETE / REACTIVATE
# ============================================================

@st.dialog("User details", width="medium")
def show_view_user(user_id):

    user = get_user(user_id)

    with st.container(key="sa_dialog"):

        if not user:
            st.error("User not found.")
            return

        age = calculate_age(user.get("user_birthdate"))

        account_tab, personal_tab, activity_tab = st.tabs(["Account", "Personal", "Activity"])

        with account_tab:
            show_rows([
                ("Name", user_name(user)),
                ("Employee ID", user.get("employee_id")),
                ("Email", user.get("email")),
                ("Role", role_name_of(user)),
                ("Hospital", hospital_name_of(user)),
                ("Status", "Active" if user.get("is_active") else "Inactive"),
            ])

        with personal_tab:
            show_rows([
                ("Sex", user.get("user_sex")),
                ("Age", f"{age} years old" if age is not None else None),
                ("Birthdate", format_date(user.get("user_birthdate"))),
                ("Contact number", user.get("user_contact_number")),
                ("Address", user.get("user_address")),
            ])

        with activity_tab:
            show_rows([
                ("Last login", format_date(user.get("last_login"), with_time=True) if user.get("last_login") else "Never"),
                ("Created", format_date(user.get("created_at"), with_time=True)),
                ("Last updated", format_date(user.get("updated_at"), with_time=True)),
            ])

        close_button(f"close_user_{user_id}")


@st.dialog("Delete user", width="small")
def show_delete_confirm(user_id, name):

    with st.container(key="sa_dialog"):

        st.markdown(f"<p class='sa-dialog-text'>Delete <b>{name}</b>?</p>", unsafe_allow_html=True)

        note(
            "This cannot be undone, and it may fail if the user has related records.",
            "red",
        )

        if confirm_buttons(f"delete_user_{user_id}", "Delete"):
            with st.spinner("Deleting user..."):
                result = delete_user(user_id)

            if result.get("success"):
                remember("User deleted.")
                st.rerun()
            else:
                st.error(result.get("message", "Failed to delete user."))


@st.dialog("Reactivate user", width="small")
def show_reactivate_confirm(user_id, name):

    with st.container(key="sa_dialog"):

        st.markdown(f"<p class='sa-dialog-text'>Reactivate <b>{name}</b>?</p>", unsafe_allow_html=True)

        if confirm_buttons(f"reactivate_user_{user_id}", "Reactivate"):
            with st.spinner("Reactivating user..."):
                result = reactivate_user(user_id)

            if result.get("success"):
                remember("User reactivated.")
                st.rerun()
            else:
                st.error(result.get("message", "Failed to reactivate user."))


# ============================================================
# FILTERS + TABLE
# ============================================================

def show_filters(users, hospital_names, show_hospital_filter):
    """Search plus three dropdowns. Returns the users that match."""

    widths = [3, 1.6, 1.4, 2] if show_hospital_filter else [3, 1.6, 1.4]
    columns = st.columns(widths)

    search = columns[0].text_input(
        "Search",
        placeholder="Search by name, email or employee ID",
        label_visibility="collapsed",
        key="users_search",
    ).strip().lower()

    role_names = sorted({role_name_of(user) for user in users})

    role = columns[1].selectbox(
        "Role", ["All roles"] + role_names, label_visibility="collapsed", key="users_role"
    )

    status = columns[2].selectbox(
        "Status", ["All status", "Active", "Inactive"], label_visibility="collapsed", key="users_status"
    )

    hospital = "All hospitals"

    if show_hospital_filter:
        hospital = columns[3].selectbox(
            "Hospital", ["All hospitals"] + hospital_names, label_visibility="collapsed", key="users_hospital"
        )

    matches = []

    for user in users:

        text = f"{user_name(user)} {user.get('email', '')} {user.get('employee_id', '')}".lower()

        if search and search not in text:
            continue
        if role != "All roles" and role_name_of(user) != role:
            continue
        if status != "All status" and ("Active" if user.get("is_active") else "Inactive") != status:
            continue
        if hospital != "All hospitals" and hospital_name_of(user) != hospital:
            continue

        matches.append(user)

    return matches


def render_users_table(users):

    if not users:
        empty_state("No users found.")
        return

    with st.container(key="sa_table_users"):

        table_header(HEADERS, WIDTHS, "users")

        for user in users:

            user_id = user.get("user_id")
            name = user_name(user)
            is_active = user.get("is_active")

            with table_row(f"users_{user_id}", WIDTHS) as cols:

                text_cell(cols[0], user.get("employee_id"), muted=True)
                name_cell(cols[1], name, user.get("email"))
                text_cell(cols[2], role_name_of(user))
                text_cell(cols[3], hospital_name_of(user))
                pill_cell(cols[4], "Active" if is_active else "Inactive", "green" if is_active else "grey")
                text_cell(
                    cols[5],
                    format_date(user.get("last_login"), with_time=True) if user.get("last_login") else "Never",
                    muted=True,
                )

                if cols[6].button("", key=f"view_{user_id}", icon=":material/visibility:", help="View user"):
                    show_view_user(user_id)

                if cols[7].button("", key=f"edit_{user_id}", icon=":material/edit:", help="Edit user"):
                    show_edit_user_form(user_id)

                if is_active:
                    if cols[8].button("", key=f"delete_{user_id}", icon=":material/delete:", help="Delete user"):
                        show_delete_confirm(user_id, name)
                else:
                    if cols[8].button("", key=f"reactivate_{user_id}", icon=":material/restore:", help="Reactivate user"):
                        show_reactivate_confirm(user_id, name)


# ============================================================
# PAGE
# ============================================================

def show():

    load_css("manage_users.css")
    show_flash_message()

    current_user, is_hospital_admin, current_hospital_id, _ = get_current_user_info()

    with st.container(key="sa_page"):

        if page_header(
            "Manage users",
            "View and manage everyone with access to the system.",
            "Add user", "add_user_button", "person_add",
        ):
            show_add_user_form()

        # ---------------- Metrics ----------------

        counts = get_user_counts()

        metrics = [
            ("Total staff", counts["total_staff"], "groups", ""),
            ("Radiologists", counts["radiologist"], "radiology", "blue"),
            ("Radiologic technologists", counts["radiologic_technologist"], "medical_services", "amber"),
            ("Total patients", counts["total_patients"], "personal_injury", "green"),
        ]

        for column, (title, value, icon, tone) in zip(st.columns(4), metrics):
            with column:
                metric_card(title, value, icon, tone)

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

        hospital_names = sorted({h["hospital_name"] for h in (get_all_hospitals() or []) if h})

        matches = show_filters(users, hospital_names, show_hospital_filter=not is_hospital_admin)

        render_users_table(matches)