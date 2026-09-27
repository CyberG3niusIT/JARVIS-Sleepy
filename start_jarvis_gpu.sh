#!/bin/bash
set -euo pipefail

export HSA_OVERRIDE_GFX_VERSION=11.0.0
export ROCM_PATH=/opt/rocm-7.2.0
export LD_LIBRARY_PATH="/opt/rocm-7.2.0/lib:${LD_LIBRARY_PATH:-}"

JARVIS_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export JARVIS_ROOT

# Never enter the normal interactive runtime silently on Piper because the
# configured primary Chatterbox server was never started. A deliberate
# degraded boot remains possible via JARVIS_ALLOW_DEGRADED_TTS=1.
/usr/bin/python3 "$JARVIS_ROOT/scripts/check_chatterbox_runtime.py" --wait 120

exec /home/alex/jarvis-venv/bin/python \
    "$JARVIS_ROOT/jarvis_continuous.py"
