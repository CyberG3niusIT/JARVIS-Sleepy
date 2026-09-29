# JARVIS Integration Handoff

Date: 2026-09-29

This document defines the current GitHub handoff baseline for the next integration pass. It is an engineering instruction, not a claim that the system is production-ready.

## 1. Source of truth

Use this order whenever information conflicts:

1. Current repository contents on the referenced GitHub branches
2. Current Git metadata and branch ancestry
3. Tests that you actually run
4. Repository documentation
5. This handoff document
6. Older notes, comments, or historical assumptions

Do not treat historical branch names, ports, model names, or old documentation as current unless they are verified in the repository.

## 2. GitHub baselines

Backend handoff branch:

`handoff/opus-backend-20260929-1821`

Backend code baseline before adding this handoff document:

`ba8585411ee7eceab1e0c3aa05b543d9b4a01827`

Native desktop UI branch:

`J.A.R.V.I.S-UI`

Verified UI head:

`aeb7ec821f9e4fd3905009acc05e7c153c4dfb91`

Mobile handoff branch:

`handoff/opus-mobile-20260929-1821`

Verified mobile head:

`ee3694df2606e7fcf8958eb5d10a223eebbf6979`

At the start of work, independently verify all branch heads and record the exact SHAs you actually use. The backend branch may be one commit newer than the code baseline above because this handoff document is committed on that branch.

Do not force-push, rewrite history, reset away work, or overwrite the existing handoff branches.

## 3. Goal

Produce one coherent repository-level integration baseline that connects the existing native Windows desktop UI to the real JARVIS backend contracts without replacing working architecture or inventing state.

The desired result is not "production-ready". The desired result is:

`READY FOR LOCAL RUNTIME VERIFICATION`

That means the repository should be internally coherent, buildable/testable to the extent possible in the cloud environment, and ready for the owner to perform the final Windows, WSL, hardware, audio, GPU, service, and end-to-end runtime checks locally.

## 4. Architecture constraints

JARVIS is local-first.

Preserve the existing modular backend and existing runtime ownership boundaries. Do not introduce a second backend, second memory implementation, second routing layer, or parallel state model just to make integration easier.

Backend remains the source of truth. UI clients must not fabricate runtime state.

Honest runtime states include concepts such as:

- STARTING
- READY
- DEGRADED
- ERROR
- STOPPED
- OFFLINE
- NOT_IMPLEMENTED
- UNAVAILABLE
- NO LIVE DATA where appropriate

Do not create fake telemetry, fake agent activity, fake model readiness, fake scheduler state, or simulated production values unless explicitly marked as test or demo data.

The production desktop client is native:

- WinUI 3
- C#
- .NET
- Windows App SDK
- XAML

Do not replace it with React, Tailwind, Vite, WebView, Node, or a browser shell.

Preserve system caption buttons. Do not add duplicate custom window controls.

The neural or brain visualization may represent observable events and real backend state only. It must never claim to expose hidden chain-of-thought.

## 5. Desktop integration contract

The backend contains a read-only desktop mode intended for the native Windows UI.

Important properties that must be preserved:

- loopback-only desktop binding
- desktop port is determined by current code/config and must be verified, not assumed
- read-only desktop process must not widen into a general administrative web process
- only explicitly allowed GET/HEAD endpoints are reachable in desktop mode
- mutation endpoints and non-allowlisted reads must fail closed
- desktop mode must not start backend-owned workers that belong to the primary runtime
- memory/context access in the second process must remain read-only
- backend-owned and unavailable states must be represented honestly

A middleware ordering defect was found during cleanup: mail authentication could return 401 before the desktop read-only boundary had a chance to reject a non-allowlisted mail endpoint with 403. The backend handoff branch includes the targeted ordering fix. Preserve the security property and its tests.

Also preserve the second-process read-only protections in:

- `core/context_window.py`
- `core/memory_manager.py`
- `jarvis_web.py`

and their focused tests.

## 6. Backend areas to inspect before integration

Inspect the current implementation, call sites, configuration, and tests before editing:

