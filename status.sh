#!/bin/bash
#
# Check Jarvis + model service status
#
# Session #7: previously only checked jarvis.service, silently blind to
# llama-server.service/chatterbox.service (system units) — real gap:
# JARVIS could be "running" per this script while its actual local LLM
# or TTS backend was down, with no way to tell from here.
#

echo "📊 Jarvis Status (user unit):"
echo ""
systemctl --user status jarvis.service --no-pager -l
echo ""
echo "📊 llama-server Status (system unit):"
echo ""
systemctl status llama-server.service --no-pager -l 2>/dev/null || echo "  (systemctl status requires sudo, or unit not installed)"
echo ""
echo "📊 chatterbox Status (system unit):"
echo ""
systemctl status chatterbox.service --no-pager -l 2>/dev/null || echo "  (systemctl status requires sudo, or unit not installed)"
echo ""
echo "📋 Recent Jarvis Logs:"
journalctl --user -u jarvis.service -n 20 --no-pager
