# JARVIS WEB SEARCH LIVE RECOVERY
# FINAL ACCEPTANCE REPORT

Stand: 30.09.2026, fortgeschrieben nach ausdrücklicher Owner-Freigabe für Lifecycle-Fix und Live-Abnahme. Der ursprüngliche Abbruch um 22:16 CEST bleibt als historischer Befund erhalten; die folgende Prüfung wurde anschließend autorisiert fortgesetzt.

## A. CLAUDE.md Compliance

Root-CLAUDE.md, Main/CLAUDE.md und Main/AGENTS.md wurden zu Beginn vollständig erneut gelesen. Deutsche Ausgabe, Main als Source of Truth, Erhalt des schmutzigen Worktrees, Privacy-Gates und gezielte WSL-Tests eingehalten. Keine Änderungen an .env, config.yaml, systemd-Units, Firewall oder Windows-Umgebung. Keine Git-Mutationen.

## B. Agent / Skill Execution

Skills: runtime-status, run-targeted-tests-wsl, runtime-restart und review-voice-integration. Der Auftrag autorisierte den notwendigen Reload ausdrücklich; die Skill-Rückfrage wurde deshalb nicht erneut gestellt. Später ausdrückliche zusätzliche Freigabe des Owners für Lifecycle-Fix und Live-Abnahme. Ausschließlich offizielle Control Plane verwendet.

Die begrenzten Agentenaufgaben wurden auf bestehende Agenten verteilt:

| Subagent | Scope | Result / Findings |
|---|---|---|
| dependencies_ports | Provider, Ergebnisvertrag, Provider-/Transportloggrenze, Vertragstests | 44 Vertragstests und 10 Planner-Cancellation-Tests PASS; malformed Outcomes und spätere Child-Logger abgesichert |
| desktop_audit | Dependency-Vertrag/Umgebung und unabhängiger Provider-Security-Review | ddgs-Pin begründet; API/Lizenz/Metadaten geprüft; Logscope-/Childhandler-/Fetch-Befunde erkannt und anschließend behoben |
| supervisor_audit | Caller-/Privacy-Tests und unabhängiger Python-/Security-Review | 71 Tests PASS; fehlende datenbasierte Synthese, falscher Erfolg, Plannerstatus und Dokumenterstellung abgesichert; erfolgreicher Web-Fallback-NameError gefunden und behoben |

Fortsetzung: dependencies_ports implementierte unterbrechbare Pollpausen und 15 echte Threadtests. desktop_audit implementierte Stop-Truthfulness samt Shell-Regressionsmatrix (85er Lauf PASS, ergänzender 12er Lauf PASS) und prüfte die verzögerte Desktop-Initialisierung lesend. supervisor_audit ergänzte vier Shutdown-Verhaltenstests und den unabhängigen Voice-/Privacy-/Handover-Review. Keine blockierenden Befunde im geprüften finalen Diff; laufende Operations- und Timergrenzen ausdrücklich erhalten.

Root prüfte Source, Reviews, gemeinsame Tests, offizielle Runtime und echten systemd-Abschluss selbst. Keine parallelen Edits derselben Dateien.

## C. Git Baseline

Branch: integration/desktop-backend-20260929.

HEAD vor und nach Arbeit: 68da00ce056ee9bad9a41918c0a35c97002ef722.

Git status, worktree list und diff --check wurden vor Änderungen geprüft. Bestehende Phase-2-/Phase-3-/Capability-Arbeit blieb erhalten. Abschließendes diff --check PASS, lediglich bekannte CRLF-Hinweise. Kein Commit, Push, Checkout, Reset, Stash oder sonstige Git-Mutation.

## D. Root Cause

**Dependency [Sicher]:** Der echte DDG-Pfad importiert ddgs.DDGS; in /home/alex/jarvis-venv fehlte ddgs. duckduckgo_search 8.1.1 war installiert. Die Runtime-Anforderungen deklarierten zuvor keines der beiden Pakete. Der initiale öffentliche Source-Stand verwendete bereits ddgs; eine frühere JARVIS-Paketmigration wurde nicht belegt.

**False Success [Sicher]:** Der Providerfehler wurde bisher in eine leere Liste umgewandelt. Die Caller emittierten danach einen erfolgreichen Toolabschluss unabhängig von tatsächlicher Provider-Ausführung und gültigen Ergebnissen.

