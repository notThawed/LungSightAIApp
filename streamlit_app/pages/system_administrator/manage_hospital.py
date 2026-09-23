import streamlit as st

from backend.fetches import (
    get_all_hospitals,
    get_hospital_staff,
    get_hospital_staff_member,
)

from backend.crud import (
    create_hospital,
    update_hospital,
    deactivate_hospital,
    reactivate_hospital,
)

from backend.backend_utils.storage_utils import (
    get_profile_picture_url,
)

from streamlit_app.components.ui import (
    load_css,
    page_header,
    section_title,
    metric_card,
    table_header,
    table_row,
    text_cell,
    name_cell,
    pill_cell,
    empty_state,
    show_rows,
    safe,
    full_name,
    format_date,
    show_flash_message,
)


# ============================================================
# SESSION STATE
# ============================================================

DIALOG_KEY = "sa_hospital_dialog"
SELECTED_HOSPITAL_KEY = "sa_selected_hospital"
SELECTED_STAFF_KEY = "sa_selected_staff"


def initialize_state():

    if DIALOG_KEY not in st.session_state:
        st.session_state[DIALOG_KEY] = None

    if SELECTED_HOSPITAL_KEY not in st.session_state:
        st.session_state[SELECTED_HOSPITAL_KEY] = None

    if SELECTED_STAFF_KEY not in st.session_state:
        st.session_state[SELECTED_STAFF_KEY] = None


def open_dialog(
    dialog_name,
    hospital=None,
    user_id=None,
):

    st.session_state[DIALOG_KEY] = dialog_name

    st.session_state[SELECTED_HOSPITAL_KEY] = hospital

    st.session_state[SELECTED_STAFF_KEY] = user_id

    st.rerun()


def close_dialog():

    st.session_state[DIALOG_KEY] = None

    st.session_state[SELECTED_HOSPITAL_KEY] = None

    st.session_state[SELECTED_STAFF_KEY] = None

    st.rerun()


def back_to_hospital_staff():

    hospital = st.session_state.get(
        SELECTED_HOSPITAL_KEY
    )

    st.session_state[DIALOG_KEY] = "hospital_staff"

    st.session_state[SELECTED_STAFF_KEY] = None

    st.session_state[SELECTED_HOSPITAL_KEY] = hospital

    st.rerun()


# ============================================================
# PAGE ENTRY
# ============================================================

def show():

    initialize_state()

    load_css("manage_hospital.css")

    with st.container(key="sa_page"):

        show_flash_message()

        hospitals = load_hospitals()

        search = show_search_bar()

        hospitals = filter_hospitals(
            hospitals,
            search,
        )

        # ----------------------------------------------------
        # PAGE HEADER
        # ----------------------------------------------------

        register_clicked = page_header(
            "Manage Hospitals",
            "View registered hospitals and manage their staff.",
            action_label="Register Hospital",
            action_key="register_hospital",
            action_icon="add_business",
        )

        if register_clicked:

            open_dialog(
                "register_hospital"
            )

        # ----------------------------------------------------
        # HOSPITAL TABLE
        # ----------------------------------------------------

        create_hospital_table(
            hospitals
        )

    # --------------------------------------------------------
    # SINGLE DIALOG DISPATCHER
    #
    # Only ONE @st.dialog function is called per run.
    # --------------------------------------------------------

    render_active_dialog()


# ============================================================
# DIALOG DISPATCHER
# ============================================================

def render_active_dialog():

    dialog_name = st.session_state.get(
        DIALOG_KEY
    )

    if dialog_name == "hospital_staff":

        hospital = st.session_state.get(
            SELECTED_HOSPITAL_KEY
        )

        if hospital:

            show_hospital_staff_dialog(
                hospital
            )

    elif dialog_name == "staff_profile":

        user_id = st.session_state.get(
            SELECTED_STAFF_KEY
        )

        if user_id:

            show_staff_member_dialog(
                user_id
            )

    elif dialog_name == "register_hospital":

        show_add_hospital_form()

    elif dialog_name == "edit_hospital":

        hospital = st.session_state.get(
            SELECTED_HOSPITAL_KEY
        )

        if hospital:

            show_edit_hospital_dialog(
                hospital
            )

    elif dialog_name == "deactivate_hospital":

        hospital = st.session_state.get(
            SELECTED_HOSPITAL_KEY
        )

        if hospital:

            show_deactivate_hospital_dialog(
                hospital
            )

    elif dialog_name == "reactivate_hospital":

        hospital = st.session_state.get(
            SELECTED_HOSPITAL_KEY
        )

        if hospital:

            show_reactivate_hospital_dialog(
                hospital
            )


