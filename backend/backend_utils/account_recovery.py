
"""Password recovery services for LungSightAI.

No passwords, tokens, or user-existence information are returned from the
public request path. A new public Auth client is created per request.
"""
from __future__ import annotations
import re
from supabase import create_client
from backend.supabase_client import SUPABASE_URL, SUPABASE_KEY, admin_supabase
from backend import audit

import os

APP_ENV = os.getenv("LUNGSIGHT_ENV", "production").lower()

REDIRECT_URL = (
    "https://notthawed.github.io/LungSightAuthRedirect/?env=local"
    if APP_ENV == "local"
    else "https://notthawed.github.io/LungSightAuthRedirect/"
)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def request_recovery_email(email: str) -> None:
    email = (email or "").strip().lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("Enter a valid email address.")
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    client.auth.reset_password_for_email(
        email,
        {"redirect_to": REDIRECT_URL},
    )


def send_staff_access_email(actor_id: str, target_id: str) -> None:
    """Server-side permission checked admin action. Uses existing Auth email."""
    if not actor_id or not target_id:
        raise PermissionError("An authenticated administrator is required.")

    actor_result = (admin_supabase.table("user_profiles")
                    .select("user_id,is_active,hospital_id,roles(role_name)")
                    .eq("user_id", str(actor_id)).limit(1).execute())
    actor_rows = actor_result.data or []
    if not actor_rows:
        raise PermissionError("Administrator account not found.")
    actor = actor_rows[0]
    role = ((actor.get("roles") or {}).get("role_name") or "").strip().lower()
    if not actor.get("is_active") or role not in ("superadmin", "hospital admin"):
        raise PermissionError("Not authorized to send account access links.")

    target_result = (admin_supabase.table("user_profiles")
                     .select("user_id,is_active,hospital_id,roles(role_name)")
                     .eq("user_id", str(target_id)).limit(1).execute())
    target_rows = target_result.data or []
    if not target_rows:
        raise ValueError("Staff account not found.")
    target = target_rows[0]
    if not target.get("is_active"):
        raise ValueError("Reactivate the staff account before sending an access link.")
    if role == "hospital admin":
        if (not actor.get("hospital_id")
            or str(actor["hospital_id"]) != str(target.get("hospital_id"))
            or ((target.get("roles") or {}).get("role_name") or "").strip().lower() == "superadmin"):
            raise PermissionError("You can only manage staff from your hospital.")

    auth_response = admin_supabase.auth.admin.get_user_by_id(str(target_id))
    auth_user = getattr(auth_response, "user", None)
    auth_email = (getattr(auth_user, "email", None) or "").strip()
    if not auth_email:
        raise ValueError("This staff account has no authentication email.")

    # Recovery links let existing invited accounts set a password without
    # attempting to create a duplicate Supabase Auth user.
    request_recovery_email(auth_email)

    try:
        audit.record_event(
            "auth.account_access_email_requested",
            target_id=str(target_id),
            target_hospital_id=target.get("hospital_id"),
            metadata={"source": "manage_users"},
            verified_actor_id=str(actor_id),
        )
    except Exception:
        # Do not claim the mail failed after the request was already accepted.
        pass
