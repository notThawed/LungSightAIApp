# streamlit_app/components/map.py

"""
Shared map rendering for LungSight.

Both the hospital admin's "My Hospital" page and
the system admin's "Client Hospitals" page call
render_hospital_map() from here.

Uses streamlit-folium + Folium. Tiles come from
CartoDB (Voyager style) when CARTO_API_KEY is set
in the environment, otherwise falls back to plain
OpenStreetMap tiles.
"""

import os

from dotenv import load_dotenv

import folium
from folium import Marker, CircleMarker

from streamlit_folium import st_folium


# ============================================================
# ENV
# ============================================================

load_dotenv()

CARTO_API_KEY = os.getenv("CARTO_API_KEY", "").strip()


# ============================================================
# CONFIG
# ============================================================

if CARTO_API_KEY:

    # CartoDB Voyager — clean, muted, Google-Maps-like
    DEFAULT_TILES = (
        "https://basemaps.cartocdn.com/rastertiles/voyager/"
        "{z}/{x}/{y}.png"
        f"?key={CARTO_API_KEY}"
    )

    DEFAULT_ATTR = (
        "&copy; OpenStreetMap contributors, "
        "&copy; CARTO"
    )

else:

    # Fallback — plain OpenStreetMap tiles
    DEFAULT_TILES = "OpenStreetMap"

    DEFAULT_ATTR = "&copy; OpenStreetMap contributors"


SINGLE_HOSPITAL_ZOOM = 16
MULTI_HOSPITAL_ZOOM = 11


# ============================================================
# MAIN RENDERER
# ============================================================

def render_hospital_map(
    hospitals,
    selected_id=None,
    height=560,
    key="hospital_map",
    zoom=None,
):
    """
    Render a hospital directory map.

    Args:
        hospitals: list of hospital dicts. Each must contain
                   at least:
                       hospital_id, hospital_name,
                       latitude, longitude

        selected_id: hospital_id of the hospital to highlight.
                     Highlighted = filled red pin.
                     Others       = small blue circle.

        height: map height in pixels.

        key: unique Streamlit key for this map instance.
             Use a different key for each page.

        zoom: override the auto-computed zoom level.

    Returns:
        The st_folium output dict. Use
        output["last_object_clicked_tooltip"] to know
        which hospital the user clicked.
    """

    # --------------------------------------------------------
    # Guard: nothing to render
    # --------------------------------------------------------

    if not hospitals:
        return None

    # --------------------------------------------------------
    # Pick a center and zoom level
    # --------------------------------------------------------

    if selected_id:

        selected = next(
            (
                h for h in hospitals
                if h["hospital_id"] == selected_id
            ),
            hospitals[0],
        )

        center = [
            selected["latitude"],
            selected["longitude"],
        ]

        auto_zoom = SINGLE_HOSPITAL_ZOOM

    else:

        avg_lat = sum(
            h["latitude"] for h in hospitals
        ) / len(hospitals)

        avg_lon = sum(
            h["longitude"] for h in hospitals
        ) / len(hospitals)

        center = [avg_lat, avg_lon]

        auto_zoom = MULTI_HOSPITAL_ZOOM

    # --------------------------------------------------------
    # Build the Folium map
    # --------------------------------------------------------

    m = folium.Map(
        location=center,
        zoom_start=zoom or auto_zoom,
        tiles=DEFAULT_TILES,
        attr=DEFAULT_ATTR,
        control_scale=True,
    )

    # --------------------------------------------------------
    # Plot each hospital
    # --------------------------------------------------------

    for h in hospitals:

        lat = h.get("latitude")
        lon = h.get("longitude")

        if lat is None or lon is None:
            continue

        name = h.get("hospital_name") or "Hospital"

        is_selected = (
            selected_id is not None
            and h["hospital_id"] == selected_id
        )

        if is_selected:

            # Big red marker with a plus glyph
            Marker(
                location=[lat, lon],
                tooltip=name,
                icon=folium.Icon(
                    color="red",
                    icon="plus-sign",
                    prefix="glyphicon",
                ),
            ).add_to(m)

        else:

            # Small blue circle marker
            CircleMarker(
                location=[lat, lon],
                radius=7,
                color="#2563eb",
                weight=2,
                fill=True,
                fill_color="#2563eb",
                fill_opacity=0.75,
                tooltip=name,
            ).add_to(m)

    # --------------------------------------------------------
    # Render in Streamlit
    # --------------------------------------------------------

    return st_folium(
        m,
        height=height,
        use_container_width=True,
        key=key,
        returned_objects=[
            "last_object_clicked",
            "last_object_clicked_tooltip",
        ],
    )