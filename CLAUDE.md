# JARVIS Main (Python-Backend)

Worktree `Main`, Branch `backup/jarvis-runtime-voice-2026-09-24`. Übergeordnete Regeln: `../CLAUDE.md`.

## Layout
| Worktree | Branch | Zweck |
|---|---|---|
| Main | backup/jarvis-runtime-voice-2026-09-24 | Python-Backend (dieses Verzeichnis) |
| UI | claude/jarvis-ui | Desktop-UI |
| Mobile-App | J.A.R.V.I.S-Mobile-App | Mobile-App |
| Architecture | claude/jarvis-architecture | Architektur |
| Backend-RC | claude/jarvis-sleepy-backend-rc-nhtfgm | Release-Candidate |

## WSL-Aufruf
- Immer `wsl -d Ubuntu-24.04` (Default-Distro ist `OpenClawGateway`).
- Interpreter: `/home/alex/jarvis-venv/bin/python3`. pytest fehlt in Windows-Python.
- Git-Bash: `MSYS_NO_PATHCONV=1`. Git nicht aus WSL (Worktree-`.git` enthält Windows-Pfad), Windows-Git nutzen.

## Gezielte Tests
```powershell
scripts\wsl-pytest.ps1 tests/unit/test_privacy_audio_reset.py tests/unit/test_turn_assembler.py
```
Entspricht: `MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -e bash -c 'cd /mnt/c/Users/Alex/Projekte/JARVIS-Sleepy/Main && /home/alex/jarvis-venv/bin/python3 -m pytest <dateien> -q -p no:cacheprovider'`.
`-All` startet `tests/unit` + `tests/routing` (Marker `hardware`/`wsl` ausgeschlossen); nur bewusst nutzen. `tests/routing` lädt Modelle (torch) und ist langsam.

## Runtime
`.\JARVIS-Runtime.ps1 -Action getRuntime|start|stop|restart [-Wait]` (JSON auf stdout; start/stop/restart laufen ohne `-Wait` detached).
- Ein WSL-Keepalive ist nötig, weil `linger` aus ist. Ein direktes `wsl -e bash start.sh` lässt den User-systemd (und damit LLM/Chatterbox) sterben, sobald die Session endet. Immer über `JARVIS-Runtime.ps1`.
- Logs: `wsl -d Ubuntu-24.04 -e bash -c 'journalctl --user -u jarvis.service -n 100 --no-pager'`.

## Architektur (Kurz)
- PRIMARY: Gemma 4 12B (llama.cpp + mmproj), direktes Audio, Tools, Vision; Port 8080.
- EXPERT: Qwen3.5-35B-A3B (Port 8082), nur per GPU-Handover (`core/model_handover.py`), nie parallel zum Primary resident.
- NPU-Sensor-Schicht (Präsenz), Chatterbox-TTS, Turn-Assembler (`core/turn_assembler.py`), spekulative, Wake-Wort-gesteuerte Turns.
- Config-Schlüssel: `llm.primary.*`, `llm.expert.*`, `handover.*`, `turn.*`, `llm.response_language`. Hinweis: `llm.small` (8081) ist aktiviert, aber laut Audit läuft dort nichts.
- Stand/Befunde: `Dokumentation/13_KNOWN_ISSUES.md` (unverifizierte Punkte dort markiert).

## Regeln
- Antworten auf Deutsch.
- Keine Änderung an `.env`, `config.yaml`, systemd-Units (`*.service`) ohne Rückfrage.
- Privacy-Gate (`core/privacy*`) nie umgehen; Audio/Transkripte nicht loggen, wenn Privacy aktiv.
- Keine erfundenen Testergebnisse; Nicht-Gelaufenes als "nicht getestet" melden.
- Keine Vollsuite blind. Keine Commits/Pushes, außer auf Anfrage. Nur in Worktrees editieren.

## Doku-Zuordnung (`../Dokumentation/`)
| Änderung | Datei |
|---|---|
| Komponenten/Architektur | `01_ARCHITECTURE.md`, `02_COMPONENTS.md` |
| Runtime, Modelle, Handover, systemd | `03_RUNTIME_AND_MODELS.md` |
| Voice/STT/TTS/Turns | `06_VOICE_STT_TTS.md` |
| Tools/MCP/Skills | `07_TOOLS_MCP_SKILLS.md` |
| Privacy/Security | `09_SECURITY_PRIVACY.md` |
| Config-Schlüssel | `10_CONFIGURATION.md` |
| Installation/Betrieb | `11_INSTALLATION_OPERATION.md` |
| Tests | `12_TESTING_QA.md` |
| Bekannte Probleme | `13_KNOWN_ISSUES.md` |
| Changelog | `15_CHANGELOG_DEVELOPMENT.md` |
| Tooling/GitHub | `17_TOOLING_UND_GITHUB.md` |
