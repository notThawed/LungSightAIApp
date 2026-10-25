"""
Runs the DB-layer RLS / grant / append-only tests in tests/db/audit_logs_rls.mjs.

Needs Node.js and PGlite outside the repo:
    npm install --prefix <dir> @electric-sql/pglite@0.3.10
    set PGLITE_MODULE=<dir>/node_modules/@electric-sql/pglite/dist/index.js
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parent / "db" / "audit_logs_rls.mjs"


@pytest.mark.skipif(
    not os.environ.get("PGLITE_MODULE") or not shutil.which("node"),
    reason="PGLITE_MODULE not set or node not installed",
)
def test_audit_logs_migration_rls_and_append_only():
    result = subprocess.run(
        ["node", str(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=300,
    )

    print(result.stdout)

    assert result.returncode == 0, result.stdout + result.stderr
