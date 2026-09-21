# Jarvis Voice Assistant Aliases
alias startjarvis='~/jarvis/start.sh'
alias stopjarvis='~/jarvis/stop.sh'
alias restartjarvis='~/jarvis/restart.sh'
alias jarvisstatus='~/jarvis/status.sh'
alias jarvislogs='journalctl --user -u jarvis.service -f'
alias killjarvis='~/jarvis/killswitch.sh'

# Model services (system units — need sudo). Added session #7: start.sh/
# killswitch.sh now manage these too, but a direct alias is handy for
# just bouncing the LLM or TTS server without touching JARVIS itself.
alias llamalogs='journalctl -u llama-server.service -f'
alias chatterboxlogs='journalctl -u chatterbox.service -f'
alias restartllama='sudo systemctl restart llama-server.service'
alias restartchatterbox='sudo systemctl restart chatterbox.service'

# For testing/development (runs in foreground)
alias runjarvis='cd ~/jarvis && python3 jarvis_continuous.py'
