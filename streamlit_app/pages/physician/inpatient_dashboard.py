# streamlit_app/pages/physician/inpatient_dashboard.py

import streamlit as st
from datetime import datetime, timezone, date, timedelta, time
from zoneinfo import ZoneInfo

from backend.supabase_client import admin_supabase
from backend.backend_utils.inpatient_utils import calculate_discharge_readiness
from backend.backend_utils.followup_utils import create_follow_up
from streamlit_app.components.ui import (
    page_header, empty_state, section_title, pill, remember, show_flash_message
)
from shared.assets import load_css

ROLE_SUPERADMIN = 1
ROLE_RADIOLOGIST = 3
ROLE_HOSPITAL_ADMIN = 6
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
    return {ROLE_SUPERADMIN: "superadmin", ROLE_RADIOLOGIST: "radiologist", ROLE_HOSPITAL_ADMIN: "hospital_admin"}.get(current_role_id(), "unknown")

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
    if role not in (ROLE_RADIOLOGIST, ROLE_HOSPITAL_ADMIN): return []
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

@st.dialog("Log Inpatient Round", width="large")
def show_log_round_dialog(patient, admission):
    exam_id = admission["examination_id"]
    admit_day = as_date(admission.get("time_in") or admission.get("examination_date"))
    
    st.markdown(f"**{patient_name(patient)}**")
    # Fetch and display diagnosis
    st.caption(f"Diagnosis: {admission.get('diagnosis') or '—'}")
    st.caption(f"Admitted {format_date(admit_day)}")
    st.divider()

    selected_date = st.date_input("Round Date", value=date.today(), min_value=admit_day, key=f"ip_round_date_{exam_id}")
    
    status = st.selectbox("Clinical Status", ["Improving", "Stable", "Worsening", "Needs Further Assessment"], key=f"ip_round_status_{exam_id}")

    c1, c2 = st.columns(2)
    with c1:
        spo2 = st.number_input("SpO₂ (%)", 0, 100, 95)
        temp = st.number_input("Temperature (°C)", 30.0, 45.0, 36.8, 0.1)
    with c2:
        rr = st.number_input("Respiratory Rate (/min)", 0, 100, 18)
        oxygen = st.selectbox("Oxygen Support", ["Unknown", "Room air", "Supplemental oxygen"], key=f"ip_oxygen_{exam_id}")

    notes = st.text_area("Clinical Observations", key=f"ip_notes_{exam_id}")
    
    # Display who is logging it
    st.divider()
    st.caption(f"Recorded by: {current_user().get('first_name', '')} {current_user().get('last_name', '')} ({current_role_label().replace('_', ' ').title()})")
    
    if st.button("Save Round", type="primary", use_container_width=True):
        if not notes.strip():
            st.error("Please enter clinical observations.")
            return
        
        try:
            now_iso = to_utc_iso(selected_date)
            r_data = {
                "patient_id": patient["patient_id"],
                "examination_type": "Inpatient Round",
                "examination_date": now_iso,
                "status": "Completed",
                "parent_examination_id": exam_id,
                "created_by": current_user_id(),
                "reviewed_by": current_user_id(),
                "clinical_status": status,
                "diagnosis": notes.strip(),
                "chief_complaint": f"Ward Round — {status}",
            }
            ins = admin_supabase.table("examinations").insert(r_data).execute()
            if not ins.data: 
                st.error("Failed to save round."); return
            
            new_id = ins.data[0]["examination_id"]
            v_data = {
                "examination_id": new_id,
                "spo2": spo2,
                "temperature": temp,
                "respiratory_rate": rr,
                "oxygen_support": oxygen,
                "recorded_by": current_user_id(),
                "recorded_by_role": current_role_label(),
            }
            admin_supabase.table("examination_vitals").insert(v_data).execute()
            remember("Round saved.")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

# ============================================================
# DISCHARGE DIALOG
# ============================================================

