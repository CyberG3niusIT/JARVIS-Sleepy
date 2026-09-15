# JARVIS — Architecture & Project Memory

Persistent technical reference for anyone (human or agent) picking up this
project cold. Complements [`DEVELOPMENT.md`](DEVELOPMENT.md) (repo/workflow
mechanics) — this file is about *what the system is, why it's built this
way, and what's known to be broken or half-done*. Keep it current: when you
make an architectural decision or find a real bug, write it here, not just
in a commit message.

Last major update: 2026-09-15 (Claude active-refactor session #3, branch
`claude/jarvis-architecture`, on top of `79d7b78`; safepoint `3a58c9e` / tag
`sleepy-pre-claude-20260915`).

**Persona note (clarified explicitly by the user this session, don't
"fix" this again):** German-first does NOT mean removing "Sir"/"Ma'am".
JARVIS's persona is deliberately a German-speaking British-butler-adjacent
character — "Guten Morgen, Sir.", "Alles klar, Sir.", "Natürlich, Sir." are
all correct and desired. German-first means: sentence structure, error
messages, reminders, memory output, and tool confirmations are German;
individual persona-defining address terms in English ("Sir", "Ma'am",
"JARVIS") are not a violation of that. What IS still wrong: a whole
English *sentence* ("Good morning, Sir." / "Standing by, Sir." / "I didn't
catch that.") — that's the actual bug class this and the previous session
fixed. Vary the phrasing (don't say "Sehr wohl" as the *only* acknowledgment
— see `core/persona.py`'s German pools for the intended range of tone) but
don't strip the honorific.

**IMPORTANT — upstream sync pattern**: this fork tracks
`upstream = InterGenJLU/jarvis` and periodically merges "Sync: ..." commits
from it. `core/tts.py` and `core/persona.py` in particular receive frequent
upstream syncs and are English by default. German content for both lives in
an **override patch appended after the English-authored content**, applied
via a straight attribute/dict reassignment (`TextToSpeech._CAL_L0_TEMPLATES = [...]`,
`_POOLS.update({...})`), not edited in place — this is an established
convention (see `core/responses.py`'s `ResponseLibrary.__init__ = _response_init_de`,
which predates this session) specifically so a future `git merge upstream/main`
doesn't produce a line-level conflict inside a 100+ line English literal.
**When adding German content to an upstream-synced file, follow this
pattern — do not edit the English lists/dicts in place.**

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

It also exposes `GET /health` (liveness) and `GET /config` (the resolved
`CHATTERBOX_*` env-var values as JSON) — the client uses `/config` to build
the cache-voice fingerprint (see §3.2) and `/health` for a fast, throttled
liveness probe (`TextToSpeech._chatterbox_available()`, re-checked every 5s
when healthy / every 1s when down) so a dead server is detected in ~1.5s
instead of only after the full `chatterbox_timeout` (60s) elapses on a real
request.

### 3.1a Producer/consumer streaming + per-chunk Piper fallback

`core/pipeline.py`'s `StreamingAudioPipeline` for Chatterbox is a genuine
two-thread producer/consumer, not a single thread that generates-then-writes:

- The pipeline's own thread (`_run()`) is the **producer**: pulls sentence
  text off `_text_queue`, calls `tts._chatterbox_generate_pcm()`, and
  submits the resulting PCM to a `_ChatterboxAudioWriter`.
- `_ChatterboxAudioWriter` runs in its **own thread** and is the sole owner
  of the persistent `aplay` process — it just pulls PCM off an internal
  queue and writes it, in order.

This split matters because a single `aplay.stdin.write()` can block on pipe
backpressure until `aplay` has drained enough of its buffer — with the old
single-thread design, "generate sentence N+1 while N plays" was only
*usually* true (whenever generation happened to outrun the write), not
structurally guaranteed. With the writer in its own thread, the producer's
only blocking call is the Chatterbox HTTP request and the writer's only
blocking call is the pipe write — they run concurrently for real.

If `tts._chatterbox_generate_pcm()` fails for one sentence (server hiccup,
one bad chunk), the producer does **not** drop that sentence or abort the
response: it falls back to `tts._piper_generate_pcm()` for that one chunk,
logs clearly, and continues streaming subsequent chunks through Chatterbox
normally. If Piper also fails, the chunk really is lost (logged as an
error) rather than hanging the stream. Piper's native sample rate (22050Hz)
differs from Chatterbox's (24000Hz); if a fallback chunk's rate doesn't
match whatever rate the `aplay` session was already opened at, the writer
resamples it via `tts._resample_pcm()` (ffmpeg, s16le in/out) before
writing — otherwise it would play back pitch-/speed-shifted.
`kill_active()` still works as a cancellation mechanism: killing the
tracked `aplay` process makes the writer's next `stdin.write()` raise
`BrokenPipeError`, which it catches and exits cleanly (no deadlock); the
producer notices `writer.error` is set and stops generating further
doomed chunks.

Kokoro's branch is unchanged (still directly writes its own sub-chunks) —
it doesn't need this because Kokoro's generator already yields many small
audio sub-chunks per sentence, which are cheap to write and interleave
with generation for free.

Tested with fakes (no GPU/network) in `tests/unit/test_streaming_audio_pipeline.py`:
ordering guarantees, mid-stream fallback, both-engines-fail handling,
sample-rate mismatch resampling, and interrupt/kill_active not hanging.

### 3.1b Bounded PCM queue (this session)

`_ChatterboxAudioWriter`'s internal PCM queue (producer → writer handoff,
distinct from `StreamingAudioPipeline._text_queue`, which holds cheap
sentence *text* and stays unbounded — not worth bounding) used to be a
plain unbounded `queue.Queue()`: a fast producer (many short sentences)
generating faster than `aplay` drains them in realtime could pile up
unlimited PCM in RAM.

Now `maxsize=4` (a few sentences of read-ahead — enough to keep the
pipeline full without unbounded growth). `submit()` and the internal
sentinel-delivery in `finish_and_wait()` both go through a shared `_put()`
that retries `queue.put(item, timeout=0.5)` in a loop rather than blocking
indefinitely, re-checking a `threading.Event` (`_stopped`, set by the
writer thread on exit — error or normal drain) each time it times out.
This makes bounding safe against the two ways an unbounded-wait-on-full-
queue could otherwise deadlock: a producer stuck handing off audio to a
writer that already died (submit() returns `False`, the producer's loop
in `StreamingAudioPipeline._run()` checks this and stops generating), and
`finish_and_wait()` itself trying to deliver the `None` sentinel into a
full queue with a dead consumer on the other end. Real backpressure (a
full queue blocks `submit()`, so the producer genuinely slows to match
playback rate) without the deadlock risk a naive bounded queue would add.

Tested in `tests/unit/test_streaming_audio_pipeline.py::TestBoundedQueueBackpressure`:
a slow/stuck consumer actually blocks the producer (bounded, not
unbounded), no data loss or reordering under backpressure, a "crashed"
consumer (aplay fails to open) is detected by `submit()` within the
0.5s poll interval instead of hanging, and `finish_and_wait()` doesn't
deadlock on a full queue once the writer is force-stopped.

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
before the previous session — Chatterbox got no instant playback for
anything, meaning every ack/greeting paid a full GPU round-trip. Both now
go through an engine-dispatching `TextToSpeech._synthesize_short_pcm()` and
are built in background threads at Chatterbox init too (blocking startup on
~300 GPU round-trips would be unacceptable, unlike Kokoro's sub-second CPU
synthesis). `_build_ack_cache()` builds into a local dict and publishes it
with one atomic reference swap (`self._ack_cache = new_cache`) rather than
mutating in place, and `speak_ack()` snapshots the reference once at the
top instead of re-reading `self._ack_cache` mid-function — fixes a
"dict changed size during iteration" crash risk from the background build
racing a concurrent read.

The on-disk cache version is a **fingerprint**, not just the engine name:
`TextToSpeech._cache_voice_version()` returns
`f"{_CAL_L0_SCHEMA_VERSION}-{engine}-{fingerprint}"`, where for Chatterbox
the fingerprint is a hash of the server's `/config` response (added this
session specifically for this — see §3.1) and for Kokoro it's a hash of
the configured voice blend/speed. This is deliberately more than just the
engine name: restarting `chatterbox_server.py` with different
`CHATTERBOX_EXAGGERATION`/`CFG_WEIGHT`/tempo env vars changes what the
cached audio actually sounds like, and the client (a separate process)
has no other way to know that happened — the fingerprint round-trip is
how it finds out and invalidates stale entries instead of silently
replaying audio generated under the old voice.

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

