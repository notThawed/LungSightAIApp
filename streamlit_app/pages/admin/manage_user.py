import streamlit as st

from datetime import date, datetime

from backend.fetches import (
    get_all_users,
    get_all_roles,
    get_user,
    get_user_counts,
    generate_employee_id
)

from backend.crud import (
    create_user,
    update_user,
    delete_user
)


# ==========================================
# BIRTHDATE VALIDATION
# ==========================================

def validate_birthdate(birthdate):

    if birthdate is None:
        return False, "Birthdate is required."

    today = date.today()

    if birthdate > today:

        return (
            False,
            "Birthdate cannot be in the future."
        )

    minimum_date = date(
        1900,
        1,
        1
    )

    if birthdate < minimum_date:

        return (
            False,
            "Please enter a valid birthdate."
        )

    age = (
        today.year
        - birthdate.year
    )

    if (
        today.month,
        today.day
    ) < (
        birthdate.month,
        birthdate.day
    ):

        age -= 1

    if age < 18:

        return (
            False,
            f"User must be at least 18 years old. "
            f"Current age: {age}."
        )

    if age > 120:

        return (
            False,
            "Please enter a valid birthdate. "
            "The calculated age is over 120 years."
        )

    return True, ""

def calculate_age(birthdate):

    if not birthdate:
        return None

    try:
        if isinstance(birthdate, datetime):
            birthdate = birthdate.date()

        elif isinstance(birthdate, str):
            birthdate = date.fromisoformat(
                birthdate[:10]
            )
        if not isinstance(birthdate, date):
            return None
        today = date.today()

        age = (
            today.year - birthdate.year
        )

        if (
            today.month,
            today.day
        ) < (
            birthdate.month,
            birthdate.day
        ):

            age -= 1

        return age

    except (
        ValueError,
        TypeError
    ):
        return None

def format_date(value):

    if not value:
        return "--"

    try:
        if isinstance(value, datetime):
            return value.strftime(
                "%B %d, %Y"
            )
        value_string = str(value)

        parsed_date = date.fromisoformat(
            value_string[:10]
        )
        return parsed_date.strftime(
            "%B %d, %Y"
        )

    except (
        ValueError,
        TypeError
    ):
        return str(value)

def metric_card(title, value, icon):

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">{title}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-icon">{icon}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def format_datetime(value):

    if not value:
        return "Never"

    try:
        if isinstance(value, datetime):
            return value.strftime(
                "%B %d, %Y at %I:%M %p"
            )
        value_string = str(value)
        parsed_datetime = datetime.fromisoformat(
            value_string.replace(
                "Z",
                "+00:00"
            )
        )

        return parsed_datetime.strftime(
            "%B %d, %Y at %I:%M %p"
        )

    except (
        ValueError,
        TypeError
    ):
        return str(value)



# ==========================================
# USERS TABLE
# ==========================================

