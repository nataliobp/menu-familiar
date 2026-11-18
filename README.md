# Family menu

Django application for household meal planning. The authoritative contracts are [SPEC.md](SPEC.md), [ARCHITECTURE.md](ARCHITECTURE.md), [docs/specs](docs/specs/README.md) and [docs/ux](docs/ux/README.md). V1 implementation and acceptance work is in progress; do not deploy it before independent review and consolidated owner QA.

## Disposable development setup

Use a supported Python version (target 3.12), an isolated virtual environment and a fresh absolute database path. Django does not automatically load `.env`.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export DJANGO_ENV=development DJANGO_DEBUG=1
export DJANGO_DB_PATH=/tmp/menu-familiar-dev.sqlite3
.venv/bin/python manage.py migrate
.venv/bin/python manage.py check
.venv/bin/python manage.py test
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Open `/menu/`. This is a development server, not production serving. Tests use isolated databases and synthetic fixtures. Optional local private-source fidelity verification uses an isolated test database:

```sh
MENU_CATALOGUE_CSV=/absolute/path/to/private.csv .venv/bin/python manage.py test menus.tests.test_catalogue_import.SourceFidelityTests
```

The concurrent SQLite tests require a new file-backed test database under the system temporary directory. To run the full suite with them:

```sh
TEST_DIR="$(mktemp -d)"
DJANGO_ENV=development DJANGO_DB_PATH="$TEST_DIR/unused.sqlite3" DJANGO_TEST_DB_PATH="$TEST_DIR/test.sqlite3" .venv/bin/python manage.py test --noinput
```

The test runner removes its test database. Without `DJANGO_TEST_DB_PATH`, these concurrency tests are skipped. Without the private-source variable the private-source test is skipped. Do not commit private data or copy its contents into logs. To import, first verify the target database path, run migrations, then run `python manage.py import_catalogue /absolute/path/to/private.csv`. The importer validates the entire source before a single atomic write and rejects conflicting IDs.

## Production configuration and release gates

The provided Compose and Docker files are preliminary and have not yet passed image verification. Set an independent `DJANGO_SECRET_KEY`, comma-separated `DJANGO_ALLOWED_HOSTS`, an absolute private data directory in `MENU_DATA_DIR`, and an explicit trusted interface and port in `MENU_BIND_ADDRESS` and `MENU_PORT`; `.env.example` contains placeholders. Production requires an absolute `DJANGO_DB_PATH` and debug defaults off. The data directory must be writable by container UID 10001. Run migrations as a one-off before starting the app. `/healthz` reports database reachability without exposing data.

Use an allowlisted build context staged outside the source directory, containing only `Dockerfile`, `requirements.txt`, `manage.py`, `config/`, and the required Python, template and static files under `menus/`. Verify its contents before building; exclude private databases, CSV files, secrets, backups and logs. Do not bind to a public interface. Actual IPv4 and IPv6 isolation, guest-network denial, router forwards and any tunnels must be checked by the owner before release. No production deployment or unrelated service changes are authorized by this document.

## Isolated Docker verification

From the repository root, run:

```sh
sh scripts/verify-docker.sh
```

Run this as your regular user from a terminal. The script requests sudo for Docker and Compose and writes the log as your regular user. The script verifies the current commit. It builds from an allowlisted temporary context, checks Docker exclusions with synthetic markers, validates the Compose configuration, and runs migrations and Gunicorn smoke checks using a disposable volume. It publishes no host ports and removes its test resources at the end. The latest completed run is saved to the ignored `logs/docker-verification.log`, including failures and the commit tested. This run does not verify network isolation on the household LAN.

## SQLite backup rehearsal

Use explicit private paths and SQLite's online backup API; never copy an active database file alone or overwrite the live database during a rehearsal. The destination must not already exist. For example, with paths selected outside the repository:

```sh
export MENU_BACKUP_SOURCE=/absolute/path/to/source.sqlite3
export MENU_BACKUP_TARGET=/absolute/path/to/new-backup.sqlite3
umask 077
.venv/bin/python - <<'PYBACKUP'
import os
from pathlib import Path
import sqlite3

source = Path(os.environ["MENU_BACKUP_SOURCE"])
target = Path(os.environ["MENU_BACKUP_TARGET"])
if not source.is_absolute() or not target.is_absolute():
    raise SystemExit("Both paths must be absolute")
source = source.resolve(strict=True)
fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
os.close(fd)
with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as source_db:
    with sqlite3.connect(target) as target_db:
        source_db.backup(target_db)
        if target_db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise SystemExit("Backup integrity check failed")
PYBACKUP
```

Restore to a separate location, verify compatible migrations and representative synthetic records, then seek owner authorization before any production switch. Rolling back code after an incompatible migration may also require a matching backup.

## Consolidated manual owner QA (pending)

Use a disposable database and synthetic dishes first. Do not run destructive or conflict checks against household data. Record pass/fail without storing private screenshots or records in Git.

- Import: verify the 13 categories, synthetic upgrade and import, identical rerun, conflicting data and no partial writes. Verify private source fidelity separately and locally.
- Template: set, change and clear a category; reload and inspect all 14 positions at mobile and tablet sizes.
- Planning: create current and future weeks; choose, replace, remove, skip and reactivate dishes; filter/search and inspect ordering; navigate weeks and verify past weeks are read-only and copied suggestions remain unchanged.
- Advanced planning: move and exchange, cancel or confirm a skipped target, undo, and verify stale tabs and later edits cannot overwrite newer data.
- Catalogue and recipes: create, edit, archive and restore a synthetic dish; save an incomplete draft, validate bad amounts, publish and edit a later draft; compare editable weeks with frozen history.
- Shopping: check aggregation, compatible conversions, repeated dishes, distinct units, `al gust`, incomplete coverage, manual products, adjustments, checks, orphan recovery and reset after menu and recipe changes.
- Readiness: inspect 360–430px mobile and 800×480 / 1024×600 tablet flows, keyboard and focus; verify restart and isolated backup/restore; confirm trusted LAN access and denial from untrusted networks over IPv4 and IPv6.

Manual owner QA has not been performed. Network isolation and release authorization are separate pending gates.
