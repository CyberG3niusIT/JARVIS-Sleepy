#!/bin/bash
set -euo pipefail

JARVIS_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$JARVIS_ROOT/systemd/chatterbox.env"
CHATTERBOX_PYTHON="/home/alex/chatterbox-venv/bin/python3"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "FEHLER: Chatterbox-Konfiguration fehlt: $ENV_FILE" >&2
    exit 1
fi

# Export every KEY=VALUE from the canonical, non-secret runtime file.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${CHATTERBOX_AUDIO_PROMPT_PATH:?CHATTERBOX_AUDIO_PROMPT_PATH fehlt}"
: "${CHATTERBOX_AUDIO_PROMPT_SHA256:?CHATTERBOX_AUDIO_PROMPT_SHA256 fehlt}"

if [[ ! -x "$CHATTERBOX_PYTHON" ]]; then
    echo "FEHLER: Chatterbox-Python nicht ausführbar: $CHATTERBOX_PYTHON" >&2
    exit 1
fi

if [[ ! -f "$CHATTERBOX_AUDIO_PROMPT_PATH" ]]; then
    echo "FEHLER: Voice-Anker fehlt: $CHATTERBOX_AUDIO_PROMPT_PATH" >&2
    exit 1
fi

actual_sha="$(sha256sum "$CHATTERBOX_AUDIO_PROMPT_PATH" | awk '{print $1}')"
if [[ "$actual_sha" != "$CHATTERBOX_AUDIO_PROMPT_SHA256" ]]; then
    echo "FEHLER: Voice-Anker hat nicht den kanonischen SHA256." >&2
    echo "Erwartet: $CHATTERBOX_AUDIO_PROMPT_SHA256" >&2
    echo "Ist:      $actual_sha" >&2
    exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "FEHLER: ffmpeg fehlt; Chatterbox-Tempo 0.89 kann nicht angewendet werden." >&2
    exit 1
fi

export HSA_OVERRIDE_GFX_VERSION="${HSA_OVERRIDE_GFX_VERSION:-11.0.0}"
export ROCM_PATH="${ROCM_PATH:-/opt/rocm-7.2.0}"
export LD_LIBRARY_PATH="$ROCM_PATH/lib:${LD_LIBRARY_PATH:-}"

exec "$CHATTERBOX_PYTHON" "$JARVIS_ROOT/tools/chatterbox_server.py"