# ============================================================
# DATA LOADING
# ============================================================

def load_hospitals():

    try:

        return get_all_hospitals()

    except Exception as exc:

        st.error(
            f"Unable to load hospitals: {exc}"
        )

        return []


# ============================================================
# SEARCH
# ============================================================

def show_search_bar():

    return st.text_input(
        "Search hospitals",
        placeholder=(
            "Search by hospital name, code, or email..."
        ),
        label_visibility="collapsed",
        key="hospital_search",
    )


def filter_hospitals(
    hospitals,
    search,
):

    search = (
        search or ""
    ).strip().lower()

    if not search:

        return hospitals

    filtered = []

    for hospital in hospitals:

        name = (
            hospital.get(
                "hospital_name"
            )
            or ""
        ).lower()

        code = (
            hospital.get(
                "hospital_code"
            )
            or ""
        ).lower()

        email = (
            hospital.get(
                "email"
            )
            or ""
        ).lower()

        if (
            search in name
            or search in code
            or search in email
        ):

            filtered.append(
                hospital
            )

    return filtered


# ============================================================
# HOSPITAL TABLE
# ============================================================

def create_hospital_table(
    hospitals
):

    if not hospitals:

        empty_state(
            "No hospitals match your search."
        )

        return

    section_title(
        "Registered Hospitals",
        (
            f"{len(hospitals)} hospital"
            f"{'' if len(hospitals) == 1 else 's'} found."
        ),
    )

    widths = [
        1.1,
        2.6,
        1.5,
        2.8,
        2.3,
        1.1,
        1.5,
    ]

    with st.container(
        key="sa_table_hospitals"
    ):

        table_header(
            [
                "Code",
                "Hospital",
                "Contact",
                "Address",
                "Email",
                "Status",
                "Actions",
            ],
            widths,
            "hospitals",
        )

        for hospital in hospitals:

            hospital_id = hospital.get(
                "hospital_id"
            )

            is_active = hospital.get(
                "is_active",
                True,
            )

            with table_row(
                f"hospitals_{hospital_id}",
                widths,
            ) as cols:

                # ------------------------------------------------
                # CODE
                # ------------------------------------------------

                text_cell(
                    cols[0],
                    hospital.get(
                        "hospital_code"
                    ) or "—",
                    strong=True,
                )

                # ------------------------------------------------
                # HOSPITAL
                # ------------------------------------------------

                name_cell(
                    cols[1],
                    hospital.get(
                        "hospital_name"
                    )
                    or "Unnamed Hospital",
                    hospital.get(
                        "email"
                    )
                    or "",
                )

                # ------------------------------------------------
                # CONTACT
                # ------------------------------------------------

                text_cell(
                    cols[2],
                    hospital.get(
                        "contact_number"
                    )
                    or "—",
                    muted=True,
                )

                # ------------------------------------------------
                # ADDRESS
                # ------------------------------------------------

                text_cell(
                    cols[3],
                    hospital.get(
                        "address"
                    )
                    or "—",
                )

                # ------------------------------------------------
                # EMAIL
                # ------------------------------------------------

                text_cell(
                    cols[4],
                    hospital.get(
                        "email"
                    )
                    or "—",
                    muted=True,
                )

                # ------------------------------------------------
                # STATUS
                # ------------------------------------------------

                pill_cell(
                    cols[5],
                    (
                        "Active"
                        if is_active
                        else "Inactive"
                    ),
                    (
                        "green"
                        if is_active
                        else "red"
                    ),
                )

                # ------------------------------------------------
                # ACTIONS
                # ------------------------------------------------

                with cols[6]:

                    action_1, action_2 = st.columns(
                        2,
                        gap="small",
                    )

                    # ------------------------------------------------
                    # VIEW STAFF
                    # ------------------------------------------------

                    with action_1:

                        if st.button(
                            "",
                            key=f"view_staff_{hospital_id}",
                            icon=":material/groups:",
                            help="View hospital staff",
                            width="stretch",
                        ):

                            open_dialog(
                                "hospital_staff",
                                hospital=hospital,
                            )

                    # ------------------------------------------------
                    # EDIT
                    # ------------------------------------------------

                    with action_2:

                        if st.button(
                            "",
                            key=f"edit_hospital_{hospital_id}",
                            icon=":material/edit:",
                            help="Edit hospital",
                            width="stretch",
                        ):

                            open_dialog(
                                "edit_hospital",
                                hospital=hospital,
                            )

            # ----------------------------------------------------
            # SECONDARY ACTION
            # ----------------------------------------------------

            with st.container(
                key=f"sa_hospital_secondary_{hospital_id}"
            ):

                left, right = st.columns(
                    [8, 1],
                    vertical_alignment="center",
                )

                with left:

                    if not is_active:

                        st.caption(
                            "This hospital is currently inactive."
                        )

                with right:

                    if is_active:

                        if st.button(
                            "Deactivate",
                            key=f"deactivate_{hospital_id}",
                            icon=":material/block:",
                            help="Deactivate hospital",
                            width="stretch",
                        ):

                            open_dialog(
                                "deactivate_hospital",
                                hospital=hospital,
                            )

                    else:

                        if st.button(
                            "Reactivate",
                            key=f"reactivate_{hospital_id}",
                            icon=":material/check_circle:",
                            help="Reactivate hospital",
                            width="stretch",
                        ):

                            open_dialog(
                                "reactivate_hospital",
                                hospital=hospital,
                            )


