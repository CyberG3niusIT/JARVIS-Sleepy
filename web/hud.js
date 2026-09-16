/**
 * JARVIS HUD — state machine, layered SVG eye animation, WebSocket client,
 * demo mode.
 *
 * Design intent (see docs/UI_INTEGRATION.md for the full writeup): every
 * state must read without the status text — color plus *how* the eye
 * moves carries the meaning. Listening pulls energy inward (particles
 * drift toward center, membrane contracts). Speaking pushes it outward
 * (membrane and energy ring expand with the audio envelope). Thinking is
 * a traveling "hot spot" chasing around the marker ring, not a faster
 * spin. Tool execution lights one directional sector, not the whole ring.
 * Wake is a single controlled shockwave, not a flash. Interrupted is a
 * sharp contraction/flinch, not a color wash. Error tints only the outer
 * accent ring and status dot — the rest of the eye stays composed.
 *
 * Every size/speed/intensity knob lives in CONFIG below. Nothing else in
 * this file should contain a magic number for "how fast" or "how strong".
 */

(function () {
  'use strict';

  // =========================================================================
  // CONFIG — single source of truth for all visual tuning parameters.
  // =========================================================================
  const CONFIG = {
    rotors: {
      // Constant regardless of state on purpose — thinking/tool_execution
      // are expressed through the marker chase / sector highlight instead
      // of spinning these faster, which would read as "loading spinner".
      aDegPerSec: 4.5,
      bDegPerSec: -6.5,
      idleSlowFactor: 0.55,       // idle breathes slower than active states
      offlineSlowFactor: 0,       // offline is fully at rest, not just slow
      errorJitterAmount: 1.4,     // deg/sec noise added only in error
    },

    ticks: { outerCount: 56, diamondCount: 4 },

    markers: {
      count: 22,
      baseRadius: 158,
      jitterRadius: 6,            // controlled asymmetry, not a perfect ring
      minSize: 1.1,
      maxSize: 2.1,
      idle: { flickerMinGapMs: 3200, flickerMaxGapMs: 7000, flickerDurationMs: 650 },
      thinking: { chaseSpeedRadPerSec: 1.35, spread: 0.16, glow: 0.75 },
      tool: { sectorHalfWidthRad: 0.55, pulseHz: 2.4 },
    },

    particles: {
      bands: [
        { count: 16, minR: 96, maxR: 140, minSize: 0.7, maxSize: 1.3, orbitDegPerSec: 0.7, drift: 0.6 },
        { count: 16, minR: 150, maxR: 200, minSize: 0.9, maxSize: 1.6, orbitDegPerSec: 1.1, drift: 1.0 },
        { count: 12, minR: 205, maxR: 258, minSize: 1.1, maxSize: 2.0, orbitDegPerSec: 1.6, drift: 1.4 },
      ],
      radialDriftPxPerSec: 9,     // listening (inward) / speaking (outward)
    },

    core: {
      baseRadius: 78,
      nucleusBaseRadius: 20,
      pulse: {
        idle:         { amplitude: 2.2, periodSec: 5.2 },
        listening:    { amplitude: 3,   periodSec: 2.0 },
        transcribing: { amplitude: 2,   periodSec: 1.5 },
        thinking:     { amplitude: 2.6, periodSec: 3.1 },
        tool:         { amplitude: 3.4, periodSec: 1.3 },
        speaking:     { amplitude: 9,   periodSec: 0.5 },  // overridden by live envelope
        error:        { amplitude: 2.4, periodSec: 2.6 },
        offline:      { amplitude: 0,   periodSec: 1 },
      },
    },

    membrane: {
      baseOffset: 34,             // px beyond core radius at rest
      segments: 72,
      idleWobble: 1.4,
      listeningPull: 9,           // inward bias while listening/transcribing
      speakingPush: 26,           // outward bias scale per envelope unit
      thinkingWobble: 3.2,
    },

    energyRing: {
      baseOffset: 60,             // px beyond core radius at rest
      segments: 84,
      speakingScale: 30,          // px per envelope unit
      listeningScale: 6,
      smoothing: 0.32,            // envelope lerp factor per frame
    },

    wake: { durationMs: 620, ringFromRadius: 78, ringToRadius: 222, coreBoost: 14 },
    interrupt: { durationMs: 420, dipAmount: 16 },

    // Tool-execution's sector currently holds a fixed random angle for
    // the whole activation (set once in stateMachine.set()); see
    // CONFIG.markers.tool above for its width/pulse rate. A slow sweep
    // instead of a fixed angle was considered and dropped as unneeded
    // for now rather than half-built — add a sectorSweepDegPerSec knob
    // here (and the tick() code to use it) if that's wanted later.

    reconnect: { initialDelayMs: 1000, maxDelayMs: 15000 },

    audio: { demoSpeechFrequencyHz: 2.1, demoNoiseAmount: 0.16 },
  };

  const AUTO_REVERT = {
    wake_detected: { toState: 'listening', afterMs: CONFIG.wake.durationMs - 80 },
    // Without this, "interrupted" shared its STATE_GROUP ('error') for
    // rotor jitter etc. indefinitely once the brief flinch finished,
    // so a real backend holding this state for more than ~half a
    // second would look identical to a genuine error except for
    // color. An interruption means the user started talking again —
    // reverting to "listening" matches that. Once the backend actually
    // emits this event (not yet wired, see docs/UI_INTEGRATION.md),
    // revisit whether it wants to own this transition instead.
    interrupted: { toState: 'listening', afterMs: CONFIG.interrupt.durationMs + 200 },
  };

  // German display labels. Deliberately plain, short words, no dashes
  // and no artificial phrasing in any user-visible string in this file.
  const STATE_LABELS = {
    offline: 'Offline',
    idle: 'Bereit',
    wake_detected: 'Aktiviert',
    listening: 'Hört zu',
    transcribing: 'Verarbeitet',
    thinking: 'Denkt nach',
    tool_execution: 'Führt aus',
    speaking: 'Spricht',
    interrupted: 'Unterbrochen',
    error: 'Fehler',
  };

  const VALID_STATES = Object.keys(STATE_LABELS);
  // transcribing gets its own group, not folded into 'thinking': it is
  // "still processing what you just said" (listening-adjacent, still
  // absorbing) rather than "reasoning about it" (thinking's traveling
  // marker chase). Sharing thinking's group left them motion-identical
  // except for an all-but-invisible scan-sweep speed difference.
  const STATE_GROUP = {
    idle: 'idle', wake_detected: 'listening', listening: 'listening',
    transcribing: 'transcribing', thinking: 'thinking', tool_execution: 'tool',
    speaking: 'speaking', interrupted: 'error', error: 'error', offline: 'offline',
  };

  // =========================================================================
  // DOM refs
  // =========================================================================
  const root = document.getElementById('hud-root');
  const rotorA = document.getElementById('ring-rotor-a');
  const rotorB = document.getElementById('ring-rotor-b');
  const ticksOuter = document.getElementById('ticks-outer');
  const primaryDiamonds = document.getElementById('primary-diamonds');
  const markersGroup = document.getElementById('markers-inner');
  const particlesFar = document.getElementById('particles-far');
  const particlesMid = document.getElementById('particles-mid');
  const particlesNear = document.getElementById('particles-near');
  const core = document.getElementById('core');
  const nucleus = document.getElementById('nucleus');
  const nucleusShimmer = document.getElementById('nucleus-shimmer');
  const membrane = document.getElementById('membrane');
  const energyWave = document.getElementById('ring-energy-wave');
  const wakeShockwave = document.getElementById('wake-shockwave');
  const interruptFlash = document.getElementById('interrupt-flash');
  const scanSweep = document.getElementById('scan-sweep');
  const toolSectorGroup = document.getElementById('ring-tool-sector');
  const toolSectorArc = document.getElementById('tool-sector-arc');
  const statusText = document.getElementById('hud-status-text');
  const clockEl = document.getElementById('hud-clock');
  const userEl = document.getElementById('hud-user');
  const modeEl = document.getElementById('hud-mode');
  const commandEl = document.getElementById('hud-command');

  const SVG_NS = 'http://www.w3.org/2000/svg';

  // Deterministic pseudo-random so layout is stable across reloads —
  // "controlled asymmetry", not a different random layout every visit.
  function mulberry32(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // =========================================================================
  // SVG construction (built once at load)
  // =========================================================================
  function buildTicks() {
    const n = CONFIG.ticks.outerCount, r1 = 236, r2 = 252;
    for (let i = 0; i < n; i++) {
      const angle = (i / n) * Math.PI * 2;
      const major = i % 7 === 0; // 7 doesn't divide 56 evenly by a "clean" fraction — avoids a too-regular look
      const line = document.createElementNS(SVG_NS, 'line');
      line.setAttribute('x1', (Math.cos(angle) * r1).toFixed(2));
      line.setAttribute('y1', (Math.sin(angle) * r1).toFixed(2));
      line.setAttribute('x2', (Math.cos(angle) * r2).toFixed(2));
      line.setAttribute('y2', (Math.sin(angle) * r2).toFixed(2));
      line.setAttribute('stroke', 'var(--ring-track-color)');
      line.setAttribute('stroke-width', major ? '1.6' : '0.8');
      ticksOuter.appendChild(line);
    }
  }

  function buildPrimaryDiamonds() {
    const n = CONFIG.ticks.diamondCount, r = 222;
    for (let i = 0; i < n; i++) {
      const angle = (i / n) * Math.PI * 2 + Math.PI / 5; // offset off-cardinal on purpose
      const x = Math.cos(angle) * r, y = Math.sin(angle) * r;
      const rect = document.createElementNS(SVG_NS, 'rect');
      rect.setAttribute('x', '-2.2'); rect.setAttribute('y', '-2.2');
      rect.setAttribute('width', '4.4'); rect.setAttribute('height', '4.4');
      rect.setAttribute('transform', `translate(${x.toFixed(2)} ${y.toFixed(2)}) rotate(45)`);
      primaryDiamonds.appendChild(rect);
    }
  }

  const markerDefs = [];
  function buildMarkers() {
    const rand = mulberry32(7331);
    const { count, baseRadius, jitterRadius, minSize, maxSize } = CONFIG.markers;
    for (let i = 0; i < count; i++) {
      // Uneven angular spacing (jittered) rather than a perfect n-gon —
      // this is what "kontrollierte Asymmetrie" means in practice.
      const angle = (i / count) * Math.PI * 2 + (rand() - 0.5) * (Math.PI * 2 / count) * 0.5;
      const radius = baseRadius + (rand() - 0.5) * 2 * jitterRadius;
      const size = minSize + rand() * (maxSize - minSize);
      const c = document.createElementNS(SVG_NS, 'circle');
      c.setAttribute('r', size.toFixed(2));
      markersGroup.appendChild(c);
      markerDefs.push({ el: c, angle, radius, baseOpacity: 0.18 + rand() * 0.12 });
    }
  }

  const particleDefs = []; // { el, angle, radius, homeRadius, band }
  function buildParticles() {
    const groups = [particlesFar, particlesMid, particlesNear];
    CONFIG.particles.bands.forEach((band, bandIndex) => {
      const rand = mulberry32(2000 + bandIndex * 97);
      for (let i = 0; i < band.count; i++) {
        const angle = rand() * Math.PI * 2;
        const radius = band.minR + rand() * (band.maxR - band.minR);
        const size = band.minSize + rand() * (band.maxSize - band.minSize);
        const c = document.createElementNS(SVG_NS, 'circle');
        c.setAttribute('r', size.toFixed(2));
        groups[bandIndex].appendChild(c);
        particleDefs.push({ el: c, angle, radius, homeRadius: radius, band });
      }
    });
  }

  buildTicks();
  buildPrimaryDiamonds();
  buildMarkers();
  buildParticles();

  // =========================================================================
  // State machine
  // =========================================================================
  let toolSectorAngle = 0;
  let wakeStartTs = null;
  let interruptStartTs = null;

  const stateMachine = {
    current: 'offline',
    revertTimer: null,

    set(next, meta) {
      if (!VALID_STATES.includes(next)) return;
      if (this.revertTimer) { clearTimeout(this.revertTimer); this.revertTimer = null; }

      const prev = this.current;
      this.current = next;
      root.setAttribute('data-state', next);
      statusText.textContent = STATE_LABELS[next] || next;

      if (meta && meta.command) {
        commandEl.textContent = meta.command;
        commandEl.hidden = false;
      } else if (next === 'idle' || next === 'offline') {
        commandEl.hidden = true;
      }

      if (next === 'wake_detected') wakeStartTs = performance.now();
      if (next === 'interrupted') interruptStartTs = performance.now();
      if (next === 'tool_execution' && prev !== 'tool_execution') {
        toolSectorAngle = Math.random() * Math.PI * 2;
      }

      const auto = AUTO_REVERT[next];
      if (auto) this.revertTimer = setTimeout(() => this.set(auto.toState), auto.afterMs);
    },
  };

  // =========================================================================
  // Audio envelope — smoothed, engine-agnostic.
  // =========================================================================
  const envelope = { target: 0, current: 0 };
  function setAudioLevel(rms) { envelope.target = Math.max(0, Math.min(1, rms)); }

  // =========================================================================
  // Reduced motion
  // =========================================================================
  // window.matchMedia is universal in any real browser this kiosk would
  // run in, but every other browser API touch in this file is defensive
  // (try/catch around JSON.parse, WebSocket errors, etc.) — a missing or
  // throwing matchMedia here used to be the one call that could take the
  // entire IIFE down before a single frame rendered. Guarded the same way.
  let motionQuery = null;
  try {
    motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  } catch (e) {
    motionQuery = null;
  }
  let reducedMotion = motionQuery ? motionQuery.matches : false;
  let demoOverrideReducedMotion = false;
  // The actual animation gating is the `motionActive` checks throughout
  // tick() below, not this class — it's kept only as a devtools-visible
  // marker (`.reduced-motion` on #hud-root) for inspecting current state
  // by hand; no CSS rule currently keys off it.
  if (motionQuery) motionQuery.addEventListener('change', (e) => {
    reducedMotion = e.matches;
    root.classList.toggle('reduced-motion', reducedMotion);
  });
  root.classList.toggle('reduced-motion', reducedMotion);

  // =========================================================================
  // Animation loop
  // =========================================================================
  let rotorAAngle = 0, rotorBAngle = 0, lastFrameTs = performance.now();
  let nextFlickerTs = 0, flickerIndex = -1, flickerStartTs = 0;

  function ease(p) { return 1 - Math.pow(1 - p, 3); } // ease-out cubic

  // Schedules only the NEXT flicker's start time. Picking flickerIndex
  // here too (as an earlier version did) caused a bug: once a flicker
  // finished, the marker loop below re-triggered the same index every
  // frame until this function ran again, so one marker strobed every
  // ~650ms for the entire gap instead of flickering once. Now
  // flickerIndex/flickerStartTs are only set at the moment a flicker
  // actually begins (in the marker loop), and the loop lets a finished
  // flicker (fp > 1) simply stay at zero extra opacity until the next
  // scheduled time — no restart.
  function scheduleNextFlicker(now) {
    const cfg = CONFIG.markers.idle;
    nextFlickerTs = now + cfg.flickerMinGapMs + Math.random() * (cfg.flickerMaxGapMs - cfg.flickerMinGapMs);
  }

  function buildWobblePath(baseR, segments, wobbleFn) {
    let d = '';
    for (let i = 0; i <= segments; i++) {
      const a = (i / segments) * Math.PI * 2;
      const r = baseR + wobbleFn(a);
      d += (i === 0 ? 'M' : 'L') + (Math.cos(a) * r).toFixed(2) + ' ' + (Math.sin(a) * r).toFixed(2) + ' ';
    }
    return d;
  }

  function tick(ts) {
    const dt = Math.min(0.05, (ts - lastFrameTs) / 1000);
    lastFrameTs = ts;
    const motionActive = !(reducedMotion || demoOverrideReducedMotion);
    const st = stateMachine.current;
    const group = STATE_GROUP[st] || 'idle';
    const pulse = CONFIG.core.pulse[group];
    const secs = ts / 1000;

    // ---- Rotors: constant ambient rotation, not a state indicator on
    // their own. Idle breathes slightly slower; offline stops entirely
    // (it should read as truly at rest, not "quietly alive" like idle);
    // error adds a small jittered wobble to the rate (a "hiccup", not a
    // spin-up). ----
    if (motionActive) {
      let speedFactor = group === 'offline' ? CONFIG.rotors.offlineSlowFactor
        : group === 'idle' ? CONFIG.rotors.idleSlowFactor : 1;
      let jitterA = 0, jitterB = 0;
      if (group === 'error') {
        jitterA = Math.sin(secs * 3.1) * CONFIG.rotors.errorJitterAmount;
        jitterB = Math.sin(secs * 2.3 + 1.7) * CONFIG.rotors.errorJitterAmount;
      }
      rotorAAngle = (rotorAAngle + (CONFIG.rotors.aDegPerSec * speedFactor + jitterA) * dt) % 360;
      rotorBAngle = (rotorBAngle + (CONFIG.rotors.bDegPerSec * speedFactor + jitterB) * dt) % 360;
      rotorA.setAttribute('transform', `rotate(${rotorAAngle.toFixed(2)})`);
      rotorB.setAttribute('transform', `rotate(${rotorBAngle.toFixed(2)})`);
    }

    // ---- Particles: ambient orbit for every band, plus a state-driven
    // radial bias — inward for listening (JARVIS absorbing), outward for
    // speaking (JARVIS emitting), directional toward the tool sector for
    // tool_execution, neutral otherwise. ----
    if (motionActive) {
      // offline freezes drift (no angle increment) rather than skipping
      // this loop outright — particles never get an initial cx/cy set
      // anywhere else, so skipping entirely on the very first frame
      // (the app boots directly into "offline") would leave them all
      // stacked at (0,0) instead of spread across the field.
      const frozen = group === 'offline';
      for (const p of particleDefs) {
        if (!frozen) p.angle += (p.band.orbitDegPerSec * (Math.PI / 180)) * dt;
        let targetR = p.homeRadius;
        if (group === 'listening' || group === 'transcribing') targetR = p.homeRadius - CONFIG.particles.radialDriftPxPerSec * 2.2;
        else if (group === 'speaking') targetR = p.homeRadius + CONFIG.particles.radialDriftPxPerSec * 2.2 * (0.4 + envelope.current);
        p.radius += (targetR - p.radius) * Math.min(1, dt * p.band.drift);
        // Recycle a particle that has drifted too far in either direction
        // back to its home band, at a new angle, rather than clamping —
        // clamping would look like it "hit a wall".
        if (p.radius < p.band.minR * 0.6) { p.radius = p.band.maxR; p.angle += Math.PI * 0.6; }
        if (p.radius > p.band.maxR * 1.15) { p.radius = p.band.minR; p.angle -= Math.PI * 0.6; }
        p.el.setAttribute('cx', (Math.cos(p.angle) * p.radius).toFixed(2));
        p.el.setAttribute('cy', (Math.sin(p.angle) * p.radius).toFixed(2));
      }
    }

    // ---- Envelope smoothing ----
    envelope.current += (envelope.target - envelope.current) * CONFIG.energyRing.smoothing;

    // ---- Wake shockwave: one-shot expanding ring, independent of
    // whether the state has already auto-reverted to "listening".
    // Under reduced motion the ring doesn't grow (no scaling motion) —
    // it just holds at its final radius and fades, still giving a
    // visible cue that something happened without any movement. ----
    // wakeCoreBoost feeds into the core radius below — wake_detected's
    // STATE_GROUP is 'listening' (it shares that pulse profile), so
    // without this the shockwave ring is the ONLY thing distinguishing
    // wake_detected from listening; if that one layer were ever hidden
    // or covered, the two states would be pixel-identical. This gives
    // the core itself a brief, fast decay so the distinction doesn't
    // live on a single layer.
    let wakeCoreBoost = 0;
    if (wakeStartTs !== null) {
      const p = (ts - wakeStartTs) / CONFIG.wake.durationMs;
      if (p >= 1) {
        wakeShockwave.style.opacity = 0;
        wakeStartTs = null;
      } else if (motionActive) {
        const e = ease(Math.min(1, p));
        const r = CONFIG.wake.ringFromRadius + (CONFIG.wake.ringToRadius - CONFIG.wake.ringFromRadius) * e;
        wakeShockwave.setAttribute('r', r.toFixed(1));
        wakeShockwave.style.opacity = (1 - e) * 0.9;
        wakeCoreBoost = (1 - e) * CONFIG.wake.coreBoost;
      } else {
        wakeShockwave.setAttribute('r', String(CONFIG.wake.ringToRadius));
        wakeShockwave.style.opacity = (1 - p) * 0.6;
      }
    }

    // ---- Interrupted: quick flinch, not a color wash ----
    let interruptDip = 0;
    if (interruptStartTs !== null) {
      const p = (ts - interruptStartTs) / CONFIG.interrupt.durationMs;
      if (p >= 1) {
        interruptFlash.style.opacity = 0;
        interruptStartTs = null;
      } else {
        interruptFlash.style.opacity = (1 - p) * 0.28;
        // Damped oscillation: sin(p*2*PI) crosses zero at p=0.5 (the
        // rebound through baseline) and goes negative past that (the
        // overshoot), while exp(-p*4) damps the swing to a settle. A
        // plain sin(p*PI) (the previous formula) never goes negative
        // over p in [0,1], so it only ever dipped and eased back —
        // no actual "flinch" overshoot. Gated by motionActive: under
        // reduced motion the flash still cues the interrupt, but the
        // core/nucleus don't visibly deform.
        if (motionActive) {
          interruptDip = Math.sin(p * Math.PI * 2) * CONFIG.interrupt.dipAmount * Math.exp(-p * 4);
        }
      }
    }

    // ---- Core + nucleus ----
    const isSpeaking = st === 'speaking';
    let coreR;
    if (isSpeaking && motionActive) coreR = CONFIG.core.baseRadius + envelope.current * 16 - interruptDip;
    else if (motionActive) coreR = CONFIG.core.baseRadius + Math.sin(secs * (Math.PI * 2 / pulse.periodSec)) * pulse.amplitude - interruptDip;
    else coreR = CONFIG.core.baseRadius - interruptDip;
    core.setAttribute('r', Math.max(40, coreR + wakeCoreBoost).toFixed(2));

    let nucleusR = CONFIG.core.nucleusBaseRadius;
    if (isSpeaking && motionActive) nucleusR += envelope.current * 6;
    else if (group === 'thinking' && motionActive) nucleusR += Math.sin(secs * 2.4) * 1.4;
    nucleus.setAttribute('r', Math.max(10, nucleusR - interruptDip * 0.4).toFixed(2));

    // Nucleus shimmer: a small internal arc slowly rotating opposite the
    // rotors — the "processing" cue that keeps the core from going fully
    // inert in every ACTIVE state. "offline" is the one exception: that
    // state is supposed to read as truly at rest (disconnected, not
    // "quietly alive"), so it skips this rather than getting the same
    // treatment as idle.
    if (motionActive && group !== 'offline') {
      const shimmerAngle = secs * (group === 'thinking' ? 1.4 : 0.4);
      const a0 = shimmerAngle, a1 = shimmerAngle + 2.1;
      const r = nucleusR * 0.62;
      nucleusShimmer.setAttribute('d',
        `M ${(Math.cos(a0) * r).toFixed(2)} ${(Math.sin(a0) * r).toFixed(2)} `
        + `A ${r.toFixed(2)} ${r.toFixed(2)} 0 0 1 ${(Math.cos(a1) * r).toFixed(2)} ${(Math.sin(a1) * r).toFixed(2)}`
      );
    }

    // ---- Membrane: tight reactive ring. Inward bias while listening,
    // outward push while speaking (scaled by the live envelope), a
    // slower irregular shimmer while thinking, minimal idle wobble. ----
    {
      const baseR = coreR + CONFIG.membrane.baseOffset;
      let wobbleFn;
      if (!motionActive) {
        // Reduced motion: hold the shape (still inward for listening,
        // since that's a constant offset, not oscillation) instead of
        // the sin()-driven wobble every other branch below uses.
        wobbleFn = (group === 'listening' || group === 'transcribing')
          ? () => -CONFIG.membrane.listeningPull : () => 0;
      } else if (isSpeaking) {
        const amp = envelope.current * CONFIG.membrane.speakingPush;
        wobbleFn = (a) => Math.sin(a * 4 + secs * 3.4) * amp * 0.5 + Math.sin(a * 7 - secs * 2.1) * amp * 0.3;
      } else if (group === 'listening' || group === 'transcribing') {
        const pull = CONFIG.membrane.listeningPull * (0.6 + 0.4 * Math.sin(secs * 1.6));
        wobbleFn = () => -pull;
      } else if (group === 'thinking') {
        wobbleFn = (a) => Math.sin(a * 6 + secs * 1.1) * CONFIG.membrane.thinkingWobble;
      } else if (group === 'offline') {
        wobbleFn = () => 0;
      } else {
        wobbleFn = (a) => Math.sin(a * 3 + secs * 0.7) * CONFIG.membrane.idleWobble;
      }
      // Under reduced motion baseR and wobbleFn are both constant frame
      // to frame (coreR is frozen too), so skip rebuilding the 72-point
      // path string once it's been drawn — same pattern as energyWave
      // below, which already had this; membrane didn't.
      if (motionActive || !membrane.dataset.staticDrawn) {
        membrane.setAttribute('d', buildWobblePath(baseR, CONFIG.membrane.segments, wobbleFn));
        membrane.dataset.staticDrawn = motionActive ? '' : '1';
      }
    }

    // ---- Outer energy ring: broad audio contour, mainly a speaking
    // phenomenon; a soft inward-leaning presence during listening;
    // nearly flat otherwise (kept static-skip below for CPU). ----
    const energyNeeded = motionActive && (isSpeaking || group === 'listening' || group === 'transcribing');
    if (energyNeeded || !energyWave.dataset.staticDrawn) {
      const baseR = coreR + CONFIG.energyRing.baseOffset;
      let wobbleFn;
      if (!motionActive) {
        wobbleFn = () => 0;
      } else if (isSpeaking) {
        const amp = envelope.current * CONFIG.energyRing.speakingScale;
        wobbleFn = (a) => Math.sin(a * 5 + secs * 2.6) * amp * 0.5 + Math.sin(a * 9 - secs * 4.1) * amp * 0.3;
      } else if (group === 'listening' || group === 'transcribing') {
        const amp = CONFIG.energyRing.listeningScale;
        wobbleFn = (a) => Math.sin(a * 3 - secs * 1.3) * amp;
      } else {
        wobbleFn = () => 0;
      }
      energyWave.setAttribute('d', buildWobblePath(baseR, CONFIG.energyRing.segments, wobbleFn));
      energyWave.dataset.staticDrawn = energyNeeded ? '' : '1';
    }

    // ---- Markers: idle flicker / thinking chase / tool sector pulse.
    // All time-driven marker motion is gated by motionActive — under
    // reduced motion every marker just sits at its base opacity. ----
    if (!motionActive) {
      for (const m of markerDefs) m.el.setAttribute('opacity', m.baseOpacity.toFixed(2));
    } else if (group === 'idle' || group === 'offline') {
      if (ts > nextFlickerTs) {
        flickerIndex = Math.floor(Math.random() * markerDefs.length);
        flickerStartTs = ts;
        scheduleNextFlicker(ts);
      }
      for (let i = 0; i < markerDefs.length; i++) {
        const m = markerDefs[i];
        let extra = 0;
        if (i === flickerIndex) {
          const fp = (ts - flickerStartTs) / CONFIG.markers.idle.flickerDurationMs;
          // fp > 1 means this marker's one flicker already finished —
          // leave it at base opacity (extra = 0) until scheduleNextFlicker
          // picks a new index; do NOT restart it here.
          if (fp <= 1) extra = Math.sin(fp * Math.PI) * 0.55;
        }
        m.el.setAttribute('opacity', (m.baseOpacity + extra).toFixed(2));
      }
    } else if (group === 'thinking') {
      const cfg = CONFIG.markers.thinking;
      const pointer = (secs * cfg.chaseSpeedRadPerSec) % (Math.PI * 2);
      // Guard against spread <= 0 (a plausible future tuning typo):
      // dividing by zero at d=0 produces NaN opacity, silently killing
      // the whole chase instead of just looking wrong.
      const spread = cfg.spread > 0 ? cfg.spread : 0.01;
      for (const m of markerDefs) {
        let d = Math.abs(m.angle - pointer);
        if (d > Math.PI) d = Math.PI * 2 - d;
        const glow = cfg.glow * Math.exp(-(d * d) / spread);
        m.el.setAttribute('opacity', Math.min(1, m.baseOpacity + glow).toFixed(2));
      }
    } else if (group === 'tool') {
      const cfg = CONFIG.markers.tool;
      const pulseVal = 0.5 + 0.5 * Math.sin(secs * Math.PI * 2 * cfg.pulseHz);
      for (const m of markerDefs) {
        let d = Math.abs(m.angle - toolSectorAngle);
        if (d > Math.PI) d = Math.PI * 2 - d;
        const inSector = d < cfg.sectorHalfWidthRad;
        m.el.setAttribute('opacity', (inSector ? m.baseOpacity + pulseVal * 0.7 : m.baseOpacity).toFixed(2));
      }
    } else {
      for (const m of markerDefs) m.el.setAttribute('opacity', m.baseOpacity.toFixed(2));
    }

    // ---- Tool sector arc on the outer ring ----
    if (group === 'tool') {
      const cfg = CONFIG.markers.tool;
      const r = 248;
      const a0 = toolSectorAngle - cfg.sectorHalfWidthRad, a1 = toolSectorAngle + cfg.sectorHalfWidthRad;
      toolSectorArc.setAttribute('d',
        `M ${(Math.cos(a0) * r).toFixed(2)} ${(Math.sin(a0) * r).toFixed(2)} `
        + `A ${r} ${r} 0 0 1 ${(Math.cos(a1) * r).toFixed(2)} ${(Math.sin(a1) * r).toFixed(2)}`
      );
      toolSectorGroup.style.opacity = 1;
    } else {
      toolSectorGroup.style.opacity = 0;
    }

    // ---- Scan sweep: slow, deliberate, distinct rate for
    // thinking (processing) vs transcribing (scanning input). ----
    if (motionActive && (group === 'thinking' || st === 'transcribing')) {
      const rate = st === 'transcribing' ? 55 : 30; // deg/sec
      scanSweep.setAttribute('transform', `rotate(${((secs * rate) % 360).toFixed(2)})`);
    }

    requestAnimationFrame(tick);
  }

  requestAnimationFrame((ts) => { lastFrameTs = ts; scheduleNextFlicker(ts); requestAnimationFrame(tick); });

  // =========================================================================
  // HUD overlay: clock
  // =========================================================================
  function updateClock() {
    clockEl.textContent = new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  }
  updateClock();
  setInterval(updateClock, 15000);

  // =========================================================================
  // WebSocket client — reuses the existing /ws endpoint and auth-token
  // convention from web/app.js. See docs/UI_INTEGRATION.md.
  // =========================================================================
  const urlToken = new URLSearchParams(location.search).get('token') || '';
  function authUrl(url) {
    if (!urlToken) return url;
    return url + (url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(urlToken);
  }

  let ws = null;
  let reconnectDelay = CONFIG.reconnect.initialDelayMs;
  let reconnectTimer = null;
  const isDemo = new URLSearchParams(location.search).get('demo') === '1';

  function connect() {
    if (isDemo) { stateMachine.set('idle'); return; }
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(authUrl(`${protocol}//${location.host}/ws`));

    ws.onopen = () => {
      reconnectDelay = CONFIG.reconnect.initialDelayMs;
      if (stateMachine.current === 'offline') stateMachine.set('idle');
    };
    ws.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }
      handleServerMessage(msg);
    };
    ws.onclose = () => {
      stateMachine.set('offline');
      reconnectTimer = setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, CONFIG.reconnect.maxDelayMs);
    };
    ws.onerror = () => { try { ws.close(); } catch {} };
  }

  function handleServerMessage(msg) {
    switch (msg.type) {
      case 'assistant_state':
        stateMachine.set(msg.state, msg);
        break;
      case 'audio_level':
        setAudioLevel(msg.rms);
        break;
      case 'stream_end':
        if (stateMachine.current === 'thinking') stateMachine.set('idle');
        break;
      case 'error':
        stateMachine.set('error');
        setTimeout(() => { if (stateMachine.current === 'error') stateMachine.set('idle'); }, 2500);
        break;
      case 'user_changed':
        if (msg.user_id) userEl.textContent = msg.user_id;
        break;
      case 'system_stats':
        if (msg.data && msg.data.user) userEl.textContent = msg.data.user;
        if (msg.data && msg.data.mode) modeEl.textContent = msg.data.mode;
        break;
      default:
        break;
    }
  }

  if (!isDemo) connect();

  // =========================================================================
  // Demo / debug mode — fully offline state + envelope simulation.
  // =========================================================================
  if (isDemo) {
    const panel = document.getElementById('demo-panel');
    panel.hidden = false;
    modeEl.textContent = 'Demo';
    userEl.textContent = 'Demo';

    const grid = document.getElementById('demo-state-buttons');
    const buttons = {};
    VALID_STATES.forEach((s) => {
      const btn = document.createElement('button');
      btn.textContent = STATE_LABELS[s];
      btn.addEventListener('click', () => {
        stateMachine.set(s, s === 'tool_execution' ? { command: 'Öffnet Programm' } : undefined);
        Object.values(buttons).forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
      });
      grid.appendChild(btn);
      buttons[s] = btn;
    });
    buttons.idle.classList.add('active');
    stateMachine.set('idle');

    const levelInput = document.getElementById('demo-audio-level');
    let demoT = 0;
    setInterval(() => {
      if (stateMachine.current !== 'speaking') return;
      demoT += 0.1;
      const base = levelInput.value / 100;
      const synthetic = base * (0.6 + 0.4 * Math.sin(demoT * CONFIG.audio.demoSpeechFrequencyHz))
        + (Math.random() - 0.5) * CONFIG.audio.demoNoiseAmount;
      setAudioLevel(Math.max(0, Math.min(1, synthetic)));
    }, 60);

    document.getElementById('demo-reduced-motion').addEventListener('change', (e) => {
      demoOverrideReducedMotion = e.target.checked;
      root.classList.toggle('reduced-motion', demoOverrideReducedMotion || reducedMotion);
    });
  }

  window.__jarvisHud = { stateMachine, setAudioLevel, CONFIG };
})();
