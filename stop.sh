#!/bin/sh
set -eu

exec "$(dirname -- "$0")/scripts/compose.sh" stop menu-familiar
