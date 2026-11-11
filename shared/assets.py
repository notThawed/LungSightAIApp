# shared/assets.py

import base64
import mimetypes
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# PATHS
# ============================================================

SHARED = Path(__file__).parent

IMAGES = SHARED / "images"

CSS_ROOT = SHARED / "theme" / "css_content"
JS_DIR = SHARED / "theme" / "js_content"

# ------------------------------------------------------------
# CSS role folders
# ------------------------------------------------------------

SYSTEM_ADMIN_CSS_DIR = CSS_ROOT / "system_admin_css"
PHYSICIAN_CSS_DIR = CSS_ROOT / "physician_css"
STAFF_CSS_DIR = CSS_ROOT / "staff_css"
RADTECH_CSS_DIR = CSS_ROOT / "radtech_css"
HOSPITAL_ADMIN_CSS_DIR = CSS_ROOT / "hospital_admin_css"

# Order matters — earlier folders win when the same filename
# exists in multiple role folders.
ROLE_CSS_DIRS = [
    PHYSICIAN_CSS_DIR,
    STAFF_CSS_DIR,
    RADTECH_CSS_DIR,
    HOSPITAL_ADMIN_CSS_DIR,
    SYSTEM_ADMIN_CSS_DIR,
]


# ============================================================
# FILE READ HELPERS
# ============================================================

@st.cache_data(show_spinner=False)
def _read_cached(path: str, mtime: float) -> str:
    return Path(path).read_text(encoding="utf-8")


def _read(path: Path) -> str:
    # mtime in the cache key means edits to a file show
    # up on the next rerun
    return _read_cached(str(path), path.stat().st_mtime)


# ============================================================
# CSS
# ============================================================

def _resolve_css(name: str):
    """
    Resolve a CSS filename to a real path.

    Search order:
        1. physician_css/<name>
        2. staff_css/<name>
        3. radtech_css/<name>
        4. hospital_admin_css/<name>
        5. system_admin_css/<name>
        6. css_content/<name>

    Also supports explicit path fragments like
    "physician_css/patient_queue.css" — the fragment is
    tried against CSS_ROOT directly.
    """

    candidates = [
        *[folder / name for folder in ROLE_CSS_DIRS],
        SYSTEM_ADMIN_CSS_DIR / name,
        CSS_ROOT / name,
    ]

    for path in candidates:
        if path.exists():
            return path

    # Not found — log so the developer can see where we looked
    print(f"[load_css] not found: {name}")
    print(f"[load_css] searched:")
    for path in candidates:
        print(f"    - {path}")

    return None


def load_css(*names: str):
    """
    Inject one or more CSS files into the main page.

    base.css is always loaded first (from system_admin_css/).
    Role-specific folders are searched automatically.

    Examples:
        load_css("patient_queue.css")   # -> physician_css/patient_queue.css
        load_css("followups.css")       # -> physician_css/followups.css
        load_css("manage_users.css")    # -> system_admin_css/manage_users.css

    Explicit paths still work:
        load_css("physician_css/patient_queue.css")
        load_css("system_admin_css/base.css", "physician_css/patient_queue.css")
    """

    css = ""
    loaded_paths = set()

    # --------------------------------------------------------
    # Resolve each name
    # --------------------------------------------------------

    resolved = []

    for name in names:
        path = _resolve_css(name)
        if path is not None:
            resolved.append((name, path))

    # --------------------------------------------------------
    # Auto-prepend base.css unless caller already supplied one
    # --------------------------------------------------------

    caller_has_base = any(
        path.name == "base.css" for _, path in resolved
    )

    if not caller_has_base:
        base_path = SYSTEM_ADMIN_CSS_DIR / "base.css"

        if base_path.exists():
            css += _read(base_path) + "\n"
            loaded_paths.add(base_path)
        else:
            print(f"[load_css] MISSING base.css at {base_path}")

    # --------------------------------------------------------
    # Append resolved files (dedup by path)
    # --------------------------------------------------------

    for name, path in resolved:
        if path in loaded_paths:
            continue
        css += _read(path) + "\n"
        loaded_paths.add(path)
        print(f"[load_css] loaded {name} from {path}")

    # --------------------------------------------------------
    # Inject
    # --------------------------------------------------------

    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ============================================================
# JS
# ============================================================

def load_js_parent(*names: str):
    """Run JS files that modify the main page (via window.parent.document)."""
    js = "\n".join(_read(JS_DIR / n) for n in names)
    components.html(f"<script>{js}</script>", height=0)


# ============================================================
# WIDGETS
# ============================================================

def load_widget(html: str, css: list[str] = (), js: list[str] = (), height: int = 300):
    """Render an iframe widget with its own CSS and JS bundled in."""
    css_tag = "".join(f"<style>{_read(CSS_ROOT / n)}</style>" for n in css)
    js_tag = "".join(f"<script>{_read(JS_DIR / n)}</script>" for n in js)
    components.html(f"{css_tag}{html}{js_tag}", height=height)


# ============================================================
# IMAGES
# ============================================================

def image_path(name: str) -> str:
    """For st.image(), which accepts a file path."""
    return str(IMAGES / name)


def image_data_uri(name: str) -> str:
    """For images referenced inside CSS or HTML."""
    path = IMAGES / name
    mime = mimetypes.guess_type(path)[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"