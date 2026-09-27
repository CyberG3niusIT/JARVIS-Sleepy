# 17 Tooling und GitHub (Vorschlag)

Stand 26.09.2026. Alles hier ist ein Entwurf; nichts wurde gepusht, installiert oder auf GitHub eingerichtet.

## Angelegt (nur lokale Dateien)
- `CLAUDE.md` (Wurzel), `Main/CLAUDE.md`
- `Main/scripts/wsl-pytest.ps1`, `Main/pyproject.toml`, `Main/requirements-ci.txt`
- `.claude/agents/`: `wsl-test-runner`, `voice-integration-reviewer`, `docs-syncer`
- `.claude/skills/`: `run-targeted-tests-wsl`, `runtime-status`, `runtime-restart`, `voice-log-tail`, `config-verify`, `review-voice-integration`
- `Main/.github/`: `workflows/ci-python.yml`, `dependabot.yml`, `CODEOWNERS`, korrigiertes `pull_request_template.md`

Hinweis: GitHub liest `.github` nur im Wurzelverzeichnis des Repos. Da `Main` ein Worktree ist, liegt `Main/.github` im Repo-Root (Branch `backup/...`), wirksam wird es erst nach Merge in `main`.

## Vorschlag Plugin-Marketplace (eigenes Repo, z. B. `JARVIS-Claude-Plugins`)
```
.claude-plugin/marketplace.json     # name, owner, plugins: [{name: jarvis-dev, source: ./plugins/jarvis-dev}]
plugins/jarvis-dev/.claude-plugin/plugin.json   # name, version, description
plugins/jarvis-dev/agents/*.md      # Kopien der Projekt-Agents
plugins/jarvis-dev/skills/<name>/SKILL.md
```
Vor Veroeffentlichung mit `validate-plugin` pruefen. Die projektlokalen Kopien in `.claude/` bleiben, bis das Plugin stabil ist. Pfade in den Skills (Windows/WSL) sind projektspezifisch und muessten vorher parametrisiert werden.

## Schritte, die der Nutzer selbst ausfuehren muss
1. Repo-Sichtbarkeit pruefen: privat (Sprach-/Privacy-Daten, 240-KB-Patch im Root).
2. `gh` installieren, dann `gh auth login` (Nutzer selbst).
3. Branch-Protection auf `main`: PR-Pflicht, Status-Check `ci-python`, keine Force-Pushes, CODEOWNERS-Review.
4. Secret Scanning und Push Protection unter Settings > Code security aktivieren.
5. claude-code-action: Repo-Secret `ANTHROPIC_API_KEY` selbst anlegen (Settings > Secrets > Actions), dann in Claude Code `/install-github-app` ausfuehren oder Workflow mit `anthropics/claude-code-action` manuell anlegen.
6. `.github` ggf. in den Repo-Root von `main` uebernehmen (siehe Hinweis oben).

## Verifiziert vs. angenommen
Verifiziert (lokal geprueft, siehe Bericht): YAML-Dateien parsen, `wsl-pytest.ps1` parst, `pyproject.toml` parst, Frontmatter der Agents/Skills ist syntaktisch gueltig, ein Testlauf (`test_privacy_audio_reset.py`) sammelt mit der neuen `pyproject.toml`.

Angenommen / unverifiziert:
- `ci-python.yml` lief nie; die Paketliste in `requirements-ci.txt` ist aus Imports abgeleitet, weitere transitive Pakete sind moeglich.
- Dass alle Tests in `tests/unit` ausser den drei ausgeschlossenen ohne Hardware laufen.
- Ruff-Regeln (E, F) melden auf bestehendem Code vermutlich viel; deshalb `continue-on-error`.
- Marker `hardware`/`wsl`/`slow` sind definiert, aber noch an keinem Test gesetzt.
- Plugin-Layout nach Claude-Code-Konvention aus dem Gedaechtnis; gegen `validate-plugin` pruefen.
- Repo-Sichtbarkeit (privat?) und Ort von Tauri (kein `src-tauri` in `UI/`) sind offen.
