# J.A.R.V.I.S DESKTOP FOUNDATION

## Ziel
Ein eigenständiges UI-/UX-Labor für eine präzise Windows-Desktop-Shell. Es entsteht ausschließlich die Foundation als interaktiver Referenzprototyp; keine fertigen Produktseiten, keine Backend-Verbindung und keine Produktionsarchitektur.

## Designplan

### Farbe
- **App Ink** `#081018` — tiefer, neutraler Arbeitsgrund
- **Panel Steel** `#0D1720` — primäre Arbeitsflächen
- **Raised Alloy** `#111E29` — aktive und angehobene Ebenen
- **Structure Blue** `#1B2D3A` — Grenzen und Raster
- **J.A.R.V.I.S Blue** `#2099E8` — Auswahl und Fokus
- **Signal Cyan** `#39B9F1` — sparsame technische Hervorhebung

Statusfarben werden ausschließlich semantisch für klar beschriftete Designbeispiele eingesetzt. Text-, Warn-, Fehler- und Erfolgstöne folgen den vorgegebenen Tokens.

### Typografie
- **Technisch-neutrale Grotesk:** IBM Plex Sans für Oberfläche, Navigation und Hierarchie; klare Windows-nahe Lesbarkeit ohne Systemschrift-Imitation.
- **Technische Werte:** IBM Plex Mono nur für Zustandsnamen, IDs und Tokenwerte.
- Tabellenziffern, moderate Laufweite, kompakte Zeilenhöhen und keine dekorativen Versalien-Etiketten.

### Raster
- Desktop-Shell mit schmaler fester Navigation, kompaktem Systemkopf und 12-Spalten-Arbeitsraster.
- Linksbündige Inhalte; klare horizontale Ausrichtung und dichter, ruhiger Vertikalrhythmus.
- Kleine Radien, flache Ebenen, feine Trennlinien; auf schmalen Ansichten wird die Navigation horizontal erreichbar, ohne eine Mobile-Kartenwand zu erzeugen.

```text
┌──────────────┬──────────────────────────────────────────┐
│ J.A.R.V.I.S  │ Systemkopf: Quelle / Privacy / Cloud    │
├──────────────┼──────────────────────────────────────────┤
│ 12 Ziele     │ Auswahlkontext                           │
│              ├───────────────┬──────────────────────────┤
│              │ Shell/Panel   │ Memory-Grundlage         │
│              ├───────────────┴──────────────────────────┤
│              │ Typografie / Tokens / Zustandsbeispiele │
└──────────────┴──────────────────────────────────────────┘
```

### Prinzipien
- **Autorität sichtbar machen:** Jede Shell-Aussage nennt die fehlende Quelle als `UNAVAILABLE`; keine implizite Betriebsbereitschaft.
- **Ein prägendes Element:** Eine ruhige, nicht-operative Memory-Struktur aus statischen Knoten und Verbindungen; keine Gedanken, Aktivität oder Effekte.
- **Desktop-Werkzeug statt Dashboard:** keine Hero-Fläche, KPI-Karten, Graphen, Glaseffekte oder dekoratives Leuchten.
- **Interaktion ohne Täuschung:** Navigation und Ansichtswechsel funktionieren; unbestätigte Aktionen sind deaktiviert und begründen die Grenze.
- **Privacy als Zuständigkeit:** Mikrofon, Kamera und Cloud zeigen ausschließlich fehlende autoritative Daten, keine Schalter mit vorgetäuschter Wirkung.

## Kritische Prüfung gegen die Produktidentität
- Die typische SaaS-Kartenwand wird durch eine zusammenhängende Shell mit Raster und wenigen klaren Panelgrenzen ersetzt.
- Die dunkle Basis erhält kein Cyberpunk-/Gaming-HUD: Cyan bleibt Akzent, es gibt weder Glow noch Scanlines oder animierte Energieeffekte.
- Die Memory-Darstellung ist bewusst statisch und als nicht-operatives Gestaltungselement bezeichnet; sie zeigt weder Chain-of-Thought noch erfundene Events.
- Der Kopf zeigt keinen globalen READY-Zustand. Ohne Backend lautet jede operative Quelle `UNAVAILABLE` oder `NO LIVE DATA`.
- `Mobile Connection` bleibt ein eigenes Ziel neben `Mobility / VVS`; beide erhalten nur ehrliche Foundation-Platzhalter.

## Umsetzung
- Zentrale semantische Tokens für Farbe, Typografie, Abstände, Radien, Fokus und Zustände definieren.
- Desktop-Shell mit Wortmarke `J.A.R.V.I.S`, `Sleepy`, `Local AI System`, Systemkopf und allen 12 exakt benannten Navigationszielen bauen.
- Aktive Navigation interaktiv machen; nicht spezifizierte Ziele zeigen denselben ehrlichen Foundation-Platzhalter statt fertiger Seiten.
- Wiederverwendbare Panels, Typografie-Muster, Privacy-/Cloud-Anzeigen und eine kompakte Galerie aller acht State-Varianten erstellen.
- Galerie unübersehbar als **„Designbeispiele — kein Live-Systemzustand“** kennzeichnen; `STOPPED` als gültigen On-demand-Zustand erklären.
- Sämtliche nicht bestätigten Aktionen deaktivieren und direkt mit fehlender Backend-Capability begründen.
- Tastaturfokus, normale Windows-Skalierung und `prefers-reduced-motion` berücksichtigen.

## Technische Grenze
Der Prototyp verwendet die vorhandene Web-Toolchain nur zur visuellen Referenz. Er enthält keine Production-Empfehlung und keine Anbindung. Das Produktionsziel bleibt WinUI 3, C#, .NET, Windows App SDK, XAML und MVVM.

## Prüfung
- Desktop- und schmale Vorschau visuell prüfen; Fokus, Überläufe und Navigation testen.
- Alle Texte und Zustände auf erfundene Telemetrie, Live-Aussagen, Geräte, Modelle, Agenten, Memory-Aktivität und Cloud-Aktivität durchsuchen.
- Sicherstellen, dass alle acht State-Beispiele vorhanden und ausschließlich als Designbeispiele markiert sind.
- Sicherstellen, dass keine externe Anbindung, Veröffentlichung oder Übernahme aus anderen Projekten erfolgt ist.

## Annahme
Dieser aktuell leere Projektbereich ist das neue unabhängige Projekt. Der sichtbare Workspace-Projektname wird auf **J.A.R.V.I.S Desktop** gesetzt, soweit die Projektoberfläche dies aus diesem Build-Kontext unterstützt; der Prototyp selbst verwendet exakt diese Wortmarke.
