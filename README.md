<div align="center">

# J.A.R.V.I.S Desktop

### Local AI System · Control Center for Sleepy

**Die Desktop-Oberfläche für ein lokales KI-System, das seinen Zustand offenlegt, statt ihn zu erfinden.**

<code>UI/UX-REFERENZ</code> &nbsp; <code>LOCAL FIRST</code> &nbsp; <code>WINUI 3 ALS PRODUKTIONSZIEL</code>

</div>

<p align="center">
  <a href="https://github.com/CyberG3niusIT/j.a.r.v.i.s-desktop">
    <img src="docs/assets/jarvis-desktop-home.png"
         alt="J.A.R.V.I.S Desktop: aktueller Home-Screen aus dem Projekt"
         width="100%">
  </a>
</p>

<p align="center"><sub>J.A.R.V.I.S Desktop: aktueller Home-Screen aus dem Projekt</sub></p>

---

## Das Zielbild

J.A.R.V.I.S Desktop ist als lokales Control Center für **JARVIS Sleepy** gedacht. Die Oberfläche soll Runtime, Modelle, Sprache, Memory, Werkzeuge und Systemzustand an einem Ort verständlich machen: präzise, ruhig und wie professionelle Windows-Systemsoftware.

Der Screenshot zeigt den aktuellen **UI-Quellprojekt-Referenzprototyp**. Er ist kein Beleg für eine laufende JARVIS-Runtime: Die sichtbaren Zustände sind `UNAVAILABLE`, `NO LIVE DATA` oder `NOT_IMPLEMENTED`, weil dieser Prototyp nicht mit einem Backend verbunden ist.

## Die zwölf Arbeitsbereiche

| Bereich | Aufgabe im Zielsystem |
|---|---|
| **Home** | Systemübersicht und zentraler Einstieg |
| **Chat** | Lokale Unterhaltung mit nachvollziehbarem Verarbeitungskontext |
| **Memory** | Suche, Herkunft und kontrollierte Memory-Verwaltung |
| **Models & Runtime** | Modelle, Dienste, Lifecycle und Routing |
| **Voice & Audio** | Wake Word, STT, TTS, Geräte und Diagnose |
| **Tools & Integrations** | Tools, Skills, MCP und Berechtigungen |
| **Automations** | Zeitpläne, Trigger und Aktionen |
| **Vision & Presence** | Kamera- und Präsenzfunktionen mit sichtbaren Privacy-Grenzen |
| **Mobility / VVS** | ÖPNV- und Mobilitätsdaten |
| **Mobile Connection** | Separater Bereich für die spätere Verbindung mit mobilen Clients |
| **Observability** | Ereignisse, Logs, Services und Recovery |
| **Settings** | Systemweite Konfiguration |

Die Bereiche bilden die Informationsarchitektur des Zielsystems. Ein Navigationspunkt ist keine Aussage, dass die dahinterliegende Runtime-Funktion bereits implementiert ist.

## Systemzustand bleibt belegbar

**Das Backend ist die Quelle der Wahrheit.** Die UI darf Ready-Zustände, Messwerte, Agentenaktivität, Memory-Ereignisse oder Geräte nicht selbst erzeugen.

- Fehlende Quelle bedeutet `UNAVAILABLE`.
- `READY` erscheint erst nach Bestätigung durch die zuständige Runtime.
- `STOPPED` kann bei On-Demand-Diensten ein gültiger Zustand sein.
- Privacy- und Berechtigungsgrenzen werden nicht durch einen UI-Schalter aufgehoben.
- Die Memory-&-Thinking-Ansicht visualisiert keine verborgenen Gedanken und keine erfundene Aktivität.

## Architekturgrenze

Der UI-Quellprojekt-Code ist ein **visuelles und interaktives Referenzprojekt**, keine Produktionsarchitektur. Das native Produktziel ist:

**WinUI 3 · C# · .NET · Windows App SDK · XAML · MVVM**

Web-Routing, Browser-State, React-Komponenten und CSS-Materialität werden nicht als Produktionsstack übernommen. Die native Anwendung bindet Zustände und Aktionen später an reale Backend-Verträge.

## Projektstand

| Artefakt | Aktueller Stand |
|---|---|
| UI-Quellprojekt-Preview | [Projekt öffnen](https://UI-Quellprojekt.dev/projects/340145c6-1e8a-47c6-9732-b08d3720c610) |
| UI-Quellprojekt-Quellrepository | [CyberG3niusIT/j.a.r.v.i.s-desktop](https://github.com/CyberG3niusIT/j.a.r.v.i.s-desktop) |
| Diese README | `CyberG3niusIT/JARVIS-Sleepy`, Branch `J.A.R.V.I.S-UI` |
| Inhalt dieses Branches | Aktuell diese Übergabe- und Projektdokumentation; der UI-Quellprojekt-Quellcode wurde noch nicht in diesen Branch übertragen |
| Backend / Live-Runtime | Nicht verbunden |
| Produktionsreife | Nicht erreicht; dies ist ein UI-Referenzprototyp |

Die UI-Quellprojekt-Vorschau kann eine Anmeldung im zugehörigen Workspace verlangen. Der oben eingebundene Screenshot wird direkt von UI-Quellprojekt ausgeliefert.

## Lokale Entwicklung des UI-Quellprojekt-Quellprojekts

Die folgenden Befehle gelten für das separate UI-Quellprojekt-Quellrepository, nicht für diesen derzeit dokumentationsbasierten Branch:

```bash
bun install
bun run dev
```

Build- und Lint-Skripte aus dem Quellprojekt:

```bash
bun run build
bun run lint
```

Diese Befehle wurden in diesem Branch nicht ausgeführt, weil der UI-Quellprojekt-Quellcode hier noch nicht liegt.

---

<div align="center">
<sub>J.A.R.V.I.S · Local AI System · Sleepy</sub>
</div>
