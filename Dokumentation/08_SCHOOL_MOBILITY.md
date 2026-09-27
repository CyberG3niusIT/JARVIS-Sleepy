# School und Mobility

## Verantwortlichkeiten

School hält bestätigte Schuldaten und Reiseereignisse. Mobility plant Route, Abfahrt und Realtime-Status. Fehlende oder stale Echtzeitdaten dürfen nicht als sichere Liveprognose dargestellt werden.

## VVS-Dienst

Der lokale WIMAEDV-VVS-Dienst verwendet Port 8088. Im Runtime-Snapshot nach Windows-Neustart wurde die Komponente `vvs` als READY gemeldet. Das belegt Dienstbereitschaft, nicht automatisch die vollständige School-/Mobility-Fachlogik.

Die JARVIS-Web-API ist separat für Port 8091 vorgesehen; die frühere 8088-Portkollision gilt damit für den aktuellen Configstand nicht mehr.

## Demand-Modell

Der Clientvertrag unterscheidet `DORMANT`, `WATCH` und `ACTIVE`. ReminderManager bleibt der Scheduler; es soll keinen zweiten unabhängigen Sleepy-Poller geben. Direkte Lookups sind auch in DORMANT möglich, periodische Realtime-Abfragen nur bei Bedarf.

## Realtime-Regeln

- partielle/stale Realtime nie als vollständige Liveprognose ausgeben
- fehlende Felder unbekannt lassen
- Fahrplanzeiten verwenden, wenn Realtime nicht belastbar ist
- EFA- und GTFS-RT-Identitäten nicht ungeprüft zusammenführen
- Alternativen nach effektiver Ankunft, Abfahrt und Regelpriorität bewerten

## Status

VVS-Infrastruktur ist live belegt. Vollständige School-/Mobility-End-to-End-Abnahme inklusive realer Regeln, Benachrichtigungen und Canary bleibt separat zu dokumentieren. Frühere Canary-/Soak-Zahlen sind historische Arbeitsstände und werden hier nicht als aktuelle Abnahme wiederholt.