**Unsupported Current-Fact Synthesis [Sicher]:** Die leere Liste wurde trotzdem an die LLM-Continuation weitergegeben. Der gelieferte echte Voice-Auszug dokumentiert Importfehler, null Treffer und anschließend eine aktuelle Wetterbehauptung. Query, Ort und Antwortinhalt werden hier nicht wiederholt.

**Invalid Date Query [Sicher / Ursache unverifiziert]:** Die Toolquery enthielt ein unmögliches Kalenderdatum. Sichtbar ist es im LLM-Toolargument; der verfügbare STT-Metadatenbeleg enthält den ursprünglichen Text nicht. Ob User-Eingabe oder LLM das Datum erzeugte, ist nicht festgestellt. Keine Date-/Time-Nebenreparatur vorgenommen.

## E. Dependency Decision

Current installed: duckduckgo_search 8.1.1 und jetzt ddgs 9.16.0.

Code expected / chosen contract: ddgs==9.16.0, ausschließlich in requirements.txt als bestehender Runtime-Manifestdatei deklariert. pyproject.toml dient hier Tooling; keine Duplikation in CI-Manifesten.

Die offiziellen Paket-/Repository-Quellen bestätigen MIT, Python >=3.10 und kompatiblen DDGS-Kontextmanager sowie text(query, max_results, backend="duckduckgo"). Die historischen duckduckgo_search-Metadaten nennen die Umbenennung; dessen installierte Version hardcodiert Bing. Retargeting auf das alte Paket wurde deshalb verworfen. DDGS wird auf den vorhandenen DuckDuckGo-Pfad begrenzt.

Bestehende Abhängigkeiten click 8.5.0, primp 2.0.1 und lxml 6.1.3 erfüllen die geprüften Anforderungen. Pip-Dry-Run mit und ohne Abhängigkeitsauflösung: ausschließlich ddgs-9.16.0 wäre neu. Geprüfter Wheel-SHA256: 175d9198c958a263f51a06a54368ba0b41294942c0cd29f4aa71be03dbcd5f4a.

Nach expliziter Owner-Freigabe wurde ausschließlich `pip install --no-deps ddgs==9.16.0` mit der echten jarvis-venv ausgeführt. Import und installierte Version verifiziert; `pip check`: No broken requirements found. Keine anderen Pakete aktualisiert.

