# shared/assets.py
import base64
import mimetypes
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

SHARED = Path(__file__).parent
IMAGES = SHARED / "images"
CSS_DIR = SHARED / "theme" / "css_content"
JS_DIR = SHARED / "theme" / "js_content"


@st.cache_data
def _read_cached(path: str, mtime: float) -> str:
    return Path(path).read_text(encoding="utf-8")


def _read(path: Path) -> str:
    # mtime in the cache key means edits to a file show up on the next rerun
    return _read_cached(str(path), path.stat().st_mtime)


def load_css(*names: str):
    """Inject one or more CSS files into the main page."""
    css = "\n".join(_read(CSS_DIR / n) for n in names)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def load_js_parent(*names: str):
    """Run JS files that modify the main page (via window.parent.document)."""
    js = "\n".join(_read(JS_DIR / n) for n in names)
    components.html(f"<script>{js}</script>", height=0)


def load_widget(html: str, css: list[str] = (), js: list[str] = (), height: int = 300):
    """Render an iframe widget with its own CSS and JS bundled in."""
    css_tag = "".join(f"<style>{_read(CSS_DIR / n)}</style>" for n in css)
    js_tag = "".join(f"<script>{_read(JS_DIR / n)}</script>" for n in js)
    components.html(f"{css_tag}{html}{js_tag}", height=height)


def image_path(name: str) -> str:
    """For st.image(), which accepts a file path."""
    return str(IMAGES / name)


def image_data_uri(name: str) -> str:
    """For images referenced inside CSS or HTML."""
    path = IMAGES / name
    mime = mimetypes.guess_type(path)[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"