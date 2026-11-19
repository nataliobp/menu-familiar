#!/bin/sh
set -eu

repo=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
# Use the production file even if a previous QA session exported settings.
unset MENU_IMAGE MENU_DATA_DIR MENU_BIND_ADDRESS MENU_PORT
unset DJANGO_SECRET_KEY DJANGO_ALLOWED_HOSTS
exec sudo docker compose --project-name menu-familiar \
    --env-file "$repo/.env" -f "$repo/compose.yaml" "$@"
