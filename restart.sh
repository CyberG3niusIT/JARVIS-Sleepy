#!/usr/bin/env bash
set -Eeuo pipefail
JARVIS_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# A live Primary<->Expert model handover (core/model_handover.py) must not be interrupted: stopping the
# daemon mid-swap would leave the expert running and the primary down. Wait for it, else refuse.
wait_for_handover() {
    local waited=0 limit="${JARVIS_HANDOVER_WAIT_S:-300}" live
    [[ -x "$RUNTIME_PYTHON" ]] || return 0
    while live="$("$RUNTIME_PYTHON" "$JARVIS_ROOT/core/runtime_state.py" --handover-live 2>/dev/null)"; do
        if (( waited == 0 )); then
            echo "Ein Modellwechsel (Expert-Handover, Zustand/PID: $live) läuft gerade; warte bis zu $limit s auf dessen Ende."
        fi
        if (( waited >= limit )); then
            echo "ERROR: Der Modellwechsel läuft noch nach $limit s. Es wurde nichts gestoppt; bitte später erneut versuchen."
            return 1
        fi
        sleep 2
        waited=$((waited + 2))
    done
    return 0
}
RUNTIME_PYTHON="${JARVIS_RUNTIME_PYTHON:-/home/alex/jarvis-venv/bin/python3}"
JARVIS_RUNTIME_STATE_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/jarvis-runtime" wait_for_handover || exit 1

# The restart owns the lifecycle record from here until start.sh finishes, so the
# runtime supervisor sees STARTING (not a STOPPED flicker) between stop and start.
export JARVIS_LIFECYCLE_ACTION=restart
export JARVIS_RUNTIME_STATE_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/jarvis-runtime"
RUNTIME_PYTHON="${JARVIS_RUNTIME_PYTHON:-/home/alex/jarvis-venv/bin/python3}"
if [[ -x "$RUNTIME_PYTHON" ]]; then
    "$RUNTIME_PYTHON" "$JARVIS_ROOT/core/runtime_state.py" \
        restart running --pid "$$" >/dev/null 2>&1 || true
fi

"$JARVIS_ROOT/stop.sh"
"$JARVIS_ROOT/start.sh"
