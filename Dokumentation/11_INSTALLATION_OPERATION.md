# Installation und Betrieb

## Zielumgebung

JARVIS läuft lokal-first auf Windows 11 mit Ubuntu 24.04 unter WSL2. Der offizielle Operator-Pfad ist die Windows-Runtime-Steuerung, nicht ein zufälliger manueller WSL-Prozess.

## Runtime-Steuerung

```powershell
$Runtime = "C:\Users\Alex\Projekte\JARVIS-Sleepy\Main\JARVIS-Runtime.ps1"
& $Runtime -Action getRuntime
```

`start`, `stop` und `restart` sind nur zulässig, wenn die vom Supervisor gemeldeten Capabilities dies erlauben. Im Zustand READY war `start:false`, `stop:true`, `restart:true` korrekt.

## Nach Reboot verifiziert

Der Supervisor meldete READY ohne Degraded-Gründe. Voice, Primary, STT, Chatterbox, Audio-Bridge und VVS waren READY. Expert und FLUX waren on-demand STOPPED. NPU war nicht initialisiert. Web war im Supervisor NOT_IMPLEMENTED.

## Betriebsregeln

1. Runtime-State immer aus dem Supervisor lesen.
2. Dienste nicht durch UI oder Configwerte als READY erfinden.
3. Logs nur zur Diagnose, nicht als Ersatz für einen strukturierten Statusvertrag.
4. GPU-Handover erst aktivieren, wenn echter Hardwaretest und Recovery akzeptiert sind.
5. Cloud erst aktivieren, wenn Provider, Modell, Credential und Privacy-Vertrag bewusst gesetzt sind.
6. Keine Secrets/DBs in Übergabe-ZIPs oder Frontend-Repositories kopieren.
