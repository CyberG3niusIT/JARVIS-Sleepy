# School und Mobility

**Code-Reife: experimental / partial. Live-Abnahme: offen.** Implementierung ist im lokalen Arbeitsbaum neu/uncommittet; Unit-Tests und Dokumentation existieren, aber kein aktueller Canary wurde in dieser Runde ausgeführt.

## Verantwortlichkeiten

School hält bestätigte Schuldaten und Reiseereignisse (`core/school_db.py`, `skills/personal/school/`). Mobility plant Route/Abfahrt und Status (`core/mobility_contract.py`, `core/mobility_planner.py`, `skills/system/mobility/`). Personenauflösung läuft über PeopleManager. Private Records und Stoppzuordnungen bleiben in externer Runtime-Datenhaltung.

## API und Demand

Laut Auftraggeber ist die lokale VVS-API unter `http://127.0.0.1:8088` vorgesehen; die aktive `config.yaml` setzt die URL absichtlich nicht fest und verlangt `WIMAEDV_VVS_BASE_URL`. Ohne Umgebungswert meldet der Client `NOT_CONFIGURED`. Der vorhandene ReminderManager-Scheduler verwaltet Demand-Fenster; es gibt keinen zweiten Sleepy-Poller. Das vom lokalen API-Vertrag beschriebene Demand-Modell unterscheidet `DORMANT`, `WATCH` und `ACTIVE`; die lokalen API-Zustände wurden nicht live verifiziert. In `DORMANT` soll es keine periodischen Realtime-Abfragen geben, direkte Lookups bleiben möglich.

Im Sleepy-Code ist ein Lease-TTL von 900 Sekunden vorgesehen, Updates frühestens alle 300 Sekunden. Demand-Fenster werden aus School-Reiseereignissen und expliziten Reise-/Haltestellenregeln berechnet: WATCH beginnt standardmäßig 90 Minuten vor dem Ereignis; ACTIVE standardmäßig 10 Minuten vor Abfahrt und endet standardmäßig 30 Minuten nach dem Ereignis. Konfigurationswerte können abweichen. `ReminderManager` triggert die Synchronisation in seinem vorhandenen Scheduler; beim Stop wird die Lease freigegeben. Diese Angaben beschreiben den Sleepy-Clientvertrag, nicht die laufende Konfiguration des separaten VVS-Dienstes.

Die bestehende School-Dokumentation beschreibt als Soll-Pollingcadence für die API WATCH: Vehicles/Trip Updates alle 300 Sekunden und Alerts alle 900 Sekunden; ACTIVE: Vehicles alle 45, Trip Updates alle 90 und Alerts alle 300 Sekunden. Diese Werte sind in den geprüften Sleepy-Clientmodulen nicht festgelegt und wurden gegen den separaten API-Dienst nicht verifiziert; sie bleiben deshalb dokumentierter API-Vertrag/Sollwert, keine Laufzeitbehauptung.

## Realtime-Behandlung

Der Entwurf trennt vollständige Echtzeitprognose, partielle Daten und reine Fahrplandaten. Stale/partial Realtime darf nicht als vollständige Liveprognose erscheinen. Fehlende Felder bleiben unbekannt. `STATIC_DATA_STALE` ist mangels verifizierbarer Metadaten nicht implementiert.

Für Schulereignisse werden nur explizit konfigurierte Regeln mit verifizierter EFA-Haltestellenzuordnung betrachtet. Eine planmäßige Abfahrt muss nach Abfahrtszeit, optionaler Linie und Richtung eindeutig zur Regel passen. Eine Verspätung qualifiziert eine primäre Abfahrt nicht automatisch als unbrauchbar: noch erreichbare Kandidaten werden gegen Ankunftsdeadline und effektive Zeiten bewertet. Eine vollständige Liveprognose erfordert frische Realtime-Kennzeichnung, geschätzte Abfahrt und geschätzte Zeiten auf allen Transit-Teilstrecken. Bei stale/partiellen Daten werden Schätzungen aus Ergebnis und Ranking entfernt und Fahrplanzeiten benutzt. Unter den zulässigen Kandidaten sortiert der Code nach frühester effektiver Ankunft, dann Abfahrt und Regelpriorität. EFA- und GTFS-RT-Trip-IDs werden nicht selbstständig zusammengeführt.

## Auftraggeberseitig berichtete Einsatzwerte

Die folgenden Angaben sind vom Auftraggeber mitgelieferter Arbeitsstand und wurden nicht live bestätigt: Primary Linie 144 um 07:18; Fallback 168 um 07:48; die Auswahl einer noch rechtzeitigen Alternative bei extremer Verspätung; 600 Unit-Tests zuletzt berichtet; 65-Minuten-DORMANT-Soak bestanden; Live-Canary vom 24.09. unvollständig (Exitcode 1); Canary für 25.09. vorbereitet; Live-Abnahme offen. Die Linien-/Uhrzeitzuordnung wird nicht durch öffentliche Repo-Konfiguration belegt und kann von privaten Mobility-Regeln abhängen. Konkrete Haltestellen, persönliche Fahrpläne und School-Datensätze werden nicht dokumentiert.
