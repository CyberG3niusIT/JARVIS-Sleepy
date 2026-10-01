# Memory und Datenhaltung

## Implementierte Pfade

`core/memory_manager.py`, `core/context_window.py`, `core/interaction_cache.py` und `core/tts_cache.py` implementieren getrennte Memory-/Cache-Aufgaben. `config.yaml` enthält Schalter, Retention-/Schwellwerte und externe DB-Pfadkonfigurationen für Memory, Metrics, People, School, Mobility und Reminder.

Der MemoryManager hält getrennte Fakten, Interaktionen und kontextuelle Historie; er unterstützt semantische Suche über FAISS, Recall-/Transparenz-/Vergessen-Pfade, Interaktionsabruf und konfigurierbare Retention. Extraktion kann pro Turn und in Batches angestoßen werden. `context_window.py` verwaltet thematisch segmentierten Arbeitskontext mit begrenzten jüngsten Originalnachrichten und Zusammenfassung älterer Segmente. Diese Codepfade sind implementiert; reale Index-/Datenbankinitialisierung und vollständige Lebenszyklusabnahme sind nicht bestätigt.

PeopleManager ist ein separater Kontakt- und Aussprachespeicher (`core/people_manager.py`) und registriert Aussprachekorrekturen für den TTS-Normalizer. Konversationsfakten im Memory und strukturierte Personenprofile sind verschiedene Datenbereiche.

Weitere persistente Bereiche liegen in eigenen Modulen/Stores: ReminderManager, EventLogger, MetricsTracker, News-/Weather-Stores sowie TTS-/Interaction-Caches und School-/Mobility-Profile. Hier werden keine konkreten Runtime-Pfade, Tabelleninhalte oder persönlichen Daten dokumentiert. Retention, Backup, Löschung und Dateirechte sind für jedes Betriebsprofil separat nachzuweisen.

## Speichergrenze

Die Runtime-Daten liegen außerhalb des Quellrepositorys. Diese Dokumentation nennt absichtlich keine privaten Datensätze, Inhalte, persönlichen Pfade oder Schema-/Zeileninhalte. Datenbanken wurden nicht geöffnet. Vorhandensein eines `db_path` belegt weder initialisierte Datenbank noch erfolgreiche Zugriffe.

## Status und offene Prüfung

Fakten-Retrieval, Interaktionscache und kontextuelle Segmente sind codegestützt, aber tatsächliche Initialisierung, Embedding-Modellverfügbarkeit, Datenintegrität, Löschpfade und Retention wurden nicht live geprüft. Ein belastbarer Runtime-Health-Nachweis fehlt.