@st.dialog("Physician Discharge Review", width="large")
def show_discharge_dialog(patient, admission, review):
    exam_id = admission["examination_id"]
    st.markdown(f"**{patient_name(patient)}**")
    st.caption("LungSight does not automatically discharge patients. The physician must confirm the clinical decision.")
    
    st.info("Review the latest trends and confirm the hospital's discharge criteria before approving.")
    
    c1 = st.checkbox("I reviewed the latest observations and their timestamps.")
    c2 = st.checkbox("I reviewed oxygen support and the patient's prescribed target.")
    c3 = st.checkbox("I reviewed fever history and the overall clinical course.")
    c4 = st.checkbox("I reviewed the treatment plan and post-discharge needs.")
    
    decision = st.radio("Decision", ["Continue admission", "Further assessment required", "Approve discharge"], index=0)
    discharge_notes = st.text_area("Discharge notes / instructions")
    
    schedule_fu = st.checkbox("Schedule post-discharge follow-up", value=True)
    fu_date = None
    fu_time = None
    
    if schedule_fu:
        st.markdown("**Follow-Up Appointment**")
        c_date, c_time = st.columns(2)
        
        with c_date:
            fu_date = st.date_input(
                "Follow-up Date (2-4 weeks)", 
                value=date.today() + timedelta(days=21), # Default to 3 weeks (middle of 2-4)
                min_value=date.today() + timedelta(days=14), # 2 weeks minimum
                max_value=date.today() + timedelta(days=28)  # 4 weeks maximum
            )
        with c_time:
            fu_time = st.time_input(
                "Follow-up Time", 
                value=time(9, 0) # Default 9:00 AM
            )
    
    st.divider()
    
    btn_disabled = (decision != "Approve discharge") or not all([c1, c2, c3, c4]) or not discharge_notes.strip()
    
    if st.button("Confirm Discharge", type="primary", disabled=btn_disabled, use_container_width=True):
        try:
            now_iso = datetime.now(UTC).isoformat()
            
            # Format time as HH:MM:SS for the database
            fu_time_str = fu_time.strftime("%H:%M:%S") if fu_time else None
            
            u_data = {
                "status": "Discharged",
                "time_of_discharge": now_iso,
                "discharged_by": current_user_id(),
                "discharge_notes": discharge_notes.strip(),
                "post_discharge_followup_status": "Pending" if schedule_fu else "Not Required",
                "follow_up_date": fu_date.isoformat() if schedule_fu else None,
            }
            upd = admin_supabase.table("examinations").update(u_data).eq("examination_id", exam_id).execute()
            if not upd.data: 
                st.error("Failed to update admission."); 
                return
            
            if schedule_fu:
                try:
                    existing = admin_supabase.table("follow_ups").select("*").eq("source_examination_id", exam_id).execute().data or []
                    active = [f for f in existing if f.get("status") not in ("Cancelled", "canceled")]
                    
                    if not active:
                        create_follow_up(
                            patient_id=patient["patient_id"],
                            examination_id=exam_id,
                            follow_up_date=fu_date,
                            follow_up_time=fu_time_str, # <-- PASSING THE TIME HERE
                            notes=f"Post-discharge follow-up. Confirm requirements with the treating physician.",
                            created_by=current_user_id(),
                        )
                    admin_supabase.table("examinations").update({"post_discharge_followup_status": "Scheduled"}).eq("examination_id", exam_id).execute()
                except Exception as e:
                    st.warning(f"Discharge saved, but follow-up failed: {e}")
            
            remember("Patient discharged.")
            st.session_state["ip_mode"] = "list"
            st.session_state.pop("ip_p", None)
            st.session_state.pop("ip_e", None)
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

# ============================================================
# ADMISSION LIST
# ============================================================

