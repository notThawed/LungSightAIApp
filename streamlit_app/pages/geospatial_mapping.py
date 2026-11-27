# LUNGSIGHT_PSGC_NO_MANUAL_GEO_V2
"""One shared hospital-scoped geospatial monitoring page for all Streamlit roles.

Real hospital-scoped records only. No demonstration or simulated data.
"""
from __future__ import annotations
from datetime import date
from html import escape
from io import BytesIO
from pathlib import Path
import re  # LUNGSIGHT_GEOSPATIAL_CSS_FILTERS_20261127

import folium
import pandas as pd
import streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium

from backend.supabase_client import admin_supabase
from backend.geospatial_backend.geospatial_utils import AGE_GROUPS, month_shift
from backend.geospatial_backend.patient_location_utils import catalog_by_hospital
from backend.geospatial_backend.incidence_cases import first_recorded_confirmed_cases
from backend.geospatial_backend.incidence_population import (
    build_incidence_rows, population_api_release,
)

CSS = Path(__file__).resolve().parents[2] / 'shared/theme/css_content/geospatial.css'

# All presentation values are configured ONLY in geospatial.css.
# The CSS file is the single source for HTML, Leaflet, charts and exports.
_GEO_CSS_TEXT = CSS.read_text(encoding='utf-8')


def geo_css_setting(name):
    """Read a CSS custom property; no duplicate Python color defaults."""
    match = re.search(r'--' + re.escape(name) + r'\s*:\s*([^;{}]+);', _GEO_CSS_TEXT)
    if not match:
        raise ValueError(f'Missing --{name} in {CSS}')
    return match.group(1).strip()


def geo_css_color(name):
    value = geo_css_setting(name)
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        raise ValueError(f'--{name} must be a six-digit hex color in geospatial.css')
    return value


def geo_css_number(name):
    try:
        return float(geo_css_setting(name))
    except ValueError as exc:
        raise ValueError(f'--{name} must be a plain CSS number') from exc


COLORS = {
    'High': geo_css_color('geo-circle-high'),
    'Moderate': geo_css_color('geo-circle-moderate'),
    'Low': geo_css_color('geo-circle-low'),
    'No cases': geo_css_color('geo-circle-no-cases'),
    'Unavailable': geo_css_color('geo-circle-unavailable'),
}
GEO_STYLE = {
    'selected_outline': geo_css_color('geo-circle-selected-outline'),
    'outline_weight': geo_css_number('geo-circle-outline-weight'),
    'selected_outline_weight': geo_css_number('geo-circle-selected-outline-weight'),
    'fill_opacity': geo_css_number('geo-circle-fill-opacity'),
    'base_radius': geo_css_number('geo-circle-base-radius'),
    'extra_radius': geo_css_number('geo-circle-extra-radius'),
    'export_circle_outline': geo_css_color('geo-export-circle-outline'),
    'export_circle_outline_width': geo_css_number('geo-export-circle-outline-width'),
    'export_circle_opacity': geo_css_number('geo-export-circle-opacity'),
    'export_circle_base_size': geo_css_number('geo-export-circle-base-size'),
    'export_circle_extra_size': geo_css_number('geo-export-circle-extra-size'),
    'export_circle_incidence_factor': geo_css_number('geo-export-circle-incidence-factor'),
    'export_table_header': geo_css_color('geo-export-table-header'),
    'hospital_pin_color': geo_css_setting('geo-hospital-pin-color'),
    'trend_line': geo_css_color('geo-trend-line'),
}


def html(content):
    st.markdown(content, unsafe_allow_html=True)


def section(text):
    html(f'<div class="geo-section">{escape(text)}</div>')


def _role(user):
    try: return int(user.get('role_id') or 0)
    except (ValueError,TypeError): return 0