Normalizer pass order (`GermanTTSNormalizer.__init__`, `self.normalizations`
dict, insertion-ordered): markdown → dates → times → ipv4 → **phone_numbers**
→ **ports** → temperatures → file_sizes → currency → percent → urls →
numbers (thousands-grouping + decimals + plain integers, unified) →
technical. Two sessions of fixes here, all with regression tests in
`tests/unit/test_tts_normalizer_de.py`:

- **Thousands vs. decimal** (previous session): German groups thousands
  with `.` (`10.000` = *zehntausend*) while `,` is the decimal separator —
  conflating them used to read "10.000" as *zehn Komma null null null*.
  All unit-bearing normalizers (currency/percent/temperature/file-size)
  and the general bare-number pass share one `_NUMBER_TOKEN` regex +
  `_german_number_to_words()` so a multi-group amount like `"1.234,56 €"`
  is captured as one token (a per-normalizer regex used to only match the
  last 3-digit group and leave a stray `"1."` in the output).
- **Numbers at the end of a sentence were never normalized at all**
  (this session, high-severity — sentence-final numbers are extremely
  common: "Die Antwort ist 42."). The general number regex's trailing
  lookahead was `(?![\w.,])`, meant to stop a match from swallowing part
  of a bigger adjacent number — but since `_NUMBER_TOKEN`'s alternation
  and the *leading* lookbehind already fully handle that, the trailing
  exclusion of a bare "." or "," just meant a number directly followed by
  its own sentence period (the overwhelmingly common case) never matched
  at all. Changed to `(?!\w)(?!\.\d)` — still blocks a following letter/
  digit (so "3D" isn't mangled) and still blocks a following "`.`+digit"
  (so a standalone multi-dot version number like "3.5.2" is left alone
  entirely rather than becoming "drei Komma fünf.2") — but a bare
  trailing "." or "," (sentence end, list comma) now matches correctly.
- **Ports and phone numbers read as giant cardinal numbers** (this
  session): `"port 8080"` was becoming *"achttausendachtzig"* instead of
  *"acht null acht null"* — correct for a quantity, wrong for an
  identifier. Added `normalize_ports` (`port[:\s]+digits` → digit-by-digit,
  must run before the general number pass) and `normalize_phone_numbers`
  (digit-by-digit for a leading `+` international prefix or a leading `0`
  domestic number with ≥7 digits — narrow trigger deliberately, so an
  ordinary large quantity like "100000 Einwohner" is never mistaken for a
  phone number).
- Not touched (documented, not a regression): URLs with a path/query
  (`normalize_urls` only speaks the domain, "/path?x=1" stays literal),
  RFC-style numbers (read as one cardinal, arguably fine), email
  addresses (no normalization at all — TTS engine's native G2P handles
  "@"/"." as best it can). None of these came up as a concrete
  requirement; flagging so a future session doesn't assume they're
  already handled.

`core/speech_chunker.py`'s abbreviation list (periods that don't end a
sentence) was English-only; German LLM output routinely contains `z.B.`,
`usw.`, `bzw.` etc., which used to trigger a false mid-sentence split and
chop prosody. German abbreviations added in the previous session.

