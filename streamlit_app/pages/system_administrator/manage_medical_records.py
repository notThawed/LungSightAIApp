# streamlit_app/pages/system_administrator/manage_medical_records.py

"""
Manage Medical Records (3-level navigation for System Administrator).

Level 0: Patient Records List — search, filter, patient table with pagination
Level 1: Patient Overview     — 3 category cards (General, Follow-up, External)
Level 2: Category List        — examinations in category / external records
Level 3: Examination Report   — full diagnostic report with X-ray, AI heatmap, and printing

Role permissions:
    Superadmin          -> view all, heatmap, add external record
    Radiologist         -> view all, heatmap
    Radiologic Tech     -> view all
    Hospital Admin      -> view all, heatmap, add external record
    Staff               -> view all, add external record
"""

import streamlit as st
import streamlit.components.v1 as components

from datetime import datetime, date
from zoneinfo import ZoneInfo

from backend.fetches import (
    get_all_patients,
    get_examinations_by_patient,
    get_medical_records_by_patient,
    get_xray_request_by_examination,
    get_xray_images_by_request,
    get_xray_image_url,
    get_xray_ai_result,
    get_xray_ai_heatmap,
    get_all_hospitals,
    get_hospital_staff_member,
    get_medical_record_images,
    get_medical_record_file_url,
)

from backend.crud import (
    create_medical_record,
    upload_medical_record_file,
)

from streamlit_app.components.ui import (
    page_header,
    empty_state,
    section_title,
    show_rows,
    full_name,
    format_date,
    table_header,
    table_row,
    text_cell,
    pill_cell,
    pill,
    remember,
    show_flash_message,
    metric_card,
)

from shared.assets import load_css


# ============================================================
# CONFIG
# ============================================================

ROLE_SUPERADMIN = 1
ROLE_RADIOLOGIST = 3
ROLE_RADIOLOGIC_TECH = 4
ROLE_HOSPITAL_ADMIN = 6
ROLE_STAFF = 7

ALLOWED_ROLES = [
    ROLE_SUPERADMIN,
    ROLE_RADIOLOGIST,
    ROLE_RADIOLOGIC_TECH,
    ROLE_HOSPITAL_ADMIN,
    ROLE_STAFF,
]

HEATMAP_ROLES = [
    ROLE_SUPERADMIN,
    ROLE_RADIOLOGIST,
    ROLE_HOSPITAL_ADMIN,
]

ADD_RECORD_ROLES = [
    ROLE_SUPERADMIN,
    ROLE_HOSPITAL_ADMIN,
    ROLE_STAFF,
]

MANILA_TZ = ZoneInfo("Asia/Manila")

CATEGORY_GENERAL = "general"
CATEGORY_FOLLOWUP = "followup"
CATEGORY_EXTERNAL = "external"

WIDTHS = [
    1.2,  # Patient ID
    2.8,  # Patient Name + Demographics
    1.0,  # Sex
    1.6,  # Contact
    1.1,  # Action (View)
]

WIDTHS_SUPERADMIN = [
    1.7,  # Hospital
    1.1,  # Patient ID
    2.5,  # Patient Name + Demographics
    0.9,  # Sex
    1.5,  # Contact
    1.1,  # Action (View)
]

HEADERS = [
    "Patient ID",
    "Name",
    "Sex",
    "Contact",
    "Action",
]

HEADERS_SUPERADMIN = [
    "Hospital",
    "Patient ID",
    "Name",
    "Sex",
    "Contact",
    "Action",
]


# ============================================================
# SESSION KEYS
# ============================================================

KEY_PATIENT = "mmr_selected_patient"
KEY_CATEGORY = "mmr_selected_category"
KEY_EXAM = "mmr_selected_examination"
KEY_EXTERNAL = "mmr_external_record"
KEY_EXTERNAL_SHOWN = "mmr_external_displayed"
KEY_ADD_RECORD = "mmr_add_record_patient"


# ============================================================
# USER & PATIENT HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}


def current_role_id():
    return current_user().get("role_id")


def current_hospital_id():
    return current_user().get("hospital_id")


def can_view_heatmap():
    return current_role_id() in HEATMAP_ROLES


def can_add_record():
    return current_role_id() in ADD_RECORD_ROLES


def patient_name(patient):
    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )


def patient_code(patient):
    return patient.get("patient_code") or patient.get("patient_id") or "—"


def patient_initials(first_name, last_name):
    f = (first_name or "").strip()[:1].upper()
    l = (last_name or "").strip()[:1].upper()
    return f"{f}{l}" or "PT"


def calculate_age(dob):
    if not dob:
        return "—"
    try:
        if isinstance(dob, str):
            dob_parsed = date.fromisoformat(str(dob)[:10])
        elif isinstance(dob, date):
            dob_parsed = dob
        else:
            return "—"

        today = date.today()
        age = today.year - dob_parsed.year
        if (today.month, today.day) < (dob_parsed.month, dob_parsed.day):
            age -= 1
        return age
    except Exception:
        return "—"


def patient_hospital_name(patient):
    hospitals = patient.get("hospitals")
    if isinstance(hospitals, dict):
        return hospitals.get("hospital_name") or "—"
    if isinstance(hospitals, list) and hospitals:
        return hospitals[0].get("hospital_name") or "—"
    return "—"


# ============================================================
# DATE / TIME
# ============================================================

def parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=MANILA_TZ)
    return parsed.astimezone(MANILA_TZ)


def format_date_only(value):
    parsed = parse_datetime(value)
    if not parsed:
        return format_date(value) or "—"
    return parsed.strftime("%B %d, %Y")


def format_time_only(value):
    parsed = parse_datetime(value)
    if not parsed:
        return "—"
    return parsed.strftime("%I:%M %p")


# ============================================================
# RISK / CONFIDENCE
# ============================================================

def risk_from_ai_findings(ai_findings):
    if not ai_findings:
        return ("No AI Result", "slate")
    normalized = str(ai_findings).strip().lower()
    if normalized == "positive":
        return ("High Risk", "red")
    if normalized == "negative":
        return ("Low Risk", "green")
    return (str(ai_findings).title(), "slate")


def pneumonia_type_label(pneumonia_type):
    if pneumonia_type == "bacterial_pneumonia":
        return ("Bacterial Pneumonia", "red")
    if pneumonia_type == "viral_pneumonia":
        return ("Viral Pneumonia", "amber")
    return ("Not applicable", "slate")


def confidence_percent(value):
    if value is None:
        return None
    try:
        n = float(value)
        if n <= 1:
            n *= 100
        return round(n, 1)
    except (TypeError, ValueError):
        return None


# ============================================================
# EXAMINATION TYPE HELPERS
# ============================================================

