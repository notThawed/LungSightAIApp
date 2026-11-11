"""One shared hospital-scoped geospatial monitoring page for all Streamlit roles.

Currently DEMONSTRATION ONLY. Never interprets simulated records as real patient data.
"""
from __future__ import annotations
from collections import Counter
from datetime import date
from html import escape
from io import BytesIO
from pathlib import Path
from streamlit_app.components.map import DEFAULT_TILES, DEFAULT_ATTR
from streamlit_app.components.ui import refresh_button

import folium
import pandas as pd
import streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium

from backend.supabase_client import admin_supabase
from backend.backend_utils.geospatial_utils import (
    MANDAUE, AGE_GROUPS, demo_records, aggregate, summary_rows, month_shift,
)

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
    """Revalidate hospital/role from the database; never trust user-selected hospital for normal roles."""
    session=st.session_state.get('user') or {}
    uid=session.get('user_id') or session.get('id')
    if not uid: raise PermissionError('Please sign in again.')
    result=(admin_supabase.table('user_profiles').select('user_id,hospital_id,role_id,is_active')
            .eq('user_id',uid).limit(1).execute()).data or []
    if not result: raise PermissionError('Your user profile could not be verified.')
    profile=result[0]
    if profile.get('is_active') is False: raise PermissionError('Your account is inactive.')
    role=_role(profile)
    if role <= 0: raise PermissionError('This role is not authorized for geospatial monitoring.')
    role_rows=(admin_supabase.table('roles').select('role_name').eq('role_id',role).limit(1).execute()).data or []
    role_name=str((role_rows[0] if role_rows else {}).get('role_name') or '').lower().replace(' ','').replace('_','')
    if role_name in ('superadmin','systemadministrator','systemadmin'):
        hospitals=(admin_supabase.table('hospitals').select('hospital_id,hospital_name,address,latitude,longitude').order('hospital_name').execute()).data or []
        if not hospitals: raise PermissionError('No hospitals are registered.')
        names={str(h['hospital_id']):h for h in hospitals}
        chosen=st.selectbox('Hospital',list(names),format_func=lambda k:names[k].get('hospital_name') or k,key='geo_hospital')
        return names[chosen]
    hospital_id=profile.get('hospital_id')
    if not hospital_id: raise PermissionError('No hospital is assigned to your account.')
    rows=(admin_supabase.table('hospitals').select('hospital_id,hospital_name,address,latitude,longitude')
          .eq('hospital_id',hospital_id).limit(1).execute()).data or []
    if not rows: raise PermissionError('Your assigned hospital was not found.')
    return rows[0]


def month_options():
    now=date.today(); return [month_shift(now.year,now.month,-i) for i in range(0,25)]


def make_map(rows, mode, selected, hospital):
    anchors={name:(lat,lon) for name,lat,lon in MANDAUE}
    center=[10.352,123.944]
    m = folium.Map(
    location=center,
    zoom_start=12,
    tiles=DEFAULT_TILES,
    attr=DEFAULT_ATTR,
    control_scale=True,
    )
    max_count=max([r['Recorded cases'] for r in rows],default=1)
    if mode=='Heatmap':
        heat=[[anchors[r['Barangay']][0],anchors[r['Barangay']][1],r['Recorded cases']]
              for r in rows if r['Recorded cases']>0]
        if heat: HeatMap(heat,radius=32,blur=23,min_opacity=.3).add_to(m)
    for row in rows:
        name=row['Barangay']; lat,lon=anchors[name]; count=row['Recorded cases']
        color=COLORS[row['Concentration']]
        folium.CircleMarker(location=[lat,lon],radius=7+min(17,count/max(1,max_count)*16) if mode=='Hotspots' else 5,
            color='#fff' if name==selected else color,weight=3 if name==selected else 1,
            fill=True,fill_color=color,fill_opacity=.9 if mode=='Hotspots' else .45,
            tooltip=f'{name} — {count} synthetic recorded cases',
            popup=folium.Popup(f'<b>{escape(name)}</b><br>{count} synthetic cases<br>{row["Concentration"]} relative concentration',max_width=260)).add_to(m)
    lat=hospital.get('latitude');lon=hospital.get('longitude')
    if lat is not None and lon is not None:
        folium.Marker([float(lat),float(lon)],tooltip='Selected hospital',icon=folium.Icon(color='blue',icon='plus-sign')).add_to(m)
    return m