### 3.4 Known TTS issues not yet fixed

- **Contextual ack latency on Chatterbox**: `Pipeline._play_ack_if_still_thinking()`
  can speak a dynamically LLM-generated (4B model) contextual ack via
  `self.tts.speak()`. This text is novel per-command, so it can't be
  pre-cached. On Chatterbox this means a real GPU round-trip inside the
  ack timer thread, which holds `TextToSpeech._tts_lock` — the main
  response's first real chunk then queues behind it. Still open (would
  need a cancellable/async HTTP request or a hard time budget on
  contextual-ack generation — the health-check throttle added this
  session doesn't help here since the server *is* up, just slow).
- ~~Single shared timeout...~~ **Fixed** (previous + this session):
  `_chatterbox_available()` probes `/health` with a short (1.5s) timeout,
  throttled (5s re-check when healthy, 1s when down), before every
  request. A **circuit breaker** on top (this session):
  `_chatterbox_record_failure()`/`_record_success()` track consecutive
  real `/tts` request failures (not health-check misses); after 3 in a
  row the circuit opens for 15s and `_chatterbox_available()` returns
  False immediately without even the health probe. A server that's up
  per `/health` but erroring on every generation (not just fully down)
  now also gets a fast, bounded backoff instead of a full request-and-
  timeout per utterance. The 60s `chatterbox_timeout` still applies to
  actual generation once a request is attempted (correctly — genuine
  GPU generation of a long response can legitimately take a while) —
  separated from a new, short `chatterbox_connect_timeout` (default 2s):
  `core/tts.py` switched from `urllib.request` to a persistent
  `requests.Session()` (already a project dependency, no new one added)
  specifically so connect and read timeouts can differ
  (`timeout=(connect, read)`), and so the underlying TCP connection is
  reused across sentences (keep-alive pooling) instead of a fresh
  handshake per utterance.
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
| All unit-bearing normalizers (currency/percent/temperature/file-size) share one `_NUMBER_TOKEN` regex + `_german_number_to_words()` | The old per-normalizer regexes only matched a single thousands-group, so "1.234,56 €" matched just "234,56 €" and left a stray literal "1." in the spoken output. One shared token fixes it structurally instead of patching each normalizer separately. |
| Chatterbox streaming uses a dedicated writer thread (`_ChatterboxAudioWriter`), not direct writes from the generation thread | A single `aplay.stdin.write()` can block on pipe backpressure, so "generate N+1 while N plays" wasn't structurally guaranteed with one thread doing both. Splitting them makes the overlap real. |
| Chatterbox chunk failures fall back to Piper per-chunk inside the stream, not just at the top-level `speak()` call | Silently dropping a sentence mid-response is worse than a voice/quality blip; matches the explicit "never lose a sentence" requirement. |
| Health-check is throttled (5s healthy / 1s down), not per-request | A per-request health check would double request latency on the happy path; throttling keeps the fast-fail benefit without that cost. |
| German content added to upstream-synced files (`core/tts.py`, `core/persona.py`) as an appended override patch, never edited in place | Matches the pre-existing convention in `core/responses.py`; keeps `git merge upstream/main` conflict-free instead of fighting a large literal diff on every sync. See top of this doc and §5a. |
| Chatterbox PCM queue bounded (`maxsize=4`), with a poll-and-check-stopped loop instead of a plain blocking `put()` | Real backpressure needs a bound; a naive bound risks deadlocking `submit()`/`finish_and_wait()` against a dead consumer, so both go through the same stoppable `_put()`. |
| `core/tts.py` switched from `urllib.request` to a persistent `requests.Session()` | `requests` was already a project dependency (no new one added); gives connection-pooling/keep-alive across sentences and native separate connect/read timeouts, neither of which `urllib.request` supports cleanly. |
| Chatterbox circuit breaker tracks real `/tts` failures separately from health-check misses | A server that's up per `/health` but erroring on every generation needs its own backoff — the health throttle alone wouldn't catch that case. |
| General-number regex's trailing lookahead changed from `(?![\w.,])` to `(?!\w)(?!\.\d)` | The old version silently skipped every sentence-final number (the single most common way a number appears in speech) because a bare trailing period was (unnecessarily) treated the same as a period that's part of a bigger number — the alternation and leading lookbehind already handle that case. |
| `is_candidate()` gates on confidence only, not `source == "explicit"` | An inferred fact must be promotable purely through repeated evidence (reinforcement raising its confidence) without ever requiring the user to state it explicitly — matches the requested "promotion via repeated confirmed pattern" path. |
| Memory contradiction/dedup detection kept on the existing subject-key matching, NOT extended with text-similarity | Measured on realistic pairs, text similarity scores a real contradiction ("editor is VS Code" vs "editor is Cursor") as *more* similar (0.88) than a paraphrase of the same fact ("Alex bevorzugt DHL" vs "...nutzt am liebsten DHL", 0.50) — backwards from what's needed. Comparing the extracted subject key (already separate from the value) doesn't have this problem. See §5c. |

