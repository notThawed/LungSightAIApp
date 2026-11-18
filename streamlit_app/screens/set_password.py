
"""LungSightAI password creation and recovery page."""
from __future__ import annotations
import re
from pathlib import Path
import streamlit as st
from supabase import create_client
from backend.supabase_client import SUPABASE_URL, SUPABASE_KEY
from backend import audit

CSS = Path(__file__).resolve().parents[2] / "shared" / "theme" / "css_content" / "set_password.css"
BAD_PASSWORDS = {
    "password123!", "password1234", "password12345", "qwerty123!",
    "welcome123!", "admin12345!", "lungsight123!", "1234567890!",
}


def _html(markup):
    st.markdown(markup, unsafe_allow_html=True)


def _cleanup():
    for key in (
        "invite_access_token", "invite_refresh_token", "invite_session_ready",
        "invite_type", "ls_recovery_auth_client", "password_set_success",
        "ls_new_password", "ls_confirm_password", "ls_link_error",
    ):
        st.session_state.pop(key, None)
    st.query_params.clear()


def _to_login(recover=False):
    _cleanup()
    st.session_state["logged_in"] = False
    st.session_state["user"] = None
    st.session_state["public_page"] = "login"
    st.session_state["ls_auth_view"] = "forgot" if recover else "login"
    st.rerun()


def _checks(password):
    return {
        "12 or more characters": len(password) >= 12,
        "Uppercase and lowercase letters": bool(re.search(r"[A-Z]", password))
                                          and bool(re.search(r"[a-z]", password)),
        "At least one number": bool(re.search(r"\d", password)),
        "At least one symbol": bool(re.search(r"[^A-Za-z0-9\s]", password)),
        "No spaces": not any(c.isspace() for c in password),
        "Not a common password": password.casefold() not in BAD_PASSWORDS,
    }


def _show_rules(password, confirm):
    checks = _checks(password)
    score = sum(checks.values())
    _html('<div class="ls-pw-rules-title"><span class="material-symbols-rounded">shield_lock</span>Strong password requirements</div>')
    st.progress(score / len(checks), text=f"{score} of {len(checks)} requirements met")
    for label, valid in checks.items():
        icon = "check_circle" if valid else "radio_button_unchecked"
        css_class = "met" if valid else "pending"
        _html(f'<div class="ls-pw-rule {css_class}"><span class="material-symbols-rounded">{icon}</span>{label}</div>')
    if confirm:
        if password == confirm:
            st.caption("✅ Passwords match")
        else:
            st.caption("❌ Passwords do not match")
    return bool(password) and all(checks.values()) and password == confirm


def _session_client(access, refresh):
    client = st.session_state.get("ls_recovery_auth_client")
    if client is not None and st.session_state.get("invite_session_ready"):
        return client
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    response = client.auth.set_session(access, refresh)
    if not getattr(response, "user", None):
        raise ValueError("The account access link could not be verified.")
    session = getattr(response, "session", None)
    if session:
        st.session_state["invite_access_token"] = getattr(session, "access_token", access)
        st.session_state["invite_refresh_token"] = getattr(session, "refresh_token", refresh)
    st.session_state["ls_recovery_auth_client"] = client
    st.session_state["invite_session_ready"] = True
    return client


def show():
    if CSS.is_file():
        _html("<style>" + CSS.read_text(encoding="utf-8") + "</style>")
    _html('<div class="ls-pw-brand"><span class="material-symbols-rounded">pulmonology</span><div>LungSight<b>AI</b><small>CLINICAL INTELLIGENCE PLATFORM</small></div></div>')

    if st.session_state.get("password_set_success"):
        _html('<div class="ls-pw-hero"><span class="ls-pw-eyebrow">ACCOUNT READY</span><h1>Password updated successfully.</h1><p>Your account is secured. Sign in with your email and new password.</p></div>')
        st.success("Your new password has been saved.")
        if st.button("Go to Login", type="primary", use_container_width=True, icon=":material/login:", key="ls_done_login"):
            _to_login()
        return

    access = st.session_state.get("invite_access_token")
    refresh = st.session_state.get("invite_refresh_token")
    invite_type = (st.session_state.get("invite_type") or "invite").strip().lower()
    heading = "Reset your password." if invite_type == "recovery" else "Secure your account."
    subheading = ("Set a strong new password to regain access to LungSightAI."
                  if invite_type == "recovery"
                  else "Create a strong password to complete your LungSightAI account setup.")
    _html(f'<div class="ls-pw-hero"><span class="ls-pw-eyebrow">SECURE ACCOUNT ACCESS</span><h1>{heading}</h1><p>{subheading}</p></div>')

    if not access or not refresh:
        st.warning("This account access link is missing or expired. You can request a fresh email.")
        if st.button("Request a new password link", use_container_width=True, icon=":material/mail:", key="ls_missing_recovery"):
            _to_login(recover=True)
        if st.button("Back to Login", use_container_width=True, key="ls_missing_login"):
            _to_login()
        return

    try:
        client = _session_client(access, refresh)
    except Exception:
        st.session_state.pop("ls_recovery_auth_client", None)
        st.session_state["invite_session_ready"] = False
        st.error("This link is invalid, expired, or has already been used.")
        if st.button("Email me a new link", type="primary", use_container_width=True, icon=":material/mail:", key="ls_expired_recovery"):
            _to_login(recover=True)
        if st.button("Back to Login", use_container_width=True, key="ls_expired_login"):
            _to_login()
        return

    _html('<div class="ls-pw-form-title">Create a strong password</div>')
    password = st.text_input("New Password", type="password", icon=":material/lock:",
                             placeholder="Enter a strong password", key="ls_new_password")
    confirm = st.text_input("Confirm Password", type="password", icon=":material/verified_user:",
                            placeholder="Re-enter your password", key="ls_confirm_password")
    valid = _show_rules(password, confirm)
    if st.button("Save Password", type="primary", use_container_width=True, disabled=not valid,
                 icon=":material/arrow_forward:", key="ls_pw_submit"):
        try:
            response = client.auth.update_user({"password": password})
            user = getattr(response, "user", None)
            if not user:
                st.error("Password update could not be confirmed. Please try again.")
                return
            if invite_type != "recovery":
                try:
                    audit.record_event(
                        "user.invite_accepted",
                        target_id=user.id,
                        metadata={"source": invite_type},
                        verified_actor_id=user.id,
                    )
                except Exception:
                    pass
            st.session_state["password_set_success"] = True
            st.rerun()
        except Exception:
            st.error("Could not save your password. Please request a fresh link if this one has expired.")
            if st.button("Request another link", key="ls_pw_error_recover"):
                _to_login(recover=True)

    _html('<div class="ls-pw-footer"><span class="material-symbols-rounded">lock</span>Secure LungSightAI account access</div>')
