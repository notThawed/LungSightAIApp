# streamlit_app/components/dialogs/manage_hospital_dialogs.py

"""
Dialogs for the System Admin's Manage Hospitals page.

All six @st.dialog functions live here:

    - show_add_hospital_form()
    - show_edit_hospital_dialog(hospital)
    - show_deactivate_hospital_dialog(hospital)
    - show_reactivate_hospital_dialog(hospital)
    - show_hospital_staff_dialog(hospital)
    - show_staff_member_dialog(user_id)

Shared session-state keys used to coordinate with the
orchestrating page (manage_hospital.py) are defined here
so both modules stay in sync.
"""

import streamlit as st

from backend.crud import (
    create_hospital,
    update_hospital,
    deactivate_hospital,
    reactivate_hospital,
)

from backend.fetches import (
    get_hospital_staff,
    get_hospital_staff_member,
)

from backend.backend_utils.geocode_utils import (
    geocode_address,
)

from backend.backend_utils.storage_utils import (
    get_profile_picture_url,
)

from backend.supabase_client import admin_supabase

from streamlit_app.components.ui import (
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
)


# ============================================================
# SHARED SESSION-STATE KEYS
# ============================================================

DIALOG_KEY = "sa_hospital_dialog"
SELECTED_HOSPITAL_KEY = "sa_selected_hospital"
SELECTED_STAFF_KEY = "sa_selected_staff"


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _close_dialog():
    """Clear all dialog-related state."""

    st.session_state[DIALOG_KEY] = None
    st.session_state[SELECTED_HOSPITAL_KEY] = None
    st.session_state[SELECTED_STAFF_KEY] = None


def _back_to_hospital_staff():
    """Return to the hospital-staff dialog from the staff-profile dialog."""

    hospital = st.session_state.get(SELECTED_HOSPITAL_KEY)

    st.session_state[DIALOG_KEY] = "hospital_staff"
    st.session_state[SELECTED_STAFF_KEY] = None
    st.session_state[SELECTED_HOSPITAL_KEY] = hospital


def _get_role_name(member):
    """Extract the role name from a staff member dict."""

    roles = member.get("roles")

    if isinstance(roles, dict):
        return roles.get("role_name") or "—"

    if isinstance(roles, list) and roles:
        return roles[0].get("role_name") or "—"

    return member.get("role_name") or "—"


def _get_hospital_name(member):
    """Extract the hospital name from a staff member dict."""

    hospitals = member.get("hospitals")

    if isinstance(hospitals, dict):
        return hospitals.get("hospital_name") or "—"

    if isinstance(hospitals, list) and hospitals:
        return hospitals[0].get("hospital_name") or "—"

    return member.get("hospital_name") or "—"


def _initials_for_profile(name):
    """Return the initials used for the fallback avatar."""

    words = str(name or "").split()

    if not words:
        return "?"

    if len(words) == 1:
        return words[0][0].upper()

    return (words[0][0] + words[-1][0]).upper()


def _load_hospital_staff(hospital_id):
    """Fetch staff for a hospital, defensively."""

    try:
        if not hospital_id:
            return []

        return get_hospital_staff(hospital_id) or []

    except Exception as exc:
        st.error(f"Unable to load hospital staff: {exc}")
        return []


def _load_staff_member(user_id):
    """Fetch a single staff member, defensively."""

    try:
        if not user_id:
            return None

        return get_hospital_staff_member(user_id)

    except Exception as exc:
        st.error(f"Unable to load staff profile: {exc}")
        return None


def _safe_rerun():
    """Rerun the app safely."""

    try:
        st.rerun()
    except Exception:
        pass


def _try_geocode_hospital(hospital_id, address, force=False):
    """
    Attempt to geocode a hospital's address and save the
    coordinates directly to the hospitals table.

    Option 1: direct UPDATE — keeps crud.py untouched.

    TODO: move this logic into crud.update_hospital() /
          crud.create_hospital() so the page does not
          reach into the database directly.

    Never raises. Never blocks the calling flow.
    """

    if not hospital_id or not address:
        return False

    try:

        coords = geocode_address(address)

        if not coords:
            return False

        lat, lon = coords

        (
            admin_supabase
            .table("hospitals")
            .update({
                "latitude": float(lat),
                "longitude": float(lon),
            })
            .eq("hospital_id", hospital_id)
            .execute()
        )

        return True

    except Exception as exc:

        print(
            f"Geocode update failed for hospital "
            f"{hospital_id}: {exc}"
        )

        return False


