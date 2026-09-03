from pathlib import Path
import html
import base64

import streamlit as st

VBASE_DIR = Path(__file__).resolve().parents[2]
LOGO_PATH = VBASE_DIR / "shared" / "images" / "LungSight Logo.png"

NAVBAR_CSS_PATH = VBASE_DIR / "shared" / "theme" / "css_content" / "navbar.css"


def _load_navbar_css() -> None:
	if NAVBAR_CSS_PATH.exists():
		st.markdown(f"<style>{NAVBAR_CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def _role_label(role_value: str | None) -> str:
	if not role_value:
		return "User"
	role_lower = str(role_value).lower()
	if "technologist" in role_lower or "radtech" in role_lower:
		return "Radiologic Technologist"
	if "radiologist" in role_lower or "physician" in role_lower:
		return "Radiologist"
	if "admin" in role_lower:
		return "Hospital Admin"
	return str(role_value)


def _initials(name: str) -> str:
	parts = [segment for segment in name.strip().split() if segment]
	if not parts:
		return "U"
	if len(parts) == 1:
		return parts[0][0].upper()
	return f"{parts[0][0]}{parts[-1][0]}".upper()


def _avatar_html(user: dict) -> str:
	avatar_url = user.get("profile_picture") or user.get("avatar_url")
	if avatar_url:
		return f'<img src="{avatar_url}" alt="User profile" class="ls-nav-avatar-image">'
	return f'<div class="ls-nav-avatar-fallback">{_initials(user.get("name", "User"))}</div>'


def _logo_data_uri() -> str:
	if not LOGO_PATH.exists():
		return ""
	encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8")
	return f"data:image/png;base64,{encoded}"


def show_top_navbar(page_name: str, page_info: str) -> None:
	_load_navbar_css()

	user = st.session_state.get("user") or {}
	user_name = user.get("name", "User")
	role_text = _role_label(user.get("role"))

	with st.container(key="top_navbar"):
		# Two columns: left for logo/name, right for profile
		left_col, right_col = st.columns([2.5, 1.5], vertical_alignment="center")

		with left_col:
			logo_html = ""
			logo_uri = _logo_data_uri()
			if logo_uri:
				logo_html = f'<img src="{logo_uri}" class="ls-nav-brand-logo" alt="LungSight logo">'
			st.markdown(
				f"""
				<div class="ls-nav-left-wrap">
					{logo_html}
					<div class="ls-nav-appname">LungSight</div>
				</div>
				""",
				unsafe_allow_html=True,
			)

		with right_col:
			st.markdown(
				f"""
				<div class="ls-nav-profile-wrap">
					{ _avatar_html(user) }
					<div class="ls-nav-user-text">
						<div class="ls-nav-user-name">{user_name}</div>
						<div class="ls-nav-user-role">{role_text}</div>
					</div>
				</div>
				""",
				unsafe_allow_html=True,
			)

