"""
No credentials in the repository, and no email secrets in client code.

Scans tracked + new (non-ignored) files. Test fixtures under tests/ are
excluded because they contain deliberately fake key-shaped values.
"""

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SECRET_PATTERNS = {
    "supabase secret key": re.compile(r"sb_secret_[A-Za-z0-9_-]{10,}"),
    "resend api key": re.compile(r"\bre_[A-Za-z0-9]{16,}"),
    "webhook signing secret": re.compile(r"whsec_[A-Za-z0-9+/=]{16,}"),
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}"),
    "paymongo secret": re.compile(r"sk_(live|test)_[A-Za-z0-9]{10,}"),
    "assigned email secret": re.compile(r"(RESEND_API_KEY|EMAIL_WORKER_SECRET|RESEND_WEBHOOK_SECRET)\s*[=:]\s*['\"][^'\"<]{8,}"),
}

CLIENT_FORBIDDEN = re.compile(r"RESEND|EMAIL_WORKER_SECRET|RESEND_WEBHOOK_SECRET|SERVICE_ROLE", re.I)


def repo_files():
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True, text=True, cwd=ROOT, check=True,
    ).stdout.splitlines()
    for name in out:
        path = ROOT / name
        if not path.is_file() or name.startswith("tests/") or path.suffix in {".pt", ".png", ".jpg", ".jpeg", ".svg", ".ttf"}:
            continue
        if path.stat().st_size > 2_000_000:
            continue
        try:
            yield name, path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue


def test_no_credentials_committed():
    findings = [
        f"{name}: {label}"
        for name, text in repo_files()
        for label, pattern in SECRET_PATTERNS.items()
        if pattern.search(text)
    ]
    assert not findings, findings


def test_client_code_never_references_email_or_service_secrets():
    offenders = [
        name
        for name, text in repo_files()
        if (name.startswith("mobile_app/") or name.startswith("streamlit_app/")) and CLIENT_FORBIDDEN.search(text)
    ]
    assert not offenders, offenders


def test_env_files_are_ignored():
    for name in (".env", "mobile_app/.env", "backend/.env"):
        result = subprocess.run(["git", "check-ignore", "-q", name], cwd=ROOT)
        assert result.returncode == 0, f"{name} is not git-ignored"
