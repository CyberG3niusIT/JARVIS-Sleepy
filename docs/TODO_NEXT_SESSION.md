# TODO — Next Session

**Updated:** February 22, 2026

---

## Tier 1: High ROI — Do Now/Soon

### 1. Inject User Facts into Web Research
**Priority:** HIGH
**Concept:** JARVIS reasons about what it knows about the user (location, preferences) during `stream_with_tools()`.
**Risk:** History poisoning — needs careful scoping.

---

## Tier 2: Medium ROI — Next Wave

### 2. Email Skill (Gmail Integration)
**Priority:** MEDIUM
**Concept:** Voice-composed email via Gmail API + OAuth (same pattern as Calendar).
**Design:** `.archive/docs/MASTER_DESIGN.md` has contact DB schema and feature list.

### 3. Google Keep Integration
**Priority:** MEDIUM
**Concept:** "Add milk to the grocery list." Shared access with secondary user.

### 4. Dual-Model Voice Recognition (Speaker Routing)
**Priority:** MEDIUM (waiting for secondary user enrollment)
**Concept:** Speaker-ID d-vector comparison (~5ms) routes to primary user's fine-tuned Whisper vs stock whisper-base. Two CTranslate2 models loaded simultaneously (~300MB total).
**Design:** `memory/plan_erica_voice_windows_port.md`
**Timing:** After secondary user can do 10-min enrollment session. Half-day implementation.

### 5. Audio Recording Skill
**Priority:** MEDIUM
**Location:** `skills/personal/audio_recording/`
**Concept:** Voice-triggered recording with natural playback queries.
- "Record audio" -> tone -> capture -> "Stop recording" -> saved as WAV
- "Play the recording from yesterday" -> date-based lookup + playback
- 6 semantic intents (start, stop, play, query, list, export)

---

## Tier 3: Lower Effort — When Ready

### 6. "Onscreen Please" — Retroactive Visual Display
**Priority:** MEDIUM
**Concept:** Buffer last raw output. "Onscreen please" displays it retroactively.

### 7. Music Control (Apple Music)
**Priority:** MEDIUM
**Concept:** Playlist learning, volume via PulseAudio. Apple Music web interface is finicky.
**Design:** `.archive/docs/MASTER_DESIGN.md` has playlist DB schema.

### 8. LLM-Centric Architecture Migration
**Priority:** MEDIUM (wait for Qwen 3.5 release)
**Design:** `docs/DEVELOPMENT_VISION.md`
**Concept:** Skills become tools, not destinations. Incremental migration.

### 9. Docker Container (Web UI Mode)
**Priority:** MEDIUM
**Concept:** Lowest-barrier community deployment. Web UI only (no mic). Proves the concept for community adoption.
**Effort:** 3-5 days
**Design:** `memory/plan_erica_voice_windows_port.md`

---

## Tier 4: Backlog

### Skill Editing System
**Design:** `docs/SKILL_EDITING_SYSTEM.md`
**Concept:** "Edit the weather skill" -> LLM code gen -> review -> apply with backup.
**Note:** VS Code + Claude Code is faster for editing skills in practice.

### STT Worker Process
**Design:** `docs/STT_WORKER_PROCESS.md`
**Concept:** GPU isolation via separate process. Only needed if GPU conflicts resurface.

### Automated Skill Generation
**Concept:** Q&A -> build -> test -> review -> deploy. Depends on Skill Editing.

### Windows Native Port
**Concept:** Full JARVIS on Windows. ~2-3 weeks effort. Biggest audience for community adoption.
**Design:** `memory/plan_erica_voice_windows_port.md`

### Mobile Access
**Concept:** Remote command via phone. Different tech stack entirely.

---

## Tier 5: Aspirational — Someday/Maybe

- **Malware Analysis Framework** — QEMU sandbox, VirusTotal/Any.run API, CISA-format reports. Build when a specific engagement needs it.
- **Video / Face Recognition** — webcam -> people/pets/objects. Hardware-dependent. Qwen3-VL vision encoder ready for text-only; image processing is future.
- **Tor / Dark Web Research** — Brave Tor mode, safety protocols. Specialized professional use.
- **Emotional context awareness** — laugh/frustration/distress detection. Research-level ML.
- **Voice cloning (Paul Bettany)** — tested Coqui, rejected. Revisit when open-source matures.
- **Proactive AI** — suggest actions based on patterns. Needs significant usage data first.
- **Self-modification** — JARVIS proposes own improvements. Far future.
- **Home automation** — IoT integration. Hardware-dependent.

---

## Active Bugs

None!

---

## Pending Live Tests

- **CONSOLE TEST: Document generation** — Implemented (Feb 22). Test in console mode:
  1. Simple (no research): "Create a presentation about the benefits of remote work"
  2. With research: "Look up the top 5 LLMs for home use and create a 7 slide PowerPoint called llm_review.pptx"
  3. Full multi-step: "Look up the current top 5 LLMs in home use today, compare the pros and cons of each, and prepare a 7 slide PowerPoint that outlines what you've found. Name it llm_review.pptx and leave it in the share for me"
  4. DOCX: "Write a report about cybersecurity trends in 2026"
  5. PDF: "Create a PDF comparing Python and Rust"
  6. Verify: open generated files in LibreOffice, check layout/images/content quality
- **VOICE TEST: Smart ack suppression** — Implemented (Feb 22). Conversational queries should skip ack, research/complex queries should still get ack.
- **Batch extraction (Phase 4)** — needs 25+ messages in one session to trigger
- **Qwen3-VL vision features** — mmproj encoder downloaded, not yet integrated. Future: image understanding via `--mmproj` flag.

---

## Completed (Feb 10-22)

*Brief summary. Full details in git history and `docs/PRIORITY_ROADMAP.md`.*

| Feature | Date |
|---------|------|
| Qwen3-VL-8B Model Upgrade (ROCm rebuild, self-quantized Q5_K_M) | Feb 22 |
| Document Generation (PPTX/DOCX/PDF with web research + Pexels) | Feb 22 |
| Smart Ack Suppression | Feb 22 |
| Edge Case Phase 2 (132 tests total) | Feb 22 |
| Automated Test Suite (122 tests) | Feb 21 |
| Conversational Flow Refactor (4 phases) | Feb 21 |
| Whisper v2 Fine-Tuning (198 phrases, 94.4%) | Feb 21 |
| Web Chat UI (5 phases) | Feb 20 |
| File Editor Skill | Feb 20 |
| Ambient Wake Word Filter | Feb 20 |
| Edge Case Testing Phase 1 | Feb 20 |
| Console Web Research + Prompt v2 | Feb 19 |
| Document Ingestion (3 phases) | Feb 19 |
| GNOME Desktop Integration (5 phases) | Feb 19 |
| Web Research (5 phases) | Feb 18 |
| GitHub Publishing System | Feb 18 |
| Gapless TTS Streaming | Feb 17 |
| Conversational Memory (6 phases) | Feb 17 |
| Context Window (4 phases) | Feb 17 |
| User Profile System (5 phases) | Feb 16 |
| Kokoro TTS Integration | Feb 16 |
| Latency Refactor (4 phases) | Feb 16 |
| Developer Tools (13 intents) | Feb 15 |
| News Headlines System | Feb 14 |
| Reminder System + Calendar | Feb 14 |

---

**Created:** Feb 10, 2026