## 5a. German-first audit (2026-09-15)

JARVIS's *active* spoken output must be German — `system.language: de-DE`,
no English fallback. `core/persona.py`'s response pools were already fully
German (a `_POOLS.update({...})` override with a redefined `pick()`, applied
after the English upstream content — same pattern as `core/responses.py`).
What was NOT yet German, found and fixed this session:

- `core/tts.py`'s `_CAL_L0_TEMPLATES` (~170 canned phrases: greetings,
  farewells, acknowledgments, small talk) — never localized when
  Chatterbox/CAL-L0 landed, entirely English. Migrated via the same
  override-patch convention (`TextToSpeech._CAL_L0_TEMPLATES = [...]`,
  see the top-of-file note on the sync pattern). Deliberately avoids
  "Sehr wohl, Sir" / "Zu Diensten, Sir"-style stiff butler-calques.
- `core/responses.py`'s existing German override still had two literal
  `"Sehr wohl, {honorific}."` entries (acknowledgment/farewell pools) —
  replaced with `"Alles klar, {honorific}."`.
- `core/reminder_manager.py`: daily/weekly rundown intros, missed-reminder
  catch-up announcements, and the per-reminder announcement builder
  (priority prefix + "in X minutes/hours" time phrase) were English —
  this fires on *every* reminder, so it was actually higher-traffic than
  CAL-L0. Fully translated, including correct German plural forms for the
  time phrase (`_de_unit()` helper: "in 3 Stunden und 20 Minuten").
