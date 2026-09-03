import streamlit as st

from backend.user_service import create_user

from backend.supabase_client import supabase
from datetime import date, datetime

FALLBACK_ROLES = [
    {"role_id": 1, "role_name": "Radiologist"},
    {"role_id": 2, "role_name": "Radiologic Technologist"},
    {"role_id": 3, "role_name": "Hospital Admin"},
]

FALLBACK_USERS = [
    {
        "user_id": "demo-rad-001",
        "user_fname": "Sarah",
        "user_lname": "Jenkins",
        "role_id": 1,
        "is_active": True,
        "roles": {"role_name": "Radiologist"},
    },
    {
        "user_id": "demo-tech-002",
        "user_fname": "Alex",
        "user_lname": "Rivera",
        "role_id": 2,
        "is_active": True,
        "roles": {"role_name": "Radiologic Technologist"},
    },
    {
        "user_id": "demo-adm-003",
        "user_fname": "Marcus",
        "user_lname": "Vance",
        "role_id": 3,
        "is_active": True,
        "roles": {"role_name": "Hospital Admin"},
    },
]

def get_roles():
    """
    Get all available roles.
    """
    try:
        response = (
            supabase
            .table("roles")
            .select("role_name", "role_id")
            .order("role_id")
            .execute()
        )
        return response.data if response and response.data else FALLBACK_ROLES
    except Exception:
        return FALLBACK_ROLES

def get_users():
    """
    Get all users with their roles.
    """
    try:
        response = (
            supabase
            .table("user_profiles")
            .select("""
                user_id,
                user_fname,
                user_lname,
                role_id,
                is_active,
                roles (
                    role_name
                )
            """)
            .order("user_lname")
            .execute()
        )
        return response.data if response and response.data else FALLBACK_USERS
    except Exception:
        return FALLBACK_USERS

def get_user_counts():
    """
    Count total staff, radiologists,
    and radiologic technologists.
    """

    users = get_users()

    total_staff = 0
    radiologist_count = 0
    radiologic_technologist_count = 0

    for user in users:

        # Get the role safely
        role_data = user.get("roles")

        if not role_data:
            continue

        role_name = role_data.get("role_name")

        # Count Radiologists
        if role_name == "Radiologist":

            radiologist_count += 1
            total_staff += 1

        # Count Radiologic Technologists
        elif role_name == "Radiologic Technologist":

            radiologic_technologist_count += 1
            total_staff += 1

        # Count General Staff
        elif role_name == "Staff":

            total_staff += 1

    return {
        "total_staff": total_staff,
        "radiologist": radiologist_count,
        "radiologic_technologist": radiologic_technologist_count,
        "total_patients": 0
    }

def prepare_users_table(users):
    """
    Prepare user data for the ALL USERS table.
    """

    table_data = []

    for user in users:

        role_data = user.get("roles")

        if role_data:
            role_name = role_data.get("role_name")
        else:
            role_name = "No Role"


        first_name = user.get("user_fname") or ""
        last_name = user.get("user_lname") or ""

        full_name = f"{last_name}, {first_name}"


        if user.get("is_active"):
            account_status = "Active"
        else:
            account_status = "Inactive"



        last_login = "Never"

        table_data.append({

            "Name": full_name,

            "Clinical Role": role_name,

            "Account Status": account_status,

            "Last Login": last_login

        })


    return table_data


def metric_card(title, value, icon):

    st.markdown(
        f"""<div class="metric-card">
<div class="metric-title">{title}</div>
<div class="metric-value">{value}</div>
<div class="metric-icon">{icon}</div>
</div>""",
        unsafe_allow_html=True
    )

def generate_employee_id():

    current_year = datetime.now().year

    response = (
        supabase
        .table("user_profiles")
        .select("employee_id")
        .execute()
    )

    users = response.data or []

    highest_number = 0

    for user in users:

        employee_id = user.get("employee_id")

        # Skip NULL employee IDs
        if not employee_id:
            continue

        # Only process current year's employee IDs
        if not employee_id.startswith(
            f"EMP-{current_year}-"
        ):
            continue

        try:

            number = int(
                employee_id.split("-")[-1]
            )

            if number > highest_number:
                highest_number = number

        except (ValueError, IndexError):

            continue


    next_number = highest_number + 1

    return (
        f"EMP-{current_year}-{next_number:03d}"
    )