# ============================================================
# REGISTER HOSPITAL
# ============================================================

@st.dialog("Register New Hospital", width="medium")
def show_add_hospital_form():

    st.markdown(
        "Add a new hospital to the LungSight system. "
        "We will try to locate it on the map automatically."
    )

    with st.form(
        "add_hospital_form",
        clear_on_submit=True,
    ):

        section_title("Hospital Information")

        hospital_name = st.text_input("Hospital Name")

        hospital_code = st.text_input(
            "Hospital Code",
            placeholder="e.g. SLMC",
        )

        address = st.text_area(
            "Address",
            placeholder="Street, Barangay, City, Province",
        )

        col1, col2 = st.columns(2)

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

        col1, col2 = st.columns(2)

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
        _close_dialog()
        _safe_rerun()
        return

    if not submitted:
        return

    if not hospital_name.strip():
        st.error("Hospital name is required.")
        return

    if not address.strip():
        st.error("Address is required.")
        return

    try:

        result = create_hospital(
            hospital_name=hospital_name.strip(),
            hospital_code=(
                hospital_code.strip() or None
            ),
            address=address.strip(),
            contact_number=(
                contact_number.strip() or None
            ),
            email=(
                email.strip() or None
            ),
            created_by=st.session_state["user"]["user_id"],
        )

        if not result:
            st.error(
                "Failed to register hospital. "
                "No data returned."
            )
            return

        # ------------------------------------------------
        # AUTOMATIC GEOCODE (Enhancement A)
        #
        # Run synchronously inside a spinner. If the
        # address cannot be geocoded, the hospital is
        # still registered — just without map coordinates.
        # ------------------------------------------------

        new_hospital = result[0]
        new_hospital_id = new_hospital.get("hospital_id")

        if new_hospital_id:

            with st.spinner("Locating hospital on the map..."):

                _try_geocode_hospital(
                    new_hospital_id,
                    address.strip(),
                )

        st.session_state["sa_flash"] = (
            "Hospital registered successfully."
        )

        _close_dialog()

        # Force the page to reload cached detail data
        try:
            st.cache_data.clear()
        except Exception:
            pass

        _safe_rerun()

    except Exception as exc:

        st.error(f"Failed to register hospital: {exc}")


# ============================================================
# EDIT HOSPITAL
# ============================================================

@st.dialog("Edit Hospital", width="medium")
def show_edit_hospital_dialog(hospital):

    st.markdown(
        "Update information for "
        f"**{safe(hospital.get('hospital_name') or 'this hospital')}**."
    )

    original_address = hospital.get("address") or ""

    hospital_name = st.text_input(
        "Hospital Name",
        value=hospital.get("hospital_name") or "",
    )

    hospital_code = st.text_input(
        "Hospital Code",
        value=hospital.get("hospital_code") or "",
    )

    address = st.text_area(
        "Address",
        value=original_address,
    )

    col1, col2 = st.columns(2)

    with col1:
        contact_number = st.text_input(
            "Contact Number",
            value=hospital.get("contact_number") or "",
        )

    with col2:
        email = st.text_input(
            "Email",
            value=hospital.get("email") or "",
        )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        save = st.button(
            "Save Changes",
            icon=":material/save:",
            type="primary",
            width="stretch",
        )

    with col2:
        cancel = st.button("Cancel", width="stretch")

    if cancel:
        _close_dialog()
        _safe_rerun()
        return

    if not save:
        return

    if not hospital_name.strip():
        st.error("Hospital name is required.")
        return

    if not address.strip():
        st.error("Address is required.")
        return

    try:

        update_hospital(
            hospital_id=hospital["hospital_id"],
            hospital_name=hospital_name.strip(),
            hospital_code=(
                hospital_code.strip() or None
            ),
            address=address.strip(),
            contact_number=(
                contact_number.strip() or None
            ),
            email=(
                email.strip() or None
            ),
        )

        # ------------------------------------------------
        # AUTOMATIC GEOCODE ON ADDRESS CHANGE (Enhancement A)
        # ------------------------------------------------

        address_changed = (
            address.strip() != original_address.strip()
        )

        if address_changed:

            with st.spinner("Re-locating hospital on the map..."):

                _try_geocode_hospital(
                    hospital["hospital_id"],
                    address.strip(),
                    force=True,
                )

        st.session_state["sa_flash"] = (
            "Hospital updated successfully."
        )

        _close_dialog()

        try:
            st.cache_data.clear()
        except Exception:
            pass

        _safe_rerun()

    except Exception as exc:

        st.error(f"Failed to update hospital: {exc}")


