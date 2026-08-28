from datetime import date

import streamlit as st
import calendar
import streamlit.components.v1 as components

def metric_card(title, value, icon):

    st.markdown(
        f"""<div class="metric-card">
<div class="metric-title">{title}</div>
<div class="metric-value">{value}</div>
<div class="metric-icon">{icon}</div>
</div>""",
        unsafe_allow_html=True
    )

def show_calendar():

    today = date.today()

    current_year = today.year
    current_month = today.month

    month_name = calendar.month_name[current_month]

    month_days = calendar.monthcalendar(
        current_year,
        current_month
    )

    # ==========================================
    # BUILD CALENDAR DAYS
    # ==========================================

    days_html = ""

    for week in month_days:

        for day in week:

            if day == 0:

                days_html += (
                    '<div class="calendar-day empty"></div>'
                )

            elif day == today.day:

                days_html += (
                    f'<div class="calendar-day today">{day}</div>'
                )

            else:

                days_html += (
                    f'<div class="calendar-day">{day}</div>'
                )

    # ==========================================
    # COMPLETE CALENDAR HTML
    # ==========================================

    calendar_html = f"""
    <!DOCTYPE html>
    <html>

    <head>

    <style>

    body {{
        margin: 0;
        padding: 0;
        font-family: Arial, sans-serif;
        background-color: transparent;
    }}

    .calendar-card {{
        background-color: white;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 15px;
    }}

    .calendar-title {{
        text-align: center;
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 15px;
        color: #374151;
    }}

    .calendar-weekdays {{
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        text-align: center;
        font-size: 11px;
        font-weight: 600;
        color: #6b7280;
        margin-bottom: 8px;
    }}

    .calendar-days {{
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 4px;
        text-align: center;
    }}

    .calendar-day {{
        padding: 5px 0;
        font-size: 12px;
        border-radius: 4px;
    }}

    .calendar-day.today {{
        background-color: #4a76b8;
        color: white;
        font-weight: bold;
    }}

    .calendar-day.empty {{
        visibility: hidden;
    }}

    </style>

    </head>

    <body>

        <div class="calendar-card">

            <div class="calendar-title">
                {month_name} {current_year}
            </div>

            <div class="calendar-weekdays">
                <div>Su</div>
                <div>Mo</div>
                <div>Tu</div>
                <div>We</div>
                <div>Th</div>
                <div>Fr</div>
                <div>Sa</div>
            </div>

            <div class="calendar-days">

                {days_html}

            </div>

        </div>

    </body>

    </html>
    """

    components.html(
        calendar_html,
        height=280
    )

def show():

    st.markdown(
            """<style>
    
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 5px;
        min-height: 110px;
        border: 1px solid #e5e7eb;
        box-shadow: 0px 2px 5px rgba(0, 0, 0, 0.08);
        position: relative;
        margin-bottom: 10px;
    }
    
    .metric-title {
        font-size: 13px;
        font-weight: 500;
        color: #6b7280;
        text-transform: uppercase;
    }
    
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        color: #4a76b8;
        margin-top: 10px;
    }
    
    .metric-icon {
        position: absolute;
        top: 18px;
        right: 18px;
        font-size: 24px;
    }

    
    </style>""",
            unsafe_allow_html=True
        )

    st.title("Administrator Dashboard")

    st.info("System Administrator Dashboard. Here you can view the system statistics and manage users, hospitals, and doctors.")

    counts = {
        "total_scans_today": 0,
        "pneumonia_detected": 0,
        "healthy_cases": 0,
        "pending_cases": 0
    }

    col1, col2, col3, col4 = st.columns(4)
    col5, col6, col7, col8 = st.columns(4)

    with col1:
    
            metric_card(
                "Total Scans Today",
                counts["total_scans_today"],
                "[ ]"
            )

    with col2:
         metric_card(
              "Pneumonia Detected",
              counts["pneumonia_detected"],
              "[]"
         )
    with col3:
         metric_card(
              "Healthy Cases",
              counts["healthy_cases"],
                "[]"
         )
    with col4:
         metric_card(
              "Pending Cases",
              counts["pending_cases"],
                "[]"
         )

    with col5:
         metric_card(
              "Active Doctors",
              0,
                "[]"
         )
    with col6:
         metric_card(
              "Active Hospitals",
              0,
                "[]"
         )
    with col7:
         metric_card(
              "Active Hospital Admins",
              0,
                "[]"
         )
    with col8:
         metric_card(
              "AI Status",
              0,
                "[]"
         )

    st.divider()

    st.subheader("System Statistics")

    chart_col, calendar_col = st.columns([3, 1], gap="large")

    with chart_col:
         st.markdown(
              "Pneumonia Detection Rate Over Time",
         )

         chart_data = {
              "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
              "Pneumonia Detected": [5, 10, 7, 12, 8],
              "Healthy Cases": [15, 20, 18, 22, 25]
         }

         st.line_chart(
              chart_data,
              x="date",
              y=["Pneumonia Detected", "Healthy Cases"]
         )

    with calendar_col:
         st.markdown(
              "Calendar View"
         )
         show_calendar()    

    st.divider()

    st.subheader("Active Hospitals")

    st.info(
        "List of active hospitals in the system."
    )

    map_col, partnered_hospital_col = st.columns([3, 1], gap="large")

    with map_col:
        st.markdown(
            "Hospital Locations"
        )
        st.map(
            {
                "lat": [10.3236],
                "lon": [123.9227]
            }
        )

    with partnered_hospital_col:
        st.markdown(
            "Partnered Hospitals"
        )

        st.dataframe(
            {
                "Hospital Name": ["Hospital A", "Hospital B", "Hospital C"],
                "Location": ["City A", "City B", "City C"],
                "Active Doctors": [5, 10, 7]
            }
        )
