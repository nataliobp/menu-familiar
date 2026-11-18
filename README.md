# Family menu

This Django project plans family meals. See `SPEC.md`, `ARCHITECTURE.md`, `DOMAIN.md`, `FEATURES.md`, and `ROADMAP.md` for requirements and development guidance.

## V1 implementation baseline

Read the [consolidated specifications](docs/specs/README.md), the [replacement UX](docs/ux/README.md), and the [implementation plan](docs/specs/07-implementation-plan.md). The current checkout contains the partial M0 importer. The contracts describe the target, including the forward migration and isolated database configuration still to be implemented. Automated quality gates permit progress through M0–M8. Manual owner QA and network isolation verification are release gates.

## Current M0 verification

Create a local virtual environment, install the existing requirements, and run the checks:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py check
.venv/bin/python manage.py test
```

The normal tests use synthetic data and an isolated test database. To additionally verify every record in the private, Git-ignored source file against a fresh test database, run:

```sh
MENU_CATALOGUE_CSV="$PWD/PLATOS_57.csv" .venv/bin/python manage.py test menus.tests.test_catalogue_import.SourceFidelityTests
```

Without that environment variable, the full-source test is skipped; its acceptance is not established by the synthetic tests alone. Do not commit the private CSV or include its contents in fixtures, logs, or issue reports.

## Initial catalogue import

After applying migrations to the intended database, run `.venv/bin/python manage.py import_catalogue /path/to/PLATOS_57.csv`. The source must have the expected CSV columns and pending recipe status. The import preserves primary and secondary categories and ignores image status. It does not correct language or infer recipe information. Identical dishes are unchanged, missing dishes are inserted, unrelated dishes remain untouched, and a conflict aborts the whole import without overwriting existing dishes or recipes. Invalid input and database failures also abort the transaction. Inspect conflicts before taking any further action; do not edit family data merely to make an import succeed.

The default database is `db.sqlite3` in the project directory. Local settings are for development; the default secret and debug configuration are not suitable for deployment.

## Current M0 manual QA preparation

Manual QA has not yet been approved or recorded. Run it in a disposable copy, never against the family database. From the project directory, create a temporary project with only the files required for this check:

```sh
PROJECT_DIR="$PWD"
QA_DIR="$(mktemp -d)"
cp -R config menus manage.py "$QA_DIR/"
cp PLATOS_57.csv "$QA_DIR/catalogue.csv"
cd "$QA_DIR"
"$PROJECT_DIR/.venv/bin/python" manage.py migrate
"$PROJECT_DIR/.venv/bin/python" manage.py import_catalogue catalogue.csv
"$PROJECT_DIR/.venv/bin/python" manage.py import_catalogue catalogue.csv
```

Confirm the first import reports 57 new dishes and the second reports zero new dishes. Inspect the disposable database, comparing representative names, IDs, primary and secondary categories, meal preferences, and occasion flags with the private CSV. Confirm the five flagged IDs are 25, 31, 43, 52, and 55 and no recipe quantities or image data were invented. Exercise a partial import with an unrelated record, then an edited conflicting record; verify missing entries are inserted only in the first case and all prior data remains unchanged on conflict. Try malformed input and confirm no data changes. Automated tests cover a simulated failure after writes begin and verify rollback. Record pass/fail and any discrepancies without copying private data into shared reports. Return to the project directory after QA; retain or remove the temporary copy according to local data-handling practice.
