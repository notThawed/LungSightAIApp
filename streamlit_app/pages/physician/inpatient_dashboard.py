# streamlit_app/pages/physician/inpatient_dashboard.py

import streamlit as st
import html
from datetime import datetime, timezone, date, timedelta, time
from zoneinfo import ZoneInfo

from backend.supabase_client import admin_supabase
from backend import audit
from backend.backend_utils.inpatient_utils import calculate_discharge_readiness
from backend.backend_utils.followup_utils import create_follow_up
from streamlit_app.components.ui import (
    page_header, empty_state, section_title, pill, remember, show_flash_message
)
from shared.assets import load_css

ROLE_SUPERADMIN = 1
ROLE_RADIOLOGIST = 3
ROLE_HOSPITAL_ADMIN = 6
ROLE_STAFF = 7
MANILA_TZ = ZoneInfo("Asia/Manila")
UTC = timezone.utc

# ============================================================
# HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}

def current_user_id():
    return current_user().get("user_id")

def current_role_id():
    try: return int(current_user().get("role_id"))
    except: return None

def current_hospital_id():
    return current_user().get("hospital_id")

def current_role_label():
    return {ROLE_SUPERADMIN: "superadmin", ROLE_RADIOLOGIST: "radiologist", ROLE_HOSPITAL_ADMIN: "hospital_admin", ROLE_STAFF: "staff"}.get(current_role_id(), "unknown")

def patient_name(p):
    if not p: return "—"
    parts = [p.get("first_name"), p.get("middle_name"), p.get("last_name"), p.get("suffix")]
    return " ".join(part for part in parts if part).strip() or "—"

def format_date(v):
    if not v: return "—"
    return datetime.fromisoformat(str(v)[:10]).strftime("%b %d, %Y")

def parse_datetime(v):
    if not v: return None
    if isinstance(v, datetime): return v
    try: return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except: return None

def format_datetime(v):
    dt = parse_datetime(v)
    if not dt: return "—"
    return dt.astimezone(MANILA_TZ).strftime("%b %d, %Y · %I:%M %p")

def as_date(v):
    dt = parse_datetime(v)
    if dt: return dt.astimezone(MANILA_TZ).date()
    try: return date.fromisoformat(str(v)[:10])
    except: return date.today()

def to_utc_iso(day, t=None):
    t = t or datetime.now(MANILA_TZ).time().replace(tzinfo=None)
    return datetime.combine(day, t).replace(tzinfo=MANILA_TZ).astimezone(UTC).isoformat()

def go_to_admission(p, e):
    st.session_state["ip_p"] = p
    st.session_state["ip_e"] = e
    st.session_state["ip_mode"] = "detail"
    st.rerun()

def back_to_admissions():
    st.session_state.pop("ip_p", None)
    st.session_state.pop("ip_e", None)
    st.session_state["ip_mode"] = "list"
    st.rerun()

# ============================================================
# HOSPITAL SCOPING & DATA FETCHING
# ============================================================

def accessible_patient_ids():
    role = current_role_id()
    if role == ROLE_SUPERADMIN: return None
    if role not in (ROLE_RADIOLOGIST, ROLE_STAFF): return []
    hosp = current_hospital_id()
    if not hosp: return []
    try:
        res = admin_supabase.table("patients").select("patient_id").eq("hospital_id", hosp).execute()
        return [r["patient_id"] for r in (res.data or []) if r.get("patient_id")]
    except: return []

def load_admissions():
    pids = accessible_patient_ids()
    if pids == []: return []
    q = admin_supabase.table("examinations").select("*, patients(*)").eq("disposition", "Admission").eq("status", "Admitted")
    if pids is not None: q = q.in_("patient_id", pids)
    return q.order("examination_date", desc=True).execute().data or []

def get_admission_record(exam_id):
    for r in load_admissions():
        if r.get("examination_id") == exam_id: return r
    return None

def load_rounds(exam_id):
    res = admin_supabase.table("examinations").select("*").eq("parent_examination_id", exam_id).eq("examination_type", "Inpatient Round").order("examination_date", desc=True).execute()
    return res.data or []

def load_vitals(exam_ids):
    if not exam_ids: return {}
    res = admin_supabase.table("examination_vitals").select("*").in_("examination_id", exam_ids).order("recorded_at", desc=True).execute()
    v_map = {}
    for r in res.data or []:
        v_map.setdefault(r.get("examination_id"), r)
    return v_map

def load_user_name(user_id):
    if not user_id: return "—"
    try:
        res = admin_supabase.table("user_profiles").select("user_fname, user_lname").eq("user_id", user_id).execute()
        if res.data:
            u = res.data[0]
            return f"{u.get('user_fname', '')} {u.get('user_lname', '')}".strip()
    except: pass
    return "—"

