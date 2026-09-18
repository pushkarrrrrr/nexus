import os
import subprocess


def test_alembic_migrations():
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    # Test upgrade head
    result = subprocess.run(
        [".venv/bin/alembic", "-c", "infra/database/alembic.ini", "upgrade", "head"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, f"Alembic upgrade failed: {result.stderr}"

    # Verify tables exist via sqlite check
    db_file = ".nexus/nexus.db"
    assert os.path.exists(db_file), "Database file should exist after migration"
