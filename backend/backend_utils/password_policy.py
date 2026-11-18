"""One consistent LungSightAI password policy for setup and changes."""
from __future__ import annotations
import re

COMMON_PASSWORDS = {
    "password123!", "password1234", "password12345", "qwerty123!",
    "welcome123!", "admin12345!", "lungsight123!", "1234567890!",
}


def password_checks(password: str) -> dict[str, bool]:
    password = password if isinstance(password, str) else ""
    return {
        "12 or more characters": len(password) >= 12,
        "Uppercase and lowercase letters": bool(re.search(r"[A-Z]", password))
                                           and bool(re.search(r"[a-z]", password)),
        "At least one number": bool(re.search(r"\d", password)),
        "At least one symbol": bool(re.search(r"[^A-Za-z0-9\s]", password)),
        "No spaces": not any(ch.isspace() for ch in password),
        "Not a common password": password.casefold() not in COMMON_PASSWORDS,
    }


def validate_strong_password(password: str) -> tuple[bool, str]:
    checks = password_checks(password)
    missing = [label for label, passed in checks.items() if not passed]
    if missing:
        return False, "Password requirements not met: " + "; ".join(missing) + "."
    return True, ""
