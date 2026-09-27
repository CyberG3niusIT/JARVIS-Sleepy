# Roadmap

Priorität: Korrektheit > bestehendes schützen > Privacy/Security > reproduzierbare Verifikation > Architektur > Performance.

## Jetzt

1. Voice-Acceptance-Fehler schließen: Turn-Aggregation, Watchdog/TTS, speculative Cancel, orphaned Retry.
2. Pfadlogging mit Turn-ID und explizitem Direct-Audio/Text-Routing ergänzen bzw. verifizieren.
3. Cloud-Fallback-Policy zentralisieren: `llm.primary.text_fallback` muss für alle automatischen Primary-Text-Cloudpfade gelten.
4. Danach Voice-Acceptance-Matrix erneut auf echter Hardware durchführen.

## Danach

5. Expert-Handover real auf Hardware testen und Recovery/Ownership verifizieren; erst dann `handover.enabled` erwägen.
6. NPU-Presence live initialisieren und abnehmen; NPU-Wake separat entwickeln.
7. School/Mobility fachlich end-to-end abnehmen, obwohl VVS-Dienst bereits READY ist.
8. Web-API als klaren Supervisor-/Frontend-Vertrag einordnen oder im Runtime-Snapshot integrieren.
9. Desktop-UI komplett neu auf Basis des aktuellen Backendvertrags und der neuen Designreferenzen aufbauen.
10. Memory-&-Thinking-Visualisierung ausschließlich aus beobachtbaren Pipeline-/Memory-/Routingdaten speisen.

## Später

11. OpenRouter bewusst aktivieren, Modell und Credential setzen und Privacy-/Failure-Verhalten testen.
12. optionale Anthropic-Unterstützung nur bei echtem Bedarf beibehalten.
13. FLUX/NPU/weitere on-demand Komponenten in den Desktop-Control-Hub integrieren.
14. alte Kommentare, Prompts und Legacy-Doku weiter konsolidieren.
