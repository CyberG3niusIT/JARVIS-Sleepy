#!/usr/bin/env bash
set -Eeuo pipefail

JARVIS_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/jarvis-runtime"
mkdir -p "$STATE_DIR"
exec 9>"$STATE_DIR/control.lock"
flock 9

state="$(systemctl --user show jarvis.service --property=LoadState --value 2>/dev/null || true)"
if [[ "$state" == not-found || -z "$state" ]]; then
    echo "STOPPED: jarvis.service ist nicht installiert."
    exit 0
fi
[[ "$state" == loaded ]] || { echo "ERROR: jarvis.service ist nicht korrekt geladen."; exit 1; }
fragment="$(systemctl --user show jarvis.service --property=FragmentPath --value 2>/dev/null || true)"
fragment_real="$(readlink -f "$fragment" 2>/dev/null || true)"
unit_real="$(readlink -f "$JARVIS_ROOT/systemd/jarvis.service" 2>/dev/null || true)"
execstart="$(systemctl --user show jarvis.service --property=ExecStart --value 2>/dev/null || true)"
[[ -n "$unit_real" && "$fragment_real" == "$unit_real" && "$execstart" == *"/home/alex/jarvis-venv/bin/python3"* && "$execstart" == *"$JARVIS_ROOT/jarvis_continuous.py"* ]] || {
    echo "ERROR: jarvis.service gehört nicht zur geprüften JARVIS-Unit; es wurde nichts gestoppt."
    exit 1
}

if systemctl --user is-active --quiet jarvis.service; then
    systemctl --user stop jarvis.service
fi
if systemctl --user is-active --quiet jarvis.service; then
    echo "ERROR: jarvis.service ist nach Stop weiterhin aktiv."
    exit 1
fi
echo "STOPPED: JARVIS-Backend beendet; LLM, Chatterbox und VVS bleiben unverändert."