def hospital_context():
    """Never accept a hospital ID from a UI control; re-check the authenticated profile."""
    session = st.session_state.get('user') or {}
    uid = session.get('user_id') or session.get('id')
    if not uid:
        raise PermissionError('Please sign in again.')
    result = (admin_supabase.table('user_profiles')
              .select('user_id,hospital_id,role_id,is_active')
              .eq('user_id', uid).limit(1).execute().data or [])
    if not result or result[0].get('is_active') is False:
        raise PermissionError('Your account is not authorized.')
    profile = result[0]
    if not profile.get('role_id') or not profile.get('hospital_id'):
        raise PermissionError('Your account must have an assigned hospital.')
    rows = (admin_supabase.table('hospitals')
            .select('hospital_id,hospital_name,address,latitude,longitude')
            .eq('hospital_id', profile['hospital_id']).limit(1).execute().data or [])
    if not rows:
        raise PermissionError('Your assigned hospital could not be found.')
    return rows[0]


def load_geo_catalog(hospital_id):
    """Hospital-scoped observed barangays from patient records, no geo_* tables."""
    return catalog_by_hospital(hospital_id)


def barangay_label(row):
    return f"{row['barangay']} — {row['city']}, {row['province']}"


# LUNGSIGHT_GEOSPATIAL_RECORDS_FIX_20261118
# Read directly on rerun; location grouping is shared with the patient-record data.
def monthly_counts(hospital_id, year, month, age, sex):
    # Existing page intentionally does not provide demographic filters.
    # Only FIRST-recorded clinician-confirmed patients count as new cases.
    return {str(k): v for k, v in
            first_recorded_confirmed_cases(hospital_id, year, month).items()}


def summary_rows_real(catalog, chosen, current, previous):
    return build_incidence_rows(catalog, chosen, current, previous)


def month_options():
    now=date.today(); return [month_shift(now.year,now.month,-i) for i in range(0,25)]


def make_map(rows, mode, selected, hospital):
    coords = [(float(r['Latitude (approx.)']), float(r['Longitude (approx.)']))
              for r in rows if r.get('Latitude (approx.)') is not None
              and r.get('Longitude (approx.)') is not None]
    if hospital.get('latitude') is not None and hospital.get('longitude') is not None:
        coords.append((float(hospital['latitude']), float(hospital['longitude'])))
    center = ([sum(x[0] for x in coords)/len(coords),
               sum(x[1] for x in coords)/len(coords)] if coords else
              [10.3157, 123.8854])
    m = folium.Map(location=center, zoom_start=11, tiles='OpenStreetMap', control_scale=True)
    # The Folium map runs in an iframe: inject the SAME geospatial CSS there.
    m.get_root().header.add_child(folium.Element('<style>' + _GEO_CSS_TEXT + '</style>'))
    max_rate = max((r['Incidence / 100k'] or 0 for r in rows), default=0)
    for row in rows:
        lat, lon = row.get('Latitude (approx.)'), row.get('Longitude (approx.)')
        if lat is None or lon is None:
            continue
        name, count = row['Barangay'], row['Recorded cases']
        incidence, ratio = row['Incidence / 100k'], row['Relative rate ratio']
        label = row['Incidence level']
        color = COLORS.get(label, COLORS['Unavailable'])
        marker_size = GEO_STYLE['base_radius'] + min(GEO_STYLE['extra_radius'], (incidence or 0) / max(1, max_rate) * GEO_STYLE['extra_radius'])
        detail = (
            f'<b>{escape(name)}</b><br>Newly recorded cases: {count}'
            f'<br>2024 census population: {row["Population (2024)"] if row["Population (2024)"] is not None else "Unavailable"}'
            f'<br>Incidence / 100k: {incidence if incidence is not None else "Unavailable"}'
            f'<br>Relative rate ratio: {ratio if ratio is not None else "Unavailable"}'
            f'<br>Relative incidence: {label}'
        )
        folium.CircleMarker(
            location=[float(lat), float(lon)], radius=marker_size,
            color=GEO_STYLE['selected_outline'] if name == selected else color,
            weight=GEO_STYLE['selected_outline_weight'] if name == selected else GEO_STYLE['outline_weight'],
            fill=True, fill_color=color, fill_opacity=GEO_STYLE['fill_opacity'],
            tooltip=f'{name} — {count} newly recorded cases',
            popup=folium.Popup(detail, max_width=310),
        ).add_to(m)
    if hospital.get('latitude') is not None and hospital.get('longitude') is not None:
        folium.Marker([float(hospital['latitude']), float(hospital['longitude'])],
                      tooltip='Your hospital',
                      icon=folium.Icon(color=GEO_STYLE['hospital_pin_color'], icon='plus-sign')).add_to(m)
    if len(coords) > 1:
        m.fit_bounds(coords)
    return m


