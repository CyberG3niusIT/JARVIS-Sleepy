# systemd units — status: NEEDS HW VERIFY

These three units were written and corrected in a session that had **no
access to the real Sleepy machine** — no shell, no `systemctl`, no way to
run `whoami`/`realpath`/check that a binary or model file actually exists
at a given path. Per the task's own instruction ("Nicht raten" / "Keine
erfolgreiche Servicevalidierung behaupten, wenn sie nicht tatsächlich
ausgeführt wurde"), none of this was installed or started, and nothing
here should be reported as verified until someone runs the checklist
below on Sleepy itself.

## Why these paths, if unverified

`config.yaml` (root of this repo, already committed, already the file
`core/config.py` actually loads at runtime) contains concrete
`/home/alex/jarvis-data/...` and `/home/alex/llama.cpp` paths — not
placeholders. That's the strongest evidence available in this session that
Sleepy's real user is `alex` and the real layout matches
`/home/alex/jarvis`, `/home/alex/jarvis-venv`, `/home/alex/jarvis-data`,
`/home/alex/llama.cpp`, consistent with what the task description names
as the "documented Sollpfade — but verify before use." The three old unit
files at the repo root (`jarvis.service`, `llama-server.service`) instead
hard-code `/home/user/...` and `/mnt/models/...`, which don't match
`config.yaml` at all — that mismatch is exactly the bug this pass fixes.

**None of this replaces actually checking Sleepy.** `config.yaml` being
correct doesn't prove `llama-server`, the venv, or the model file exist at
those exact paths — only that the Python app is configured to expect them
there.

## Verification checklist (run on Sleepy, in this order)

```bash
whoami                                   # expect: alex
realpath /home/alex/jarvis               # expect: repo checkout root
realpath /home/alex/jarvis-venv          # expect: exists, has python3
realpath /home/alex/jarvis-data          # expect: exists
realpath /home/alex/llama.cpp/build/bin/llama-server   # expect: exists, executable
ls -la /home/alex/jarvis-data/models/llm/Qwen3.5-35B-A3B-abliterated-Q3_K_M.gguf
ls -la /home/alex/jarvis-data/models/qwen3-asr/sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25
ls -la /home/alex/jarvis-data/models/piper/jarvis-de-high/model.onnx
/home/alex/jarvis-venv/bin/python3 -c "import sounddevice, chatterbox.mtl_tts"  # confirms venv has what jarvis_continuous.py and chatterbox_server.py need — SEE NOTE BELOW
```

**Note on the Chatterbox venv**: `chatterbox.service` currently points
`ExecStart` at `/home/alex/jarvis-venv/bin/python3`. This was **not**
verified — Chatterbox's GPU/torch/chatterbox-tts dependency set may
conflict with the main venv's pinned versions and need its own separate
venv. If the `import chatterbox.mtl_tts` check above fails in
`jarvis-venv`, find (or create) the correct venv and change
`chatterbox.service`'s `ExecStart` accordingly — don't just widen
`jarvis-venv`'s pins to make it fit without checking why they were pinned
that way.

## Install strategy: MIXED — jarvis.service is a user unit, llama-server/chatterbox are system units

