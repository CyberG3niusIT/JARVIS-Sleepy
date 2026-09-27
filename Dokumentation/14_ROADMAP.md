# Roadmap

Dies ist eine Lücken-/Prioritätenliste aus dem geprüften Code- und Statusstand, keine verbindliche Produktplanung.

1. **School/Mobility live abnehmen**: Canary reproduzierbar beenden, Exitcode-1-Ursache klären, reale Feed-Antworten/Timeouts und Stale-/Partial-Fälle nachweisen, DORMANT-Soak erneut mit Version/Telemetrie dokumentieren.
2. **Runtime-Inventar**: Prozess-, Modell-, GPU-, MCP- und externe Dienstzustände mit sicheren Health-Probes erfassen.
3. **Voice Directions**: Parserverhalten, Cache-/Baseline-Isolation und Audiofreigabe getrennt abschließen.
4. **Privacy/Security**: Capability-Gates über Tool-, Skill-, MCP- und Beobachtungspfade auditieren.
5. **Doku-Governance**: ADRs für bestätigte Architekturentscheidungen; klare Besitzer und Aktualisierungsregeln.
6. **Android**: Entscheidungen zu Pairing/Trust, Permissions, Privacy Policy und Runtime-Modell treffen und erst danach echte Bindungen implementieren.
7. **Legacy-Dokumente**: inhaltliche Einzelprüfung und sichere, portable Referenzen auf diesen zentralen Index.

## Nächste Schritte Modell-/Voice-Umbau (25.09.2026)

8. **Hardware-Verifikation**: Gemma-Unit und mmproj-Dateinamen, Port 8082, Unit-Installation; Direct-Audio Ende-zu-Ende; echten Handover mit systemd messen.
9. **Handover härten**: Eigentümer-Prüfungen (FragmentPath/ExecStart/Port-Besitzer) in den Python-Handover; Qwen-Ladezeit (ca. 90-100 s) verkürzen; `/api/gpu-status` von `gpu_swap` lösen.
10. **Direct-Audio**: Memory-/Awareness-Kontext für spekulative Turns; Tool-Auswahl statt ALL_TOOLS; STT-Rauschfilter; Quality-Gate-Fallback mit Audio; Fragmente <= 1.6 s aggregieren.
11. **NPU**: Live-Kamera auf NPU, NPU-Wake-Word (danach STT aus dem Wake-Normalpfad entfernen), Identitätsschwelle kalibrieren, MOTION-Event, CLOUD_LLM-Gate im Vision-Gate.
12. VRAM-Messung Gemma 12B + Chatterbox parallel.