def png_export(rows, hospital_name, label):
    """Schematic export using approximate barangay reference locations."""
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11,7), dpi=160)
    for r in rows:
        if r.get('Latitude (approx.)') is None or r.get('Longitude (approx.)') is None:
            continue
        ax.scatter(float(r['Longitude (approx.)']), float(r['Latitude (approx.)']),
                   s=GEO_STYLE['export_circle_base_size']+min(GEO_STYLE['export_circle_extra_size'],
                       (r['Incidence / 100k'] or 0)*GEO_STYLE['export_circle_incidence_factor']),
                   c=COLORS[r['Incidence level']],
                   alpha=GEO_STYLE['export_circle_opacity'],
                   edgecolors=GEO_STYLE['export_circle_outline'],
                   linewidths=GEO_STYLE['export_circle_outline_width'])
        ax.annotate(r['Barangay'], (float(r['Longitude (approx.)']), float(r['Latitude (approx.)'])),
                    xytext=(4,5), textcoords='offset points', fontsize=7)
    ax.set_title(f'{hospital_name} | {label}\nHospital-recorded pneumonia incidence by approximate barangay point')
    ax.set_xlabel('Longitude'); ax.set_ylabel('Latitude'); ax.grid(alpha=.15)
    fig.text(.05,.025,'Approximate barangay markers; facility-recorded indicator, not community infection risk.',fontsize=9)
    fig.tight_layout(rect=[0,.04,1,1]); buf=BytesIO(); fig.savefig(buf,format='png',dpi=160)
    plt.close(fig); return buf.getvalue()


