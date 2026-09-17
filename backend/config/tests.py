import socket
import tempfile
from copy import deepcopy
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.db.utils import ConnectionHandler
from django.test import SimpleTestCase, TestCase


class StartupTests(SimpleTestCase):
    def test_system_check_needs_no_network(self):
        with patch.object(
            socket.socket, "connect", side_effect=AssertionError("network")
        ):
            call_command("check", stdout=StringIO())

    def test_sqlite_is_default(self):
        self.assertEqual(
            settings.DATABASES["default"]["ENGINE"], "django.db.backends.sqlite3"
        )


class SQLiteConnectionTests(TestCase):
    def test_foreign_keys_are_enabled_in_test_database(self):
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA foreign_keys")
            self.assertEqual(cursor.fetchone()[0], 1)


class FileBackedSQLitePolicyTests(TestCase):
    def test_file_backed_connection_uses_wal_and_foreign_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            config = deepcopy(settings.DATABASES["default"])
            config["NAME"] = Path(directory) / "policy.sqlite3"
            probe = ConnectionHandler({"default": config})["default"]
            try:
                with probe.cursor() as cursor:
                    cursor.execute("PRAGMA journal_mode")
                    self.assertEqual(cursor.fetchone()[0].lower(), "wal")
                    cursor.execute("PRAGMA foreign_keys")
                    self.assertEqual(cursor.fetchone()[0], 1)
                    cursor.execute("PRAGMA busy_timeout")
                    self.assertGreaterEqual(cursor.fetchone()[0], 5000)
            finally:
                probe.close()