def png_export(rows, hospital_name, label):
    """Static schematic coordinate scatter; no web tiles. Explicitly not a screenshot of live tiles."""
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(11,7),dpi=160)
    fig.patch.set_facecolor('white');ax.set_facecolor('#f1f8fa')
    for r in rows:
        if r['Recorded cases']==0: continue
        name=r['Barangay']; anchor=next((a for a in MANDAUE if a[0]==name),None)
        if not anchor: continue
        ax.scatter(anchor[2],anchor[1],s=70+r['Recorded cases']*17,c=COLORS[r['Concentration']],alpha=.78,edgecolors='white',linewidths=1.5)
        ax.annotate(name,(anchor[2],anchor[1]),xytext=(4,5),textcoords='offset points',fontsize=7)
    ax.set_title(f'{hospital_name} | {label}\nSynthetic barangay case distribution (schematic, approximate locations)',fontsize=13,fontweight='bold')
    ax.set_xlabel('Longitude (approximate)');ax.set_ylabel('Latitude (approximate)');ax.grid(alpha=.15)
    fig.text(.05,.025,'DEMONSTRATION ONLY — not real patient addresses, incidence, transmission, or clinical risk.',fontsize=9)
    fig.tight_layout(rect=[0,.04,1,1]);buf=BytesIO();fig.savefig(buf,format='png',dpi=160);plt.close(fig);return buf.getvalue()


def pdf_export(rows,hospital_name,label,png):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Image,Table,TableStyle
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4,landscape
    buf=BytesIO();doc=SimpleDocTemplate(buf,pagesize=landscape(A4),leftMargin=35,rightMargin=35)
    styles=getSampleStyleSheet();story=[Paragraph('LungSightAI | Geospatial Demonstration Report',styles['Title']),
      Paragraph(f'{escape(hospital_name)} — {escape(label)}',styles['Heading2']),
      Paragraph('SYNTHETIC DEMONSTRATION DATA. Relative case concentration is not epidemiological incidence or risk.',styles['Normal']),Spacer(1,10)]
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
        pd.DataFrame([{'Hospital':hospital_name,'Period':label,'Data source':'SYNTHETIC DEMONSTRATION','Interpretation':'Not actual incidence, transmission or patient addresses'}]).to_excel(writer,sheet_name='Read Me',index=False)
        for sheet in writer.sheets.values():sheet.set_column(0,12,22)
    return buf.getvalue()


