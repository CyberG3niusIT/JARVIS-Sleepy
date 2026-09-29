#!/usr/bin/env bash
set -Eeuo pipefail

JARVIS_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/jarvis-runtime"
mkdir -p "$STATE_DIR"
exec 9>"$STATE_DIR/control.lock"
flock 9

# Lifecycle record for the runtime supervisor (scripts/runtime_status.py reads it).
# Best effort: recording must never change the outcome of a stop. Under
# restart.sh the restart itself owns the record until start.sh finishes.
export JARVIS_RUNTIME_STATE_DIR="$STATE_DIR"
RUNTIME_PYTHON="${JARVIS_RUNTIME_PYTHON:-/home/alex/jarvis-venv/bin/python3}"
lifecycle_action="${JARVIS_LIFECYCLE_ACTION:-stop}"
record_lifecycle() {
    [[ -x "$RUNTIME_PYTHON" ]] || return 0
    "$RUNTIME_PYTHON" "$JARVIS_ROOT/core/runtime_state.py" \
        "$lifecycle_action" "$@" --pid "$$" >/dev/null 2>&1 || true
}
finish_lifecycle() {
    local code=$?
    if (( code != 0 )); then
        record_lifecycle finished --result ERROR --message "Stop fehlgeschlagen (exit $code)."
    elif [[ "$lifecycle_action" == stop ]]; then
        record_lifecycle finished --result STOPPED
    fi
}
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
wait_for_handover || exit 1   # before the EXIT trap: a refusal leaves the lifecycle record untouched
trap finish_lifecycle EXIT
if [[ "$lifecycle_action" == stop ]]; then record_lifecycle running; fi

# The read-only desktop API goes first (it only reads what the voice daemon writes). Only this checkout's
# unit is stopped; a foreign one is reported and left alone, and never blocks stopping the voice backend.
desktop_unit=jarvis-desktop-api.service
desktop_state="$(systemctl --user show $desktop_unit --property=LoadState --value 2>/dev/null || true)"
if [[ "$desktop_state" == loaded ]]; then
    desktop_fragment_real="$(readlink -f "$(systemctl --user show $desktop_unit --property=FragmentPath --value 2>/dev/null || true)" 2>/dev/null || true)"
    desktop_unit_real="$(readlink -f "$JARVIS_ROOT/systemd/$desktop_unit" 2>/dev/null || true)"
    desktop_exec="$(systemctl --user show $desktop_unit --property=ExecStart --value 2>/dev/null || true)"
    if [[ -n "$desktop_unit_real" && "$desktop_fragment_real" == "$desktop_unit_real" \
          && "$desktop_exec" == *"$JARVIS_ROOT/jarvis_web.py"* && "$desktop_exec" == *"--desktop-mode"* ]]; then
        if systemctl --user is-active --quiet $desktop_unit; then
            systemctl --user stop $desktop_unit
        fi
        if systemctl --user is-active --quiet $desktop_unit; then
            echo "ERROR: $desktop_unit ist nach Stop weiterhin aktiv."
            exit 1
        fi
    else
        echo "WARN: $desktop_unit gehört nicht zu diesem Checkout; unverändert gelassen."
    fi
fi

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
