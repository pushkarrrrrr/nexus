import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def test_alembic_migrations_lifecycle():
    with TemporaryDirectory() as tmpdir:
        temp_db = Path(tmpdir) / "test_migration.db"
        env = os.environ.copy()
        env["PYTHONPATH"] = "."
        env["DATABASE_URL"] = f"sqlite+aiosqlite:///{temp_db}"

        alembic_cmd = [sys.executable, "-m", "alembic", "-c", "infra/database/alembic.ini"]

        # 1. Upgrade to head
        up_result = subprocess.run(
            alembic_cmd + ["upgrade", "head"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert up_result.returncode == 0, f"Alembic upgrade failed: {up_result.stderr}"
        assert temp_db.exists(), "Database file should exist after migration"

        # 2. Downgrade to base
        down_result = subprocess.run(
            alembic_cmd + ["downgrade", "base"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert down_result.returncode == 0, f"Alembic downgrade failed: {down_result.stderr}"

        # 3. Re-upgrade to head
        re_up_result = subprocess.run(
            alembic_cmd + ["upgrade", "head"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert re_up_result.returncode == 0, f"Alembic re-upgrade failed: {re_up_result.stderr}"