# ============================================================
# HOSPITAL STAFF DIALOG
# ============================================================

@st.dialog(
    "Hospital Staff",
    width="large",
)
def show_hospital_staff_dialog(
    hospital
):

    hospital_id = hospital.get(
        "hospital_id"
    )

    hospital_name = (
        hospital.get(
            "hospital_name"
        )
        or "Hospital"
    )

    # --------------------------------------------------------
    # HEADER
    #
    # Native Streamlit elements are used here instead of
    # injecting a raw HTML <div>.
    # --------------------------------------------------------

    header_col1, header_col2 = st.columns(
        [0.7, 5],
        vertical_alignment="center",
    )

    with header_col1:

        st.markdown(
            """
            <div class="mh-dialog-icon">
                business
            </div>
            """,
            unsafe_allow_html=True,
        )

    with header_col2:

        st.subheader(
            hospital_name
        )

        st.caption(
            "Hospital staff and personnel"
        )

    # --------------------------------------------------------
    # STAFF
    # --------------------------------------------------------

    staff = load_hospital_staff(
        hospital_id
    )

    active_staff = [
        member
        for member in staff
        if member.get(
            "is_active",
            True,
        )
    ]

    total_staff = len(
        staff
    )

    active_count = len(
        active_staff
    )

    inactive_count = (
        total_staff
        - active_count
    )

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    metric_col1, metric_col2, metric_col3 = st.columns(
        3
    )

    with metric_col1:

        metric_card(
            "Total Staff",
            total_staff,
            "groups",
            "blue",
        )

    with metric_col2:

        metric_card(
            "Active Staff",
            active_count,
            "person_check",
            "green",
        )

    with metric_col3:

        metric_card(
            "Inactive Staff",
            inactive_count,
            "person_off",
            "amber",
        )

    # --------------------------------------------------------
    # HOSPITAL INFORMATION
    # --------------------------------------------------------

    section_title(
        "Hospital Information"
    )

    show_rows(
        [
            (
                "Hospital Code",
                hospital.get(
                    "hospital_code"
                )
                or "—",
            ),
            (
                "Contact Number",
                hospital.get(
                    "contact_number"
                )
                or "—",
            ),
            (
                "Email",
                hospital.get(
                    "email"
                )
                or "—",
            ),
            (
                "Address",
                hospital.get(
                    "address"
                )
                or "—",
            ),
        ]
    )

    # --------------------------------------------------------
    # ACTIVE STAFF
    # --------------------------------------------------------

    section_title(
        "Currently Active Staff",
        "Only active staff members are shown here.",
    )

    if not active_staff:

        empty_state(
            "No active staff members are currently assigned to this hospital."
        )

    else:

        create_staff_table(
            active_staff
        )

    # --------------------------------------------------------
    # BACK
    # --------------------------------------------------------

    st.divider()

    if st.button(
        "Back",
        key=f"back_hospital_staff_{hospital_id}",
        icon=":material/arrow_back:",
        width="stretch",
    ):

        close_dialog()


