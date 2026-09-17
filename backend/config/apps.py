from django.apps import AppConfig
from django.db.backends.signals import connection_created

from .sqlite_policy import configure_sqlite_connection


class ConfigApp(AppConfig):
    name = "config"

    def ready(self):
        connection_created.connect(
            configure_sqlite_connection,
            dispatch_uid="config.sqlite_connection_policy",
        )