# ============================================================
# DEACTIVATE HOSPITAL
# ============================================================

@st.dialog("Deactivate Hospital", width="small")
def show_deactivate_hospital_dialog(hospital):

    hospital_name = (
        hospital.get("hospital_name") or "this hospital"
    )

    st.warning(
        "Are you sure you want to deactivate "
        f"**{safe(hospital_name)}**?"
    )

    st.markdown(
        "The hospital will remain in the system, "
        "but its status will be set to **Inactive**."
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "Deactivate",
            icon=":material/block:",
            type="primary",
            width="stretch",
        ):

            try:

                deactivate_hospital(hospital["hospital_id"])

                st.session_state["sa_flash"] = (
                    "Hospital deactivated successfully."
                )

                _close_dialog()

                try:
                    st.cache_data.clear()
                except Exception:
                    pass

                _safe_rerun()

            except Exception as exc:

                st.error(
                    f"Failed to deactivate hospital: {exc}"
                )

    with col2:

        if st.button("Cancel", width="stretch"):

            _close_dialog()
            _safe_rerun()


# ============================================================
# REACTIVATE HOSPITAL
# ============================================================

@st.dialog("Reactivate Hospital", width="small")
def show_reactivate_hospital_dialog(hospital):

    hospital_name = (
        hospital.get("hospital_name") or "this hospital"
    )

    st.info(f"Reactivate **{safe(hospital_name)}**?")

    st.markdown(
        "The hospital will become active again "
        "and can be used normally."
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "Reactivate",
            icon=":material/check_circle:",
            type="primary",
            width="stretch",
        ):

            try:

                reactivate_hospital(hospital["hospital_id"])

                st.session_state["sa_flash"] = (
                    "Hospital reactivated successfully."
                )

                _close_dialog()

                try:
                    st.cache_data.clear()
                except Exception:
                    pass

                _safe_rerun()

            except Exception as exc:

                st.error(
                    f"Failed to reactivate hospital: {exc}"
                )

    with col2:

        if st.button("Cancel", width="stretch"):

            _close_dialog()
            _safe_rerun()


# ============================================================
# HOSPITAL STAFF DIALOG
# ============================================================

@st.dialog("Hospital Staff", width="large")
def show_hospital_staff_dialog(hospital):

    hospital_id = hospital.get("hospital_id")
    hospital_name = (
        hospital.get("hospital_name") or "Hospital"
    )

    header_col1, header_col2 = st.columns(
        [0.7, 5],
        vertical_alignment="center",
    )

    with header_col1:
        st.markdown(
            '<div class="mh-dialog-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16"/><path d="M9 21v-4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v4"/><path d="M10 9h4"/><path d="M12 7v4"/></svg></div>',
            unsafe_allow_html=True,
        )

    with header_col2:
        st.subheader(hospital_name)
        st.caption("Hospital staff and personnel")

    staff = _load_hospital_staff(hospital_id)

    active_staff = [
        member
        for member in staff
        if member.get("is_active", True)
    ]

    total_staff = len(staff)
    active_count = len(active_staff)
    inactive_count = total_staff - active_count

    metric_col1, metric_col2, metric_col3 = st.columns(3)

    with metric_col1:
        metric_card("Total Staff", total_staff, "groups", "blue")

    with metric_col2:
        metric_card("Active Staff", active_count, "person_check", "green")

    with metric_col3:
        metric_card("Inactive Staff", inactive_count, "person_off", "amber")

    section_title("Hospital Information")

    show_rows([
        ("Hospital Code", hospital.get("hospital_code") or "—"),
        ("Contact Number", hospital.get("contact_number") or "—"),
        ("Email", hospital.get("email") or "—"),
        ("Address", hospital.get("address") or "—"),
    ])

    section_title(
        "Currently Active Staff",
        "Only active staff members are shown here.",
    )

    if not active_staff:

        empty_state(
            "No active staff members are currently "
            "assigned to this hospital."
        )

    else:

        _create_staff_table(active_staff)

    st.divider()

    if st.button(
        "Back",
        key=f"back_hospital_staff_{hospital_id}",
        icon=":material/arrow_back:",
        width="stretch",
    ):
        _close_dialog()
        _safe_rerun()


