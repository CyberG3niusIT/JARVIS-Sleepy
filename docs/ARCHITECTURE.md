# JARVIS — Architecture & Project Memory

Persistent technical reference for anyone (human or agent) picking up this
project cold. Complements [`DEVELOPMENT.md`](DEVELOPMENT.md) (repo/workflow
mechanics) — this file is about *what the system is, why it's built this
way, and what's known to be broken or half-done*. Keep it current: when you
make an architectural decision or find a real bug, write it here, not just
in a commit message.

Last major update: 2026-09-15 (Claude active-refactor session, branch
`claude/jarvis-architecture`, safepoint `3a58c9e` / tag
`sleepy-pre-claude-20260915`).

## 1. What JARVIS is

A local-first, always-listening voice assistant ("Aura" wake word) running
on a Windows host via WSL2. German-first (`system.language: de-DE`,
`stt.language: de`), British-butler persona (`core/persona.py`). Three
entry points, all sharing `core/pipeline.py` as the conversation engine:

| Entry point | Purpose |
|---|---|
| `jarvis_continuous.py` | Primary runtime — always-on mic, wake word, VAD, full voice loop |
| `jarvis_console.py` | Text/hybrid console for development and debugging |
| `jarvis_web.py` | Web UI (dashboard, WebSocket chat, mobile) on port 8088/8443 |

`core/pipeline.py`'s `Pipeline` class (event-driven, coordinator + worker
threads — `pipeline.event_mode: true` in config.yaml) is the shared brain:
routing, LLM streaming, tool calling, TTS orchestration. `jarvis_console.py`
re-implements a **simplified, non-streaming** speak path (see §4) rather
than going through the same streaming machinery — a known divergence, not
a bug, but be aware the console's TTS behavior does not represent the
voice runtime's.

## 2. Runtime stack

| Layer | Technology | Notes |
|---|---|---|
| STT | Qwen3-ASR (sherpa-onnx, int8) | `core/stt_qwen3.py`; fine-tuned Whisper available but disabled (`stt_finetuned.enabled: false`) |
| Wake word | Porcupine ("aura") | `core/wake_word.py` |
| LLM (main) | Qwen3.5-35B-A3B-abliterated, llama.cpp, GGUF Q3_K_M | local, `core/llm_router.py` |
| LLM (small) | local endpoint :8081 | used for quality gating / fast paths |
| LLM (cloud) | Claude (Anthropic API) | opt-in, `llm.api` |
| TTS | **Chatterbox Multilingual V3** | active engine — see §3, own GPU process |
| TTS (alt) | Kokoro-82M (in-process, CPU) | supported, currently unused (`tts.engine: chatterbox`) |
| TTS (fallback) | Piper (subprocess) | last-resort if primary engine fails |
| Vision | InsightFace (presence), GNOME screenshot | |
| Image gen | FLUX.2 Klein 4B | GPU-swapped in on demand, `services/flux_server.py` |
| Memory | SQLite + FAISS | conversational facts, context window, people, reminders, news |

## 3. TTS / Speech pipeline (audited & partially refactored 2026-09-15)

### 3.1 Active engine: Chatterbox

`tools/chatterbox_server.py` is a **standalone process** (own GPU, own
venv `chatterbox-venv`, not started by any script/systemd unit as of this
writing — start it manually). It is not a Python import inside the main
JARVIS process; the client side (`core/tts.py`) talks to it over HTTP
(`tts.chatterbox_endpoint`, default `http://127.0.0.1:8765/tts`).

Verified `generate()` signature (do not change without re-verifying against
the installed `chatterbox` package):
```python
model.generate(
    text, language_id, audio_prompt_path=None,
    exaggeration=0.5, cfg_weight=0.5, temperature=0.8,
    repetition_penalty=1.2, min_p=0.05, top_p=1.0,
)
```
Playback tempo is a post-processing step (`ffmpeg atempo`), not a model
parameter — currently `0.89`, tuned by ear. Both the generation params and
tempo are read from `CHATTERBOX_*` env vars at server startup (see the
module docstring in `tools/chatterbox_server.py`) and can be overridden
per-request in the JSON body — this is the intended hook for a **future
vocal-behavior layer** (dynamic exaggeration/cfg_weight per utterance,
e.g. more emphasis on important reminders, flatter delivery for status
reads).

`tools/chatterbox_server.py` deliberately uses a plain (non-threading)
`HTTPServer`: the model lives on one GPU and can't safely serve two
concurrent `generate()` calls, so single-request-at-a-time is correct, not
an oversight.

### 3.2 Client-side flow (`core/tts.py`, `core/pipeline.py`)