def render_users_table(users):

    if not users:

        st.info(
            "No users found. Please add users first."
        )

        return

    col_widths = [
        2,
        3,
        2,
        2,
        2,
        1,
        1,
        1
    ]

    header_cols = st.columns(
        col_widths
    )

    headers = [
        "Employee ID",
        "Name",
        "Clinical Role",
        "Status",
        "Last Login",
        "",
        "",
        ""
    ]

    for col, header in zip(
        header_cols,
        headers
    ):

        col.markdown(
            f"**{header}**"
        )

    st.divider()

    for user in users:

        user_id = user.get(
            "user_id"
        )

        employee_id = (
            user.get("employee_id")
            or "--"
        )

        # ------------------------------------------
        # ROLE
        # ------------------------------------------

        role_data = user.get(
            "roles"
        )

        role_name = (
            role_data.get("role_name")
            if role_data
            else "N/A"
        )

        # ------------------------------------------
        # NAME
        # ------------------------------------------

        first_name = (
            user.get("user_fname")
            or ""
        )

        middle_name = (
            user.get("user_mname")
            or ""
        )

        last_name = (
            user.get("user_lname")
            or ""
        )

        full_name = (
            f"{first_name} "
            f"{middle_name} "
            f"{last_name}"
        ).strip()

        # ------------------------------------------
        # STATUS
        # ------------------------------------------

        status = (
            "Active"
            if user.get("is_active")
            else "Inactive"
        )

        # ------------------------------------------
        # LAST LOGIN
        # ------------------------------------------

        last_login = (
            format_datetime(
                            user.get(
                                "last_login"
                            )
                        )
        )

        if last_login != "Never":

            last_login = str(
                last_login
            ).replace(
                "T",
                " "
            )

        # ------------------------------------------
        # TABLE ROW
        # ------------------------------------------

        row = st.columns(
            col_widths
        )

        row[0].write(
            employee_id
        )

        row[1].write(
            full_name
        )

        row[2].write(
            role_name
        )

        row[3].write(
            status
        )

        row[4].write(
            last_login
        )

        # ------------------------------------------
        # EDIT
        # ------------------------------------------

        if row[5].button(
            "Edit",
            key=f"edit_{user_id}",
            help="Edit user details"
        ):

            show_edit_user_form(
                user_id
            )

        # ------------------------------------------
        # DELETE
        # ------------------------------------------

        if row[6].button(
            "Delete",
            key=f"delete_{user_id}",
            help="Delete user"
        ):

            show_delete_confirm(
                user_id,
                full_name
            )

        if row[7].button(
            "View",
            key=f"view_{user_id}",
            help="View User"
        ):
            show_view_user(
                user_id
            )

        st.divider()


# ==========================================
# ADD USER
# ==========================================

