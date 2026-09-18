import os
import subprocess


def test_alembic_migrations_lifecycle():
    env = os.environ.copy()
    env["PYTHONPATH"] = "."

    # 1. Upgrade to head
    up_result = subprocess.run(
        [".venv/bin/alembic", "-c", "infra/database/alembic.ini", "upgrade", "head"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert up_result.returncode == 0, f"Alembic upgrade failed: {up_result.stderr}"
    assert os.path.exists(".nexus/nexus.db"), "Database file should exist after migration"

    # 2. Downgrade to base
    down_result = subprocess.run(
        [".venv/bin/alembic", "-c", "infra/database/alembic.ini", "downgrade", "base"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert down_result.returncode == 0, f"Alembic downgrade failed: {down_result.stderr}"

    # 3. Re-upgrade to head
    re_up_result = subprocess.run(
        [".venv/bin/alembic", "-c", "infra/database/alembic.ini", "upgrade", "head"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert re_up_result.returncode == 0, f"Alembic re-upgrade failed: {re_up_result.stderr}"
