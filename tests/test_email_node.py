"""
Runs the Node-based email tests from pytest.

* tests/email/*.test.ts — Edge Function modules (templates, providers,
  webhook verification, worker). Needs Node >= 22.6 (runs TypeScript natively).
* tests/db/email_outbox.mjs — migration on a real local PostgreSQL via
  embedded-postgres. Needs EMAIL_DB_NODE_MODULES pointing at a folder with
  `npm install embedded-postgres@17.5.0-beta.15 pg@8.16.3` (outside the repo).
"""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


def _node_version():
    if not NODE:
        return (0, 0)
    out = subprocess.run([NODE, "--version"], capture_output=True, text=True).stdout
    match = re.match(r"v(\d+)\.(\d+)", out.strip())
    return (int(match.group(1)), int(match.group(2))) if match else (0, 0)


@pytest.mark.skipif(_node_version() < (22, 6), reason="Node >= 22.6 is required to run TypeScript tests")
def test_email_typescript_modules():
    files = sorted(str(p) for p in (ROOT / "tests" / "email").glob("*.test.ts"))
    result = subprocess.run([NODE, "--test", *files], capture_output=True, text=True, cwd=ROOT, timeout=300)

    print(result.stdout[-4000:])
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]


@pytest.mark.skipif(
    not os.environ.get("EMAIL_DB_NODE_MODULES") or not NODE,
    reason="EMAIL_DB_NODE_MODULES not set (embedded PostgreSQL unavailable)",
)
def test_email_outbox_migration_on_real_postgres():
    with tempfile.TemporaryDirectory() as data_dir:
        result = subprocess.run(
            [NODE, str(ROOT / "tests" / "db" / "email_outbox.mjs"), str(Path(data_dir) / "pg")],
            capture_output=True, text=True, cwd=ROOT, timeout=600,
        )

    lines = [line for line in result.stdout.splitlines() if line.startswith(("PASS", "FAIL")) or "passed" in line]
    print("\n".join(lines))
    assert result.returncode == 0, "\n".join(lines) + result.stderr[-2000:]
