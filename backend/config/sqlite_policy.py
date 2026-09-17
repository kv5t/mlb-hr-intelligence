"""Connection policy for file-backed SQLite databases."""

from django.core.exceptions import ImproperlyConfigured


def configure_sqlite_connection(sender, connection, **kwargs):
    if connection.vendor != "sqlite":
        return

    # Use the raw connection here: connection_created fires while Django is
    # establishing the wrapper, before application queries or transactions.
    cursor = connection.connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    if cursor.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise ImproperlyConfigured("SQLite foreign-key enforcement is required")

    database_path = next(
        (
            path
            for _, name, path in cursor.execute("PRAGMA database_list")
            if name == "main"
        ),
        "",
    )
    if database_path:
        mode = cursor.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        if mode.lower() != "wal":
            raise ImproperlyConfigured("File-backed SQLite must use WAL mode")
