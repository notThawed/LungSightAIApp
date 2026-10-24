# streamlit_app/pages/physician/inpatient_dashboard.py

import streamlit as st
from datetime import datetime, timezone, date, timedelta

from backend.supabase_client import admin_supabase
from backend.backend_utils.inpatient_utils import calculate_discharge_readiness
from streamlit_app.components.ui import (
    page_header, empty_state, section_title, pill, remember, show_flash_message
)
from shared.assets import load_css


# ============================================================
# HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}


def current_user_id():
    return current_user().get("user_id")


def patient_name(p):
    if not p:
        return "—"
    return f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()


def format_date(v):
    if not v:
        return "—"
    return datetime.fromisoformat(str(v)[:10]).strftime("%b %d, %Y")


def go_to_discharge(p, exam):
    st.session_state["ip_p"] = p
    st.session_state["ip_e"] = exam
    st.session_state["ip_mode"] = "detail"
    st.rerun()


def back_to_ward():
    st.session_state.pop("ip_p", None)
    st.session_state.pop("ip_e", None)
    st.session_state["ip_mode"] = "list"
    st.rerun()


# ============================================================
# DIALOGS
# ============================================================

@st.dialog("Log Inpatient Round")
def show_log_round_dialog(patient, parent_exam, admit_date):

    st.markdown(f"**{patient_name(patient)}**")
    st.caption(parent_exam.get("diagnosis") or "—")
    st.divider()

    # ==========================================
    # MANUAL DATE SELECTOR
    # ==========================================
    st.markdown("**Round Date**")
    st.caption("Defaults to today. Cannot be before admission.")
    
    # Force admit_date to be a date object for the min_value
    try:
        if isinstance(admit_date, str):
            min_date = date.fromisoformat(str(admit_date)[:10])
        else:
            min_date = admit_date
    except Exception:
        min_date = date.today()

    selected_date = st.date_input(
        "Date of Round",
        value=date.today(),
        min_value=min_date,
        label_visibility="collapsed",
        key=f"round_date_{parent_exam['examination_id']}"
    )

    
    st.divider()

    # Fetch last round's vitals to pre-fill
    last_vitals = {}
    try:
        res = (
            admin_supabase.table("examinations")
            .select("examination_id")
            .eq("parent_examination_id", parent_exam["examination_id"])
            .order("examination_date", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            last_exam_id = res.data[0]["examination_id"]
            v_res = (
                admin_supabase.table("examination_vitals")
                .select("*")
                .eq("examination_id", last_exam_id)
                .execute()
            )
            if v_res.data:
                last_vitals = v_res.data[0]
    except Exception:
        last_vitals = {}

    default_spo2 = int(last_vitals.get("spo2") or 95)
    default_temp = float(last_vitals.get("temperature") or 36.8)
    default_rr = int(last_vitals.get("respiratory_rate") or 18)
    default_bp = int(last_vitals.get("bp_systolic") or 120)

    c1, c2 = st.columns(2)
    with c1:
        spo2 = st.number_input("SpO₂ (%)", min_value=0, max_value=100, value=default_spo2)
        temp = st.number_input("Temperature (°C)", min_value=30.0, max_value=45.0, value=default_temp, step=0.1)
    with c2:
        rr = st.number_input("Respiratory Rate (/min)", min_value=0, max_value=100, value=default_rr)
        bp = st.number_input("BP Systolic", min_value=0, max_value=300, value=default_bp)

    notes = st.text_area("Clinical Observations")
    st.divider()

    if st.button("Save Round", type="primary", use_container_width=True):
        try:
            # Combine the selected date with the current time
            now_utc = datetime.now(timezone.utc)
            combined_datetime = datetime.combine(selected_date, now_utc.time(), tzinfo=timezone.utc)

            e_data = {
                "patient_id": patient["patient_id"],
                "examination_type": "Inpatient Round",
                "examination_date": combined_datetime.isoformat(),
                "status": "Completed",
                "parent_examination_id": parent_exam["examination_id"],
                "created_by": current_user_id(),
                "reviewed_by": current_user_id(),
                "diagnosis": notes,
                "chief_complaint": "Ward Round",
            }
            res = admin_supabase.table("examinations").insert(e_data).execute()
            if not res.data:
                st.error("Failed to create round.")
                return

            new_id = res.data[0]["examination_id"]
            admin_supabase.table("examination_vitals").insert({
                "examination_id": new_id,
                "spo2": spo2,
                "temperature": temp,
                "respiratory_rate": rr,
                "bp_systolic": bp,
                "recorded_by": current_user_id(),
                "recorded_by_role": "doctor",
            }).execute()

            remember("Round logged.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")


@st.dialog("Discharge Patient & Schedule Follow-Up")
def show_discharge_dialog(patient, exam):

    st.markdown(f"**{patient_name(patient)}**")
    st.caption(
        "Patient meets discharge criteria. Schedule a post-discharge "
        "follow-up X-ray in 4 to 6 weeks to confirm radiological clearance."
    )
    st.divider()

    if st.button("Mark as Discharged & Schedule Follow-Up", type="primary", use_container_width=True):
        admin_supabase.table("examinations").update({
            "status": "Discharged",
            "time_of_discharge": datetime.now(timezone.utc).isoformat(),
        }).eq("examination_id", exam["examination_id"]).execute()

        st.session_state["ip_mode"] = "list"
        st.session_state["review_examination"] = exam
        st.session_state["review_patient"] = patient
        st.session_state["review_schedule_followup_open"] = True
        st.rerun()


# ============================================================
# WARD LIST VIEW
# ============================================================

def render_ward_list():

    page_header(
        "Inpatient Monitoring",
        "Oversee admitted patients, record daily rounds, and evaluate clinical readiness for discharge.",
    )

    admitted = []
    try:
        res = (
            admin_supabase.table("examinations")
            .select("*, patients(*)")
            .eq("disposition", "Admission")
            .eq("status", "Admitted")
            .execute()
        )
        admitted = res.data or []
    except Exception as e:
        st.error(f"Failed to load admissions: {e}")

    rounds_today_count = 0
    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        res_today = (
            admin_supabase.table("examinations")
            .select("examination_id")
            .eq("examination_type", "Inpatient Round")
            .gte("examination_date", today_start.isoformat())
            .execute()
        )
        rounds_today_count = len(res_today.data) if res_today.data else 0
    except Exception:
        rounds_today_count = 0

    m1, m2, m3 = st.columns(3)
    m1.metric("Currently Admitted", len(admitted))
    m2.metric("Needs Review", len(admitted))
    m3.metric("Rounds Today", rounds_today_count)

    section_title("Current Admissions")

    if not admitted:
        empty_state("No patients are currently admitted.")
        return

    for e in admitted:
        p = e.get("patients") or {}

        admit_date_str = e.get("updated_at") or e.get("examination_date")
        try:
            db_date_part = str(admit_date_str)[:10]
            admit_day = date.fromisoformat(db_date_part)
            today = date.today()
            days_admitted = (today - admit_day).days + 1
            if days_admitted < 1:
                days_admitted = 1
        except Exception as ex:
            days_admitted = 1
            print(f"Date parse error: {ex}")

        with st.container(key=f"ip_card_{p.get('patient_id')}"):
            st.markdown(
                f"<p class='ip-patient-name'>{patient_name(p)}</p>"
                f"<p class='ip-patient-meta'>Hospital Day {days_admitted} "
                f"· Admitted {format_date(admit_date_str)}</p>",
                unsafe_allow_html=True,
            )

        if st.button(
            "Open Monitoring",
            key=f"ip_btn_{p.get('patient_id')}",
            use_container_width=True,
        ):
            go_to_discharge(p, e)


# ============================================================
# PATIENT DETAIL VIEW
# ============================================================

def render_patient_detail():

    if st.button("← Back to Ward", key="ip_back"):
        back_to_ward()

    p = st.session_state["ip_p"]
    e = st.session_state["ip_e"]
    exam_id = e["examination_id"]

    # Get admission date for Hospital Day calculation
    admit_date_str = e.get("updated_at") or e.get("examination_date")
    try:
        db_date_part = str(admit_date_str)[:10]
        admit_day = date.fromisoformat(db_date_part)
    except Exception:
        admit_day = date.today()

    try:
        res = (
            admin_supabase.table("examinations")
            .select("*")
            .eq("parent_examination_id", exam_id)
            .order("examination_date", desc=True)
            .execute()
        )
        rounds = res.data or []
        v_map = {}
        for r in rounds:
            v = (
                admin_supabase.table("examination_vitals")
                .select("*")
                .eq("examination_id", r["examination_id"])
                .execute()
            )
            if v.data:
                v_map[r["examination_id"]] = v.data[0]
        history = [v_map[r["examination_id"]] for r in rounds if r["examination_id"] in v_map]

        chart_data = []
        for r in reversed(rounds):
            v = v_map.get(r["examination_id"])
            if v:
                chart_data.append({
                    "Date": format_date(r.get("examination_date")),
                    "SpO2": v.get("spo2"),
                    "Temp": v.get("temperature"),
                    "RR": v.get("respiratory_rate"),
                })
    except Exception:
        rounds, v_map, history, chart_data = [], {}, [], []

    page_header(
        "Inpatient Monitoring",
        f"{patient_name(p)} · Admitted {format_date(admit_date_str)}",
    )

    readiness = calculate_discharge_readiness(history)
    section_title("Clinical Decision Support")

    if not readiness["alerts"]:
        st.success("No red flags detected. Patient is trending in the correct direction.")
    else:
        for a in readiness["alerts"]:
            st.error(a)

    section_title("Discharge Readiness Checklist")

    c1, c2, c3 = st.columns(3)
    c1.checkbox("Afebrile for > 24 hours", value=readiness["checklist"].get("afebrile", False), disabled=True)
    c2.checkbox("SpO₂ ≥ 92% on room air", value=readiness["checklist"].get("spo2_stable", False), disabled=True)
    c3.checkbox("Respiratory rate < 24 / min", value=readiness["checklist"].get("rr_normal", False), disabled=True)

    st.markdown(
        f"<p class='ip-status-line'>Overall Status: {pill(readiness['status'], readiness['tone'])}</p>",
        unsafe_allow_html=True,
    )

    # -------- Daily Rounds Table --------
    section_title("Daily Rounds")

    if not rounds:
        st.info("No rounds have been logged for this admission.")
    else:
        widths = [1.3, 0.7, 0.7, 0.7, 0.9, 3.0]
        
        with st.container(key="ip_rounds_header"):
            h1, h2, h3, h4, h5, h6 = st.columns(widths)
            h1.markdown("<span class='ip-th'>Date & Time</span>", unsafe_allow_html=True)
            h2.markdown("<span class='ip-th'>Day</span>", unsafe_allow_html=True)
            h3.markdown("<span class='ip-th'>SpO₂</span>", unsafe_allow_html=True)
            h4.markdown("<span class='ip-th'>Temp</span>", unsafe_allow_html=True)
            h5.markdown("<span class='ip-th'>Resp. Rate</span>", unsafe_allow_html=True)
            h6.markdown("<span class='ip-th'>Clinical Notes</span>", unsafe_allow_html=True)

        for r in rounds:
            v = v_map.get(r["examination_id"], {})
            
            dt_str = r.get("examination_date")
            if dt_str:
                dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
                ph_tz = timezone(timedelta(hours=8))
                dt_ph = dt.astimezone(ph_tz)
                date_time_str = dt_ph.strftime("%b %d, %I:%M %p")
                round_date = dt_ph.date()
            else:
                date_time_str = "—"
                round_date = date.today()

            try:
                round_day_num = (round_date - admit_day).days + 1
                if round_day_num < 1:
                    round_day_num = 1
                day_str = f"Day {round_day_num}"
            except Exception:
                day_str = "—"

            with st.container(key=f"ip_round_row_{r['examination_id']}"):
                c1, c2, c3, c4, c5, c6 = st.columns(widths, vertical_alignment="center")
                
                c1.markdown(f"<span class='ip-cell-strong'>{date_time_str}</span>", unsafe_allow_html=True)
                c2.markdown(f"<span class='ip-cell'>{day_str}</span>", unsafe_allow_html=True)
                c3.markdown(f"<span class='ip-cell'>{v.get('spo2')}%</span>", unsafe_allow_html=True)
                c4.markdown(f"<span class='ip-cell'>{v.get('temperature')}°C</span>", unsafe_allow_html=True)
                c5.markdown(f"<span class='ip-cell'>{v.get('respiratory_rate')}/min</span>", unsafe_allow_html=True)
                
                notes = r.get("diagnosis") or "—"
                c6.markdown(f"<span class='ip-cell-notes'>{notes}</span>", unsafe_allow_html=True)

    # -------- Clinical Trend --------
    if chart_data:
        section_title("Clinical Trend")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.caption("SpO₂ (%)")
            st.line_chart([{"Date": d["Date"], "SpO2": d["SpO2"]} for d in chart_data], x="Date", y="SpO2", color="#0F7C88")
        with c2:
            st.caption("Temperature (°C)")
            st.line_chart([{"Date": d["Date"], "Temp": d["Temp"]} for d in chart_data], x="Date", y="Temp", color="#B45309")
        with c3:
            st.caption("Respiratory Rate (/min)")
            st.line_chart([{"Date": d["Date"], "RR": d["RR"]} for d in chart_data], x="Date", y="RR", color="#B91C1C")

    # -------- Actions --------
    st.write("")
    c1, c2 = st.columns(2)

    if c1.button("+ Log New Daily Round", use_container_width=True):
        # PASS THE admit_day TO THE DIALOG
        show_log_round_dialog(p, e, admit_day)

    if c2.button("Mark as Discharged", type="primary", use_container_width=True, disabled=(readiness["score"] < 3)):
        show_discharge_dialog(p, e)


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