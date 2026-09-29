# JARVIS-Sleepy (Wurzelverzeichnis)

Hinweis: Im Wurzelverzeichnis gibt es KEIN `.git`. `.git-store` ist ein Bare-Repo (origin: https://github.com/CyberG3niusIT/JARVIS-Sleepy.git). Gearbeitet wird nur in den Worktrees. Details zum Python-Backend: `Main/AGENTS.md`.

## Layout

| Ordner | Branch | Zweck |
|---|---|---|
| `Main` | `backup/jarvis-runtime-voice-2026-09-24` | Python-Backend (Voice, LLM, Runtime, Tests) |
| `UI` | `Codex/jarvis-ui` | Desktop-UI (Vite/React, Control Hub) |
| `Mobile-App` | `J.A.R.V.I.S-Mobile-App` | Mobile-App |
| `Architecture` | `Codex/jarvis-architecture` | Architektur-Arbeit |
| `Backend-RC` | `Codex/jarvis-sleepy-backend-rc-nhtfgm` | Backend-Release-Candidate |
| `Dokumentation` | (unversioniert) | Deutsche Doku `00`-`17` |
| `Handoff` | (unversioniert) | Übergabenotizen |

## WSL-Regeln (Windows-Host)
- Projekt-Distro ist `Ubuntu-24.04`. Die Standard-Distro ist `OpenClawGateway`, also immer `wsl -d Ubuntu-24.04 ...`.
- Python: `/home/alex/jarvis-venv/bin/python3`. pytest ist für Windows-Python NICHT installiert.
- Aus Git-Bash: `MSYS_NO_PATHCONV=1` vor `wsl` setzen, sonst werden `/mnt/...`-Pfade umgeschrieben.
- Die `.git`-Datei der Worktrees enthält einen Windows-Pfad. Git funktioniert nicht aus WSL heraus, nur mit Windows-Git.
- Tests gezielt starten: `Main\scripts\wsl-pytest.ps1 tests/unit/<datei>.py` (nie blind die Vollsuite).

## Regeln
- Antworten und Nutzertexte auf Deutsch.
- Keine Änderungen an `.env`, `config.yaml`, `*.service` ohne Rückfrage.
- Privacy-Gate nie umgehen.
- Nie behaupten, etwas sei getestet, wenn es nicht gelaufen ist.
- Keine Commits/Pushes/Checkouts/Resets, außer der Nutzer verlangt es ausdrücklich.
- Nur innerhalb der Worktrees editieren.
- Kein ungefragtes einfügen von zb. Co-Autor oder anderen Anthropic spuren, außer der Nutzer verlangt es ausdrücklich.