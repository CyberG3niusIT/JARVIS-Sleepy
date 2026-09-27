# Tooling und GitHub

Stand 27.09.2026. Projektlokales Tooling unterstützt Entwicklung und QA, ist aber keine JARVIS-Runtime-Fähigkeit.

## Vorhandene lokale Hilfen

- `Main/scripts/wsl-pytest.ps1`
- `Main/pyproject.toml`
- `Main/requirements-ci.txt`
- projektlokale Agent-/Skill-Hilfen unter `.claude/`
- `.github/`-Entwürfe für CI, Dependabot, CODEOWNERS und PR-Template

## Regeln

- Kein Tooling darf Commits, Co-Author-Trailer oder Providerwahl ungefragt erzwingen.
- Runtime-Provider und Entwicklungsagent sind getrennte Konzepte.
- Kein API-Secret in Repository, Workflow-Datei oder Handoff-ZIP.
- GitHub-Actions/CI erst nach Prüfung des Repo-Roots und der tatsächlichen Dependency-Matrix aktivieren.
- Keine automatische Anthropic-/Claude-Integration ist für CI oder Runtime erforderlich.

## CI-Status

Vorhandene CI-Dateien sind Entwürfe, solange sie nicht im echten GitHub-Workflow gelaufen sind. Lokale Syntax-/Parsing-Checks sind kein Beweis für einen erfolgreichen Remote-Run.

## Git

Vor Commit/Push immer Repository, Branch, HEAD und Status prüfen. Dirty Changes anderer Arbeiten bewahren. Keine History-Rewrites ohne explizite Entscheidung.
