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
| `listening` | **not yet wired** — see §4 | Höre zu |
| `transcribing` | **not yet wired** — see §4 | Verarbeite |
| `thinking` | `_handle_chat_message` (message received → processing) | Denke nach |
| `tool_execution` | **not yet wired** — see §4 | Führe aus |
| `speaking` | `WebTTSProxy._speak_and_notify` (brackets every real `speak()` call) | Spreche |
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
architecture branch is actively changing it). Documented instead:

To make `wake_detected` / `listening` / `transcribing` / `tool_execution` /
`interrupted` real, the voice runtime would need to publish its existing
`core/events.py` `EventType` transitions (`SPEECH_STARTED`,
`SPEECH_FINISHED`, `COMMAND_DETECTED`, tool-call start/end, a barge-in/
interrupt signal) somewhere a browser can reach. Two isolated, low-risk
options (neither requires touching `Coordinator`'s dispatch logic beyond
adding a subscriber callback):

1. **Simplest**: `jarvis_continuous.py` also opens a connection into
   `jarvis_web.py`'s `/ws` (as a privileged internal client) and forwards
   `assistant_state` events into the same `_broadcast_assistant_state`
   path already built here. No new server.
2. **Cleaner long-term**: a small pub/sub queue in `core/events.py` that
   `Coordinator._dispatch()` already pushes every `Event` into (it's a
   single choke point — `Coordinator._dispatch()` in `core/pipeline.py`),
   which either process can subscribe to. This is the kind of change that
   belongs to whoever owns `core/pipeline.py` next, reviewed together
   rather than added unilaterally from this branch.

For `audio_level`: the voice runtime would need to expose the live PCM
buffer/amplitude during TTS playback (Kokoro/Chatterbox streaming, see
the architecture branch's `StreamingAudioPipeline`) and during mic input
(VAD RMS is already computed internally for endpointing — `core/vad.py` —
just not published anywhere external today). Same "small adapter, not a
core rewrite" shape as above.

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
