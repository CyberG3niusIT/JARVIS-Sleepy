# J.A.R.V.I.S Mobile

Local AI Assistant. UI/UX Baseline als Web-Prototyp.

Dieses Repository enthält die freigegebene Gestaltungs- und Interaktionsgrundlage
für J.A.R.V.I.S Mobile. Der Prototyp bildet die spätere Android-Anwendung
(Kotlin, Jetpack Compose) vor und bindet bewusst keine Laufzeit an: alle
Zustände sind wahrheitsgetreue Entwurfszustände, es gibt keine erfundene
Telemetrie.

## Inhalt

- `/` Entwicklungs- und Referenzseite mit Informationsarchitektur
- `/prototypes/shell` Produktvorschau, standardmäßig die freigegebene Variante D
  (Varianten A, B und C bleiben als historischer Entwicklungsvergleich über
  `?v=1`, `?v=2`, `?v=3` erreichbar)
- `/design-system` interne Referenz für Tokens, Komponenten und Motion

Struktur:

```
src/components/jarvis     Produktkomponenten, Screens, Motion, Controls
src/components/prototype  Entwicklungs-Harness (Geräterahmen, Variantenauswahl)
src/lib/jarvis            Informationsarchitektur, Tokens, Vergleichsbasis
src/routes                TanStack Router Routen, src/server.ts als Server-Entry
```

## Technik

TanStack Start, TanStack Router, React 19, Vite, Tailwind CSS 4, TypeScript.
Schriften (Inter, JetBrains Mono) werden lokal über Fontsource gebündelt, es
werden keine externen Schriftdienste geladen. `src/server.ts` setzt
Content-Security-Policy und weitere Sicherheits-Header.

## Entwicklung

Voraussetzung: Bun (alternativ npm mit denselben Skripten).

```sh
bun install
bun run dev        # Entwicklungsserver auf http://localhost:8080
bun run build      # Produktionsbuild
bun run preview    # Vorschau des Builds
bun run lint
bun run format
```

## Lizenzen

Der Code dieses Repositories steht unter der Apache License 2.0.
Drittanbieter-Lizenzhinweis: OpenDroid, Apache License 2.0.