# ============================================================
# ROUND DIALOG
# ============================================================


@st.dialog("Record Inpatient Round", width="large")
def show_log_round_dialog(patient, admission):

    # ============================================================
    # ROLE AUTHORIZATION
    # ============================================================
    if current_role_id() not in (ROLE_RADIOLOGIST, ROLE_STAFF):
        st.error(
            "Only Staff and Physician accounts may record inpatient rounds."
        )
        return

    admission_id = admission["examination_id"]

    st.markdown(f"**{patient_name(patient)}**")
    st.caption(
        "Document observations actually measured. "
        "Leave unmeasured values empty."
    )

    # ============================================================
    # OBSERVATION DATE AND 12-HOUR TIME
    # ============================================================

    now_ph = datetime.now(MANILA_TZ)

    admission_day = as_date(
        admission.get("time_in")
        or admission.get("examination_date")
    )

    day = st.date_input(
        "Observation date",
        value=max(now_ph.date(), admission_day),
        min_value=admission_day,
        format="MM/DD/YYYY",
        key=f"ip_observation_date_{admission_id}",
    )

    st.markdown("**Observation time (Philippines)**")

    time_col1, time_col2, time_col3 = st.columns(3)

    current_hour = now_ph.hour % 12 or 12
    current_period = "AM" if now_ph.hour < 12 else "PM"

    with time_col1:
        hour = st.selectbox(
            "",
            options=list(range(1, 13)),
            index=current_hour - 1,
            key=f"ip_hour_{admission_id}",
        )

    with time_col2:
        minute = st.selectbox(
            "",
            options=list(range(60)),
            index=now_ph.minute,
            format_func=lambda value: f"{value:02d}",
            key=f"ip_minute_{admission_id}",
        )

    with time_col3:
        period = st.selectbox(
            "AM / PM",
            options=["AM", "PM"],
            index=0 if current_period == "AM" else 1,
            key=f"ip_period_{admission_id}",
        )

    hour_24 = hour % 12

    if period == "PM":
        hour_24 += 12

    clock = time(
        hour=hour_24,
        minute=minute,
    )


    # ============================================================
    # CLINICAL OBSERVATION
    # ============================================================
    status = st.selectbox(
        "Clinical observation",
        [
            "Stable",
            "Improving",
            "Worsening",
            "Needs Further Assessment",
        ],
    )

    # ============================================================
    # VITAL SIGNS
    # ============================================================
    a, b, c = st.columns(3)

    with a:
        spo2_text = st.text_input(
            "SpO₂ (%)",
            placeholder="Not measured",
            key=f"ip_spo2_{admission_id}",
        )

        bp_s = st.text_input(
            "Systolic BP (mmHg)",
            placeholder="Optional",
            key=f"ip_bps_{admission_id}",
        )

    with b:
        temp_text = st.text_input(
            "Temperature (°C)",
            placeholder="Not measured",
            key=f"ip_temp_{admission_id}",
        )

        bp_d = st.text_input(
            "Diastolic BP (mmHg)",
            placeholder="Optional",
            key=f"ip_bpd_{admission_id}",
        )

    with c:
        rr_text = st.text_input(
            "Respiratory rate (/min)",
            placeholder="Not measured",
            key=f"ip_rr_{admission_id}",
        )

        pulse = st.text_input(
            "Pulse (/min)",
            placeholder="Optional",
            key=f"ip_pulse_{admission_id}",
        )

    # ============================================================
    # OXYGEN SUPPORT AND CLINICAL NOTES
    # ============================================================
    oxygen = st.selectbox(
        "Oxygen support",
        [
            "Unknown",
            "Room air",
            "Supplemental oxygen",
        ],
    )

    notes = st.text_area(
        "Clinical observations / handoff notes"
    )

    st.caption(
        "Ward-round observations do not authorize "
        "discharge or medication changes."
    )

    # ============================================================
    # SAVE WARD ROUND
    # ============================================================
    if st.button(
        "Save ward round",
        type="primary",
        use_container_width=True,
    ):

        try:
            # ----------------------------------------------------
            # VALIDATE NOTES
            # ----------------------------------------------------
            if not notes.strip():
                raise ValueError(
                    "Clinical observations are required."
                )

            # ----------------------------------------------------
            # VALIDATE VITAL SIGNS
            # ----------------------------------------------------
            def parse(
                text,
                lo,
                hi,
                label,
                integer=False,
            ):
                if not text.strip():
                    return None

                v = float(text)

                if (
                    not lo <= v <= hi
                    or (integer and not v.is_integer())
                ):
                    raise ValueError(
                        f"{label} must be between {lo} and {hi}."
                    )

                return int(v) if integer else v

            values = {
                "spo2": parse(
                    spo2_text, 0, 100, "SpO₂", True
                ),
                "temperature": parse(
                    temp_text, 30, 45, "Temperature"
                ),
                "respiratory_rate": parse(
                    rr_text, 1, 99, "Respiratory rate", True
                ),
                "bp_systolic": parse(
                    bp_s, 40, 300, "Systolic BP", True
                ),
                "bp_diastolic": parse(
                    bp_d, 20, 200, "Diastolic BP", True
                ),
                "pulse_rate": parse(
                    pulse, 20, 250, "Pulse", True
                ),
            }

            if all(
                v is None for v in values.values()
            ):
                raise ValueError(
                    "Record at least one measured vital sign."
                )

            # ----------------------------------------------------
            # CONVERT OBSERVATION TIME TO UTC
            # ----------------------------------------------------
            observed = to_utc_iso(day, clock)

            observed_dt = parse_datetime(observed)

            if observed_dt is None:
                raise ValueError(
                    "Invalid observation date or time."
                )


            # ----------------------------------------------------
            # RECHECK ACTIVE ADMISSION
            # ----------------------------------------------------
            if not get_admission_record(admission_id):
                raise ValueError(
                    "Admission is no longer active or accessible."
                )

            # ----------------------------------------------------
            # SAVE EXAMINATION AND VITAL SIGNS
            # ----------------------------------------------------
            new_id = None

            try:
                inserted = (
                    admin_supabase
                    .table("examinations")
                    .insert({
                        "patient_id": patient["patient_id"],
                        "examination_type": "Inpatient Round",
                        "examination_date": observed,
                        "status": "Completed",
                        "parent_examination_id": admission_id,
                        "created_by": current_user_id(),
                        "clinical_status": status,
                        "diagnosis": notes.strip(),
                        "chief_complaint": (
                            f"Ward Round — {status}"
                        ),
                    })
                    .execute()
                )

                if not inserted.data:
                    raise RuntimeError(
                        "Round examination could not be saved."
                    )

                new_id = inserted.data[0][
                    "examination_id"
                ]

                payload = {
                    "examination_id": new_id,
                    **values,
                    "oxygen_support": oxygen,
                    "recorded_by": current_user_id(),
                    "recorded_by_role": current_role_label(),
                    "recorded_at": observed,
                }

                saved = (
                    admin_supabase
                    .table("examination_vitals")
                    .insert(payload)
                    .execute()
                )

                if not saved.data:
                    raise RuntimeError(
                        "Vital-sign record was not saved."
                    )

            except Exception:
                # Best-effort rollback of the new examination.
                if new_id:
                    try:
                        (
                            admin_supabase
                            .table("examinations")
                            .delete()
                            .eq(
                                "examination_id",
                                new_id,
                            )
                            .execute()
                        )

                    except Exception:
                        st.error(
                            "Incomplete round may remain; "
                            "contact administrator to reconcile it."
                        )

                raise

            # ----------------------------------------------------
            # SUCCESS
            # ----------------------------------------------------
            remember("Ward round recorded.")
            st.rerun()

        except Exception as exc:
            st.error(str(exc))

