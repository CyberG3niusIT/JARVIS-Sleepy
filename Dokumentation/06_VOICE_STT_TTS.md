# Voice, STT und TTS

## Pipeline

Die Codebasis enthält Listener, VAD, Wakeword, STT-Backends, Pipeline, Chunking/Normalisierung, TTS-Engines und Audiowiedergabe-Adapter. Die relevante Implementierung liegt in `core/continuous_listener.py`, `core/vad.py`, `core/wake_word.py`, `core/stt.py`, `core/stt_qwen3.py`, `core/pipeline.py` und `core/tts.py`.

## Konfiguration

Die geprüfte YAML wählt Qwen3 als STT-Backend auf CPU und Chatterbox als TTS-Engine. Wake Word läuft über den separaten Porcupine-Adapter (`core/wake_word.py`). Chatterbox wird per HTTP von einem separaten Serverprozess bedient; Piper und Kokoro sind alternative TTS-Pfade. Ein gesetzter Endpunkt oder Engine-Name ist keine Verfügbarkeitsgarantie.

Die Pipeline führt Mikrofonaufnahme, VAD/Wakeword, STT, Router/Skills/Tools und Chunked TTS/Audiowiedergabe zusammen. Normalisierung und Caching liegen in separaten Komponenten. Gerätewahl, Windows-Ausgabe und WSL-Audiobrücke sind hostabhängig und wurden nicht live geprüft.

## Vocal Directions

Im aktuellen Arbeitsbaum liegen neu `core/vocal_directions.py`, zugehörige Pipeline-/TTS-Änderungen und Probe-/Testdateien. Diese Arbeit ist experimentell. Historische Probe-Ergebnisse vom 22.09. sind keine aktuelle Live-Abnahme oder Nutzerfreigabe; die genaue Parser-/Cache-Grenze ist in den Quelländerungen zu prüfen.

## Verteilte Voice-Dokumente

Die früheren Dateien `VOICE_BASELINE.md`, `VOCAL_DIRECTIONS.md`, `TTS_VOICE_OPTIONS.md`, `VOICE_TRAINING_GUIDE.md` und `STT_WORKER_PROCESS.md` sind als Quellen im [Inventar](INVENTORY.md) erfasst. Ältere Modell-, Hardware- und Qualitätsangaben sind nicht automatisch aktuell.

## Turn-Aggregation und Direct-Audio (Stand 25.09.2026)

Evidenz: alle Punkte dieses Abschnitts sind **nur per Unit-Test mit Fakes** belegt; die JARVIS-Integration mit Gemma-Audio wurde **nicht auf Hardware getestet** (das llama.cpp-`input_audio`-Schema selbst hat der Nutzer früher manuell als funktionierend bestätigt).

### Turn-Assembler (`core/turn_assembler.py`)

Mehrere Sprachsegmente werden zu einem Turn zusammengefasst, bevor er an Primary geht. Config `turn.*`: `grace_ms` 1200, `max_turn_s` 20, `max_segments` 8, `min_segment_ms`, `fast_stop_max_s` 1.6.

- Fast Path nur für kurze Segmente, die einen Turn eröffnen; kurze Fragmente <= 1.6 s, die einen Turn eröffnen, werden nicht aggregiert (bekannte Einschränkung).
- Stop/Barge-in wirken sofort; Eingaben während TTS (`during_tts`) umgehen den Assembler.

### Direct-Audio (`core/direct_audio.py`)

- Das Audio geht direkt an Gemma; STT blockiert den Turn nicht mehr. Ein paralleler Helfer läuft für Wake-Kompatibilität (`stt.wake_compat`), außerdem Stop-Fast-Path, Diagnose und optionales Transkript.
- Das ASR-Transkript ist nur `asr_hint`, nicht die Wahrheitsquelle.
- Text-Fallback ist standardmäßig aus (`llm.primary.text_fallback`).
- Gespeicherter Nutzertext ist ein Platzhalter `[Sprachnachricht aN]`.
- Direct-Audio-Turns bieten ALLE Tools an (Option `llm.primary.audio_tools: always`).
- Kein STT-Rauschfilter für Direct-Audio im Konversationsfenster; der Quality-Gate-Fallback ruft `llm.chat` ohne Audio auf.

### Spekulativer Turn (`core/speculative_turn.py`)

Vor der Wake-Bestätigung startet eine spekulative Gemma-Anfrage. Sie ist nebenwirkungsfrei: keine Tools, kein Memory-Schreiben, keine State- und History-Änderung, kein TTS, keine UI; bei ausbleibendem Wake wird sie abgebrochen (`test_speculative_audio_side_effects.py`). Spekulative Wake-Turns haben keinen Memory-/Awareness-Kontext, nur History (Folgearbeit).

Der Wake-Normalpfad enthält weiterhin STT; entfernen erst, wenn NPU-Wake real ist (derzeit NOT_IMPLEMENTED).
