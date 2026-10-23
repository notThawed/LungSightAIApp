"""
Regression tests for repository-level breakage found during the redesign.
"""

import ast
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

SKIP_DIRS = {"node_modules", ".venv", "venv", ".git", "__pycache__", ".expo"}


def project_files(pattern):
    return [
        path for path in ROOT.rglob(pattern)
        if not SKIP_DIRS.intersection(path.relative_to(ROOT).parts)
    ]


@pytest.mark.parametrize("path", project_files("*.py"), ids=lambda p: str(p.relative_to(ROOT)))
def test_python_files_parse(path):
    """Regression: merge 119c8a7 committed conflict markers into app.py,
    login.py, auth_manager.py, backend/auth.py and backend/database.py."""
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".json", ".css", ".md", ".txt", ".toml", ".html", ""}


def tracked_text_files():
    try:
        output = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
        files = [ROOT / line for line in output.splitlines()]
    except (OSError, subprocess.CalledProcessError):
        files = project_files("*")
    return [f for f in files if f.is_file() and f.suffix in TEXT_SUFFIXES]


def test_no_merge_conflict_markers():
    offenders = []

    for path in tracked_text_files():
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if line.startswith(("<<<<<<< ", ">>>>>>> ")):
                offenders.append(f"{path.relative_to(ROOT)}:{number}")

    assert not offenders, offenders


def test_requirements_are_plain_package_names():
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        assert line and not line.startswith(("<", "=", ">")), repr(line)


def test_env_files_are_ignored_and_templates_exist():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert ".env" in gitignore.splitlines()
    assert (ROOT / ".env.example").exists()
    assert (ROOT / "mobile_app/.env.example").exists()


def test_mobile_never_references_service_role_key():
    """The mobile app ships to devices; it must only use the anon key."""
    for path in (ROOT / "mobile_app/src").rglob("*.ts*"):
        source = path.read_text(encoding="utf-8")
        assert "SECRET_KEY" not in source and "service_role" not in source, path


def test_every_role_layout_routes_profile():
    """Regression: Staff had a 'Manage Profile' button that rendered a blank page."""
    for layout in (ROOT / "streamlit_app/layouts").glob("*_layout.py"):
        assert '"Profile"' in layout.read_text(encoding="utf-8"), layout.name


def test_sidebar_pages_are_routed_by_layouts():
    """Every sidebar entry must have a matching branch in its layout."""
    sidebar = (ROOT / "streamlit_app/components/sidebar.py").read_text(encoding="utf-8")
    tree = ast.parse(sidebar)
    navs = {}

    for node in tree.body:
        if isinstance(node, ast.Assign) and node.targets[0].id.endswith("_NAV"):
            pages = []
            for section in ast.literal_eval(node.value):
                pages += [item[0] for item in section["items"]]
            navs[node.targets[0].id] = pages

    layout_for = {
        "RADTECH_NAV": "radtech_layout.py",
        "PHYSICIAN_NAV": "physician_layout.py",
        "ADMIN_NAV": "system_admin_layout.py",
        "STAFF_NAV": "staff_layout.py",
        "HOSPITAL_ADMIN_NAV": "hospital_admin_layout.py",
    }

    for nav, pages in navs.items():
        layout = (ROOT / "streamlit_app/layouts" / layout_for[nav]).read_text(encoding="utf-8")
        for page in pages:
            assert f'page == "{page}"' in layout, f"{page} from {nav} is not routed"
