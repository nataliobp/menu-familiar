#!/bin/sh
set -eu

exec "$(dirname -- "$0")/scripts/compose.sh" up -d --no-build --pull never menu-familiar
