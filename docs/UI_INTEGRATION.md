# JARVIS HUD — UI Integration & Event Contract

Branch `claude/jarvis-ui`, built in worktree `/home/alex/jarvis-ui` while a
separate agent works on `claude/jarvis-architecture` (voice pipeline, TTS,
streaming, memory). This document is the handoff point between the two:
what the HUD needs from the backend, what already exists and was reused,
what's stubbed/mocked today, and exactly what would need to change in
`core/pipeline.py` / `jarvis_continuous.py` to make the mocked parts real —
without this branch having touched either file.

## 1. What was found or reused

- **`jarvis_web.py`** already runs an aiohttp server with a single
  WebSocket endpoint (`/ws`) and a JSON message envelope
  (`{"type": "...", ...}`) used for ~15 message types (`stream_start`,
  `stream_token`, `stream_end`, `announcement`, `stats`, `system_stats`,
  `voice_status`, `user_changed`, ...). This is the **only** transport the
  HUD uses — no new server, port, or protocol was introduced.
- **`app['ws_connections']`** (a `dict[WebSocketResponse, ConnectionContext]`)
  already existed for targeted weather-alert routing. Reused as-is to
  broadcast the new `assistant_state` event to every connected client.
- **Auth**: reused the existing `?token=` query-param convention
  (`_check_auth_token`, `web/app.js`'s `authUrl()`), including the sidebar
  nav links' click handler that appends the token automatically.
- **`web/index.html` / `web/app.js`**: the existing chat/dashboard UI was
  **not replaced**. A new page was added alongside it (`/hud`), reachable
  from the sidebar ("JARVIS HUD"), because the two serve different
  purposes — one is a text-chat + admin-dashboard app, the other is a
  fullscreen ambient display. Forcing them into one page would have
  compromised both.

## 2. New backend surface added (jarvis_web.py only)

No file outside `jarvis_web.py` and `web/*` was touched. Specifically NOT
touched: `core/pipeline.py`, `core/tts.py`, `core/continuous_listener.py`,
`jarvis_continuous.py`, or anything else the architecture-branch agent
owns.

| Addition | Where | Purpose |
|---|---|---|
| `GET /hud` → `hud_handler` | `jarvis_web.py` | Serves `web/hud.html` |
| `_broadcast_assistant_state(app, state, **extra)` | `jarvis_web.py` | Pushes `{"type": "assistant_state", "state": ..., "timestamp": ...}` to every connection in `app['ws_connections']`; also stores it as `app['assistant_state']` |
| `app['assistant_state']` init in `on_startup` | `jarvis_web.py` | So a client connecting mid-conversation gets the current state immediately (sent right after `ws_conns[ws] = conn_ctx` in `websocket_handler`), not silence until the next transition |
| `WebTTSProxy.on_state_change` hook + `_speak_and_notify()` | `jarvis_web.py` | Every `tts_proxy.speak(...)` call (skills, reminders, alerts, LLM fallback) now brackets real audio with `speaking` → `idle`, instead of the HUD guessing from a timer |
| `_handle_chat_message(..., app=None)` | `jarvis_web.py` | Broadcasts `thinking` at the start of processing a message, `error` on exception, `idle` at the end **only when voice is off** (see §4 — when voice is on, the TTS bracket owns that transition instead, to avoid a race) |

## 3. Event contract

### `assistant_state` (implemented, real)

```json
{"type": "assistant_state", "state": "thinking", "timestamp": 1758000000.123}
```

`state` is one of the 10 identifiers below (internal/wire identifiers are
English; the HUD renders German labels — see `STATE_LABELS` in `hud.js`).
An optional `command` field (short string) is shown in the HUD's command
readout when present.

| State | Currently emitted by | German label |
|---|---|---|
| `offline` | client-side only (WS disconnected) | Offline |
| `idle` | `_handle_chat_message` (voice off) / TTS bracket (voice on) | Bereit |
| `wake_detected` | **not yet wired** — see §4 | Aktiviert |
| `listening` | **not yet wired** — see §4 | Hört zu |
| `transcribing` | **not yet wired** — see §4 | Verarbeitet |
| `thinking` | `_handle_chat_message` (message received → processing) | Denkt nach |
| `tool_execution` | **not yet wired** — see §4 | Führt aus |
| `speaking` | `WebTTSProxy._speak_and_notify` (brackets every real `speak()` call) | Spricht |
| `interrupted` | **not yet wired** — see §4 | Unterbrochen |
| `error` | `_handle_chat_message` exception handler | Fehler |

### `audio_level` (contract defined, not yet emitted)

```json
{"type": "audio_level", "rms": 0.37, "peak": 0.61}
```

`rms`/`peak` are floats in `[0, 1]`. `hud.js`'s `handleServerMessage()`
already routes this to `setAudioLevel()`, which drives the core pulse and
energy-ring waveform during `speaking` — the client side is done and
waiting. **No backend currently sends this.** See §4 for what emitting it
for real would take.

## 4. What's mocked and what the backend would need to add

The web chat path (`jarvis_web.py`) is text-in/text-out; it has no mic,
no wake word, no STT, so `wake_detected` / `listening` / `transcribing`
have no natural home there. Those states are meaningful for the **voice**
runtime (`jarvis_continuous.py` + `core/pipeline.py`'s `Coordinator`),
which today has no WebSocket or event-emission of any kind — it's a
standalone process talking to speakers/mic directly.

**This branch deliberately did not add that wiring**, per the
parallel-development instructions (avoid `core/pipeline.py` while the
architecture branch is actively changing it). Documented instead — and
corrected here after an earlier draft of this section got the process
topology wrong (see below).

**`jarvis_continuous.py` and `jarvis_web.py` are two separate OS
processes** (separate `python3` invocations, separate interpreters,
separate memory spaces — check how they're launched, e.g. `start.sh` /
the systemd units, to confirm this on the real deployment). Nothing
defined inside one process's memory — including a queue, list, or
pub/sub object built from `core/events.py`'s `EventType` — is reachable
from the other just because both files `import` the same module. Each
process gets its own independent copy of anything at module scope.
Making an event cross that boundary requires an actual transport: a
socket, a shared file/database polled by both sides, or one process
acting as a network client of the other. `core/events.py`'s `EventType`
enum is still useful here — as the shared *vocabulary* for what to send —
but it is not, by itself, a transport, and no wiring described below
should be read as "just subscribe to the same queue."

To make `wake_detected` / `listening` / `transcribing` / `tool_execution` /
`interrupted` real, the voice runtime would need to publish its existing
`Coordinator._dispatch()` event transitions (`SPEECH_STARTED`,
`SPEECH_FINISHED`, `COMMAND_DETECTED`, tool-call start/end, a barge-in/
interrupt signal — `Coordinator._dispatch()` in `core/pipeline.py` is the
single choke point they already all pass through) across an actual
process boundary. Two options that use a real transport, neither
requiring more than a subscriber callback at that one choke point:

1. **Simplest, and the one this doc originally under-specified**:
   `jarvis_continuous.py` opens an outbound WebSocket connection *into*
   `jarvis_web.py`'s already-running `/ws` endpoint, the same way a
   browser tab does (privileged internal client, e.g. a fixed internal
   token rather than the user's). It forwards each `Coordinator` event as
   an `assistant_state` message down that real network connection, which
   `_broadcast_assistant_state` then fans out to every browser tab
   exactly as it does today for web-originated states. Requires
   `jarvis_web.py` to be running for voice-originated states to reach the
   HUD — reasonable, since the HUD itself is served by `jarvis_web.py`.
2. **If the voice process must work without `jarvis_web.py` running**: a
   small local IPC channel directly between the two processes — a Unix
   domain socket or a loopback TCP socket that `jarvis_web.py` listens on
   and `jarvis_continuous.py` connects to (or vice versa), carrying the
   same JSON envelope. More moving parts than option 1, only worth it if
   the two processes' lifecycles genuinely need to be independent.

Either way, this is a `core/pipeline.py` change (a subscriber callback at
`Coordinator._dispatch()`) and belongs with whoever owns that file next,
reviewed together rather than added unilaterally from this branch.

For `audio_level`: the voice runtime would need to expose the live PCM
buffer/amplitude during TTS playback (Kokoro/Chatterbox streaming, see
the architecture branch's `StreamingAudioPipeline`) and during mic input
(VAD RMS is already computed internally for endpointing — `core/vad.py` —
just not published anywhere external today), then send it across the same
transport as above. Same shape as the state events, same caveat: no
transport, no bridge, regardless of which process computes the number.

**Until then**: `?demo=1` (see §5) exercises every one of the 10 states
and a synthetic `audio_level` stream, so the visual design and animation
timing can be fully built and tuned today without any of this existing.

## 5. Demo / debug mode

`GET /hud?demo=1` — never touches the network (skips `connect()` entirely),
shows a control panel (top-right) with one button per state and a slider
that drives a synthetic speaking envelope (`hud.js`, bottom section). Not
rendered at all without `?demo=1` — checked once via
`URLSearchParams(location.search).get('demo') === '1'` at load, no runtime
toggle, so there's no way to accidentally surface it in normal use.

A `window.__jarvisHud` debug handle is also exposed
(`{stateMachine, setAudioLevel, CONFIG}`) for console-driven testing
(`__jarvisHud.stateMachine.set('speaking')`) independent of the panel.

## 6. Known gaps / follow-ups

- **`stream_start`/`stream_end` vs. real speech**: when voice output is
  disabled, `stream_start` is the closest available signal to "JARVIS is
  responding," but the HUD deliberately does **not** show `speaking` for
  it (see `hud.js`'s `handleServerMessage`) — that state is reserved for
  actual TTS audio via the `WebTTSProxy` bracket, so it never lies about
  audio that isn't playing. Text-only mode will show `thinking` → `idle`
  with no `speaking` phase at all, which is correct but means the HUD
  looks less "alive" when voice is off. Not fixed — this is a deliberate
  accuracy-over-liveliness tradeoff, flag if the visual reference wants
  otherwise.
- **Error state has a 2.5s client-side auto-clear** (`hud.js`) as a safety
  net: if an error occurs while voice is on but before any `speak()` call
  happens, nothing server-side would ever announce `idle` afterward (the
  `_handle_chat_message` `finally` only self-announces idle when voice is
  off, to avoid racing the TTS bracket). The client-side timeout covers
  that gap; a more precise fix would be for the exception handler to know
  whether TTS was actually about to fire, which it currently can't.
- **Multi-tab / multi-client**: `assistant_state` is broadcast to *every*
  connected `/ws` client — if two browser tabs (or a phone + the kiosk
  display) are open at once, both see the same global state, which is
  correct for "what is JARVIS doing" but means one user's typed chat
  message will show up as `thinking`/`speaking` on someone else's HUD too.
  Matches the existing announcement/alert broadcast behavior (not a new
  limitation introduced here).
- `core/tts_normalizer.py` / German-first / memory / latency work: out of
  scope for this branch — see the architecture branch's own
  `docs/ARCHITECTURE.md` for that audit.

## 7. Second pass — bug fixes and visual/motion revisions (2026-09-16)

Found via a `code-review` skill pass on the diff plus four independent
review agents (visual design, animation/motion, accessibility, performance)
and one final adversarial quality pass, all reviewing by reading the code
only (no browser available in this environment — see each finding for
what's verified vs. inferred). Fixed:

**Backend (`jarvis_web.py`)**
- `_broadcast_assistant_state` called `asyncio.get_event_loop()` from
  inside a worker thread (`WebTTSProxy`'s TTS thread), which either
  raises or can return the wrong loop — every speaking/idle broadcast
  from that path was silently a no-op. Fixed: `app['loop']` is now
  captured once via `asyncio.get_running_loop()` in `on_startup` (which
  does run on the real loop) and reused everywhere.
- 10 call sites bypassed `WebTTSProxy` entirely
  (`threading.Thread(target=tts_proxy.real_tts.speak, ...)`), so none of
  them ever produced a `speaking` HUD state. All now route through
  `tts_proxy.speak(...)`.
- Overlapping `speak()` calls (e.g. two lines from a skill fired close
  together) could race the HUD into `idle` while a later call was still
  speaking. Fixed with a reference count (`_active_speak_count`) on
  `WebTTSProxy`: `speaking` fires on the 0→1 transition, `idle` on 1→0,
  never per-call. Verified with a standalone script simulating two
  overlapping `speak()` calls (see commit) — no idle flicker mid-overlap.
- This doc's own §4 previously implied a shared in-memory queue could
  bridge `jarvis_continuous.py` and `jarvis_web.py` — corrected: they are
  separate OS processes with separate memory: an in-process object never
  crosses that boundary; a real transport (a client/server WebSocket
  connection, or a local socket) is required either way.

**Visual / motion (`hud.js` / `hud.css`)**
- Idle marker flicker restarted the same marker every ~650ms for the
  whole 3-7s gap instead of flickering once (a scheduling bug, not a
  design choice) — fixed.
- The `interrupted` "flinch" formula could never go negative, so it only
  ever dipped and eased back, not the documented dip-then-rebound
  oscillation — fixed (and now auto-reverts to `listening` afterward,
  instead of drifting into looking identical to `error`).
- Reduced motion was inconsistently gated: membrane wobble, marker
  chase/flicker/pulse, the energy ring, and the envelope-driven
  core/nucleus reaction during speaking all ran regardless of
  `prefers-reduced-motion`, contradicting this file's own stated intent.
  All are now gated by `motionActive`; wake/interrupt keep a
  non-scaling opacity cue so the transition is still visible without
  growth/shrink motion.
- `transcribing` was mapped to the same internal state group as
  `thinking`, making them motion-identical except for a
  near-invisible scan-sweep speed difference. `transcribing` now has
  its own group (listening-like inward bias, static markers, no chase).
- `--state-idle` and `--state-speaking` were the identical hex value;
  speaking is now a distinct brighter tone.
- `--eye-size`'s breakpoint overrides made the eye a *smaller* fraction
  of the screen at 1440p/4K than at 1080p — the opposite of the stated
  "stays dominant at every target resolution" goal. Replaced with a
  single `vmin`-based formula, which scales proportionally by
  construction instead of needing per-breakpoint tuning.
- Membrane path lacked the frame-skip caching the energy-ring path
  already had, rebuilding an unchanging 72-point path string every
  frame in static states. Added.
- Removed a dead CSS rule (`animation: none` targeting a CSS `animation`
  property nothing in the file ever sets — all motion is JS-driven SVG
  attribute writes, not `@keyframes`).

**Not fixed / acknowledged as open**: the reviews also raised several
MEDIUM/LOW items (further hue separation between remaining close state
colors, unifying CSS transition durations, whether `thinking`'s several
independent-frequency motions read as "processing" or as visual noise)
that are documented here rather than changed, since they're closer to
taste calls the user's incoming visual reference should settle than
clear defects — revisit once that reference lands.

## 8. Third pass — findings from an adversarial final review (2026-09-16)

A final review agent, briefed only to find weaknesses (not confirm the
above fixes worked), read the post-fix code fresh and found several more
real issues. Fixed:

- `window.matchMedia(...)` was called with no guard; every other browser
  API touch in this file is defensive, but a missing/throwing
  `matchMedia` here would have taken down the entire IIFE before a
  single frame rendered. Now wrapped in try/catch with a `false` fallback.
- The reduced-motion CSS block shortened transitions on 3 of the 5
  elements that share the `0.45s stroke/fill` rule (`#ring-rotor-b
  circle`, `.ring-markers circle`, `.ring-energy-wave`, `.membrane`,
  `.particles circle`) — markers, the energy-ring path, and the membrane
  were missing, so their color still animated for 450ms per state change
  under reduced motion despite the file's own comment claiming otherwise.
  All five are now covered.
- `wake_detected` shares `listening`'s STATE_GROUP, so the one-shot
  shockwave ring was the *only* thing distinguishing it from `listening`
  — if that single layer were ever hidden (z-index issue, a future merge
  conflict), the two states would be pixel-identical. The core itself
  now gets a brief, fast-decaying radius boost during the wake window too.
- `CONFIG.tool.sectorSweepDegPerSec` was dead — read nowhere in the file,
  despite an inline comment implying it was a working toggle. Removed
  (with a comment on where to add a real one if a sweeping, rather than
  fixed, tool sector is wanted later).
- This doc's own state/label table (§3) didn't match `hud.js`'s actual
  `STATE_LABELS` (listed imperative-ish forms like "Höre zu" where the
  code renders third-person "Hört zu", etc.) — corrected to match exactly.
- `Math.exp(-(d*d)/cfg.spread)` in the thinking marker chase divides by
  `cfg.spread` with no guard; `spread <= 0` (a plausible future tuning
  typo) would produce `NaN` opacity and silently kill the whole chase
  effect. Guarded with a floor value.
- `offline` kept several motion sources running that `idle` also uses
  (nucleus shimmer, rotor rotation at idle's slow-but-nonzero rate,
  particle orbit), undercutting its purpose as the one state that should
  read as genuinely at rest rather than "quietly alive" like idle. Rotors
  now fully stop and the nucleus shimmer is skipped in `offline`;
  particles freeze their orbit angle but keep their last drawn position
  (skipping the loop outright would leave them stacked at the SVG origin
  on first load, since the app boots directly into `offline` and nothing
  else ever gives them an initial position).
- "Reduced Motion testen" (demo panel, English term in otherwise German
  UI copy) → "Reduzierte Bewegung testen".

**Acknowledged as open** (documented, not changed — see the review for
full reasoning): `tool_execution`/`error`/`interrupted` fall back to the
same idle-style membrane wobble once their primary differentiator
(sector arc / error ring / flinch) finishes or is otherwise not visible,
so a failure of that one secondary layer would make them read as idle at
the membrane level too — a real but lower-severity version of the same
"single point of differentiation" pattern fixed for wake above; and
`thinking`'s six-ish independently-phased motions (rotors, 3 particle
bands, membrane, marker chase, nucleus shimmer, scan sweep) were flagged
as possibly reading as noise rather than one coherent "processing"
gesture when all overlaid — a judgment call left for visual verification
against tomorrow's reference rather than blind rebalancing today.
