# Finaler Finish- und Konsistenzpass

## Ziel
Die bestehende Shell, Top-Navigation und offizielle J.A.R.V.I.S Wortmarke bleiben erhalten. Alle zwölf Bereiche werden innerhalb dieser freigegebenen Richtung zu eigenständigen, konsistenten Desktop-Arbeitsflächen verfeinert. Es werden ausschließlich statische, eindeutig gekennzeichnete Designzustände verwendet.

## Umsetzung

### 1. Gemeinsames Page-Kit präzisieren
- Seitenkopf, Subtabs, Toolbars, Panels, Tabellen, Detail-Drawer, deaktivierte Controls und alle State-Flächen visuell vereinheitlichen.
- Panel-Hierarchie über klar definierte Primär-, Sekundär- und Diagnoseflächen stärken, ohne das aktuelle Shell-Konzept umzubauen.
- Hover, Fokus, Aktiv- und Disabled-Zustände vollständig und tastaturtauglich ausarbeiten.
- Import und Export als konsistente, deaktivierte Backend-Aktionen behandeln.
- Drawer-Fokusführung, Schließen per Escape und visuellen Hintergrundzustand prüfen.

### 2. Zwölf Seiten individuell ausarbeiten
- **Home:** Kontrollraum-Dichte, Brain-Fläche, Runtime-/Privacy-Slots, leere Aktivität und Command Surface ausbalancieren.
- **Chat:** technische Conversation Surface statt Messenger-Layout; Kontext, Verlauf und Eingabe als zusammengehöriger Arbeitsbereich.
- **Memory:** Brain als dominantes zentrales Element; Suche, Typen, Provenance und Memory Tools klar darum ordnen; keine Aktivität oder Gedanken simulieren.
- **Models & Runtime:** Primary, Expert, Speech, Services und Routing als technische Runtime-Topologie statt austauschbarer Karten darstellen.
- **Voice & Audio:** Pipeline-Struktur, Geräte, Privacy und Diagnose visuell als Audio-Signalweg organisieren.
- **Tools & Integrations:** Capability-, Permission-, Skill- und MCP-Flächen als kontrollierte Werkzeuginventur differenzieren, weiterhin ohne Integration.
- **Automations:** Liste, Trigger, Aktionen und Detailzustand als Desktop-Ablaufeditor strukturieren, ohne Beispielautomation.
- **Vision & Presence:** Kamerafläche, Sensorik, Ereignisse und Privacy mit klarer visueller Trennung und ehrlichen Zuständen.
- **Mobility / VVS:** Verkehrs- und Routenkontext, Verbindungsansicht sowie Import/Aktualisierung eindeutig auf Mobilitätsdaten ausrichten.
- **Mobile Connection:** bewusst reduzierte Geräte-/Pairing-/Handoff-Oberfläche mit durchgehendem `NOT_IMPLEMENTED`; klar anders als Mobility / VVS.
- **Observability:** dichte System-, Service-, Ereignis-, Log- und Recovery-Struktur ohne Diagramm- oder Grafana-Anmutung und ohne Messwerte.
- **Settings:** professionelle Windows-Master/Detail-Ansicht mit fester Bereichsliste, klarer Detailhierarchie und vollständig deaktivierten Backend-Controls.

### 3. Zustände und Texte vollständig prüfen
- `STARTING`, `READY`, `DEGRADED`, `ERROR`, `STOPPED`, `OFFLINE`, `NOT_IMPLEMENTED`, `UNAVAILABLE` sowie Loading und Empty konsistent darstellen.
- Fehlende Quellen ausschließlich ehrlich kennzeichnen; kein Live-Eindruck durch Farbe, Bewegung, Zahlen oder Formulierungen.
- Alle sichtbaren Texte auf Deutsch, kurz und technisch direkt überarbeiten.
- Projektweit U+2013 und U+2014 entfernen und durch ASCII-Zeichen ersetzen.
- Chain-of-Thought, Fake-Logs, Fake-Geräte, Fake-Runtimewerte und sonstige erfundene Daten ausschließen.

### 4. Altlasten gezielt bereinigen
- Eindeutig ungenutzte Regeln der verworfenen Sidebar-/frühen Foundation entfernen.
- Ungenutzte Platzhalter und tote Imports entfernen.
- Funktionierende aktuelle Regeln nicht aus rein stilistischen Gründen umbauen.
- Die interne Zustands- und Typografie-Referenz ausschließlich auf `/__design` belassen.

### 5. Vollständige visuelle Qualitätssicherung
- Jede der zwölf Seiten und alle Tabs gegen die Referenzscreens prüfen.
- Drawer, Menüs, Dialogzustände, Tabellen, Toolbars, Import/Export, leere Flächen und Keyboard-Fokus testen.
- Screenshots und Overflow-Prüfung bei 1920×1080, 1600×900, 1366×768 und einem schmalen Desktop-Fenster durchführen.
- Netzwerkprüfung auf externe Requests sowie Konsole, Laufzeitfehler und aktuellen Build-Status prüfen.
- Sichtbar schwächere Seiten vor Abschluss weiter verfeinern.

## Technische Leitplanken
- Bestehende Top-Navigation und offizielle Wortmarke bleiben maßgeblich.
- Moduldefinitionen bleiben konfigurationsgetrieben; nur eindeutig spezielle Seiten erhalten eigene Layout-Kompositionen.
- Keine Backend-, Auth-, Datenbank-, Analytics-, Connector-, API-, Cloud-, Publish- oder WinUI-Arbeit.
- Keine Änderung an anderen Projekten.

## Abschlussbericht
Kompakter Bericht mit genau diesen Punkten:
- `[Sicher] fertiggestellte Seiten`
- `[Sicher] bereinigte Inkonsistenzen`
- `[Sicher] offizielle Brand Assets`
- `[Sicher] En-Dash-/Em-Dash-Audit`
- `[Sicher] Fake-Data-Audit`
- `[Sicher] getestete Auflösungen`
- `[Sicher] verbleibende Placeholder`
- `[Review] echte verbleibende visuelle Schwächen`
- `[Preview] aktueller Stand`

Danach Stopp. Keine Veröffentlichung und keine native Umsetzung.
