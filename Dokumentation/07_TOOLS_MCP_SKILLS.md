# Tools, MCP und Skills

## Prinzip

Eindeutige Aufgaben werden deterministisch vor generativ gelöst. Skills und Tools sollen vorhandene Architektur wiederverwenden; ein neuer Pfad darf keine zweite Zuständigkeit erzeugen.

## Skills

`core/skill_manager.py` lädt lokale Skill-Pakete aus `skills/`. School/Mobility und Systemfähigkeiten sind Teil dieser Schicht. Ein geladener Skill ist noch kein Nachweis, dass alle externen Abhängigkeiten verfügbar sind.

## Tools

`core/tool_registry.py`, `core/tool_executor.py`, `core/tool_gate.py` und `core/tools/` bilden Registrierung, Schema, Ausführung und Schutzpfade. Toolrechte bleiben durch Privacy-/Governance-/Capability-Gates begrenzt.

Im Voice-Design werden Tool-Schemas derzeit nicht direkt an Gemma-Direct-Audio gehängt. Der parallele STT-/Textpfad erkennt Tool-/Skill-Turns und nutzt dann den etablierten deterministischen Pfad.

## MCP

`core/mcp_client.py` ist die Bridge zu explizit konfigurierten MCP-Servern. Externe MCP-Server, Sessions und Credentials sind Runtimekonfiguration und werden nicht aus Projektdateien als aktiv angenommen. `.mcp.json` ist nicht automatisch gleichbedeutend mit produktiver Runtime-Aktivierung.

## Agents

Tools und Skills sind keine autonomen Agenten. Mehrschritt-Agenten erhalten begrenztes Ziel, Kontext, Rechte, Budget, Timeout und Abbruchbedingungen. Sie dürfen Governance, Privacy oder Tool-Gates nicht umgehen.