`TextToSpeech.speak()` is the single entry point: CAL-L0 cache lookup →
normalize (`core/tts_normalizer_de.py`) → engine dispatch → Piper fallback
on failure. For **streaming** multi-sentence responses (the normal voice
path), `core/pipeline.py`'s `Pipeline._stream_llm_response()` instead uses
`SpeechChunker` (`core/speech_chunker.py`) to cut LLM tokens into sentence
chunks and feeds them to `StreamingAudioPipeline`, which keeps one
persistent `aplay` process open and writes each sentence's PCM to it as
soon as it's generated — this is what makes multi-sentence responses sound
gapless instead of pausing between every sentence.

As of this session, `StreamingAudioPipeline` supports **both** Kokoro
(streams Kokoro's own sub-chunks) and Chatterbox (one HTTP round-trip per
sentence, PCM decoded from the WAV response via `core/tts.py`'s
`_chatterbox_generate_pcm()`). Before this session, the gapless pipeline
was Kokoro-only and Chatterbox fell through to a fully blocking
generate-then-play-then-generate-next path — since Chatterbox is the
*active* engine, that was the single biggest latency problem in the
pipeline. Fixed by generalizing `StreamingAudioPipeline._run()` to branch
on `tts.engine` (`core/pipeline.py`).

The ack cache (instant "One moment..."-style filler phrases,
`_ack_cache`) and the CAL-L0 response cache (pre-synthesized full
canned responses like greetings, `core/tts_cache.py`) were **Kokoro-only**
before this session — Chatterbox got no instant playback for anything,
meaning every ack/greeting paid a full GPU round-trip. Both now go through
an engine-dispatching `TextToSpeech._synthesize_short_pcm()` and are built
in background threads at Chatterbox init too (blocking startup on ~300
GPU round-trips would be unacceptable, unlike Kokoro's sub-second CPU
synthesis). The on-disk cache version string is now engine-tagged
(`f"5-{self.engine}"`) so switching `tts.engine` in config invalidates and
regenerates rather than silently playing back the wrong voice.

### 3.3 Text normalization

Two independent normalizer modules exist — **only one is live**:

- `core/tts_normalizer_de.py` (`GermanTTSNormalizer`) — the one `core/tts.py`
  actually uses. Handles German number words, dates, times, currency,
  percentages, IPv4, file sizes, markdown stripping, technical-term
  spell-out.
- `core/tts_normalizer.py` (`TTSNormalizer`, English, 1000+ lines) —
  **not used by the speech path at all.** `core/people_manager.py` used to
  register pronunciation overrides on *this* one by mistake (fixed this
  session — see §5). It's still imported by tests and by nothing else in
  the runtime. Candidate for deletion or a documented "legacy, kept for
  future English-mode support" note — undecided; flagged here rather than
  removed since deleting a whole module needs a deliberate call, not a
  drive-by.

Normalizer pass order matters (`GermanTTSNormalizer.__init__`,
`self.normalizations` dict, insertion-ordered): markdown → dates → times →
ipv4 → temperatures → file_sizes → currency → percent → urls → **thousands**
→ decimals → technical → numbers. `thousands` must run before `decimals`:
German groups thousands with `.` (`10.000` = *zehntausend*) while the
decimal separator is `,` — conflating them used to read "10.000" as *zehn
Komma null null null* (fixed this session).

`core/speech_chunker.py`'s abbreviation list (periods that don't end a
sentence) was English-only; German LLM output routinely contains `z.B.`,
`usw.`, `bzw.` etc., which used to trigger a false mid-sentence split and
chop prosody. German abbreviations added this session.

### 3.4 Known TTS issues not yet fixed

- **Contextual ack latency on Chatterbox**: `Pipeline._play_ack_if_still_thinking()`
  can speak a dynamically LLM-generated (4B model) contextual ack via
  `self.tts.speak()`. This text is novel per-command, so it can't be
  pre-cached. On Chatterbox this means a real GPU round-trip inside the
  ack timer thread, which holds `TextToSpeech._tts_lock` — the main
  response's first real chunk then queues behind it. Not fixed this
  session (would need a cancellable/async HTTP request or a hard budget
  on contextual-ack generation time).
- **Single shared timeout** (`tts.chatterbox_timeout`, default 60s) covers
  both the HTTP request and (in the non-streaming `_speak_chatterbox`
  path) `aplay.communicate()`. No fast health preflight before the first
  request of a session — if the Chatterbox server is down, the user waits
  the full timeout before Piper fallback kicks in.
- `core/tts_cache.py` opens a new SQLite connection per `put()` call
  during bulk generation (~300 phrases at first boot) — works, just more
  I/O than necessary. Not thread-locked around `_memory` dict access;
  fine today (single writer thread) but fragile if cache writes are ever
  parallelized.
- `resolve_output_device()`'s `/proc/asound/cards` regex assumes simple
  card-description formatting; unverified against unusual card names.

## 4. Known duplicate / divergent code paths