def _create_staff_table(staff):

    widths = [3.2, 2.3, 1.8, 1.2, 1.4]

    with st.container(key="sa_table_hospital_staff"):

        table_header(
            ["Staff Member", "Role", "Employee ID", "Status", "Action"],
            widths,
            "hospital_staff",
        )

        for member in staff:

            user_id = member.get("user_id")

            name = full_name(
                member.get("user_fname"),
                member.get("user_mname"),
                member.get("user_lname"),
            )

            role = _get_role_name(member)
            employee_id = member.get("employee_id") or "—"
            is_active = member.get("is_active", True)

            with table_row(f"staff_{user_id}", widths) as cols:

                name_cell(
                    cols[0],
                    name or "Unnamed User",
                    member.get("email")
                    or member.get("user_email")
                    or member.get("auth_email")
                    or "",
                )

                text_cell(cols[1], role, strong=True)
                text_cell(cols[2], employee_id, muted=True)

                pill_cell(
                    cols[3],
                    "Active" if is_active else "Inactive",
                    "green" if is_active else "red",
                )

                with cols[4]:

                    if st.button(
                        "View",
                        key=f"view_staff_member_{user_id}",
                        icon=":material/person:",
                        width="stretch",
                    ):

                        st.session_state[DIALOG_KEY] = "staff_profile"
                        st.session_state[SELECTED_STAFF_KEY] = user_id
                        _safe_rerun()


# ============================================================
# STAFF PROFILE DIALOG
# ============================================================

@st.dialog("Staff Profile", width="large")
def show_staff_member_dialog(user_id):

    member = _load_staff_member(user_id)

    if not member:

        st.error("Unable to load this staff member.")

        if st.button(
            "Back",
            key=f"back_missing_staff_{user_id}",
            icon=":material/arrow_back:",
            width="stretch",
        ):
            _back_to_hospital_staff()
            _safe_rerun()

        return

    name = full_name(
        member.get("user_fname"),
        member.get("user_mname"),
        member.get("user_lname"),
    )

    role = _get_role_name(member)

    email = (
        member.get("email")
        or member.get("user_email")
        or member.get("auth_email")
        or "—"
    )

    last_login = member.get("last_login")

    profile_picture_url = (
        member.get("profile_picture_url")
        or member.get("profile_picture")
        or member.get("avatar_url")
    )

    if not profile_picture_url:
        try:
            profile_picture_url = get_profile_picture_url(user_id)
        except Exception:
            profile_picture_url = None

    avatar_col, info_col = st.columns(
        [1, 4],
        vertical_alignment="center",
    )

    with avatar_col:

        if profile_picture_url:

            st.image(profile_picture_url, width=110)

        else:

            st.markdown(f'<div class="mh-profile-avatar">{safe(_initials_for_profile(name))}</div>', unsafe_allow_html=True)

    with info_col:

        st.subheader(name or "Unnamed User")
        st.caption(role)

        is_active = member.get("is_active", True)

        pill_cell(
            st,
            "Active" if is_active else "Inactive",
            "green" if is_active else "red",
        )

    section_title("Account Information")

    show_rows([
        ("Email", email),
        ("Employee ID", member.get("employee_id") or "—"),
        ("Role", role),
        ("Last Login", format_date(last_login, with_time=True)),
        ("Created", format_date(member.get("created_at"), with_time=True)),
        ("Last Updated", format_date(member.get("updated_at"), with_time=True)),
    ])

    section_title("Personal Information")

    show_rows([
        ("First Name", member.get("user_fname") or "—"),
        ("Middle Name", member.get("user_mname") or "—"),
        ("Last Name", member.get("user_lname") or "—"),
        ("Birth Date", format_date(member.get("user_birthdate"))),
        ("Sex", member.get("user_sex") or "—"),
        ("Contact Number", member.get("user_contact_number") or "—"),
        ("Address", member.get("user_address") or "—"),
    ])

    section_title("Work Information")

    show_rows([
        ("Hospital", _get_hospital_name(member)),
    ])

    st.divider()

    if st.button(
        "Back to Hospital Staff",
        key=f"back_to_hospital_staff_{user_id}",
        icon=":material/arrow_back:",
        width="stretch",
    ):
        _back_to_hospital_staff()
        _safe_rerun()