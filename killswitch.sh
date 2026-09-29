#!/bin/bash
#
# Jarvis Emergency Kill Switch
# Stops Jarvis AND its model services completely, prevents restart
#
# Session #7: previously only stopped jarvis.service and killed a few
# process names, missing llama-server.service/chatterbox.service
# entirely — an "emergency kill switch" that left the local LLM and TTS
# GPU servers running was a real gap, not acceptable for what this
# script promises to do.
#

echo "🛑 JARVIS EMERGENCY KILL SWITCH ACTIVATED"
echo ""

# Stop the systemd service
echo "Stopping systemd service..."
systemctl --user stop jarvis.service

# Disable auto-restart
echo "Disabling service..."
systemctl --user disable jarvis.service

# Stop and disable the model services too (system units — need sudo)
echo "Stopping model services (llama-server, chatterbox)..."
if sudo -n true 2>/dev/null; then
    sudo systemctl stop llama-server.service chatterbox.service
    sudo systemctl disable llama-server.service chatterbox.service
else
    echo "⚠️  No passwordless sudo — llama-server/chatterbox not stopped via systemd."
    echo "   Run manually: sudo systemctl disable --now llama-server.service chatterbox.service"
fi

# Stop the Primary/Expert user units first: they have Restart=on-failure, so a bare pkill of
# llama-server would just bring them back.
echo "Stopping llama-server user units (primary, expert)..."
systemctl --user stop llama-server-primary.service llama-server-expert.service 2>/dev/null || true

# Kill any running Python processes running jarvis
echo "Killing any remaining Jarvis processes..."
pkill -9 -f "jarvis_continuous.py"
pkill -9 -f "jarvis/main.py"

# Kill TTS/STT/model-server processes directly too, in case the systemd
# stop above didn't reach them (no sudo, or a process started outside
# systemd entirely — e.g. run manually via runjarvis/chatterbox_server.py).
echo "Killing any remaining model-server and audio processes..."
pkill -9 -f "llama-server"
pkill -9 -f "chatterbox_server.py"
pkill -9 -f "piper"
pkill -9 -f "aplay"
pkill -9 -f "whisper-cli"

echo ""
echo "✅ Jarvis and its model services have been shut down completely"
echo ""
echo "To restart everything:"
echo "  ./start.sh"
echo ""
echo "Or use the 'startjarvis' alias"
