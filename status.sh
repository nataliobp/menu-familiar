#!/bin/sh
set -eu

exec "$(dirname -- "$0")/scripts/compose.sh" ps --all menu-familiar
