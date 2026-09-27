# Memory und Datenhaltung

## Runtime-Bausteine

`core/memory_manager.py`, `core/context_window.py`, `core/interaction_cache.py` und weitere Stores trennen Langzeitfakten, Interaktionen, Arbeitskontext und Caches. Semantische Suche nutzt FAISS; persistente Daten liegen außerhalb des Quellrepositorys.

Memory muss explizite Aussagen, bestätigte Fakten, Beobachtungen, Inferenz, Hypothesen, temporären Kontext, Korrekturen und veraltete Informationen unterscheiden. Nutzerkorrekturen haben Vorrang; Unsicherheit und Provenance müssen erhalten bleiben.

## UI-Vertrag

Die neue Desktop-Oberfläche darf Memory visualisieren, aber keine internen Zustände erfinden. Die geplante Gehirn-/Synapsenansicht ist eine **Visualisierung beobachtbarer Verarbeitungsschritte**, zum Beispiel:

- aktiver Arbeitskontext,
- Memory-Retrieval,
- semantische Verknüpfungen,
- Tool-/Skill-Entscheidungen,
- Modellrouting,
- Antwortgenerierung,
- neue bestätigte Memory-Verknüpfungen.

Sie ist kein wörtliches Auslesen oder Anzeigen verborgener Modell-Gedankenketten. Nicht verfügbare Daten werden als unbekannt/unavailable dargestellt.

## Datenschutz und Persistenz

Private Datenbanken, konkrete persönliche Inhalte und Secrets werden nicht in dieser Doku gespiegelt. Memory Learning ist keine Self-Modification: Memory darf keine Rechte erweitern, Privacy umgehen, Tools freischalten, Cloud aktivieren oder Code verändern.

## Status

Memory-/Context-Code ist implementiert. Die Desktop-UI soll Backenddaten verwenden und keine Speichergrößen, Confidence-Werte oder Wissenswachstumsmetriken simulieren, wenn dafür keine reale Quelle existiert.
