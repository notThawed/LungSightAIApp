"""One shared hospital-scoped geospatial monitoring page for all Streamlit roles.

Real hospital-scoped records only. No demonstration or simulated data.
"""
from __future__ import annotations
from datetime import date
from html import escape
from io import BytesIO
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium

from backend.supabase_client import admin_supabase
from backend.backend_utils.geospatial_utils import AGE_GROUPS, month_shift
from backend.backend_utils.patient_location_utils import (get_barangays, real_case_counts)

CSS = Path(__file__).resolve().parents[2] / 'shared/theme/css_content/geospatial.css'
COLORS={'Higher':'#ef4444','Moderate':'#f59e0b','Lower':'#22c55e','No cases':'#94a3b8'}


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


def load_geo_catalog():
    """Read only reference barangays; never synthesize geographic coordinates."""
    all_rows = []
    offset = 0
    while True:
        batch = (admin_supabase.table('geo_barangays')
                 .select('barangay_id,province,city,barangay,latitude,longitude')
                 .eq('is_active', True).order('barangay_id')
                 .range(offset, offset + 999).execute().data or [])
        all_rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += len(batch)
    return all_rows


def barangay_label(row):
    return f"{row['barangay']} — {row['city']}, {row['province']}"


def monthly_counts(hospital_id, year, month, age, sex):
    return {str(k): v for k, v in real_case_counts(hospital_id, year, month, age, sex).items()}


def summary_rows_real(catalog, chosen, current, previous):
    values = [current.get(key, 0) for key in chosen]
    positive = sorted([n for n in values if n > 0])
    high = positive[max(0, int(len(positive) * .75) - 1)] if positive else 0
    mid = positive[max(0, int(len(positive) * .4) - 1)] if positive else 0
    rows = []
    for key in chosen:
        item = catalog[key]
        count, prior = current.get(key, 0), previous.get(key, 0)
        concentration = ('No cases' if count == 0 else 'Higher' if count >= high else
                         'Moderate' if count >= mid else 'Lower')
        rows.append({'Barangay': barangay_label(item), 'Recorded cases': count,
                     'Concentration': concentration, 'Previous month': prior,
                     'Change (%)': round((count-prior)*100/prior, 1) if prior else None,
                     'Latitude (approx.)': item.get('latitude'),
                     'Longitude (approx.)': item.get('longitude'),
                     'Barangay ID': key})
    return sorted(rows, key=lambda r: (-r['Recorded cases'], r['Barangay']))


def month_options():
    now=date.today(); return [month_shift(now.year,now.month,-i) for i in range(0,25)]


def make_map(rows, mode, selected, hospital):
    coords = [(float(r['Latitude (approx.)']), float(r['Longitude (approx.)']))
              for r in rows if r.get('Latitude (approx.)') is not None and r.get('Longitude (approx.)') is not None]
    if hospital.get('latitude') is not None and hospital.get('longitude') is not None:
        coords.append((float(hospital['latitude']), float(hospital['longitude'])))
    center = [sum(x[0] for x in coords)/len(coords), sum(x[1] for x in coords)/len(coords)] if coords else [10.3157, 123.8854]
    m = folium.Map(location=center, zoom_start=11, tiles="OpenStreetMap", control_scale=True)
    max_count = max((r['Recorded cases'] for r in rows), default=1)
    if mode == 'Heatmap':
        heat = [[float(r['Latitude (approx.)']), float(r['Longitude (approx.)']), r['Recorded cases']]
                for r in rows if r['Recorded cases'] > 0 and r.get('Latitude (approx.)') is not None and r.get('Longitude (approx.)') is not None]
        if heat:
            HeatMap(heat, radius=32, blur=23, min_opacity=.3).add_to(m)
    for row in rows:
        lat, lon = row.get('Latitude (approx.)'), row.get('Longitude (approx.)')
        if lat is None or lon is None or not row['Recorded cases']:
            continue
        name, count = row['Barangay'], row['Recorded cases']
        color = COLORS[row['Concentration']]
        folium.CircleMarker(
            location=[float(lat), float(lon)],
            radius=7+min(17, count/max(1,max_count)*16) if mode=='Hotspots' else 5,
            color='#fff' if name==selected else color, weight=3 if name==selected else 1,
            fill=True, fill_color=color, fill_opacity=.9 if mode=='Hotspots' else .45,
            tooltip=f'{name} — {count} recorded cases',
            popup=folium.Popup(f'<b>{escape(name)}</b><br>{count} recorded cases<br>{row["Concentration"]} relative concentration',max_width=280),
        ).add_to(m)
    if hospital.get('latitude') is not None and hospital.get('longitude') is not None:
        folium.Marker([float(hospital['latitude']),float(hospital['longitude'])],
                      tooltip='Your hospital', icon=folium.Icon(color='blue',icon='plus-sign')).add_to(m)
    if len(coords) > 1:
        m.fit_bounds(coords)
    return m


