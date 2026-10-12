"""Startup failures must be clear and return failure to the launching shell."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from backend import server


class StartupErrorTests(unittest.TestCase):
    def test_invalid_environment_port_is_reported_without_traceback(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / 'unused.db'
            result = subprocess.run(
                [sys.executable, 'run.py', '--check'], cwd=server.PROJECT_ROOT,
                env={**os.environ, 'RISKORA_PORT': 'invalid', 'RISKORA_DB_PATH': str(database)},
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn('invalid configuration', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertFalse(database.exists())

    def test_exhausted_ports_raise_and_stay_within_valid_range(self):
        with patch.object(server.RiskInferenceEngine, 'get_instance'), \
             patch.object(server, 'init_db'), patch.object(server, 'seed_default_cases'), \
             patch.object(server, 'make_app') as make_app:
            make_app.return_value.listen.side_effect = OSError(98, 'Address in use')
            with self.assertRaisesRegex(RuntimeError, 'between 65535 and 65535'):
                server.run_server(65535)
            make_app.return_value.listen.assert_called_once_with(65535, address=server.HOST)


if __name__ == '__main__':
    unittest.main()