def load_hospital_staff(
    hospital_id
):

    try:

        if not hospital_id:

            return []

        return (
            get_hospital_staff(
                hospital_id
            )
            or []
        )

    except Exception as exc:

        st.error(
            f"Unable to load hospital staff: {exc}"
        )

        return []


# ============================================================
# STAFF TABLE
# ============================================================

def create_staff_table(
    staff
):

    widths = [
        3.2,
        2.3,
        1.8,
        1.2,
        1.4,
    ]

    with st.container(
        key="sa_table_hospital_staff"
    ):

        table_header(
            [
                "Staff Member",
                "Role",
                "Employee ID",
                "Status",
                "Action",
            ],
            widths,
            "hospital_staff",
        )

        for member in staff:

            user_id = member.get(
                "user_id"
            )

            name = full_name(
                member.get(
                    "user_fname"
                ),
                member.get(
                    "user_mname"
                ),
                member.get(
                    "user_lname"
                ),
            )

            role = get_role_name(
                member
            )

            employee_id = (
                member.get(
                    "employee_id"
                )
                or "—"
            )

            is_active = member.get(
                "is_active",
                True,
            )

            with table_row(
                f"staff_{user_id}",
                widths,
            ) as cols:

                name_cell(
                    cols[0],
                    name or "Unnamed User",
                    member.get(
                        "email"
                    )
                    or member.get(
                        "user_email"
                    )
                    or member.get(
                        "auth_email"
                    )
                    or "",
                )

                text_cell(
                    cols[1],
                    role,
                    strong=True,
                )

                text_cell(
                    cols[2],
                    employee_id,
                    muted=True,
                )

                pill_cell(
                    cols[3],
                    (
                        "Active"
                        if is_active
                        else "Inactive"
                    ),
                    (
                        "green"
                        if is_active
                        else "red"
                    ),
                )

                with cols[4]:

                    if st.button(
                        "View",
                        key=f"view_staff_member_{user_id}",
                        icon=":material/person:",
                        width="stretch",
                    ):

                        open_dialog(
                            "staff_profile",
                            user_id=user_id,
                        )


# ============================================================
# ROLE
# ============================================================

def get_role_name(
    member
):

    roles = member.get(
        "roles"
    )

    if isinstance(
        roles,
        dict,
    ):

        return (
            roles.get(
                "role_name"
            )
            or "—"
        )

    if isinstance(
        roles,
        list,
    ) and roles:

        return (
            roles[0].get(
                "role_name"
            )
            or "—"
        )

    return (
        member.get(
            "role_name"
        )
        or "—"
    )


# ============================================================
# STAFF PROFILE DIALOG
# ============================================================

