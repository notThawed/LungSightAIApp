import calendar
from datetime import date

import streamlit as st

from streamlit_app.components.ui import (
    load_css,
    page_header,
    metric_card,
    section_title,
)


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
# PAGE
# ============================================================

def show():

    load_css("dashboard.css")

    # Keep the eight core metrics aligned and lightweight for the admin dashboard.
    # Placeholder numbers: replace these with real queries when ready
    metrics = [
        ("Total scans today", 0, "radiology", ""),
        ("Pneumonia detected", 0, "coronavirus", "red"),
        ("Healthy cases", 0, "check_circle", "green"),
        ("Pending cases", 0, "hourglass_top", "amber"),
        ("Active doctors", 0, "stethoscope", "blue"),
        ("Active hospitals", 0, "local_hospital", ""),
        ("Active hospital admins", 0, "admin_panel_settings", "blue"),
        ("AI status", "Operational", "smart_toy", "green"),
    ]

    with st.container(key="sa_page"):

        page_header(
            "Administrator dashboard",
            "System-wide statistics for hospitals, users and scans.",
        )

        # ---------------- Metrics: two rows of four ----------------

        for start in (0, 4):

            columns = st.columns(4)

            for column, (title, value, icon, tone) in zip(columns, metrics[start:start + 4]):
                with column:
                    metric_card(title, value, icon, tone)

        # ---------------- Chart + calendar ----------------

        chart_col, calendar_col = st.columns([3, 1.2], gap="medium")

        with chart_col:
            with st.container(key="sa_card_chart"):

                section_title("Pneumonia detection rate over time")

                chart_data = {
                    "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
                    "Pneumonia detected": [5, 10, 7, 12, 8],
                    "Healthy cases": [15, 20, 18, 22, 25],
                }

                st.line_chart(
                    chart_data,
                    x="date",
                    y=["Pneumonia detected", "Healthy cases"],
                    height=260,
                )

        with calendar_col:
            with st.container(key="sa_card_calendar"):

                section_title("Calendar")
                show_calendar()

        # ---------------- Hospitals ----------------

        map_col, hospitals_col = st.columns([3, 1.2], gap="medium")

        with map_col:
            with st.container(key="sa_card_map"):

                section_title("Hospital locations")

                st.map(
                    {"lat": [10.3236], "lon": [123.9227]},
                    height=260,
                )

        with hospitals_col:
            with st.container(key="sa_card_hospitals"):

                section_title("Partnered hospitals")

                st.dataframe(
                    {
                        "Hospital": ["Hospital A", "Hospital B", "Hospital C"],
                        "Doctors": [5, 10, 7],
                    },
                    hide_index=True,
                    height=260,
                )