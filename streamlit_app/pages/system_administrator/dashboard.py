import calendar
from datetime import date

import altair as alt
import streamlit as st

from backend.backend_utils.dashboard_utils import (
    get_ai_daily_counts,
    get_hospital_overview,
    get_system_metrics,
)

from streamlit_app.components.ui import (
    empty_state,
    page_header,
    section_title,
)
from streamlit_app.components.role_dashboard import show_metric_row

from shared.assets import load_css



# ============================================================
# CALENDAR
# Built as plain HTML (no iframe), styled by dashboard.css
# ============================================================

def show_calendar():

    today = date.today()

    weekdays = "".join(
        f"<div class='sa-cal-head'>{name}</div>"
        for name in ("Su", "Mo", "Tu", "We", "Th", "Fr", "Sa")
    )

    days = ""

    # Sunday is the first day of the week, like the original calendar
    for week in calendar.Calendar(firstweekday=6).monthdayscalendar(today.year, today.month):
        for day in week:

            if day == 0:
                days += "<div class='sa-cal-day sa-cal-empty'></div>"
            elif day == today.day:
                days += f"<div class='sa-cal-day sa-cal-today'>{day}</div>"
            else:
                days += f"<div class='sa-cal-day'>{day}</div>"

    st.markdown(
        "<div class='sa-cal'>"
        f"<p class='sa-cal-title'>{calendar.month_name[today.month]} {today.year}</p>"
        f"<div class='sa-cal-grid'>{weekdays}{days}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# DATA (cached briefly; the Refresh button clears it)
# ============================================================

# Categorical pair validated for color-vision deficiency (dataviz validator).
AI_NEGATIVE_COLOR = "#2A5FA8"
AI_POSITIVE_COLOR = "#C2410C"


@st.cache_data(ttl=60, show_spinner=False)
def load_dashboard_data():
    metrics = get_system_metrics()

    try:
        daily = get_ai_daily_counts(days=14)
    except Exception as exc:
        print(f"[dashboard] daily AI counts failed: {exc}")
        daily = None

    try:
        hospitals = get_hospital_overview()
    except Exception as exc:
        print(f"[dashboard] hospital overview failed: {exc}")
        hospitals = None

    return metrics, daily, hospitals


def ai_activity_chart(daily):
    """Stacked daily bars: AI negative (bottom) and AI positive (top)."""

    rows = [
        {"date": day["date"], "finding": finding, "count": day[key], "order": order}
        for day in daily
        for order, (key, finding) in enumerate((("negative", "AI negative"), ("positive", "AI positive")))
    ]

    return (
        alt.Chart(alt.Data(values=rows))
        .mark_bar(cornerRadiusEnd=4, stroke="white", strokeWidth=2)
        .encode(
            x=alt.X("date:T", timeUnit="yearmonthdate", title=None,
                    axis=alt.Axis(format="%b %d", labelAngle=0, grid=False, tickCount=7)),
            y=alt.Y("sum(count):Q", title="Analyses", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color(
                "finding:N",
                scale=alt.Scale(domain=["AI negative", "AI positive"], range=[AI_NEGATIVE_COLOR, AI_POSITIVE_COLOR]),
                legend=alt.Legend(title=None, orient="top"),
            ),
            order=alt.Order("order:Q"),
            tooltip=[
                alt.Tooltip("date:T", title="Date", format="%b %d, %Y"),
                alt.Tooltip("finding:N", title="AI finding"),
                alt.Tooltip("count:Q", title="Analyses"),
            ],
        )
        .properties(height=260)
        .configure_view(stroke=None)
    )


# ============================================================
# PAGE
# ============================================================

def show():

    load_css("dashboard.css")

    with st.container(key="sa_page"):

        if page_header(
            "Administrator dashboard",
            "System-wide activity across hospitals, users and AI analyses.",
            "Refresh",
            "sa_dashboard_refresh",
            "refresh",
        ):
            load_dashboard_data.clear()
            st.rerun()

        metrics, daily, hospitals = load_dashboard_data()

        show_metric_row(metrics)

        # ---------------- AI activity + calendar ----------------

        chart_col, calendar_col = st.columns([3, 1.2], gap="medium")

        with chart_col:
            with st.container(key="sa_card_chart"):

                section_title(
                    "AI analyses per day",
                    "Last 14 days, by AI finding. AI findings are not diagnoses.",
                )

                if daily is None:
                    empty_state("AI activity could not be loaded.")

                elif not any(day["positive"] or day["negative"] for day in daily):
                    empty_state("No chest X-rays were analyzed in the last 14 days.")

                else:
                    st.altair_chart(ai_activity_chart(daily), width="stretch")

                    with st.expander("View as table"):
                        st.dataframe(
                            {
                                "Date": [day["date"] for day in daily],
                                "AI negative": [day["negative"] for day in daily],
                                "AI positive": [day["positive"] for day in daily],
                            },
                            hide_index=True,
                        )

        with calendar_col:
            with st.container(key="sa_card_calendar"):

                section_title("Calendar")
                show_calendar()

        # ---------------- Hospitals ----------------

        map_col, hospitals_col = st.columns([3, 1.2], gap="medium")

        located = [
            hospital
            for hospital in hospitals or []
            if hospital.get("latitude") is not None
            and hospital.get("longitude") is not None
        ]

        with map_col:
            with st.container(key="sa_card_map"):

                section_title("Hospital locations")

                if located:
                    st.map(
                        {
                            "lat": [float(h["latitude"]) for h in located],
                            "lon": [float(h["longitude"]) for h in located],
                        },
                        height=260,
                    )
                else:
                    empty_state("No hospital locations have been recorded yet.")

        with hospitals_col:
            with st.container(key="sa_card_hospitals"):

                section_title("Partnered hospitals")

                if hospitals is None:
                    empty_state("Hospitals could not be loaded.")

                elif not hospitals:
                    empty_state("No hospitals yet.")

                else:
                    st.dataframe(
                        {
                            "Hospital": [h.get("hospital_name") or "—" for h in hospitals],
                            "Status": ["Active" if h.get("is_active") else "Inactive" for h in hospitals],
                        },
                        hide_index=True,
                        height=260,
                    )
