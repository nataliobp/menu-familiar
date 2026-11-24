#!/bin/sh
set -eu
repo=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
exec /usr/bin/python3 -I "$repo/scripts/deploy.py" "$@"