def show():
    if CSS.is_file(): html('<style>'+CSS.read_text(encoding='utf-8')+'</style>')
    header_col, refresh_col = st.columns([8, 0.7], vertical_alignment='center')
    with header_col:
        html('<div class="geo-hero"><div class="geo-eyebrow">LungSightAI · Analytics & Monitoring</div><div class="geo-title">Geospatial Case Monitoring</div><div class="geo-sub">Barangay-level pneumonia case visualization and hospital planning</div></div>')
    with refresh_col:
        refresh_button('page_refresh_geospatial_mapping')
    try: hospital=hospital_context()
    except Exception as exc:
        st.error(f'Cannot load hospital context: {exc}');return
    name=hospital.get('hospital_name') or 'Selected hospital';address=hospital.get('address') or ''
    if 'mandaue' not in (name+' '+address).lower():
        st.warning('This hospital is not identified as being in Mandaue City. The map below uses a **Mandaue City demonstration area** only; it does not represent this hospital’s actual catchment area or patients.')
    st.info('DEMONSTRATION MODE — All case counts, demographics, and trends are synthetic. Barangay marker locations are approximate; no patient addresses are used.')
    options=month_options();labels={f'{date(y,m,1):%B %Y}':(y,m) for y,m in options}
    c1,c2,c3,c4=st.columns([1.4,1.4,1,1])
    with c1: period=st.selectbox('Reporting month',list(labels),index=0,key='geo_month')
    with c2: chosen=st.multiselect('Barangays',[a[0] for a in MANDAUE],default=[a[0] for a in MANDAUE],key='geo_barangays')
    with c3: age=st.selectbox('Age group',['All ages',*AGE_GROUPS],key='geo_age')
    with c4: sex=st.selectbox('Sex',['All', 'Female','Male'],key='geo_sex')
    if not chosen: st.warning('Select at least one barangay.');return
    year,month=labels[period];previous_year,previous_month=month_shift(year,month,-1)
    hid=str(hospital['hospital_id'])
    current=demo_records(hid,year,month);previous=demo_records(hid,previous_year,previous_month)
    counts=aggregate(current,chosen,age,sex);prior=aggregate(previous,chosen,age,sex)
    rows=summary_rows(counts,prior);total=sum(counts.values());prior_total=sum(prior.values())
    highest=rows[0]['Barangay'] if rows and rows[0]['Recorded cases'] else '—'
    change=f'{(total-prior_total)/prior_total:+.1%}' if prior_total else 'N/A'
    kpis=[('Recorded cases',str(total)),('Barangays with cases',f'{sum(x>0 for x in counts.values())} / {len(chosen)}'),('Highest-count barangay',highest),('Month-over-month change',change)]
    for col,(label,value) in zip(st.columns(4),kpis):
        with col:html(f'<div class="geo-kpi"><div class="geo-kpi-label">{escape(label)}</div><div class="geo-kpi-value">{escape(value)}</div></div>')
    st.write('')
    left,right=st.columns([1.5,1],gap='medium')
    with left:
        section('Geographic Distribution')
        mode=st.segmented_control('Map layer',['Hotspots','Heatmap'],default='Hotspots',key='geo_layer')
        selected=st.session_state.get('geo_selected')
        result=st_folium(make_map(rows,mode,selected,hospital),height=510,width=None,use_container_width=True,key=f'geo_map_{hid}_{mode}',returned_objects=['last_object_clicked','last_object_clicked_tooltip'])
        tooltip=(result or {}).get('last_object_clicked_tooltip') or ''
        if ' — ' in tooltip:
            clicked=tooltip.split(' — ',1)[0]
            if clicked in counts and clicked!=selected:
                st.session_state['geo_selected']=clicked;st.rerun()
        html('<div class="geo-note">🟢 Lower &nbsp;&nbsp; 🟠 Moderate &nbsp;&nbsp; 🔴 Higher — relative counts within the selected dataset, not disease risk. Markers are illustrative barangay anchors.</div>')
    with right:
        section('Barangay Case Summary')
        st.dataframe(pd.DataFrame(rows)[['Barangay','Recorded cases','Concentration','Previous month','Change (%)']],hide_index=True,use_container_width=True,height=270)
        options_by_name=[r['Barangay'] for r in rows]
        default_idx=options_by_name.index(selected) if selected in options_by_name else 0
        barangay=st.selectbox('Select barangay to inspect',options_by_name,index=default_idx,key='geo_detail_pick')
        if st.button('View Detailed Summary',icon=':material/insights:',use_container_width=True,type='primary'):
            st.session_state['geo_detail_open']=barangay
        if st.session_state.get('geo_detail_open'):
            selected_name=st.session_state['geo_detail_open']
            r=next((x for x in rows if x['Barangay']==selected_name),None)
            if r:
                html(f'<div class="geo-note"><b>{escape(selected_name)}</b><br>Recorded synthetic cases: <b>{r["Recorded cases"]}</b><br>Relative concentration: <b>{escape(r["Concentration"])}</b><br>Previous month: {r["Previous month"]}<br>Change: {r["Change (%)"] if r["Change (%)"] is not None else "N/A"}%</div>')
                sample=[x for x in current if x['barangay']==selected_name and (age=='All ages' or x['age_group']==age) and (sex=='All' or x['sex']==sex)]
                if sample:
                    st.caption('Synthetic age distribution')
                    st.bar_chart(pd.Series(Counter(x['age_group'] for x in sample)).reindex(AGE_GROUPS,fill_value=0))
                if st.button('Close summary',key='geo_close_summary'):
                    st.session_state.pop('geo_detail_open',None);st.rerun()
        section('Monthly Trend')
        trend=[]
        for offset in range(-5,1):
            yy,mm=month_shift(year,month,offset)
            n=sum(aggregate(demo_records(hid,yy,mm),chosen,age,sex).values())
            trend.append({'Month':f'{date(yy,mm,1):%b %Y}','Cases':n})
        st.line_chart(pd.DataFrame(trend).set_index('Month'),height=190)
    section('Export Geospatial Report')
    st.caption('Exports reflect the currently selected hospital, reporting month, barangays, age group, and sex. PNG is a schematic coordinate plot, not a screenshot of map tiles.')
    try:
        png=png_export(rows,name,period)
        p1,p2,p3=st.columns(3)
        with p1:st.download_button('Export PNG',png,file_name=f'geospatial_{year}_{month:02d}.png',mime='image/png',icon=':material/image:',use_container_width=True)
        with p2:st.download_button('Export PDF',pdf_export(rows,name,period,png),file_name=f'geospatial_{year}_{month:02d}.pdf',mime='application/pdf',icon=':material/picture_as_pdf:',use_container_width=True)
        with p3:st.download_button('Export Excel',excel_export(rows,trend,name,period),file_name=f'geospatial_{year}_{month:02d}.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',icon=':material/table_view:',use_container_width=True)
    except Exception as exc:st.error(f'Could not generate export: {exc}')
    html('<div class="geo-note"><b>Interpretation:</b> Synthetic hospital-scoped counts demonstrate visualization workflows only. No real patient addresses, population denominators, epidemiological incidence, transmission estimates, or validated risk thresholds are included.</div>')