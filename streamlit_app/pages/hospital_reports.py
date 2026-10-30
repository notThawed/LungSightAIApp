"""
Hospital Reports — Hospital Admin (own hospital, full detail) and Superadmin
(any hospital, aggregates only).

Scope, numbers and exports all come from backend.reports; this page only
collects the period, shows the immutable report and offers the exports.
"""

import logging
from datetime import date

import streamlit as st

from backend import audit
from backend.reports import data as report_data
from backend.reports import service
from backend.reports.calculations import format_minutes
from backend.reports.periods import (
    REPORT_TZ,
    REPORT_TZ_LABEL,
    custom_period,
    monthly_period,
    weekly_period,
)
from streamlit_app.components.ui import (
    empty_state,
    page_header,
    section_title,
    safe,
    pill,
    show_rows,
)
from shared.assets import load_css


logger = logging.getLogger("lungsight.reports")

REPORT_KEY = "hospital_report"
EXPORT_KEY = "hospital_report_exports"

PERIOD_KINDS = ("Weekly", "Monthly", "Custom")
MONTHS = [date(2000, m, 1).strftime("%B") for m in range(1, 13)]

SECTION_TITLES = {
    "screening": "Screening Activity",
    "ai": "AI Screening Outcomes",
    "review": "Physician Review & Concordance",
    "operations": "Operational Efficiency",
}


# ============================================================
# CONTROLS
# ============================================================

def _today_local():
    from datetime import datetime

    return datetime.now(REPORT_TZ).date()


def _period_controls():
    today = _today_local()

    kind = st.radio("Reporting Period", PERIOD_KINDS, horizontal=True, key="report_period_kind")

    if kind == "Weekly":
        day = st.date_input("Select any day in target week", value=today, key="report_week_day")
        return weekly_period(day)

    if kind == "Monthly":
        c1, c2 = st.columns(2)
        month = c1.selectbox("Month", MONTHS, index=today.month - 1, key="report_month")
        year = c2.number_input(
            "Year", min_value=2020, max_value=today.year + 1, value=today.year, step=1, key="report_year"
        )
        return monthly_period(int(year), MONTHS.index(month) + 1)

    picked = st.date_input("Date range", value=(today.replace(day=1), today), key="report_custom_range")
    if not isinstance(picked, (tuple, list)) or len(picked) != 2:
        raise ValueError("Choose both a start and an end date.")
    return custom_period(picked[0], picked[1])


def _hospital_control():
    hospitals = report_data.list_report_hospitals()

    if not hospitals:
        raise ValueError("No hospitals are registered yet.")

    names = {h["hospital_name"] or h["hospital_id"]: h["hospital_id"] for h in hospitals}
    choice = st.selectbox("Healthcare Facility", sorted(names), key="report_hospital")
    return names[choice]


# ============================================================
# RENDERING
# ============================================================

def _metric_grid(metrics):
    columns = st.columns(4)

    for index, metric in enumerate(metrics):
        with columns[index % 4]:
            if metric.unit == "minutes":
                value = format_minutes(metric.value) if metric.value is not None else "Not available"
                caption = f"n = {metric.denominator}"
            else:
                value = f"{metric.value:,}"
                caption = ""
                if metric.denominator is not None:
                    pct = metric.pct
                    caption = f"of {metric.denominator:,}" + (f" · {pct:.1f}%" if pct is not None else " · n/a")

            lbl_lower = metric.label.lower()
            if "abnormal" in lbl_lower or "flagged" in lbl_lower:
                tone = "amber"
                icon = "warning"
            elif "critical" in lbl_lower or "high risk" in lbl_lower or "failure" in lbl_lower:
                tone = "red"
                icon = "emergency"
            elif "normal" in lbl_lower or "reviewed" in lbl_lower or "concordance" in lbl_lower:
                tone = "green"
                icon = "check_circle"
            elif "analysed" in lbl_lower or "turnaround" in lbl_lower:
                tone = "blue"
                icon = "radiology"
            else:
                tone = "teal"
                icon = "analytics"

            caption_div = f"<div style='font-size:0.75rem; color:var(--sa-slate); margin-top:2px;'>{safe(caption)}</div>" if caption else ""

            st.markdown(
                f"<div class='sa-metric sa-metric-{tone}' title='{safe(metric.note or '')}'>"
                f"<div class='sa-metric-icon'><span class='material-symbols-rounded'>{icon}</span></div>"
                f"<div>"
                f"<div class='sa-metric-title'>{safe(metric.label)}</div>"
                f"<div class='sa-metric-value'>{value}</div>"
                f"{caption_div}"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )


