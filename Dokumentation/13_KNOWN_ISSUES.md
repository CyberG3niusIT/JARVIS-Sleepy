# Bekannte Probleme und Widersprüche

- Großes uncommittetes Arbeitsset: HEAD allein beschreibt nicht den tatsächlichen dokumentierten Implementierungsstand.
- Ältere README/Projektübersicht/Architekturtexte nennen widersprüchliche Hardware, Modelle, Stimme, Laufzeitstatus und Produktionsreife.
- `config.yaml` enthält aktive Auswahlwerte, aber kein Runtime-Protokoll; aktive Dienste sind nicht verifiziert.
- Der vorgesehene VVS-Endpunkt ist Port 8088; die JARVIS-Webkonfiguration hat ebenfalls `web.port: 8088` als Default. Wenn beide Dienste denselben Loopback-Namespace teilen, kollidiert der Bind-Port. Tatsächliche Prozess-/Namespace-Topologie und Overrides sind offen.
- `mobility.base_url` wird per Environment gesetzt; im geprüften Configfile ist die tatsächliche URL nicht angegeben. Die gegebene VVS-Adresse ist ein Einsatzwert, nicht aus der Config verifizierter Livezustand.
- School/Mobility hat Implementierungs- und Testartefakte, jedoch offene Live-Abnahme und fehlgeschlagen/unvollständigen Canary laut Auftraggeberstatus.
- Chatterbox/RoCM-GPU-Validierung ist historisch durch fehlendes WSL-Passthrough blockiert gewesen; aktueller Status unbekannt.
- Android besitzt UI und Schnittstellen, aber Pairing, Privacy-Regeln, Permissions und reale Runtime-Anbindung sind offene Architekturentscheidungen.
- Ruflo, ECC, Agency Agents, OpenClaw und LM Studio sind nicht als aktive Main-Runtime belegt.
- `self_evolution.auto_consult` ist in `config.yaml` aktiviert, während ein Kommentar im Web-Einstieg Auto-Consult als standardmäßig aus bezeichnet. Die Collector-Implementierung liest das Config-Flag; dieser Widerspruch ist wichtig für Cloud-/Privacy-Prüfung.
- `LLMRouter` nutzt einen fest codierten lokalen Chat-Completions-Endpunkt; ein separater `LLMServerClient` ist vorhanden, aber im Python-Quellbaum ohne sichtbaren Konstruktor-Aufruf. Die konfigurierten CLI-Pfade belegen nicht den aktiven Routertransport.
- Der aktive `mcp_servers`-Configblock ist auskommentiert; MCP-Bridge-Code vorhanden, aber kein aktiver Runtime-Server konfiguriert belegt.
- Ein zentrales ADR-Verzeichnis mit beschlossenen, versionsgebundenen Architekturentscheidungen war in den überprüften Git-Dateien nicht vorhanden.
- Zentrales Doku-Verzeichnis liegt außerhalb der drei Projekt-Git-Roots; Änderungen dort werden nicht von Git versioniert.

## Offene Punkte Modell-/Voice-Umbau (25.09.2026)

- Gemma-Unit und mmproj-Dateinamen sowie Port 8082 in den neuen Unit-Vorlagen sind Platzhalter (NEEDS HW VERIFY); Nutzer muss Units installieren.
- Direct-Audio-Integration von JARVIS nicht auf Hardware getestet (das llama.cpp-`input_audio`-Schema lief in einem früheren manuellen Test des Nutzers).
- GPU-Handover nur mit Fake-`systemctl` getestet; Eigentümer-Prüfungen (FragmentPath/ExecStart/Port-Besitzer) nur in `start.sh`, nicht im Python-Handover.
- `core/gpu_swap.py` stale (System-Scope-sudo, nur FLUX); `/api/gpu-status` hängt noch daran.
- Qwen-Ladezeit ca. 90-100 s, nicht optimiert.
- VRAM Gemma 12B + Chatterbox parallel unverifiziert.
- Spekulative Wake-Turns ohne Memory-/Awareness-Kontext (nur History).
- Direct-Audio-Turns bieten alle Tools an (`llm.primary.audio_tools: always`); kein STT-Rauschfilter im Konversationsfenster; Quality-Gate-Fallback ruft `llm.chat` ohne Audio auf; gespeicherter Nutzertext ist Platzhalter `[Sprachnachricht aN]`.
- Kurze Fragmente <= 1.6 s, die einen Turn eröffnen, werden nicht aggregiert.
- NPU: Live-Kamera auf NPU und NPU-Wake-Word NOT_IMPLEMENTED; Identitätsschwelle nicht kalibriert; MOTION-Event wird noch nicht emittiert.
- Vision-Gate: CLOUD_LLM-Gate für Cloud-Route noch nicht verdrahtet.
