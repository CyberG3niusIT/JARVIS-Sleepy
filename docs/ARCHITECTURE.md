# JARVIS — Architecture & Project Memory

Persistent technical reference for anyone (human or agent) picking up this
project cold. Complements [`DEVELOPMENT.md`](DEVELOPMENT.md) (repo/workflow
mechanics) — this file is about *what the system is, why it's built this
way, and what's known to be broken or half-done*. Keep it current: when you
make an architectural decision or find a real bug, write it here, not just
in a commit message.

Last major update: 2026-09-15 (Claude active-refactor session #2, branch
`claude/jarvis-architecture`, on top of `1558e8b`; safepoint `3a58c9e` / tag
`sleepy-pre-claude-20260915`).

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
  response's first real chunk then queues behind it. Still open (would
  need a cancellable/async HTTP request or a hard time budget on
  contextual-ack generation — the health-check throttle added this
  session doesn't help here since the server *is* up, just slow).
- ~~Single shared timeout...~~ **Fixed this session**: `_chatterbox_available()`
  probes `/health` with a short (1.5s) timeout, throttled (5s re-check
  interval when healthy, 1s when down), before every request — a down
  server now fails over to Piper in ~1.5s instead of up to 60s. The
  60s `chatterbox_timeout` still applies to the actual generation
  request once the health check passes (correctly — genuine GPU
  generation of a long response can legitimately take a while).
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

Not audited in depth this session (time-boxed): deduplication of
near-identical facts, update-vs-append semantics when a fact changes
("VS Code" → "Cursor"), and conflict resolution — `delete_fact()` /
`_pending_forget` exist, but whether new extraction auto-detects "this
contradicts an existing fact" wasn't traced through.

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

Roughly in priority order — see §3.4 for the detailed TTS-specific list and
§5a/§5b for German-first / memory specifics.

1. Live GPU run of the new Chatterbox streaming path (`_ChatterboxAudioWriter`
   producer/consumer) — this session's environment had no CUDA, so it's
   verified with fakes/mocks (`tests/unit/test_streaming_audio_pipeline.py`)
   but not yet observed against the real server. Do this before relying on
   the latency win in production.
2. Cancellable/bounded contextual-ack synthesis so a slow Chatterbox ack
   can't delay the real response's first audio chunk (§3.4).
3. Decide the honorific-default question (§5a) — "sir"/"ma'am" is a
   persona/brand call, not something to change unilaterally.
4. Finish `skills/system/file_editor/skill.py` (~50 strings) and audit
   `skills/system/developer_tools/skill.py` beyond the confirmation flow;
   determine whether `skills/personal/conversation/skill.py` is active or
   dead code before deciding whether to translate it too.
5. Redesign fact storage/extraction to not be English-sentence-shaped
   (§5b) — needed before memory-transparency responses can be fully
   German without mixed-language sentences.
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
10. Real latency instrumentation: `core/pipeline.py` and `core/tts.py`
    already emit some structured `event_logger` timing events (e.g.
    Kokoro/Chatterbox synthesis RTF), but there's no single, complete
    wake→first-audio latency trace across STT/LLM-TTFT/chunking/TTS-TTFA
    stages, and no live measurements exist for this session (no
    mic/GPU/STT model available in this sandbox to run the real voice
    loop). Adding full-path `time.monotonic()` checkpoints + a p50/p95
    rollup, then actually running it on the real WSL2 box, is real
    future work — not done here to avoid reporting fabricated numbers.
11. STT hot-path (persistent model residency, adaptive endpointing),
    LLM TTFT (prompt/context size, prewarm), and fast-paths for
    deterministic local commands (open app, set volume, etc. without the
    35B model) were all explicitly requested but require either live
    hardware measurement or a larger design/implementation effort beyond
    this session's scope — not started. See task history for the full
    list of what was asked; none of it should be assumed done.