def _breakdown_table(breakdown):
    st.markdown(f"**{breakdown.title}** (n = {breakdown.denominator:,})")

    if not breakdown.items:
        st.caption("No data recorded in this period.")
        return

    st.dataframe(
        [
            {
                "Category": label,
                "Count": count,
                "Percent": f"{breakdown.pct(count):.1f}%" if breakdown.pct(count) is not None else "n/a",
            }
            for label, count in breakdown.items
        ],
        hide_index=True,
        width="stretch",
    )


def _activity_tab(report):
    if report.metric("exams_registered").value == 0:
        empty_state("No examinations were registered in this period. All metrics below are zero.")

    for section, title in SECTION_TITLES.items():
        st.markdown(f"<div class='sa-report-section-header'>{title}</div>", unsafe_allow_html=True)
        _metric_grid(report.section_metrics(section))

        if section == "screening":
            st.markdown(f"**Examinations Trend per {report.trend_granularity.capitalize()}**")
            st.bar_chart(
                [
                    {
                        "Period": b.label,
                        "Registered": b.registered,
                        "Analysed": b.analyzed,
                        "Reviewed": b.reviewed,
                    }
                    for b in report.trend
                ],
                x="Period",
                y=["Registered", "Analysed", "Reviewed"],
                stack=False,
            )
            st.caption("Grouped by registration date; totals equal the KPI metrics above.")

        if section == "ai":
            st.bar_chart(
                [
                    {"Outcome": m.label, "Examinations": m.value}
                    for m in report.section_metrics("ai")
                ],
                x="Outcome",
                y="Examinations",
            )
            st.caption("AI screening flags serve as clinical decision support, not an independent diagnosis.")

        breakdowns = report.section_breakdowns(section)
        if breakdowns:
            columns = st.columns(len(breakdowns))
            for column, breakdown in zip(columns, breakdowns):
                with column:
                    _breakdown_table(breakdown)

        st.divider()


def _system_tab(report):
    activity = report.audit_activity

    if activity is None:
        empty_state("System activity logs are unavailable for this report.")
        return

    st.caption(activity.note)

    if activity.total == 0:
        empty_state("No audit events were recorded for this hospital in this period.")
        return

    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown(
            f"<div class='sa-metric sa-metric-teal'>"
            f"<div class='sa-metric-icon'><span class='material-symbols-rounded'>history</span></div>"
            f"<div>"
            f"<div class='sa-metric-title'>Audit Events</div>"
            f"<div class='sa-metric-value'>{activity.total:,}</div>"
            f"<div style='font-size:0.75rem; color:var(--sa-slate);'>Total logged actions</div>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.dataframe(
            [{"Measure": label, "Count": count} for label, count in activity.highlights],
            hide_index=True,
            width="stretch",
        )

    d1, d2 = st.columns(2)
    with d1:
        st.markdown("**By Category**")
        st.dataframe(
            [{"Category": k, "Count": v} for k, v in activity.by_category],
            hide_index=True,
            width="stretch",
        )
    with d2:
        st.markdown("**By Outcome**")
        st.dataframe(
            [{"Outcome": k, "Count": v} for k, v in activity.by_outcome],
            hide_index=True,
            width="stretch",
        )


def _definitions_tab(report):
    for term, definition in report.definitions:
        st.markdown(f"**{term}.** {definition}")

    st.markdown("**Clinical Limitations**")
    for item in report.limitations:
        st.markdown(f"- {item}")