def png_export(rows, hospital_name, label):
    """Schematic export using only verified reference barangay centroids."""
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11,7), dpi=160)
    for r in rows:
        if not r['Recorded cases'] or r.get('Latitude (approx.)') is None or r.get('Longitude (approx.)') is None:
            continue
        ax.scatter(float(r['Longitude (approx.)']), float(r['Latitude (approx.)']),
                   s=70+r['Recorded cases']*17, c=COLORS[r['Concentration']],
                   alpha=.78, edgecolors='white', linewidths=1.5)
        ax.annotate(r['Barangay'], (float(r['Longitude (approx.)']), float(r['Latitude (approx.)'])),
                    xytext=(4,5), textcoords='offset points', fontsize=7)
    ax.set_title(f'{hospital_name} | {label}\nReal hospital case counts by verified barangay centroid')
    ax.set_xlabel('Longitude'); ax.set_ylabel('Latitude'); ax.grid(alpha=.15)
    fig.text(.05,.025,'Barangay centroids are approximate; markers do not represent homes or incidence risk.',fontsize=9)
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
      Paragraph('Real hospital-scoped confirmed case counts. Relative concentration is not incidence or clinical risk.',styles['Normal']),Spacer(1,10)]
    story.append(Image(BytesIO(png),width=530,height=337));story.append(Spacer(1,10))
    data=[['Barangay','Cases','Relative concentration','Previous month','Change (%)']]
    for r in rows:data.append([str(r[k]) if r[k] is not None else 'N/A' for k in ('Barangay','Recorded cases','Concentration','Previous month','Change (%)')])
    t=Table(data,repeatRows=1,colWidths=[145,80,145,100,90]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dceff2')),('GRID',(0,0),(-1,-1),.25,colors.lightgrey),('FONTSIZE',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story.append(t)
    doc.build(story);return buf.getvalue()


def excel_export(rows,trend,hospital_name,label):
    buf=BytesIO()
    with pd.ExcelWriter(buf,engine='xlsxwriter') as writer:
        pd.DataFrame(rows).drop(columns=['Latitude (approx.)','Longitude (approx.)'],errors='ignore').to_excel(writer,sheet_name='Barangay Summary',index=False)
        pd.DataFrame(trend).to_excel(writer,sheet_name='Monthly Trend',index=False)
        pd.DataFrame([{'Hospital':hospital_name,'Period':label,'Data source':'REAL HOSPITAL RECORDS','Interpretation':'Not incidence, transmission or patient home coordinates'}]).to_excel(writer,sheet_name='Read Me',index=False)
        for sheet in writer.sheets.values():sheet.set_column(0,12,22)
    return buf.getvalue()


def show():
    if CSS.is_file():
        html('<style>'+CSS.read_text(encoding='utf-8')+'</style>')
    html('<div class="geo-hero"><div class="geo-eyebrow">LungSightAI · Analytics & Monitoring</div><div class="geo-title">Geospatial Case Monitoring</div><div class="geo-sub">Hospital-specific, clinician-confirmed pneumonia cases by residential barangay</div></div>')
    try:
        hospital = hospital_context()
        geo_rows = load_geo_catalog()
    except Exception as exc:
        st.error(f'Cannot load hospital geospatial data: {exc}')
        return
    name = hospital.get('hospital_name') or 'Assigned hospital'
    catalog = {str(x['barangay_id']): x for x in geo_rows}
    if not catalog:
        st.info('No barangays have been configured. Import verified location reference data first.')
        return
    options = month_options()
    labels = {f'{date(y,m,1):%B %Y}':(y,m) for y,m in options}
    c1,c2,c3,c4 = st.columns([1.4,1.4,1,1])
    with c1:
        period = st.selectbox('Reporting month', list(labels), index=0, key='geo_month')
    with c2:
        chosen = st.multiselect('Barangays', list(catalog), default=list(catalog),
                                format_func=lambda key: barangay_label(catalog[key]),key='geo_barangays')
    with c3:
        age = st.selectbox('Age group',['All ages',*AGE_GROUPS],key='geo_age')
    with c4:
        sex = st.selectbox('Sex',['All','Female','Male'],key='geo_sex')
    if not chosen:
        st.warning('Select at least one barangay.')
        return
    year, month = labels[period]
    previous_year, previous_month = month_shift(year, month, -1)
    hid = str(hospital['hospital_id'])
    try:
        current = monthly_counts(hid,year,month,age,sex)
        prior = monthly_counts(hid,previous_year,previous_month,age,sex)
    except Exception as exc:
        st.error(f'Could not load confirmed cases from Supabase: {exc}')
        return
    rows = summary_rows_real(catalog,chosen,current,prior)
    total = sum(current.get(key,0) for key in chosen)
    prior_total = sum(prior.get(key,0) for key in chosen)
    highest = rows[0]['Barangay'] if rows and rows[0]['Recorded cases'] else '—'
    change = f'{(total-prior_total)/prior_total:+.1%}' if prior_total else 'N/A'
    kpis = [('Recorded cases',str(total)),
            ('Barangays with cases',f'{sum(current.get(key,0)>0 for key in chosen)} / {len(chosen)}'),
            ('Highest-count barangay',highest),('Month-over-month change',change)]
    for col,(label,value) in zip(st.columns(4),kpis):
        with col:
            html(f'<div class="geo-kpi"><div class="geo-kpi-label">{escape(label)}</div><div class="geo-kpi-value">{escape(value)}</div></div>')
    st.write('')
    left,right = st.columns([1.5,1],gap='medium')
    with left:
        section('Geographic Distribution')
        mode = st.segmented_control('Map layer',['Hotspots','Heatmap'],default='Hotspots',key='geo_layer')
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
        html('<div class="geo-note">🟢 Lower &nbsp;&nbsp; 🟠 Moderate &nbsp;&nbsp; 🔴 Higher — relative counts in the selected hospital data, not disease risk. Markers use verified barangay centroids, never patient homes.</div>')
    with right:
        section('Barangay Case Summary')
        st.dataframe(pd.DataFrame(rows)[['Barangay','Recorded cases','Concentration','Previous month','Change (%)']],
                     hide_index=True,use_container_width=True,height=270)
        names = [r['Barangay'] for r in rows]
        default_idx = names.index(selected) if selected in names else 0
        barangay = st.selectbox('Select barangay to inspect',names,index=default_idx,key='geo_detail_pick')
        if st.button('View Detailed Summary',icon=':material/insights:',use_container_width=True,type='primary'):
            st.session_state['geo_detail_open'] = barangay
        if st.session_state.get('geo_detail_open'):
            r = next((x for x in rows if x['Barangay']==st.session_state['geo_detail_open']),None)
            if r:
                html(f'<div class="geo-note"><b>{escape(r["Barangay"])}</b><br>Confirmed cases: <b>{r["Recorded cases"]}</b><br>Relative concentration: <b>{escape(r["Concentration"])}</b><br>Previous month: {r["Previous month"]}<br>Change: {r["Change (%)"] if r["Change (%)"] is not None else "N/A"}%</div>')
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
        st.line_chart(pd.DataFrame(trend).set_index('Month'),height=190)
    missing = sum(1 for r in rows if r['Recorded cases'] and (r.get('Latitude (approx.)') is None or r.get('Longitude (approx.)') is None))
    if missing:
        st.warning(f'{missing} barangay group(s) have recorded cases but no verified coordinates. They are shown in the table but cannot be plotted yet.')
    section('Export Geospatial Report')
    st.caption('Exports reflect this hospital, reporting month, barangays, age group, and sex. PNG uses verified barangay centroids and is not a screenshot of map tiles.')
    try:
        png = png_export(rows,name,period)
        p1,p2,p3 = st.columns(3)
        with p1:
            st.download_button('Export PNG',png,file_name=f'geospatial_{year}_{month:02d}.png',mime='image/png',icon=':material/image:',use_container_width=True)
        with p2:
            st.download_button('Export PDF',pdf_export(rows,name,period,png),file_name=f'geospatial_{year}_{month:02d}.pdf',mime='application/pdf',icon=':material/picture_as_pdf:',use_container_width=True)
        with p3:
            st.download_button('Export Excel',excel_export(rows,trend,name,period),file_name=f'geospatial_{year}_{month:02d}.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',icon=':material/table_view:',use_container_width=True)
    except Exception as exc:
        st.error(f'Could not generate export: {exc}')
    html('<div class="geo-note"><b>Interpretation:</b> Hospital-scoped confirmed case counts only. Not epidemiological incidence, transmission estimates, or validated risk thresholds.</div>')


if __name__ == '__main__':
    show()

# Note: map tile provider is OpenStreetMap (no API key required).
