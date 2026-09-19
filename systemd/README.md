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

## Install steps (once the checklist above is confirmed)

```bash
sudo cp systemd/llama-server.service systemd/chatterbox.service systemd/jarvis.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now llama-server.service
sudo systemctl enable --now chatterbox.service
sudo systemctl enable --now jarvis.service

systemctl status --no-pager llama-server.service chatterbox.service jarvis.service
journalctl -u llama-server.service --no-pager -n 50
journalctl -u chatterbox.service --no-pager -n 50
journalctl -u jarvis.service --no-pager -n 50
```

If `/etc/systemd/system` isn't writable in whatever session does this
install, user-level units under `~/.config/systemd/user/` (matching the
old root `jarvis.service`'s own install comment) are the fallback — but
then `EnvironmentFile=-/home/alex/jarvis/.env` and `User=alex` should be
dropped (user units already run as that user) and `loginctl enable-linger
alex` is needed for them to start before login.

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
