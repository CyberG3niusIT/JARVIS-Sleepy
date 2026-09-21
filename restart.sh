#!/bin/bash
#
# Restart Jarvis Service
#
# Only restarts jarvis.service (user unit) — leaves llama-server.service/
# chatterbox.service (system units) running, matching stop.sh's
# philosophy (a misbehaving JARVIS usually doesn't mean the model
# servers need restarting too). Restart those independently if needed:
#   sudo systemctl restart llama-server.service chatterbox.service
#

echo "🔄 Restarting Jarvis..."
systemctl --user restart jarvis.service

# Wait a moment for restart
sleep 2

# Show status
systemctl --user status jarvis.service --no-pager -l