- `jarvis_web.py`
- `core/context_window.py`
- `core/memory_manager.py`
- `core/privacy_gate.py`
- `core/tool_registry.py`
- `core/live_telemetry.py`
- `core/runtime_state.py`
- `scripts/runtime_status.py`
- `core/mail_integration.py`
- `core/tools/mail_status.py`
- relevant unit, routing, integration, and PowerShell tests

Do not infer contracts from filenames alone.

## 7. Native UI areas to inspect

The UI branch is the canonical native desktop UI source.

Audit the actual UI code and adapters before modifying backend contracts. Determine:

- backend base URL resolution
- expected desktop-mode port
- authentication/token behavior
- endpoint list
- polling intervals
- readiness and degraded-state mapping
- event schema
- runtime/model status mapping
- memory summary contract
- agent and automation status contracts
- webcam or presence status contract
- lifecycle expectations
- startup/supervisor expectations
- Windows to WSL boundary assumptions

Prefer adapting the smallest side of a mismatch. Do not redesign both client and server when a targeted compatibility fix is enough.

## 8. Mail integration status and required safety review

Mail support exists in the backend handoff branch and has focused unit coverage.

Known status at handoff:

- implementation exists
- focused mail unit tests previously passed
- no real Mailcow IMAP/SMTP runtime configuration was verified
- no real send/receive runtime acceptance was performed
- the integration separates read and writer capabilities
- privacy capabilities exist for mail read/write
- automatic classification is intended to stay local-only
- uncertain send outcomes must not be automatically retried

Known issue requiring review before production exposure:

The mail dashboard has contained hardcoded account identifiers in client-side HTML. Remove hardcoded personal/account identifiers from unauthenticated static UI. Account identity should come from an appropriate authenticated/backend-owned source or be omitted.

Do not weaken authentication, privacy gates, or send safeguards to make the UI easier to wire.

## 9. Test evidence already obtained

Do not reinterpret this as a fully green suite.

During cleanup and targeted verification:

- Desktop read-only allowlist regression test passed after the middleware-order fix
- School/Mobility test file passed: 10 tests
- Live telemetry failure-response test passed after correcting a UTF-8 mojibake literal
- Focused Mailcow tests previously passed: 8 tests plus 2 subtests
- A broader unit/routing run reached 219 passing tests before stopping on the live-telemetry encoding failure
- An earlier broader run reached 308 passing tests before the desktop mail middleware-order failure

After the final focused encoding fix, the entire unit/routing suite was not rerun because the local cleanup session was time-bounded.

Therefore the correct status is:

- targeted regressions: passing where explicitly listed
- full current unit/routing suite: NOT YET VERIFIED GREEN
- integration suite: NOT YET FULLY VERIFIED
- Windows runtime: NOT VERIFIED BY THIS HANDOFF
- WSL service runtime: NOT VERIFIED BY THIS HANDOFF
- hardware/GPU/audio/voice end-to-end: NOT VERIFIED BY THIS HANDOFF

Run cloud-safe/static/unit/integration checks as appropriate, but do not claim local runtime or hardware verification.

## 10. School/Mobility unit-test isolation

A unit-test fixture instantiated the real `SkillManager`, which preloads `SentenceTransformer`. That caused the test to reach Hugging Face over the network and stall.

The test fixture now disables the embedding model through monkeypatching for this unit-test path. Preserve the production preload behavior unless you identify a real production defect. Unit tests should remain deterministic and should not require external model downloads.

## 11. Encoding discipline

A real mojibake literal was found in a backend error response:

`Live-Telemetrie nicht verfügbar`

The broken form was corrected.

Audit touched user-visible German strings for genuine source-file encoding defects, but do not mass-rewrite files merely because an old PowerShell report rendered UTF-8 incorrectly. Distinguish source corruption from report/terminal mojibake.

## 12. Mobile branch

The mobile handoff branch contains the previously local metadata/documentation changes.

Audit at least:

- `.gitignore`
- `.gitattributes`
- `README.md`

Check README links for repository portability. A workspace-relative link to documentation outside the mobile tree may not work on GitHub. Fix only if the current file actually has that problem.

Do not fold mobile implementation into desktop UI architecture.

## 13. Documentation