def is_follow_up_examination(exam):
    sequence = exam.get("follow_up_sequence")
    if sequence is not None:
        try:
            if int(sequence) > 0:
                return True
        except (TypeError, ValueError):
            return True

    exam_type = exam.get("examination_type") or ""
    normalized = (
        str(exam_type)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )
    return "follow up" in normalized or "followup" in normalized


def split_examination_history(examinations):
    general = []
    follow_ups = []
    for exam in examinations:
        if is_follow_up_examination(exam):
            follow_ups.append(exam)
        else:
            general.append(exam)

    follow_ups.sort(
        key=lambda e: (
            e.get("follow_up_sequence") is None,
            e.get("follow_up_sequence") or 999999,
        )
    )
    return general, follow_ups


def display_exam_type(exam):
    if not is_follow_up_examination(exam):
        return exam.get("examination_type") or "General Consultation"
    seq = exam.get("follow_up_sequence")
    if seq is not None:
        try:
            return f"Follow-Up Examination {int(seq):03d}"
        except (TypeError, ValueError):
            pass
    return "Follow-Up Examination"


def exam_has_xray(exam):
    try:
        req = get_xray_request_by_examination(exam.get("examination_id"))
        if not req:
            return False
        imgs = get_xray_images_by_request(req.get("request_id")) or []
        return len(imgs) > 0
    except Exception:
        return False


# ============================================================
# NAVIGATION
# ============================================================

def go_to_patient_overview(patient):
    st.session_state[KEY_PATIENT] = patient
    st.session_state.pop(KEY_CATEGORY, None)
    st.session_state.pop(KEY_EXAM, None)
    st.rerun()


def go_to_category(patient, category):
    st.session_state[KEY_PATIENT] = patient
    st.session_state[KEY_CATEGORY] = category
    st.session_state.pop(KEY_EXAM, None)
    st.rerun()


def go_to_examination(exam):
    st.session_state[KEY_EXAM] = exam
    st.rerun()


def back_to_records_list():
    st.session_state.pop(KEY_PATIENT, None)
    st.session_state.pop(KEY_CATEGORY, None)
    st.session_state.pop(KEY_EXAM, None)
    st.rerun()


def back_to_patient_overview():
    st.session_state.pop(KEY_CATEGORY, None)
    st.session_state.pop(KEY_EXAM, None)
    st.rerun()


def back_to_category():
    st.session_state.pop(KEY_EXAM, None)
    st.rerun()


# ============================================================
# DATA LOADING
# ============================================================

def load_patient_rows(hospital_id=None):
    role_id = current_role_id()
    user_hospital_id = current_hospital_id()

    if role_id == ROLE_SUPERADMIN:
        filter_hospital = hospital_id
    else:
        filter_hospital = user_hospital_id

    try:
        patients = get_all_patients() or []
        if filter_hospital:
            patients = [p for p in patients if p.get("hospital_id") == filter_hospital]

        rows = []
        for p in patients:
            rows.append({
                "patient": p,
                "examination_date": p.get("created_at"),
                "ai_findings": None,
                "ai_confidence": None,
                "pneumonia_type": None,
            })
        return rows
    except Exception as error:
        st.error(f"Failed to load patient records: {error}")
        return []


# ============================================================
# UI COMPONENTS & CELLS
# ============================================================

