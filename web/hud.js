/**
 * JARVIS HUD — state machine, SVG eye animation, WebSocket client, demo mode.
 *
 * Architecture note for future visual tuning (see docs/UI_INTEGRATION.md):
 * every size/speed/intensity knob lives in CONFIG below. Nothing else in
 * this file should contain a magic number for "how fast" or "how strong" —
 * if tomorrow's reference material calls for different pacing, this is the
 * only object that needs to change.
 */

(function () {
  'use strict';

  // =========================================================================
  // CONFIG — single source of truth for all visual tuning parameters.
  // =========================================================================
  const CONFIG = {
    rotorA: { baseSpeedDegPerSec: 6 },      // outer dashed ring, clockwise
    rotorB: { baseSpeedDegPerSec: -9 },     // segmented ring, counter-clockwise
    particles: { count: 42, speedDegPerSec: 1.2, minR: 100, maxR: 236, minSize: 0.8, maxSize: 2.2 },
    ticks: { outerCount: 48, innerMarkerCount: 14 },

    core: {
      baseRadius: 86,
      pulse: {
        idle:      { amplitude: 3,  periodSec: 4.2 },
        listening: { amplitude: 6,  periodSec: 1.6 },
        thinking:  { amplitude: 5,  periodSec: 1.1 },
        tool:      { amplitude: 4,  periodSec: 0.7 },
        speaking:  { amplitude: 10, periodSec: 0.5 },  // overridden by live envelope
        error:     { amplitude: 7,  periodSec: 0.35 },
        offline:   { amplitude: 0,  periodSec: 1 },
      },
    },

    energyRing: {
      baseRadius: 150,
      waveSegments: 90,
      idleAmplitude: 2,
      speakingAmplitudeScale: 46, // px per unit envelope (0..1)
      smoothing: 0.35,            // envelope lerp factor per frame (higher = snappier)
    },

    wakeDetected: {
      durationMs: 550,   // brief impulse, then auto-advances to "listening"
      burstScale: 1.35,
    },

    transitions: {
      colorFadeMs: 400,
    },

    audio: {
      // Demo-mode synthetic envelope shaping only — real envelope comes
      // from the backend's audio_level events (0..1 rms/peak) untouched.
      demoSpeechFrequencyHz: 2.1,
      demoNoiseAmount: 0.18,
    },

    reconnect: {
      initialDelayMs: 1000,
      maxDelayMs: 15000,
    },
  };

  // Auto-revert timings for transient / non-terminal states when the
  // backend doesn't (yet) send an explicit follow-up event. Keeps the HUD
  // from getting stuck if e.g. "tool_execution" never gets a matching
  // "done" — states not listed here just wait for the next real event.
  const AUTO_REVERT = {
    wake_detected: { toState: 'listening', afterMs: CONFIG.wakeDetected.durationMs },
  };

  // German display labels — see docs/UI_INTEGRATION.md for the canonical
  // state identifiers (English, internal) vs. these (German, user-facing).
  const STATE_LABELS = {
    offline: 'Offline',
    idle: 'Bereit',
    wake_detected: 'Aktiviert',
    listening: 'Höre zu',
    transcribing: 'Verarbeite',
    thinking: 'Denke nach',
    tool_execution: 'Führe aus',
    speaking: 'Spreche',
    interrupted: 'Unterbrochen',
    error: 'Fehler',
  };

  const VALID_STATES = Object.keys(STATE_LABELS);

  // =========================================================================
  // DOM refs
  // =========================================================================
  const root = document.getElementById('hud-root');
  const svg = document.getElementById('eye');
  const rotorA = document.getElementById('ring-rotor-a');
  const rotorB = document.getElementById('ring-rotor-b');
  const particlesGroup = document.getElementById('particles');
  const ticksOuter = document.getElementById('ticks-outer');
  const markersInner = document.getElementById('markers-inner');
  const core = document.getElementById('core');
  const energyTrack = document.getElementById('ring-energy-track');
  const energyWave = document.getElementById('ring-energy-wave');
  const statusDot = document.getElementById('hud-status-dot');
  const statusText = document.getElementById('hud-status-text');
  const clockEl = document.getElementById('hud-clock');
  const userEl = document.getElementById('hud-user');
  const modeEl = document.getElementById('hud-mode');
  const commandEl = document.getElementById('hud-command');

  // =========================================================================
  // SVG construction — ticks, markers, particles (built once at load)
  // =========================================================================
  const SVG_NS = 'http://www.w3.org/2000/svg';

  function buildTicks() {
    const n = CONFIG.ticks.outerCount;
    const r1 = 240, r2 = 248;
    for (let i = 0; i < n; i++) {
      const angle = (i / n) * Math.PI * 2;
      const x1 = Math.cos(angle) * r1, y1 = Math.sin(angle) * r1;
      const x2 = Math.cos(angle) * r2, y2 = Math.sin(angle) * r2;
      const line = document.createElementNS(SVG_NS, 'line');
      line.setAttribute('x1', x1.toFixed(2));
      line.setAttribute('y1', y1.toFixed(2));
      line.setAttribute('x2', x2.toFixed(2));
      line.setAttribute('y2', y2.toFixed(2));
      line.setAttribute('stroke', 'var(--ring-track-color)');
      line.setAttribute('stroke-width', i % 4 === 0 ? '2' : '1');
      ticksOuter.appendChild(line);
    }
  }

  function buildMarkers() {
    const n = CONFIG.ticks.innerMarkerCount;
    const r = 168;
    for (let i = 0; i < n; i++) {
      const angle = (i / n) * Math.PI * 2;
      const x = Math.cos(angle) * r, y = Math.sin(angle) * r;
      const c = document.createElementNS(SVG_NS, 'circle');
      c.setAttribute('cx', x.toFixed(2));
      c.setAttribute('cy', y.toFixed(2));
      c.setAttribute('r', '1.6');
      c.setAttribute('opacity', '0.55');
      markersInner.appendChild(c);
    }
  }

  // Deterministic pseudo-random so particle layout is stable across reloads.
  function mulberry32(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const particleDefs = [];
  function buildParticles() {
    const rand = mulberry32(1337);
    const { count, minR, maxR, minSize, maxSize } = CONFIG.particles;
    for (let i = 0; i < count; i++) {
      const angle = rand() * Math.PI * 2;
      const radius = minR + rand() * (maxR - minR);
      const size = minSize + rand() * (maxSize - minSize);
      const c = document.createElementNS(SVG_NS, 'circle');
      c.setAttribute('r', size.toFixed(2));
      c.setAttribute('opacity', (0.15 + rand() * 0.35).toFixed(2));
      particlesGroup.appendChild(c);
      particleDefs.push({ el: c, angle, radius, phase: rand() * Math.PI * 2 });
    }
  }

  buildTicks();
  buildMarkers();
  buildParticles();

  // =========================================================================
  // State machine
  // =========================================================================
  const stateMachine = {
    current: 'offline',
    since: performance.now(),
    revertTimer: null,

    set(next, meta) {
      if (!VALID_STATES.includes(next)) return;
      if (this.revertTimer) { clearTimeout(this.revertTimer); this.revertTimer = null; }

      this.current = next;
      this.since = performance.now();
      root.setAttribute('data-state', next);
      statusText.textContent = STATE_LABELS[next] || next;

      if (meta && meta.command) {
        commandEl.textContent = meta.command;
        commandEl.hidden = false;
      } else if (next === 'idle' || next === 'offline') {
        commandEl.hidden = true;
      }

      const auto = AUTO_REVERT[next];
      if (auto) {
        this.revertTimer = setTimeout(() => this.set(auto.toState), auto.afterMs);
      }
    },
  };

  // =========================================================================
  // Audio envelope — smoothed, engine-agnostic. Real data via WS
  // 'audio_level' messages ({rms, peak} in 0..1), demo mode synthesizes it.
  // =========================================================================
  const envelope = { target: 0, current: 0, peak: 0 };

  function setAudioLevel(rms, peak) {
    envelope.target = Math.max(0, Math.min(1, rms));
    envelope.peak = Math.max(0, Math.min(1, peak != null ? peak : rms));
  }

  // =========================================================================
  // Animation loop
  // =========================================================================
  let reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', (e) => {
    reducedMotion = e.matches;
    root.classList.toggle('reduced-motion', reducedMotion);
  });
  root.classList.toggle('reduced-motion', reducedMotion);

  let rotorAAngle = 0, rotorBAngle = 0, particleAngleOffset = 0;
  let lastFrameTs = performance.now();
  let demoOverrideReducedMotion = false;

  function stateColorPulse(t) {
    const st = stateMachine.current;
    const key = ({
      idle: 'idle', wake_detected: 'listening', listening: 'listening',
      transcribing: 'listening', thinking: 'thinking', tool_execution: 'tool',
      speaking: 'speaking', interrupted: 'error', error: 'error', offline: 'offline',
    })[st] || 'idle';
    return CONFIG.core.pulse[key];
  }

  function tick(ts) {
    const dt = Math.min(0.05, (ts - lastFrameTs) / 1000); // clamp to avoid jumps on tab-resume
    lastFrameTs = ts;
    const motionActive = !(reducedMotion || demoOverrideReducedMotion);

    // --- Rotor rotation (skipped when reduced motion) ---
    if (motionActive) {
      rotorAAngle = (rotorAAngle + CONFIG.rotorA.baseSpeedDegPerSec * dt) % 360;
      rotorBAngle = (rotorBAngle + CONFIG.rotorB.baseSpeedDegPerSec * dt) % 360;
      particleAngleOffset += CONFIG.particles.speedDegPerSec * dt * (Math.PI / 180);
      rotorA.setAttribute('transform', `rotate(${rotorAAngle.toFixed(2)})`);
      rotorB.setAttribute('transform', `rotate(${rotorBAngle.toFixed(2)})`);
      for (const p of particleDefs) {
        const a = p.angle + particleAngleOffset;
        p.el.setAttribute('cx', (Math.cos(a) * p.radius).toFixed(2));
        p.el.setAttribute('cy', (Math.sin(a) * p.radius).toFixed(2));
      }
    }

    // --- Envelope smoothing (always active — needed for speaking state) ---
    envelope.current += (envelope.target - envelope.current) * CONFIG.energyRing.smoothing;

    // --- Core pulse ---
    const pulse = stateColorPulse(ts);
    const isSpeaking = stateMachine.current === 'speaking';
    const wakeBoost = stateMachine.current === 'wake_detected'
      ? CONFIG.wakeDetected.burstScale
      : 1;
    let coreR;
    if (isSpeaking) {
      coreR = CONFIG.core.baseRadius + envelope.current * 22;
    } else if (motionActive) {
      const phase = (ts / 1000) * (Math.PI * 2 / pulse.periodSec);
      coreR = CONFIG.core.baseRadius + Math.sin(phase) * pulse.amplitude * wakeBoost;
    } else {
      coreR = CONFIG.core.baseRadius;
    }
    core.setAttribute('r', coreR.toFixed(2));

    // --- Energy ring: radius breathes gently, waveform reacts to envelope ---
    const energyBase = CONFIG.energyRing.baseRadius;
    let energyR = energyBase;
    if (isSpeaking) {
      energyR = energyBase + envelope.current * 10;
    } else if (motionActive) {
      const phase = (ts / 1000) * (Math.PI * 2 / (pulse.periodSec * 1.3));
      energyR = energyBase + Math.sin(phase) * CONFIG.energyRing.idleAmplitude;
    }
    energyTrack.setAttribute('r', energyR.toFixed(2));

    // Skip the per-frame path rebuild entirely when nothing would move —
    // reduced motion + not speaking means a perfectly static ring, so
    // draw it once and stop (real CPU savings, not just a visual no-op).
    if (!motionActive && !isSpeaking) {
      if (!energyWave.dataset.staticDrawn) {
        drawEnergyWave(ts, energyR, 0, false);
        energyWave.dataset.staticDrawn = '1';
      }
    } else {
      energyWave.dataset.staticDrawn = '';
      drawEnergyWave(ts, energyR, isSpeaking ? envelope.current : 0.06, motionActive);
    }

    requestAnimationFrame(tick);
  }

  function drawEnergyWave(ts, baseR, amplitudeUnit, motionActive) {
    const segs = CONFIG.energyRing.waveSegments;
    const scale = CONFIG.energyRing.speakingAmplitudeScale;
    let d = '';
    for (let i = 0; i <= segs; i++) {
      const a = (i / segs) * Math.PI * 2;
      // Layered sines give an organic, non-repetitive wobble instead of a
      // single clean sine — reads as "energy", not "equalizer bar".
      const wobble = motionActive
        ? Math.sin(a * 5 + ts / 260) * 0.5 + Math.sin(a * 9 - ts / 410) * 0.3
        : 0;
      const r = baseR + wobble * amplitudeUnit * (scale / 10);
      const x = Math.cos(a) * r, y = Math.sin(a) * r;
      d += (i === 0 ? 'M' : 'L') + x.toFixed(2) + ' ' + y.toFixed(2) + ' ';
    }
    energyWave.setAttribute('d', d);
  }

  requestAnimationFrame((ts) => { lastFrameTs = ts; requestAnimationFrame(tick); });

  // =========================================================================
  // HUD overlay: clock
  // =========================================================================
  function updateClock() {
    const now = new Date();
    clockEl.textContent = now.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
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
    if (isDemo) { stateMachine.set('idle'); return; } // demo mode never touches the network
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
        setAudioLevel(msg.rms, msg.peak);
        break;
      case 'stream_start':
        // Text is streaming back — if voice is off this is effectively
        // "speaking" in spirit, but we don't want to claim audio output
        // that may not exist, so we stay in 'thinking' here and let a
        // real 'speaking' assistant_state (TTS-bracketed) take over when
        // voice is on. See docs/UI_INTEGRATION.md for the known gap.
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
        applySystemStats(msg.data || {});
        break;
      default:
        break; // Other message types (session_list, doc_status, ...) don't concern the HUD.
    }
  }

  function applySystemStats(data) {
    if (data.user) userEl.textContent = data.user;
    if (data.mode) modeEl.textContent = data.mode;
  }

  if (!isDemo) connect();

  // =========================================================================
  // Demo / debug mode — fully offline state + envelope simulation.
  // Enable with ?demo=1. Never visible otherwise.
  // =========================================================================
  if (isDemo) {
    const panel = document.getElementById('demo-panel');
    panel.hidden = false;
    modeEl.textContent = 'Demo';
    userEl.textContent = 'Demo-Nutzer';

    const grid = document.getElementById('demo-state-buttons');
    const buttons = {};
    VALID_STATES.forEach((s) => {
      const btn = document.createElement('button');
      btn.textContent = STATE_LABELS[s];
      btn.addEventListener('click', () => {
        stateMachine.set(s, s === 'tool_execution' ? { command: 'Führe Systembefehl aus…' } : undefined);
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
      setAudioLevel(Math.max(0, Math.min(1, synthetic)), Math.max(0, Math.min(1, synthetic + 0.1)));
    }, 60);

    document.getElementById('demo-reduced-motion').addEventListener('change', (e) => {
      demoOverrideReducedMotion = e.target.checked;
      root.classList.toggle('reduced-motion', demoOverrideReducedMotion || reducedMotion);
    });
  }

  // Expose a tiny debug hook for console-driven testing without the panel.
  window.__jarvisHud = { stateMachine, setAudioLevel, CONFIG };
})();
