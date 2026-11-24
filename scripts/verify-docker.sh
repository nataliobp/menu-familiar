#!/bin/sh
# Verify the committed application in disposable Docker resources.
set -eu
umask 077
result=''
requested_ref=''
case "${1:-}" in
    "") keep_image=false ;;
    --keep-image) [ "$#" -eq 1 ]; keep_image=true ;;
    --deployment-result)
        [ "$#" -eq 3 ]
        keep_image=false
        result=$2
        requested_ref=$3
        ;;
    *) printf 'Usage: %s [--keep-image]\n' "$0" >&2; exit 2 ;;
esac

if [ -n "${result:-}" ]; then
    repo=$(git rev-parse --show-toplevel)
else
    repo=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
fi
cd "$repo"
log_dir="$repo/logs"
[ -z "${result:-}" ] || log_dir=$(dirname -- "$result")
mkdir -p "$log_dir"
log="$log_dir/docker-verification.log"
log_tmp=$(mktemp "$log_dir/.docker-verification.XXXXXX")
printf 'Docker verification output: %s\n' "$log"
exec 3>&1 4>&2 >"$log_tmp" 2>&1

work=''
tag=''
audit_tag=''
app=''
audit_container=''
volume=''
docker_cmd() {
    if [ -n "${result:-}" ]; then
        sudo -n /usr/bin/docker --host unix:///var/run/docker.sock "$@"
    elif [ "${MENU_DOCKER_DIRECT:-0}" = 1 ]; then
        docker "$@"
    else
        sudo docker "$@"
    fi
}

finish() {
    code=$?
    trap - 0 HUP INT TERM
    cleanup_failed=0
    [ -z "$app" ] || docker_cmd container rm -f "$app" || cleanup_failed=1
    [ -z "$audit_container" ] || docker_cmd container rm "$audit_container" || cleanup_failed=1
    [ -z "$volume" ] || docker_cmd volume rm "$volume" || cleanup_failed=1
    [ -z "$audit_tag" ] || docker_cmd image rm "$audit_tag" || cleanup_failed=1
    [ -z "$tag" ] || docker_cmd image rm "$tag" || cleanup_failed=1
    [ -z "$work" ] || rm -rf -- "$work" || cleanup_failed=1
    if [ "$cleanup_failed" -ne 0 ]; then
        printf 'Cleanup failed for one or more disposable resources.\n'
        [ "$code" -ne 0 ] || code=1
    fi
    if [ "$code" -eq 0 ]; then
        printf 'PASS: isolated Docker verification. Household LAN verification is separate.\n'
    else
        printf 'FAIL: Docker verification exited with status %s.\n' "$code"
    fi
    mv -f -- "$log_tmp" "$log"
    exit "$code"
}
trap finish 0
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

ref=$(git rev-parse --verify HEAD)
[ "$ref" = "${requested_ref:-$ref}" ]
printf 'Commit: %s\n' "$ref"
printf '\n== Docker access ==\n'
if [ -z "${result:-}" ] && [ "${MENU_DOCKER_DIRECT:-0}" != 1 ] && ! sudo -v >&3 2>&4; then
    printf 'Could not authenticate with sudo. Run this script from your terminal as an authorized user.\n'
    exit 1
fi
exec 3>&- 4>&-
docker_cmd info --format 'Docker server {{.ServerVersion}}'
docker_cmd compose version

work=$(mktemp -d "${TMPDIR:-/tmp}/menu-docker-verify.XXXXXXXX")
run_id="menu-qa-$(basename "$work" | tr '[:upper:]' '[:lower:]' | sed 's/^menu-docker-verify\.//')"
context="$work/context"
mkdir "$context" "$work/data"

