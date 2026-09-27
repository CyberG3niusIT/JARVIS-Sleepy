# Dokumentationsinventar und Klassifikation

Erhebung am 24.09.2026. Verzeichnisse `Architecture`, `Backend-RC` und `UI` sind getrennte Quellstände im Projektordner; ihre Texte wurden nicht als Main-HEAD behandelt. Das Markdown-Quellenregister führt **137 Dateivorkommen in 5 Checkouts** mit Hash und Klassifikation; darin stecken **43 unterschiedliche Inhaltsgruppen**, einschließlich generierter pytest-Cache-README-Dateien. Nichtdokumentarische Vorlagen/Metadaten und Audit-/Prompt-Textdateien sind hier thematisch aufgeführt, nicht inhaltlich übernommen. Keine `.env`, Logs oder Datenbanken gelesen. Bei der geprüften Dateiendungserhebung wurden keine `.rst`- oder `.adoc`-Dateien gefunden.

## Klassifikationsregeln

- **CURRENT**: Aussagen direkt durch aktuellen Code/Config/Git bestätigt.
- **PARTIAL**: einzelne Abschnitte aktuell, andere historisch oder nicht verifiziert.
- **LEGACY**: historische Projekt-/Laufzeitbeschreibung ohne Gültigkeitsnachweis.
- **EXPERIMENTAL**: Versuch/Entwurf ohne vollständige Abnahme.
- **OBSOLETE**: Cache-/Generated-/nichtkanonische Kopie, nicht als Projektdoku führen.

## Main-Dateien

| Quelle(n) | Klassifikation | Behandlung |
|---|---|---|
| `README.md`, `PROJECT_OVERVIEW.md` | PARTIAL / LEGACY | ersetzt durch zentrale README; überholte konkrete Laufzeitdaten nicht übernommen |
| `docs/ARCHITECTURE.md` | PARTIAL / LEGACY | Architektur gegen Quellpfade neu beschrieben; historische Notizen bleiben Quelle |
| `docs/SETUP_GUIDE.md`, `docs/DEVELOPMENT.md`, `CONTRIBUTING.md`, `systemd/README.md` | PARTIAL | Betriebshinweise zentral abstrahiert, aktuelle Umgebung vor Ausführung prüfen |
| `docs/SCHOOL_MOBILITY.md` | EXPERIMENTAL | neue uncommittete Fachimplementierung; Abnahme offen |
| `docs/VOCAL_DIRECTIONS.md`, `docs/VOICE_BASELINE.md` | EXPERIMENTAL | Arbeitsbaumänderungen, keine Produktfreigabe |
| `docs/STT_WORKER_PROCESS.md`, `docs/TTS_VOICE_OPTIONS.md`, `docs/VOICE_TRAINING_GUIDE.md` | PARTIAL / LEGACY | historische Optionen/Versuche; aktuelle Engine configabhängig |
| `docs/DEVELOPMENT_INVENTORY.md`, `DEVELOPMENT_VISION.md`, `PRIORITY_ROADMAP.md`, `CHANGELOG.md` | LEGACY | historical claims not accepted as current without code proof |
| `docs/SEMANTIC_INTENT_MATCHING.md`, `docs/INTERACTION_ARTIFACT_CACHE_*`, `docs/EDGE_CASE_TESTING.md` | PARTIAL / LEGACY | design/research/test plans versus current implementation require item-level review |
| `docs/CONSOLE_GUIDE.md`, `docs/SYSTEM_SPECIFIC_NOTES.md` | PARTIAL / LEGACY | operational details may drift; no host-specific private values carried over |
| `docs/SKILL_DEVELOPMENT.md`, `docs/SKILL_EDITING_SYSTEM.md`, `skills/CHANGELOG.md`, `skills/system/web_navigation/README.md` | PARTIAL | skill architecture exists; individual skill behavior check against code |
| `SECURITY.md`, `CODE_OF_CONDUCT.md`, `governance/commandments.md` | CURRENT as policy sources | governance files not copied as technical runtime guarantees |
| `.github/ISSUE_TEMPLATE/*`, `.github/pull_request_template.md` | CURRENT templates | process templates, not runtime documentation |
| `assets/README.md` | PARTIAL | asset inventory needs current filesystem check |
| `tests/grading_system_overhaul_session276.md` | LEGACY | session-specific test narrative |
| `reports/journal_audits/audit_2026-03-17.txt`, `audit_2026-03-23.txt`, `voice_training/prompts_de.txt` (Main, Architecture, Backend-RC, UI) | LEGACY / sensitive review required | Inhalt nicht kopiert; kann private oder beispielhafte Daten enthalten |
| `.pytest_cache/README.md` | OBSOLETE/generated | excluded |

## Weitere Quellbestände

- `Architecture/`: duplizierte/ältere Projektkopie metadaten- und docsseitig parallel zu Main; alle Markdown-Kategorien aus Main finden sich dort überwiegend erneut; zusätzliche `_in_development/web_navigation/README.md`, journal-audit-Texte und voice prompts. Klassifikation: **LEGACY**; nicht als gleichwertiger HEAD behandelt.
- `Backend-RC/`: ältere Backend-Kopie mit denselben Kern-README/docs/Policy/Skill-/Systemd-Dateien und zusätzlichen journal audits/voice prompt; **LEGACY**.
- `UI/`: ältere UI-Kopie mit wiederholten allgemeinen Dokumenten plus `docs/UI_INTEGRATION.md`; **LEGACY**.
- `Mobile-App/README.md`, `android/PORTING_PLAN.md`, `android/OPEN_DECISIONS.md`, `src/routes/README.md`: eigenes Git-Repo, eigener Branch/HEAD. README/Porting Plan **PARTIAL**; Open Decisions **CURRENT** als offene Fragen; Routen-README **PARTIAL**. Referenz im zentralen Mobile-Abschnitt, nicht verschoben.
- `.claude-flow`, `.swarm`, `.git-store`: Verzeichnisse vorhanden, kein fachlicher Runtime-Code-/Doku-Nachweis für produktive Integration daraus abgeleitet.

## Referenzen und Zentralisierung

Der zentrale Einstieg ist `Dokumentation/README.md`; das vollständige Pfad-/Hashregister ist [LEGACY/SOURCE_REGISTER.md](LEGACY/SOURCE_REGISTER.md). Interne Links im zentralen Doku-Baum sind geprüft. Bestehende Repo-Dateien wurden nicht verschoben oder verändert; ihre existierenden Links bleiben dadurch erhalten. Die zentralen kanonischen Fachdokumente und das vollständige Quellenregister befinden sich im neuen Ordner; die bytegleichen oder sensiblen historischen Quelldateien verbleiben an den Originalorten und werden dort durch das zentrale Register als Legacy/Partial oder Experimental gekennzeichnet. Sie wurden nicht roh in die zentrale Ablage kopiert, damit keine privaten Pfade, personenbezogenen Beispiele oder sensiblen Betriebsinhalte weiterverbreitet werden.
