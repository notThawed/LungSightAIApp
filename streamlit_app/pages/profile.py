import streamlit as st

from pathlib import Path
from datetime import date

from backend.backend_utils.profile_utils import (
    get_role_permissions,
    account_status_label,
    update_personal_information,
    remove_profile_picture,
    get_user_preferences,
    update_user_preferences,
    DATE_FORMAT_OPTIONS,
    TIME_FORMAT_OPTIONS,
    change_password,
    get_last_login,
)

from backend.backend_utils.hospital_utils import (
    get_user_profile_by_id,
    get_hospital_by_id,
    update_hospital_information,
    update_hospital_logo_url,
    update_profile_picture_url,
)

from backend.backend_utils.storage_utils import (
    upload_hospital_logo,
    upload_profile_picture,
    delete_profile_picture,
)

from streamlit_app.components.ui import format_date


# ============================================================
# CSS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROFILE_CSS_PATH = (
    PROJECT_ROOT
    / "shared"
    / "theme"
    / "css_content"
    / "profile.css"
)


def load_profile_css():
    """
    Load Profile Settings page-specific CSS.
    """

    if not PROFILE_CSS_PATH.exists():
        return

    css = PROFILE_CSS_PATH.read_text(
        encoding="utf-8"
    )

    st.markdown(
        f"<style>{css}</style>",
        unsafe_allow_html=True,
    )


# ============================================================
# CONSTANTS
# ============================================================