- `core/memory_manager.py`: `confirm_forget()`, `cancel_forget()`, and the
  "no facts found" guards in `handle_transparency()`/`list_facts_by_category()`
  translated. **Not** translated: the parts of `handle_transparency()` and
  the multi-fact "I found N stored facts..." listing that interpolate
  `_fact_to_phrase()` output — see §5b, facts are stored as English
  sentences, so translating only the wrapper text would produce mixed-
  language output, which is worse than leaving it consistently English.
- `core/llm_router.py`: two spoken fallback strings in `_clean_llm_output()`
  (a "the LLM leaked its prompt" recovery path). Note: the pattern list
  that path uses to detect *where* a leaked English prompt starts
  (`"You are JARVIS"`, `"Good morning, {h}"`, ...) is itself stale — the
  real system prompt (`persona.system_prompt()`) has been German for a
  while, so this detection logic likely never matches in practice
  anymore. Not touched (speculative behavior change, out of scope).
- **Functional bugs, not just cosmetic** — `skills/system/developer_tools/skill.py`
  and `skills/system/file_editor/skill.py`'s destructive-action
  confirmation flows (`confirm_action()`) matched only English
  affirmative/negative words (`{'yes', 'go ahead', ...}` / `{'no', 'cancel', ...}`).
  A German user saying "ja" or "nein" matched neither set, so confirming
  or cancelling a pending destructive command (delete a file, run a shell
  command) silently fell through to "I didn't catch that" every time.
  Added German words to both sets (German first, English kept as
  fallback) and translated the surrounding strings. Same fix pattern in
  `skills/personal/reminders/skill.py`'s `cancel_reminder()` fragment-
  extraction regex, which only stripped English prefixes ("cancel the
  reminder about...") — German "lösche die Erinnerung an..." wasn't
  stripped, so the search fragment used to match against stored reminder
  titles was wrong.
- `skills/personal/reminders/skill.py`: remaining ~13 user-facing strings
  (set/list/cancel/acknowledge/snooze reminder) translated.

**Explicitly NOT done this session** (documented, not silently skipped):

- `skills/system/file_editor/skill.py` has ~50 more English response
  strings beyond the confirmation-flow fix (file creation/deletion/
  editing/printing/document-generation messages). This is a large,
  self-contained translation task — deferred to its own pass rather than
  rushed here. Grep `self\.honorific}` in that file to find them.
- `skills/system/developer_tools/skill.py` likely has more beyond what
  was touched (35 total `self.honorific}` occurrences found, only the
  confirmation flow + one "what to display" line fixed).
- `skills/personal/conversation/skill.py` — a near-duplicate of
  `core/persona.py`'s pools, all English, purpose/active-status
  unconfirmed (not referenced from a skill manifest with an obvious
  enabled flag in this pass — worth checking whether it's dead code or
  a genuinely separate active path before translating).
- The **honorific default itself is `"sir"`** (`core/honorific.py`,
  `_current_honorific = "sir"`, and `"sir"`/`"ma'am"` hardcoded at ~15
  call sites across `reminder_manager.py`, `presence_detector.py`,
  `conversation_router.py`, `pipeline.py`, both entry points). With
  `user_profiles.voice_recognition: false` in config, this fallback is
  what actually gets used in every interaction today, and it's woven
  into essentially every spoken template. Whether "Sir"/"ma'am" as an
  intentional charming Anglicism is *wanted* (part of the persona brief:
  "ruhig, kompetent, trocken, leicht humorvoll") or should become a
  German/neutral default is a **persona/brand decision for the user**,
  not something to change unilaterally — flagged, not changed.
- Regex-based fact extraction (`core/memory_manager.py`) stores facts as
  English third-person sentences ("the user loves the band Tool") — see
  §5b. Fixing this properly means redesigning extraction + storage
  format, not a string-level translation.
- `intent_examples` (semantic-matching training phrases, e.g. in
  `skills/personal/reminders/skill.py`) are still English-phrased. Left
  as-is per the task's own framing: input-recognition phrasing isn't the
  priority, output speech is (German STT already transcribes German
  input fine regardless of what language the matching examples are
  written in).

New regression test: `tests/unit/test_german_first_active_path.py` — fails
if any of the specific previously-confirmed banned English phrases
reappear in the CAL-L0 templates, persona pools, or `ResponseLibrary`
(guards against a future upstream sync silently reintroducing them).

## 5b. Memory architecture map (read-only audit, 2026-09-15)

No code changes here — this is a map + findings, per the explicit
instruction not to rebuild subsystems without real need. Five *separate*
SQLite databases are involved in what's conceptually "memory":

| DB | Owner | Contents |
|---|---|---|
| `memory.db` | `core/memory_manager.py` **and** `core/context_window.py` (shared file, different tables) | long-term facts (+ FAISS index alongside), topic-segmented working context |
| `interaction_cache.db` | `core/interaction_cache.py` | typed interaction/tool-result artifacts |
| `people.db` | `core/people_manager.py` | known people, pronunciation, relationships |
| `reminders.db`, `news_headlines.db` | respective managers | not really "memory," but feed into awareness |

Flow: user utterance → `extract_facts_realtime()` (regex-pattern fact
extraction, <5ms budget, `core/memory_manager.py`) → SQLite (+ FAISS
embedding) → two retrieval paths:
1. **Passive background** (`get_full_user_context()`): unconditionally
   dumps up to 500 facts (~capped at 5000 tokens, semantic-top-50 +
   high-confidence fallback beyond that) into *every* prompt, regardless
   of relevance to the current utterance. This is a **deliberate design
   choice** (the docstring calls it out explicitly) — background
   knowledge the LLM should "just know," not scored per-query. Not a bug;
   worth revisiting only if context budget gets tight or the fact count
   grows large enough that 5000 tokens of constant overhead matters.
2. **Proactive surfacing** (`core/awareness.py`'s `AwarenessAssembler`):
   *is* exactly the relevance/recency/novelty-scored, token-budgeted,
   per-source-thresholded retrieval the task asked to verify exists —
   `score = 0.6·relevance + 0.3·recency + 0.1·novelty`, gated by
   `awareness.fact_threshold` / `interaction_threshold` / `news_threshold`,
   capped by `awareness.proactive_token_budget` (expands when context
   headroom allows), deduped within a conversation window. Already
   correctly implements the "relevant, not just big" requirement — this
   was already-good architecture, not a gap.

**Real finding**: facts are stored as complete English third-person
sentences ("the user loves the band Tool"), produced by English regex
extraction patterns, and `_fact_to_phrase()` only has a "convert to second
person" transform (English "the user" → "You"), not a language transform.
This is why `handle_transparency()` / the forget-confirmation fact listing
couldn't be safely translated this session (§5a) — the wrapper sentence
can be German, but the interpolated fact content can't be, without
redesigning extraction+storage. This is the single largest remaining
German-first gap, and it's an architecture-level fix (new extraction
patterns, probably a stored-language-neutral fact representation with
phrasing generated at read-time in the target language), not a quick win.

Dedup/contradiction resolution (traced through this session, see §5c):
`store_fact()` already had a working subject-based supersede mechanism
before this session — `_find_similar_fact()` matches on exact or
substring-fuzzy `subject`, and an exact-content match used to just no-op
(`return None`) while a same-subject-different-content match already
correctly superseded the old fact via `superseded_by`. This session added
candidate/confirmed tiers and reinforcement on top of it (§5c) without
touching that mechanism, and specifically did NOT add text-similarity-based
contradiction detection — see §5c for why that's actively the wrong tool.

## 5c. Memory candidate/confirmed tiers (implemented this session)

Additive on top of the existing fact store — no schema replacement, one
new column (`evidence_count`, migrated via `ALTER TABLE ... ADD COLUMN`
wrapped in `try/except sqlite3.OperationalError` since SQLite has no
`ADD COLUMN IF NOT EXISTS`).

- **`MemoryManager.is_candidate(fact)`**: `confidence < 0.80`
  (`CANDIDATE_CONFIDENCE_THRESHOLD`). Deliberately confidence-only, not
  gated on `source == "explicit"` — an inferred fact should be promotable
  purely through repeated evidence ("mehrfach bestätigtem Muster"),
  without ever requiring the user to state it outright. Explicit facts
  (confidence 0.90) start confirmed; inferred (0.70) and per-turn (0.75)
  start as candidates.
- **`_reinforce_fact()`**: when `store_fact()`'s existing dedup check
  finds an *exact* content match (previously a silent no-op), it now
  bumps confidence by `+0.05` (capped at `MAX_FACT_CONFIDENCE = 0.99`)
  and increments `evidence_count`, instead of discarding the repeated
  observation. Enough reinforcement naturally crosses the candidate
  threshold — that's the entire "promotion" mechanism; there's no
  separate promotion algorithm/state machine to keep in sync with it.
- **Subject normalization**: `store_fact()` now lowercases/strips
  `subject` before both the lookup and the insert. The exact-match branch
  of `_find_similar_fact()` does a case/whitespace-sensitive SQL
  comparison (`WHERE subject = ?`) — "Editor" and "editor " used to
  silently miss each other and fall through to the weaker substring-fuzzy
  path (or miss a supersede entirely). Old rows keep whatever casing they
  already have; this only fixes matching going forward.
- **Rejected approach, documented so it isn't re-attempted**: using text
  similarity (tried `difflib.SequenceMatcher`) to distinguish "same fact
  reworded" from "contradicting fact about the same topic" doesn't work —
  measured on realistic pairs: `"favorite editor is VS Code"` vs.
  `"favorite editor is Cursor"` (a **contradiction**) scores 0.88
  (high/"similar"), while `"Alex bevorzugt DHL"` vs. `"Alex nutzt am
  liebsten DHL"` (the **same fact**, paraphrased) scores only 0.50
  (low/"different"). Character-overlap similarity conflates topic
  closeness with content agreement — exactly backwards from what's
  needed. The existing subject-key approach (compare the *extracted
  subject*, e.g. `"editor"`, not the whole sentence) sidesteps this
  correctly, because same-subject-different-content is precisely what
  "contradiction" means once subject and value are separated. A
  semantic-embedding-based version of contradiction detection might work
  better than text-similarity, but couldn't be tuned/verified in this
  sandbox (no GPU/embedding model available) — noted as open work, not
  implemented speculatively.

**Not done, and why**: a separate `fact_candidates` table, explicit
`WORKING/SHORT_TERM/LONG_TERM` tier columns, and an autonomy-budget
governor (max candidates/promotions per session) from the original
memory-tier proposal were not built. The existing `facts` table's
`confidence` + new `evidence_count` already model the working/candidate/
confirmed distinction adequately for what's actually exercised today
(single fact store, no separate working-memory table exists or is
needed — `core/context_window.py` already serves the "current
conversation" working-memory role); adding parallel tier tables now would
be new architecture without a demonstrated need, which the task
explicitly asked to avoid. Revisit if/when actual usage shows the single-
table model isn't enough.

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

Roughly in priority order — see §3.4 for the detailed TTS-specific list,
§5a-c for German-first / memory specifics.

**Resolved this session (previously listed here, no longer open):**
honorific-default question — user confirmed explicitly: "Sir"/"Ma'am" stays,
it's an intentional persona element, not a German-first violation (see the
persona note near the top of this doc). Chatterbox connection reuse/circuit
breaker/connect-timeout — done (§3.4). Streaming queue backpressure — done
(§3.1b). Sentence-final numbers not normalized — fixed (§3.3, was a real
correctness bug). Ports/phone numbers read as cardinal numbers — fixed
(§3.3). Memory candidate/confirmed tiers + reinforcement — done (§5c).

1. Live GPU run of the Chatterbox streaming path (`_ChatterboxAudioWriter`
   producer/consumer, bounded queue, circuit breaker) — this environment
   has no CUDA, so all of it is verified with fakes/mocks
   (`tests/unit/test_streaming_audio_pipeline.py`,
   `tests/unit/test_chatterbox_client.py`) but not yet observed against
   the real server. Do this before relying on the latency win in
   production.
2. Cancellable/bounded contextual-ack synthesis so a slow Chatterbox ack
   can't delay the real response's first audio chunk (§3.4) — still open.
3. Finish `skills/system/file_editor/skill.py` (~50 strings) and audit
   `skills/system/developer_tools/skill.py` beyond the confirmation flow;
   determine whether `skills/personal/conversation/skill.py` is active or
   dead code before deciding whether to translate it too.
4. Redesign fact storage/extraction to not be English-sentence-shaped
   (§5b) — needed before memory-transparency responses can be fully
   German without mixed-language sentences. This blocks natural German
   output for `handle_transparency()` and the multi-fact forget listing
   specifically (see §5a for what's already safely translated around it).
5. Embedding-based contradiction detection for memory facts, evaluated
   properly against a real embedding model (§5c documents why the
   text-similarity approach that was tried doesn't work — don't repeat
   that attempt; a semantic-similarity version might work but needs
   real tuning this sandbox couldn't do).
6. Vocal-behavior layer: now that `chatterbox_server.py` accepts
   per-request `exaggeration`/`cfg_weight`/etc. overrides, design the
   policy that decides when to use them (e.g. per persona mood, per
   response category).
7. Decide the fate of `core/tts_normalizer.py` (unused English normalizer) —
   delete, or document as intentionally-kept groundwork for a future
   English mode.
8. Delete `legacy_backups_20260915/` once confirmed unneeded.
9. `tests/unit/test_edge_cases.py` phase 7C-03 (`"Dr. Smith..."`) asserts
   pre-abbreviation-guard chunking behavior — the test itself expects a
   split that the (correct) abbreviation guard now prevents; it's a stale
   test expectation, not a pipeline bug. Update the expectation rather
   than "fixing" the chunker.
10. **Real latency instrumentation — still not done, and still the single
    biggest gap against the stated "feels instantaneous" goal.**
    `core/pipeline.py`/`core/tts.py` emit some structured `event_logger`
    timing events (e.g. synthesis RTF) but there's no single wake→
    first-audio trace across VAD-endpointing/STT/intent/memory-retrieval/
    LLM-TTFT/chunking/TTS-TTFA stages, and — because this sandbox has no
    mic, GPU, STT model, or llama.cpp/Chatterbox server running — **no
    live measurement of any kind exists for any of this project's TTS,
    STT, LLM, or end-to-end latency claims.** Every "streamed faster",
    "fails over in ~1.5s", etc. statement in this doc is an architectural
    claim verified by code/mocks, not a measured one. Adding full-path
    `time.monotonic()` checkpoints + a p50/p95 rollup, then actually
    running it on the real Sleepy hardware, is required before any
    latency number in this project can be trusted.
11. STT hot-path (persistent model residency, adaptive endpointing), LLM
    TTFT (prompt/context size, prewarm, KV-cache reuse), and fast-paths
    for deterministic local commands (open app, set volume, etc. without
    the 35B model) were all explicitly requested but require either live
    hardware measurement or a larger design/implementation effort beyond
    what a code-only sandbox session can responsibly do — not started.
    Don't assume any of it is done; nothing in this bullet has been
    touched across any session so far.
12. Memory: no autonomy budget (max candidates/promotions per session),
    no explicit consolidation job (session-end/idle-triggered review of
    short-term → long-term), no decay (candidates with low confidence
    that age out un-reinforced) — §5c's reinforcement mechanism only
    covers "the exact same fact observed again," it doesn't yet decay
    stale unreinforced candidates over time. All explicitly requested;
    not built this session — the additive tier/reinforcement work in §5c
    was judged the highest-value, lowest-risk slice to ship now.