@st.dialog("Add New User")
def show_add_user_form():
    st.subheader("Add New User")

    roles = get_roles()
    role_options = {
        role["role_name"]: role["role_id"]
        for role in roles
    }

    if not role_options:
        st.error(
            "No roles found. Please add roles first."
        )
        return

    with st.form(
        "add_user_form",
        clear_on_submit=False
    ):
         # ==========================================
        # ACCOUNT INFORMATION
        # ==========================================

        st.markdown("### Account Information")

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

        # ==========================================
        # PERSONAL INFORMATION
        # ==========================================

        st.markdown("### Personal Information")

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

        with col1:

            birthdate = st.date_input(
                "Birthdate",
                min_value=date(1900, 1, 1),
                max_value=date.today(),
            )

        with col2:

            sex = st.selectbox(
                "Sex",
                [
                    "Male",
                    "Female",
                    "Prefer not to say"
                ]
            )


        contact_number = st.text_input(
            "Contact Number",
            placeholder="+63 912 345 6789"
        )

        address = st.text_area(
            "Address"
        )


        # ==========================================
        # EMPLOYMENT INFORMATION
        # ==========================================

        st.markdown("### Employment Information")

        col1, col2 = st.columns(2)

        with col1:

            department = st.text_input(
                "Department",
                placeholder="e.g. Radiology"
            )

        with col2:

            job_title = st.text_input(
                "Job Title",
                placeholder="e.g. Radiologic Technologist"
            )


        # ==========================================
        # SYSTEM ROLE
        # ==========================================

        st.markdown("### System Role")

        selected_role = st.selectbox(
            "Select Role",
            options=list(role_options.keys())
        )


        # ==========================================
        # FORM BUTTONS
        # ==========================================

        col1, col2 = st.columns(2)

        with col1:

            submitted = st.form_submit_button(
                "Create User",
                width="stretch"
            )

        with col2:

            cancel = st.form_submit_button(
                "Cancel",
                width="stretch"
            )


        # ==========================================
        # CANCEL
        # ==========================================

        if cancel:

            st.session_state.show_add_user = False

            st.rerun()


        # ==========================================
        # CREATE USER
        # ==========================================

        if submitted:

            if not employee_id:

                st.error(
                    "Employee ID is required."
                )

                return


            if not email:

                st.error(
                    "Email is required."
                )

                return


            if not first_name:

                st.error(
                    "First name is required."
                )

                return


            if not last_name:

                st.error(
                    "Last name is required."
                )

                return


            if not department:

                st.error(
                    "Department is required."
                )

                return


            if not job_title:

                st.error(
                    "Job title is required."
                )

                return


            role_id = role_options[selected_role]

            with st.spinner("Creating user..."):

                result = create_user(
                    email=email.strip(),
                    temporary_password="LungSight123!",
                    employee_id=employee_id,
                    first_name=first_name.strip(),
                    middle_name=middle_name.strip(),
                    last_name=last_name.strip(),
                    birthdate=birthdate,
                    sex=sex,
                    contact_number=contact_number.strip(),
                    address=address.strip(),
                    department=department.strip(),
                    job_title=job_title.strip(),
                    role_id=role_id
                )

            if result.get("success") is True:

                st.session_state.user_created_success = True

                st.rerun()

            else:

                st.error(
                    result.get(
                        "message",
                        "Failed to create user."
                    )
    )

def show():

    if st.session_state.get("user_created_success"):

        st.success(
            "User successfully created!"
        )

        del st.session_state.user_created_success

    st.markdown(
        """<style>

.metric-card {
    background-color: white;
    padding: 20px;
    border-radius: 5px;
    min-height: 110px;
    border: 1px solid #e5e7eb;
    box-shadow: 0px 2px 5px rgba(0, 0, 0, 0.08);
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

</style>""",
        unsafe_allow_html=True
    )

    title_col, button_col = st.columns([4, 1])

    with title_col:

        st.title("Manage Users")


    with button_col:

        st.write("")

        if st.button(
    "Add New User",
    width="stretch"
    ):
            show_add_user_form()


    st.info(
        "View and Manage all the Users in the System."
    )

    

    counts = get_user_counts()

    col1, col2, col3, col4 = st.columns(4)


    # TOTAL STAFF

    with col1:

        metric_card(
            "Total Staff",
            counts["total_staff"],
            "[ ]"
        )


    # RADIOLOGIST

    with col2:

        metric_card(
            "Radiologist",
            counts["radiologist"],
            "[ ]"
        )


    # DOCTORS

    with col3:

        metric_card(
            "Radiologic Technologist",
            counts["radiologic_technologist"],
            "[ ]"
        )


    # TOTAL PATIENTS

    with col4:

        metric_card(
            "Total Patients",
            counts["total_patients"],
            "[ ]"
        )



    st.divider()

    st.subheader("All Users")


    # Get users from Supabase
    users = get_users()


    # Check if users exist
    if users:

        # Prepare data
        table_data = prepare_users_table(users)


        # Display table
        st.dataframe(
            table_data,
            hide_index=True,
            width="stretch"
        )

    else:

        st.info(
            "No users found."
        )
