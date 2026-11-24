# Menú Familiar

Django application for household meal planning. The authoritative contracts are [ARCHITECTURE.md](ARCHITECTURE.md), [docs/specs](docs/specs/README.md) and [docs/ux](docs/ux/README.md). The [V2.5 contract](docs/specs/V2.5-SHOPPING-REMINDER.md) describes the read-only `Llista de la compra` tab. Record consolidated owner QA and verify household network isolation before releasing the service.

For an existing V1 installation, follow the [V2.0.0 production upgrade runbook](docs/V2.0.0-RELEASE.md) for the guarded data merge, rehearsal and rollback.

For V2.0.1, follow the [PWA and Tailscale deployment runbook](docs/V2.0.1-RELEASE.md) to retain LAN access and add a separate tailnet-only HTTPS endpoint.

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

## Permanent deployment

Run these commands as your regular user on the Home Server. The maintenance scripts invoke `sudo` for Docker, use the repository's private `.env`, and target only the `menu-familiar` Compose project. Production uses TCP **18766** on the server's stable trusted LAN IPv4 address and keeps SQLite in **/var/lib/menu-familiar/data**. Use the host's local system disk. The container runs as UID/GID 10001 and requires the data directory to exist.

### First installation

1. Check out and verify the release locally. Inspect the interface addresses, the fixed port and Docker's boot configuration.

   ```bash
   git switch --detach v1.0.0
   sh scripts/verify-docker.sh --keep-image
   ip -4 -br address show up
   sudo ss -lnt 'sport = :18766'
   sudo docker ps --format 'table {{.Names}}	{{.Ports}}'
   systemctl is-enabled docker.service
   ```

   Port 18766 must be free. Choose the stable IPv4 address on the trusted household interface. Check that it comes up on boot. Record the verified image tag and image ID from the verification output.

2. Create the private configuration and dedicated storage. Run this once from the release checkout in Bash. The configuration command refuses to replace an existing `.env`.

   ```bash
   (
       set -euo pipefail
       umask 077
       set -o noclobber
       read -r -p 'Stable trusted LAN IPv4 address: ' menu_lan_ip
       menu_secret="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
       menu_commit="$(git rev-parse HEAD)"
       cat > .env <<EOF
   DJANGO_SECRET_KEY=$menu_secret
   DJANGO_ALLOWED_HOSTS=$menu_lan_ip
   MENU_BIND_ADDRESS=$menu_lan_ip
   MENU_PORT=18766
   MENU_DATA_DIR=/var/lib/menu-familiar/data
   MENU_IMAGE=menu-familiar:verified-$menu_commit
   EOF
   )
   sudo install -d -m 0755 /var/lib/menu-familiar
   sudo install -d -m 0700 -o 10001 -g 10001 /var/lib/menu-familiar/data
   ./scripts/compose.sh config --quiet
   ```

3. Initialize the new production database. Keep the existing QA project, environment and database in place until the owner decides whether to migrate or discard them. For an owner-approved migration, use the backup procedure below to snapshot the QA database into a new production directory, then apply the release migrations to that copy.

   ```bash
   ./scripts/compose.sh run --rm --no-deps --pull never menu-familiar python manage.py migrate --noinput
   ```

   For a fresh database, the owner can optionally seed the private catalogue from the checkout before starting the service.

   ```bash
   ./scripts/compose.sh run --rm --no-deps --pull never -T menu-familiar \
       sh -ec 'umask 077; cat > /tmp/catalogue.csv; python manage.py import_catalogue /tmp/catalogue.csv' < PLATOS_57.csv
   ```

4. Complete the owner QA checklist with the disposable QA instance. Before opening production to household use, confirm that the router, any inter-network firewall, and any VPN or tunnel restrict this endpoint to the trusted household LAN. A specific IPv4 bind limits the published destination, while routers and VPNs can still route clients to it. Keep the port out of router forwards, public proxies and tunnels. Verify the installed endpoint from trusted devices and test denial from guest Wi-Fi, a VPN client and outside the LAN over IPv4 and IPv6. If isolation fails, stop the service and correct the scoped access rules before resuming.

   ```bash
   ./start.sh
   ./status.sh
   menu_lan_ip="$(sed -n 's/^MENU_BIND_ADDRESS=//p' .env)"
   curl --noproxy '*' -fsS --retry 10 --retry-connrefused --retry-delay 1 --max-time 5 "http://$menu_lan_ip:18766/healthz"
   ```

   Expect `OK` and open `/menu/` from a trusted device. Compose uses `restart: unless-stopped`, so a running service returns when Docker starts after a reboot. `./stop.sh` leaves it stopped until `./start.sh` is run. Verify automatic restart and data persistence at the next scheduled reboot.

