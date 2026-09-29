# J.A.R.V.I.S Mobile

> Workspaceweite technische Einordnung: [JARVIS Sleepy Dokumentation](../Dokumentation/README.md). Diese App bleibt ein separates Repository; ihr eigener Runtime- und Portierungsstand steht in den folgenden Abschnitten.

**Local AI Assistant**

J.A.R.V.I.S Mobile ist die native Android-Oberfläche für den mobilen Teil von J.A.R.V.I.S. Das Repository enthält zwei bewusst getrennte Ebenen:

- `src/` ist die freigegebene Web-Referenz für Informationsarchitektur, Inhalte, Zustände und Interaktionsverhalten.
- `android/` ist der native Port in Kotlin und Jetpack Compose.

Die Web-Anwendung bleibt die UI/UX Source of Truth. Die Android-App ist kein WebView und keine React-Native-Hülle, sondern eine eigenständige Compose-Anwendung.

## Aktueller Stand

Der native Android-Port bildet die freigegebenen J.A.R.V.I.S-Mobile-Screens und Interaktionsflüsse ab. Runtime-Funktionen werden nur dort als echt dargestellt, wo bereits reale Android-Funktionalität vorhanden ist. Nicht angebundene Bereiche bleiben ausdrücklich als Design-State, `UNAVAILABLE`, `PERMISSION_REQUIRED` oder `NOT_IMPLEMENTED` sichtbar.

| Bereich | Stand |
|---|---|
| Navigation und App-Shell | nativ in Compose |
| Start, Chat, System und Mehr | portiert |
| Modelle, Agenten, Tools und Berechtigungen | UI und Demo-State portiert |
| Privacy, Runtimes, Gerät und Diagnose | UI und Demo-State portiert |
| Voice, Memory, Automationen, Einstellungen und About | UI und Demo-State portiert |
| Datei- und Bildanhänge im Chat | echter Android-Dateipicker, lokale Validierung und Preview |
| Lifecycle-State | für interaktive Compose-Zustände gezielt abgesichert, Details in `android/PORTING_PLAN.md` |
| Local AI Runtime | Schnittstelle vorhanden, noch nicht real gebunden |
| Android Permission Runtime | Schnittstelle vorhanden, noch nicht real gebunden |
| Privacy Enforcement | zentrale Schnittstelle vorhanden, konkrete Policy noch offen |
| Sleepy Pairing und Handoff | UI vorhanden, Transport und Trust-Protokoll noch offen |
| Echter Geräte-Test | noch ausstehend |

Die noch offenen Architekturentscheidungen werden bewusst nicht im UI erfunden. Sie sind in `android/OPEN_DECISIONS.md` dokumentiert.

## Projektstruktur

```text
src/components/jarvis     Web-Referenz für Produktkomponenten und Screens
src/components/prototype  Entwicklungs-Harness der Web-Referenz
src/lib/jarvis            Informationsarchitektur, Tokens und Vergleichsbasis
src/routes                TanStack-Routen der Web-Referenz
android/                  Native Android-App in Kotlin und Jetpack Compose
```

Für das Mapping zwischen Web-Referenz und Compose-Implementierung siehe:

- `android/PORTING_PLAN.md`
- `android/OPEN_DECISIONS.md`

## Android

Technischer Stand der nativen App:

- Kotlin
- Jetpack Compose
- Material 3
- Navigation Compose
- Hilt
- Room
- DataStore
- WorkManager
- AndroidX Security Crypto
- Coil
- minSdk 26
- compileSdk / targetSdk 36
- Java / Kotlin Target 17
- Application ID `com.jarvis.mobile`
- Version `0.1.0`

### Build und Qualitätsprüfungen

Linux / macOS / CI:

```sh
cd android
./gradlew clean assembleDebug
./gradlew lintDebug
./gradlew testDebugUnitTest
```

Windows:

```powershell
cd android
.\gradlew.bat clean assembleDebug
.\gradlew.bat lintDebug
.\gradlew.bat testDebugUnitTest
```

Die Debug-APK wird unter folgendem Pfad erzeugt:

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

Der nächste zwingende Qualitätsschritt nach dem automatisierten QA ist die Installation auf echter Android-Hardware und die Prüfung von Navigation, Insets, Tastatur, Dateipicker, Activity-Recreation, Accessibility und Performance.

## Web-Referenz

Technik:

- TanStack Start
- TanStack Router
- React 19
- Vite
- Tailwind CSS 4
- TypeScript
- lokal gebündelte Inter- und JetBrains-Mono-Schriften

`src/server.ts` setzt Content-Security-Policy und weitere Sicherheits-Header.

Entwicklung:

```sh
bun install
bun run dev
bun run build
bun run preview
bun run start
bun run lint
bun run format
```

Der Produktionsserver läuft aus `.output/server/index.mjs`.

## Architekturgrundsätze

- local first
- keine erfundene Telemetrie
- deterministisch vor generativ
- Privacy als harte Architekturgrenze
- keine implizite Rechteausweitung
- reale Android-Zustände statt Mock-Gerätedaten
- Web-Referenz als UI/UX Source of Truth
- native Android-Implementierung ohne WebView

## Noch nicht als fertig zu betrachten

Die vollständige J.A.R.V.I.S-Mobile-Runtime entsteht erst mit den realen Bindings hinter der Oberfläche. Dazu gehören insbesondere:

- lokale Modell-Inferenz
- echte Android-Berechtigungsprüfung und Permission-Flows
- zentrale Privacy-Policy pro Capability
- Agent- und Action-Runtime
- Voice Runtime
- persistente produktive Datenhaltung
- Sleepy Discovery, Pairing, Trust und Handoff

Diese Punkte sind bewusst von der bereits portierten Oberfläche getrennt, damit UI-Zustand und echte Runtime-Fähigkeit nicht miteinander verwechselt werden.

## Lizenzhinweise

Drittanbieter-Komponenten behalten ihre jeweiligen Lizenzen und Attributionen. OpenDroid wird als Apache-2.0-lizenzierte Referenz für die spätere Android-Agent- und Action-Schicht geführt. Die konkrete Übernahme einzelner Komponenten ist nicht Bestandteil des aktuellen Compose-UI-Ports.