def render_ward_list():
    page_header("Admission Tracking", "Track admitted patients, log rounds, and evaluate clinical readiness for discharge.")
    
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
    m2.metric("Needs Review", len(admissions))
    m3.metric("Rounds Today", rounds_today)

    section_title("Current Admissions")
    if not admissions:
        empty_state("No patients are currently admitted.")
        return

    for a in admissions:
        p = a.get("patients") or {}
        admit_id = a.get("examination_id")  # Use unique exam ID for keys
        admit_day = as_date(a.get("time_in") or a.get("examination_date"))
        h_day = max(1, (date.today() - admit_day).days + 1)
        
        with st.container(key=f"ip_card_{admit_id}"):  # <-- Unique key
            st.markdown(
                f"<p class='ip-patient-name'>{patient_name(p)}</p>"
                f"<p class='ip-patient-meta'>Hospital Day {h_day} · Admitted {format_date(admit_day)}</p>",
                unsafe_allow_html=True,
            )
        if st.button("Open Monitoring", key=f"ip_btn_{admit_id}", use_container_width=True): # <-- Unique key
            go_to_admission(p, a)


# ============================================================
# ADMISSION DETAIL
# ============================================================

def render_patient_detail():
    e_id = (st.session_state.get("ip_e") or {}).get("examination_id")
    if not e_id: back_to_admissions(); return
    
    admission = get_admission_record(e_id)
    if not admission:
        st.error("Admission not found."); return
    
    p = admission.get("patients") or {}
    if st.button("← Back to Ward", key="ip_back"): back_to_admissions()

    admit_day = as_date(admission.get("time_in") or admission.get("examination_date"))
    page_header("Inpatient Monitoring", f"{patient_name(p)} · Admitted {format_date(admit_day)}")

    # Fetch Rounds & Vitals
    try:
        rounds = load_rounds(e_id)
        v_map = load_vitals([r["examination_id"] for r in rounds])
        history = []
        chart_data = []
        
        for r in rounds:
            v = v_map.get(r["examination_id"])
            if v:
                merged = dict(v)
                merged["examination_date"] = r.get("examination_date")
                history.append(merged)
        
        for h in reversed(history):
            chart_data.append({
                "Date": format_date(h.get("examination_date")),
                "SpO2": h.get("spo2"),
                "Temp": h.get("temperature"),
                "RR": h.get("respiratory_rate"),
            })
    except Exception:
        rounds, v_map, history, chart_data = [], {}, [], []

    readiness = calculate_discharge_readiness(history)
    
    # Clinical Decision Support
    section_title("Clinical Decision Support")
    if not readiness["alerts"]:
        st.success("No clinical flags detected from the latest observation.")
    else:
        for a in readiness["alerts"]:
            st.warning(a)

    section_title("Discharge Readiness Checklist")
    c1, c2, c3 = st.columns(3)
    c1.checkbox("Afebrile for > 24h", value=readiness["checklist"].get("afebrile", False), disabled=True)
    c2.checkbox("SpO₂ ≥ 92% on room air", value=readiness["checklist"].get("spo2_stable", False), disabled=True)
    c3.checkbox("Respiratory rate < 24 / min", value=readiness["checklist"].get("rr_normal", False), disabled=True)
    
    st.markdown(f"<p class='ip-status-line'>Overall Status: {pill(readiness['status'], readiness['tone'])}</p>", unsafe_allow_html=True)

    # Table
    section_title("Daily Rounds")
    if not rounds:
        st.info("No rounds logged.")
    else:
        # Adjusted widths to include Clinical Status and Recorded By
        widths = [1.2, 0.6, 1.0, 0.7, 0.7, 0.8, 2.0, 1.0]
        with st.container(key="ip_rounds_header"):
            h1, h2, h3, h4, h5, h6, h7, h8 = st.columns(widths)
            h1.markdown("<span class='ip-th'>Date & Time</span>", unsafe_allow_html=True)
            h2.markdown("<span class='ip-th'>Day</span>", unsafe_allow_html=True)
            h3.markdown("<span class='ip-th'>Status</span>", unsafe_allow_html=True)
            h4.markdown("<span class='ip-th'>SpO₂</span>", unsafe_allow_html=True)
            h5.markdown("<span class='ip-th'>Temp</span>", unsafe_allow_html=True)
            h6.markdown("<span class='ip-th'>RR</span>", unsafe_allow_html=True)
            h7.markdown("<span class='ip-th'>Notes</span>", unsafe_allow_html=True)
            h8.markdown("<span class='ip-th'>Recorded By</span>", unsafe_allow_html=True)

        for r in rounds:
            v = v_map.get(r["examination_id"], {})
            dt_str = r.get("examination_date")
            if dt_str:
                dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00")).astimezone(MANILA_TZ)
                date_str = dt.strftime("%b %d, %I:%M %p")
                rd = dt.date()
            else:
                date_str = "—"
                rd = date.today()
            
            r_day = max(1, (rd - admit_day).days + 1)
            status_label = r.get("clinical_status") or "—"
            recorded_by = load_user_name(r.get("created_by"))
            
            with st.container(key=f"ip_round_row_{r['examination_id']}"):
                c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(widths, vertical_alignment="center")
                c1.markdown(f"<span class='ip-cell-strong'>{date_str}</span>", unsafe_allow_html=True)
                c2.markdown(f"<span class='ip-cell'>Day {r_day}</span>", unsafe_allow_html=True)
                c3.markdown(f"<span class='ip-cell'>{status_label}</span>", unsafe_allow_html=True)
                c4.markdown(f"<span class='ip-cell'>{v.get('spo2')}%</span>", unsafe_allow_html=True)
                c5.markdown(f"<span class='ip-cell'>{v.get('temperature')}°C</span>", unsafe_allow_html=True)
                c6.markdown(f"<span class='ip-cell'>{v.get('respiratory_rate')}/min</span>", unsafe_allow_html=True)
                c7.markdown(f"<span class='ip-cell-notes'>{r.get('diagnosis') or '—'}</span>", unsafe_allow_html=True)
                c8.markdown(f"<span class='ip-cell'>{recorded_by}</span>", unsafe_allow_html=True)

    # Charts
    if chart_data:
        import altair as alt
        import pandas as pd

        st.write("")
        section_title("Clinical Trend")

        df = pd.DataFrame(chart_data)

        # Shared style for all three charts
        base = (
            alt.Chart(df)
            .mark_line(point=True, strokeWidth=2.5)
            .properties(height=220, padding={"left": 10, "right": 10, "top": 15, "bottom": 10})
            .configure_axis(
                labelFontSize=11,
                labelColor="#4A677B",
                titleFontSize=0,
                gridColor="#EEF3F5",
                domainColor="#DCE7EB",
            )
            .configure_view(strokeWidth=0)
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.caption("SpO₂ (%)")
            st.altair_chart(
                base.encode(
                    x=alt.X("Date:N", axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y("SpO2:Q", scale=alt.Scale(domain=[60, 100])),
                    color=alt.value("#0F7C88"),
                ),
                use_container_width=True,
            )

        with col2:
            st.caption("Temperature (°C)")
            st.altair_chart(
                base.encode(
                    x=alt.X("Date:N", axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y("Temp:Q", scale=alt.Scale(domain=[35, 42])),
                    color=alt.value("#B45309"),
                ),
                use_container_width=True,
            )

        with col3:
            st.caption("Resp Rate (/min)")
            st.altair_chart(
                base.encode(
                    x=alt.X("Date:N", axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y("RR:Q", scale=alt.Scale(domain=[10, 40])),
                    color=alt.value("#B91C1C"),
                ),
                use_container_width=True,
            )

        st.write("")

    act1, act2 = st.columns(2)
    if act1.button("+ Log New Daily Round", use_container_width=True):
        show_log_round_dialog(p, admission)
    
    if act2.button("Review Discharge", type="primary", use_container_width=True, disabled=not readiness["can_discharge"]):
        show_discharge_dialog(p, admission, readiness)

# ============================================================
# PAGE
# ============================================================

def show():
    load_css("inpatient_dashboard.css")
    show_flash_message()

    with st.container(key="physician_inpatient_page"):
        if st.session_state.get("ip_mode") == "detail":
            render_patient_detail()
        else:
            render_ward_list()