@st.dialog("Request Physician Review", width="large")
def show_review_request_dialog(patient, admission):
    if current_role_id() not in (ROLE_STAFF, ROLE_RADIOLOGIST):
        st.error("Not authorized.")
        return
    st.write(f"**{patient_name(patient)}**")
    reason = st.text_area("Reason for physician review", placeholder="Describe the concern or discharge assessment request")
    if st.button("Send review request", type="primary", use_container_width=True):
        if len(reason.strip()) < 10:
            st.error("Please provide a reason (at least 10 characters).")
            return
        try:
            admission_id = admission["examination_id"]
            if not get_admission_record(admission_id):
                raise RuntimeError("Admission is not active or accessible.")
            result = (admin_supabase.table("examinations").update({
                "inpatient_review_status": "Pending",
                "inpatient_review_requested_at": datetime.now(UTC).isoformat(),
                "inpatient_review_requested_by": current_user_id(),
                "inpatient_review_reason": reason.strip(),
                "inpatient_reviewed_at": None,
                "inpatient_reviewed_by": None,
                "inpatient_review_response": None,
            }).eq("examination_id", admission_id).eq("status", "Admitted").execute())
            if not result.data:
                raise RuntimeError("Could not save review request.")
            remember("Physician review requested.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog("Respond to Review Request", width="large")
def show_review_response_dialog(patient, admission):
    if current_role_id() != ROLE_RADIOLOGIST:
        st.error("Physician authorization required.")
        return
    st.write(f"**{patient_name(patient)}**")
    st.info(admission.get("inpatient_review_reason") or "No reason provided")
    response = st.text_area("Physician response / plan")
    if st.button("Resolve request", type="primary", use_container_width=True):
        if len(response.strip()) < 10:
            st.error("Please document the response.")
            return
        try:
            result = (admin_supabase.table("examinations").update({
                "inpatient_review_status": "Resolved",
                "inpatient_reviewed_at": datetime.now(UTC).isoformat(),
                "inpatient_reviewed_by": current_user_id(),
                "inpatient_review_response": response.strip(),
            }).eq("examination_id", admission["examination_id"]).eq("status", "Admitted").eq("inpatient_review_status", "Pending").execute())
            if not result.data:
                raise RuntimeError("Review request has changed or admission is no longer active.")
            remember("Physician review resolved.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog("Physician Discharge Review", width="large")
def show_discharge_dialog(patient, admission, review):
    if current_role_id() != ROLE_RADIOLOGIST:
        st.error("Only physicians can authorize discharge.")
        return

    admission_id = admission["examination_id"]

    st.markdown(f"**{patient_name(patient)}**")
    st.warning(
        "The score is advisory, not clearance for discharge. "
        "Review the HIS and patient before deciding."
    )

    # ============================================================
    # PHYSICIAN VERIFICATION
    # ============================================================
    c1 = st.checkbox(
        "I reviewed observations, missing values, and trends."
    )

    c2 = st.checkbox(
        "I verified oxygen needs and the patient's prescribed target."
    )

    c3 = st.checkbox(
        "I reviewed fever history and overall clinical stability."
    )

    c4 = st.checkbox(
        "I reviewed the treatment and safe discharge plan."
    )

    decision = st.radio(
        "Decision",
        [
            "Continue admission",
            "Further assessment required",
            "Approve discharge",
        ],
    )

    notes = st.text_area(
        "Physician assessment and discharge instructions"
    )

    # ============================================================
    # POST-DISCHARGE APPOINTMENT
    # ============================================================
    st.markdown("**Required post-discharge appointment**")

    fu_day = st.date_input(
        "Follow-up date (physician-selected)",
        value=date.today() + timedelta(days=21),
        min_value=date.today(),
    )

    # ============================================================
    # FOLLOW-UP TIME — HOUR / MINUTE / AM-PM
    # ============================================================
    st.markdown("**Follow-up time**")

    time_col1, time_col2, time_col3 = st.columns(3)

    with time_col1:
        fu_hour = st.selectbox(
            "Hour",
            options=list(range(1, 13)),
            index=8,
            label_visibility="collapsed",
            key=f"ip_fu_hour_{admission_id}",
        )

    with time_col2:
        fu_minute = st.selectbox(
            "Minute",
            options=list(range(60)),
            index=0,
            format_func=lambda m: f"{m:02d}",
            label_visibility="collapsed",
            key=f"ip_fu_minute_{admission_id}",
        )

    with time_col3:
        fu_period = st.selectbox(
            "AM / PM",
            options=["AM", "PM"],
            index=0,
            key=f"ip_fu_period_{admission_id}",
        )

    # Convert 12-hour time to a Python time object.
    hour_24 = fu_hour % 12

    if fu_period == "PM":
        hour_24 += 12

    fu_clock = time(
        hour=hour_24,
        minute=fu_minute,
    )

    st.caption(
        "Follow-up imaging is ordered separately "
        "when clinically indicated."
    )

    # ============================================================
    # CONFIRM DISCHARGE
    # ============================================================
    if st.button(
        "Confirm physician discharge",
        type="primary",
        use_container_width=True,
        disabled=(
            decision != "Approve discharge"
            or not all((c1, c2, c3, c4))
            or len(notes.strip()) < 10
        ),
    ):
        try:
            # ----------------------------------------------------
            # RECHECK ACTIVE ADMISSION
            # ----------------------------------------------------
            if not get_admission_record(admission_id):
                raise RuntimeError(
                    "Admission is no longer active or accessible."
                )

            # ----------------------------------------------------
            # RESOLVE FOLLOW-UP CHAIN
            # ----------------------------------------------------
            marker = (
                f"[post_discharge_admission:{admission_id}]"
            )

            from backend.backend_utils.followup_utils import (
                resolve_follow_up_chain
            )

            source_id, _ = resolve_follow_up_chain(
                patient["patient_id"],
                admission_id,
            )

            if not source_id:
                raise RuntimeError(
                    "Cannot resolve original General Consult; "
                    "discharge not saved."
                )

            # ----------------------------------------------------
            # CHECK EXISTING APPOINTMENT
            # ----------------------------------------------------
            existing = (
                admin_supabase
                .table("follow_ups")
                .select("*")
                .eq(
                    "patient_id",
                    patient["patient_id"],
                )
                .eq(
                    "source_examination_id",
                    source_id,
                )
                .execute()
            ).data or []

            matching = [
                f for f in existing
                if (
                    marker in (f.get("notes") or "")
                    and f.get("status") in (
                        "Scheduled",
                        "Rescheduled",
                    )
                )
            ]

            if matching:
                if (
                    str(
                        matching[0].get(
                            "follow_up_date"
                        )
                    )
                    != fu_day.isoformat()
                ):
                    raise RuntimeError(
                        "An appointment already exists "
                        "for this admission on another date; "
                        "reconcile it before discharge."
                    )

            else:
                # ------------------------------------------------
                # CREATE FOLLOW-UP
                # ------------------------------------------------
                created = create_follow_up(
                    patient_id=patient["patient_id"],
                    examination_id=admission_id,
                    follow_up_date=fu_day,
                    follow_up_time=fu_clock.strftime(
                        "%H:%M:%S"
                    ),
                    notes=(
                        "Post-discharge clinical follow-up "
                        f"{marker}. {notes.strip()}"
                    ),
                    created_by=current_user_id(),
                )

                if not created.get("success"):
                    raise RuntimeError(
                        created.get("message")
                        or "Follow-up creation failed; "
                        "discharge not saved."
                    )

            # ----------------------------------------------------
            # UPDATE ADMISSION STATUS
            # ----------------------------------------------------
            update = (
                admin_supabase
                .table("examinations")
                .update({
                    "status": "Discharged",
                    "time_of_discharge": (
                        datetime.now(UTC).isoformat()
                    ),
                    "discharged_by": current_user_id(),
                    "discharge_notes": notes.strip(),
                    "post_discharge_followup_status": (
                        "Scheduled"
                    ),
                    "follow_up_date": fu_day.isoformat(),
                    "inpatient_review_status": (
                        "Resolved"
                        if admission.get(
                            "inpatient_review_status"
                        ) == "Pending"
                        else admission.get(
                            "inpatient_review_status",
                            "None",
                        )
                    ),
                })
                .eq(
                    "examination_id",
                    admission_id,
                )
                .eq(
                    "status",
                    "Admitted",
                )
                .eq(
                    "disposition",
                    "Admission",
                )
                .execute()
            )

            if not update.data:
                raise RuntimeError(
                    "Follow-up exists, but admission "
                    "was not discharged; "
                    "reconcile before retrying."
                )

            # ----------------------------------------------------
            # SUCCESS
            # ----------------------------------------------------
            remember(
                "Discharge confirmed and post-discharge "
                "follow-up scheduled."
            )

            st.session_state["ip_mode"] = "list"
            st.session_state.pop("ip_e", None)
            st.session_state.pop("ip_p", None)

            st.rerun()

        except Exception as exc:
            st.error(str(exc))



# ============================================================
# ADMISSION LIST
# ============================================================

def render_ward_list():
    page_header("Inpatient Rounds" if current_role_id() == ROLE_STAFF else "Admission Tracking", "Ward-round observations, clinical trends and physician review.")
    st.markdown("<div class='ip-workspace-banner'><h3>Clinical Admission Workspace</h3><p>Track active admissions, ward rounds and physician review requests.</p></div>", unsafe_allow_html=True)
    
    try:
        raw_admissions = load_admissions()
    except Exception as e:
        st.error(f"Failed to load admissions: {e}"); return

    # ==========================================
    # DEDUPLICATION GUARD
    # ==========================================
    # If a patient has multiple active admission rows, keep only the newest one.
    admissions_dict = {}
    for a in raw_admissions:
        p_id = a.get("patient_id")
        if not p_id:
            continue
        # If we haven't seen this patient yet, add them
        if p_id not in admissions_dict:
            admissions_dict[p_id] = a
        else:
            # If we HAVE seen them, compare dates and keep the newer admission
            current_newest = admissions_dict[p_id].get("examination_date") or ""
            new_candidate = a.get("examination_date") or ""
            if new_candidate > current_newest:
                admissions_dict[p_id] = a
                
    admissions = list(admissions_dict.values())
    # ==========================================

    # Metrics
    rounds_today = 0
    try:
        ids = [r["examination_id"] for r in admissions]
        if ids:
            today_start = datetime.now(MANILA_TZ).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC).isoformat()
            r_today = admin_supabase.table("examinations").select("examination_id").eq("examination_type", "Inpatient Round").in_("parent_examination_id", ids).gte("examination_date", today_start).execute()
            rounds_today = len(r_today.data or [])
    except: pass

    m1, m2, m3 = st.columns(3)
    m1.metric("Currently Admitted", len(admissions))
    m2.metric("Physician Reviews Pending", sum(a.get("inpatient_review_status") == "Pending" for a in admissions))
    m3.metric("Rounds Today", rounds_today)

    search = st.text_input("Search admitted patients", placeholder="Patient name or patient code", key="ip_admission_search")
    if search.strip():
        q = search.casefold().strip()
        admissions = [a for a in admissions if q in patient_name(a.get("patients") or {}).casefold() or q in str((a.get("patients") or {}).get("patient_code") or "").casefold()]
    section_title("Current Admissions")
    if not admissions:
        empty_state("No patients are currently admitted.")
        return

    for a in admissions:
        p = a.get("patients") or {}
        admit_id = a.get("examination_id")  # Use unique exam ID for keys
        admit_day = as_date(a.get("time_in") or a.get("examination_date"))
        h_day = max(1, (date.today() - admit_day).days + 1)
        
        with st.container(key=f"ip_card_{admit_id}"):
            c_info, c_btn = st.columns([4, 1.2], vertical_alignment="center")
            with c_info:
                st.markdown(
                    f"<div class='ip-card-patient-row'>"
                    f"<div class='ip-patient-avatar'><span class='material-symbols-rounded'>hotel</span></div>"
                    f"<div class='ip-patient-details'>"
                    f"<p class='ip-patient-name'>{patient_name(p)}</p>"
                    f"<div class='ip-patient-meta'>"
                    f"<span class='ip-meta-badge'>Hospital Day {h_day}</span>"
                    f"<span class='ip-meta-date'><span class='material-symbols-rounded'>calendar_today</span>Admitted {format_date(admit_day)}</span>"
                    f"<span class='ip-meta-diag'>{a.get('diagnosis') or 'Inpatient Stay'}</span>"
                    f"</div>"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with c_btn:
                if st.button("Open Monitoring", key=f"ip_btn_{admit_id}", icon=":material/monitor_heart:", use_container_width=True):
                    go_to_admission(p, a)


# ============================================================
# ADMISSION DETAIL
# ============================================================


def render_patient_detail():
    e_id = (st.session_state.get("ip_e") or {}).get("examination_id")
    if not e_id:
        back_to_admissions()
        return

    admission = get_admission_record(e_id)
    if not admission:
        st.error("Admission not found.")
        return

    p = admission.get("patients") or {}

    # ============================================================
    # ROLE PERMISSIONS
    # ============================================================
    role_id = current_role_id()

    ROLE_STAFF = 7
    is_physician = role_id == ROLE_RADIOLOGIST
    is_staff = role_id == ROLE_STAFF

    if not (is_physician or is_staff):
        st.error("You are not authorized to access inpatient monitoring.")
        return

    if st.button(
        "Back to Ward",
        key="ip_back",
        icon=":material/arrow_back:",
    ):
        back_to_admissions()
        return

    admit_day = as_date(
        admission.get("time_in")
        or admission.get("examination_date")
    )

    page_header(
        "Inpatient Monitoring",
        f"{patient_name(p)} · Admitted {format_date(admit_day)}",
    )

    # ============================================================
    # FETCH DAILY ROUNDS AND VITAL SIGNS
    # ============================================================
    try:
        rounds = load_rounds(e_id)

        v_map = load_vitals([
            r["examination_id"]
            for r in rounds
        ])

        history = []
        chart_data = []

        for r in rounds:
            v = v_map.get(r["examination_id"])

            if v:
                merged = dict(v)
                merged["examination_date"] = r.get(
                    "examination_date"
                )
                history.append(merged)

        for h in reversed(history):
            chart_data.append({
                "Date": format_date(
                    h.get("examination_date")
                ),
                "SpO2": h.get("spo2"),
                "Temp": h.get("temperature"),
                "RR": h.get("respiratory_rate"),
            })

    except Exception as exc:
        st.error(f"Failed to load inpatient rounds: {exc}")
        return

    # ============================================================
    # ADMISSION BASELINE
    # ============================================================
    try:
        baseline_map = load_vitals([e_id])
        baseline = baseline_map.get(e_id) or {}
    except Exception:
        baseline = {}

    readiness = calculate_discharge_readiness(history)

    if baseline:
        baseline_items = [
            f"{label}: {baseline.get(key)}"
            for label, key in (
                ("SpO₂", "spo2"),
                ("Temp", "temperature"),
                ("RR", "respiratory_rate"),
            )
            if baseline.get(key) is not None
        ]

        if baseline_items:
            st.caption(
                "Admission baseline · "
                + " · ".join(baseline_items)
            )

    # ============================================================
    # PHYSICIAN REVIEW REQUEST STATUS
    # ============================================================
    review_status = (
        admission.get("inpatient_review_status")
        or "None"
    )

    if review_status == "Pending":

        st.markdown(
            "<div class='ip-review-pending'>"
            "Physician review requested"
            "</div>",
            unsafe_allow_html=True,
        )

        st.info(
            admission.get("inpatient_review_reason")
            or "No reason recorded."
        )

        # Only physicians can respond to review requests.
        if is_physician:
            if st.button(
                "Respond to Request",
                key="ip_review_response",
                icon=":material/rate_review:",
                use_container_width=False,
            ):
                show_review_response_dialog(
                    p,
                    admission,
                )

    elif review_status == "Acknowledged":

        st.info(
            "The physician has acknowledged the review request."
        )

    elif review_status == "Resolved":

        st.markdown(
            "<div class='ip-review-resolved'>"
            "Last physician review resolved"
            "</div>",
            unsafe_allow_html=True,
        )

        if admission.get("inpatient_review_response"):
            st.caption(
                "Physician response: "
                + str(
                    admission.get("inpatient_review_response")
                )
            )

    # ============================================================
    # CLINICAL DECISION SUPPORT
    # ============================================================
    section_title("Clinical Decision Support")

    if not readiness["alerts"]:
        st.success(
            "No clinical flags detected from the latest observation."
        )
    else:
        for alert in readiness["alerts"]:
            st.warning(alert)

    # ============================================================
    # DISCHARGE READINESS CHECKLIST
    # ============================================================
    section_title("Discharge Readiness Checklist")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.checkbox(
            "24-hour temperature trend met (verify clinically)",
            value=readiness["checklist"].get(
                "afebrile", False
            ),
            disabled=True,
        )

    with c2:
        st.checkbox(
            "Latest SpO₂ indicator on room air",
            value=readiness["checklist"].get(
                "spo2_stable", False
            ),
            disabled=True,
        )

    with c3:
        st.checkbox(
            "Respiratory rate < 24 / min",
            value=readiness["checklist"].get(
                "rr_normal", False
            ),
            disabled=True,
        )

    st.markdown(
        f"<p class='ip-status-line'>"
        f"Overall Status: "
        f"{pill(readiness['status'], readiness['tone'])}"
        f"</p>",
        unsafe_allow_html=True,
    )

    # ============================================================
    # DAILY ROUNDS TABLE
    # ============================================================
    section_title("Daily Rounds")

    if not rounds:
        st.info("No rounds logged.")

    else:
        widths = [
            1.2, 0.6, 1.0, 0.7,
            0.7, 0.8, 2.0, 1.0
        ]

        with st.container(key="ip_rounds_header"):
            h1, h2, h3, h4, h5, h6, h7, h8 = (
                st.columns(widths)
            )

            headers = [
                (h1, "Date & Time"),
                (h2, "Day"),
                (h3, "Status"),
                (h4, "SpO₂"),
                (h5, "Temp"),
                (h6, "RR"),
                (h7, "Notes"),
                (h8, "Recorded By"),
            ]

            for col, label in headers:
                col.markdown(
                    f"<span class='ip-th'>"
                    f"{label}"
                    f"</span>",
                    unsafe_allow_html=True,
                )

        for r in rounds:
            v = v_map.get(
                r["examination_id"], {}
            )

            dt_str = r.get("examination_date")

            if dt_str:
                dt = datetime.fromisoformat(
                    str(dt_str).replace(
                        "Z", "+00:00"
                    )
                ).astimezone(MANILA_TZ)

                date_str = dt.strftime(
                    "%b %d, %I:%M %p"
                )
                rd = dt.date()

            else:
                date_str = "—"
                rd = date.today()

            r_day = max(
                1,
                (rd - admit_day).days + 1
            )

            status_label = (
                r.get("clinical_status")
                or "—"
            )

            recorded_by = load_user_name(r.get("created_by"))

            # Get the role recorded with this ward round
            v = v_map.get(r["examination_id"], {})
            recorded_role = str(
                v.get("recorded_by_role") or ""
            ).strip().lower()

            # Add Dr. prefix only for physician/doctor/radiologist
            if recorded_role in ("physician", "doctor", "radiologist"):
                if recorded_by and recorded_by != "—":
                    if not recorded_by.lower().startswith("dr."):
                        recorded_by = f"Dr. {recorded_by}"

            # Avoid displaying None%, None°C, etc.
            spo2_display = (
                f"{v['spo2']}%"
                if v.get("spo2") is not None
                else "—"
            )

            temp_display = (
                f"{v['temperature']}°C"
                if v.get("temperature") is not None
                else "—"
            )

            rr_display = (
                f"{v['respiratory_rate']}/min"
                if v.get("respiratory_rate") is not None
                else "—"
            )

            notes_display = (
                r.get("physical_examination")
                or r.get("diagnosis")
                or "—"
            )

            with st.container(
                key=f"ip_round_row_{r['examination_id']}"
            ):
                c1, c2, c3, c4, c5, c6, c7, c8 = (
                    st.columns(
                        widths,
                        vertical_alignment="center",
                    )
                )

                values = [
                    (c1, "ip-cell-strong", date_str),
                    (c2, "ip-cell", f"Day {r_day}"),
                    (c3, "ip-cell", status_label),
                    (c4, "ip-cell", spo2_display),
                    (c5, "ip-cell", temp_display),
                    (c6, "ip-cell", rr_display),
                    (c7, "ip-cell-notes", notes_display),
                    (c8, "ip-cell", recorded_by),
                ]

                for col, css_class, value in values:
                    col.markdown(
                        f"<span class='{css_class}'>"
                        f"{html.escape(str(value))}"
                        f"</span>",
                        unsafe_allow_html=True,
                    )

    # ============================================================
    # CLINICAL TREND CHARTS
    # ============================================================
    if chart_data:
        import altair as alt
        import pandas as pd

        st.write("")
        section_title("Clinical Trend")

        df = pd.DataFrame(chart_data)

        base = (
            alt.Chart(df)
            .mark_line(
                point=True,
                strokeWidth=2.5,
            )
            .properties(
                height=220,
                padding={
                    "left": 10,
                    "right": 10,
                    "top": 15,
                    "bottom": 10,
                },
            )
            .configure_axis(
                labelFontSize=11,
                labelColor="#4A677B",
                titleFontSize=0,
                gridColor="#EEF3F5",
                domainColor="#DCE7EB",
            )
            .configure_view(
                strokeWidth=0
            )
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.caption("SpO₂ (%)")

            st.altair_chart(
                base.encode(
                    x=alt.X(
                        "Date:N",
                        axis=alt.Axis(
                            labelAngle=-45
                        ),
                    ),
                    y=alt.Y(
                        "SpO2:Q",
                        scale=alt.Scale(
                            domain=[60, 100]
                        ),
                    ),
                    color=alt.value(
                        "#0F7C88"
                    ),
                ),
                use_container_width=True,
            )

        with col2:
            st.caption("Temperature (°C)")

            st.altair_chart(
                base.encode(
                    x=alt.X(
                        "Date:N",
                        axis=alt.Axis(
                            labelAngle=-45
                        ),
                    ),
                    y=alt.Y(
                        "Temp:Q",
                        scale=alt.Scale(
                            domain=[35, 42]
                        ),
                    ),
                    color=alt.value(
                        "#B45309"
                    ),
                ),
                use_container_width=True,
            )

        with col3:
            st.caption("Resp Rate (/min)")

            st.altair_chart(
                base.encode(
                    x=alt.X(
                        "Date:N",
                        axis=alt.Axis(
                            labelAngle=-45
                        ),
                    ),
                    y=alt.Y(
                        "RR:Q",
                        scale=alt.Scale(
                            domain=[10, 40]
                        ),
                    ),
                    color=alt.value(
                        "#B91C1C"
                    ),
                ),
                use_container_width=True,
            )

        st.write("")

    # ============================================================
    # ROLE-BASED ACTION BUTTONS
    # ============================================================

    if is_physician:

        # PHYSICIAN:
        # Can log rounds and review discharge.
        # Does not request a physician review.

        act1, act2 = st.columns(2)

        with act1:
            if st.button(
                "Log New Daily Round",
                key="ip_btn_new_round",
                icon=":material/add_circle:",
                use_container_width=True,
            ):
                show_log_round_dialog(
                    p,
                    admission,
                )

        with act2:
            if st.button(
                "Review Discharge",
                key="ip_btn_discharge",
                type="primary",
                icon=":material/assignment_turned_in:",
                use_container_width=True,
            ):
                show_discharge_dialog(
                    p,
                    admission,
                    readiness,
                )

    elif is_staff:

        # STAFF:
        # Can log rounds and request physician review.
        # Cannot approve discharge.

        act1, act2 = st.columns(2)

        with act1:
            if st.button(
                "Log New Daily Round",
                key="ip_btn_new_round",
                icon=":material/add_circle:",
                use_container_width=True,
            ):
                show_log_round_dialog(
                    p,
                    admission,
                )

        with act2:
            if st.button(
                "Request Physician Review",
                key="ip_btn_review",
                icon=":material/notification_important:",
                use_container_width=True,
                disabled=review_status in (
                    "Pending",
                    "Acknowledged",
                ),
            ):
                show_review_request_dialog(
                    p,
                    admission,
                )

        if review_status in ("Pending", "Acknowledged"):
            st.caption(
                "A physician review request is already active "
                "for this admission."
            )

# ============================================================
# PAGE
# ============================================================

def show():
    if current_role_id() not in (ROLE_RADIOLOGIST, ROLE_STAFF):
        st.error("Inpatient monitoring is restricted to Staff and Physician accounts.")
        return
    load_css("inpatient_dashboard.css")
    load_css("inpatient_redesign.css")
    show_flash_message()

    with st.container(key="physician_inpatient_page"):
        if st.session_state.get("ip_mode") == "detail":
            render_patient_detail()
        else:
            render_ward_list()