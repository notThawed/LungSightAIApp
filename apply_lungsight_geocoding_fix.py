"""Safely patch LungSightDefense patient CRUD and Geoapify fallback geocoding.

Run from the LungSightAIApp repository root:
    python apply_lungsight_geocoding_fix.py

Creates timestamped .bak backups, refuses to patch unexpected code, and does
not connect to Supabase or Geoapify itself.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
CRUD_PATH = ROOT / 'backend' / 'crud.py'
GEO_PATH = ROOT / 'backend' / 'geospatial_backend' / 'barangay_geocoding.py'


def replace_once(src: str, before: str, after: str, label: str) -> str:
    count = src.count(before)
    if count != 1:
        raise RuntimeError(f'{label}: expected one exact match, found {count}; no files modified')
    return src.replace(before, after, 1)


def patched_crud(original: str) -> str:
    src = original
    import_anchor = 'from backend.backend_utils.password_policy import validate_strong_password\n'
    src = replace_once(src, import_anchor,
        import_anchor + 'from backend.geospatial_backend.barangay_geocoding import prepare_patient_coordinates\n',
        'CRUD geocoding import')

    create_start = src.index('def create_patient(')
    update_start = src.index('def update_patient(', create_start)
    delete_start = src.index('def delete_patient(', update_start)
    create = src[create_start:update_start]
    update = src[update_start:delete_start]

    create_anchor = '''        response = (
            admin_supabase
            .table("patients")
            .insert(patient_data)
'''
    create = replace_once(create, create_anchor,
        '''        # PSGC-based barangay reference only; never geocode a patient's home.
        patient_data = prepare_patient_coordinates(patient_data, db=admin_supabase)

''' + create_anchor, 'create_patient save')

    update_anchor = '''        response = (
            admin_supabase
            .table("patients")
            .update(patient_data)
'''
    update = replace_once(update, update_anchor,
        '''        # Read previous PSGC/coordinates to retain a verified point only
        # when the patient's barangay has not changed.
        previous_rows = (
            admin_supabase.table("patients")
            .select("psgc_barangay_code,latitude,longitude,location_precision")
            .eq("patient_id", patient_id)
            .limit(1)
            .execute().data or []
        )
        if not previous_rows:
            raise ValueError("Patient not found; coordinate-safe update cancelled")
        patient_data = prepare_patient_coordinates(
            patient_data, previous=previous_rows[0], db=admin_supabase
        )

''' + update_anchor, 'update_patient save')
    return src[:create_start] + create + update + src[delete_start:]


def patched_geo(original: str) -> str:
    src = original
    city_anchor = '''    city_name = str(city).strip()
    if city_name.lower().startswith("city of "):
        city_name = city_name[8:].strip() + " City"
    query = ", ".join(part for part in (barangay, city_name, province, "Philippines") if part)
'''
    # Keep exact-match validation; normalize only query construction.
    src = replace_once(src, city_anchor,
        '''    city_name = str(city).strip()
    city_base = _norm_city(city_name)
    # Prefer the PSGC name; then try bare city name (e.g., "Mandaue"),
    # followed by "Mandaue City" for Geoapify's differing naming conventions.
    variants = [city_name, city_base, city_base.title() + " City"]
    city_variants = list(dict.fromkeys(v for v in variants if v))
''', 'Geoapify city variants')

    block_start = src.index('    try:\n        response = requests.get(', src.index('def _geocode_api_cached('))
    block_end = src.index('\n\ndef geocode_barangay(', block_start)
    replacement = '''    try:
        # Do not allow any one failing query to silence another unambiguous
        # geographic match. Query ONLY the public barangay/city/province.
        for variant in city_variants:
            query = ", ".join(part for part in (
                barangay, variant, province, "Philippines") if part)
            response = requests.get(
                GEOAPIFY_URL,
                params={"text": query, "filter": "countrycode:ph", "format": "json",
                        "limit": 8, "apiKey": api_key},
                timeout=(5, 15),
            )
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results", []) if isinstance(payload, dict) else []
            if not isinstance(results, list):
                continue
            valid = [r for r in results if isinstance(r, dict)
                     and _candidate_matches(r, barangay, city, province)]
            if expected_code:
                valid = [r for r in valid if not _reference_codes(r)
                         or _reference_codes(r) == {expected_code}]
                exact = [r for r in valid if _reference_codes(r) == {expected_code}]
                if exact:
                    valid = exact
            unique = {(round(float(r["lat"]), 5), round(float(r["lon"]), 5))
                      for r in valid}
            # Multiple plausible points are ambiguous: do not guess, and do
            # not turn an amenity, school or road into a barangay point.
            if len(unique) > 1:
                LOGGER.warning("Ambiguous barangay geocoding: %s, %s, PSGC=%s, candidates=%s",
                               barangay, city, expected_code, len(unique))
                return None
            if len(unique) == 1:
                lat, lon = next(iter(unique))
                point = {"latitude": lat, "longitude": lon,
                         "location_precision": "barangay", "source": "geoapify"}
                with _CACHE_LOCK:
                    if len(_SUCCESS_CACHE) >= 1024:
                        _SUCCESS_CACHE.pop(next(iter(_SUCCESS_CACHE)), None)
                    _SUCCESS_CACHE[cache_key] = point
                return dict(point)
        LOGGER.warning("Unresolved barangay geocoding: %s, %s, PSGC=%s",
                       barangay, city, expected_code)
        return None
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        LOGGER.warning("Geocoding unavailable for %s, %s: %s", barangay, city, type(exc).__name__)
        return None
'''
    src = src[:block_start] + replacement + src[block_end:]
    return src


def main() -> None:
    originals = {}
    transformed = {}
    for path, handler in [(CRUD_PATH, patched_crud), (GEO_PATH, patched_geo)]:
        if not path.is_file():
            raise SystemExit(f'Missing {path}; run from the repo root on LungSightDefense')
        originals[path] = path.read_text(encoding='utf-8')
        if 'LUNGSIGHT_AUTO_COORDS_PATCH_20261126' in originals[path]:
            raise SystemExit(f'Already patched: {path}')
        transformed[path] = '# LUNGSIGHT_AUTO_COORDS_PATCH_20261126\n' + handler(originals[path])
        compile(transformed[path], str(path), 'exec')

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    for path, content in originals.items():
        backup = path.with_suffix(path.suffix + '.' + stamp + '.bak')
        backup.write_text(content, encoding='utf-8')
        print(f'Backup: {backup.relative_to(ROOT)}')
    for path, content in transformed.items():
        path.write_text(content, encoding='utf-8')
        print(f'Patched: {path.relative_to(ROOT)}')
    print('Patch complete. Review git diff, run pytest and preview the backfill before applying.')

if __name__ == '__main__':
    main()
