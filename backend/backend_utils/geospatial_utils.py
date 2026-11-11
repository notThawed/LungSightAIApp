"""Synthetic, reproducible geospatial demonstration data. NOT clinical surveillance data."""
from __future__ import annotations
from datetime import date
from hashlib import sha256
import random

# Approximate visualization anchors, NOT geocoded patient addresses or official boundaries.
MANDAUE = [
 ('Alang-alang',10.331,123.949),('Bakilid',10.339,123.929),('Banilad',10.352,123.919),
 ('Basak',10.334,123.961),('Cabancalan',10.363,123.932),('Cambaro',10.325,123.942),
 ('Canduman',10.375,123.944),('Casili',10.382,123.930),('Casuntingan',10.346,123.939),
 ('Centro',10.324,123.940),('Cubacub',10.369,123.955),('Guizo',10.321,123.948),
 ('Ibabao-Estancia',10.329,123.935),('Jagobiao',10.388,123.949),('Labogon',10.397,123.950),
 ('Looc',10.315,123.950),('Maguikay',10.345,123.951),('Mantuyong',10.318,123.935),
 ('Opao',10.321,123.959),('Paknaan',10.360,123.966),('Pagsabungan',10.369,123.962),
 ('Subangdaku',10.326,123.922),('Tabok',10.358,123.952),('Tawason',10.386,123.937),
 ('Tingub',10.371,123.934),('Tipolo',10.335,123.945),('Umapad',10.342,123.965),
]
AGE_GROUPS = ('0–17','18–39','40–59','60+')
SEXES = ('Female','Male')

def month_shift(year, month, delta):
    index = year * 12 + month - 1 + delta
    return index // 12, index % 12 + 1

def demo_records(hospital_id: str, year: int, month: int, city: str = 'Mandaue City'):
    """Deterministic patient-like aggregate records for demonstration ONLY."""
    rows=[]
    for idx,(barangay,lat,lon) in enumerate(MANDAUE):
        seed=int.from_bytes(sha256(f'{hospital_id}|{year}|{month}|{barangay}'.encode()).digest()[:8],'big')
        rng=random.Random(seed)
        weight=1.8 if barangay in ('Paknaan','Canduman','Tipolo','Maguikay') else 1
        count=max(0,round((rng.randint(0,12)+rng.random()*6)*weight))
        for n in range(count):
            rows.append({'barangay':barangay,'lat':lat,'lon':lon,'age_group':rng.choices(AGE_GROUPS,[20,35,27,18])[0],
                         'sex':rng.choice(SEXES),'year':year,'month':month,'demo':True})
    return rows

def aggregate(records, barangays=None, age='All ages', sex='All'):
    allowed=set(barangays or [x[0] for x in MANDAUE]); counts={name:0 for name in allowed}
    for row in records:
        if row['barangay'] in allowed and (age=='All ages' or row['age_group']==age) and (sex=='All' or row['sex']==sex):
            counts[row['barangay']]+=1
    return counts

def classify(count, max_count):
    """Relative *count concentration* only, NOT epidemiological risk or incidence."""
    if count == 0: return 'No cases'
    ratio=count/max(1,max_count)
    return 'Higher' if ratio>=0.67 else ('Moderate' if ratio>=0.34 else 'Lower')

def summary_rows(counts, previous=None):
    previous=previous or {}; top=max(counts.values(),default=0)
    out=[]
    for name,lat,lon in MANDAUE:
        if name not in counts: continue
        n=counts[name]; prior=previous.get(name,0)
        change=None if prior==0 else round((n-prior)/prior*100,1)
        out.append({'Barangay':name,'Recorded cases':n,'Concentration':classify(n,top),
                    'Previous month':prior,'Change (%)':change,'Latitude (approx.)':lat,'Longitude (approx.)':lon})
    return sorted(out,key=lambda x:(-x['Recorded cases'],x['Barangay']))