SEX_OPTIONS = [
    "Male",
    "Female",
    "Prefer not to say",
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
    """
    Safely display a value.
    """

    if value is None:
        return "—"

    value = str(value).strip()

    return value if value else "—"


def full_name_of(person):
    """
    Build a user's complete name.
    """

    parts = [
        person.get("first_name"),
        person.get("middle_name"),
        person.get("last_name"),
    ]

    parts = [
        part.strip()
        for part in parts
        if part and str(part).strip()
    ]

    return " ".join(parts) or "—"


def get_initials(name):
    """
    Generate profile initials.
    """

    words = [
        word
        for word in str(name).split()
        if word
    ]

    if not words:
        return "U"

    if len(words) == 1:
        return words[0][0].upper()

    return (
        words[0][0]
        + words[-1][0]
    ).upper()


def rows_html(rows):
    """
    Render compact label/value rows.
    """

    items = ""

    for label, value in rows:

        items += (
            "<div class='ls-row'>"
            f"<span>{label}</span>"
            f"<b>{safe(value)}</b>"
            "</div>"
        )

    return (
        "<div class='ls-rows'>"
        f"{items}"
        "</div>"
    )


def status_badge(status):
    """
    Render account status badge.
    """

    label = account_status_label(status)

    modifier = str(
        status or "inactive"
    ).lower()

    if modifier not in (
        "active",
        "inactive",
        "suspended",
        "pending",
    ):
        modifier = "inactive"

    return (
        f"<span class='ls-badge ls-badge-{modifier}'>"
        f"{label}"
        "</span>"
    )


def section_header(
    icon,
    title,
    caption=None,
):
    """
    Render a profile section heading.
    """

    caption_html = ""

    if caption:

        caption_html = (
            f"<p class='ls-section-caption'>"
            f"{caption}"
            "</p>"
        )

    st.markdown(
        "<div class='ls-section-header'>"
        f"<span class='ls-section-icon material-symbols-rounded'>"
        f"{icon}"
        "</span>"
        f"<span class='ls-section-title'>"
        f"{title}"
        "</span>"
        "</div>"
        f"{caption_html}",
        unsafe_allow_html=True,
    )


def note(text):
    """
    Render a compact informational note.
    """

    st.markdown(
        f"<div class='ls-note'>{text}</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# CURRENT USER
# ============================================================

def get_current_user():
    return st.session_state.get(
        "user"
    ) or {}


def refresh_current_user():

    user = get_current_user()

    user_id = user.get(
        "user_id"
    )

    if not user_id:
        return user

    profile = get_user_profile_by_id(
        user_id
    )

    if not profile:
        return user

    updated_user = {
        **user,
        **profile,
    }

    # --------------------------------------------------------
    # Personal information
    # --------------------------------------------------------

    updated_user["first_name"] = (
        profile.get("user_fname")
        or ""
    )

    updated_user["middle_name"] = (
        profile.get("user_mname")
        or ""
    )

    updated_user["last_name"] = (
        profile.get("user_lname")
        or ""
    )

    updated_user["birthdate"] = (
        profile.get("user_birthdate")
    )

    updated_user["sex"] = (
        profile.get("user_sex")
    )

    updated_user["contact_number"] = (
        profile.get(
            "user_contact_number"
        )
        or ""
    )

    updated_user["address"] = (
        profile.get(
            "user_address"
        )
        or ""
    )

    # --------------------------------------------------------
    # Profile picture
    # --------------------------------------------------------

    updated_user["profile_picture_url"] = (
        profile.get(
            "profile_picture_url"
        )
    )

    # --------------------------------------------------------
    # Account status
    # --------------------------------------------------------

    if profile.get("is_active") is True:
        updated_user["account_status"] = (
            "active"
        )
    else:
        updated_user["account_status"] = (
            "inactive"
        )

    # --------------------------------------------------------
    # Last login
    # --------------------------------------------------------

    updated_user["last_login"] = (
        profile.get("last_login")
    )

    # --------------------------------------------------------
    # Save refreshed user
    # --------------------------------------------------------

    st.session_state.user = (
        updated_user
    )

    return updated_user


def get_current_hospital(user):

    hospital_id = user.get(
        "hospital_id"
    )

    if not hospital_id:
        return None

    return get_hospital_by_id(
        hospital_id
    )


# ============================================================
# PROFILE HEADER
# ============================================================

def render_profile_header(
    user,
    permissions,
):
    """
    Professional profile overview header.

    The actual upload controls remain inside the
    Profile Picture section below.
    """

    with st.container(
        key="profile_identity"
    ):

        current_picture = (
            user.get(
                "profile_picture_url"
            )
            or user.get(
                "profile_picture"
            )
            or user.get(
                "avatar_url"
            )
        )

        profile_col, info_col = st.columns(
            [1, 3],
            gap="large",
            vertical_alignment="center",
        )

        with profile_col:

            if current_picture:

                st.image(
                    current_picture,
                    width=150,
                )

            else:

                initials = get_initials(
                    full_name_of(user)
                )

                st.markdown(
                    f"""
                    <div class="ls-profile-avatar">
                        {initials}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with info_col:

            st.markdown(
                f"""
                <div class="ls-profile-name">
                    {safe(full_name_of(user))}
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(
                f"""
                <div class="ls-profile-role">
                    {safe(user.get("role"))}
                </div>
                """,
                unsafe_allow_html=True,
            )

            status = status_badge(
                user.get(
                    "account_status"
                )
            )

            st.markdown(
                f"""
                <div class="ls-profile-status">
                    {status}
                </div>
                """,
                unsafe_allow_html=True,
            )

            hospital_name = (
                user.get(
                    "hospital_name"
                )
            )

            if hospital_name:

                st.markdown(
                    f"""
                    <div class="ls-profile-hospital">
                        <span class="material-symbols-rounded">
                            local_hospital
                        </span>
                        {safe(hospital_name)}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# ============================================================
# PROFILE PICTURE
# ============================================================

def render_profile_picture_section(
    user,
    permissions,
):

    with st.container(
        key="profile_section_picture"
    ):

        section_header(
            "account_circle",
            "Profile Picture",
            "Use a clear photo to help identify your account.",
        )

        current_picture = (
            user.get(
                "profile_picture_url"
            )
            or user.get(
                "profile_picture"
            )
            or user.get(
                "avatar_url"
            )
        )

        avatar_col, action_col = st.columns(
            [1, 2.5],
            gap="large",
            vertical_alignment="center",
        )

        with avatar_col:

            if current_picture:

                st.image(
                    current_picture,
                    width=130,
                )

            else:

                initials = get_initials(
                    full_name_of(user)
                )

                st.markdown(
                    f"""
                    <div class="ls-large-avatar">
                        {initials}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with action_col:

            if not permissions[
                "edit_profile_picture"
            ]:

                st.caption(
                    "Only the account owner can "
                    "change this picture."
                )

                return

            new_picture = st.file_uploader(
                "Upload a new picture",
                type=[
                    "png",
                    "jpg",
                    "jpeg",
                    "webp",
                ],
                help=(
                    "Maximum file size: 5 MB."
                ),
                key="profile_picture_upload",
            )

            upload_col, remove_col = st.columns(
                2,
                gap="small",
            )

            with upload_col:

                upload_clicked = st.button(
                    "Save Picture",
                    key="profile_save_picture",
                    type="primary",
                    width="stretch",
                    disabled=not new_picture,
                )

            with remove_col:

                remove_clicked = st.button(
                    "Remove",
                    key="profile_remove_picture_btn",
                    width="stretch",
                    disabled=not current_picture,
                )

        # ----------------------------------------------------
        # Upload
        # ----------------------------------------------------

        if (
            permissions[
                "edit_profile_picture"
            ]
            and new_picture
            and upload_clicked
        ):

            user_id = user.get(
                "user_id"
            )

            upload_result = (
                upload_profile_picture(
                    user_id=user_id,
                    file_bytes=new_picture.getvalue(),
                    file_name=new_picture.name,
                )
            )

            if not upload_result[
                "success"
            ]:

                st.error(
                    "Unable to upload picture: "
                    f"{upload_result['message']}"
                )

                return

            picture_url = (
                upload_result.get(
                    "url"
                )
            )

            if not picture_url:

                st.error(
                    "Picture was uploaded, but "
                    "no public URL was returned."
                )

                return

            save_result = (
                update_profile_picture_url(
                    user_id=user_id,
                    profile_picture_url=picture_url,
                )
            )

            if not save_result[
                "success"
            ]:

                st.error(
                    "Unable to save picture URL: "
                    f"{save_result['message']}"
                )

                return

            refresh_current_user()

            st.success(
                "Profile picture updated."
            )

            st.rerun()

        # ----------------------------------------------------
        # Remove
        # ----------------------------------------------------

        if (
            permissions[
                "edit_profile_picture"
            ]
            and current_picture
            and remove_clicked
        ):

            user_id = user.get(
                "user_id"
            )

            storage_result = (
                delete_profile_picture(
                    user_id
                )
            )

            if not storage_result[
                "success"
            ]:

                st.error(
                    "Unable to remove profile picture: "
                    f"{storage_result['message']}"
                )

                return

            database_result = (
                remove_profile_picture(
                    user_id
                )
            )

            if not database_result[
                "success"
            ]:

                st.error(
                    "The image was removed from "
                    "storage, but the profile record "
                    f"could not be cleared: "
                    f"{database_result['message']}"
                )

                return

            refresh_current_user()

            st.success(
                "Profile picture removed."
            )

            st.rerun()


# ============================================================
# PERSONAL INFORMATION
# ============================================================

def render_personal_information_section(
    user,
    permissions,
):

    with st.container(
        key="profile_section_personal"
    ):

        section_header(
            "badge",
            "Personal Information",
            "Your personal details used throughout LungSight.",
        )

        if not permissions[
            "edit_personal_info"
        ]:

            st.markdown(
                rows_html([
                    (
                        "First name",
                        user.get(
                            "first_name"
                        ),
                    ),
                    (
                        "Middle name",
                        user.get(
                            "middle_name"
                        ),
                    ),
                    (
                        "Last name",
                        user.get(
                            "last_name"
                        ),
                    ),
                    (
                        "Birthdate",
                        format_date(
                            user.get(
                                "birthdate"
                            )
                        ),
                    ),
                    (
                        "Sex",
                        user.get(
                            "sex"
                        ),
                    ),
                    (
                        "Contact number",
                        user.get(
                            "contact_number"
                        ),
                    ),
                    (
                        "Address",
                        user.get(
                            "address"
                        ),
                    ),
                ]),
                unsafe_allow_html=True,
            )

            return

        with st.form(
            "profile_personal_info_form"
        ):

            first_col, middle_col, last_col = (
                st.columns(3)
            )

            with first_col:

                first_name = st.text_input(
                    "First name *",
                    value=user.get(
                        "first_name",
                        "",
                    ),
                )

            with middle_col:

                middle_name = st.text_input(
                    "Middle name",
                    value=user.get(
                        "middle_name",
                        "",
                    ),
                )

            with last_col:

                last_name = st.text_input(
                    "Last name *",
                    value=user.get(
                        "last_name",
                        "",
                    ),
                )

            birth_col, sex_col = st.columns(
                2
            )

            current_birthdate = (
                user.get(
                    "birthdate"
                )
            )

            birth_value = None

            if current_birthdate:

                try:

                    if isinstance(
                        current_birthdate,
                        date,
                    ):

                        birth_value = (
                            current_birthdate
                        )

                    else:

                        birth_value = date.fromisoformat(
                            str(
                                current_birthdate
                            )[:10]
                        )

                except (
                    ValueError,
                    TypeError,
                ):

                    birth_value = None

            with birth_col:

                birthdate = st.date_input(
                    "Birthdate",
                    value=birth_value,
                    min_value=date(
                        1900,
                        1,
                        1,
                    ),
                    max_value=date.today(),
                )

            current_sex = user.get(
                "sex"
            )

            sex_index = (
                SEX_OPTIONS.index(
                    current_sex
                )
                if current_sex in SEX_OPTIONS
                else 0
            )

            with sex_col:

                sex = st.selectbox(
                    "Sex",
                    SEX_OPTIONS,
                    index=sex_index,
                )

            contact_number = st.text_input(
                "Contact number",
                value=(
                    user.get(
                        "contact_number"
                    )
                    or ""
                ),
            )

            address = st.text_area(
                "Address",
                value=(
                    user.get(
                        "address"
                    )
                    or ""
                ),
                height=90,
            )

            submitted = (
                st.form_submit_button(
                    "Save Changes",
                    type="primary",
                    width="stretch",
                )
            )

        if not submitted:
            return

        result = (
            update_personal_information(
                user_id=user.get(
                    "user_id"
                ),
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name,
                birthdate=birthdate,
                sex=sex,
                contact_number=contact_number,
                address=address,
            )
        )

        if result["success"]:

            refresh_current_user()

            st.success(
                result["message"]
            )

            st.rerun()

        else:

            st.error(
                result["message"]
            )


# ============================================================
# ACCOUNT INFORMATION
# ============================================================

def render_account_information_section(
    user,
):

    with st.container(
        key="profile_section_account"
    ):

        section_header(
            "shield_person",
            "Account Information",
        )

        st.markdown(
            rows_html([
                (
                    "Email",
                    user.get("email"),
                ),
                (
                    "Employee ID",
                    user.get(
                        "employee_id"
                    ),
                ),
                (
                    "Role",
                    user.get("role"),
                ),
                (
                    "Hospital",
                    user.get(
                        "hospital_name"
                    ),
                ),
            ]),
            unsafe_allow_html=True,
        )

        st.markdown(
            (
                "<div class='ls-row'>"
                "<span>Account status</span>"
                f"<b>{status_badge(user.get('account_status'))}</b>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


# ============================================================
# HOSPITAL INFORMATION
# ============================================================

def render_hospital_information_section(
    hospital,
    permissions,
):

    if (
        not permissions[
            "show_hospital_info"
        ]
        or not hospital
    ):
        return

    with st.container(
        key="profile_section_hospital"
    ):

        section_header(
            "local_hospital",
            "Hospital Information",
            "Hospital details associated with your account.",
        )

        current_logo_url = (
            hospital.get(
                "hospital_logo_url"
            )
        )

        if not permissions[
            "edit_hospital_info"
        ]:

            logo_col, info_col = st.columns(
                [1, 3],
                gap="large",
                vertical_alignment="center",
            )

            with logo_col:

                if current_logo_url:

                    st.image(
                        current_logo_url,
                        width=120,
                    )

                else:

                    st.markdown(
                        """
                        <div class="ls-hospital-logo-placeholder">
                            <span class="material-symbols-rounded">
                                local_hospital
                            </span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            with info_col:

                st.markdown(
                    rows_html([
                        (
                            "Hospital name",
                            hospital.get(
                                "hospital_name"
                            ),
                        ),
                        (
                            "Hospital type",
                            hospital.get(
                                "hospital_type"
                            ),
                        ),
                        (
                            "Address",
                            hospital.get(
                                "address"
                            ),
                        ),
                        (
                            "Contact number",
                            hospital.get(
                                "contact_number"
                            ),
                        ),
                        (
                            "Email",
                            hospital.get(
                                "email"
                            ),
                        ),
                        (
                            "Website",
                            hospital.get(
                                "website"
                            ),
                        ),
                    ]),
                    unsafe_allow_html=True,
                )

            return

        logo_col, form_col = st.columns(
            [1, 3],
            gap="large",
            vertical_alignment="top",
        )

        with logo_col:

            if current_logo_url:

                st.image(
                    current_logo_url,
                    width=120,
                )

            else:

                st.markdown(
                    """
                    <div class="ls-hospital-logo-placeholder">
                        <span class="material-symbols-rounded">
                            local_hospital
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            hospital_logo = st.file_uploader(
                "Update logo",
                type=[
                    "png",
                    "jpg",
                    "jpeg",
                    "webp",
                ],
                help=(
                    "Maximum file size: 5 MB."
                ),
                key="profile_hospital_logo",
            )

        with form_col:

            with st.form(
                "profile_hospital_info_form"
            ):

                hospital_name = st.text_input(
                    "Hospital name *",
                    value=(
                        hospital.get(
                            "hospital_name",
                            "",
                        )
                    ),
                )

                type_col, contact_col = (
                    st.columns(2)
                )

                current_type = hospital.get(
                    "hospital_type"
                )

                if current_type not in HOSPITAL_TYPES:

                    current_type = (
                        HOSPITAL_TYPES[0]
                    )

                with type_col:

                    hospital_type = (
                        st.selectbox(
                            "Hospital type",
                            HOSPITAL_TYPES,
                            index=HOSPITAL_TYPES.index(
                                current_type
                            ),
                        )
                    )

                with contact_col:

                    contact_number = st.text_input(
                        "Contact number",
                        value=(
                            hospital.get(
                                "contact_number"
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
                    height=80,
                )

                email_col, website_col = (
                    st.columns(2)
                )

                with email_col:

                    email = st.text_input(
                        "Hospital email",
                        value=(
                            hospital.get(
                                "email"
                            )
                            or ""
                        ),
                    )

                with website_col:

                    website = st.text_input(
                        "Website",
                        value=(
                            hospital.get(
                                "website"
                            )
                            or ""
                        ),
                    )

                submitted = (
                    st.form_submit_button(
                        "Save Hospital Info",
                        type="primary",
                        width="stretch",
                    )
                )

        if not submitted:
            return

        if not hospital_name.strip():

            st.error(
                "Hospital name is required."
            )

            return

        hospital_id = hospital.get(
            "hospital_id"
        )

        result = (
            update_hospital_information(
                hospital_id=hospital_id,
                hospital_name=hospital_name,
                hospital_type=hospital_type,
                address=address,
                contact_number=contact_number,
                email=email,
                website=website,
            )
        )

        if not result["success"]:

            st.error(
                result["message"]
            )

            return

        if hospital_logo:

            upload_result = (
                upload_hospital_logo(
                    hospital_id=hospital_id,
                    file_bytes=hospital_logo.getvalue(),
                    file_name=hospital_logo.name,
                )
            )

            if not upload_result[
                "success"
            ]:

                st.error(
                    "Hospital information saved, "
                    "but the logo could not be uploaded: "
                    f"{upload_result['message']}"
                )

                return

            logo_url = (
                upload_result.get(
                    "url"
                )
            )

            if logo_url:

                logo_result = (
                    update_hospital_logo_url(
                        hospital_id=hospital_id,
                        logo_url=logo_url,
                    )
                )

                if not logo_result[
                    "success"
                ]:

                    st.error(
                        "Logo uploaded, but its URL "
                        "could not be saved: "
                        f"{logo_result['message']}"
                    )

                    return

        st.success(
            "Hospital information updated."
        )

        st.rerun()


# ============================================================
# PREFERENCES
# ============================================================

def render_preferences_section(
    user,
    permissions,
):

    if not permissions[
        "edit_preferences"
    ]:
        return

    with st.container(
        key="profile_section_preferences"
    ):

        section_header(
            "tune",
            "System Preferences",
        )

        prefs = get_user_preferences(
            user.get("user_id")
        )

        notifications_enabled = st.toggle(
            "Enable notifications",
            value=prefs[
                "notifications_enabled"
            ],
        )

        date_col, time_col = st.columns(
            2
        )

        with date_col:

            date_format = st.selectbox(
                "Date format",
                DATE_FORMAT_OPTIONS,
                index=DATE_FORMAT_OPTIONS.index(
                    prefs["date_format"]
                ),
            )

        with time_col:

            time_format = st.selectbox(
                "Time format",
                TIME_FORMAT_OPTIONS,
                index=TIME_FORMAT_OPTIONS.index(
                    prefs["time_format"]
                ),
            )

        if permissions[
            "edit_system_settings"
        ]:

            note(
                "System-wide settings are available "
                "under System Settings in the sidebar."
            )

        if st.button(
            "Save Preferences",
            key="profile_save_preferences",
            type="primary",
            width="stretch",
        ):

            result = (
                update_user_preferences(
                    user_id=user.get(
                        "user_id"
                    ),
                    notifications_enabled=(
                        notifications_enabled
                    ),
                    date_format=date_format,
                    time_format=time_format,
                )
            )

            if result["success"]:

                st.success(
                    result["message"]
                )

            else:

                st.error(
                    result["message"]
                )


# ============================================================
# SECURITY
# ============================================================

def render_security_section(
    user,
    permissions,
):

    with st.container(
        key="profile_section_security"
    ):

        section_header(
            "lock",
            "Security",
            "Manage your password and account security.",
        )

        last_login = get_last_login(
            user.get("user_id")
        )

        st.markdown(
            rows_html([
                (
                    "Last login",
                    format_date(
                        last_login,
                        with_time=True,
                    ),
                ),
            ]),
            unsafe_allow_html=True,
        )

        if not permissions[
            "edit_password"
        ]:
            return

        st.markdown(
            "<div class='ls-security-title'>"
            "Change Password"
            "</div>",
            unsafe_allow_html=True,
        )

        with st.form(
            "profile_change_password_form"
        ):

            new_password = st.text_input(
                "New password",
                type="password",
            )

            confirm_password = st.text_input(
                "Confirm new password",
                type="password",
            )

            submitted = (
                st.form_submit_button(
                    "Update Password",
                    type="primary",
                    width="stretch",
                )
            )

        if not submitted:
            return

        result = change_password(
            user_id=user.get(
                "user_id"
            ),
            new_password=new_password,
            confirm_password=confirm_password,
        )

        if result["success"]:

            st.success(
                result["message"]
            )

        else:

            st.error(
                result["message"]
            )


# ============================================================
# MAIN PAGE
# ============================================================

def show():

    load_profile_css()

    user = refresh_current_user()

    if (
        not user
        or not user.get("user_id")
    ):

        st.error(
            "Your profile could not be loaded."
        )

        return

    role = user.get(
        "role"
    )

    permissions = get_role_permissions(
        role
    )

    hospital = (
        get_current_hospital(user)
        if permissions[
            "show_hospital_info"
        ]
        else None
    )

    if hospital:

        user["hospital_name"] = (
            hospital.get(
                "hospital_name"
            )
        )

    with st.container(
        key="profile_page"
    ):

        # ----------------------------------------------------
        # Page heading
        # ----------------------------------------------------

        st.markdown(
            """
            <div class="ls-profile-heading">
                <div class="ls-profile-heading-title">
                    Profile Settings
                </div>
                <div class="ls-profile-heading-caption">
                    Manage your personal information,
                    account security, and preferences.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------
        # Identity card
        # ----------------------------------------------------

        render_profile_header(
            user,
            permissions,
        )

        # ----------------------------------------------------
        # Main profile sections
        # ----------------------------------------------------

        render_profile_picture_section(
            user,
            permissions,
        )

        render_personal_information_section(
            user,
            permissions,
        )

        render_account_information_section(
            user,
        )

        render_hospital_information_section(
            hospital,
            permissions,
        )

        render_preferences_section(
            user,
            permissions,
        )

        render_security_section(
            user,
            permissions,
        )