@st.dialog("Add New User")
def show_add_user_form():

    st.subheader(
        "Add New User"
    )

    # ------------------------------------------
    # GET ROLES
    # ------------------------------------------

    roles = get_all_roles()

    role_options = {
        role["role_name"]:
            role["role_id"]
        for role in roles
    }

    if not role_options:

        st.error(
            "No roles found. Please add roles first."
        )

        return

    # ------------------------------------------
    # FORM
    # ------------------------------------------

    with st.form(
        "add_user_form",
        clear_on_submit=False
    ):

        # ======================================
        # ACCOUNT INFORMATION
        # ======================================

        st.markdown(
            "### Account Information"
        )

        employee_id = generate_employee_id()

        st.text_input(
            "Employee ID",
            value=employee_id,
            disabled=True
        )

        email = st.text_input(
            "Email",
            placeholder="user@hospital.com"
        )

        # ======================================
        # PERSONAL INFORMATION
        # ======================================

        st.markdown(
            "### Personal Information"
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            first_name = st.text_input(
                "First Name"
            )

        with col2:

            middle_name = st.text_input(
                "Middle Name"
            )

        with col3:

            last_name = st.text_input(
                "Last Name"
            )

        col1, col2 = st.columns(2)

        # ======================================
        # BIRTHDATE
        # ======================================

        with col1:

            birthdate = st.date_input(
                "Birthdate",
                value=None,
                min_value=date(
                    1900,
                    1,
                    1
                ),
                max_value=date.today(),
                format="YYYY-MM-DD"
            )

        # ======================================
        # SEX
        # ======================================

        with col2:

            sex = st.selectbox(
                "Sex",
                [
                    "Male",
                    "Female",
                    "Prefer not to say"
                ]
            )

        # ======================================
        # CONTACT
        # ======================================

        contact_number = st.text_input(
            "Contact Number",
            placeholder="+63 912 345 6789"
        )

        # ======================================
        # ADDRESS
        # ======================================

        address = st.text_area(
            "Address"
        )

        # ======================================
        # SYSTEM ROLE
        # ======================================

        st.markdown(
            "### System Role"
        )

        selected_role = st.selectbox(
            "Select Role",
            options=list(
                role_options.keys()
            )
        )

        # ======================================
        # BUTTONS
        # ======================================

        col1, col2 = st.columns(2)

        with col1:

            submitted = (
                st.form_submit_button(
                    "Create User",
                    width="stretch"
                )
            )

        with col2:

            cancel = (
                st.form_submit_button(
                    "Cancel",
                    width="stretch"
                )
            )

        # ======================================
        # CANCEL
        # ======================================

        if cancel:

            st.rerun()

        # ======================================
        # CREATE
        # ======================================

        if submitted:

            # ----------------------------------
            # EMAIL
            # ----------------------------------

            if not email.strip():

                st.error(
                    "Email is required."
                )

                return

            # ----------------------------------
            # FIRST NAME
            # ----------------------------------

            if not first_name.strip():

                st.error(
                    "First name is required."
                )

                return

            # ----------------------------------
            # LAST NAME
            # ----------------------------------

            if not last_name.strip():

                st.error(
                    "Last name is required."
                )

                return

            # ----------------------------------
            # BIRTHDATE
            # ----------------------------------

            is_valid_birthdate, birthdate_error = (
                validate_birthdate(
                    birthdate
                )
            )

            if not is_valid_birthdate:

                st.error(
                    birthdate_error
                )

                return

            # ----------------------------------
            # ROLE
            # ----------------------------------

            role_id = role_options[
                selected_role
            ]

            # ----------------------------------
            # CREATE USER
            # ----------------------------------

            with st.spinner(
                "Creating user..."
            ):

                result = create_user(
                    email=email.strip(),
                    password="LungSight123!",
                    first_name=first_name.strip(),
                    middle_name=middle_name.strip(),
                    last_name=last_name.strip(),
                    birth_date=birthdate,
                    employee_id=employee_id,
                    role_id=role_id,
                    sex=sex,
                    contact_number=(
                        contact_number.strip()
                    ),
                    address=address.strip()
                )

            # ----------------------------------
            # SUCCESS
            # ----------------------------------

            if result.get("success"):

                st.session_state[
                    "user_created_success"
                ] = True

                st.rerun()

            # ----------------------------------
            # ERROR
            # ----------------------------------

            else:

                st.error(
                    result.get(
                        "message",
                        "Failed to create user."
                    )
                )


# ==========================================
# EDIT USER
# ==========================================

@st.dialog("Edit User")
def show_edit_user_form(user_id):

    user = get_user(
        user_id
    )

    if not user:

        st.error(
            "User not found."
        )

        return

    # ------------------------------------------
    # ROLES
    # ------------------------------------------

    roles = get_all_roles()

    role_options = {
        role["role_name"]:
            role["role_id"]
        for role in roles
    }

    role_names = list(
        role_options.keys()
    )

    role_id_to_name = {
        role_id: role_name
        for role_name, role_id
        in role_options.items()
    }

    current_role_name = (
        role_id_to_name.get(
            user.get("role_id")
        )
    )

    current_index = (
        role_names.index(
            current_role_name
        )
        if current_role_name in role_names
        else 0
    )

    # ------------------------------------------
    # FORM
    # ------------------------------------------

    with st.form(
        "edit_user_form",
        clear_on_submit=False
    ):

        # ======================================
        # ACCOUNT INFORMATION
        # ======================================

        st.markdown(
            "### Account Information"
        )

        email = st.text_input(
            "Email",
            value=user.get("email") or ""
        )

        st.text_input(
            "Employee ID",
            value=(
                user.get("employee_id")
                or ""
            ),
            disabled=True
        )

        password = st.text_input(
            "New Password",
            type="password",
            placeholder=(
                "Leave blank to keep current password"
            )
        )

        # ======================================
        # PERSONAL INFORMATION
        # ======================================

        st.markdown(
            "### Personal Information"
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            first_name = st.text_input(
                "First Name",
                value=(
                    user.get("user_fname")
                    or ""
                )
            )

        with col2:

            middle_name = st.text_input(
                "Middle Name",
                value=(
                    user.get("user_mname")
                    or ""
                )
            )

        with col3:

            last_name = st.text_input(
                "Last Name",
                value=(
                    user.get("user_lname")
                    or ""
                )
            )

        col1, col2 = st.columns(2)

        # ======================================
        # BIRTHDATE
        # ======================================

        with col1:

            birthdate_value = (
                user.get(
                    "user_birthdate"
                )
            )

            try:

                if birthdate_value:

                    parsed_birthdate = (
                        date.fromisoformat(
                            str(
                                birthdate_value
                            )[:10]
                        )
                    )

                else:

                    parsed_birthdate = date(
                        1990,
                        1,
                        1
                    )

            except (
                ValueError,
                TypeError
            ):

                parsed_birthdate = date(
                    1990,
                    1,
                    1
                )

            birthdate = st.date_input(
                "Birthdate",
                value=parsed_birthdate,
                min_value=date(
                    1900,
                    1,
                    1
                ),
                max_value=date.today(),
                format="YYYY-MM-DD"
            )


        # ======================================
        # SEX
        # ======================================

        with col2:

            sex_options = [
                "Male",
                "Female",
                "Prefer not to say"
            ]

            current_sex = user.get(
                "user_sex"
            )

            sex = st.selectbox(
                "Sex",
                sex_options,
                index=(
                    sex_options.index(
                        current_sex
                    )
                    if current_sex in sex_options
                    else 0
                )
            )

        # ======================================
        # CONTACT
        # ======================================

        contact_number = st.text_input(
            "Contact Number",
            value=(
                user.get(
                    "user_contact_number"
                )
                or ""
            )
        )

        # ======================================
        # ADDRESS
        # ======================================

        address = st.text_area(
            "Address",
            value=(
                user.get(
                    "user_address"
                )
                or ""
            )
        )

        # ======================================
        # ROLE
        # ======================================

        st.markdown(
            "### System Role"
        )

        selected_role = st.selectbox(
            "Select Role",
            role_names,
            index=current_index
        )

        # ======================================
        # BUTTONS
        # ======================================

        col1, col2 = st.columns(2)

        with col1:

            submitted = (
                st.form_submit_button(
                    "Save Changes",
                    width="stretch"
                )
            )

        with col2:

            cancel = (
                st.form_submit_button(
                    "Cancel",
                    width="stretch"
                )
            )

        # ======================================
        # CANCEL
        # ======================================

        if cancel:

            st.rerun()

        # ======================================
        # SAVE
        # ======================================

        if submitted:

            # ----------------------------------
            # FIRST NAME
            # ----------------------------------

            if not first_name.strip():

                st.error(
                    "First name is required."
                )

                return

            # ----------------------------------
            # LAST NAME
            # ----------------------------------

            if not last_name.strip():

                st.error(
                    "Last name is required."
                )

                return

            # ----------------------------------
            # BIRTHDATE
            # ----------------------------------

            is_valid_birthdate, birthdate_error = (
                validate_birthdate(
                    birthdate
                )
            )

            if not is_valid_birthdate:

                st.error(
                    birthdate_error
                )

                return

            # ----------------------------------
            # SAVE CHANGES
            # ----------------------------------

            with st.spinner(
                "Saving changes..."
            ):

                result = update_user(
                    user_id=user_id,
                    email=email.strip(),
                    password=password.strip(),
                    first_name=first_name.strip(),
                    middle_name=middle_name.strip(),
                    last_name=last_name.strip(),
                    birth_date=birthdate,
                    role_id=role_options[
                        selected_role
                    ],
                    sex=sex,
                    contact_number=(
                        contact_number.strip()
                    ),
                    address=address.strip()
                )

            # ----------------------------------
            # SUCCESS
            # ----------------------------------

            if result.get("success"):

                st.session_state[
                    "user_updated_success"
                ] = True

                st.rerun()

            # ----------------------------------
            # ERROR
            # ----------------------------------

            else:

                st.error(
                    result.get(
                        "message",
                        "Failed to update user."
                    )
                )


# ==========================================
# DELETE USER
# ==========================================

@st.dialog("Delete User")
def show_delete_confirm(
    user_id,
    full_name
):

    st.warning(
        f"Are you sure you want to delete "
        f"**{full_name}**? "
        "This cannot be undone, and may fail "
        "if this user has related records."
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "Cancel",
            width="stretch"
        ):

            st.rerun()

    with col2:

        if st.button(
            "Delete",
            width="stretch",
            type="primary"
        ):

            with st.spinner(
                "Deleting user..."
            ):

                result = delete_user(
                    user_id
                )

            if result.get("success"):

                st.session_state[
                    "user_deleted_success"
                ] = True

                st.rerun()

            else:

                st.error(
                    result.get(
                        "message",
                        "Failed to delete user."
                    )
                )

@st.dialog("View User")
def show_view_user(user_id):

    user = get_user(
        user_id
    )

    if not user:

        st.error(
            "User not found."
        )

        return

    first_name = user.get("user_fname") or ""
    middle_name = user.get("user_mname") or ""
    last_name = user.get("user_lname") or ""

    full_name = (
        f"{first_name} "
        f"{middle_name} "
        f"{last_name}"
    ).strip()

    role_data = user.get("roles")

    role_name = (
        role_data.get("role_name")
        if role_data
        else "N/A"
    )

    status = (
        "Active"
        if user.get("is_active")
        else "Inactive"
    )

    birthdate_value = user.get("user_birthdate")

    formatted_birthdate = format_date(
        birthdate_value
    )

    age = calculate_age(
        birthdate_value
    )

    age_display = (
        f"{age} years old"
        if age is not None
        else "--"
    )

    st.markdown(
        f"### {full_name}'s Account Information"
    )

    st.divider()

    col1, col2 = st.columns(2)


    with col1:
        st.markdown(
            "**Employee ID**"
        )

        st.write(
            user.get("employee_id")
            or "--"
        )

    with col2:
        st.markdown(
            "**Account Status**"
        )

        st.write(
            status
        )
    st.write("")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(
            "**Email**"
        )

        st.write(
            user.get("email")
            or "--"
        )

    with col2:
        st.markdown(
            "**System Role**"
        )

        st.write(
            role_name
        )

    st.divider()

    st.markdown(
        "### Personal Information"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.markdown(
            "**First Name**"
        )

        st.write(
            first_name
        )

    with col2:
    
            st.markdown(
                "**Middle Name**"
            )
    
            st.write(
                middle_name
            )

    with col3:
    
            st.markdown(
                "**Last Name**"
            )
    
            st.write(
                last_name
            )
    st.write("")
    col1, col2, col3 = st.columns(3)

    with col1:

        st.markdown(
            "**Sex**"
        )

        st.write(
            user.get("user_sex")
        )

    with col2:

        st.markdown(
            "**Age**"
        )

        st.write(
            age_display
        )

    with col3:

        st.markdown(
            "**Birthdate**"
        )

        st.write(
            formatted_birthdate
        )

    st.divider()

    st.markdown(
        "### Contact Information"
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            "**Contact Number**"
        )

        st.write(
            user.get("user_contact_number")
            or "--"
        )

    with col2:
        st.markdown(
            "**Address**"
        )
        st.write(
            user.get("user_address")
            or "--"
        )

    st.divider()

    st.markdown("### Account Activity")

    col1, col2 = st.columns(2)

    with col1:

        st.markdown(
            "**Last Login**"
        )

        st.write(
            format_datetime(
                user.get(
                    "last_login"
                )
            )
        )

    with col2:

        st.markdown(
            "**Created At**"
        )

        st.write(
            format_datetime(
                user.get(
                    "created_at"
                )
            )
        )

    st.markdown(
        "**Last Updated**"
    )

    st.write(
        format_datetime(
            user.get(
                "updated_at"
            )
        )
    )

    if st.button(
        "Return",
        width="content"
    ):
        st.rerun()

# ==========================================
# MAIN PAGE
# ==========================================

def show():

    # ==========================================
    # SUCCESS MESSAGES
    # ==========================================

    if st.session_state.get(
        "user_updated_success"
    ):

        st.success(
            "User updated successfully!"
        )

        del st.session_state[
            "user_updated_success"
        ]

    if st.session_state.get(
        "user_deleted_success"
    ):

        st.success(
            "User deleted successfully!"
        )

        del st.session_state[
            "user_deleted_success"
        ]

    if st.session_state.get(
        "user_created_success"
    ):

        st.success(
            "User successfully created!"
        )

        del st.session_state[
            "user_created_success"
        ]

    # ==========================================
    # CSS
    # ==========================================

    st.markdown(
        """
        <style>

        .metric-card {
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            min-height: 110px;
            border: 1px solid #e5e7eb;
            box-shadow:
                0px 2px 5px rgba(0, 0, 0, 0.08);
            position: relative;
            margin-bottom: 10px;
        }

        .metric-title {
            font-size: 13px;
            font-weight: 500;
            color: #6b7280;
            text-transform: uppercase;
        }

        .metric-value {
            font-size: 28px;
            font-weight: bold;
            color: #4a76b8;
            margin-top: 10px;
        }

        .metric-icon {
            position: absolute;
            top: 18px;
            right: 18px;
            font-size: 24px;
        }

        </style>
        """,
        unsafe_allow_html=True
    )

    # ==========================================
    # HEADER
    # ==========================================

    title_col, button_col = st.columns(
        [4, 1]
    )

    with title_col:

        st.title(
            "Manage Users"
        )

    with button_col:

        st.write("")

        if st.button(
            "Add New User",
            width="stretch"
        ):

            show_add_user_form()

    st.info(
        "View and Manage all the Users "
        "in the System."
    )

    # ==========================================
    # USER METRICS
    # ==========================================

    counts = get_user_counts()

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        metric_card(
            "Total Staff",
            counts["total_staff"],
            "[ ]"
        )

    with col2:

        metric_card(
            "Radiologist",
            counts["radiologist"],
            "[ ]"
        )

    with col3:

        metric_card(
            "Radiologic Technologist",
            counts[
                "radiologic_technologist"
            ],
            "[ ]"
        )

    with col4:

        metric_card(
            "Total Patients",
            counts["total_patients"],
            "[ ]"
        )

    # ==========================================
    # USERS LIST
    # ==========================================

    st.divider()

    subtitle_col, search_col, filter_col = (
        st.columns([1, 1, 1])
    )

    with subtitle_col:

        st.subheader(
            "Users List"
        )

    with search_col:

        st.text_input(
            "Search by Name or Email",
            key="search_user"
        )

    with filter_col:

        st.selectbox(
            "Filter by",
            options=[
                "Select Filter",
                "Roles",
                "Status",
                "Emp ID"
            ],
            key="role_filter"
        )

    # ==========================================
    # GET USERS
    # ==========================================

    users = get_all_users()

    # ==========================================
    # SEARCH
    # ==========================================

    search_term = (
        st.session_state.get(
            "search_user",
            ""
        )
        .strip()
        .lower()
    )

    if search_term:

        users = [
            user
            for user in users
            if search_term
            in (
                f"{user.get('user_fname', '')} "
                f"{user.get('user_mname', '')} "
                f"{user.get('user_lname', '')} "
                f"{user.get('email', '')}"
            ).lower()
        ]

    # ==========================================
    # FILTER
    # ==========================================

    selected_filter = (
        st.session_state.get(
            "role_filter"
        )
    )

    if selected_filter == "Roles":

        role_names = sorted(
            {
                user.get(
                    "roles",
                    {}
                ).get(
                    "role_name"
                )
                for user in users
                if user.get("roles")
            }
        )

        if role_names:

            selected_role = st.selectbox(
                "Select Role",
                ["All"] + role_names,
                key="selected_role_filter"
            )

            if selected_role != "All":

                users = [
                    user
                    for user in users
                    if user.get(
                        "roles",
                        {}
                    ).get(
                        "role_name"
                    ) == selected_role
                ]

    elif selected_filter == "Status":

        selected_status = st.selectbox(
            "Select Status",
            [
                "All",
                "Active",
                "Inactive"
            ],
            key="selected_status_filter"
        )

        if selected_status != "All":

            is_active = (
                selected_status == "Active"
            )

            users = [
                user
                for user in users
                if user.get(
                    "is_active"
                ) == is_active
            ]

    elif selected_filter == "Emp ID":

        employee_search = st.text_input(
            "Employee ID",
            key="employee_id_filter"
        )

        if employee_search:

            users = [
                user
                for user in users
                if employee_search.lower()
                in (
                    user.get(
                        "employee_id"
                    )
                    or ""
                ).lower()
            ]

    # ==========================================
    # RENDER
    # ==========================================

    render_users_table(
        users
    )