def render_patient_hero(patient):
    fname = patient.get("first_name", "")
    lname = patient.get("last_name", "")
    full_n = patient_name(patient)
    code = patient_code(patient)
    p_sex = patient.get("sex") or "—"
    dob_fmt = format_date(patient.get("date_of_birth"))
    age_val = calculate_age(patient.get("date_of_birth"))
    contact = patient.get("contact_number") or "No contact"
    hospital = patient_hospital_name(patient)

    initials = patient_initials(fname, lname)
    avatar_class = "sa-dialog-avatar-female" if p_sex.lower() == "female" else "sa-dialog-avatar"

    st.markdown(
        f"""
        <div class="sa-dialog-hero">
            <div class="{avatar_class}">{initials}</div>
            <div class="sa-dialog-info">
                <div class="sa-dialog-name">{full_n}</div>
                <div class="sa-dialog-badges">
                    <span class="sa-code-badge">#{code}</span>
                    <span class="sa-chip">{p_sex}</span>
                    <span class="sa-chip">{age_val} yrs ({dob_fmt})</span>
                    <span class="sa-chip">{contact}</span>
                    <span class="sa-chip">{hospital}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def patient_code_cell(column, code):
    column.markdown(
        f"<div class='sa-code-cell'><span class='sa-code-badge'>#{code}</span></div>",
        unsafe_allow_html=True,
    )


def patient_name_cell(column, patient):
    fname = patient.get("first_name", "")
    lname = patient.get("last_name", "")
    full_n = patient_name(patient)
    initials = patient_initials(fname, lname)
    sex = (patient.get("sex") or "").lower()

    avatar_class = "sa-patient-avatar"
    if sex == "female":
        avatar_class += " sa-patient-avatar-female"
    elif sex == "male":
        avatar_class += " sa-patient-avatar-male"

    age_val = calculate_age(patient.get("date_of_birth"))
    sub_text = f"{age_val} yrs old" if age_val != "—" else ""
    civil = patient.get("civil_status")
    if civil:
        sub_text += f" &bull; {civil}" if sub_text else civil

    column.markdown(
        f"<div class='sa-patient-cell'>"
        f"  <div class='{avatar_class}'>{initials}</div>"
        f"  <div class='sa-patient-info'>"
        f"    <span class='sa-patient-name'>{full_n}</span>"
        f"    <span class='sa-patient-sub'>{sub_text}</span>"
        f"  </div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def patient_contact_cell(column, contact, emergency=None):
    if not contact and not emergency:
        column.markdown("<span style='color:var(--sa-slate);'>—</span>", unsafe_allow_html=True)
        return
    emg_html = (
        f"<span style='font-size:0.73rem; color:var(--sa-slate); margin-top:0.1rem; display:block;'>ICE: {emergency}</span>"
        if emergency
        else ""
    )
    column.markdown(
        f"<div style='display:flex; flex-direction:column;'>"
        f"  <span style='font-size:0.86rem; font-weight:500; color:var(--sa-ink);'>{contact or '—'}</span>"
        f"  {emg_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_table_pagination(current_page, total_pages, total_items, start_idx, end_idx):
    st.markdown("<div class='sa-pagination-bar'>", unsafe_allow_html=True)
    if total_pages > 1:
        col_prev, col_info, col_next = st.columns([1, 2.5, 1], vertical_alignment="center")

        with col_prev:
            if st.button(
                "Previous",
                icon=":material/chevron_left:",
                key="mmr_page_prev",
                disabled=(current_page <= 1),
                width="stretch",
            ):
                st.session_state["mmr_page"] = current_page - 1
                st.rerun()

        with col_info:
            st.markdown(
                f"<div class='sa-pagination-info'>"
                f"Showing <b>{start_idx + 1}–{end_idx}</b> of <b>{total_items}</b> &bull; Page <b>{current_page}</b> of <b>{total_pages}</b>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with col_next:
            if st.button(
                "Next",
                icon=":material/chevron_right:",
                key="mmr_page_next",
                disabled=(current_page >= total_pages),
                width="stretch",
            ):
                st.session_state["mmr_page"] = current_page + 1
                st.rerun()
    else:
        st.markdown(
            f"<div class='sa-pagination-info' style='text-align:center; padding: 0.5rem 0 0.8rem;'>"
            f"Showing all <b>{total_items}</b> records"
            f"</div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# LEVEL 0 — PATIENT RECORDS LIST
# ============================================================

def render_patient_list(rows):
    with st.container(key="manage_medical_records_page"):
        page_header(
            "Medical Records",
            "Review diagnostic examination archives, chest X-rays, and AI findings.",
        )

        role_id = current_role_id()
        hospitals = get_all_hospitals() or [] if role_id == ROLE_SUPERADMIN else []

        # ---------------- Overview Metrics ----------------
        patients_list = [r["patient"] for r in rows]
        total_p = len(patients_list)
        active_p = sum(1 for p in patients_list if (p.get("status") or "active").strip().lower() == "active")
        male_p = sum(1 for p in patients_list if (p.get("sex") or "").strip().lower() == "male")
        female_p = sum(1 for p in patients_list if (p.get("sex") or "").strip().lower() == "female")

        m_cols = st.columns(4)
        with m_cols[0]:
            metric_card("Total Patients", total_p, "groups", "teal")
        with m_cols[1]:
            metric_card("Active Patients", active_p, "verified", "green")
        with m_cols[2]:
            metric_card("Male Patients", male_p, "male", "blue")
        with m_cols[3]:
            metric_card("Female Patients", female_p, "female", "amber")

        st.write("")

        # ---------------- Filters Toolbar ----------------
        with st.container(key="sa_patient_filters"):
            if role_id == ROLE_SUPERADMIN and hospitals:
                hosp_col, search_col, sex_col, reset_col = st.columns(
                    [1.6, 2.8, 1.2, 0.9],
                    vertical_alignment="center",
                )

                hospital_names = ["All hospitals"] + sorted({
                    h.get("hospital_name") for h in hospitals if h.get("hospital_name")
                })

                hospital_filter = hosp_col.selectbox(
                    "Hospital",
                    hospital_names,
                    label_visibility="collapsed",
                    key="mmr_hospital_filter",
                )
            else:
                search_col, sex_col, reset_col = st.columns(
                    [3.5, 1.5, 1.0],
                    vertical_alignment="center",
                )
                hospital_filter = "All hospitals"

            search = search_col.text_input(
                "Search patient",
                placeholder="Search by patient ID, name, or contact number...",
                key="mmr_search",
                label_visibility="collapsed",
            ).strip().lower()

            sex = sex_col.selectbox(
                "Sex",
                ["All sexes", "Male", "Female"],
                label_visibility="collapsed",
                key="mmr_sex",
            )

            def _reset_filters():
                st.session_state["mmr_page"] = 1
                st.session_state["mmr_search"] = ""
                st.session_state["mmr_sex"] = "All sexes"
                if "mmr_hospital_filter" in st.session_state:
                    st.session_state["mmr_hospital_filter"] = "All hospitals"
                st.cache_data.clear()

            reset_col.button(
                "Reset",
                icon=":material/refresh:",
                width="stretch",
                key="mmr_refresh",
                on_click=_reset_filters,
                help="Reset filters and refresh list",
            )

        # Track filter changes to reset pagination to page 1
        curr_filter_key = (search, sex, hospital_filter)
        prev_filter_key = (
            st.session_state.get("_prev_mmr_search"),
            st.session_state.get("_prev_mmr_sex"),
            st.session_state.get("_prev_mmr_hosp"),
        )
        if prev_filter_key != curr_filter_key:
            st.session_state["mmr_page"] = 1
            st.session_state["_prev_mmr_search"] = search
            st.session_state["_prev_mmr_sex"] = sex
            st.session_state["_prev_mmr_hosp"] = hospital_filter

        # Reload rows if hospital filter changed (Superadmin)
        if role_id == ROLE_SUPERADMIN and hospital_filter != "All hospitals":
            selected_hospital_id = next(
                (h.get("hospital_id") for h in hospitals if h.get("hospital_name") == hospital_filter),
                None,
            )
            rows = load_patient_rows(hospital_id=selected_hospital_id)
        elif role_id == ROLE_SUPERADMIN:
            rows = load_patient_rows(hospital_id=None)

        # Apply Search & Sex Filters
        filtered = []
        for r in rows:
            p = r["patient"]
            text = f"{patient_name(p)} {patient_code(p)} {p.get('contact_number') or ''}".lower()

            if search and search not in text:
                continue
            if sex != "All sexes" and (p.get("sex") or "").strip().lower() != sex.lower():
                continue

            filtered.append(r)

        if not filtered:
            empty_state("No patient records found matching your search or filter criteria.")
            return

        # ---------------- Client-side Pagination ----------------
        PAGE_SIZE = 15
        total_items = len(filtered)
        total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)
        current_page = st.session_state.get("mmr_page", 1)
        if current_page > total_pages:
            current_page = total_pages
            st.session_state["mmr_page"] = current_page
        elif current_page < 1:
            current_page = 1
            st.session_state["mmr_page"] = current_page

        start_idx = (current_page - 1) * PAGE_SIZE
        end_idx = min(start_idx + PAGE_SIZE, total_items)
        page_rows = filtered[start_idx:end_idx]

        # Toolbar with patient count
        st.markdown(
            f"<div class='sa-table-toolbar'>"
            f"<div class='sa-table-count-badge'>"
            f"Showing <b>{start_idx + 1}–{end_idx}</b> of <b>{total_items}</b> patients"
            f"</div>"
            f"<span style='font-size:0.78rem; color:var(--sa-slate);'>Page {current_page} of {total_pages}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # ---------------- Patient Table ----------------
        is_sup = role_id == ROLE_SUPERADMIN

        with st.container(key="sa_table_mmr_patients"):
            table_header(
                HEADERS_SUPERADMIN if is_sup else HEADERS,
                WIDTHS_SUPERADMIN if is_sup else WIDTHS,
                "mmr_patients",
            )

            for row in page_rows:
                patient = row["patient"]
                patient_id = patient.get("patient_id")
                p_sex = patient.get("sex") or "—"
                tone = "blue" if p_sex.lower() == "male" else "pink"

                with table_row(
                    f"mmr_patients_{patient_id}",
                    WIDTHS_SUPERADMIN if is_sup else WIDTHS,
                ) as cols:
                    idx = 0
                    if is_sup:
                        text_cell(cols[idx], patient_hospital_name(patient), muted=True)
                        idx += 1

                    patient_code_cell(cols[idx], patient_code(patient))
                    idx += 1

                    patient_name_cell(cols[idx], patient)
                    idx += 1

                    pill_cell(cols[idx], p_sex, tone)
                    idx += 1

                    patient_contact_cell(cols[idx], patient.get("contact_number"), patient.get("emergency_contact_no"))
                    idx += 1

                    if cols[idx].button(
                        "View",
                        key=f"mmr_view_{patient_id}",
                        icon=":material/visibility:",
                        width="stretch",
                    ):
                        go_to_patient_overview(patient)

        # Bottom pagination
        render_table_pagination(current_page, total_pages, total_items, start_idx, end_idx)


# ============================================================
# LEVEL 1 — PATIENT OVERVIEW
# ============================================================

SVG_ICONS = {
    CATEGORY_GENERAL: """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
        <rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
        <path d="M9 12h6"/>
        <path d="M9 16h6"/>
    </svg>""",
    CATEGORY_FOLLOWUP: """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M8 2v4"/>
        <path d="M16 2v4"/>
        <rect width="18" height="18" x="3" y="4" rx="2"/>
        <path d="M3 10h18"/>
        <path d="M10 14h4v4"/>
        <path d="M14 14a3 3 0 1 0-3 3"/>
    </svg>""",
    CATEGORY_EXTERNAL: """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/>
        <circle cx="12" cy="13" r="2"/>
        <path d="M8 17a4 4 0 0 1 8 0"/>
    </svg>""",
}

def count_category_items(patient):
    patient_id = patient.get("patient_id")

    exams = get_examinations_by_patient(patient_id) or []
    valid_exams = [e for e in exams if (e.get("status") or "").lower() != "cancelled"]

    general, follow_ups = split_examination_history(valid_exams)
    records = get_medical_records_by_patient(patient_id) or []

    return {
        CATEGORY_GENERAL: len(general),
        CATEGORY_FOLLOWUP: len(follow_ups),
        CATEGORY_EXTERNAL: len(records),
    }


def render_category_card(
    patient,
    category,
    title,
    count,
    description,
    allow_add=False,
):
    svg_icon = SVG_ICONS.get(category, "")

    with st.container(key=f"mmr_cat_{category}"):
        st.markdown(
            f"""
            <div class='pr-cat-card'>
                <div class='pr-cat-icon'>
                    {svg_icon}
                </div>
                <h4 class='pr-cat-title'>{title}</h4>
                <div class='pr-cat-badge'>{count} record{'s' if count != 1 else ''}</div>
                <p class='pr-cat-desc'>{description}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if allow_add:
            if count > 0:
                v_col, a_col = st.columns(2, gap="small")
                with v_col:
                    if st.button(
                        "View",
                        key=f"mmr_cat_view_{category}",
                        icon=":material/visibility:",
                        type="primary",
                        width="stretch",
                    ):
                        go_to_category(patient, category)
                with a_col:
                    if st.button(
                        "Add",
                        key=f"mmr_cat_add_{category}",
                        icon=":material/add:",
                        type="secondary",
                        width="stretch",
                    ):
                        st.session_state[KEY_ADD_RECORD] = patient
                        st.rerun()
            else:
                if st.button(
                    "Add External Record",
                    key=f"mmr_cat_add_{category}",
                    icon=":material/add:",
                    type="primary",
                    width="stretch",
                ):
                    st.session_state[KEY_ADD_RECORD] = patient
                    st.rerun()
        else:
            if count > 0:
                if st.button(
                    "View Records",
                    key=f"mmr_cat_view_{category}",
                    icon=":material/arrow_forward:",
                    type="primary",
                    width="stretch",
                ):
                    go_to_category(patient, category)
            else:
                st.button(
                    "No Records Yet",
                    key=f"mmr_cat_view_{category}",
                    icon=":material/folder_off:",
                    disabled=True,
                    width="stretch",
                )


def render_patient_overview(patient):
    back_col, _ = st.columns([2, 5], vertical_alignment="center")
    with back_col:
        if st.button(
            "Back to Patient Records",
            key="mmr_back_to_list",
            icon=":material/arrow_back:",
        ):
            back_to_records_list()

    st.write("")

    # Sleek Hero Banner
    render_patient_hero(patient)

    st.markdown("<div class='sa-form-section-title' style='margin-top:1.5rem;'>Medical Record Archives</div>", unsafe_allow_html=True)

    counts = count_category_items(patient)

    col1, col2, col3 = st.columns(3, gap="medium", vertical_alignment="top")

    with col1:
        render_category_card(
            patient,
            CATEGORY_GENERAL,
            "General Consults",
            counts[CATEGORY_GENERAL],
            "Initial examinations, preliminary evaluations, and baseline diagnostic reports.",
        )

    with col2:
        render_category_card(
            patient,
            CATEGORY_FOLLOWUP,
            "Follow-Up Examinations",
            counts[CATEGORY_FOLLOWUP],
            "Scheduled reassessments, treatment follow-ups, and interval scan comparisons.",
        )

    with col3:
        render_category_card(
            patient,
            CATEGORY_EXTERNAL,
            "External Records",
            counts[CATEGORY_EXTERNAL],
            "Outside clinical histories, previous imaging from other hospitals, and laboratory reports.",
            allow_add=can_add_record(),
        )


# ============================================================
# LEVEL 2 — CATEGORY LIST
# ============================================================

def render_exam_list_card(exam):
    exam_id = exam.get("examination_id")
    exam_date = exam.get("examination_date") or exam.get("created_at")
    has_xray = exam_has_xray(exam)

    if has_xray:
        xray_icon = ":material/check_circle:"
        xray_text = "Available"
        xray_class = "pr-xray-available"
    else:
        xray_icon = ":material/warning:"
        xray_text = "No X-Ray"
        xray_class = "pr-xray-missing"

    chief = (exam.get("chief_complaint") or "—").strip()
    if len(chief) > 100:
        chief = chief[:100] + "…"

    diagnosis = (exam.get("diagnosis") or "—").strip()
    if len(diagnosis) > 100:
        diagnosis = diagnosis[:100] + "…"

    with st.container(key=f"mmr_exam_card_{exam_id}"):
        st.markdown(
            f"""
            <div class='pr-exam-card'>
                <div class='pr-exam-head'>
                    <span class='pr-exam-title'>{display_exam_type(exam)}</span>
                    <span class='pr-exam-date'>{format_date_only(exam_date)} &bull; {format_time_only(exam_date)}</span>
                </div>
                <div class='pr-exam-row'>
                    <span>Chief Complaint</span><b>{chief}</b>
                </div>
                <div class='pr-exam-row'>
                    <span>Diagnosis</span><b>{diagnosis}</b>
                </div>
                <div class='pr-exam-row'>
                    <span>Chest X-Ray</span>
                    <span class='{xray_class}'>{xray_text}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            "View Details & AI Analysis",
            key=f"mmr_exam_view_{exam_id}",
            icon=":material/arrow_forward:",
            type="primary",
            width="stretch",
        ):
            go_to_examination(exam)


def render_record_list_card(record):
    record_id = record.get("medical_record_id") or record.get("record_id")

    with st.container(key=f"mmr_rec_card_{record_id}"):
        st.markdown(
            f"""
            <div class='pr-exam-card'>
                <div class='pr-exam-head'>
                    <span class='pr-exam-title'>{record.get('record_type') or 'Medical Record'}</span>
                    <span class='pr-exam-date'>{format_date(record.get('record_date'))}</span>
                </div>
                <div class='pr-exam-row'>
                    <span>Facility / Hospital</span>
                    <b>{record.get('facility_name') or '—'}</b>
                </div>
                <div class='pr-exam-row'>
                    <span>Diagnosis</span>
                    <b>{record.get('diagnosis') or '—'}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            "View Medical Record",
            key=f"mmr_rec_view_{record_id}",
            icon=":material/visibility:",
            width="stretch",
        ):
            st.session_state[KEY_EXTERNAL] = record
            st.session_state.pop(KEY_EXTERNAL_SHOWN, None)
            st.rerun()


def render_category_list(patient, category):
    category_titles = {
        CATEGORY_GENERAL: "General Consults",
        CATEGORY_FOLLOWUP: "Follow-Up Examinations",
        CATEGORY_EXTERNAL: "External Records",
    }

    back_col, add_col = st.columns([3, 1.4], vertical_alignment="center")

    with back_col:
        if st.button(
            "Back to Patient Overview",
            key="mmr_back_to_overview",
            icon=":material/arrow_back:",
        ):
            back_to_patient_overview()

    with add_col:
        if category == CATEGORY_EXTERNAL and can_add_record():
            if st.button(
                "Add External Record",
                key="mmr_add_from_list",
                icon=":material/add:",
                type="primary",
                width="stretch",
            ):
                st.session_state[KEY_ADD_RECORD] = patient
                st.rerun()

    st.write("")

    # Hero Card
    render_patient_hero(patient)

    st.markdown(
        f"<div class='sa-form-section-title'>{category_titles.get(category, 'Records')} Archive</div>",
        unsafe_allow_html=True,
    )

    patient_id = patient.get("patient_id")

    if category in (CATEGORY_GENERAL, CATEGORY_FOLLOWUP):
        exams = get_examinations_by_patient(patient_id) or []
        valid_exams = [e for e in exams if (e.get("status") or "").lower() != "cancelled"]
        general, follow_ups = split_examination_history(valid_exams)

        items = general if category == CATEGORY_GENERAL else follow_ups

        if not items:
            empty_state(f"No {category_titles.get(category, 'records').lower()} found.")
            return

        for exam in items:
            render_exam_list_card(exam)
        return

    records = get_medical_records_by_patient(patient_id) or []

    if not records:
        empty_state("No external medical records found.")
        return

    for record in records:
        render_record_list_card(record)


# ============================================================
# LEVEL 3 — EXAMINATION REPORT
# ============================================================

def trigger_print_report(patient, exam, request, ai):
    hospitals = get_all_hospitals()
    hospital_id = patient.get("hospital_id")
    hospital = next((h for h in hospitals if h.get("hospital_id") == hospital_id), {})

    hospital_name = hospital.get("hospital_name", "LUNGSIGHT MEDICAL CENTER")
    hospital_logo = hospital.get("hospital_logo_url", "")
    hospital_address = hospital.get("address", "San Isidro, Talisay City, Cebu")
    hospital_contact = hospital.get("contact_number", "(032) 123-4567")
    hospital_email = hospital.get("email", "info@lungsight.com")

    doctor_name = "Attending Physician"
    reviewed_by = exam.get("reviewed_by")
    if reviewed_by:
        doctor = get_hospital_staff_member(reviewed_by)
        if doctor:
            doctor_name = f"Dr. {doctor.get('user_fname')} {doctor.get('user_lname')}"

    ai_findings = (ai or {}).get("ai_findings", "No AI Result")
    ai_type = (ai or {}).get("pneumonia_type", "")
    ai_conf = (ai or {}).get("ai_confidence")

    ai_text = f"AI Analysis: {ai_findings.title()}"
    if ai_type:
        ai_text += f" ({ai_type.replace('_', ' ').title()})"
    if ai_conf:
        ai_text += f" - {float(ai_conf)*100:.1f}% confidence"

    doc_diagnosis = exam.get("diagnosis", "No diagnosis recorded.")
    chief_complaint = exam.get("chief_complaint", "N/A")
    logo_html = f"<img src='{hospital_logo}' style='height: 70px; margin-right: 20px;' />" if hospital_logo else ""

    html = f"""
    <html>
    <head>
        <title>X-Ray Report - {patient.get('first_name')}</title>
        <style>
            body {{ 
                font-family: 'Times New Roman', Times, serif; 
                color: #000; 
                padding: 40px; 
                font-size: 13px;
            }}
            .header {{ 
                display: flex; 
                align-items: center; 
                border-bottom: 2px solid #000; 
                padding-bottom: 10px; 
                margin-bottom: 20px; 
            }}
            .header-text h2 {{ margin: 0; font-size: 16px; font-weight: normal; }}
            .header-text h1 {{ margin: 0; font-size: 20px; font-weight: bold; }}
            .header-text p {{ margin: 2px 0; font-size: 12px; }}
            
            .title-box {{
                text-align: center;
                font-size: 16px;
                font-weight: bold;
                text-decoration: underline;
                margin: 20px 0;
                letter-spacing: 1px;
            }}
            
            .info-grid {{ 
                display: grid; 
                grid-template-columns: 1.2fr 1fr 1fr; 
                gap: 8px; 
                margin-bottom: 20px; 
            }}
            .info-grid div {{ font-size: 13px; }}
            
            .divider {{ border-top: 1px solid #000; margin: 15px 0; }}
            .section-title {{ font-weight: bold; margin-top: 15px; }}
            .content {{ margin-top: 5px; line-height: 1.4; }}
            
            .signature {{ 
                margin-top: 60px; 
                text-align: right; 
                padding-right: 50px;
            }}
            .signature-line {{ border-top: 1px solid #000; width: 200px; display: inline-block; margin-bottom: 5px; }}
            
            .footer {{
                margin-top: 60px;
                border-top: 2px solid #000;
                padding-top: 10px;
                font-size: 11px;
                display: flex;
                justify-content: space-between;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            {logo_html}
            <div class="header-text">
                <h2>Republic of the Philippines</h2>
                <h2>Department of Health</h2>
                <h1>{hospital_name.upper()}</h1>
                <p>{hospital_address}</p>
            </div>
        </div>
        <div class="title-box">XRAY RESULT</div>
        <div class="info-grid">
            <div><b>Patient Name:</b> {patient.get('first_name')} {patient.get('last_name')}</div>
            <div><b>Age:</b> {calculate_age(patient.get('date_of_birth'))}</div>
            <div><b>Sex:</b> {patient.get('sex')}</div>
            <div><b>Address:</b> {patient.get('address', 'N/A')}</div>
            <div><b>Date:</b> {format_date_only(exam.get('examination_date'))}</div>
            <div><b>X-ray No.:</b> {str(exam.get('examination_id'))[:8]}</div>
            <div><b>Procedure:</b> {request.get('body_part', 'CHEST PA')}</div>
        </div>
        <div class="divider"></div>
        <div class="section-title">Clinical Indication:</div>
        <div class="content">{chief_complaint}</div>
        <div class="section-title">AI Findings (Research Tool):</div>
        <div class="content">{ai_text}</div>
        <div class="section-title">******* [IMPRESSION] *******</div>
        <div class="content" style="white-space: pre-wrap;">{doc_diagnosis}</div>
        <div class="signature">
            <div class="signature-line"></div>
            <div style="margin-top: 5px; font-weight: bold;">{doctor_name}</div>
            <div style="font-size: 12px;">Attending Radiologist</div>
        </div>
        <div class="footer">
            <div><b>Lungsight AI System</b><br>{hospital_contact} | {hospital_email}</div>
            <div style="text-align: right;">Page 1 of 1</div>
        </div>
        <script>
            window.onload = function() {{ window.print(); }};
        </script>
    </body>
    </html>
    """
    components.html(html, height=0, width=0)
    st.success("Print dialog opened.")


def render_risk_card(ai_findings, ai_conf, pneumonia_type=None):
    risk_label, risk_tone = risk_from_ai_findings(ai_findings)
    conf_pct = confidence_percent(ai_conf)
    type_label, type_tone = pneumonia_type_label(pneumonia_type)

    if conf_pct is not None:
        conf_block = (
            "<div class='pr-hero-row pr-hero-row-block'>"
            "<div class='pr-conf-label'>"
            "<span>AI Confidence</span>"
            f"<b>{conf_pct:.1f}%</b>"
            "</div>"
            "<div class='pr-conf-bar'>"
            f"<div class='pr-conf-fill' style='width:{conf_pct}%'></div>"
            "</div>"
            "</div>"
        )
    else:
        conf_block = (
            "<div class='pr-hero-row'>"
            "<span>AI Confidence</span><b>—</b>"
            "</div>"
        )

    st.markdown(
        f"""
        <div class='pr-hero-card'>
            <p class='pr-hero-eyebrow'>AI Diagnostic Assessment</p>
            <div class='pr-hero-row'>
                <span>Risk Level</span>
                <div>{pill(risk_label, risk_tone)}</div>
            </div>
            <div class='pr-hero-row'>
                <span>Pneumonia Classification</span>
                <div>{pill(type_label, type_tone)}</div>
            </div>
            {conf_block}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_examination_details_card(exam):
    exam_date = exam.get("examination_date") or exam.get("created_at")

    rows = [
        ("Type", display_exam_type(exam)),
        ("Date", format_date_only(exam_date)),
        ("Time", format_time_only(exam_date)),
        ("Status", exam.get("status") or "—"),
        ("Chief Complaint", exam.get("chief_complaint") or "—"),
        ("HPI", exam.get("history_of_present_illness") or "—"),
        ("Physical Exam", exam.get("physical_examination") or "—"),
        ("Diagnosis", exam.get("diagnosis") or "—"),
        ("Plans / Orders", exam.get("plans_orders") or "—"),
        ("Disposition", exam.get("disposition") or "—"),
    ]

    st.markdown(
        "<div class='pr-hero-card'>"
        "<p class='pr-hero-eyebrow'>Clinical Evaluation</p>"
        + "".join(
            f"<div class='pr-hero-row'>"
            f"<span>{label}</span><b>{value}</b>"
            f"</div>"
            for label, value in rows
        )
        + "</div>",
        unsafe_allow_html=True,
    )


def render_xray_analysis(exam):
    section_title("X-Ray Imaging Analysis", "Digital chest radiograph submitted for diagnostic evaluation.")

    exam_id = exam.get("examination_id")
    request = get_xray_request_by_examination(exam_id)

    if not request:
        st.markdown(
            """
            <div class='pr-no-xray'>
                <div class='pr-no-xray-icon'>
                    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>
                        <circle cx="9" cy="9" r="2"/>
                        <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>
                    </svg>
                </div>
                <p class='pr-no-xray-title'>No X-Ray Requested</p>
                <p class='pr-no-xray-text'>No chest X-ray was requisitioned for this examination session.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return None, None, None

    images = get_xray_images_by_request(request["request_id"]) or []

    if not images:
        st.markdown(
            """
            <div class='pr-no-xray'>
                <div class='pr-no-xray-icon'>
                    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10"/>
                        <polyline points="12 6 12 12 16 14"/>
                    </svg>
                </div>
                <p class='pr-no-xray-title'>X-Ray In Queue / Pending</p>
                <p class='pr-no-xray-text'>An X-ray was requested, but radiographic images have not been uploaded yet.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return request, None, None

    image = images[0]
    image_url = get_xray_image_url(image.get("image_path"))
    ai = get_xray_ai_result(image.get("image_id"))

    show_heatmap = can_view_heatmap()

    if show_heatmap:
        original_col, heatmap_col = st.columns(2, gap="medium")
    else:
        original_col = st.container()
        heatmap_col = None

    with original_col:
        st.markdown("<p class='pr-img-label'>Original Radiograph</p>", unsafe_allow_html=True)
        if image_url:
            st.image(image_url, width="stretch")
        else:
            st.warning("Unable to retrieve original radiograph image.")

    if show_heatmap and heatmap_col is not None:
        with heatmap_col:
            st.markdown("<p class='pr-img-label'>Grad-CAM AI Heatmap</p>", unsafe_allow_html=True)

            heatmap_bytes = None
            if ai and ai.get("ai_result_id"):
                heatmap_bytes = get_xray_ai_heatmap(ai.get("ai_result_id"))

            if heatmap_bytes:
                st.image(
                    heatmap_bytes,
                    caption="Grad-CAM activation overlay — highlighted regions guided the model prediction.",
                    width="stretch",
                )
            else:
                st.markdown(
                    """
                    <div class='pr-heatmap-placeholder'>
                        <div class='pr-heatmap-icon'>
                            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <circle cx="12" cy="12" r="10"/>
                                <line x1="12" y1="8" x2="12" y2="12"/>
                                <line x1="12" y1="16" x2="12.01" y2="16"/>
                            </svg>
                        </div>
                        <p class='pr-heatmap-title'>Heatmap Processing / Unavailable</p>
                        <p class='pr-heatmap-text'>No saved Grad-CAM explanatory overlay is recorded for this scan.</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    return request, image, ai


def ai_findings_narrative(ai_findings, pneumonia_type):
    if not ai_findings:
        return None
    normalized = str(ai_findings).strip().lower()

    if normalized == "positive":
        if pneumonia_type == "bacterial_pneumonia":
            return (
                "The AI model identified radiographic features strongly indicative of "
                "<b>bacterial pneumonia</b> (lobar consolidation / dense opacities). "
                "Recommend immediate clinical correlation, CBC, blood culture, and empirical antibiotics."
            )
        if pneumonia_type == "viral_pneumonia":
            return (
                "The AI model identified radiographic features suggestive of "
                "<b>viral pneumonia</b> (diffuse interstitial markings / bilateral infiltrates). "
                "Recommend clinical correlation, supportive management, and close monitoring."
            )
        return (
            "The AI model detected radiographic features consistent with <b>pneumonia</b>. "
            "Recommend clinical correlation and physician verification."
        )

    if normalized == "negative":
        return (
            "The AI model did <b>not</b> identify patterns consistent with pneumonia in this chest radiograph. "
            "Continue standard clinical evaluation and monitor patient symptoms."
        )

    return None


def ai_recommendations(ai_findings, pneumonia_type):
    if not ai_findings:
        return []
    normalized = str(ai_findings).strip().lower()

    if normalized == "positive":
        base = [
            "Immediate physical correlation and vital signs reassessment",
            "Obtain CBC with differential and baseline blood culture",
        ]
        if pneumonia_type == "bacterial_pneumonia":
            base.append("Initiate targeted empirical antibacterial therapy")
        elif pneumonia_type == "viral_pneumonia":
            base.append("Consider antiviral therapy and supportive respiratory protocol")
        base.append("Schedule follow-up chest radiograph within 48–72 hours")
        return base

    if normalized == "negative":
        return [
            "Continue standard supportive clinical pathway",
            "Re-evaluate chest radiograph if clinical signs or dyspnea worsen",
        ]

    return []


def render_ai_summary(ai, ai_findings, pneumonia_type, ai_conf):
    section_title("Diagnostic Interpretation & Guidance")

    narrative = ai_findings_narrative(ai_findings, pneumonia_type)
    if not narrative:
        st.caption("No AI narrative interpretation available for this examination.")
        return

    _, risk_tone = risk_from_ai_findings(ai_findings)
    conf_pct = confidence_percent(ai_conf)

    tone_class = "pr-ai-summary-positive" if risk_tone == "red" else "pr-ai-summary-negative"
    conf_line = (
        f"<br><span class='pr-ai-summary-meta'>Model Confidence Score: <b>{conf_pct:.1f}%</b></span>"
        if conf_pct is not None
        else ""
    )

    st.markdown(
        f"""
        <div class='pr-ai-summary {tone_class}'>
            <p class='pr-ai-summary-text'>{narrative}</p>
            {conf_line}
        </div>
        """,
        unsafe_allow_html=True,
    )

    recs = ai_recommendations(ai_findings, pneumonia_type)
    if recs:
        section_title("Clinical Recommendations")
        items = "".join(
            f"<li><span class='pr-rec-num'>{i+1}</span><span>{text}</span></li>"
            for i, text in enumerate(recs)
        )
        st.markdown(f"<ul class='pr-rec-list'>{items}</ul>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class='pr-disclaimer'>
            <b>Clinical Notice:</b> This AI-generated assessment is intended solely as an investigational and explanatory decision-support tool. It must not serve as the exclusive determinant for clinical diagnoses. Final diagnosis and care pathways remain the responsibility of the attending physician.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_examination_report(patient, exam):
    back_col, print_col, _ = st.columns([2, 2, 6], vertical_alignment="center")

    with back_col:
        if st.button("Back to Records", key="mmr_back_to_category", icon=":material/arrow_back:", width="stretch"):
            back_to_category()

    with print_col:
        if st.button("Print Result", type="primary", icon=":material/print:", width="stretch"):
            exam_id = exam.get("examination_id")
            req = get_xray_request_by_examination(exam_id)
            img = None
            ai_res = None
            if req:
                imgs = get_xray_images_by_request(req["request_id"]) or []
                if imgs:
                    img = imgs[0]
                    ai_res = get_xray_ai_result(img.get("image_id"))
            trigger_print_report(patient, exam, req or {}, ai_res)

    st.write("")

    # Hero Banner
    render_patient_hero(patient)

    exam_id = exam.get("examination_id")
    ai = None
    request = None
    image = None

    try:
        request = get_xray_request_by_examination(exam_id)
        if request:
            imgs = get_xray_images_by_request(request["request_id"]) or []
            if imgs:
                image = imgs[0]
                ai = get_xray_ai_result(image.get("image_id"))
    except Exception:
        pass

    ai_findings = (ai or {}).get("ai_findings")
    pneumonia_type = (ai or {}).get("pneumonia_type")
    ai_conf = (ai or {}).get("ai_confidence")

    left_col, right_col = st.columns([1, 1.5], gap="large")

    with left_col:
        with st.container(key="mmr_hero_left"):
            render_risk_card(ai_findings, ai_conf, pneumonia_type)
            render_examination_details_card(exam)

    with right_col:
        render_xray_analysis(exam)
        render_ai_summary(ai, ai_findings, pneumonia_type, ai_conf)


# ============================================================
# DIALOGS (EXTERNAL MEDICAL RECORD)
# ============================================================

@st.dialog("External Medical Record", width="large")
def show_external_record_dialog(record):
    with st.container(key="sa_dialog"):
        record_type = record.get("record_type") or "Medical Record"
        record_date = format_date(record.get("record_date"))

        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between; align-items: center; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 0.65rem 1rem; margin-bottom: 1rem;">
                <span style="font-size: 1rem; font-weight: 700; color: var(--sa-ink);">{record_type}</span>
                <span style="font-size: 0.8rem; color: var(--sa-slate);">Date: <b>{record_date}</b></span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("<div class='sa-form-section-title'>Facility & Provider</div>", unsafe_allow_html=True)
            show_rows([
                ("Facility", record.get("facility_name") or "—"),
                ("Department", record.get("department") or "—"),
                ("Attending Physician", record.get("attending_physician") or "—"),
                ("Record Status", record.get("record_status") or "—"),
            ])

        with col_right:
            st.markdown("<div class='sa-form-section-title'>Clinical Record</div>", unsafe_allow_html=True)
            show_rows([
                ("Chief Complaint", record.get("chief_complaint") or "—"),
                ("Clinical History", record.get("clinical_history") or "—"),
                ("Diagnosis", record.get("diagnosis") or "—"),
                ("Procedure", record.get("procedure_name") or "—"),
                ("Findings", record.get("findings") or "—"),
                ("Impression", record.get("impression") or "—"),
                ("Treatment", record.get("treatment") or "—"),
                ("Follow-Up", record.get("follow_up") or "—"),
            ])

        # Attached Images / Scans
        rec_id = record.get("medical_record_id") or record.get("record_id")
        if rec_id:
            try:
                images = get_medical_record_images(rec_id) or []
                if images:
                    st.markdown("<div class='sa-form-section-title' style='margin-top:1rem;'>Attached Documents & Scans</div>", unsafe_allow_html=True)
                    img_cols = st.columns(min(len(images), 3))
                    for idx, img_info in enumerate(images):
                        file_path = img_info.get("file_path")
                        if file_path:
                            img_url = get_medical_record_file_url(file_path)
                            if img_url:
                                with img_cols[idx % 3]:
                                    st.image(img_url, caption=img_info.get("caption") or f"Document #{idx + 1}")
            except Exception:
                pass

        st.divider()
        _, close_col = st.columns([3.5, 1])
        with close_col:
            if st.button("Close", key="mmr_external_close", width="stretch"):
                st.session_state.pop(KEY_EXTERNAL, None)
                st.session_state.pop(KEY_EXTERNAL_SHOWN, None)
                st.rerun()


@st.dialog("Add External Medical Record", width="large")
def show_add_medical_record_dialog(patient):
    with st.container(key="sa_dialog"):
        render_patient_hero(patient)

        with st.form("mmr_add_medical_record_form"):
            st.markdown("<div class='sa-form-section-title'>1. Record Metadata & Facility</div>", unsafe_allow_html=True)

            f_col1, f_col2 = st.columns(2)
            record_date = f_col1.date_input("Record Date", value=date.today(), format="YYYY-MM-DD")
            record_type = f_col2.selectbox(
                "Record Type",
                [
                    "Consultation",
                    "Hospitalization",
                    "Laboratory",
                    "Imaging",
                    "Treatment",
                    "Discharge Summary",
                    "Other",
                ],
            )

            p_col1, p_col2 = st.columns(2)
            facility_name = p_col1.text_input("Facility / Hospital Name *", placeholder="e.g. Cebu South Medical Center")
            department = p_col2.text_input("Department / Unit", placeholder="e.g. Pulmonology / Radiology")

            attending_physician = st.text_input("Attending Physician", placeholder="e.g. Dr. Juan Dela Cruz")

            st.markdown("<div class='sa-form-section-title' style='margin-top:1.25rem;'>2. Clinical Findings & Impressions</div>", unsafe_allow_html=True)

            c_col1, c_col2 = st.columns(2)
            chief_complaint = c_col1.text_area("Chief Complaint", placeholder="Primary symptom or reason for evaluation...")
            clinical_history = c_col2.text_area("Clinical History", placeholder="Underlying history, past illnesses...")

            d_col1, d_col2 = st.columns(2)
            diagnosis = d_col1.text_area("Diagnosis / Clinical Impression", placeholder="Outside facility diagnosis...")
            procedure_name = d_col2.text_input("Procedure / Diagnostic Test", placeholder="e.g. Chest Radiograph PA View")

            findings = st.text_area("Findings", placeholder="Detailed imaging or laboratory findings...")
            treatment = st.text_area("Prescribed Treatment / Plan", placeholder="Medications, referrals, therapies...")

            st.markdown("<div class='sa-form-section-title' style='margin-top:1.25rem;'>3. Supporting Files & Attachments</div>", unsafe_allow_html=True)
            uploaded_files = st.file_uploader(
                "Upload Scans, Lab Results, or Referral Letters",
                type=["png", "jpg", "jpeg", "pdf"],
                accept_multiple_files=True,
            )

            st.write("")
            cancel_col, save_col = st.columns(2)

            cancel = cancel_col.form_submit_button("Cancel", width="stretch")
            submitted = save_col.form_submit_button("Save Medical Record", type="primary", icon=":material/check_circle:", width="stretch")

        if cancel:
            st.session_state.pop(KEY_ADD_RECORD, None)
            st.rerun()

        if not submitted:
            return

        if not facility_name.strip():
            st.error("Facility / Hospital name is required.")
            return

        try:
            result = create_medical_record(
                patient_id=patient["patient_id"],
                record_date=record_date,
                record_type=record_type,
                facility_name=facility_name.strip(),
                department=department.strip() or None,
                attending_physician=attending_physician.strip() or None,
                chief_complaint=chief_complaint.strip() or None,
                clinical_history=clinical_history.strip() or None,
                diagnosis=diagnosis.strip() or None,
                procedure_name=procedure_name.strip() or None,
                findings=findings.strip() or None,
                treatment=treatment.strip() or None,
                created_by=current_user().get("user_id"),
            )

            if not result.get("success"):
                st.error(result.get("message") or "Unable to create medical record.")
                return

            medical_record_id = result["data"]["medical_record_id"]

            for uploaded_file in (uploaded_files or []):
                upload_medical_record_file(
                    medical_record_id=medical_record_id,
                    uploaded_file=uploaded_file,
                    image_type=uploaded_file.type or "File",
                    description=uploaded_file.name,
                )

            remember("External medical record added successfully.")
            st.session_state.pop(KEY_ADD_RECORD, None)
            st.session_state[KEY_CATEGORY] = CATEGORY_EXTERNAL
            st.session_state.pop(KEY_EXAM, None)
            st.rerun()

        except Exception as error:
            st.error(f"Failed to save medical record: {error}")


# ============================================================
# PAGE ENTRYPOINT
# ============================================================

def show():
    load_css("manage_medical_records.css")
    show_flash_message()

    role_id = current_role_id()
    if role_id not in ALLOWED_ROLES:
        st.error("You don't have access to Patient Records.")
        return

    # Dialog: External Record View
    if st.session_state.get(KEY_EXTERNAL):
        if not st.session_state.get(KEY_EXTERNAL_SHOWN):
            show_external_record_dialog(st.session_state[KEY_EXTERNAL])
            st.session_state[KEY_EXTERNAL_SHOWN] = True
        else:
            st.session_state.pop(KEY_EXTERNAL, None)
            st.session_state.pop(KEY_EXTERNAL_SHOWN, None)
            st.rerun()

    # Dialog: Add External Record
    if st.session_state.get(KEY_ADD_RECORD) and can_add_record():
        show_add_medical_record_dialog(st.session_state[KEY_ADD_RECORD])

    with st.container(key="sa_page"):
        # Router
        selected_patient = st.session_state.get(KEY_PATIENT)
        selected_category = st.session_state.get(KEY_CATEGORY)
        selected_exam = st.session_state.get(KEY_EXAM)

        if selected_patient and selected_exam:
            render_examination_report(selected_patient, selected_exam)
            return

        if selected_patient and selected_category:
            render_category_list(selected_patient, selected_category)
            return

        if selected_patient:
            render_patient_overview(selected_patient)
            return

        rows = load_patient_rows()
        render_patient_list(rows)