Primärquellen: [PyPI ddgs](https://pypi.org/project/ddgs/), [Versionmetadaten](https://pypi.org/pypi/ddgs/9.16.0/json), [DDGS Source v9.16.0](https://github.com/deedy5/ddgs/tree/v9.16.0), [historisches Paket](https://pypi.org/project/duckduckgo-search/).

## F. Changes

| Datei | Änderung |
|---|---|
| requirements.txt | Eindeutiger Runtime-Pin ddgs==9.16.0 |
| core/web_research.py | SearchOutcome, Provider-/Dependency-/Timeout-/Empty-Unterscheidung, Validierung, per-call Backend, fehlertolerante Caller-Grenze, sensible Provider- und auf Search/Fetch begrenzte Transportlogs |
| core/pipeline.py | Wahrheitsgemäße Toolstatus; ohne Daten feste deutsche Antwort vor Cache/Synthese/LLM-Fallback; alte Suchzustände gelöscht; ungegatete Toolargumentlogs entfernt |
| jarvis_web.py | Gleiche Regeln für WS und nichtstreamenden Fallback; kein parametrischer Chat-Fallback bei fehlenden Suchdaten; zwei ungebundene Synthese-Kwargs im erfolgreichen Fallback entfernt |
| core/task_planner.py | Ohne Researchdaten leerer Fehlerausgang, dadurch FAILED und abhängige Schritte SKIPPED; kein Ersatz durch parametrisches Wissen |
| skills/system/file_editor/skill.py | Ohne erforderliche Researchdaten keine Dokumentgenerierung; keine ungegateten Topic-/Fehlerinhalte |
| tests/unit/test_web_search_contract.py | Neue Provider-/Vertrags-/Logtests |
| tests/unit/test_web_search_failure_paths.py | Neue Caller-/Synthese-/Fail-Honest-Tests |
| tests/unit/test_web_search_persistence_privacy.py | Fakes auf neuen Vertrag angepasst; Gate-/Writer-Erwartungen erhalten |

Config und Units unverändert. Keine neue Engine, Cloud-Abhängigkeit, Router- oder Memory-Architektur.

Zusätzlich autorisierter Lifecycle-Scope:

- stop.sh bestätigt einen sauberen Stop nur nach erfolgreicher Prüfung von ActiveState=inactive, Result=success und MainPID=0. Fehlgeschlagene/fehlende Prüfungen und Timeout erzeugen ERROR; restart.sh startet danach nicht weiter.
- core/news_manager.py, core/weather_poller.py, core/reminder_manager.py und core/presence_detector.py verwenden Stop-Events für ruhende Pollpausen und Startverzögerungen. Laufende Operations-Timeouts und TTS-Pausen bleiben erhalten.
- core/continuous_listener.py weckt den Device-Monitor über ein Stop-Event und protokolliert technische Audio-Stop-/Close-Marker.
- jarvis_continuous.py hält den Startup-Health-Timer, daemonisiert und cancelt ihn vor Cleanup. Reminder-Starttimer ebenfalls abbrechbar und gegen späte Ankündigungen geschützt.
- tests/unit/test_runtime_lifecycle_shell.py erweitert; test_poller_shutdown.py und test_voice_shutdown_lifecycle.py neu.

## G. Tests

Gezielte kombinierte Regression: **376 passed**, 243 Warnings, 30.44s. Nach dem anschließenden kleinen Fetch-Logscope-Fix wurden alle drei Search-Testdateien erneut gemeinsam ausgeführt: **115 passed**, 7.21s. Zusätzlich Agentlauf Contract + Planner-Cancellation: **54 passed**, 1.16s. Ergebnisse verschiedener Läufe werden nicht zu einer scheinbaren Gesamtzahl addiert.

Kombinierte Regression umfasste web_search_contract, web_search_failure_paths, web_search_persistence_privacy, tool_calling, llm_router_hardening, voice_routing_hardening, jarvis_web_app, jarvis_web_desktop_mode, privacy_gate, privacy_memory_integration, privacy_conversation_persistence, content_logging_privacy_gate, tool_registry_audit_privacy, skill_audit_logging, active_voice_event_telemetry, memory_read_only, task_planner_cancellation und single_user_voice_session.

Ausgeführt in Ubuntu-24.04 mit /home/alex/jarvis-venv/bin/python3, PYTHONDONTWRITEBYTECODE=1, -p no:cacheprovider. Keine echten Providerrequests in Unit Tests. Keine Tests gelockert. Finale Searchläufe ohne Fehler/Skips. Keine blinde Vollsuite.

A-H abgedeckt: Treffer, fehlende Dependency, Providerexception, echte erfolgreiche Leersuche, Timeout, False-Success-Verhinderung, keine datenlose Current-Fact-Synthese und DENY-Persistenz. Ergänzend malformed Ergebnisse, spätere eigene Loggerhandler, erhaltene RecordFactory, HTTP-Diagnostik nach Such-/Fetch-Abschluss, Plannerstatus und unterbundene Dokumenterstellung.

Beim ursprünglichen Abbruch noch nicht ausgeführt: produktive Netzwerksuche, produktive LLM-Synthese nach Reload, neuer Voice-Search-Turn. Grund damals: §20 Stop-Timeout. Die folgenden Nachweise ersetzen diese historische Lücke nach expliziter Freigabe.

Fortsetzung nach Freigabe: Kombinierte Lifecycle-/Voice-/Privacy-/Search-Regression **433 passed, 1 skipped**, 98.91s. Skip ist der bestehende optionale NPU-Hardwaretest. Umfasst zusätzlich voice_shutdown_lifecycle, poller_shutdown, runtime_lifecycle_shell, runtime_status, stop_fastpath_integration, turn_assembler, voice_barge_in, privacy_audio_reset und presence_npu_backend sowie die drei Search-Dateien. Unabhängiger Review ohne verbleibenden blockierenden Diff-Befund. Produktive Provider-/Continuation-Prüfungen und Owner-Voice-Test jetzt tatsächlich ausgeführt, siehe J und L.

## H. Privacy Regression

CONTENT_LOGGING: **PASS (gezielte Tests / Source)**.

MEMORY_WRITE: **PASS (gezielte Tests / Source)**.

Sensitive error logging: **PASS (gezielte Tests / Source)**.

Technische Status, Backend, Trefferzahl und Fehlerklasse dürfen diagnostiziert werden; Exceptiontext, Query, URLs, Snippets und Antwortinhalte werden nicht neu ungegatet ausgegeben. Provider-Logger werden quellseitig geschützt, auch für spätere Child-Logger mit eigenen Handlern. HTTP-Transportlogs sind im aktuellen Thread nur während Search/Fetch unterdrückt; unabhängige HTTP-Diagnostik bleibt verfügbar. Bestehende RecordFactory und Handler/Levels/Propagation werden erhalten.

Reale temporäre SQLite-DENY-Tests belegen keine Suchinhalts-Persistenz in geprüften Callern. Dies ist keine vollständige produktive Phase-3-Live-Security-Abnahme.

## I. Runtime Reload

Vor Reload: offizielles getRuntime **READY**, 20:15:19Z. Voice, Primary, STT, Chatterbox, Audio Bridge, Desktop API und VVS READY.

Gewählt: ausschließlich offizieller kontrollierter Stop, dann erst Prüfung vor einem möglichen Start. Der geprüfte direkte restart.sh-Pfad ruft stop.sh und danach start.sh auf; stop.sh überprüft nach Stop nur is-active, nicht Result=timeout. Er könnte deshalb trotz Timeout weiter starten. Dieser Lifecycle-Befund wurde nicht repariert.

Ausgeführt: JARVIS-Runtime.ps1 -Action stop -Wait.

Aktueller Journalbeleg:

- 22:15:40 CEST Desktop-Stop begonnen; 22:15:49 sauber beendet.
- 22:15:49 Voice-Stop begonnen.
- 22:16:00 Continuous Listener beginnt Stop.
- 22:16:09 systemd stop-sigterm timed out; SIGKILL durch systemd.
- 22:16:10 Hauptprozess status=9/KILL, Result=timeout.

Historical stop-timeout triggered: **YES, Voice**. Desktop diesmal sauber.

Control Plane meldete accepted=true und abgeschlossenen Stop; die echte systemd-/Runtime-Prüfung widerspricht einem sauberen Abschluss. Voice ActiveState=failed, SubState=failed, MainPID=0, Result=timeout, ExecMainStatus=9. Desktop inactive/dead, Result=success, MainPID=0.

An diesem Punkt gemäß §20 angehalten. Anschließend hob der Owner die Grenze ausdrücklich auf und autorisierte gezielte Lifecycle-Reparatur, Installation, offiziellen Start und Live-Abnahme.

Diagnostischer Lauf nach Freigabe: erster offizieller Start, dann sauberer Stop 22:26:52 bis 22:27:07 CEST. Die Marker belegen: Audio stream.stop und close kehrten in derselben Sekunde zurück. Der native Audio-Abschluss wurde deshalb nicht als bewiesene Ursache geändert. Serien von ruhenden Poller-/Monitor-Wartezeiten sind durch Source und echte Threadtests belegt; der vorherige konkrete Stack beim SIGKILL bleibt unbekannt.

Nach Lifecycle-Fix und 433er Regression offizieller Start und Stop: 22:38:40 CEST Desktop sauber gestoppt, Voice-Cleanup in derselben Sekunde abgeschlossen; systemd bestätigt Voice-Stop 22:38:46. Beide Units inactive, Result=success, MainPID=0, ExecMainStatus=0. Kein Stop-Timeout, kein systemd-SIGKILL in diesem geprüften Zyklus. Anschließend offizieller Start zur finalen Abnahme ausgelöst.

Keine Unit-Timeouts verlängert, kein reset-failed/manueller Prozesskill. Stop-Truthfulness und beobachteter Cleanup verbessert; dies garantiert nicht die Laufzeit aller denkbaren in-flight HTTP-/Hardwareoperationen.

Finaler offizieller Start abgeschlossen. Zunächst Desktop nach 90s noch STARTING, später tatsächlicher Listener und HTTP-Readiness bestätigt. PID31700 arbeitete währenddessen aktiv mit hoher nativer CPU-Last, kein Restart/Stillstand behauptet. Exakte Verzögerungsursache nicht per Stack festgestellt. getRuntime 20:48:34Z: alle geforderten Komponenten READY, keine degradedReasons. Desktop /api/stats und /api/desktop/snapshot jeweils HTTP200 mit gültigem JSON-Objekt.

## J. Live Search

Provider: **LIVE PASS**, ddg über real installiertes ddgs 9.16.0. Öffentliche Query zur offiziellen Python-Dokumentation über List Comprehensions; mehrere echte Aufrufe lieferten jeweils drei gültige Treffer, darunter docs.python.org. Keine Importexception, SearchOutcome success, error_type=None.

Synthesis grounded: **YES für echte lokale Gemma-Tool-Continuation**. Realer WebResearcher und tatsächliche LLMRouter.continue_after_tool_call erhielten formatierte echte Suchresultate und lieferten eine nichtleere deutsche Erklärung, ein korrektes Listenbeispiel und die offizielle Dokumentationsquelle. Public-only Probe in separatem Prozess ohne Gesprächshistorie; Cloudprovider ausschließlich im Prozess deaktiviert, keine Configdatei verändert. Keine Fake-Provider/Modelle. Dies ist Provider + lokale Synthese, noch kein Mikrofon-E2E.

Separater echter Befund: Der nichtstreamende _do_web_search/LLMRouter.chat-Aufruf erhielt ebenfalls die echten Suchdaten, lieferte in der Probe aber eine leere Antwort. Kein unbelegter Fakt wurde generiert. Die streamende Tool-Continuation funktionierte. Ursache der nichtstreamenden Leerantwort nicht abschließend geprüft; keine globale LLM-/Router-Nebenreparatur vorgenommen.

## K. Failure Semantics

| Outcome | Toolstatus | Verhalten ohne Daten |
|---|---|---|
| success mit validen Ergebnissen | success | Ergebnisse dürfen an Synthese gehen |
| technisch erfolgreiche echte Leersuche | empty | Feste Antwort, keine Continuation |
| provider_unavailable | error | Feste Abruf-Fehlermeldung |
| dependency_missing | error | Feste Abruf-Fehlermeldung |
| error | error | Feste Abruf-Fehlermeldung |
| timeout | error | Feste Abruf-Fehlermeldung |
| invalid_query | blocked | Feste Bitte um gültige öffentliche Suche |

DDGSException("No results found.") allein beweist keine erfolgreiche Leersuche, weil DDGS auch unbrauchbare Transportantworten so abbildet; deshalb unavailable. Nur ein tatsächlich erfolgreich zurückgegebenes [] ist empty. Nichtleere vollständig unbrauchbare Ergebnisse sind InvalidSearchResults. Failure-Outcomes enthalten keine alten Suchdaten.

Sicherer echter Failure-Test nach Freigabe: leere Query über echten run_search/WebResearcher liefert invalid_query und feste deutsche Bitte um gültige öffentliche Suche, ohne Providerrequest. Provider-/Dependency-/Timeoutfehler bleiben durch kontrollierte Tests nachgewiesen; Dependencies nicht absichtlich entfernt.

## L. Voice Search E2E

Vor Fix real belegt: Wake und STT 21:35:00 CEST, Suchaufruf und Importfehler 21:35:13, datenlose LLM-Antwort, Chatterbox Windows TTS completed 21:35:27 (8.53s), Listener danach resumed. Owner bestätigte hörbare Sprache. Der gelieferte Terminalauszug belegt den vorhandenen akustischen Pfad und gleichzeitig den ursprünglichen Searchfehler.

Nach Fix: Neuer realer Voice-Turn von PID31424 nach finalem offiziellen Start. Belege aus aktuellem Journal, EventDB und neuem Owner-Terminalauszug:

- STT 22:42:59 CEST, 97 Zeichen; Wake 22:43:01.
- Toolaufruf 22:43:16, DDG-Ergebnis 22:43:17: fünf gültige Treffer.
- Echter EventDB-Eintrag 20:43:17.297310Z: tool_completed, stage=web_search, status=success, search_status=success, results_count=5, backend=ddg, error_type=null. Nur diese technischen Felder lesend ausgegeben.
- Vollseitenabruf 0/5 wegen Fetch-Timeout; Synthese erhielt die vorhandenen Suchsnippets.
- Chatterbox erster Audiochunk 22:44:03; Abschluss 22:44:43: 19.0s Audio über zwei Chunks. LLM-Antwort abgeschlossen, Gesamtlatenz 109.301s.
- Owner ausdrücklich: **Ja, verständlich gehört**. Dies ist die neue Hörbestätigung, nicht die frühere Abnahme vor Search-Fix.

**Technischer Search-Voice-E2E: belegt. Semantische/zeitliche Abnahme: eingeschränkt.** Das LLM-Toolargument suchte nach Listenvergleich, und die Antwort erläuterte Listenvergleich statt der gewünschten List Comprehensions. Der rohe ursprüngliche STT-Text ist in diesem Metadatenauszug nicht vorhanden; Ursprung der Themenverschiebung zwischen STT und Toolargument bleibt unverifiziert. Kein großer STT-/Prompt-/Routingumbau vorgenommen.

Danach meldete der Watchdog 22:44:53 einen seit122s hängenden Command-Zustand und setzte IDLE, obwohl die gestreamte Antwort kurz vorher beendet war. Das ist ein realer weiterer State-/Latenzbefund, kein Import- oder Search-Ausfall. Ob noch ausstehender Cleanup oder ein veralteter Command-Zustand den Eingriff auslöste, ist nicht abschließend festgestellt. TTS- und nichtstreamende Leerantwort-/Timeout-Marker in anschließenden Hintergrundaufgaben bleiben getrennt. Die menschliche Hörbestätigung beweist verständliche Ausgabe, nicht die korrekte Interpretation des Suchthemas.

## M. Final Runtime

Historischer Abbruchzustand 20:16:25Z und20:19:14Z: ERROR. Dieser wurde nach Owner-Freigabe durch die offizielle Wiederinbetriebnahme ersetzt.

Finale Prüfung 20:52:05Z bestätigt erneut **Overall READY**, degradedReasons=[]; abschließendes diff --check PASS und HEAD unverändert.

Voice: READY, PID31424.

Desktop API: READY, PID31700, beide geprüften Endpunkte HTTP200.

Primary: READY.

STT: READY, tatsächliche neue Transkription belegt.

Chatterbox: READY.

Audio Bridge und VVS: READY. Expert/FLUX/NPU STOPPED; Standard Web API8091 OFFLINE wie im Desktop-Betriebsmodus zuvor. Kein globales Runtime-PASS als Ersatz für die einzelnen Funktionsbefunde verwendet.

## N. Remaining Findings

1. Historischer konkreter Shutdown-Stack unbekannt. Belegte idle-Wartezeiten und falsche Stop-Erfolgsmeldung behoben; aktueller Live-Zyklus sauber. Laufende Operationen unterliegen weiterhin ihren eigenen Timeouts.
2. Nichtstreamende Recherche/LLMRouter.chat lieferte in echter Probe eine leere Antwort trotz Suchdaten; streamende Tool-Continuation erfolgreich. Separate LLM-Qualitätsgrenze.
3. Voice-Suche funktionierte mit Audio, änderte aber das Suchthema; Gesamtlatenz109.301s und anschließender Watchdog-Eingriff. Ursprung der Themenverschiebung und des auffälligen Command-Zustands nicht abschließend bestimmt.
4. Ursache des unmöglichen Datums im ursprünglichen Toolargument unverifiziert.
5. HIGH-4, HIGH-5 und vollständige Phase-3-Live-Security-Abnahme bleiben getrennt offen.
6. Desktop-API-Initialisierung überschritt90s deutlich, erreichte aber später echte HTTP-/Runtime-Readiness. Hohe aktive native CPU-Last beobachtet; konkrete Stackursache unverifiziert. Chatterbox-/health zeitweise zu langsam, finale Prüfung READY.

## O. Decision

**WEB SEARCH LIVE ACCEPTANCE: PARTIAL**

Source-Vertrag, Fail-Honest-Verhalten, Dependency-Installation, gezielte Tests, realer Provider, streamende lokale Synthese und technischer Voice-Suchpfad mit neuer Owner-Hörbestätigung belegt. Nach Freigabe Lifecycle-Fix mit sauberem Live-Stop und finaler Runtime READY verifiziert. Gesamtbewertung PARTIAL wegen der echten nichtstreamenden Leerantwort, Voice-Themenverschiebung und Latenz-/Watchdog-Befunde. Keine Behauptung einer vollständigen semantischen/Performance- oder Phase-3-Security-Abnahme. Kein Commit, kein Push, keine weitere Feature-Arbeit. STOPP.