def pdf_export(rows,hospital_name,label,png):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Image,Table,TableStyle
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4,landscape
    buf=BytesIO();doc=SimpleDocTemplate(buf,pagesize=landscape(A4),leftMargin=35,rightMargin=35)
    styles=getSampleStyleSheet();story=[Paragraph('LungSightAI | Geospatial Hospital Report',styles['Title']),
      Paragraph(f'{escape(hospital_name)} — {escape(label)}',styles['Heading2']),
      Paragraph('Hospital-recorded first-confirmation incidence per 100,000 using PSA-derived 2024 census populations; not clinical severity or validated public-health risk.',styles['Normal']),Spacer(1,10)]
    story.append(Image(BytesIO(png),width=530,height=337));story.append(Spacer(1,10))
    data=[['Barangay','New cases','2024 population','Incidence / 100k','Ratio','Incidence level']]
    for r in rows:data.append([str(r[k]) if r[k] is not None else 'N/A' for k in ('Barangay','Recorded cases','Population (2024)','Incidence / 100k','Relative rate ratio','Incidence level')])
    t=Table(data,repeatRows=1,colWidths=[155,70,85,95,60,85]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(GEO_STYLE['export_table_header'])),('GRID',(0,0),(-1,-1),.25,colors.lightgrey),('FONTSIZE',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story.append(t)
    doc.build(story);return buf.getvalue()


def excel_export(rows,trend,hospital_name,label):
    buf=BytesIO()
    with pd.ExcelWriter(buf,engine='xlsxwriter') as writer:
        pd.DataFrame(rows).drop(columns=['Latitude (approx.)','Longitude (approx.)'],errors='ignore').to_excel(writer,sheet_name='Barangay Summary',index=False)
        pd.DataFrame(trend).to_excel(writer,sheet_name='Monthly Trend',index=False)
        pd.DataFrame([{'Hospital':hospital_name,'Period':label,'Data source':'REAL HOSPITAL RECORDS','Interpretation':'Facility-based first recorded pneumonia indicator; not total community incidence or clinical severity'}]).to_excel(writer,sheet_name='Read Me',index=False)
        for sheet in writer.sheets.values():sheet.set_column(0,12,22)
    return buf.getvalue()


def show():
    if CSS.is_file():
        html('<style>'+CSS.read_text(encoding='utf-8')+'</style>')
    from streamlit_app.components.ui import refresh_button
    with st.container(key="geo_hero_refresh_20261127"):
        hero_col, refresh_col = st.columns([15, 1], vertical_alignment="center")
        with hero_col:
            html('<div class="geo-hero"><div class="geo-eyebrow">LungSightAI · Analytics & Monitoring</div><div class="geo-title">Geospatial Case Monitoring</div><div class="geo-sub">First-recorded clinician-confirmed pneumonia patients by barangay, adjusted for PSA 2024 population</div></div>')
        with refresh_col:
            refresh_button("page_refresh_geospatial")
    try:
        hospital = hospital_context()
        geo_rows = load_geo_catalog(hospital["hospital_id"])
    except Exception as exc:
        st.error(f'Cannot load hospital geospatial data: {exc}')
        return
    name = hospital.get('hospital_name') or 'Assigned hospital'
    catalog = {str(x['barangay_id']): x for x in geo_rows}
    if not catalog:
        st.info('No patient records with barangay addresses exist for this hospital yet.')
        return
    # No manual geographic filters; report is for the current PH month.
    from datetime import datetime
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo("Asia/Manila")).date()
    year, month = today.year, today.month
    period = f"{date(year, month, 1):%B %Y}"
    chosen = list(catalog)
    age, sex = "All ages", "All"
    previous_year, previous_month = month_shift(year, month, -1)
    hid = str(hospital["hospital_id"])
    try:
        current = monthly_counts(hid, year, month, age, sex)
        prior = monthly_counts(hid, previous_year, previous_month, age, sex)
    except Exception as exc:
        st.error(f"Could not load confirmed cases from Supabase: {exc}")
        return
    rows, incidence_meta = summary_rows_real(catalog,chosen,current,prior)
    from collections import Counter

    level_counts = Counter(
        row["Incidence level"] for row in rows
    )

    st.caption(
        "Incidence classification: "
        + " | ".join(
            f"{level}: {level_counts.get(level, 0)}"
            for level in (
                "Low",
                "Moderate",
                "High",
                "No cases",
                "Unavailable",
            )
        )
    )
    reference = incidence_meta['reference_incidence']
    reference_label = f'{reference:,.2f}' if reference is not None else 'Unavailable'
    st.caption(
        f"Study-area reference: {reference_label} first-recorded cases per 100,000 "
        f"(population-weighted across {incidence_meta['covered_barangays']} "
        f"mapped patient barangays; PSA-derived {incidence_meta['census_year']} population)."
    )
    if incidence_meta['unavailable_barangays']:
        st.warning(
            f"{incidence_meta['unavailable_barangays']} barangay(s) have no verified population "
            "match; incidence is unavailable there. Confirm PSGC codes in Manage Patients."
        )
    try:
        release = population_api_release()
        st.caption(f"Population source: PSA 2024 POPCEN via PSGC API; API dataset {release['version']}.")
    except Exception:
        st.caption('Population API release information is currently unavailable.')
    total = sum(current.get(key,0) for key in chosen)
    prior_total = sum(prior.get(key,0) for key in chosen)
    highest = next((r['Barangay'] for r in rows if (r['Incidence / 100k'] or 0) > 0), '—')
    change = f'{(total-prior_total)/prior_total:+.1%}' if prior_total else 'N/A'
    kpis = [('Recorded cases',str(total)),
            ('Barangays with cases',f'{sum(current.get(key,0)>0 for key in chosen)} / {len(chosen)}'),
            ('Highest-incidence barangay',highest),('Month-over-month change',change)]
    for col,(label,value) in zip(st.columns(4),kpis):
        with col:
            html(f'<div class="geo-kpi"><div class="geo-kpi-label">{escape(label)}</div><div class="geo-kpi-value">{escape(value)}</div></div>')
    st.write('')
    left,right = st.columns([1.5,1],gap='medium')
    with left:
        section('Geographic Distribution')
        mode = 'Hotspots'  # No manually selected map filter
        selected = st.session_state.get('geo_selected')
        result = st_folium(make_map(rows,mode,selected,hospital),height=510,width=None,
                           use_container_width=True,key=f'geo_map_{hid}_{mode}',
                           returned_objects=['last_object_clicked_tooltip'])
        tooltip = (result or {}).get('last_object_clicked_tooltip') or ''
        if ' — ' in tooltip:
            clicked = tooltip.rsplit(' — ',1)[0]
            if clicked in [r['Barangay'] for r in rows] and clicked != selected:
                st.session_state['geo_selected'] = clicked
                st.rerun()
        html('<div class="geo-note geo-legend">'
             '<span class="geo-legend-item"><span class="geo-legend-dot geo-legend-dot-low"></span> Low</span>'
             '<span class="geo-legend-item"><span class="geo-legend-dot geo-legend-dot-moderate"></span> Moderate</span>'
             '<span class="geo-legend-item"><span class="geo-legend-dot geo-legend-dot-high"></span> High</span>'
             '<span class="geo-legend-item"><span class="geo-legend-dot geo-legend-dot-no-cases"></span> No cases</span>'
             '<span class="geo-legend-item"><span class="geo-legend-dot geo-legend-dot-unavailable"></span> Population unavailable</span>'
             '<span class="geo-legend-disclaimer">Relative <b>hospital-recorded incidence</b>, not clinical severity. Markers are approximate barangay reference points, not patient homes.</span></div>')
    with right:
        section('Barangay Case Summary')
        # FILTER SWITCH: comment out the next line to hide the entire toolbar.
        show_geo_filters = False
        show_geo_filters = True
        visible_rows = list(rows)
        if show_geo_filters:
            with st.container(key='geo_summary_filters'):
                search_col, sort_col = st.columns([2, 1])
                search_text = search_col.text_input('Search barangay', key='geo_summary_search').strip().casefold()
                sort_choice = sort_col.selectbox('Sort by', ['Default order', 'Barangay A–Z', 'Barangay Z–A', 'Numbers ascending', 'Numbers descending'], key='geo_summary_sort_simple')
            visible_rows = [r for r in rows if search_text in str(r['Barangay']).casefold()]
            if sort_choice in ('Barangay A–Z', 'Barangay Z–A'):
                visible_rows.sort(key=lambda r: str(r['Barangay']).casefold(), reverse=sort_choice == 'Barangay Z–A')
            elif sort_choice in ('Numbers ascending', 'Numbers descending'):
                # Numeric order uses incidence; other columns have clickable headers.
                metric = 'Incidence / 100k'
                visible_rows.sort(key=lambda r: (pd.isna(r[metric]), 0 if pd.isna(r[metric]) else float(r[metric]) * (1 if sort_choice == 'Numbers ascending' else -1)))
        with st.container(key='geo_summary_table'):
            html(f'<div class="geo-summary-count">Showing {len(visible_rows)} of {len(rows)} barangays</div>')
            if visible_rows:
                st.dataframe(
                    pd.DataFrame(visible_rows)[[
                        'Barangay', 'Recorded cases', 'Population (2024)',
                        'Incidence / 100k', 'Relative rate ratio', 'Incidence level',
                    ]], hide_index=True, use_container_width=True, height=270,
                )
            else:
                st.info('No barangays match the current search or case filter.')

        names = [r['Barangay'] for r in visible_rows]
        default_idx = names.index(selected) if selected in names else 0
        barangay = selected if selected in names else (names[default_idx] if names else None)
        # Avoid displaying a stale detail card for a filtered-out barangay.
        if st.session_state.get('geo_detail_open') not in names:
            st.session_state.pop('geo_detail_open', None)
        with st.container(key='geo_detail_button'):
            open_detail = st.button(
                'View Detailed Summary', icon=':material/insights:',
                use_container_width=True, type='primary',
                key='geo_show_detail', disabled=not names,
            )
        if open_detail:
            st.session_state['geo_detail_open'] = barangay
        if st.session_state.get('geo_detail_open'):
            r = next((x for x in visible_rows if x['Barangay']==st.session_state['geo_detail_open']),None)
            if r:
                html(f'<div class="geo-note geo-detail-card"><b>{escape(r["Barangay"])}</b><br>Confirmed cases: <b>{r["Recorded cases"]}</b><br>Population (2024): <b>{r["Population (2024)"] if r["Population (2024)"] is not None else "Unavailable"}</b><br>Incidence / 100k: <b>{r["Incidence / 100k"] if r["Incidence / 100k"] is not None else "Unavailable"}</b><br>Relative rate ratio: <b>{r["Relative rate ratio"] if r["Relative rate ratio"] is not None else "Unavailable"}</b><br>Relative incidence: <b>{escape(r["Incidence level"])}</b><br>Previous month: {r["Previous month"]}<br>Change: {r["Change (%)"] if r["Change (%)"] is not None else "N/A"}%</div>')
                if st.button('Close summary',key='geo_close_summary'):
                    st.session_state.pop('geo_detail_open',None)
                    st.rerun()
        section('Monthly Trend')
        trend = []
        try:
            for offset in range(-5,1):
                yy,mm = month_shift(year,month,offset)
                month_data = monthly_counts(hid,yy,mm,age,sex)
                trend.append({'Month':f'{date(yy,mm,1):%b %Y}',
                              'Cases':sum(month_data.get(key,0) for key in chosen)})
        except Exception as exc:
            st.error(f'Could not load monthly trend: {exc}')
            return
        st.line_chart(pd.DataFrame(trend).set_index('Month'),height=190,color=GEO_STYLE['trend_line'])
    # Include zero-case barangays: map point availability is independent of incidence.
    missing = sum(1 for r in rows if (r.get('Latitude (approx.)') is None or r.get('Longitude (approx.)') is None))
    if missing:
        st.warning(f'{missing} barangay group(s) lack an approximate reference location. They remain in the table but cannot be plotted yet.')
    st.caption('Geocoded reference points may use Geoapify / OpenStreetMap data. Map tiles © OpenStreetMap contributors; use points only for approximate barangay visualisation.')
    section('Export Geospatial Report')
    st.caption('Exports reflect this hospital and the current Philippine reporting month. PNG uses approximate barangay reference points, not patient homes or a screenshot of map tiles.')
    try:
        png = png_export(rows,name,period)
        p1,p2,p3 = st.columns(3)
        with p1:
            st.download_button('Export PNG',png,file_name=f'geospatial_{year}_{month:02d}.png',mime='image/png',icon=':material/image:',use_container_width=True,key='geo_export_png')
        with p2:
            st.download_button('Export PDF',pdf_export(rows,name,period,png),file_name=f'geospatial_{year}_{month:02d}.pdf',mime='application/pdf',icon=':material/picture_as_pdf:',use_container_width=True,key='geo_export_pdf')
        with p3:
            st.download_button('Export Excel',excel_export(rows,trend,name,period),file_name=f'geospatial_{year}_{month:02d}.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',icon=':material/table_view:',use_container_width=True,key='geo_export_excel')
    except Exception as exc:
        st.error(f'Could not generate export: {exc}')
    html('<div class="geo-note geo-interpretation"><b>Interpretation:</b> First hospital-recorded clinician-confirmed cases ÷ 2024 PSA census population × 100,000 (current PH month). Relative incidence categories compare to the population-weighted study-area reference. Not complete community surveillance, clinical case severity, transmission risk, or validated DOH alert levels.</div>')


if __name__ == '__main__':
    show()

# Note: map tile provider is OpenStreetMap (no API key required).
