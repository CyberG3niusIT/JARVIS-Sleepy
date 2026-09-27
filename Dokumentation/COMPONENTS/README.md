# Komponentenregister

Status: **implemented**, **partial**, **experimental**, **planned**, **blocked**, **deprecated**. Wenn Code und eine ausdrückliche Planung fehlen, steht **not implemented / not evidenced**; daraus wird kein `planned` erfunden. `implemented` bezeichnet einen Codepfad, nicht Produktionsbetrieb oder vollständige Featureabnahme. Alle Statuswerte gelten für die geprüfte lokale Main-Arbeitskopie am 24.09.2026.

| Bereich | Status | Evidenz / Grenze |
|---|---|---|
| JARVIS Core, Pipeline, Console | implemented | `core/pipeline.py`, `jarvis_console.py`; echte Audiogeräte nicht live geprüft |
| Continuous Voice | partial | `jarvis_continuous.py`; STT/TTS-/Device-Abhängigkeiten, kein aktueller Prozessnachweis |
| Web UI / API | partial | `jarvis_web.py`, `web/`; Backend-Pfade im Code, nicht live abgenommen |
| ConversationRouter | implemented | `core/conversation_router.py`; mehrere Frontends binden ihn unterschiedlich ein |
| TaskPlanner | implemented | `core/task_planner.py`; Plan, Step, Abbruch, Pause/Resume und Ausführung im Code |
| MemoryManager | implemented | `core/memory_manager.py`; Daten-/Indexinitialisierung nicht geprüft |
| PeopleManager | implemented | `core/people_manager.py`; Personenbestand privat/external |
| SkillManager / Skills | implemented | `core/skill_manager.py`, `skills/`; externe Modell-/Skill-Abhängigkeiten möglich |
| ToolRegistry / ToolExecutor | implemented | `core/tool_registry.py`, `core/tool_executor.py`; Einzelwerkzeuge separat zu bewerten |
| MCPBridge | partial | `core/mcp_client.py`; Client implementiert, aktiver `mcp_servers`-Block in Config auskommentiert |
| ReminderManager | implemented | `core/reminder_manager.py`; Scheduler-/Kalenderdienstzustand nicht live geprüft |
| ObservationCollector | implemented | `core/observation_collector.py`; Web startet bei vorhandenem EventLogger; externe Claude-Beratung konfiguriert |
| School | experimental | `core/school_db.py`, Personal Skill und neue Tests uncommittet |
| Mobility | experimental | Contract/Planner/Skill und neue Tests uncommittet; Live-Abnahme offen |
| Vocal Directions | experimental | `core/vocal_directions.py` und Pipeline-/TTS-Änderungen uncommittet; Hörfreigabe offen |
| Android-App | partial | separates Repository; UI/Compose-Port, Runtime-/Trust-/Permission-Entscheidungen offen |
| Ruflo | not implemented / not evidenced | keine Main-Runtime-Verknüpfung gefunden |
| ECC | not implemented / not evidenced | keine Main-Runtime-Verknüpfung gefunden |
| Agency Agents | not implemented / not evidenced | keine Main-Runtime-Verknüpfung gefunden |
| OpenClaw | not implemented / not evidenced | keine Main-Runtime-Verknüpfung gefunden |
| LM Studio | not implemented / not evidenced | kein spezifischer aktiver Aufruf-/Konfigurationspfad gefunden |
| `LLMServerClient` | partial / unused in inspected call graph | Modul vorhanden; kein Aufrufknoten im geprüften Python-Quellbaum |

## Technische Notizen

- [Entrypoints, Dienste und Audio-Grenzen](ENTRYPOINTS.md)
- [Persistenz und Datenbereiche](STORAGE.md)
- [Beobachtung, Cloud-Beratung und Privacy-Gates](OBSERVATION_AND_PRIVACY.md)
- [Tools, Skills und MCP](../07_TOOLS_MCP_SKILLS.md)
- [School und Mobility](../08_SCHOOL_MOBILITY.md)
