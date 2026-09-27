# Persistenz und Datenbereiche

Diese Übersicht beschreibt Code-/Config-Kategorien. Sie enthält keine Datenbankdateien, persönlichen Runtime-Pfade, Schemazeilen oder Inhalte.

| Bereich | Code / Speicherart | Statusgrenze |
|---|---|---|
| Gesprächsfakten/-interaktionen | MemoryManager, SQLite und FAISS-Index | Existenz, Größe und Rebuild-Fähigkeit nicht geprüft |
| segmentierter Kontext | ContextWindow, SQLite | geladene Segmente und Retention nicht live geprüft |
| Personenprofile | PeopleManager, SQLite | private Kontaktinhalte ausgeschlossen |
| Reminder | ReminderManager, SQLite; optionale Kalender-Synchronisation | Kalenderzugriff nicht verifiziert |
| Betriebsevents/Beobachtung | EventLogger, Findings als Scores; Laufzeitverlauf zusätzlich begrenzt im Speicher | keine Log-/Finding-Inhalte geprüft |
| LLM-Metriken | MetricsTracker, persistente DB | keine Metriken ausgelesen |
| News/Wetter | jeweilige Manager und Stores | externe Aktualität nicht geprüft |
| School/Mobility | separate SQLite-Fachbereiche; Mobility-Profile und verifizierte Stop-Präferenzen | neu im uncommitteten Stand; keine privaten Einträge gelesen |
| Interaction-/TTS-Caches | eigene Cachekomponenten | Cacheinhalt und Löschstatus nicht geprüft |

Retentionwerte sind in `config.yaml` verteilt. Für echte Deployment-Dokumentation müssen Backup, Verschlüsselung, Berechtigungen, Migrationen, Löschung und Recovery zusätzlich auf dem Zielsystem geprüft werden.
