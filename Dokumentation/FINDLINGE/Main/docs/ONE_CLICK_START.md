# JARVIS One-Click Runtime Control

Double-click `JARVIS-Start.cmd`, `JARVIS-Stop.cmd`, or `JARVIS-Restart.cmd` in
this checkout. The `.ps1` files are the PowerShell entry points; all three use
`JARVIS.Runtime.psm1`, which invokes the existing WSL lifecycle scripts in the
fixed `Ubuntu-24.04` distribution. The `.cmd` files apply execution-policy
bypass to that PowerShell process only; no machine-wide policy is changed.

## Lifecycle ownership

- `jarvis.service` is the JARVIS backend user unit. Its process hosts the
  listener, STT, wake-word matching, router, skills/LLM calls, TTS and Windows
  audio output. The current wake-word match occurs after STT transcription;
  there is no separate acoustic wake service.
- `llama-server.service` is a shared local LLM dependency. Start reuses the
  verified active user unit or starts that same loaded unit. It is not stopped
  by normal JARVIS Stop so the model can remain warm.
- Chatterbox Multilingual V3 is the primary TTS dependency. A healthy process
  is reused only when its executable and checkout script match this runtime.
  If it is absent and no system unit is installed, Start runs the existing
  `start_chatterbox.sh` in a user-scoped transient systemd unit named
  `jarvis-chatterbox.service`. If a system unit exists, it must be a verified
  root-owned unit with the expected user and executable before it is reused.
  It never links a unit from the writable checkout into the root systemd
  search path. Normal Stop leaves Chatterbox warm; a failed Start rolls back
  a transient unit it started. Piper remains the existing TTS fallback, but
  a failed primary Chatterbox contract prevents READY.
- VVS is an external service. Start checks its configured `/health` and
  `/ready` URLs; Stop never controls it. A missing VVS config or unready API
  yields DEGRADED, so School/Mobility requests cannot be reported as ready.
- Stop controls only the verified JARVIS backend unit. It never kills a
  process based on port number. It keeps LLM and Chatterbox warm; VVS remains
  externally managed and is never stopped.

The first Start may create a user-level link for the repository's existing
JARVIS unit. It does not enable services at boot. A foreign unit, executable,
or occupied port causes ERROR without replacing or killing the process.

## Startup states

- `STARTING`: the serialized start sequence is checking dependencies and
  starting only missing, verified services.
- `READY`: the configured loopback LLM health check passes, the canonical
  Chatterbox health/config/voice check passes, required STT model files exist,
  and JARVIS logs the real continuous-listener activation marker. This confirms
  runtime and listener readiness; it does not verify Windows speaker playback
  or subjective audio quality.
- `DEGRADED`: those core runtime checks and listener activation pass, while an
  optional dependency such as VVS, the small LLM, or the Windows audio bridge
  is unavailable.
- `ERROR`: a required dependency, unit identity, port owner, or listener
  readiness check fails. The start script attempts to stop only services it
  started in that invocation.
- `STOPPED`: the verified JARVIS backend is inactive. Its model dependencies
  remain available.

The controller reads the existing JARVIS systemd journal internally only to
find the listener marker; it does not print journal contents or user speech.

## Verification boundaries

Run deterministic controller tests with:

```powershell
pwsh -NoProfile -File tests/powershell/Test-JarvisRuntime.ps1
```

Run Python unit tests from the WSL project environment as documented in the
repository. These tests do not emulate microphone capture, Windows playback,
or subjective audio quality. A real listening check must be done locally on
Sleepy after signing in and confirming the microphone/audio session is ready.
