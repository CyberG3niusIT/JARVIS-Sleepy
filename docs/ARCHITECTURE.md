# JARVIS — Architecture & Project Memory

Persistent technical reference for anyone (human or agent) picking up this
project cold. Complements [`DEVELOPMENT.md`](DEVELOPMENT.md) (repo/workflow
mechanics) — this file is about *what the system is, why it's built this
way, and what's known to be broken or half-done*. Keep it current: when you
make an architectural decision or find a real bug, write it here, not just
in a commit message.

Last major update: 2026-09-21 (Claude session #8, same branch
`claude/jarvis-sleepy-backend-rc-nhtfgm`, starting from `6ef9e4a` —
verified via `git status`/`git log`/`git diff` against `origin/main`
before any change; working tree was clean, 23 commits ahead of
`origin/main`, 0 behind). Ran with **no shell access to the real
Sleepy machine**, same as sessions #5-#7 — every "NEEDS HW VERIFY" tag
still means exactly that.

**Session #8 — security/agentic-runtime/proactive-core pass.** Opened
with four required findings, all reproduced with real exploit strings
or a standalone repro before any fix, all fixed and covered by new
regression tests:

1. **CRITICAL — developer_tools' command safety classifier
   (`skills/system/developer_tools/_safety.py`) was still exploitable
   after session #7's chain-operator fix.** Reproduced 12 bypasses:
   `find -delete`/`-exec`, `git branch -D`, `git remote add`/`set-url`,
   `git tag -d`, `curl -T`/`-o` to arbitrary paths, `wget --post-file`,
   and three `xargs`-piped-destructive-command cases (`ps aux | xargs
   kill -9`, `ls | xargs rm`, `find . | xargs rm -f`) — all classified
   `'allowed'` because the classifier only ever inspected the first
   one or two words of a command and never split on `|` at all.
   Redesigned rather than patched further: chain-split (unchanged
   policy from #7) → pipe-split every chain segment via shlex
   tokenization (quote-aware) → argument-sensitive validators
   dispatched by command name (find, git subcommands, curl/wget
   including `--flag=value` attached forms, xargs — recursively
   classifies its target command, systemctl, pip/apt/dpkg/docker) →
   tier-set fallback for everything else → default-deny
   ('confirmation') for anything unclassifiable. 44 tests (24 new).
   `_run_cmd()` still uses `shell=True` — required for the pipe/
   redirect semantics the classifier now actually validates
   segment-by-segment; a full subprocess-pipeline executor to drop
   `shell=True` entirely was out of scope.
2. `core/tools/developer_tools.py`'s `run_command`/`confirm_pending`
   used a hardcoded, stale `cwd='/home/user/jarvis'`. No single
   "jarvis home" config key exists to read this from, so the fix
   derives it from the module's own file location instead
   (`_JARVIS_ROOT`, two directories up from `core/tools/
   developer_tools.py`) — correct in this sandbox and on real
   hardware, nothing to keep in sync by hand, no new hardcode.
3. **Privacy logging audit.** `tool_registry.execute_tool()`'s own
   `logger.debug()` logged full tool arguments *before* the
   `CONTENT_LOGGING` gate that session #7 only applied to its
   `event_logger.emit()` call further down — the exact bug named in
   the task. Fixed, plus three more content-bearing, ungated sites
   found in the same audit pass: `core/llm_router.py`'s
   `stream_with_tools()` (LLM tool-call arguments, both call sites —
   extracted into a shared `_log_tool_call()` helper for direct
   testability), `core/tool_gate.py`'s classifier-skip log (up to 80
   chars of raw query), `core/tools/generate_image.py`'s
   image-generation prompt. A broader follow-up audit (background
   subagent) found a much larger separate content-logging surface —
   see §14 item 13 — deliberately NOT touched here (out of this
   finding's tool/skill-log scope, and two of the biggest offenders,
   `core/continuous_listener.py`/`core/pipeline.py`, import
   `sounddevice` and cannot be imported or exercised at all in this
   sandbox).
4. **`PrivacyControlWatcher`'s sentinel files lived directly under
   `/tmp`** (world-writable — any local user on the host, not just the
   one running jarvis, could create a same-named file and flip this
   process's privacy mode). Now resolves a user-private runtime
   directory (`$XDG_RUNTIME_DIR/jarvis` / `/run/user/$UID/jarvis` when
   available, else a self-created, ownership-and-symlink-validated
   `/tmp/jarvis-$UID` fallback) — same sentinel-file mechanism, no new
   IPC layer, just a directory only this user can write to.

After the four required findings, continued into the still-open
agentic-runtime items from session #7's audit (§14 item 13) with two
concrete, bounded, tested pieces — **not** the full unified
Skill/Tool/MCP capability-permission model (see §14 item 13a for why
that was deliberately not attempted this session):
- **TaskPlanner cooperative mid-step cancellation.** Previously
  `cancel()` only took effect *between* plan steps; a step already in
  flight (e.g. a multi-page web-research fetch) always ran to
  completion. Added a thread-local cancellation token
  (`current_cancel_event()`) published for the duration of
  `execute_plan()`, which a genuinely interruptible tool may poll
  between its own internal sub-steps — cooperative, not a thread kill.
  `core/web_research.py`'s `fetch_pages_parallel()` is the first real
  consumer: it now stops collecting further pages once cancelled,
  returning whatever was already fetched.
- **Watchdog background-worker visibility.** Previously zero
  visibility outside the voice pipeline — a crashed reminder/weather/
  news poll thread or a stuck TaskPlanner step went unnoticed by
  anything. `Watchdog` now optionally takes `task_planner`/
  `reminder_manager`/`weather_poller`/`news_manager` references and
  detects dead threads, stale (stuck) poll loops, and plan steps stuck
  past `command_hung_threshold` — detection + structured-event logging
  only, deliberately no auto-restart (a blind restart could have side
  effects, e.g. re-firing a reminder, this watchdog can't reason about
  safely).

Not attempted this session (see §14 for the honest reasoning on each):
the full Skill/Tool/MCP capability-permission model, the generic
proactive/event-notification layer, XTTSv2-Streaming-ONNX/Windows
Audio (still no Windows/model access), the German-first backlog, and
the broader content-logging surface the follow-up audit found outside
tool/skill logs.

---

Previous major update: 2026-09-21 (Claude session #7, same branch
`claude/jarvis-sleepy-backend-rc-nhtfgm`, starting from `ddb49c9`).

Session #7 opened with five findings from an external review of session
#6's own work — all real, all fixed:
1. `PrivacyControlWatcher`'s poll order (LOCK, ENTER, EXIT) actually made
   EXIT win any sentinel collision, backwards from the "protective
   outcome wins" comment sitting right above it (the old test even
   asserted the buggy outcome while calling it "lock wins" in its own
   name). Reordered to EXIT, ENTER, LOCK — see §11.
2. `ConversationManager.add_message()`'s own debug log leaked message
   content into `core/logger.py`'s output regardless of privacy mode —
   a gap separate from the already-gated `chat_history.jsonl` write.
   Gated on `CONTENT_LOGGING`.
3. `run_consolidation()`'s docstring admitted "decay only" while its
   name implied full consolidation — implemented a real second action
   (MERGE: collapse exact-duplicate conflicting-candidate rows) instead
   of just renaming. See §5d.
4. The systemd docs recommended system-level units, but the REAL
   control plane (`start.sh`/`stop.sh`/`killswitch.sh`/aliases, already
   in daily use) was entirely user-level for `jarvis.service` — session
   #6's "system-level primary" recommendation was an architectural guess
   that never checked for an existing convention. Corrected to the real,
   evidence-based mixed strategy and wired the control-plane scripts to
   also manage the two system-level model services they'd never touched.
   See §13.
5. `PrivacyControlWatcher` was only started in `jarvis_continuous.py`'s
   event_mode branch, leaving the legacy branch a privacy-exit dead end
   even though mic/STT gating itself (shared code) still worked there.
   Started in both branches now.

After the review fixes, a background agent ran a full agentic-system
audit (skill system, tools, MCP, task planner, background jobs, audit
logging, dead code). Of its ~10 findings, the highest-value ones were
acted on this session:
- **CRITICAL, fixed**: `skills/system/developer_tools/_safety.py`'s
  `classify_command()` only ever inspected the first word/two words of
  a command string — `"git status ; cat /etc/shadow"` and
  `"git log && rm important_file.txt"` both classified as `'allowed'`
  (no confirmation) purely because their first segment matched a
  Tier-1 command, while `_run_cmd()` executes the ENTIRE string via
  `shell=True`. This was the one path in the codebase where LLM/voice-
  controlled tool arguments become a shell command, effectively
  unguarded against basic command chaining. Fixed with a conservative
  chain-operator detector that never lets a compound command auto-allow.
- MCP tool-call timeouts didn't actually cancel the underlying
  coroutine (a `future.result(timeout=...)` gotcha) — it kept running
  on the shared event-loop thread, able to race the next call over
  `self._sessions`. Fixed with `asyncio.wait_for()` inside the
  coroutine itself.
- `skill_manager.execute_intent()` — the dispatch path for most voice
  commands — had zero structured audit logging, unlike
  `tool_registry.execute_tool()` (the separate LLM-function-calling
  path). Added, and found the existing `tool_registry` audit logging
  had no PrivacyGate awareness either — both now gated on
  `CONTENT_LOGGING`.
- `developer_tools`' pending-confirmation mechanism was a single global
  slot that silently overwrote an unresolved confirmation — fixed to
  refuse instead.
- Confirmed-dead prototype skill (`skills/system/_in_development/
  web_navigation/`, unreachable by directory-depth, a stale v1.0.0 fork
  of the real v2.0.0 skill) deleted.