- **Console vs. voice streaming**: `jarvis_console.py`'s
  `_stream_llm_console()` builds a `SpeechChunker` but only uses it to
  quality-gate the *first* sentence — it speaks the entire accumulated
  response in one `real_tts.speak()` call after the LLM finishes, unlike
  `core/pipeline.py` and `jarvis_continuous.py`/`jarvis_web.py`, which
  speak sentence-by-sentence as they stream. This means console/hybrid
  mode has no gapless streaming playback and noticeably higher
  time-to-first-audio. Likely fine (console is a dev tool), but anyone
  optimizing perceived latency should know console numbers don't
  generalize to production runtime.
- **Legacy `.bak-*` files**: `core/`, repo root and `config.yaml` had ~25
  ad-hoc backup files (`foo.py.bak-livefix`, `config.yaml.bak-20260914-...`)
  from manual pre-edit snapshots during earlier sessions — none tracked in
  git (all covered by `.gitignore`'s `*.bak-*` rule), pure clutter since
  real history already lives in git commits. Moved to
  `legacy_backups_20260915/` at the repo root this session (not deleted —
  irreversible-destruction guard declined an `rm -rf`; safe to delete for
  good once you're satisfied nothing in them is needed).

## 5. Decisions & why

| Decision | Reason |
|---|---|
| `people_manager` now registers pronunciation overrides on `tts_normalizer_de`, not `tts_normalizer` | Was wired to the unused English normalizer — pronunciation overrides for known people's names silently never applied to actual (German) speech. Pure bug fix. |
| `StreamingAudioPipeline` generalized to Chatterbox | Chatterbox is the active engine; blocking sequential generate-then-play was the largest latency source in the whole pipeline. |
| Ack/CAL-L0 caches now built for Chatterbox too, in background threads | Instant filler/greeting audio previously only existed for the (inactive) Kokoro engine. Background, not blocking init, because each phrase is a real GPU call unlike Kokoro's CPU synth. |
| Cache version string is engine-tagged | Prevents a cached-under-Kokoro phrase from silently playing back in Chatterbox's voice (or vice versa) after an engine switch. |
| Chatterbox tempo/generation params moved to `CHATTERBOX_*` env vars, overridable per-request | `tools/chatterbox_server.py` is a separate process that doesn't read `config.yaml`; hardcoded constants made tuning (and a future vocal-behavior layer) impossible without editing the server file. |
| `chatterbox_server.py`'s ffmpeg tempo step now pipes raw PCM in/out (not WAV) | ffmpeg can't patch a WAV's RIFF size field on a non-seekable pipe — piping WAV out produced a technically-malformed (streaming-size) header. Raw PCM has no such field; the server builds the final WAV itself with a correct header. |
| `HTTPServer` (not threaded) in `chatterbox_server.py` | Deliberate — the GPU model can't serve two `generate()` calls concurrently. Don't "fix" this by switching to `ThreadingHTTPServer`. |
| German thousands-grouping normalizer runs before decimals | German uses `.` for thousands, `,` for decimals — opposite of English. Order matters; see §3.3. |

## 6. Conventions

- Config access: dotted-path `config.get("tts.chatterbox_endpoint", default)`
  (`core/config.py`). Never read `config.yaml` directly in application code.
- Logging: `core.logger.get_logger(__name__, config)`; per-subsystem debug
  levels are toggled in `config.yaml`'s `logging.modules` block (commented
  out by default — uncomment to enable).
- TTS engine selection is a single switch (`tts.engine` in config.yaml:
  `chatterbox` | `kokoro` | `piper`); `TextToSpeech` dispatches internally,
  application code should never branch on engine name itself except inside
  `core/tts.py` / `core/pipeline.py`'s `StreamingAudioPipeline`.
- Tests: mix of pytest-style (`tests/unit/test_router.py`,
  `tests/unit/test_tts_normalizer_de.py`) and a custom case-driven runner
  (`tests/unit/test_edge_cases.py`, run via
  `python3 tests/unit/test_edge_cases.py --phase <id>`). Both live under
  `tests/unit/`.

## 7. Open work / recommended next steps

Roughly in priority order — see §3.4 for the detailed TTS-specific list.

1. Decide the fate of `core/tts_normalizer.py` (unused English normalizer) —
   delete, or document as intentionally-kept groundwork for a future
   English mode.
2. Chatterbox health preflight + split connect/read timeout, so a down
   TTS server fails over to Piper in ~1-2s instead of up to 60s.
3. Cancellable/bounded contextual-ack synthesis so a slow Chatterbox ack
   can't delay the real response's first audio chunk.
4. Vocal-behavior layer: now that `chatterbox_server.py` accepts
   per-request `exaggeration`/`cfg_weight`/etc. overrides, design the
   policy that decides when to use them (e.g. per persona mood, per
   response category).
5. Delete `legacy_backups_20260915/` once confirmed unneeded.
6. `tests/unit/test_edge_cases.py` phase 7C-03 (`"Dr. Smith..."`) asserts
   Chatterbox-era chunking behavior that predates the abbreviation guard —
   the test itself expects the split IS made; it's a stale test, not a
   pipeline bug. Update the expectation rather than "fixing" the chunker.