## Isolated Docker verification

From the repository root, run:

```sh
sh scripts/verify-docker.sh
```

Run this as your regular user from a terminal. The script requests sudo for Docker and Compose and writes the log as your regular user. The script verifies the current commit. It builds from an allowlisted temporary context, checks Docker exclusions with synthetic markers, validates the Compose configuration, and runs migrations and Gunicorn smoke checks using a disposable volume. It publishes no host ports and removes its test resources at the end. The latest completed run is saved to the ignored `logs/docker-verification.log`, including failures and the commit tested. This run does not verify network isolation on the household LAN.

## Browser regression checks

Install Playwright and Chromium in a QA environment using `python -m pip install playwright` and `python -m playwright install chromium`. Then run `python scripts/verify-browser.py` from the checkout. It starts a disposable loopback server, creates a fresh synthetic SQLite database, and runs the browser with JavaScript disabled. Playwright is a QA tool and is excluded from the runtime image.

## Private recipe and photo operations

See the [V2.3 and V2.4 operations guide](docs/specs/V2.3-V2.4.md) for the guarded proposal import, local photos, and paired database and media backups. The SQLite-only procedure below also applies to pre-upgrade V1 and V2.2 data.

## Backup

Use SQLite's online backup API for a consistent snapshot, including when the app is running. For an update, stop the service before taking the snapshot so it also captures the final pre-migration state. Store backups and a protected copy of `.env` outside Git and keep a copy on separate private storage. Record the release tag and verified image ID alongside each backup. Use the configured data directory if it differs from the default below.

```sh
sudo install -d -m 0700 /var/lib/menu-familiar/backups
menu_backup="/var/lib/menu-familiar/backups/menu-$(date -u +%Y%m%dT%H%M%SZ).sqlite3"
sudo python3 - /var/lib/menu-familiar/data/menu.sqlite3 "$menu_backup" <<'PYBACKUP'
import os
from pathlib import Path
import sqlite3
import sys

source, target = map(Path, sys.argv[1:])
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

## Updates

For routine updates to the existing Home Server installation, run `./deploy.sh` from a clean, committed branch. See the [local deployment runbook](docs/DEPLOYMENT.md) for owner setup, verification, backup and recovery. The manual procedure below covers changes that need explicit intervention.

Fetch the approved release tag and verify it while the old container is still running.

```bash
read -r -p 'Approved release tag: ' menu_release
git fetch origin tag "$menu_release"
git switch --detach "$menu_release"
sh scripts/verify-docker.sh --keep-image
```

Run `./stop.sh`, take a backup using the commands above, and preserve the current `.env` in the backup directory.

```bash
sudo install -m 0600 .env "$menu_backup.env"
vim .env
```

Set `MENU_IMAGE` to the new verified tag printed by the script. Keep the same address, port, secret and data directory. Run the migration and start only if it succeeds.

```bash
./scripts/compose.sh config --quiet &&
./scripts/compose.sh run --rm --no-deps --pull never menu-familiar python manage.py migrate --noinput &&
./start.sh &&
./status.sh
```

Repeat the health and trusted-device checks. If the migration or smoke check fails, use the recovery procedure with the matching pre-update backup and image.

### Pizza catalogue update

For an existing installation, take a [paired database and photo backup](docs/V2.0.0-RELEASE.md#start-stop-status-and-routine-backup), retain the previous image and configuration, and follow the update procedure above. Stop Menú Familiar before running the candidate migration. Migration 0012 adds the Pizza category row. The previous app expects the previous vocabulary, so start the candidate image after the migration succeeds. For rollback, use the matching pre-change backup and image.

After startup, find the seeded Pizza dish by its stable source ID and open its editor.

```bash
./scripts/compose.sh exec -T menu-familiar python manage.py shell -c \
  'from menus.models import CatalogueSourceRecord; print(CatalogueSourceRecord.objects.get(pk=39).dish_id)'