- Also investigated: the documented latency-chain turn-id-handoff
  blocker. Found the real integration seam (STTWorker's
  TRANSCRIPTION_READY event already carries a dict payload in some
  cases) but the full wiring requires a breaking change to the
  audio_queue contract between two files neither importable in this
  sandbox — implemented only the safe, fully-tested half
  (`LatencyTracker.mark(stage, at=...)` backfill capability) rather
  than push an untestable change to the live audio pipeline. See §8.

Not attempted this session, same reasoning as session #6 for most:
XTTSv2-Streaming-ONNX/Windows-Audio (still no Windows/model access), a
generic proactive/event-notification layer (the audit's background-jobs
findings suggested existing pieces — reminder_manager, watchdog,
event_logger — already cover real needs; building a new layer without
finishing that audit first risked the "zweite konkurrierende Engine"
earlier sessions were told to avoid), the German-first backlog, and the
remaining ~6 smaller/architectural agentic-audit findings (tool_gate.py
not actually being a permission gate despite its name; no skill-level
capability manifest; TaskPlanner can't cancel a step already mid-
execution; Watchdog has no visibility into background-job health) — see
the updated §14.

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
| `jarvis_web.py` | Web UI (dashboard, WebSocket chat, mobile) on port 8091/8443 (8088 = VVS API) |

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
| LLM (cloud) | Configured provider, OpenRouter preferred | disabled until `llm.api.enabled`, provider, model, endpoint, and credential are configured; Anthropic is optional and explicit only |
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

