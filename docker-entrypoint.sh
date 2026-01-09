#!/usr/bin/env bash
set -euo pipefail
# ensure we're in the app directory
cd /data
# pass through any args and run bot.py with unbuffered output
exec python -u bot.py "$@"
