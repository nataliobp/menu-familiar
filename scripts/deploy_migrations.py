"""Run inside the verified image against the live schema or its disposable copy."""

import json
import os
from pathlib import Path
import sys

import django
from django.conf import settings
from django.core.management import call_command
from django.db import connection, migrations, models
from django.db.migrations.executor import MigrationExecutor

SAFE_FIELDS = {models.BooleanField, models.CharField, models.DateField, models.DateTimeField,
               models.IntegerField, models.TextField}


def supported(migration):
    # Existing rows receive NULL. No data code, constraints, table removals,
    # backfills or index creation are admitted by the unattended path.
    return migration.atomic and not migration.replaces and all(
        type(op) is migrations.AddField
        and type(op.field) in SAFE_FIELDS
        and op.field.null and not op.field.primary_key and not op.field.unique
        and not op.field.db_index and not op.field.has_default()
        and not op.field.has_db_default() and op.preserve_default
        for op in migration.operations
    )


def plan():
    executor = MigrationExecutor(connection)
    loader = executor.loader
    loader.check_consistent_history(connection)
    if (not loader.applied_migrations or loader.detect_conflicts()
            or loader.applied_migrations.keys() - loader.disk_migrations.keys()):
        raise SystemExit("Unrecognized or inconsistent migration history")
    entries = executor.migration_plan(loader.graph.leaf_nodes())
    return [[migration.app_label, migration.name, not backwards and supported(migration)]
            for migration, backwards in entries]


def main():
    mode = sys.argv[1]
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    database = Path(settings.DATABASES["default"]["NAME"])
    # SQLite must open an existing file even for apply mode. An empty bind or
    # missing database must never be turned into a fresh installation here.
    settings.DATABASES["default"]["NAME"] = database.as_uri() + (
        "?mode=ro" if mode == "plan" else "?mode=rw"
    )
    django.setup()
    pending = plan()
    if mode == "plan":
        print(json.dumps(pending))
        return
    if mode != "apply" or pending != json.loads(sys.argv[2]) or not pending or not all(
        approved for _, _, approved in pending
    ):
        raise SystemExit("Migration plan changed or requires manual review")
    call_command("migrate", interactive=False)
    if plan():
        raise SystemExit("Migrations remain pending")
    with connection.cursor() as cursor:
        if cursor.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise SystemExit("SQLite integrity check failed")
        if cursor.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise SystemExit("SQLite foreign key check failed")


if __name__ == "__main__":
    main()