printf '\n== Build context and Compose configuration ==\n'
git ls-tree -r "$ref" -- .dockerignore Dockerfile requirements.txt manage.py config menus >"$work/git-tree"
(
    # Keep the temporary parent private while preserving source access for the
    # non-root image user. Docker COPY preserves the file and directory modes.
    umask 022
    while read -r mode type oid path; do
        case "$path" in
            menus/tests/*|*/__pycache__/*) continue ;;
            .dockerignore|Dockerfile|requirements.txt|manage.py|config/*.py|menus/*.py|menus/templates/*|menus/static/*) ;;
            *) continue ;;
        esac
        case "$mode:$type" in
            100644:blob|100755:blob) ;;
            *) printf 'Unexpected Git entry: %s\n' "$path"; exit 1 ;;
        esac
        mkdir -p "$(dirname -- "$context/$path")"
        git cat-file blob "$oid" >"$context/$path"
        if [ "$mode" = 100755 ]; then chmod 755 "$context/$path"; fi
    done <"$work/git-tree"
)
git show "$ref:compose.yaml" >"$work/compose.yaml"
cat >"$work/compose.env" <<EOF
DJANGO_SECRET_KEY=qa-compose-placeholder-only
DJANGO_ALLOWED_HOSTS=127.0.0.1
MENU_DATA_DIR="$work/data"
MENU_BIND_ADDRESS=127.0.0.1
MENU_PORT=18765
MENU_IMAGE=$run_id:app
EOF
docker_cmd compose --env-file "$work/compose.env" --project-directory "$work" \
    -f "$work/compose.yaml" -p "$run_id" config --format json > "$work/compose.json"
printf 'Compose configuration validated without loading project .env or starting services.\n'

printf '\n== Build application image ==\n'
docker_cmd build --label "org.opencontainers.image.revision=$ref" --tag "$run_id:app" "$context"
tag="$run_id:app"
docker_cmd run --rm -i --network none --entrypoint python "$tag" -c '
import json
import sys

ports = json.load(sys.stdin)["services"]["menu-familiar"]["ports"]
actual = {(port["host_ip"], str(port["published"]), port["target"], port["protocol"]) for port in ports}
expected = {("127.0.0.1", "18765", 8000, "tcp"), ("127.0.0.1", "18768", 8001, "tcp")}
assert actual == expected and len(ports) == len(expected), "Unexpected Compose port bindings"
' < "$work/compose.json"
printf 'Existing LAN listener and dedicated loopback backend mappings verified.\n'

printf '\n== Verify Docker build-context exclusions ==\n'
# The real build above uses only Git blobs. This separate build checks that
# Docker also filters representative excluded files. The markers are synthetic.
markers='.env .git/config PLATOS_57.csv db.sqlite3 db.sqlite3-wal backups/example.sqlite3
logs/example.log private-ux/demo.html docs/ux/index.html .venv/example
config/__pycache__/example.pyc config/.env menus/tests/qa_marker.py menus/qa_marker.sqlite3
menus/static/menus/qa_marker.csv menus/templates/menus/qa_marker.key
menus/templates/menus/TECHNICAL-REVIEW.md'
for path in $markers
do
    mkdir -p "$(dirname -- "$context/$path")"
    printf 'synthetic Docker verification marker\n' >"$context/$path"
done
docker_cmd build --tag "$run_id:context" --file - "$context" <<'DOCKERFILE'
FROM scratch
COPY . /
CMD ["/unused"]
DOCKERFILE
audit_tag="$run_id:context"
audit_container=$(docker_cmd create --network none "$audit_tag")
docker_cmd export "$audit_container" >"$work/context.tar"
tar -tf "$work/context.tar" >"$work/context.paths"
for path in $markers
do
    if grep -Fx -e "$path" -e "./$path" "$work/context.paths" >/dev/null; then
        printf 'Docker included an excluded marker: %s\n' "$path"
        exit 1
    fi
done
grep -Fx -e manage.py -e ./manage.py "$work/context.paths" >/dev/null
printf 'Docker excluded every synthetic marker.\n'

printf '\n== Inspect final application image ==\n'
docker_cmd run --rm -i --network none --entrypoint python "$tag" - <<'PY'
from pathlib import Path
import os

root = Path("/app")
root_entries = {"requirements.txt", "manage.py", "config", "menus", "staticfiles"}
assert {p.name for p in root.iterdir()} == root_entries, "Unexpected files at image app root"
for path in root.rglob("*"):
    relative = path.relative_to(root)
    assert not path.is_symlink(), f"Unexpected symlink: {relative}"
    mode = os.R_OK | os.X_OK if path.is_dir() else os.R_OK
    assert os.access(path, mode), f"Application user cannot access: {relative}"
    if relative.parts[0] == "staticfiles":
        continue
    assert path.name not in {".env", ".git", ".venv", "tests", "PLATOS_57.csv"}, relative
    assert ".sqlite3" not in path.name and not path.name.endswith(".log"), relative
assert os.getuid() == 10001, "Application must run as its unprivileged user"
assert (root / "staticfiles/menus/app.css").is_file(), "Collected CSS missing"
print("Application files, unprivileged UID and collected CSS verified.")
PY

printf '\n== Initialize a disposable SQLite volume ==\n'
volume=$(docker_cmd volume create "$run_id-data")
docker_cmd run --rm --network none --user 0 --mount "type=volume,src=$volume,dst=/data" \
    --entrypoint chown "$tag" 10001:10001 /data
DJANGO_SECRET_KEY='qa-only-docker-verification-key-not-used-by-any-service-374962'
DJANGO_ALLOWED_HOSTS=127.0.0.1
DJANGO_DB_PATH=/data/verify.sqlite3

with_database() {
    docker_cmd run --rm -i --network none --mount "type=volume,src=$volume,dst=/data" \
        -e "DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY" -e "DJANGO_ALLOWED_HOSTS=$DJANGO_ALLOWED_HOSTS" \
        -e "DJANGO_DB_PATH=$DJANGO_DB_PATH" "$@"
}

with_database "$tag" python manage.py migrate --noinput
with_database "$tag" python manage.py check
with_database "$tag" python manage.py migrate --check
with_database "$tag" python manage.py shell -c \
    'from menus.models import DishRecord; DishRecord.objects.create(name="Plat sintètic Docker", primary_category_id="cereals", meal_preference="both", special_occasion=False)'

printf '\n== Verify a matching SQLite backup and restore ==\n'
with_database "$tag" python - <<'PYBACKUP'
import os
import sqlite3

with sqlite3.connect(os.environ["DJANGO_DB_PATH"]) as source, sqlite3.connect("/data/restored.sqlite3") as restored:
    source.backup(restored)
    assert restored.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert list(restored.iterdump()) == list(source.iterdump())
print("Synthetic backup restored with identical schema and data.")
PYBACKUP

DJANGO_DB_PATH=/data/restored.sqlite3
with_database "$tag" python manage.py migrate --check

printf '\n== Test Gunicorn against the restored database from inside the container ==\n'
app=$(docker_cmd run --detach --name "$run_id-app" --network none \
    --mount "type=volume,src=$volume,dst=/data" \
    -e "DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY" -e "DJANGO_ALLOWED_HOSTS=$DJANGO_ALLOWED_HOSTS" \
        -e "DJANGO_DB_PATH=$DJANGO_DB_PATH" "$tag")
if ! docker_cmd exec -i "$app" python - <<'PY'
from time import monotonic, sleep
from json import loads
from struct import unpack
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

# This probe runs inside the container and must always use its own loopback.
opener = build_opener(ProxyHandler({}))

def request(path, *, timeout=15, port=8000, **kwargs):
    req = Request(f"http://127.0.0.1:{port}" + path, **kwargs)
    try:
        with opener.open(req, timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as error:
        with error:
            return error.code, error.read()

deadline = monotonic() + 75
attempts = 0
last_result = "no response"
while True:
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise SystemExit(f"Gunicorn health check did not become ready: {last_result}")
    attempts += 1
    try:
        status, body = request("/healthz", timeout=min(5, remaining))
        if status == 200 and body == b"OK":
            break
        last_result = f"HTTP {status}"
    except (URLError, TimeoutError, ConnectionError) as error:
        last_result = str(error)
    sleep(min(1, max(0, deadline - monotonic())))
print(f"Gunicorn health check passed after {attempts} attempt(s).", flush=True)

assert request("/menu/")[0] == 200, "Menu unavailable"
assert request("/static/menus/app.css")[0] == 200, "Collected stylesheet unavailable"
status, body = request("/manifest.webmanifest")
assert status == 200, "PWA manifest unavailable"
manifest = loads(body)
assert (manifest["start_url"], manifest["scope"], manifest["display"]) == ("/menu/", "/", "standalone")
assert {icon["sizes"] for icon in manifest["icons"]} == {"192x192", "512x512"}
for icon in manifest["icons"]:
    status, data = request(icon["src"])
    assert status == 200 and data.startswith(b"\x89PNG\r\n\x1a\n"), "Collected icon unavailable"
    assert "x".join(map(str, unpack(">II", data[16:24]))) == icon["sizes"], "Icon dimensions differ"
assert request("/healthz", port=8001)[0] == 403, "Unconfigured proxy listener must deny requests"
status, body = request("/plats/")
assert status == 200 and "Plat sintètic Docker".encode() in body, "Seed not visible in the restored database"
assert request("/menu/", headers={"Host": "invalid.example"})[0] == 400, "Host validation failed"
assert request("/plantilla/0/lunch/", data=b"category=cereals")[0] == 403, "CSRF validation failed"
print("Health, menu, persisted seed, PWA assets, disabled proxy listener, Host validation and CSRF verified.")
PY
then
    docker_cmd logs "$app"
    exit 1
fi

if "$keep_image"; then
    candidate="menu-familiar:verified-$ref"
    docker_cmd image tag "$tag" "$candidate"
    printf 'Verified candidate: %s\n' "$candidate"
    docker_cmd image inspect --format '{{.Id}}' "$candidate"
fi
if [ -n "${result:-}" ]; then
    image_id=$(docker_cmd image inspect --format '{{.Id}}' "$tag")
    # Retain the verified image without replacing any existing release tag.
    docker_cmd image tag "$image_id" "menu-familiar:verified-$ref-$run_id"
    printf '%s\n' "$image_id" >"$result"
fi
