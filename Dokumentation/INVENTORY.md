# Dokumentationsinventar und Klassifikation

## Aktueller Stand

Die zentrale Dokumentation wurde am 27.09.2026 gegen die zuletzt verfügbaren Runtime-, Git- und Code-Audit-Befunde aktualisiert. Das historische Quellenregister unter `LEGACY/SOURCE_REGISTER.md` bleibt ein Snapshot der älteren Erhebung und wird nicht als aktueller Architekturstand interpretiert.

## Kanonisch

CURRENT/PARTIAL je nach Evidenz:

- `00_PROJECT_STATUS.md`
- `01_ARCHITECTURE.md`
- `02_COMPONENTS.md`
- `03_RUNTIME_AND_MODELS.md`
- `04_AGENTS_AND_ORCHESTRATION.md`
- `05_MEMORY.md`
- `06_VOICE_STT_TTS.md`
- `07_TOOLS_MCP_SKILLS.md`
- `08_SCHOOL_MOBILITY.md`
- `09_SECURITY_PRIVACY.md`
- `10_CONFIGURATION.md`
- `11_INSTALLATION_OPERATION.md`
- `12_TESTING_QA.md`
- `13_KNOWN_ISSUES.md`
- `14_ROADMAP.md`
- `15_CHANGELOG_DEVELOPMENT.md`
- `16_UI_CONTROL_HUB.md`
- `17_TOOLING_UND_GITHUB.md`
- `18_DESKTOP_REDESIGN_LOVABLE.md`

## Legacy / nicht als Source of Truth

- `Architecture/`
- `Backend-RC/`
- bisheriger `UI/`-Worktree als visuelle Implementierung
- Mobile-App für Desktop-Architektur
- ältere Main-README/PROJECT_OVERVIEW/docs, soweit sie Qwen als Primary, alte Ports, alte TTS/STT-Hardware oder automatische Claude-Pfade behaupten

## Sensible / nicht in Übergaben

- `.env`
- Logs
- private Datenbanken
- Tokens/Credentials
- persönliche Runtime-Dateien
- `.git-store`
- agentenspezifische Cache-/State-Verzeichnisse

## Klassifikationsregeln

- **CURRENT**: direkt durch aktuellen Code/Runtime/Test belegt
- **PARTIAL**: Code vorhanden, Abnahme unvollständig
- **LEGACY**: historischer Stand, nicht aktuelle Source of Truth
- **EXPERIMENTAL**: Versuch/Entwurf ohne belastbare Abnahme
- **OBSOLETE**: generated/cache/nichtkanonische Kopie
