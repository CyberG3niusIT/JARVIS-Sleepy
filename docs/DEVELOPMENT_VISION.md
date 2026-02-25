# JARVIS Development Vision — LLM-Centric Architecture

**Created:** February 18, 2026
**Updated:** February 25, 2026
**Context:** Qwen3.5-35B-A3B running in production (native multimodal, MoE architecture, proven tool calling)

---

## Background

JARVIS was built with hard-coded skill handlers because early development focused on reliability over LLM flexibility. The skill system (semantic routing, keyword matching, priority layers) works well but requires significant maintenance — greedy keyword bugs, threshold tuning, priority conflicts, and per-skill handler code.

With Qwen3.5's native multimodal capabilities, proven tool calling (web research via `stream_with_tools()`), and the MoE architecture delivering strong reasoning at only 3B active parameters, the project can begin shifting toward an LLM-centric approach where the model acts as an **agent with tools** rather than a dispatcher to pre-built handlers.

**What's changed since the original vision (Feb 18):**
- Qwen3.5-35B-A3B is live — not the speculated 9B dense model, but a 35B MoE (256 experts, 8+1 active, 3B active params)
- Native multimodal confirmed — early-fusion architecture with text + image + video baked into the base model (no separate VL release)
- Tool calling proven — `web_search` via `stream_with_tools()` works reliably with prescriptive prompts
- Vision unblocked — mmproj-F16.gguf (~900MB) available, llama.cpp support merged Feb 10 (PR #19468)
- VRAM is the constraint — Q3_K_M uses ~19.5/20.0 GB, leaving ~1.8GB free at ctx-size 7168

---

## Core Principle

**Skills become tools, not destinations.**

The current skill handlers aren't wasted work — they're the tool execution layer an agentic LLM needs. The migration path is:

1. Convert skill handlers into **tool definitions** (function signatures + descriptions)
2. Let the LLM decide which tools to call and how to compose them
3. Keep the skill infrastructure as the **execution layer** the LLM calls into

The web research implementation (Qwen3.5 + DuckDuckGo tool calling via `stream_with_tools()`) already proves this pattern works in JARVIS.

---

## Routing Simplification

### Current Architecture (12-layer priority chain)
```
P1:      Rundown acceptance/deferral
P1.5:    Task planner control (active/pending plans)
P2:      Reminder acknowledgment
P2.5:    Memory forget confirmation
P2.7:    Dismissal detection (in conversation)
P2.8:    Bare acknowledgment filter (in conversation)
P3:      Memory operations (forget, recall, transparency)
P3.5:    Research follow-up (in conversation)
P3.7:    News article pull-up
Pre-P4:  Multi-step task planning (compound detection)
P4:      Skill routing (4-layer hybrid: exact → fuzzy → keyword → semantic)
P5:      News continuation
Fallback: LLM streaming with tools (Qwen3.5 → quality gate → Claude API)
```

### Target Architecture
```
Layer 1: Wake word detection
Layer 2: Hard-coded fast-paths (time, dismissals, greetings — latency-critical)
Layer 3: LLM agent with tools (everything else)
```

The semantic matcher, keyword routing, generic keyword blocklist, priority levels, and threshold tuning all exist because routing needed to be cheap and fast without hitting the LLM. If the LLM is fast and reliable enough at tool selection, the P4 skill routing layer (4 sub-layers, ~50+ patterns, ~109 semantic intent registrations) becomes unnecessary. The stateful priorities (P1-P3.7, Pre-P4) would remain — they handle state machines (reminders, memory, task planner) that require deterministic behavior.

---

## Migration Plan — Incremental, Skill by Skill

### Phase 1: Low-Stakes Skills (First Candidates)

**System Info + Filesystem**
- Low stakes if the LLM picks a slightly wrong command
- Benefits from flexible query interpretation ("how much disk space do I have" vs "show me storage" vs "am I running low on space")
- Implementation: `run_command` tool with a whitelist of safe commands
- The LLM decides whether to run `free -h`, `lscpu`, `df -h`, `du`, `find`, etc.

**Time/Date**
- Trivial tool call, no need for a dedicated skill
- Could be a simple function tool that returns current time/date info
- LLM handles formatting naturally ("quarter past three" vs "3:15 PM")

### Phase 2: API-Backed Skills

**Weather**
- LLM calls weather API tool, formats response naturally
- Eliminates hard-coded response templates
- Can handle complex queries ("do I need an umbrella tomorrow?" "is it colder than yesterday?")

### Phase 3: Vision-Enabled (Unblocked — Native in Qwen3.5)

Vision is NOT a future dependency — it's available now. Qwen3.5's early-fusion multimodal architecture means the model already running in production can process images when the mmproj file is loaded.

**Web Navigation with Vision**
- Currently uses per-site CSS selectors and structured scraping
- With mmproj loaded: screenshot the page, let the LLM see it, decide what to click
- Replaces brittle CSS selectors with visual understanding
- VRAM cost: +900MB when active (requires display offload or dynamic loading)

**Screen Reading / OCR**
- "What does this say?" → screenshot active window → LLM describes content
- "Read this chart" → screenshot → structured data extraction
- Tesseract as fast CPU fallback for simple text extraction (~1-3s, zero VRAM)
- Full VLM path via mmproj for complex images (~3-6s with model cached)

**IoT Camera Integration (Future)**
- Security camera feeds processed by the same model handling conversation
- "Is anyone at the front door?" — LLM sees the camera frame directly
- No separate vision pipeline needed — same mmproj handles all image tasks

### Phase 4: Routing Layer Evaluation

After Phases 1-3 are stable, evaluate:
- Can the semantic matcher be removed entirely?
- Can keyword routing be reduced to just the fast-paths?
- What's the latency impact of routing everything through the LLM?

---

## What Must Stay Hard-Coded

### Non-Negotiable — Keep as Structured Code

| Component | Reason |
|-----------|--------|
| **Audio pipeline** (STT, TTS, VAD, wake word) | Real-time audio processing, not an LLM problem |
| **Reminder state machine** | Scheduling, nag behavior, Google Calendar sync — too stateful, reliability-critical. A missed reminder is worse than awkward phrasing |
| **News RSS polling** | Background daemon behavior, not request-response |
| **Conversation memory / context window** | Persistence and retrieval layers that *feed* the LLM |
| **Speaker identification** | Real-time d-vector matching during audio processing |
| **Streaming TTS pipeline** | Gapless playback, aplay management, chunking — all latency-critical |

### Keep as Fast-Paths

| Query Type | Reason |
|------------|--------|
| **Time queries** | ~50ms hard-coded vs ~1-2s through LLM |
| **Dismissals** ("no thanks", "that's all") | Must be instant, no inference needed |
| **Minimal greetings** | "Good morning sir" shouldn't require LLM inference |

---

## Tradeoffs to Monitor

### What We Gain
- Dramatically less routing code to maintain
- No more "keyword X is too greedy" bugs
- Natural handling of ambiguous queries
- Vision capabilities without a separate pipeline
- Composable tool use (LLM chains multiple tools for complex queries)

### What We Risk
- **Latency** — every query hits LLM inference instead of fast keyword match
- **Reliability** — hard-coded handlers are deterministic; LLM tool selection can be wrong (e.g., "can you help me" returning a Wikipedia article about a 1985 song)
- **Debuggability** — skill handler bugs show exact line numbers; LLM mis-routing requires reading inference logs
- **Resource usage** — more GPU inference cycles per interaction

### Mitigation Strategies
- **Prescriptive prompts** — explicit rules for tool use, not vague guidance (proven with web research via `stream_with_tools()`)
- **Fast-paths bypass LLM** — keep latency-critical responses hard-coded
- **Tool whitelisting** — LLM can only call explicitly defined tools, not arbitrary code
- **Fallback to current system** — if LLM tool selection fails, fall back to semantic/keyword routing
- **Incremental migration** — one skill at a time, validate before moving to the next

---

## Dual-GPU Strategy — RX 6600 Analysis

Adding a second GPU changes the VRAM calculus for this entire migration. This section analyzes the RX 6600 (8GB, RDNA 2, $180-220 used) across three potential use cases, from lowest to highest risk.

### Current VRAM Budget (Single GPU)

| Component | Typical VRAM | Notes |
|-----------|-------------|-------|
| Qwen3.5-35B-A3B Q3_K_M weights | ~17.5 GB | 16GB on disk + compute buffers |
| KV cache (ctx-size 7168) | ~5.0 GB | Pre-allocated by llama.cpp |
| CTranslate2 Whisper (transient) | ~0.4 GB | Loaded during transcription only |
| Sentence Transformer | ~0.15 GB | Semantic matching (in-memory) |
| Kokoro TTS (when active) | ~0.2 GB | 82M params, CPU primary but some GPU |
| System overhead | ~0.5 GB | Allocators, buffers, Python |
| **GNOME compositor** | **~0.5-1.0 GB** | **Display rendering on same GPU** |
| **Total used** | **~19.5 GB** | **of 20.0 GB** |
| **Free** | **~1.8 GB** | Measured after ctx-size reduction (session 63) |

**The problem:** The GNOME compositor shares the GPU with LLM inference. Under peak load (Feb 24), compositor starvation caused `Failed to pin framebuffer with error -12` (ENOMEM) and crashed the desktop. The ctx-size reduction from 8192→7168 freed 1.2 GB as a band-aid, but the fundamental contention remains.

### RX 6600 Specs

| Spec | Value |
|------|-------|
| Architecture | RDNA 2 (Navi 23, gfx1032) |
| VRAM | 8 GB GDDR6, 128-bit bus |
| Memory Bandwidth | 224 GB/s |
| Compute Units | 28 (1,792 stream processors) |
| TDP | 132W |
| ROCm Status | **Unofficial** — requires `HSA_OVERRIDE_GFX_VERSION=10.3.0` |
| Used Market Price | $180-220 |

**Hardware compatibility:** X570 Pro4 motherboard has a second PCIe x16 slot (x4 electrical). 850W PSU confirmed adequate for dual GPU (~435W peak realistic draw).

### Use Case A: Display Offload (HIGH VALUE, LOW RISK)

Move the GNOME compositor to the RX 6600. The RX 7900 XT becomes a dedicated compute GPU.

**What it gives you:**
- Frees ~500MB-1GB of VRAM on the primary GPU (compositor overhead eliminated)
- Eliminates ENOMEM crash risk entirely — compositor can never starve the LLM
- Total usable VRAM for inference grows from ~19.0 GB to ~19.5-20.0 GB
- Enough headroom to load mmproj (~900MB) for vision without exceeding budget
- Potentially enough to try Q4_K_S quantization (~19GB) for better model quality

**Implementation:** Configure GNOME/Mutter to render on the secondary GPU via display output routing. ROCm is NOT required for this — standard Mesa/AMDGPU kernel driver suffices.

**Risk:** Near-zero. Display offload is a standard multi-GPU configuration. No ROCm compatibility concerns.

### Use Case B: Dedicated Image Generation (MEDIUM VALUE, LOW-MEDIUM RISK)

Run image generation models on the RX 6600 independently from the primary GPU.

**What fits in 8GB:**
- SDXL Lightning (~7GB) — 4-step generation, ~4-8s per image
- Stable Diffusion 1.5 (~4GB) — older but fast
- FLUX.1-schnell does NOT fit (13-16GB FP8)

**Implementation:** ROCm required. RX 6600 needs `HSA_OVERRIDE_GFX_VERSION=10.3.0` (unofficial but widely confirmed working with llama.cpp and Ollama). Per-GPU HSA overrides supported since ROCm 6.2:
```bash
export HSA_OVERRIDE_GFX_VERSION_0=11.0.0  # GPU 0: RX 7900 XT (gfx1100)
export HSA_OVERRIDE_GFX_VERSION_1=10.3.0  # GPU 1: RX 6600 (gfx1032 → gfx1030)
```

**Risk:** Low-medium. The override is well-tested by the community, but some users report instability after ROCm upgrades. Image generation is a non-critical feature — failures are annoying, not catastrophic.

### Use Case C: Model Splitting Across GPUs (NOT RECOMMENDED)

Split Qwen3.5 transformer layers across both GPUs to fit a larger quantization (Q4_K_M or Q5_K_M).

**Why it's tempting:** Q4_K_M or Q5_K_M would significantly improve model quality. The combined 28GB (20+8) could theoretically fit Q5_K_M.

**Why it doesn't work:**
- **Multiple open segfault bugs** in llama.cpp with mixed RDNA3 + RDNA2 architectures:
  - [Issue #4030](https://github.com/ggml-org/llama.cpp/issues/4030): RX 7900 XTX + RX 6900 XT (gfx1100 + gfx1030) → segfault immediately after model load. Open, 23 comments, no fix.
  - [Issue #19518](https://github.com/ggml-org/llama.cpp/issues/19518): Mixed GPU crash specifically with Qwen models — `"no kernel image is available for execution on the device"` during matrix multiplication.
  - [Issue #17583](https://github.com/ggml-org/llama.cpp/issues/17583): Multi-GPU segfaults regardless of model size.
- **Layer split is serialized** — only one GPU computes at a time (`--split-mode layer`). Performance is often worse than single GPU for smaller models due to inter-GPU communication overhead.
- **Row split (`--split-mode row`) is unstable** on ROCm — reports of garbage output.
- The `ik_llama.cpp` fork achieved 3-4x multi-GPU improvement, but only for CUDA — not yet available for ROCm.

**Recommendation:** Do not pursue model splitting with mixed architectures until llama.cpp resolves these issues. Monitor the open bugs.

### Use Case Summary

| Use Case | Value | Risk | ROCm Required? | Recommendation |
|----------|-------|------|-----------------|----------------|
| A: Display offload | High | Near-zero | No (Mesa only) | **Do this first** |
| B: Image generation | Medium | Low-medium | Yes (unofficial) | Viable after A is stable |
| C: Model splitting | High (if it worked) | Very high | Yes (buggy) | **Do not pursue** |

### Alternative: RX 7600 Instead of RX 6600

| Factor | RX 6600 | RX 7600 |
|--------|---------|---------|
| Architecture | RDNA 2 (gfx1032) | RDNA 3 (gfx1102) |
| VRAM | 8 GB | 8 GB |
| ROCm | Unofficial (override needed) | **Officially supported** |
| Model splitting risk | Very high (mixed arch) | Lower (same arch family as 7900 XT) |
| Used price | $180-220 | $200-250 |

The RX 7600 costs $20-50 more but eliminates the ROCm override requirement and reduces mixed-architecture risk if model splitting becomes viable in future llama.cpp releases. For Use Case A (display offload), both cards are equivalent since ROCm isn't needed.

### VRAM Scenarios With Second GPU

| Scenario | Primary GPU (RX 7900 XT) | Secondary GPU | Status |
|----------|--------------------------|---------------|--------|
| Current (single GPU) | 19.5 / 20.0 GB (~1.8 GB free) | N/A | Stable but tight |
| + display offload | ~19.0 / 20.0 GB (~2.3-2.8 GB free) | Compositor only | Comfortable |
| + display offload + mmproj (vision) | ~19.9 / 20.0 GB (~1.4-1.9 GB free) | Compositor | Workable |
| + display offload + SDXL on secondary | ~19.0 / 20.0 GB | ~7 / 8 GB | Both comfortable |
| + display offload + mmproj + SDXL | ~19.9 / 20.0 GB | ~7 / 8 GB | Tight primary, good secondary |
| Model split (Q5_K_M across both) | — | — | Blocked by mixed-GPU bugs |

---

## Qwen3.5-35B-A3B — Confirmed Capabilities

### What's Running Now

| Feature | Status | Details |
|---------|--------|---------|
| **Native multimodal** | Confirmed | Early-fusion architecture — text + image + video trained jointly from pretraining. Outperforms Qwen3-VL on visual reasoning benchmarks |
| **MoE architecture** | Running | 35B total params, 256 experts, 8+1 active per token, 3B active params |
| **Tool calling** | Proven | `web_search` via `stream_with_tools()` with prescriptive prompts and `tool_choice=auto` |
| **Vision support** | Available | mmproj-F16.gguf (~900MB) from unsloth. llama.cpp support merged Feb 10 (PR #19468). Not yet activated |
| **Quantization** | Q3_K_M | ~16GB on disk, ~19.5GB VRAM with KV cache at ctx-size 7168 |
| **Context window** | 7168 tokens | VRAM-constrained (reduced from 8192 after GNOME compositor crash). Tool schemas consume ~100-200 tokens each |

### Vision Details

Qwen3.5 uses the same ViT architecture as Qwen3-VL but integrated via early fusion — no separate VL model release planned. The mmproj (multimodal projector) bridges the vision encoder to the language model:

| mmproj Variant | Size | Source |
|---|---|---|
| mmproj-F16.gguf | ~900 MB | unsloth/Qwen3.5-35B-A3B-GGUF |
| mmproj-BF16.gguf | ~903 MB | unsloth/Qwen3.5-35B-A3B-GGUF |
| mmproj-F32.gguf | ~1.79 GB | unsloth/Qwen3.5-35B-A3B-GGUF |

**Usage:** `llama-server -m Qwen3.5-35B-A3B-Q3_K_M.gguf --mmproj mmproj-F16.gguf`

**VRAM impact:** +900MB when loaded. At current utilization (~19.5/20.0 GB), this exceeds budget without either dynamic loading or display offload to a second GPU (see Dual-GPU Strategy above).

---

## Success Criteria

Before declaring a skill "migrated" to LLM-driven:

1. **Accuracy**: LLM tool selection matches hard-coded routing for 95%+ of test queries
2. **Latency**: Response time stays under 3 seconds for common queries
3. **Reliability**: No regressions in edge cases (test with the same voice test methodology used for web research — systematic multi-run validation)
4. **Graceful failure**: When the LLM picks the wrong tool, the result is unhelpful but not harmful

---

## Key Lessons From Web Research Implementation

These lessons (Feb 18, sessions 2-14) directly apply to future LLM-driven skills:

1. **Prescriptive > permissive** — "MUST search for X / ONLY skip for Y" works; "when in doubt, search" gets ignored
2. **Context history poisons tool calling** — if conversation history shows a pattern, Qwen copies it instead of following instructions
3. **Start with `tool_choice=auto`** — let the LLM decide, but make the decision rules crystal clear in the prompt
4. **Test systematically** — 15 runs x N queries, not "try it once and ship it"
5. **Small LLMs can't reason about when to use tools for familiar topics** — they'll confidently answer from stale training data. Prompt design must account for this.

---

## Timeline

No fixed dates — this is a directional vision, not a sprint plan. All phases are now **unblocked** by the Qwen3.5 capabilities.

### Without Second GPU
- **Now possible**: Phase 1 (system_info, filesystem, time as tools) + Phase 2 (weather as tool)
- **Now possible with dynamic loading**: Phase 3 (vision via mmproj) — load mmproj on-demand for image tasks, unload when done. Adds latency for model loading (~5-10s cold start) but avoids VRAM overcommit
- **Constrained**: Tool schema budget eats into ctx-size 7168. Each tool definition costs ~100-200 tokens. Adding 5-10 tools could consume 500-2000 tokens of context before the conversation starts

### With Second GPU (Display Offload)
- **Accelerates everything**: ~500MB-1GB freed on primary GPU
- **Vision becomes practical**: mmproj can stay loaded alongside Qwen3.5 with comfortable margin
- **Larger context possible**: Could increase ctx-size from 7168 → 8192+ (more room for tool schemas + conversation)
- **Image generation independent**: SDXL Lightning on secondary GPU doesn't compete with LLM inference

### Sequencing
1. **Phase 1 (low-stakes skills as tools)** — can start immediately, no hardware changes needed
2. **Second GPU acquisition** — display offload gives headroom for everything that follows
3. **Phase 2 (API skills as tools)** — straightforward once Phase 1 patterns are validated
4. **Phase 3 (vision)** — activate mmproj, add vision tools (screen reading, web nav, image understanding)
5. **Phase 4 (routing evaluation)** — after 1-3 are stable, assess what routing layers can be removed

---

*Originally discussed February 18, 2026. Updated February 25, 2026 with confirmed Qwen3.5-35B-A3B capabilities, native multimodal status, and dual-GPU strategy analysis.*
