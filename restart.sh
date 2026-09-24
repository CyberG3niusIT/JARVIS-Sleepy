#!/usr/bin/env bash
set -Eeuo pipefail
JARVIS_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
"$JARVIS_ROOT/stop.sh"
"$JARVIS_ROOT/start.sh"
