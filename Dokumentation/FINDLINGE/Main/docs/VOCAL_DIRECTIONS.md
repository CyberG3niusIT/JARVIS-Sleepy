# Interne Regieanweisungen für TTS

Die Regie-Schicht erkennt `[voice:pause=short]`, `[voice:pause=medium]` und
`[voice:pause=long]`. Tags sind interne Steuerdaten und werden vor Chatterbox
und Piper entfernt. Normale Satzzeichen bleiben im Text; sie lösen keine
zusätzlichen Synthese-Aufrufe aus.

Die Pausen dauern derzeit probeweise 200, 500 und 1000 ms. Diese Werte sind
keine freigegebene Voice-Baseline. Ein Hörtest auf Sleepy entscheidet über
endgültige Werte und darüber, ob segmentierte Sprache natürlich genug klingt.

Eine Pause am Anfang oder Ende bleibt erhalten. Aufeinanderfolgende Pausen
bleiben separate Events und ihre Stille addiert sich. Beispielsweise ergeben
`[voice:pause=short][voice:pause=medium]` zusammen 700 ms.

`breath`, `inhale`, `exhale`, `yawn`, `cough` und `sneeze` sind als
`unsupported` erfasst. Chatterbox Multilingual V3 hat dafür keine verifizierte
native Unterstützung. Unbekannte und beschädigte reservierte Tags werden
entfernt. Ein fragmentierter Tag wird höchstens 256 Zeichen gepuffert; bei
Overflow wird bis zur nächsten schließenden Klammer verworfen.

Tag-freier Text verwendet den bisherigen TTS- und Cache-Pfad. Gerichtete
Gesamtausgaben werden nicht unter ihrem bereinigten Text gecacht. Der Parser
trennt Textnormalisierung von Regie und protokolliert nur Eventtyp, Status
und Position.

Für den Hörvergleich:

```bash
/home/alex/jarvis-venv/bin/python scripts/vocal_direction_probe.py \
  --output-dir /mnt/c/Users/Alex/AppData/Local/Temp/JARVIS/vocal-directions-20260922
```

Die fünf WAVs enthalten Baseline, natürliche Kommas und drei Pause-Varianten.
Das Skript spielt nichts ab und verändert keine Chatterbox-Parameter.
