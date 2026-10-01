# Tools, MCP und Skills

## Skills

`core/skill_manager.py` lädt lokale Skill-Pakete aus `skills/`. Im Checkout vorhanden sind unter anderem System-, Personal-, School- und Mobility-Skills. Discovery/Safe-Mode-Werte stehen in `config.yaml`; ein Lockdown oder menschliches Freigabeverhalten ist nicht aus dem Statusflag abzuleiten.

## Tools

`core/tool_registry.py`, `core/tool_executor.py`, `core/tool_gate.py` und `core/tools/` bilden Registrierung, Ausführung und Schutzpfade. `tools/` enthält separate Dienste/Utilities. Fähigkeiten, die ein externes Binary, Netzwerk oder Freigabe benötigen, sind nur unter diesen Voraussetzungen nutzbar.

Die Registry scannt Python-Toolmodule und erwartet Name, Schema und Prompt-Regel; Handler, Skill-Gating und immer verfügbare Tools werden getrennt registriert. MCP-Werkzeuge können dynamisch ergänzt werden. Ein Registry-Eintrag bestätigt weder sichere Konfiguration noch externe Erreichbarkeit.

Die Registry scannt Python-Toolmodule automatisch und erwartet Name, Schema und Prompt-Regel; Handler, Skill-Gating und immer verfügbare Tools werden getrennt registriert. MCP-Werkzeuge können zur Laufzeit ergänzt werden. Ein Registry-Eintrag bestätigt nicht, dass ein externer Handler sicher konfiguriert oder erreichbar ist.

## Sprachvertrag für Tools und Skills

Es gilt die [zentrale Sprachinvariante](01_ARCHITECTURE.md#verbindliche-owner-sprache). JARVIS-eigene Skill-, Tool-, MCP-, Kalender-, Reminder- und Planner-Rahmenantworten sowie Fehler und Bestätigungen werden deutsch formuliert. Externe Toolresultate und genaue Zitate dürfen ihre Originalsprache behalten; Toolnamen, Schemas und Statuscodes werden nicht übersetzt.

Chat und Tool-Continuation verwenden `persona.OWNER_LANGUAGE_RULE`; vorhandene englische technische Prompt-/Schemaanteile heben diese übergeordnete Regel nicht auf. Bekannte MCP-/Toolfehler werden als feste deutsche Rückmeldung ausgegeben. Fehler-, Sperr- und Bestätigungspräfixe werden von den bestehenden Verbrauchern sowohl in deutscher als auch bisheriger englischer Form erkannt, damit transiente Ergebnisse nicht als erfolgreiche Ergebnisse gecacht werden. Bestätigungs- und Privacy-Prüfungen werden dadurch nicht umgangen.

## MCP

`core/mcp_client.py` enthält die Client-Bridge und `.mcp.json` liegt im Projekt. Serverinventar, erreichbare Sessions und Credentials werden hier nicht wiedergegeben; diese Werte müssen lokal vertraulich geprüft werden.

In der geprüften `config.yaml` ist der `mcp_servers`-Block auskommentiert. Console und Voice starten die Bridge nur bei nichtleerer geladener Serverzuordnung. `.mcp.json` ist nicht gleichbedeutend mit dieser Runtime-Konfiguration; seine Werte werden nicht gespiegelt.

Die Bridge verbindet konfigurierte MCP-Server als Subprozesse, führt einen asyncio-Loop im Hintergrund, entdeckt deren Tools und bindet Handler in den synchronen JARVIS-Toolpfad ein. Timeouts und begrenzte Reconnect-Versuche sind implementiert. Kein Server wurde während der Dokumentation verbunden.

Die Bridge startet konfigurierte MCP-Server als Subprozesse, führt einen asyncio-Loop im Hintergrund, entdeckt deren Tools und bindet synchrone Handler in den JARVIS-Toolpfad ein. Connect-/Call-Timeouts und begrenzte Reconnect-Versuche sind implementiert. Kein aktiver Server wurde in dieser Dokumentationsrunde verbunden.

## Entwicklung und Agents

Skill-Guides und Änderungen sind in älteren Dokuquellen zu finden. Ruflo, ECC und Agency Agents werden nicht als JARVIS-Runtimekomponenten dokumentiert, da Integration im aktiven Code nicht belegt ist.