**Session #6 got this wrong** — it recommended system-level for
everything based on architectural reasoning alone ("always-on services
should start before login"), without first checking whether an
established, *working* convention already existed in this repo. It did:
`start.sh`, `stop.sh`, `restart.sh`, `status.sh`, `killswitch.sh`,
`jarvis_aliases.sh` (all at the repo root) call `systemctl --user ...
jarvis.service` and `journalctl --user -u jarvis.service` throughout —
including a real emergency kill switch with a working `killjarvis`
alias — and `core/health_check.py` / `core/tools/developer_tools.py`
both query `jarvis` the same way. That's not a stale leftover to
reconcile away; it's the real, in-use control plane for this service,
confirmed by `core/tools/developer_tools.py`'s own
`_devtools_service_status()`, which lists `jarvis`/`jarvis-web` under
"User services" unconditionally. **`jarvis.service` is a user unit.
This is settled by evidence, not a preference.**

This also converges with the Windows-Audio target named in later
sessions' tasks: a system-level unit starting before any login has no
path to Windows Audio / WSLg's audio forwarding, which is tied to an
active logged-in session — only a user unit (running as that session)
can reach it. So the correction isn't just "match existing scripts," it
also happens to be the architecturally right call once real audio
output is in scope.

`llama-server.service` and `chatterbox.service` stay **system units**
— headless GPU HTTP servers with no session/audio dependency of their
own (only `jarvis.service` itself needs to reach the audio session).
This part is a reasoned best guess, not confirmed the way
`jarvis.service` is: `developer_tools.py`'s own status check hedges on
`llama-server` (`systemctl --user is-active` first, falls back to plain
`systemctl` on failure) — the codebase itself isn't fully sure either.
**NEEDS HW VERIFY**: confirm on Sleepy which scope `llama-server`/
`chatterbox` actually run under today, if anything already manages them,
before installing `systemd/llama-server.service`/`chatterbox.service`
as written.

`systemd/jarvis.service` was rewritten this session to be a proper user
unit (`%h`-relative paths, no `User=` line — user units already run as
the invoking user). `llama-server.service`/`chatterbox.service` are
unchanged from session #6 (already system units).

**Cross-manager caveat**: `jarvis.service`'s `After=`/`Wants=` naming
the two system units are not reliably enforced by systemd across the
user/system manager boundary — `systemctl --user start jarvis.service`
will NOT reliably also start them. Start/enable them independently (the
updated `start.sh` below does this, with a passwordless-sudo check
rather than hanging on a password prompt).

### Install

```bash
# System units (llama-server, chatterbox) — need root
sudo cp systemd/llama-server.service systemd/chatterbox.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now llama-server.service
sudo systemctl enable --now chatterbox.service

# User unit (jarvis) — runs as the invoking user, no sudo
mkdir -p ~/.config/systemd/user
cp systemd/jarvis.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now jarvis.service
loginctl enable-linger "$USER"   # so jarvis.service can start before login too

# Or, once installed once: ./start.sh does all of the above each time
```

### Verify

```bash
systemctl status --no-pager llama-server.service chatterbox.service
journalctl -u llama-server.service --no-pager -n 50
journalctl -u chatterbox.service --no-pager -n 50

systemctl --user status --no-pager jarvis.service
journalctl --user -u jarvis.service --no-pager -n 50

# Or: ./status.sh (updated this session to check all three)
```

Before installing, confirm nothing is already running under the other
scope for the same service name
(`systemctl list-units | grep -i jarvis` AND
`systemctl --user list-units | grep -i jarvis`) — two instances fighting
over the mic, port 8080, or port 8765 is exactly the failure mode this
mixed strategy has to avoid getting backwards.

## What's deliberately NOT included

- **small-llm.service**: `config.yaml`'s `llm.small.endpoint` points at
  `127.0.0.1:8081`, but nothing in this repo says what process/binary/model
  serves that port — the task explicitly said only add this "wenn der
  reale Small-LLM-Pfad zweifelsfrei bestimmt werden kann," and it
  couldn't be, without Sleepy access. Whatever currently serves 8081 on
  Sleepy needs its own unit written the same way once that's known.
- **Running `systemctl`/`journalctl` and reporting results**: not done,
  for the reason stated at the top of this file. Do not mark this
  workstream's systemd items as verified until someone actually runs the
  checklist and install steps above and records the real output.
- **jarvis-web.service**: `core/tools/developer_tools.py`'s service
  listing references a `jarvis-web` unit, but no `jarvis-web.service`
  file exists anywhere in this repo (checked this session). Either it
  was never written, or it's managed some other way on Sleepy — not
  investigated further; flagged rather than guessed at.

## Control-plane scripts (repo root) — updated session #7

`start.sh`/`stop.sh`/`restart.sh`/`status.sh`/`killswitch.sh`/
`jarvis_aliases.sh` previously only knew about `jarvis.service` —
`llama-server.service`/`chatterbox.service` (added session #5/#6) were
never wired in, a real gap beyond just documentation:
- `start.sh` now also enables+starts the two system units first
  (sudo, skipped with a clear message if no passwordless sudo).
- `status.sh` now reports all three services, not just `jarvis`.
- `killswitch.sh` — an *emergency, stop everything* switch that left
  the local LLM/TTS GPU servers running was a real gap in what it
  promises — now also stops+disables both system units and adds
  `llama-server`/`chatterbox_server.py` to its direct `pkill` list as a
  second line of defense if systemd itself couldn't reach them (no
  sudo, or a process started outside systemd).
- `stop.sh`/`restart.sh` deliberately still only touch `jarvis.service`
  (a graceful pause/restart of JARVIS shouldn't tear down slow-to-reload
  GPU models) — this is a documented choice in each script now, not
  silent scope-narrowing.
- `jarvis_aliases.sh` gained `llamalogs`/`chatterboxlogs`/
  `restartllama`/`restartchatterbox` for bouncing a model service
  directly without going through `start.sh`'s full sequence.

## Update 2026-09-25: Primary/Expert-Units (User-Scope)

**Der Abschnitt "Install strategy: MIXED" oben ist für die LLM-Server veraltet.** Er beschreibt `llama-server.service` als System-Unit; der neue Handover (`core/model_handover`, siehe `docs/RUNTIME_SUPERVISOR.md`) arbeitet ausschließlich mit `systemctl --user`. System-Scope-`sudo` ist nur noch im stalen `core/gpu_swap.py` (FLUX) vorhanden.

Neue Vorlagen im Repo (beide **User-Scope**, nicht installiert, nicht auf Hardware verifiziert):

- `systemd/llama-server-primary.service`: Gemma 4 12B mit mmproj, Port 8080 (`llm.primary`).
- `systemd/llama-server-expert.service`: Qwen3.5-35B-A3B, Port 8082 (`llm.expert`), GPU-exklusiv.

**NEEDS HW VERIFY:** Gemma-/mmproj-Dateinamen und Port 8082 sind Platzhalter. Der Nutzer muss die Units selbst nach `~/.config/systemd/user/` installieren und `daemon-reload` ausführen. Die tatsächlich laufende Unit liegt außerhalb des Repos; die Vorlagen ersetzen sie nicht automatisch. Vor der Installation prüfen, dass keine alte System-Unit `llama-server.service` denselben Port 8080 belegt (Doppelbelegung).

## Update 2026-09-29: jarvis-desktop-api.service (User-Scope)

`jarvis-desktop-api.service` runs `jarvis_web.py --desktop-mode`, the read-only API of the native WinUI app, on
`127.0.0.1:8092`. It is a user unit like `jarvis.service` and uses the same checkout path and venv. `start.sh`
links it from this checkout (never replaces a foreign unit), starts it after the voice listener is ready and waits
up to 90 s for `scripts/runtime_status.py --desktop-api-ready`; a failure there makes the start DEGRADED and does
not roll back the voice backend. `stop.sh` stops it before `jarvis.service` (and only if it is this checkout's
unit), so the statement above that stop/restart touch only `jarvis.service` no longer holds. It is not enabled
for boot; it follows the runtime lifecycle. Not verified on Sleepy: run `systemctl --user status
jarvis-desktop-api.service` and `curl -s http://127.0.0.1:8092/api/stats` after `start.sh`.