@st.dialog(
    "Staff Profile",
    width="large",
)
def show_staff_member_dialog(
    user_id
):

    member = load_staff_member(
        user_id
    )

    if not member:

        st.error(
            "Unable to load this staff member."
        )

        if st.button(
            "Back",
            key=f"back_missing_staff_{user_id}",
            icon=":material/arrow_back:",
            width="stretch",
        ):

            back_to_hospital_staff()

        return

    # --------------------------------------------------------
    # BASIC INFORMATION
    # --------------------------------------------------------

    name = full_name(
        member.get(
            "user_fname"
        ),
        member.get(
            "user_mname"
        ),
        member.get(
            "user_lname"
        ),
    )

    role = get_role_name(
        member
    )

    # --------------------------------------------------------
    # EMAIL
    #
    # Important:
    # get_hospital_staff_member() must return this field.
    # --------------------------------------------------------

    email = (
        member.get(
            "email"
        )
        or member.get(
            "user_email"
        )
        or member.get(
            "auth_email"
        )
        or "—"
    )

    # --------------------------------------------------------
    # LAST LOGIN
    # --------------------------------------------------------

    last_login = member.get(
        "last_login"
    )

    # --------------------------------------------------------
    # PROFILE PICTURE
    # --------------------------------------------------------

    profile_picture_url = (
        member.get(
            "profile_picture_url"
        )
        or member.get(
            "profile_picture"
        )
        or member.get(
            "avatar_url"
        )
    )

    if not profile_picture_url:

        try:

            profile_picture_url = (
                get_profile_picture_url(
                    user_id
                )
            )

        except Exception:

            profile_picture_url = None

    # --------------------------------------------------------
    # PROFILE HEADER
    # --------------------------------------------------------

    avatar_col, info_col = st.columns(
        [1, 4],
        vertical_alignment="center",
    )

    with avatar_col:

        if profile_picture_url:

            st.image(
                profile_picture_url,
                width=110,
            )

        else:

            st.markdown(
                f"""
                <div class="mh-profile-avatar">
                    {safe(initials_for_profile(name))}
                </div>
                """,
                unsafe_allow_html=True,
            )

    with info_col:

        st.subheader(
            name or "Unnamed User"
        )

        st.caption(
            role
        )

        is_active = member.get(
            "is_active",
            True,
        )

        pill_cell(
            st,
            (
                "Active"
                if is_active
                else "Inactive"
            ),
            (
                "green"
                if is_active
                else "red"
            ),
        )

    # --------------------------------------------------------
    # ACCOUNT INFORMATION
    # --------------------------------------------------------

    section_title(
        "Account Information"
    )

    show_rows(
        [
            (
                "Email",
                email,
            ),
            (
                "Employee ID",
                member.get(
                    "employee_id"
                )
                or "—",
            ),
            (
                "Role",
                role,
            ),
            (
                "Last Login",
                format_date(
                    last_login,
                    with_time=True,
                ),
            ),
            (
                "Created",
                format_date(
                    member.get(
                        "created_at"
                    ),
                    with_time=True,
                ),
            ),
            (
                "Last Updated",
                format_date(
                    member.get(
                        "updated_at"
                    ),
                    with_time=True,
                ),
            ),
        ]
    )

    # --------------------------------------------------------
    # PERSONAL INFORMATION
    # --------------------------------------------------------

    section_title(
        "Personal Information"
    )

    show_rows(
        [
            (
                "First Name",
                member.get(
                    "user_fname"
                )
                or "—",
            ),
            (
                "Middle Name",
                member.get(
                    "user_mname"
                )
                or "—",
            ),
            (
                "Last Name",
                member.get(
                    "user_lname"
                )
                or "—",
            ),
            (
                "Birth Date",
                format_date(
                    member.get(
                        "user_birthdate"
                    )
                ),
            ),
            (
                "Sex",
                member.get(
                    "user_sex"
                )
                or "—",
            ),
            (
                "Contact Number",
                member.get(
                    "user_contact_number"
                )
                or "—",
            ),
            (
                "Address",
                member.get(
                    "user_address"
                )
                or "—",
            ),
        ]
    )

    # --------------------------------------------------------
    # WORK INFORMATION
    #
    # Department intentionally removed.
    # --------------------------------------------------------

    section_title(
        "Work Information"
    )

    show_rows(
        [
            (
                "Hospital",
                get_hospital_name(
                    member
                ),
            ),
        ]
    )

    # --------------------------------------------------------
    # BACK
    # --------------------------------------------------------

    st.divider()

    if st.button(
        "Back to Hospital Staff",
        key=f"back_to_hospital_staff_{user_id}",
        icon=":material/arrow_back:",
        width="stretch",
    ):

        back_to_hospital_staff()


