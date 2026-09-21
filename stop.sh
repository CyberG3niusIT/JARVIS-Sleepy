#!/bin/bash
#
# Stop Jarvis Service (graceful)
#
# Only stops jarvis.service (user unit) — deliberately leaves
# llama-server.service/chatterbox.service (system units) running, since
# a graceful "pause JARVIS" shouldn't tear down GPU-loaded models that
# are slow to reload. Use killswitch.sh for a full stop of everything.
#

echo "🟡 Stopping Jarvis..."
systemctl --user stop jarvis.service

echo "✅ Jarvis stopped"
echo ""
echo "Service is still enabled and will restart on boot."
echo "To disable: systemctl --user disable jarvis.service"
echo "llama-server/chatterbox were left running — use killswitch.sh to stop everything."