- ~~Contextual ack latency on Chatterbox~~ **Fixed (session #5)**:
  `Pipeline._play_ack_if_still_thinking()` speaks a dynamically LLM-
  generated (4B model) contextual ack via `self.tts.speak()` — novel
  per-command text, can't be pre-cached, so on Chatterbox this is a real
  GPU round-trip inside the ack timer thread, holding
  `TextToSpeech._tts_lock` while it runs. `speak()` gained two optional
  params: `cancel_check` (re-checked immediately after the lock is
  acquired — same pattern `speak_ack()` already used — so a response
  that arrived while waiting for the lock stops a now-stale ack before
  synthesis starts) and `timeout_override` (forwarded to the Chatterbox
  request timeout, capping the call at `Coordinator._CONTEXTUAL_ACK_TIMEOUT_S`
  = 2.5s instead of the full response-length `chatterbox_timeout`, 60s
  by default). The call site now passes both; `_ack_played` is only set
  when `speak()` actually returns True (previously set unconditionally).
  This bounds the worst case a contextual ack can add ahead of the real
  response to ~2.5s instead of up to 60s, without new concurrency
  machinery — it does not eliminate the window entirely (a request that
  passes `cancel_check` and is already in flight when the real response
  becomes ready still blocks up to the timeout budget), which is the
  explicitly accepted trade-off of the "hard time budget" approach over
  building a cancellable-HTTP-request architecture. Tests:
  `tests/unit/test_contextual_ack_blocking.py` (bare-object pattern, no
  real Chatterbox needed). **Not yet observed against a real Chatterbox
  server** — see item 2 in §14.
  ~~Session #6 gap in this fix~~ **Fixed (session #6)**: on a Chatterbox
  timeout/failure, `speak()`'s failure path still unconditionally fell
  back to Piper — trading one slow engine for another, still holding
  `_tts_lock` for the full Piper synthesis+playback, with no re-check of
  `cancel_check` first (so it could speak a stale ack even after the
  real response had already arrived). Fixed: the Chatterbox branch now
  checks `cancel_check is not None` (only ever passed by the ack call
  site) before falling back — on that path, a failure now drops the ack
  unconditionally instead of trying Piper. Real (non-ack) `speak()`
  calls never pass `cancel_check`, so their Piper fallback is
  byte-for-byte unchanged. Known residual, not fixed: the Kokoro engine
  branch still falls back to Piper unconditionally regardless of
  `cancel_check` — Kokoro is inactive in this deployment, so this is a
  dormant version of the same bug class, left alone to keep the change
  scoped to the actually-exercised path. Tests: 3 more cases added to
  the same `test_contextual_ack_blocking.py`.
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

### 3.5 Startup warmup contention (session #4)

`_init_chatterbox()` used to start the ack cache (~9 phrases) and CAL-L0
cache (~300 phrases) in **two parallel** background threads, both hitting
the single-threaded Chatterbox server at once. Worst case: a live
`speak()` request during the first minute or two after boot could end up
queued (at the OS TCP-accept level) behind whichever warmup requests the
server already accepted — up to the tail of a multi-minute CAL-L0 batch.

Fixed: one thread (`_run_chatterbox_warmup`) runs ack-cache-then-CAL-L0
sequentially (ack first — it's small and matters more for perceived
responsiveness). Both now use `_synthesize_short_pcm_throttled()`, which
acquires `TextToSpeech._tts_lock` for just the current phrase's HTTP call
(the same lock `speak()` takes) — so a live request contends for the lock
fairly against warmup instead of racing it unlocked at the HTTP level, and
is delayed by at most one in-flight warmup phrase (~1-3s), not the whole
batch. (A dedicated Concurrency reviewer this session found the ack cache
had been missed — it still used the unthrottled path — fixed alongside;
see §5e.)

Tested in `tests/unit/test_tts_startup_contention.py`: warmup order,
throttled-lock acquire/release per phrase, a live caller can interleave
between warmup phrases (not just after the whole batch), and both engines
route through the correct (throttled/unthrottled) path.

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
- Regex-based fact extraction (`core/memory_manager.py`) stores facts as
  English third-person sentences ("the user loves the band Tool") — see
  §5b. Fixing this properly means redesigning extraction + storage
  format, not a string-level translation. §5d's `render_fact_de()` works
  around this for facts that have a structured `value`, but older/
  one-group-extracted facts still fall back to the raw English sentence.
- `intent_examples` (semantic-matching training phrases, e.g. in
  `skills/personal/reminders/skill.py`) are still English-phrased. Left
  as-is per the task's own framing: input-recognition phrasing isn't the
  priority, output speech is (German STT already transcribes German
  input fine regardless of what language the matching examples are
  written in).

**RESOLVED this session — persona/honorific question**: the user
explicitly confirmed "Sir"/"Ma'am" is a *deliberate, wanted* persona
element, not a German-first violation. German-first means sentence
structure/error messages/reminders/memory output/confirmations are
German; the address term itself staying English is fine and should not
be "fixed." See the persona note near the top of this document — don't
re-relitigate this.

New regression test: `tests/unit/test_german_first_active_path.py` — fails
if any of the specific previously-confirmed banned English phrases
reappear in the CAL-L0 templates, persona pools, or `ResponseLibrary`
(guards against a future upstream sync silently reintroducing them).

### German-first backlog (from the session #4 audit, see §5e)

A dedicated Explore-agent audit (backend only — UI explicitly excluded)
found roughly **330-340 remaining active English strings**, none of them
fixed this session beyond the two small high-signal ones below (translating
all of it responsibly needs its own dedicated session — this list exists
so that session doesn't have to re-scan the repo from scratch):

| File | Est. count | Status |
|---|---|---|
| `skills/personal/conversation/skill.py` | ~90 | **Confirmed ACTIVE** (metadata.yaml `enabled: true`) — near-duplicate of `core/persona.py`'s already-German pools; highest priority, and the fastest to translate since equivalent German phrasing already exists in `core/persona.py` to adapt from |
| `skills/system/file_editor/skill.py` | ~45 | Rest beyond the confirmation flow already fixed in session #3 (create/edit/delete/print/document-generation messages); one confirmation-adjacent line still English too: `"That confirmation has expired..."` at the line found by the audit |
| `skills/system/app_launcher/skill.py` | ~35 | Only `launch_app` is translated (monkeypatch override, `"BEGIN JARVIS DE-DE APP RESPONSES"` marker exists — follow that pattern); close/fullscreen/minimize/maximize, volume, workspaces, focus/switch, list_windows, clipboard all still English |
| `skills/system/weather/skill.py` | ~30 | Fully English |
| `skills/system/web_navigation/skill.py` | ~25 | Fully English |
| `skills/system/system_info/skill.py` | ~25 | Fully English |
| `skills/system/filesystem/skill.py` | ~24 | Fully English |
| `skills/system/developer_tools/skill.py` + `core/health_check.py` | ~17 | Confirmation flow already German (session #3); `format_voice_brief()` translated this session (§ above); `format_voice_summary()` in the same file is dead code (unreferenced) — don't translate it, delete-or-ignore |
| `core/tools/enroll_face.py` + `core/presence_detector.py` | ~16 | Voice-guided face-enrollment flow, fully English |
| `skills/personal/social_introductions/skill.py` | ~9 | Fully English |
| `skills/personal/news/skill.py` + `core/news_manager.py` | ~9 | Fully English |
| `skills/system/time_info/skill.py` | ~6 | Fully English |
| `core/task_planner.py` | 0 | The one active string found (line ~1044) translated this session |

Classification per the audit: everything above is category A (active
German runtime path, should be translated). `core/google_calendar.py`,
`core/caldav_calendar.py`, `core/weather_poller.py`, `core/desktop_manager.py`,
`core/conversation_router.py`, `core/self_awareness.py`, `core/watchdog.py`,
`core/tool_executor.py`, `core/tool_registry.py` were checked and have
**no** active category-A findings (tool_registry's English strings feed
LLM synthesis, not direct TTS — category C).

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

## 5d. Memory: value-based reinforcement, risk gate, German output, bug fixes (session #4)

Continues §5c. Two more schema-additive columns: `value` (nullable TEXT)
alongside the already-added `evidence_count`.

**The "Kernproblem" this session was explicitly asked to solve**: distinguish
a paraphrase of the same fact ("Alex nutzt häufig VS Code" / "Alex arbeitet
meistens mit VS Code") from a real change to the same attribute ("VS Code"
→ "Cursor"), without falling into the text-similarity trap §5c already
found (a genuine contradiction scores as *more* textually similar than a
paraphrase). Solution: extraction now also produces a structured `value`
(the two-group `EXPLICIT_PATTERNS` already captured this as a local
variable, just wasn't stored; `BATCH_EXTRACTION_PROMPT`/
`PER_TURN_EXTRACTION_PROMPT` now ask the LLM for it too, with an explicit
instruction to use the *same* subject wording every time for the same
attribute — consistency of the key is what makes matching work at all).
`store_fact()` compares `value` when both sides have one: same value →
`_reinforce_fact()`; different value → supersede. No `value` on either
side (older data, or a one-group free-form extraction) → falls back to
the pre-existing exact-content comparison, unchanged.

**Sensitive-topic risk gate** (§7 "Leine" in the task): `_is_sensitive()`
— category `"health"` or a DE/EN keyword hit (illness, religion, political,
sexuality, debt, criminal record, pregnancy, ...) — caps a *non-explicit*
fact's confidence at `_SENSITIVE_CAP_CONFIDENCE = 0.75` (below the
candidate threshold), enforced both at insert time and every time
`_reinforce_fact()` would otherwise raise it further. An **explicit**
user statement is exempt — the risk gate is specifically about the system
promoting its own inference to "confirmed truth" on a sensitive topic
without the user ever having said it, not about refusing to store what
the user directly tells JARVIS. Best-effort keyword heuristic, not a real
classifier — deliberately conservative (false positive = an innocuous
fact stays a permanent candidate; false negative = a sensitive inference
could get promoted — the former is the much cheaper mistake).

**German rendering**: `render_fact_de()` renders `subject: value` (short,
often language-neutral technical terms — "editor: VS Code") instead of
interpolating the full stored English sentence into German wrapper text.
`handle_forget()`, `handle_transparency()`, `list_facts_by_category()` now
use it and are fully German. `handle_transparency()` additionally
separates confirmed facts from candidates in its own response (§14 in the
task: "muss unterscheiden zwischen bestätigt, beobachtet, vermutet") —
if only candidates exist, it says so explicitly rather than presenting an
inference with the confidence of a stated fact. New `is_why_query()`/
`handle_why()` ("Warum glaubst du, dass ich X?") explains provenance:
explicit → "das haben Sie mir selbst gesagt"; reinforced inference →
names the `evidence_count`; single observation → says so plainly. Wired
into `conversation_router.py`'s `_handle_memory_ops` alongside the
existing forget/transparency routes.

**German recall/forget/transparency/fact-request patterns** added
alongside the existing English ones (English kept, German is now the
first-tried path) — `RECALL_PATTERNS`, `FACT_REQUEST_PATTERNS`,
`FORGET_PATTERNS`, `TRANSPARENCY_PATTERNS`. The German forget patterns use
a `(?!\s+nicht)` negative lookahead — "vergiss nicht, dass X" means the
*opposite* (remember X) and must not match a forget pattern.

**Candidate vs. confirmed labeling in LLM prompt injection** (§15/§16 in
the task): `get_full_user_context()`/`_build_user_context_block()` now
puts unconfirmed observations in a separately-labeled
"UNCONFIRMED OBSERVATIONS" section instead of mixing them into
"WHAT YOU KNOW ABOUT THE USER" — the LLM is instructed to only ever
present that section as a guess. `get_proactive_context()`'s single
injected fact is now labeled "BESTÄTIGTER FAKT" or "UNBESTÄTIGTE VERMUTUNG"
depending on `is_candidate()`.

**Bugs found by the dedicated Memory Reviewer subagent this session and
fixed** (see §5e for the full review — this lists only what got fixed):

1. **CRITICAL — "don't forget that X" was deleting instead of remembering.**
   `FORGET_PATTERNS`' English `r"forget (?:that|the) (.+)"` used unanchored
   `re.search`, so it matched the substring inside `"don't forget that I
   love pizza"` too — `is_forget_request()` returned `True` before
   `is_fact_request()` was even checked in `_handle_memory_ops`'s ordering,
   so a request to *remember* something got routed to *delete* it instead.
   Fixed with the same `(?<!don't )(?<!do not )` negative-lookbehind
   pattern already used for the German patterns' `(?!\s+nicht)` exclusion.
2. **CRITICAL — subject-only matching could supersede unrelated facts.**
   `_find_similar_fact()` matched purely on `subject` text, with no
   category constraint — two independent facts that happen to share a
   generic subject (e.g. `"mutter"` — "Mutter heißt Petra" in one category,
   an unrelated observation also tagged `subject="mutter"` in another)
   could match each other, and the value-comparison logic above would then
   silently supersede one. Fixed: `_find_similar_fact()` now takes an
   optional `category` and constrains both its exact-match and
   substring-fuzzy queries to it; `store_fact()` always passes the new
   fact's category.
3. **CRITICAL — TOCTOU race across concurrent extraction threads.**
   `_find_similar_fact()` (read) and the subsequent reinforce/supersede/
   insert (write) happened in separate `self._db_lock` acquisitions.
   `extract_facts_realtime()` (main thread), batch extraction, and
   per-turn extraction (each their own background thread) all call
   `store_fact()` for the same user concurrently — two threads could both
   see "no existing fact" and insert duplicates, or both reinforce from
   the same stale snapshot and lose one of two observations. Fixed:
   `self._db_lock` is now a `threading.RLock` (was `Lock`), and
   `store_fact()` wraps its entire read-decide-write sequence in one
   acquisition (`_store_fact_locked()` holds it for the whole method body;
   the RLock is required because that method still calls
   `_find_similar_fact()`/`update_fact()`, which each also take the lock).
   Verified with a real 8-thread concurrent-write test
   (`test_concurrent_identical_facts_produce_no_duplicate`) — all 8
   observations correctly counted via `evidence_count`, no duplicate row.

~~Not fixed this session...~~ **Fixed in session #5**: the
same-subject-same-value-but-opposite-sentiment case ("ich liebe X" →
later "ich hasse X", same extracted `value="X"`) previously reinforced
instead of registering as a real reversal, since sentiment wasn't part
of the value comparison. Rather than reworking the extractor's `value`
field (which the note above worried would weaken its "short canonical
answer" design), session #5 added a separate, narrower fix: an
idempotent migration adds a nullable `polarity` column (-1/0/+1) to
`facts`, and `MemoryManager._detect_polarity()` is a small explicit
German+English sentiment-keyword lexicon scoped to the
`preference`/`opinion` categories only. In `_store_fact_locked()`, when
both the existing and new fact have a determinable polarity and they
disagree, that forces `SUPERSEDE` regardless of what the value
comparison alone would have decided. A miss (no recognized sentiment
word, or a category outside preference/opinion) falls back to the
pre-existing value/content comparison unchanged — this is deliberately
not a general sentiment classifier, just enough to close the specific
reversal bug without regressing anything the value-comparison logic
already handled correctly. Also closed in the same change: a single
inferred/per-turn extraction could previously supersede (overwrite) a
fact the user stated explicitly — `existing.source == "explicit"` and
`new.source != "explicit"` now stores the conflicting inference as its
own non-superseding, confidence-capped candidate instead, leaving the
explicit fact intact until an explicit correction (or the user
restating it) actually supersedes it. Tests:
`tests/unit/test_memory_polarity.py` — polarity detection (DE/EN,
split negation like "mag ... nicht"), reversal-supersedes-not-
reinforces in both directions, paraphrase-with-same-polarity still
reinforces (regression guard), no-polarity-data falls back unchanged,
explicit-wins-over-inference in both directions, and a 10-thread
concurrent-writes race test asserting no false reinforcement survives
mixed-polarity concurrent `store_fact()` calls on the same subject.

**Session #6: the "explicit wins" fix above had an escalation bug,
reproduced and fixed.** It only handled the *first* conflicting
inferred observation correctly. `_find_similar_fact()` matches "the
most recent active row for this subject+category" — after the first
conflict inserts a new active (non-superseded) candidate row, a
*second* matching inferred observation finds *that candidate* instead
of the original explicit fact (it's now the most recent active row),
and since neither side of that comparison is `"explicit"` anymore, it
falls through to plain reinforcement. Confirmed with a real repro
script before writing the fix (per the task's explicit instruction to
reproduce, not just theorize): starting from an explicit fact at 0.90
confidence, 7 repeated conflicting inferred observations pushed the
*inferred* candidate to 0.99 (`MAX_FACT_CONFIDENCE`, `evidence_count=7`)
while the explicit fact sat untouched at 0.90 — now the lower-
confidence, effectively shadowed row for that subject.

Fix: idempotent migration adds `excluded_from_matching INTEGER NOT
NULL DEFAULT 0`. Every candidate created via the "explicit wins" branch
is inserted with this set to 1, and `_find_similar_fact()`'s two
queries (exact + fuzzy subject match) both add
`AND excluded_from_matching = 0` — so a conflicting-inferred-vs-
explicit candidate can never again be anyone's "existing" match. Every
future conflicting inference for the same subject compares against the
explicit fact again, landing as its own separate low-confidence row
rather than accumulating reinforcement. Accepted trade-off: repeated
identical contradictions now produce multiple near-duplicate
low-confidence rows instead of one reinforced row — a storage cost,
not a correctness one, and the one the safety requirement calls for.
The column only affects the internal dedup/reinforcement lookup —
`get_facts()` still returns these rows unchanged (same "visible but not
overwriting" behavior as session #5 intended). Also reused this
session for **decay** (§14 note, "archived" is a separate column but
follows the same "exclude from active queries, keep for audit" shape) —
see the new decay/consolidation/autonomy-budget work below.

Tests: `TestConflictingInferredFactsNeverEscalate` in the same
`test_memory_polarity.py` (4 tests) — 7 repeated conflicting
observations each create a distinct, never-reinforced row strictly
below the explicit fact's confidence (the actual invariant, not just
"doesn't crash"); excluded candidates remain visible via `get_facts()`;
the explicit fact's own `evidence_count` stays untouched either
direction.

### Memory: decay, bounded consolidation, autonomy budget (session #6)

Closes the item session #5 explicitly deferred (old open-work item 14).
Additive on the existing `facts` table, no new architecture.

**Decay** (`MemoryManager.run_decay_pass()`): idempotent migration adds
`archived INTEGER NOT NULL DEFAULT 0`. A candidate is archived only if
ALL of: `source != 'explicit'`, confidence still below
`CANDIDATE_CONFIDENCE_THRESHOLD`, `evidence_count <= 1` (never
reinforced), and older than
`conversational_memory.autonomy_budget.decay_days` (default 14).
Archived rows are excluded from every active-fact query via a blanket
`AND archived = 0` added alongside the existing `AND deleted = 0 AND
superseded_by IS NULL` filter (7 call sites, including
`_find_similar_fact()` — an archived candidate can't be silently
reinforced back to life). Rows are archived, never hard-deleted, so
decay stays auditable; explicit facts and anything reinforced even once
are never touched regardless of age.

**Consolidation** (`run_consolidation()`): bounded, deterministic, with
its own budget (`autonomy_budget.max_consolidation_runs`, default 50
per process lifetime). Wired at two trigger points: session-end
(`jarvis_continuous.py`'s shutdown, before `memory_manager.save()`) and
"N new candidates" (every `autonomy_budget.consolidation_interval_
candidates`, default 50, checked inside `store_fact()`). Idle and
"explicit maintenance job" triggers are NOT wired to anything —
`run_consolidation()` is a plain public method either could call, but
no idle-detection or maintenance-job caller was added.

~~Currently just the decay pass~~ **Session #7: implemented a real
second action instead of leaving the name/docstring mismatched.** An
external review caught that the docstring admitted "decay only" while
the method's name implied full consolidation. Rather than just
renaming, `_merge_duplicate_excluded_candidates()` (MERGE, one of the
ten actions from the original consolidation vocabulary) now also runs:
it collapses exact-duplicate `excluded_from_matching` rows — created
because each conflicting inference intentionally gets its own row (the
fix for the escalation bug above) — into one canonical row, summing
`evidence_count` as a visible "observed N times" counter. Confidence is
never touched by the merge and merged rows stay
`excluded_from_matching`, so this can't reopen the escalation risk that
column exists to prevent. The docstring now names exactly which two of
the ten actions are implemented (DECAY, MERGE) instead of "decay only."
REINFORCE/SUPERSEDE/UPDATE/PROMOTE/KEEP/NEEDS_CONFIRMATION remain out
of scope for the same reason as before (no LLM self-reflection loop).

**Autonomy budget**: `max_new_candidates` (default 500) caps genuinely
NEW candidate rows per `MemoryManager` instance lifetime — not
reinforcement of an existing row, which must keep working unbounded
(that's bounded confidence growth, not row creation). Explicit
statements are never budget-limited. Counters are scoped to this
instance's lifetime (one `jarvis_continuous.py` process run in
practice) — no shorter "session" boundary exists in the architecture to
reset them against. `retrieval_candidate_count` and background-LLM-call
budgets from the original request were NOT added — existing `limit`
parameters on `get_facts()`/`get_proactive_context()`/etc. already
bound retrieval size, and no unbounded background LLM-call loop was
found that needed bounding.

Tests: `tests/unit/test_memory_decay_consolidation.py` (12 tests, real
temp-file SQLite) — old+low-evidence candidates archive, recent/
reinforced/explicit ones don't regardless of age; archived rows
excluded from `get_facts()` and from being re-matched; consolidation
budget enforcement, the N-candidates auto-trigger firing exactly once
at the configured interval; new-candidate budget denial past the cap,
explicit facts bypassing it, reinforcement confirmed not to consume
budget.

## 5e. Session #4 specialized reviews (Memory, Concurrency, German runtime)

Per the task's explicit ask, three subagents each reviewed a fixed scope
of the *current* code (not a design proposal) and reported findings as a
priority list. CRITICAL findings were fixed (see §5d and §3.5); this
section records what was reviewed, at what confidence, and what's
deliberately still open.

**Memory reviewer** — read `core/memory_manager.py` in full plus
`conversation_router.py`'s `_handle_memory_ops`. 3 CRITICAL (all fixed,
§5d), 2 HIGH, 4 MEDIUM/LOW not fixed this session:
- HIGH: `render_fact_de()` can still leak English `subject`/`value`
  terms verbatim (extraction prompts give English examples like "editor",
  "shipping carrier" — the LLM isn't told to keep those terms German).
  Not fixed — would need prompt tuning + verification against a live
  model, which this sandbox can't run.
- HIGH: value comparison ignores sentiment reversal (see §5d, last
  paragraph).
- MEDIUM: `_SENSITIVE_KEYWORDS` uses substring matching without word
  boundaries (`"kirche"`, `"glaube"`, `"partei"` can false-positive on
  innocuous mentions) and is missing some real gaps (addiction, disability,
  income/salary, separation/divorce). Not tightened this session — the
  keyword list is already flagged in its own docstring as a best-effort
  heuristic; retuning it needs real usage data, not a sandbox guess.
- LOW: `handle_why()`'s topic-extraction stopword list is incomplete
  ("mein/dein/hat/möchte" not stripped) — cosmetic, `search_facts_text`
  still degrades gracefully on a noisier topic string.

**Concurrency reviewer** — read the full `_ChatterboxAudioWriter`/
`StreamingAudioPipeline`/`_process_speech_chunk` chain in `core/pipeline.py`
plus the relevant parts of `core/tts.py`. 1 CRITICAL (fixed, §3.5), 2 HIGH
(1 fixed, 1 documented), 2 MEDIUM (1 fixed, 1 documented):
- HIGH, fixed (§3.5): `_build_ack_cache()` used the unthrottled synth path
  for Chatterbox, so the ~9 ack phrases warmed up completely unprotected
  against a concurrent live request, contrary to `_run_chatterbox_warmup`'s
  documented intent.
- HIGH, **not fixed** — documented instead: Kokoro's `StreamingAudioPipeline`
  branch holds `_tts_lock` for the entire session including
  `aplay.stdin.write()` backpressure; Chatterbox's branch releases it
  before waiting on playback. This means `speak_ack()` can be starved for
  the whole spoken duration of a response on Kokoro but not on Chatterbox.
  Since Chatterbox is the active engine and Kokoro's streaming code is
  otherwise untouched/working, changing Kokoro's lock scope for a
  currently-inactive-engine inconsistency was judged higher risk than
  value this session — flagged for whoever next touches Kokoro's
  streaming path.
- MEDIUM, fixed (§8): `LatencyTracker` is genuinely written from two
  threads (the coordinator thread and `StreamingAudioPipeline`'s
  `on_first_audio` callback thread) — now lock-protected instead of
  relying on CPython's GIL making single dict writes safe by accident.
- MEDIUM, not fixed: `finish_and_wait()`'s worst-case blocking time
  (~30s thread-join timeout + ~90s aplay-wait timeout) is bounded but not
  tight. Acceptable as a safety net against a truly stuck `aplay`, not
  expected to be hit in normal operation — lowering it needs real timing
  data from a live run to tune correctly, not a guess.

**German runtime reviewer** (Explore agent, read-only, backend only —
`web/*`, HUD, `jarvis-ui` explicitly excluded) — see §5a for the
consolidated findings and the resulting backlog. Confirmed
`skills/personal/conversation/skill.py` is **active** (`metadata.yaml:
enabled: true`), not the dead code the previous session's docs implied —
this session's docs/DEVELOPMENT.md note calling it "(DISABLED)" is stale.

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

## 8. Latency instrumentation (`core/latency_tracker.py`, session #4)

**Session #7**: `mark(stage, at=...)` now accepts an explicit
`time.monotonic()` value to backfill a stage that happened before the
tracker existed (e.g. `speech_end`/`stt_start`/`stt_end`, which happen
on `continuous_listener.py`'s/`STTWorker`'s own thread before
`_handle_command()` creates the tracker) — see this section's own
open-work item for why the actual pipeline wiring (a breaking change to
the `audio_queue` payload contract between two files neither importable
in this sandbox) wasn't done, just the tracker-side capability. Existing
callers/behavior are completely unaffected (`at` defaults to `None` →
"mark now," same as before).

Real per-turn monotonic checkpoints — implemented, not just documented,
per the explicit ask. One `LatencyTracker` instance per voice-command turn,
held as `Coordinator._current_latency` (created in `_handle_command()`,
cleared after the turn's summary is emitted). Checkpoints:
`command_received` → `router_done` (routing **and** memory retrieval,
which `ConversationRouter.route()` does internally and synchronously —
not separately instrumented, see below) → `llm_start` → `llm_first_token`
→ `first_speakable_chunk` (first `SpeechChunker` output) →
`tts_first_pcm` (via `StreamingAudioPipeline`'s new `on_first_audio`
callback, fired at the exact moment its "first chunk in Xs" log line
already fires) → `response_done`.

Every turn logs one compact line at INFO
(`[abc12345] JARVIS LATENCY — Routing+Memory: 12ms | LLM TTFT: 420ms | ...`)
— never a transcript, never per-token spam — plus a structured
`event_logger` emission (`category="performance", event="turn_latency"`)
carrying raw per-stage offsets for a future p50/p95 rollup. Both are
best-effort: `LatencyTracker.emit()` swallows any exception so
instrumentation can never break a real voice turn, and `mark()` is
idempotent (first call per stage wins) plus lock-protected (see §5e —
it's genuinely written from two threads: the coordinator thread and
`StreamingAudioPipeline`'s background thread via the `on_first_audio`
callback).

**Scope, stated plainly**: this covers the portion of a turn within
`core/pipeline.py`'s control. It does **not** cover VAD end-of-speech
detection or STT (those run in `core/continuous_listener.py` /
`core/stt_qwen3.py`, on a different thread, before a turn/turn-id even
exists) — wiring that in would mean passing a turn-id from the listener
thread into the coordinator, which wasn't done this session. It also
doesn't separately measure memory retrieval from routing (both happen
inside one `ConversationRouter.route()` call).

**No real numbers exist yet.** This sandbox has no microphone, GPU, STT
model, or LLM/Chatterbox server to run the actual voice loop against —
every example in this section is illustrative of the *format*, not a
measurement. The very first real data point should come from running
JARVIS on Sleepy and reading the `JARVIS LATENCY` log lines it produces.

## 9. Startup preflight (`scripts/preflight_check.py`, session #4)

A single, small script — not a diagnostics framework — that answers "can
JARVIS start cleanly right now, and if not, why": LLM main model
(`:8080/health`) and small/fast model (`:8081/health`, config-driven),
Chatterbox (`/health`, config-driven), Qwen3-ASR model directory, mic/
speaker presence (`pactl list short sources|sinks`), memory DB + FAISS
directory writability, WSL2 detection (`/proc/version`), storage path,
free disk space, and required executables (`aplay`, `ffmpeg`, plus
optional `whisper-cli`/`piper`/`llama-cli` paths from config.yaml). German,
one line per check, exits 1 only on a genuinely CRITICAL failure (a down
Chatterbox server is a WARN, not a FAIL — Piper is a real fallback).

Actually run against this real environment during development (this
machine *is* the real jarvis-data/config.yaml, just without the LLM/
Chatterbox servers started in this session) — correctly detected the real
mic/speakers, the real model paths, and the actually-running llama-server
on `:8080`. Not a synthetic/mocked demonstration.

Existing `jarvis.service`/`llama-server.service`/`flux-server.service`
files in the repo root were checked per the task's instruction not to
blindly duplicate service infrastructure — they're **stale upstream
templates** (`/home/user/jarvis`, `/mnt/models/...`, unexpanded `$USER`,
llama-server port matches `core/llm_router.py`'s hardcoded `:8080` but no
Chatterbox service exists at all). Not rewritten this session — guessing
at the real Sleepy paths/username for a systemd unit that can't be tested
here felt riskier than useful; flagged in §14 as real Sleepy-side work
instead.

### Shutdown fix (found while checking startup/shutdown together)

`jarvis_continuous.py`'s shutdown `finally` block (the primary voice
runtime) never called `MemoryManager.save()` — the FAISS embedding index
persist explicitly documented as "Call on shutdown" in that method's own
docstring. `jarvis_web.py` already did this correctly; `jarvis_continuous.py`
never did. SQLite facts themselves were never at risk (each `store_fact()`
write commits immediately), but the FAISS semantic-search index's
in-session additions were lost on every restart until the next periodic
backfill. Fixed: added `self.memory_manager.save()` and
`self.tts.kill_active()` (stops an in-flight `aplay` from being orphaned
as a child process after the Python process exits) to the shutdown
sequence. The signal handler's `sys.exit(0)` raises `SystemExit`, not
`KeyboardInterrupt` — the surrounding `except KeyboardInterrupt` doesn't
catch it, but the enclosing `finally:` still runs regardless of exception
type, so this cleanup path was already reachable; it just didn't do
enough.

## 11. Privacy Gate (`core/privacy_gate.py`, session #5, P0, new)

**Status: IMPLEMENTED and wired into the ingestion/egress chokepoints
identified by reading the real code; NOT exhaustively wired — see
"Deferred" below.**

Before this session, no privacy concept existed anywhere in the backend —
only unrelated booleans that happen to also be called "paused"/"muted":
`continuous_listener`'s mic pause during TTS playback (echo prevention,
not privacy), `desktop_manager.toggle_mute()` (speaker volume via
`pactl`), `readback_session`/`task_planner` pause (document readback /
multi-step plan state). Confirmed via a full-repo grep for
`privacy|mute|paused|PRIVACY` before writing anything, per the task's
"nicht raten" instruction.

`PrivacyGate` is a process-wide singleton (`get_privacy_gate(config)`,
same pattern as `core/event_logger.py`'s `get_event_logger`) that is the
single technical authority every ingestion/memory/logging/cloud call
site consults — not a collection of independent flags. Three modes
(`PrivacyMode.NORMAL/PRIVACY/PRIVACY_LOCK`), fifteen `Capability` values
(`MIC_INGEST`, `STT`, `SCREEN_CAPTURE`, `WEBCAM_CAPTURE`,
`CLIPBOARD_READ`, `FILESYSTEM_OBSERVATION`, `MEMORY_EXTRACT`,
`MEMORY_WRITE`, `EMBEDDING_GENERATE`, `SESSION_SUMMARY`,
`AGENT_CONTEXT_INGEST`, `CLOUD_LLM`, `REMOTE_TOOL`, `CONTENT_LOGGING`,
`PROACTIVE_OBSERVATION`), gated via `gate.allow(capability)` /
`gate.assert_allowed(capability)`. `PRIVACY` blocks every capability
except `REMOTE_TOOL`; `PRIVACY_LOCK` blocks that too.

**Race safety** (the part of the spec most likely to be gotten wrong):
`enter()`/`exit()` both run registered flush callbacks under the gate's
own lock *before* changing the mode, and mint a new opaque `epoch()`
token on every transition (enter *and* exit). Background work that
defers a write to another thread (memory's batch/per-turn extraction)
captures `gate.epoch()` at trigger time and re-checks
`gate.is_current_epoch(captured)` immediately before persisting anything
— this is what stops content whose extraction started before a privacy
transition from landing after it, including the case where privacy is
entered *and exited again* while the background thread is still running
(a plain "is privacy active right now" re-check at write time would
wrongly allow that, since `mode()` would read `NORMAL` again by then).
See the module docstring in `core/privacy_gate.py` for the full
reasoning.

**Wired this session** (chosen by reading the actual call sites, per the
research this session ran first — not assumed):

| Site | Capability | Effect when denied |
|---|---|---|
| `continuous_listener._on_speech_start()` / `_process_speech()` | `MIC_INGEST`, `STT` | Speech isn't even buffered; a flush callback (`register_flush_callback`) drops any in-flight `speech_buffer`/`_pre_speech_audio` on enter/exit |
| `memory_manager.on_message()` | `MEMORY_EXTRACT` | Entire per-message handling (indexing + extraction + batch/per-turn triggers) skipped |
| `memory_manager.index_message()` | `EMBEDDING_GENERATE` | No FAISS embed/add |
| `memory_manager.store_fact()` | `MEMORY_WRITE` | Returns `None`, no SQLite write — this is the second line of defense behind the epoch checks in the two background extraction runners |
| `desktop_manager.take_screenshot()` | `SCREEN_CAPTURE` | Returns `None`, **no file written** |
| `desktop_manager.get_clipboard()` | `CLIPBOARD_READ` | Returns `None` |
| `webcam_manager.start()` | `WEBCAM_CAPTURE` | Raises `PermissionError` before the `ffmpeg` capture process is ever launched |
| `debug_logger.ConversationDebugLogger._write()` | `CONTENT_LOGGING` | No JSONL line written (single chokepoint every `log_*` method funnels through) |
| `llm_router._generate_api()` | `CLOUD_LLM` | Returns `""`, no request sent |
| `claude_consultation._call_claude()` | explicit Anthropic provider + `CLOUD_LLM` | Requires `llm.api.provider: anthropic`, enabled cloud config, model, and credential; privacy denial raises before the client is constructed |

**Audit logging**: `enter()`/`exit()` log only `mode`, `actor`,
`timestamp`, `duration` via `core/logger.py` — never the `reason` text
passed to `enter()`, never content. Matches the requirement explicitly.

**Local control path**: `skills/system/privacy/skill.py` — German voice
intents ("Privatsphäre aktivieren", "Privacy Lock aktivieren",
"Privatsphäre beenden", status query) call `enter()`/`exit()` directly
on the in-process singleton. No separate control-plane/IPC needed since
every wired call site above shares the same process; this is the "local
CLI/control path is acceptable for now" fallback the task allowed,
implemented as a voice skill instead of a literal CLI since that was
just as simple given the existing skill-registration pattern.

**Session #5 tests**: `tests/unit/test_privacy_gate.py` (49 tests —
mode/capability matrix, flush/enter/exit callbacks, epoch-based race
guarantees, concurrent enter/exit stress test) and
`tests/unit/test_privacy_memory_integration.py` (real temp-file SQLite
`MemoryManager`, not mocked). Maps to the acceptance criteria named in
the task: PRIV-001 (audio) — covered at the gate+continuous_listener
level, not yet observed against real mic hardware; PRIV-002 (screen) —
covered; PRIV-003 (memory) — covered; PRIV-004 (cloud) — covered;
PRIV-005 (exit/no catch-up) — covered by the epoch race tests.

### Session #6: closed real gaps in the above, wired the deferred capabilities

Two real bugs found and fixed in session #5's own wiring — not new
features, gaps in what was already claimed done:

- **Audio ring-buffer leak.** Session #5 gated
  `_on_speech_start()`/`_process_speech()` (the speech-collection
  handoff), but `continuous_listener._audio_callback()` still fed
  every raw frame into `VoiceActivityDetector.process_frame()`
  unconditionally — which appends to `vad.audio_buffer` regardless of
  privacy mode, and that ring buffer is what `_on_speech_start()` reads
  as the pre-speech snapshot. So audio recorded *during* PRIVACY could
  still sit in the ring buffer and leak into the very first utterance
  captured right after exit. Fixed: `_audio_callback()` now returns
  before RNNoise/VAD processing when `MIC_INGEST` is denied, and the
  flush callback now also calls `vad.clear_buffer()` + `vad.reset()`
  (clears the ring buffer, resets Silero's hidden state and the
  speech/silence counters) on both enter() and exit(), not just
  `speech_buffer`/`_pre_speech_audio` as before.
- **Webcam capture kept running.** `start()` was gated (session #5),
  but a capture already running when privacy was entered was never
  stopped, and `get_frame()`'s <2s cached-frame shortcut plus
  `stream_frames()` didn't re-check the gate at all. Fixed:
  `WebcamManager` registers its own flush callback that stops any
  running capture (scheduling the async `stop()` onto whichever loop
  `start()` recorded, via `run_coroutine_threadsafe` with a bounded 5s
  wait) and clears `_current_frame`; `get_frame()`/`stream_frames()`
  both check `WEBCAM_CAPTURE` directly now.

Conversation persistence — three unconditional paths in
`conversation.add_message()`'s side-effect chain that session #5 only
partly covered (`memory_manager.on_message()` was gated; three others
weren't):
- `ConversationManager._append_to_history_file()` wrote every message
  to `chat_history.jsonl` unconditionally — reachable even from
  `jarvis_console.py`/`jarvis_web.py`'s typed-text paths, which never
  touch mic/STT at all, so this was a real bypass of the PRIVACY
  guarantee, not just an audio-path gap. Gated on `CONTENT_LOGGING`.
- `ContextWindow.on_message()` (topic-segment/embedding ingestion) —
  gated on `AGENT_CONTEXT_INGEST`.
- `ContextWindow._persist_segment()` (writes the full segment,
  including raw text, to SQLite) and `_summarize_segment()` (sends
  that transcript to the local LLM for summarization) — both ran from
  a background thread on every topic shift, not just at shutdown. Both
  gated on `SESSION_SUMMARY`, both take the same captured-epoch
  parameter as memory's background extraction (same race class, same
  fix).
Deliberate design choice, not an oversight: `ConversationManager.
session_history` (in-RAM) is NOT gated — the typed-text path has no
STT gate to rely on, so the user must still be able to get a coherent
reply (e.g. to type "privacy beenden"). Nothing added to it during
privacy is written anywhere; it disappears on process restart.

**Voice-exit is unreliable by design, not a bug to work around.**
`PrivacyGate` is a process-local singleton, and
`jarvis_continuous.py`/`jarvis_console.py`/`jarvis_web.py` are three
separate entrypoints/processes (each constructs its own
`ConversationManager` etc.) — so session #5's `PrivacySkill` only ever
reached whichever process's gate instance the text arrived in, not
necessarily the one actually running the mic pipeline. More
fundamentally: once `PRIVACY` is entered, `MIC_INGEST`/`STT` are both
denied, so spoken audio is never transcribed while privacy is active —
a spoken "Privatsphäre beenden" can never reach any intent matcher, in
any process, because there is no text for it to match against. A
special-case STT bypass for an exit phrase was explicitly ruled out
("kein STT-Bypass") since that would mean privacy-mode audio *is*
being transcribed after all. Fix: `core/privacy_control_watcher.py` —
a daemon thread polling three sentinel files
(`/tmp/.jarvis_privacy_enter|_lock|_exit`, existence-only, same trust
model as the existing `core/debug_logger.py` sentinel convention),
wired into `jarvis_continuous.py` (the one entrypoint with genuinely no
interactive text input) alongside `Watchdog`. Also maintains
`/tmp/.jarvis_privacy_status` (mode + timestamp only) via the gate's
own enter/exit callbacks, regardless of what triggered the transition.

~~Fail-closed by design: lock/enter checked before exit~~ **Session #7
found this backwards and fixed it.** Each `_consume()` call is a plain
state assignment (`gate.enter()`/`gate.exit()`), so within one poll
iteration whichever runs LAST is the actual final mode — the original
order (LOCK, ENTER, EXIT, i.e. EXIT applied last) meant EXIT actually
won any sentinel collision, the opposite of "the protective outcome
wins." The old regression test even asserted the buggy outcome (NORMAL
after a LOCK+EXIT collision) while calling it `test_lock_wins_over_
simultaneous_exit` — the bug was written into both the code and its own
test. Corrected order: EXIT, ENTER, LOCK (weakest first, strongest
applied last), so `PRIVACY_LOCK > PRIVACY > EXIT` now actually holds.
Also: `PrivacyControlWatcher` was only started in the event_mode branch
of `jarvis_continuous.py` — the legacy branch (mic/STT gating itself
still worked there, shared code in `continuous_listener.py`) had no way
to exit privacy at all. Started in both branches now.

**Memory escalation bug** (found while implementing the above,
confirmed with a repro script before fixing): session #5's "explicit
fact wins over a single conflicting inference" logic only handled the
*first* conflicting observation — `_find_similar_fact()` matches "the
most recent active row for this subject+category," and after the first
conflict creates a new active candidate row, a *second* matching
inferred observation found *that candidate* instead of the explicit
fact and reinforced it. Confirmed: confidence climbed 0.70 → 0.99
(`MAX_FACT_CONFIDENCE`) after 7 repeated conflicting observations,
while the actual explicit fact (0.90) sat untouched and was now the
*lower*-confidence row. Fixed via a new `excluded_from_matching`
column (idempotent migration) — see §5d for the full writeup, this is
the memory-side half of session #6's privacy/correctness work.

**Deferred capabilities wired this session**: `FILESYSTEM_OBSERVATION`
— `core/tools/find_files.py`'s `handler()` (single dispatch chokepoint)
and `skills/system/filesystem/skill.py`'s four registered intent
handlers (a separate, independent implementation with its own direct
filesystem reads — gating one does not cover the other). `REMOTE_TOOL`
— `core/mcp_client.py`'s `MCPBridge._make_sync_handler()`, the single
closure every registered MCP tool call funnels through. Per the
existing (unchanged) capability matrix: plain `PRIVACY` does **not**
block `REMOTE_TOOL`, only `PRIVACY_LOCK` does.

**Still deferred, do not assume covered**: `core/web_research.py` and
other external-API-reaching tools were not reviewed for `REMOTE_TOOL`
coverage this session — MCP was the clearest, most literally-named
"remote tool execution" abstraction actually verified. A true
remote/networked privacy control plane was still not attempted (the
task allows the local sentinel-file path for now).

**Session #6 tests**: `tests/unit/test_privacy_audio_reset.py` (6,
against the real `core/vad.py` — `continuous_listener.py` itself still
can't be imported in this sandbox, see §12),
`tests/unit/test_privacy_webcam.py` (8, real async methods against
`core/webcam_manager.py`), `tests/unit/test_privacy_conversation_
persistence.py` (11, real `ConversationManager`/`ContextWindow` against
tmp_path-backed files/SQLite), `tests/unit/test_privacy_control_
watcher.py` (15, real background-thread polling integration test),
`tests/unit/test_privacy_gate_audit_callsites.py` (11). Full
non-hardware unit suite by the end of session #6: 251 passed (was 159
at the end of session #4, 182 partway through session #5).

## 12. Lifecycle / shutdown audit (session #5)

Session #5 re-read `jarvis_continuous.py`'s shutdown `finally:` block
against everything it starts (continuing session #4's shutdown fix
above) and found two concrete gaps, both now fixed:

- **`Watchdog.stop()` was never called.** `core/watchdog.py`'s
  `Watchdog` is a daemon thread, started in `jarvis_continuous.py` when
  `watchdog.enabled` (config, default `True`), and exposes `stop()`
  (sets a `threading.Event`) — but grepping the shutdown block found
  zero calls to it. Being a daemon thread it wouldn't have blocked
  process exit, but its health-check loop and any in-flight recovery
  action never got a clean stop signal. Fixed: `self.watchdog.stop()`
  added to the `finally:` block, guarded by `hasattr`/truthiness so it's
  safe regardless of whether the watchdog was actually started.
- **`TextToSpeech._chatterbox_session` (a `requests.Session()` with its
  own connection pool, created once in `TextToSpeech.__init__`) was
  never closed.** Confirmed via a full-repo grep for
  `_chatterbox_session.close()` returning zero matches before this
  change. Fixed: closed right after `self.tts.kill_active()` in the same
  `finally:` block.

**Checked and found already adequate, not changed**: `MemoryManager`
has no persistent SQLite connection to close (each read/write already
opens a short-lived `sqlite3.connect()` per call — confirmed by reading
`_get_conn()`/`store_fact()`), so `memory_manager.save()` (already
called per the session #4 fix above) covers what actually needs
flushing (FAISS). Signal handlers' `sys.exit(0)` still reaches the
`finally:` block correctly (`SystemExit` unwinds through it regardless
of the `except KeyboardInterrupt` clause not catching that specific
exception type) — re-verified, not just assumed, by tracing the call
stack.

**Not audited this session, flagged as open**: background extraction
threads spawned by `memory_manager._trigger_batch_extraction()`/
`_trigger_per_turn_extraction()` are daemon threads with no explicit
join/cancel on shutdown — they'll die with the process, which is
probably fine (no partial-write risk, since `store_fact()` either
completes a full SQLite transaction or doesn't run), but wasn't
specifically verified this session. Consolidation/decay worker
lifecycle is moot since that mechanism doesn't exist yet (§14 item 12).

**Not testable in this sandbox**: `jarvis_continuous.py` is the
monolithic entrypoint and imports `core.continuous_listener` at module
scope, which requires the `sounddevice`/PortAudio native library — not
installable here (confirmed: `pip install sounddevice` succeeds but
`import sounddevice` raises `OSError: PortAudio library not found`).
Verified by code inspection and `python3 -m py_compile` only.

## 13. Sleepy systemd units (sessions #5-#7, NEEDS HW VERIFY)

`systemd/llama-server.service`, `systemd/chatterbox.service` (new — no
Chatterbox unit existed anywhere in the repo before session #5,
confirmed by grep), and `systemd/jarvis.service` use the real
`/home/alex/...` paths already present in `config.yaml` (which
`core/config.py` actually loads at runtime — not a placeholder file),
replacing the stale `/home/user/...` and `/mnt/models/...` paths in the
old root-level `jarvis.service`/`llama-server.service` (left in place,
not deleted, each with a one-line header pointing at the replacement).
Also fixed: `--ctx-size 32768` (was `8192`, now matches `config.yaml`'s
`llm.local.context_size`), `EnvironmentFile` for secrets instead of an
inline placeholder value, `Restart=on-failure` + sensible
`TimeoutStopSec`, `ExecStartPre` existence checks, and `jarvis.service`
soft-depending (`Wants=`/`After=`, not `Requires=`) on the other two —
matching the fallback logic that already exists in code
(`llm_router.py`'s cloud fallback, `tts.py`'s Piper fallback), so a down
llama-server/Chatterbox doesn't block JARVIS starting in degraded mode.

**Session #6 got the install strategy wrong; session #7 corrected it
with real evidence.** Session #6 recommended system-level units for
everything, based on architectural reasoning alone ("always-on services
should start before login") — without first checking whether an
established, working convention already existed. Session #7 grepped the
repo and found a complete, real, already-in-use control plane at the
root: `start.sh`/`stop.sh`/`restart.sh`/`status.sh`/`killswitch.sh`/
`jarvis_aliases.sh`, all built around `systemctl --user ...
jarvis.service`, plus `core/health_check.py`/`core/tools/developer_tools.py`
querying it the same way. **`jarvis.service` is a user unit — settled
by evidence, not a preference.** `llama-server.service`/
`chatterbox.service` stay system units (headless GPU servers, no
session/audio dependency of their own) — a reasoned guess, not
confirmed the way `jarvis.service` now is:
`developer_tools.py`'s own status check hedges on `llama-server`'s
scope (tries `--user`, falls back to system), so the codebase itself
isn't fully sure either. This split also converges with the Windows-
Audio target: a system-level unit starting before login has no path to
WSLg/Windows-Audio's session-tied forwarding — only a user unit
(running as that session) can reach it. `systemd/jarvis.service` was
rewritten as a proper user unit (`%h`-relative paths, no `User=` line).
The control-plane scripts themselves were the deeper gap: they never
managed `llama-server`/`chatterbox` at all (added session #5/#6, never
wired in) — `start.sh` now also enables+starts them (sudo, skipped
cleanly without passwordless sudo), `status.sh` reports all three
services, and `killswitch.sh` — an "emergency, stop everything" switch
that left the GPU servers running was a real functional gap — now stops
both and `pkill`s their process names directly as a second line of
defense. Full detail and the corrected install/verify steps are in
`systemd/README.md`.

**This session had no shell access to Sleepy** — no `whoami`, no
`realpath`, no way to confirm the venv, the `llama-server` binary, or
any model file actually exists at these paths, and no `systemctl`/
`journalctl` was run. `systemd/README.md` states this plainly, gives the
exact verification checklist (in order) and install steps for whoever
has real Sleepy access, and explicitly flags the one path that's a
genuine unknown rather than a documented target: whether Chatterbox
needs its own separate venv from the main `jarvis-venv` (its GPU/torch
dependency set may conflict with the main venv's pins — this couldn't
be checked without running on Sleepy). **Do not report this workstream
as validated until someone actually runs that checklist and records
real output** — that's the explicit instruction this section is
following, not an oversight.

Deliberately not included: `small-llm.service` — `config.yaml` names
`127.0.0.1:8081` as the small model's endpoint, but nothing in this
repo says what process/binary/model actually serves that port, and the
task said only add this unit "wenn der reale Small-LLM-Pfad zweifelsfrei
bestimmt werden kann."

## 14. Open work / recommended next steps

Roughly in priority order — see §3.4/§3.5 for TTS specifics, §5a-e for
German-first/memory specifics, §8/§9 for instrumentation/preflight.

**Resolved across sessions #3-7 (previously listed here, no longer open):**
honorific-default question · Chatterbox connection reuse/circuit
breaker/connect-timeout · streaming queue backpressure · sentence-final
numbers · ports/phone numbers · memory candidate/confirmed tiers +
reinforcement · value-based reinforcement-vs-supersede · sensitive-topic
risk gate · German memory rendering/commands/why-query · TTS startup
warmup contention · 3 CRITICAL bugs from the memory/concurrency reviews
(§5d/§5e) · real latency instrumentation (§8) · startup preflight script
(§9) · cancellable/bounded contextual-ack synthesis + its session #6/#7
stale-Piper-fallback gap (§3.4) · polarity-reversal memory bug + its
session #6 escalation gap (§5d) · central PrivacyGate P0 + its session
#6/#7 audio-ring-buffer/webcam/conversation-persistence/voice-exit/
watcher-priority/legacy-mode gaps (§11) · watchdog/Chatterbox-session
shutdown gaps (§12) · memory decay/consolidation/autonomy-budget +
session #7's real MERGE addition (§5d) · FILESYSTEM_OBSERVATION/
REMOTE_TOOL call-site audit (§11) · systemd --user-vs-system install
strategy, corrected with real evidence and wired into the actual
control-plane scripts (§13) · **session #7 additions**: shell-command-
chaining bypass in developer_tools' safety classifier (CRITICAL) ·
MCP tool-call timeout not cancelling its coroutine · skill_manager
audit-logging gap + PrivacyGate awareness for it and the pre-existing
tool_registry audit log · developer_tools confirmation-slot race ·
confirmed-dead prototype skill deleted. · **session #8 additions**:
argument/pipe bypass in developer_tools' safety classifier (CRITICAL,
session #7's chain-operator fix alone wasn't enough) · developer_tools
`run_command`/`confirm_pending` hardcoded stale `cwd` · four ungated
content-bearing tool/skill logs (`tool_registry.execute_tool`,
`llm_router.stream_with_tools` ×2, `tool_gate.should_include_tools`,
`generate_image.handler`) · `PrivacyControlWatcher` sentinels moved off
world-writable `/tmp` · TaskPlanner cooperative mid-step cancellation ·
Watchdog background-worker visibility.

1. **German-first backlog — ~330-340 strings across ~12 files, see the
   table in §5a.** The single largest remaining piece of work. Still not
   attempted after three sessions — P0 correctness/privacy work has
   consistently outranked it. `skills/personal/conversation/skill.py`
   (~90, confirmed active) is the best first target. Per session #5's
   pass over `skills/system/*`: `app_launcher/skill.py` is the most
   English-heavy (~64 strings), `file_editor/skill.py` is a partial
   migration (~20 remaining), `conversation/skill.py` itself has ~2
   stray strings left.
2. Live GPU run of the Chatterbox streaming path and every
   PrivacyGate-gated Chatterbox/webcam/mic code path — this environment
   has no CUDA/audio hardware, so all of it is verified with fakes/mocks
   but not yet observed against real hardware. Do this before relying on
   any of it in production, and before reporting any "NEEDS HW VERIFY"
   item in this document as done.
3. Kokoro/Chatterbox `_tts_lock` scope inconsistency (§5e) — not fixed,
   Kokoro is inactive. The Kokoro branch of `speak()`'s Piper-fallback
   logic also still lacks session #6's `cancel_check` guard (§3.4) — same
   reason, same dormant-bug-class note.
4. Redesign fact storage/extraction to not be English-sentence-shaped
   (§5b) — `render_fact_de()` works around this for facts with a
   structured `value`; older/one-group-extracted facts still fall back
   to raw English content.
5. Embedding-based contradiction detection for memory facts (§5c/§5d
   explain why text-similarity doesn't work — don't repeat that
   attempt). The keyword-lexicon polarity check (§5d) and
   `excluded_from_matching` (§5d, session #6) are narrower, cheaper
   fixes for specific cases, not a replacement for this.
6. Vocal-behavior layer: `chatterbox_server.py` accepts per-request
   `exaggeration`/`cfg_weight`/etc. overrides; no policy exists yet for
   when to use them.
7. Decide the fate of `core/tts_normalizer.py` (unused) and
   `core/health_check.py`'s `format_voice_summary()` (confirmed dead
   code) — delete or document as intentionally kept.
8. Delete `legacy_backups_20260915/` once confirmed unneeded.
9. `tests/unit/test_edge_cases.py` phase 7C-03 (`"Dr. Smith..."`) — stale
   test expectation, not a pipeline bug.
10. **Sleepy systemd units — written, corrected, and given a
    consistent (system-level primary, user-level fallback) install
    strategy this session, but NEEDS HW VERIFY — see §13 and
    `systemd/README.md`.** Not installed, not started, no real
    `systemctl`/`journalctl` output exists yet. This is now purely a
    "run the checklist on Sleepy" item — nothing left to design.
11. STT hot-path, LLM TTFT, fast-paths for deterministic local
    commands — all require live hardware measurement. **§8's
    instrumentation exists; the next step on Sleepy is: run real turns,
    read the `JARVIS LATENCY` lines, let the actual bottleneck decide.**
    §8's checkpoint set is STILL not extended to the full
    `speech_end`→...→`response_done` chain — confirmed again this
    session, same root cause as session #5 found: no turn-id/tracker
    handoff exists between `continuous_listener.py`'s callback thread
    and `core/pipeline.py` (where the tracker is created, at
    `command_received`). Not attempted in session #6 either — a real,
    separate piece of work, deliberately not rushed.
12. **XTTSv2-Streaming-ONNX + Windows Audio as the primary local TTS
    path — a real architectural target named this session, NOT
    attempted.** The model lives at a Windows path
    (`C:\Users\Alex\Projekte\KI\Modelle\.onnx\XTTSv2-Streaming-ONNX`)
    this Linux sandbox has no access to, and there is no Windows
    environment here to build or test a Windows-Audio-backend
    integration against. Implementing this blind — guessing at the
    ONNX runtime API, the streaming chunking behavior, and the
    Windows audio backend's actual interface — would mean shipping
    unverified code against a path this session couldn't even confirm
    exists, which is exactly what §13's "nicht raten" discipline exists
    to prevent. Chatterbox/Piper remain the active local TTS path
    (§3) — nothing about them was degraded to make room for this.
    Genuinely needs a session with access to that Windows machine (or
    at minimum the ONNX model files and a way to exercise ONNX Runtime)
    to do responsibly.
13. **Agentic system audit — done in session #7, ~10 findings; session
    #8 closed two more (TaskPlanner cancellation, Watchdog visibility —
    see the session #8 summary at the top of this doc), 3 remain open:**
    - `core/tool_gate.py` is not actually a permission/security gate
      despite its name — it only decides whether tool *schemas* are
      included in the LLM prompt (token-saving), with no authorization/
      allowlist/capability check anywhere. Any tool the LLM calls
      executes via `tool_registry.execute_tool()` unconditionally.
      Rename or build the permission layer the name implies — currently
      neither has happened.
    - No skill-level capability/permission model at all —
      `core/base_skill.py`/`core/skill_manager.py` give every skill full
      access to `config`/`conversation`/`tts`/`responses` and skills
      freely `import subprocess`/`os`. Any dropped-in skill directory
      with a valid manifest loads at the same trust level as core
      skills. Architectural root cause underlying the chaining bypass
      fixed in sessions #7/#8 — those fixes close the exploitable paths
      found so far, not the underlying lack of containment.
    - MCP server config (`config.yaml`'s `mcp_servers` section) is
      fully trusted — subprocess command/args taken verbatim, full
      `os.environ` inherited before per-server overrides. Fine for a
      config file only the local admin edits; no guard if `config.yaml`
      were ever machine-written by a future self-modification feature.
    - ~~`TaskPlanner.execute_plan()` can only cancel *between* steps~~
      **— session #8: added a cooperative mid-step cancellation token
      (`current_cancel_event()`), consumed by `web_research.py`'s
      parallel page fetch. Only one real consumer wired up so far —
      `core/tools/developer_tools.py`'s `run_command()` subprocess has
      no cancellation seam at all (blocking `subprocess.run()`); would
      need a Popen+poll rewrite, left open.**
    - ~~`Watchdog._run_checks()` has no visibility into `TaskPlanner`'s
      active plan or the poll-thread managers~~ **— session #8: added
      `task_planner`/`reminder_manager`/`weather_poller`/`news_manager`
      as optional Watchdog inputs; detects dead/stuck poll threads and
      plan steps stuck past `command_hung_threshold`. Detection +
      structured-event logging only — no auto-restart, since a blind
      restart could have side effects (e.g. re-firing a reminder) the
      watchdog can't reason about safely. `get_background_health()`
      gives a metadata-only snapshot for a future `system_health`
      integration.**
    `skills/system/_in_development/web_navigation/` (confirmed dead by
    directory-depth, a stale v1.0.0 fork) was deleted in session #7.
13a. **Unified Skill/Tool/MCP capability-permission model — named as the
    session #8 goal for the three findings above, deliberately NOT
    attempted.** This is a real architectural undertaking (declared
    capabilities per skill/tool/MCP server, central enforcement points,
    local/remote distinction, PrivacyGate integration, destructive-
    action confirmation, auditable decisions, default-deny) that
    touches `core/base_skill.py`, `core/skill_manager.py`,
    `core/tool_gate.py`/`core/tool_registry.py`, and `core/mcp_client.py`
    simultaneously, and the task's own instructions are explicit that
    it must not blindly break any of the ~15+ existing skills — that
    needs a real migration plan and a full regression pass most of
    which is untestable without a live pipeline run on real hardware
    for the voice-driven skills. Rushing a partial version in the time
    remaining this session would risk exactly that breakage. Left as a
    dedicated next-sprint item with its own design pass, not bundled
    into the smaller, independently-testable pieces (TaskPlanner
    cancellation, Watchdog visibility) session #8 did complete.
13b. **Broader content-logging audit (session #8 follow-up, background
    subagent, NOT fixed — see §14's session #8 summary for the 4 sites
    that WERE fixed).** Found a much larger separate content-logging
    surface, ranked most-sensitive first: raw voice transcription/
    command text logged unconditionally at 15+ call sites across
    `core/continuous_listener.py` (`_transcribe_and_check`) and
    `core/pipeline.py` (looks like a duplicate/refactored copy of the
    same flow) — both import `sounddevice` and cannot be imported or
    exercised at all in this sandbox, so any fix here is currently
    unverifiable without real hardware; extracted-fact text and
    proactive-surfacing phrases in `core/memory_manager.py`; spoken
    response text in `core/tts.py`; raw search queries in
    `core/web_research.py`; command/interrupt text in
    `core/task_planner.py`; routing-decision command/query text in
    `core/conversation_router.py`; personal-fact content in
    `core/people_manager.py`; full announcement text in
    `core/watchdog.py`. Each of these is real and should eventually be
    gated the same way the session #7/#8 fixes were, but mass-editing
    ~15 sites across several large, partly-untestable files without
    being able to run and verify each one contradicts this project's
    own "never fabricate test results" discipline — a dedicated
    follow-up session should work through this list file by file with
    real tests for each, same as sessions #7/#8 did for the smaller set.
14. **Generic proactive/event-notification layer** (service/hardware/
    security events, reminders, background-task results, scheduled
    tasks, with policy/severity/destination/channel-adapter concepts,
    WhatsApp/phone as later adapters) — named again this session ("if
    passend"), still not attempted. Building a new cross-cutting
    subsystem without first confirming none of the existing pieces
    (`reminder_manager.py`, `news_manager.py`, `weather_poller.py`,
    `event_logger.py`, `watchdog.py`'s recovery actions — session #8's
    Watchdog visibility work (item 13 above) touched several of these
    but only added read-only observation, not an event/policy/channel
    layer) already cover enough of this need would risk exactly the
    "zweite konkurrierende Engine" earlier sessions were told to avoid.
    A real audit of what `reminder_manager`/`news_manager`/
    `event_logger` already do vs. what a unified Event → Policy →
    Severity/Urgency → Channel path would add is still the prerequisite
    step, not built in parallel with it.

## 15. Presence face backend: CPU / Intel NPU (2026-09-25)

Status: **NPU path implemented and proven on file input; live camera not available; identity threshold not calibrated.**

- **Seam.** `core/presence_detector.py::_get_face_app()` returns either the CPU `insightface.FaceAnalysis` (default) or `core/npu_face_backend.py::NpuFaceBackend`. Both expose `.get(frame_bgr) -> [face]` with `bbox` / `normed_embedding`. Matching, state machine, greetings and enrollment are unchanged.
- **Config** (`vision.presence`): `backend: cpu | npu | auto` (code default `cpu`; `config.yaml` sets `auto` since 2026-09-25), `npu.windows_python`, `npu.model_dir`, `npu.fallback_to_cpu`, `npu.request_timeout`. `windows_python` may also come from env `JARVIS_NPU_WINDOWS_PYTHON`; empty means the NPU is unavailable. Permanent Windows environment: `C:\Users\Alex\AppData\Local\JARVIS\npu-venv` (Python 3.14.7, `openvino` 2026.4.0, `numpy` 2.5.3, `openvino-telemetry` 2025.2.0; only these packages, global Python untouched).
- **Why a Windows worker.** WSL2 cannot use the NPU (no `/dev/accel`; dxg escape calls are rejected by the host, microsoft/WSL#40445). `NpuWorkerClient` starts `tools/openvino_npu_worker.py` under a Windows Python through the same WSL->Windows interop the audio bridge uses (stdin/stdout, length-prefixed JSON + raw tensors). No port, no firewall rule, no second control plane. If `WSLInterop` is missing the backend reports `interop_unavailable`.
- **Work split.** WSL does SCRFD pre/post-processing and ArcFace alignment (`insightface.utils.face_align.norm_crop`, the same code as the CPU path). The worker compiles `det_10g.onnx` at `[1,3,640,640]` and `w600k_r50.onnx` at `[1,3,112,112]` on `NPU` (in-memory input reshape only) and runs tensors. It refuses a model whose `EXECUTION_DEVICES` does not contain `NPU`.
- **Models.** `<system.storage_path>/models/insightface/buffalo_l/{det_10g.onnx,w600k_r50.onnx}` (official `buffalo_l.zip`, model-zoo release; SHA-256 pinned in `core/npu_face_backend.py`, verified by the worker before compiling). Not modified.
- **Fallback.** NPU init failure -> visible warning, `get_status()['backend'] = {requested, active, reason}` and CPU InsightFace (unless `fallback_to_cpu: false`, then nothing runs on CPU and the reason stays in the status). A worker failure at runtime switches to CPU once, visibly. Sticky until restart. The CPU path downloads `buffalo_l` to `~/.insightface` on first use if it is not there.
- **Camera.** The detector is constructed even without `/dev/video0` (`jarvis_continuous.py` only catches `FileNotFoundError` from `webcam_mgr.start()`); `get_status()['camera']` is `UNAVAILABLE`, polling idles, no frames are faked. A camera plugged in later needs a JARVIS restart (the webcam event loop is only wired at start). A Windows webcam (e.g. Smart Connect) is **not** a supported capture path; a real V4L2 webcam in WSL (usbipd) is the precondition for live presence.
- **Identity threshold.** `face_confidence_threshold: 0.6` is a configured value, **not calibrated**. Measured only: same-person cosine 0.555-0.958 over 13 photos of one person; no impostor data. `get_status()['matching']` and `PresenceDetector.last_matches` expose similarity, threshold and `threshold_validated: false`. Do not use it as sole authorisation. Calibration needs impostor data and is a separate step.
- **Tests.** `tests/unit/test_presence_npu_backend.py` (decoding, selection/fallback/states with a fake backend; `test_real_npu_smoke` runs the real worker on the NPU when `JARVIS_NPU_WINDOWS_PYTHON`, `JARVIS_NPU_SMOKE_PHOTOS` and the models exist).