def load_staff_member(
    user_id
):

    try:

        if not user_id:

            return None

        return get_hospital_staff_member(
            user_id
        )

    except Exception as exc:

        st.error(
            f"Unable to load staff profile: {exc}"
        )

        return None


# ============================================================
# HOSPITAL NAME
# ============================================================

def get_hospital_name(
    member
):

    hospitals = member.get(
        "hospitals"
    )

    if isinstance(
        hospitals,
        dict,
    ):

        return (
            hospitals.get(
                "hospital_name"
            )
            or "—"
        )

    if isinstance(
        hospitals,
        list,
    ) and hospitals:

        return (
            hospitals[0].get(
                "hospital_name"
            )
            or "—"
        )

    return (
        member.get(
            "hospital_name"
        )
        or "—"
    )


# ============================================================
# PROFILE INITIALS
# ============================================================

def initials_for_profile(
    name
):

    words = (
        str(name or "")
        .split()
    )

    if not words:

        return "?"

    if len(words) == 1:

        return words[0][0].upper()

    return (
        words[0][0]
        + words[-1][0]
    ).upper()


# ============================================================
# REGISTER HOSPITAL
# ============================================================

@st.dialog(
    "Register New Hospital",
    width="medium",
)
def show_add_hospital_form():

    st.markdown(
        "Add a new hospital to the LungSight system."
    )

    with st.form(
        "add_hospital_form",
        clear_on_submit=True,
    ):

        section_title(
            "Hospital Information"
        )

        hospital_name = st.text_input(
            "Hospital Name"
        )

        hospital_code = st.text_input(
            "Hospital Code",
            placeholder="e.g. SLMC",
        )

        address = st.text_area(
            "Address"
        )

        col1, col2 = st.columns(
            2
        )

        with col1:

            contact_number = st.text_input(
                "Contact Number",
                placeholder="+63 000 000 0000",
            )

        with col2:

            email = st.text_input(
                "Email",
                placeholder="admin@hospital.com",
            )

        st.divider()

        col1, col2 = st.columns(
            2
        )

        with col1:

            submitted = st.form_submit_button(
                "Register Hospital",
                icon=":material/add_business:",
                type="primary",
                width="stretch",
            )

        with col2:

            cancel = st.form_submit_button(
                "Cancel",
                width="stretch",
            )

    if cancel:

        close_dialog()

    if not submitted:

        return

    if not hospital_name.strip():

        st.error(
            "Hospital name is required."
        )

        return

    if not address.strip():

        st.error(
            "Address is required."
        )

        return

    try:

        create_hospital(
            hospital_name=hospital_name.strip(),
            hospital_code=(
                hospital_code.strip()
                or None
            ),
            address=address.strip(),
            contact_number=(
                contact_number.strip()
                or None
            ),
            email=(
                email.strip()
                or None
            ),
            created_by=st.session_state[
                "user"
            ]["user_id"],
        )

        st.session_state[
            "sa_flash"
        ] = (
            "Hospital registered successfully."
        )

        st.session_state[
            DIALOG_KEY
        ] = None

        st.session_state[
            SELECTED_HOSPITAL_KEY
        ] = None

        st.rerun()

    except Exception as exc:

        st.error(
            f"Failed to register hospital: {exc}"
        )


# ============================================================
# EDIT HOSPITAL
# ============================================================

