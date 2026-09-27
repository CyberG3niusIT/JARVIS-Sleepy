# Komponenten

Status bedeutet Code-Reife im aktuellen Checkout, nicht Betriebsfreigabe.

| Komponente | Status | Quellpfade / Grenzen |
|---|---|---|
| Pipeline und Console | implemented | `core/pipeline.py`, `jarvis_console.py`; reale Audio-Hardware nicht geprüft |
| Webfrontend | partial | `jarvis_web.py`, `web/`; kein aktueller Web-Live-Test |
| ConversationRouter | implemented | `core/conversation_router.py`; Reihenfolge/Integrationen configabhängig |
| TaskPlanner | implemented | `core/task_planner.py`; Testcode vorhanden |
| MemoryManager/ContextWindow | implemented, runtimeabhängig | `core/memory_manager.py`, `core/context_window.py`; keine DB gelesen |
| PeopleManager | implemented, runtimeabhängig | `core/people_manager.py`; Personenbestand extern |
| SkillManager/Skills | implemented | `core/skill_manager.py`, `skills/`; dynamische Discovery konfiguriert |
| ToolRegistry/MCP | partial | `core/tool_registry.py`, `core/mcp_client.py`; externe MCP-Server nicht verifiziert |
| Reminder/Awareness/Observation | implemented/partial | `core/reminder_manager.py`, `core/awareness*`, `core/observation_collector.py`; externe Kalenderdienste abhängig |
| School/Mobility | experimental | uncommittete Module und Tests; Live-Canary offen |
| Voice Directions | experimental | uncommittete Parser-/Pipelineänderungen; subjektive Freigabe fehlt |
| Chatterbox Runtime | configured/partial | Endpunkt und Servercode; Prozessverfügbarkeit unbestätigt |
| Android | partial | separates Repo; echte Sleepy-Verbindung und Permission-/Privacy-Regeln fehlen |

Die Statusbegriffe bedeuten: **implemented** = ausführbarer Codepfad vorhanden; **partial** = Teilfunktion oder Anbindung unvollständig bzw. Livebetrieb unbelegt; **experimental** = neue/nicht abgenommene Arbeit; **planned** = ausdrückliche Planungs-/Entscheidungsevidenz vorhanden; **blocked** = konkrete externe Blockade dokumentiert; **deprecated** = als abgelöst markierter Pfad. Wenn weder Code noch Planung belegt sind, wird „nicht implementiert/nicht belegt“ statt `planned` verwendet. `implemented` bedeutet keine Produktionsabnahme.

ObservationCollector ist code-implementiert. Web initialisiert ihn, falls EventLogger verfügbar ist; der Hintergrundworker wird explizit gestartet. Externe Claude-Beratung ist getrennt und über `self_evolution.auto_consult` konfiguriert. Laufzeitstatus wurde nicht geprüft.

Details je Komponente stehen in [COMPONENTS](COMPONENTS/README.md). Nicht im Code belegte Featurebehauptungen aus älteren Dokumenten sind nicht als aktuelle Fähigkeiten übernommen.
