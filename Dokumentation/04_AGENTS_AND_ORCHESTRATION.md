# Agents und Orchestrierung

## Interne Orchestrierung

JARVIS bevorzugt deterministische Routen vor generativer Planung. `ConversationRouter`, Skills und Tools behandeln eindeutige Aufgaben; `TaskPlanner` ist für echte Mehrschrittaufgaben vorgesehen.

`ObservationCollector` analysiert Betriebsereignisse und kann Findings speichern. **Automatische externe Beratung ist aktuell deaktiviert:** `self_evolution.auto_consult: false`.

## Expert-Delegation

Gemma ist PRIMARY. Qwen3.5-35B-A3B ist EXPERT. Eine Expert-Eskalation soll nur erfolgen bei:

- ausdrücklicher Nutzeranforderung,
- strukturiertem Hochkomplexitäts-Signal,
- fehlgeschlagener harter Verifikation,
- oder unzuverlässigem Tool-Ergebnis.

Keine pauschalen Domänen-Heuristiken sollen Qwen laden. Der Expert soll direkt antworten; eine verpflichtende zweite Gemma-Reformulierung ist nicht vorgesehen.

Der Handover ist in der aktuellen Konfiguration deaktiviert. Damit ist die Expert-Delegation ein implementierter, aber noch nicht freigegebener Runtimepfad.

## Skills, Tools und MCP

Skills und Tools sind Fähigkeiten, keine automatisch autonomen Agenten. MCP erweitert den Tool-Pfad um externe, explizit konfigurierte Server. Agenten dürfen keine Rechte über den aufrufenden Kontext hinaus erhalten.

## Externe Entwicklungsagenten

Codex, Claude Code, OpenClaw oder andere Entwicklungswerkzeuge können außerhalb der Produkt-Runtime verwendet werden. Ihre Existenz am Arbeitsplatz ist keine JARVIS-Produktintegration. Projektlokale Claude-/Codex-Dateien dienen Entwicklung/Tooling und dürfen nicht mit Runtime-Providern verwechselt werden.