```

Open `/plats/<dish_id>/edit/`, select **Pizza** as the primary category, clear every secondary category, and save. Review any household-added pizza dishes in both the active and archived catalogue and apply the same edit. The editor preserves dish IDs, names, recipes, photo references and menu assignments. Editable snapshots refresh and past snapshots remain frozen. Check the Pizza and Pasta filters before completing the update.

For a fresh install, use the corrected private CSV at `data/PLATOS_57-pizza.csv` if it is available on the installation host. Keep it outside Git. The original CSV and approved recipe bundle still describe the pre-change category. After importing the corrected seed, use the recipe importer's standard dry run and apply commands without the legacy catalogue option, since the fresh seed already provides stable source links. The CSV importer is insert-only and rejects category changes to existing dishes.

## Recovery

Rehearse with a synthetic backup before relying on the procedure. For a production restore or rollback, stop the production service and use a new directory. Preserve the previous data directory and its SQLite sidecar files. The backup file must be the verified standalone snapshot.

```bash
./stop.sh
read -r -p 'Absolute path to the verified SQLite backup: ' menu_backup
menu_restore_dir="$(sudo mktemp -d /var/lib/menu-familiar/restore.XXXXXXXX)"
sudo install -m 0600 -o 10001 -g 10001 "$menu_backup" "$menu_restore_dir/menu.sqlite3"
sudo chown 10001:10001 "$menu_restore_dir"
sudo python3 -c 'import pathlib, sqlite3, sys; db = sqlite3.connect(pathlib.Path(sys.argv[1]).as_uri() + "?mode=ro", uri=True); sys.exit(0 if db.execute("PRAGMA integrity_check").fetchall() == [("ok",)] else "Backup integrity check failed")' "$menu_restore_dir/menu.sqlite3"
printf 'Restore MENU_DATA_DIR=%s\n' "$menu_restore_dir"
```

Proceed after the integrity check succeeds. Use `vim .env` to restore the matching configuration and set `MENU_DATA_DIR` to the printed directory. Set `MENU_IMAGE` to the verified image that matches the snapshot. If the image is missing, check out the matching release and run `sh scripts/verify-docker.sh --keep-image` to rebuild and verify it.

```bash
./scripts/compose.sh run --rm --no-deps --pull never menu-familiar python manage.py migrate --check &&
./start.sh &&
./status.sh
```

Repeat the health check, then inspect representative weeks, dishes and shopping lists from a trusted device.

## Consolidated manual owner QA (pending)

Use a disposable database and synthetic dishes first. Do not run destructive or conflict checks against household data. Record pass/fail without storing private screenshots or records in Git.

- Import: verify the 13 categories, synthetic upgrade and import, identical rerun, conflicting data and no partial writes. Verify private source fidelity separately and locally.
- Template: set, change and clear a category; reload and inspect all 14 positions at mobile and tablet sizes.
- Planning: open and browse a missing future week, then create it by choosing or skipping a meal. Check immediate filtering, replacement, removal and reactivation, live suggestions in empty editable slots, and read-only past weeks.
- Advanced planning: move and exchange, cancel or confirm a skipped target, undo, and verify stale tabs and later edits cannot overwrite newer data.
- Catalogue and recipes: create, edit, archive and restore a synthetic dish; save an incomplete draft, validate bad amounts, publish and edit a later draft; compare editable weeks with frozen history.
- Ingredient reminder: check grouping, exact totals, repeated dishes, distinct units, `Al gust`, incomplete coverage, week switching and refresh after menu or recipe changes. See the [V2.5 owner QA handoff](docs/V2.5-OWNER-QA.md).
- Readiness: inspect 360–430px mobile and 800×480 / 1024×600 tablet flows, keyboard and focus; verify restart and isolated backup/restore; confirm trusted LAN access and denial from untrusted networks over IPv4 and IPv6.

Record the owner’s results and the actual network isolation checks before making the service available for household use.
