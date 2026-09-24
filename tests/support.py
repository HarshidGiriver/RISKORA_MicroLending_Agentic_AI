"""Fresh SQLite database per test, never the configured application database."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from backend import database


class IsolatedDatabaseMixin:
    def setUp(self):
        temporary = TemporaryDirectory(prefix="riskora-test-")
        self.addCleanup(temporary.cleanup)
        self.test_db_path = Path(temporary.name) / "test.db"
        override = patch.object(database, "DB_PATH", str(self.test_db_path))
        override.start()
        self.addCleanup(override.stop)
        database.init_db()
        database.seed_default_cases()
        super().setUp()