The repository contains backend documentation under `docs/` and other existing project documents. Update documentation when integration changes contracts, ownership, lifecycle, configuration, ports, endpoints, privacy, memory, or test status.

A separate local workspace directory named `Dokumentation` existed during cleanup but was not confirmed as present on this GitHub handoff branch. Do not claim those local files are available in the cloud.

Use the repository content you can actually verify. If important documentation is absent, record that gap rather than reconstructing facts from guesses.

## 14. Required work sequence

1. Verify repository, branches, heads, status, and ancestry.
2. Read the backend and UI implementations that define the current integration contract.
3. Build a concrete contract matrix: UI expectation vs backend implementation.
4. Reproduce each mismatch before changing code where feasible.
5. Make the smallest clean fixes.
6. Preserve privacy, read-only, auth, backend ownership, and local-first boundaries.
7. Run targeted tests for each changed contract.
8. Run the broadest practical cloud-safe regression suite.
9. Build the native UI if the environment supports it. If it does not, state that clearly.
10. Update documentation for actual changes.
11. Recheck Git status and ensure no generated/cache artifacts are committed unintentionally.
12. Produce a final handoff with exact commits and explicit unverified local-runtime items.

## 15. Git strategy for this task

Create a new integration branch from the current backend handoff branch.

Do not work directly on `main`.

Do not overwrite the existing UI or mobile handoff branches.

Avoid wholesale merging unrelated histories if a targeted integration is cleaner. Reuse existing files and architecture. If UI source must be brought into the integration branch, choose the least destructive method that preserves the canonical UI content and makes provenance clear.

Do not discard unknown changes.

Do not use force-push.

Do not rewrite history.

Do not relax or delete tests merely to obtain green CI.

## 16. Privacy and security invariants

Treat privacy as a system boundary, not a UI preference.

Review real call sites and data flow for any touched area involving:

- microphone or STT
- screen or webcam
- clipboard
- memory
- agents
- cloud providers
- remote tools
- mail
- content logging

Do not claim data is private or protected without evidence from the actual flow.

Secrets must not be committed, logged, copied into fixtures, or exposed in UI.

Agents must not gain more rights than the invoking context.

Memory learning must not become self-modification or permission escalation.

## 17. Performance and voice

Do not optimize based on guessed latency.

Do not invent benchmarks.

Do not modify voice architecture unless integration actually requires it.

Any Windows, WSL, GPU, audio, microphone, TTS, ASR, wake-word, hardware, or service claim that cannot be verified in the cloud must remain explicitly unverified and be included in the local acceptance checklist.

## 18. Agents, subagents, and skills

Use agents, subagents, and skills where they materially reduce risk or improve parallel analysis.

Good uses include:

- backend contract audit
- native UI contract audit
- privacy/security review
- test/regression review
- documentation consistency review

Keep each delegated task bounded by goal, files, rights, time, and expected output.

In the final report, list which agents/subagents/skills were used, what each did, and why it was useful.

Do not create redundant parallel implementations from delegated work.

## 19. Repository hygiene

Do not add generated caches or build outputs unless the repository intentionally tracks them.

Examples that normally remain untracked:

- `__pycache__`
- `.pytest_cache`
- `bin`
- `obj`
- `node_modules`
- temporary reports
- local secrets
- runtime databases
- model files

Do not add AI-tool attribution, generated-by signatures, co-author trailers, agent signatures, or similar branding to source, documentation, or commit messages.

Required provider/library names that are part of real configuration or dependencies may remain.

## 20. Final deliverable

The final report must include:

- exact source branches and SHAs used
- exact integration branch and final SHA
- concise contract matrix
- files changed and why
- defects reproduced
- fixes made
- tests actually run with exact results
- tests not run
- build status
- privacy/security impact
- memory impact
- runtime/service impact
- documentation changes
- remaining risks
- explicit local verification checklist
- agents/subagents/skills used and why

End with exactly one of these statuses:

`READY FOR LOCAL RUNTIME VERIFICATION`

or

`NOT READY FOR LOCAL RUNTIME VERIFICATION`

Use the ready status only if repository-level integration is coherent and all remaining blockers are genuinely local/runtime/hardware checks rather than unresolved code defects.
