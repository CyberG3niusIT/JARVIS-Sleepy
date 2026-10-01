# Agents und Orchestrierung

## Interne Aufgabenorchestrierung

`TaskPlanner` in `core/task_planner.py` zerlegt zusammengesetzte Aufgaben, verwaltet Plan-/Step-Status, Unterbrechung, Pause/Resume, Bestätigung und Ausführung; er ist über Pipeline/Console/Web eingebunden. `ConversationRouter` koordiniert direkte Fähigkeiten, Skills, Tools und LLM-Routen.

`ObservationCollector` erkennt Muster aus Event-Daten und kann Findings speichern. Web initialisiert ihn, wenn der EventLogger existiert; API-Endpunkte können Sammlung und Beratung anstoßen. `self_evolution.auto_consult` steht in der geprüften YAML auf `true`, wodurch Findings an Claude zur Analyse gesendet werden können. Das ist ein externer Datenfluss und ein Privacy-relevanter Configpfad. Ein Kommentar im Web-Code widerspricht dem Configwert; für das Flag ist die geladene Konfiguration maßgeblich. Laufzeitstatus und Cloud-Aufruf wurden nicht geprüft.

## Skills, Tools und MCP

Skills sind lokale Code-/Metadatenpakete. Tools werden durch `ToolRegistry` verwaltet. `MCPBridge` kapselt MCP-Client-Aufgaben. Das ist von autonomen Agent-Frameworks zu unterscheiden: ein Tool oder Skill ist nicht automatisch ein Subagent.

## Externe Frameworks

| System | Status in Main | Aussage |
|---|---|---|
| Ruflo | external / not integrated | kein aktiver Runtime-Import/-Dienst belegt |
| ECC | external / not integrated | keine Projektintegration belegt |
| Agency Agents | external / not integrated | keine Projektintegration belegt |
| OpenClaw | not evidenced | im geprüften Code/Config nicht als Runtime gebunden |
| Subagents | not evidenced in product runtime | keine produktive Agent-Dispatch-Schicht festgestellt |

Für diese fünf Systeme wurde im aktiven `Main`-Quellpfad keine implementierte JARVIS-Integration festgestellt. Daraus lässt sich auch kein Projektstatus `planned` ableiten. Sie werden als nicht integriert dokumentiert, nicht als fertige oder laufende Agentenfähigkeit.

Der Nutzer-Arbeitsplatz kann solche Werkzeuge außerhalb des JARVIS-Projekts besitzen. Das begründet keine Systemarchitekturbehauptung.

## Expert-Delegation (Stand 25.09.2026)

Evidenz: nur Unit-/Integrationstests mit Fakes (`test_expert_delegation.py`, `test_expert_handover_integration.py`); nicht auf Hardware getestet. Modell-/Handover-Hintergrund in [03](03_RUNTIME_AND_MODELS.md).

- Tool `delegate_to_expert`; Entscheidung in `core/expert_policy.py`.
- Eskalation **nur** bei: ausdrücklicher Anfrage, strukturiertem Hochkomplexitäts-Signal, fehlgeschlagener harter Verifikation oder unzuverlässigem Tool-Ergebnis. **Keine** Domänen-Heuristiken.
- Die Qwen-Antwort geht direkt an TTS unter JARVIS-Kontext, wird im Konversationsstatus gespeichert; Gemma wird im Hintergrund wiederhergestellt.
- Anfragen während Gemma `STARTING` warten/queuen ehrlich; ein Fallback greift nur, wenn er wirklich konfiguriert ist.
- Qwen-Ladezeit ca. 90-100 s ist für den Nutzer spürbar (nicht optimiert).
