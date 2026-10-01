# JARVIS Voice Baseline

## Status

This file defines the reproducible production Voice/TTS baseline recovered from
the 15/16 September 2026 JARVIS work. It is a runtime contract, not a tuning
playground.

## Primary TTS

- Engine: Chatterbox Multilingual V3
- Runtime: `/home/alex/chatterbox-venv/bin/python3`
- Device: AMD Radeon RX 7900 XTX via ROCm
- Language: `de`
- Tempo: `0.89`
- Exaggeration: `0.5`
- CFG weight: `0.5`
- Temperature: `0.8`
- Repetition penalty: `1.2`
- min_p: `0.05`
- top_p: `1.0`

Canonical runtime values are stored in `systemd/chatterbox.env`.

## Canonical voice anchor

Path:

```text
/home/alex/jarvis-data/voices/chatterbox/jarvis-reference.wav
```

SHA256:

```text
0ccc1fe174ea5aec6e9b416711a0f6d8247a9ea21039255896ec90f7a959ff2f
```

Provenance: `chatterbox-diag-20260916.zip/05.wav` == `chatterbox-05.wav`
== recovered `chatterbox-test-reset.wav`.

Do not replace this file silently. `start_chatterbox.sh` refuses to start when
its hash differs from the canonical value.

## Audio output

Primary playback is native Windows audio through the existing
`audio.output_backend: windows` path. Chatterbox emits native 24 kHz mono WAV;
JARVIS does not upsample it as a quality hack.

Pulse/PipeWire/ALSA remain compatibility paths, not the production playback
baseline on Sleepy.

## Startup policy

Normal startup is strict: JARVIS must not silently enter the normal interactive
runtime with Piper because Chatterbox was never started. The runtime checker
verifies `/health`, `/config`, all canonical generation parameters and the voice
anchor SHA.

A deliberately degraded start remains possible by explicitly setting:

```bash
export JARVIS_ALLOW_DEGRADED_TTS=1
```

Piper remains the last runtime fallback after a failure during an already
running session.

## Preserved historical code

At the recovery point, the following important voice components matched the
known-good historical Git blobs and must not be retuned prophylactically:

- `core/tts_normalizer_de.py`
- `core/speech_chunker.py`
- `core/persona.py`
- `core/people_manager.py`

## Acceptance

The baseline is accepted only after real Sleepy verification of:

1. canonical SHA and `/config`
2. direct Chatterbox WAV generation
3. `TextToSpeech.speak()` through Windows audio
4. multi-sentence streaming
5. German pronunciation regression texts
6. deliberate Piper fallback
7. complete unit suite