def _exports(report):
    cache = st.session_state.setdefault(EXPORT_KEY, {})

    if cache.get("report_id") != report.report_id:
        cache.clear()
        cache["report_id"] = report.report_id

    if report.patient_level:
        export_note = "Excel export includes examination-level breakdown sheets (internal IDs and patient codes only, names masked)."
        if report.exam_rows_capped:
            export_note += (
                f" Only the first {len(report.exam_rows):,} of {report.exam_rows_total:,} "
                "examinations are included; narrow the timeframe for the full list."
            )
    else:
        export_note = "Platform administrator view: exports contain validated aggregate figures and KPI summaries."

    st.markdown(
        f"<div class='sa-report-export-box'>"
        f"<div class='sa-report-export-title'>Export Report Documents</div>"
        f"<div class='sa-report-export-desc'>{export_note}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    for column, fmt, label in ((c1, "pdf", "PDF Report"), (c2, "xlsx", "Excel Spreadsheet")):
        with column:
            ready = cache.get(fmt)

            if ready:
                st.download_button(
                    f"Download {label}",
                    data=ready["data"],
                    file_name=ready["filename"],
                    mime=ready["mime"],
                    icon=":material/download:",
                    key=f"report_download_{fmt}",
                    width="stretch",
                )
                continue

            if st.button(
                f"Generate {label}",
                icon=":material/description:",
                key=f"report_prepare_{fmt}",
                width="stretch",
                type="primary" if fmt == "pdf" else "secondary",
            ):
                try:
                    with st.spinner(f"Preparing {label}..."):
                        data, filename, mime = service.export_hospital_report(report, fmt)
                    cache[fmt] = {"data": data, "filename": filename, "mime": mime}
                    st.rerun()
                except audit.AuditAccessDenied as exc:
                    st.error(str(exc))
                except service.ReportExportError as exc:
                    logger.error("report export failed: %s", fmt)
                    st.error(f"{exc} No file was created.")


def _render(report):
    st.markdown(
        f"<div class='sa-report-banner'>"
        f"<div class='sa-report-banner-left'>"
        f"<div class='sa-report-hosp-chip'>"
        f"<svg width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='#0F7C88' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M3 21h18'/><path d='M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16'/><path d='M9 21v-4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v4'/><path d='M10 9h4'/><path d='M12 7v4'/></svg>"
        f"<h3>{safe(report.hospital_name)}</h3>"
        f"</div>"
        f"<div class='sa-report-meta-tags'>"
        f"<span class='sa-meta-tag'>📅 Period: <b>{safe(report.period_label)}</b></span>"
        f"<span class='sa-meta-tag'>🕒 Generated: <b>{safe(report.generated_at_local)} (PH)</b></span>"
        f"<span class='sa-meta-tag code'>🆔 <code>{safe(report.report_id[:12])}...</code></span>"
        f"</div>"
        f"</div>"
        f"<div class='sa-report-banner-right'>"
        f"{pill('Verified Report', 'green')}"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    tabs = st.tabs(["Screening & Clinical Activity", "System Audit Logs", "AI Performance Matrix", "Definitions & Scope"])

    with tabs[0]:
        _activity_tab(report)
    with tabs[1]:
        _system_tab(report)
    with tabs[2]:
        empty_state(report.report_b_status)
    with tabs[3]:
        _definitions_tab(report)

    st.divider()
    _exports(report)
    st.caption(report.disclaimer)


# ============================================================
# PAGE
# ============================================================

def show():
    load_css("reports.css")

    try:
        scope = audit.get_viewer_scope(report_data.RESOURCE)
    except audit.AuditAccessDenied as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        logger.error("report scope check failed: %s", type(exc).__name__)
        st.error("Unable to verify your access right now. Please try again.")
        return

    page_header(
        "Hospital Reports",
        f"Generate and analyze screening throughput, AI outcomes, and physician review statistics. Times follow {REPORT_TZ_LABEL}.",
    )

    with st.container(key="sa_report_controls"):
        section_title("Report Generator", "Filter by facility and select the reporting period.")

        try:
            ctrl_col1, ctrl_col2 = st.columns([1.5, 2.5], gap="medium")
            with ctrl_col1:
                hospital_id = _hospital_control() if scope["platform"] else scope["hospital_id"]
            with ctrl_col2:
                period = _period_controls()
        except ValueError as exc:
            st.warning(str(exc))
            return
        except Exception as exc:
            logger.error("report controls failed: %s", type(exc).__name__)
            st.error("Report options could not be loaded. Please try again.")
            return

        signature = (hospital_id, period.kind, period.start.isoformat(), period.end.isoformat())
        stored = st.session_state.get(REPORT_KEY)

        if st.button("Generate Official Report", type="primary", icon=":material/analytics:", key="report_generate"):
            try:
                with st.spinner("Generating and verifying clinical report..."):
                    report = service.generate_hospital_report(period, hospital_id)
                stored = {"signature": signature, "report": report}
                st.session_state[REPORT_KEY] = stored
                st.session_state.pop(EXPORT_KEY, None)
                st.rerun()
            except audit.AuditAccessDenied as exc:
                st.error(str(exc))
                return
            except ValueError as exc:
                st.warning(str(exc))
                return
            except Exception as exc:
                logger.error("report generation failed: %s", type(exc).__name__)
                st.error("The report could not be generated. Please try again.")
                return

    if not stored:
        empty_state("Select a healthcare facility and reporting period above, then click 'Generate Official Report'.")
        return

    if stored["signature"] != signature:
        st.info("Reporting parameters changed. Click 'Generate Official Report' to refresh the figures below.")

    _render(stored["report"])
