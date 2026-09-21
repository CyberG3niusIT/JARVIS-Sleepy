#!/bin/bash
#
# Start Jarvis + its local model services
#
# Session #7: previously only managed jarvis.service (user-level).
# llama-server.service and chatterbox.service (added session #5/#6,
# systemd/*.service) were never wired into this control plane at all —
# real gap, not just a documentation one. jarvis.service is a USER unit
# (systemctl --user) — confirmed by this script's own pre-existing
# convention (see systemd/README.md for the evidence). llama-server/
# chatterbox are SYSTEM units, so starting them needs sudo; skipped with
# a clear message if sudo isn't available non-interactively (e.g. a
# constrained session) rather than hanging on a password prompt.
#

echo "🟢 Starting Jarvis model services (llama-server, chatterbox)..."
if sudo -n true 2>/dev/null; then
    sudo systemctl start llama-server.service chatterbox.service
    sudo systemctl enable llama-server.service chatterbox.service
else
    echo "⚠️  No passwordless sudo — skipping llama-server/chatterbox."
    echo "   Run manually: sudo systemctl enable --now llama-server.service chatterbox.service"
fi

echo "🟢 Starting Jarvis..."
systemctl --user start jarvis.service
systemctl --user enable jarvis.service

# Wait a moment for startup
sleep 2

# Show status
systemctl --user status jarvis.service --no-pager -l