@st.dialog(
    "Edit Hospital",
    width="medium",
)
def show_edit_hospital_dialog(
    hospital
):

    st.markdown(
        f"Update information for "
        f"**{safe(hospital.get('hospital_name') or 'this hospital')}**."
    )

    hospital_name = st.text_input(
        "Hospital Name",
        value=(
            hospital.get(
                "hospital_name"
            )
            or ""
        ),
    )

    hospital_code = st.text_input(
        "Hospital Code",
        value=(
            hospital.get(
                "hospital_code"
            )
            or ""
        ),
    )

    address = st.text_area(
        "Address",
        value=(
            hospital.get(
                "address"
            )
            or ""
        ),
    )

    col1, col2 = st.columns(
        2
    )

    with col1:

        contact_number = st.text_input(
            "Contact Number",
            value=(
                hospital.get(
                    "contact_number"
                )
                or ""
            ),
        )

    with col2:

        email = st.text_input(
            "Email",
            value=(
                hospital.get(
                    "email"
                )
                or ""
            ),
        )

    st.divider()

    col1, col2 = st.columns(
        2
    )

    with col1:

        save = st.button(
            "Save Changes",
            icon=":material/save:",
            type="primary",
            width="stretch",
        )

    with col2:

        cancel = st.button(
            "Cancel",
            width="stretch",
        )

    if cancel:

        close_dialog()

    if not save:

        return

    if not hospital_name.strip():

        st.error(
            "Hospital name is required."
        )

        return

    if not address.strip():

        st.error(
            "Address is required."
        )

        return

    try:

        update_hospital(
            hospital_id=hospital[
                "hospital_id"
            ],
            hospital_name=(
                hospital_name.strip()
            ),
            hospital_code=(
                hospital_code.strip()
                or None
            ),
            address=address.strip(),
            contact_number=(
                contact_number.strip()
                or None
            ),
            email=(
                email.strip()
                or None
            ),
        )

        st.session_state[
            "sa_flash"
        ] = (
            "Hospital updated successfully."
        )

        st.session_state[
            DIALOG_KEY
        ] = None

        st.session_state[
            SELECTED_HOSPITAL_KEY
        ] = None

        st.rerun()

    except Exception as exc:

        st.error(
            f"Failed to update hospital: {exc}"
        )


# ============================================================
# DEACTIVATE HOSPITAL
# ============================================================

@st.dialog(
    "Deactivate Hospital",
    width="small",
)
def show_deactivate_hospital_dialog(
    hospital
):

    hospital_name = (
        hospital.get(
            "hospital_name"
        )
        or "this hospital"
    )

    st.warning(
        f"Are you sure you want to deactivate "
        f"**{safe(hospital_name)}**?"
    )

    st.markdown(
        "The hospital will remain in the system, "
        "but its status will be set to **Inactive**."
    )

    col1, col2 = st.columns(
        2
    )

    with col1:

        if st.button(
            "Deactivate",
            icon=":material/block:",
            type="primary",
            width="stretch",
        ):

            try:

                deactivate_hospital(
                    hospital[
                        "hospital_id"
                    ]
                )

                st.session_state[
                    "sa_flash"
                ] = (
                    "Hospital deactivated successfully."
                )

                st.session_state[
                    DIALOG_KEY
                ] = None

                st.session_state[
                    SELECTED_HOSPITAL_KEY
                ] = None

                st.rerun()

            except Exception as exc:

                st.error(
                    f"Failed to deactivate hospital: {exc}"
                )

    with col2:

        if st.button(
            "Cancel",
            width="stretch",
        ):

            close_dialog()


# ============================================================
# REACTIVATE HOSPITAL
# ============================================================

@st.dialog(
    "Reactivate Hospital",
    width="small",
)
def show_reactivate_hospital_dialog(
    hospital
):

    hospital_name = (
        hospital.get(
            "hospital_name"
        )
        or "this hospital"
    )

    st.info(
        f"Reactivate **{safe(hospital_name)}**?"
    )

    st.markdown(
        "The hospital will become active again "
        "and can be used normally."
    )

    col1, col2 = st.columns(
        2
    )

    with col1:

        if st.button(
            "Reactivate",
            icon=":material/check_circle:",
            type="primary",
            width="stretch",
        ):

            try:

                reactivate_hospital(
                    hospital[
                        "hospital_id"
                    ]
                )

                st.session_state[
                    "sa_flash"
                ] = (
                    "Hospital reactivated successfully."
                )

                st.session_state[
                    DIALOG_KEY
                ] = None

                st.session_state[
                    SELECTED_HOSPITAL_KEY
                ] = None

                st.rerun()

            except Exception as exc:

                st.error(
                    f"Failed to reactivate hospital: {exc}"
                )

    with col2:

        if st.button(
            "Cancel",
            width="stretch",
        ):

            close_dialog()