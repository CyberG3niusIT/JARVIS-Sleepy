import { TransportError, getJson, type JarvisTarget } from "./transport";
import {
  getRuntimeControl,
  notImplementedRuntime,
  parseRuntimeSnapshot,
  type RuntimeControlCapabilities,
  type RuntimeControlSnapshot,
} from "./runtime-control";
import type {
  Activity,
  ConfiguredService,
  JarvisAdapter,
  JarvisSnapshot,
  Metric,
  RuntimeEnvelope,
  RuntimeStatus,
  StatusTone,
} from "./types";

/**
 * Production adapter. Only values that a verified backend source delivers are shown; everything
 * else stays "Keine Live-Daten" / empty, every action reports NOT_IMPLEMENTED.
 *
 * RUNTIME STATE: the backend data API has no interface that reports STARTING/READY/DEGRADED/
 * ERROR/STOPPED (only stdout/exit code of start.sh/stop.sh), and this adapter never derives one
 * from HTTP probes. Runtime state and lifecycle come solely from the RuntimeControlTransport
 * (runtime-control.ts, later the native supervisor); without one the state is NOT_IMPLEMENTED and
 * all lifecycle capabilities are off. Reachability of single services is shown separately and
 * describes only that service's own answer.
 *
 * Verified sources (see Dokumentation/16_UI_CONTROL_HUB.md for evidence):
 *   web        GET /api/stats               jarvis_web.py:3352      reachability of jarvis_web.py, `llm.model`
 *   web        GET /api/events/watchdog     jarvis_web.py:4056      watchdog events (epoch-second timestamps) -> activity feed
 *   web        GET /api/events/health       jarvis_web.py:4087      last health snapshot (10-min interval) -> CPU/RAM cards
 *   web        GET /api/memory/summary      jarvis_web.py:4128      facts.total, faiss.vectors -> memory counts
 *   web        GET /api/metrics/summary     jarvis_web.py:3371      total_interactions, avg_latency_ms -> AI Core rows
 *   llm-main   GET /health                  llama-server (live)     {status:"ok"}
 *   llm-main   GET /v1/models               llama-server (live)     data[0].id, meta.{n_ctx,n_params,ftype}
 *   llm-small  GET /health                  llama-server            {status:"ok"}
 *   tts        GET /health                  chatterbox (401 w/o token in live env)
 *   flux       GET /health                  services/flux_server.py {status:"ready"|"loading"}
 *   vvs        GET /health, /ready          VVS (live)              {ok, static:{ready,...}} / {ready}
 */

const unavailable = "Keine Live-Daten";

interface StatsPayload {
  llm?: { model?: string } | null;
  memory?: { vectors?: number } | null;
}
interface HealthTrendsPayload {
  trends?: Record<string, { stats?: { latest?: number | null; latest_ts?: number | null } }>;
}
interface MetricsSummaryPayload {
  total_interactions?: number;
  avg_latency_ms?: number;
  hours?: number;
}
interface MemorySummaryPayload {
  facts?: { total?: number; error?: string };
  faiss?: { vectors?: number; error?: string };
}
interface HealthPayload {
  status?: string;
}
interface VvsHealthPayload {
  ok?: boolean;
  healthy?: boolean;
  status?: string;
}
interface VvsReadyPayload {
  ready?: boolean;
}
interface ModelsPayload {
  data?: {
    id?: string;
    owned_by?: string;
    meta?: { n_ctx?: number; n_params?: number; ftype?: string };
  }[];
}
interface WatchdogPayload {
  events?: { timestamp?: string | number; event?: string; message?: string; severity?: string }[];
}

type Probe<T> = { ok: true; value: T } | { ok: false; error: TransportError };
interface Reach {
  tone: StatusTone;
  text: string;
}

async function probe<T>(target: JarvisTarget, path: string): Promise<Probe<T>> {
  try {
    return { ok: true, value: await getJson<T>(target, path) };
  } catch (error) {
    if (error instanceof TransportError) return { ok: false, error };
    throw error;
  }
}

/** Describes only what the service itself answered. Not a runtime state. */
function failureReach(error: TransportError): Reach {
  if (error.kind === "http" && (error.status === 401 || error.status === 403))
    return { tone: "warning", text: `Erreichbar, Zugriff verweigert (HTTP ${error.status})` };
  if (error.kind === "http") return { tone: "warning", text: `Antwortet mit HTTP ${error.status}` };
  if (error.kind === "invalid-json") return { tone: "warning", text: "Ungültige Antwort" };
  if (error.kind === "no-transport")
    return { tone: "idle", text: "Transport nicht verfügbar (kein Proxy/keine Bridge)" };
  return { tone: "offline", text: "Nicht erreichbar" };
}

function healthReach(result: Probe<HealthPayload>): Reach {
  if (!result.ok) return failureReach(result.error);
  const status = result.value.status;
  if (status === "ok" || status === "ready")
    return { tone: "online", text: "Erreichbar, Health ok" };
  if (status === "loading") return { tone: "info", text: "Erreichbar, lädt" };
  return { tone: "warning", text: `Erreichbar, Health-Status: ${status ?? "ohne Angabe"}` };
}

/** Same predicate as scripts/check_runtime_dependencies.py uses for VVS. */
function vvsReach(health: Probe<VvsHealthPayload>, ready: Probe<VvsReadyPayload>): Reach {
  if (!health.ok) return failureReach(health.error);
  if (!ready.ok) return failureReach(ready.error);
  const h = health.value;
  const healthy =
    h.ok !== false &&
    h.healthy !== false &&
    (h.status === undefined || h.status === "ok" || h.status === "healthy");
  if (ready.value.ready === true && healthy) return { tone: "online", text: "Erreichbar, ready" };
  return { tone: "warning", text: "Erreichbar, nicht ready" };
}

/** jarvis_web.py's /api/stats always carries these keys (`_gather_system_stats`). */
function isStatsPayload(value: unknown): value is StatsPayload {
  return typeof value === "object" && value !== null && "skills_loaded" in value;
}

function webReach(web: Probe<StatsPayload>): Reach {
  if (web.ok) return { tone: "online", text: "Erreichbar" };
  return failureReach(web.error);
}

function watchdogLevel(severity: string | undefined): Activity["level"] {
  switch ((severity ?? "").toLowerCase()) {
    case "error":
    case "fatal":
      return "Fehler";
    case "warn":
    case "warning":
      return "Warnung";
    case "debug":
    case "trace":
      return "Debug";
    default:
      return "Info";
  }
}

/** Backend timestamps are float epoch seconds (time.time()), see event_logger.py. */
function epochTime(value: string | number | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "";
  return new Date(value * 1000).toLocaleTimeString("de-DE");
}

/** Last stored health snapshot of one metric, or undefined when the backend has none. */
function latestSnapshot(payload: HealthTrendsPayload | undefined, metric: string) {
  const stats = payload?.trends?.[metric]?.stats;
  if (!stats || typeof stats.latest !== "number") return undefined;
  return { value: stats.latest, ts: stats.latest_ts ?? undefined };
}

function snapshotMetric(
  label: string,
  payload: HealthTrendsPayload | undefined,
  metric: string,
  note: string,
  answered: boolean,
): Metric {
  const snapshot = latestSnapshot(payload, metric);
  if (!snapshot)
    return {
      label,
      value: unavailable,
      detail: answered ? "Kein Health-Snapshot im Backend vorhanden" : unavailable,
    };
  const at =
    snapshot.ts === undefined
      ? "Zeitpunkt unbekannt"
      : new Date(snapshot.ts * 1000).toLocaleString("de-DE", {
          day: "2-digit",
          month: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
        });
  return {
    label,
    value: `${snapshot.value} %`,
    detail: `${note}, Snapshot ${at}`,
    progress: Math.min(Math.max(snapshot.value, 0), 100),
  };
}

function toActivities(payload: WatchdogPayload | undefined): Activity[] {
  return (payload?.events ?? []).map((event, index) => {
    return {
      id: `watchdog-${event.timestamp ?? index}-${event.event ?? ""}`,
      time: epochTime(event.timestamp),
      source: "Watchdog",
      level: watchdogLevel(event.severity),
      message: event.message ?? event.event ?? unavailable,
      context: event.event ?? "watchdog",
    };
  });
}

const modelName = (id: string) => id.split(/[\\/]/).pop() || id;
const formatParams = (n: number) =>
  `${(n / 1e9).toLocaleString("de-DE", { maximumFractionDigits: 1 })} Mrd.`;

let runtimeCapabilities: RuntimeControlCapabilities = { start: false, stop: false, restart: false };

const supervisorTimeoutMs = 3000;

async function readRuntime(): Promise<RuntimeControlSnapshot> {
  try {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const timeout = new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error("supervisor timeout")), supervisorTimeoutMs);
    });
    try {
      return parseRuntimeSnapshot(await Promise.race([getRuntimeControl().getRuntime(), timeout]));
    } finally {
      clearTimeout(timer);
    }
  } catch {
    // The supervisor could not be asked. That is not a runtime state, so none is reported.
    return notImplementedRuntime("Runtime-Supervisor nicht abfragbar");
  }
}

function toRuntimeStatus(reading: RuntimeControlSnapshot): RuntimeStatus {
  return {
    state: reading.state,
    degradedReasons: reading.degradedReasons,
    ...(reading.degradedReasons.length > 0
      ? { degradedReason: reading.degradedReasons.join("; ") }
      : {}),
    components: reading.components,
    ...(reading.detail !== undefined ? { detail: reading.detail } : {}),
    // NOT_IMPLEMENTED readings are synthesized locally (no supervisor observation): no "Stand".
    ...(reading.state !== "NOT_IMPLEMENTED" ? { backendTimestamp: reading.updatedAt } : {}),
  };
}

async function loadSnapshot(): Promise<RuntimeEnvelope<JarvisSnapshot>> {
  // Capabilities are only valid together with the reading that produced them.
  runtimeCapabilities = { start: false, stop: false, restart: false };
  const runtimePromise = readRuntime();
  const [web, llmMain, models, llmSmall, tts, flux, vvsHealth, vvsReady] = await Promise.all([
    probe<StatsPayload>("web", "/api/stats").then((result): Probe<StatsPayload> =>
      result.ok && !isStatsPayload(result.value)
        ? {
            ok: false,
            error: new TransportError("invalid-json", "web/api/stats: unerwartete Antwort"),
          }
        : result,
    ),
    probe<HealthPayload>("llm-main", "/health"),
    probe<ModelsPayload>("llm-main", "/v1/models"),
    probe<HealthPayload>("llm-small", "/health"),
    probe<HealthPayload>("tts", "/health"),
    probe<HealthPayload>("flux", "/health"),
    probe<VvsHealthPayload>("vvs", "/health"),
    probe<VvsReadyPayload>("vvs", "/ready"),
  ]);
  const [watchdog, health, memory, llmSummary] = web.ok
    ? await Promise.all([
        probe<WatchdogPayload>("web", "/api/events/watchdog?hours=24"),
        probe<HealthTrendsPayload>(
          "web",
          "/api/events/health?hours=24&metrics=cpu.load,ram.percent",
        ),
        probe<MemorySummaryPayload>("web", "/api/memory/summary"),
        probe<MetricsSummaryPayload>("web", "/api/metrics/summary?hours=24"),
      ])
    : [undefined, undefined, undefined, undefined];
  const runtimeReading = await runtimePromise;
  runtimeCapabilities = runtimeReading.capabilities;
  const healthPayload = health?.ok ? health.value : undefined;
  const healthAnswered = health?.ok === true;
  // /api/memory/summary answers total 0 without an error when no memory manager exists;
  // /api/stats reports memory: null in that case, so only trust the counts when it is set.
  const memoryReady =
    web.ok && web.value.memory != null && memory?.ok && !memory.value.facts?.error;

  const mainReach = healthReach(llmMain);
  const reach: [string, string, Reach][] = [
    ["Web-API", "jarvis_web.py /api/stats", webReach(web)],
    ["Main LLM", "llama-server /health", mainReach],
    ["Small LLM", "llama-server /health", healthReach(llmSmall)],
    ["Chatterbox", "/health", healthReach(tts)],
    ["FLUX.2 Klein 4B", "/health", healthReach(flux)],
    ["VVS", "/health, /ready", vvsReach(vvsHealth, vvsReady)],
  ];
  const services: ConfiguredService[] = reach.map(([name, endpoint, r]) => ({
    name,
    endpoint,
    configuration: r.text,
    health: r.tone,
  }));
  const entry = models.ok ? models.value.data?.[0] : undefined;
  const meta = entry?.meta;

  const snapshot: JarvisSnapshot = {
    // Reported by the runtime supervisor only; NOT_IMPLEMENTED while none is installed.
    runtime: toRuntimeStatus(runtimeReading),
    version: unavailable,
    build: unavailable,
    metrics: [
      snapshotMetric("CPU", healthPayload, "cpu.load", "Auslastung", healthAnswered),
      // The backend health check falls back to '0%' when rocm-smi has no value (health_check.py),
      // so a stored gpu1.* value cannot be told apart from "unknown". Not shown.
      { label: "GPU", value: unavailable, detail: "Backend-Wert nicht eindeutig" },
      snapshotMetric("RAM", healthPayload, "ram.percent", "Belegung", healthAnswered),
      { label: "VRAM", value: unavailable, detail: "Backend-Wert nicht eindeutig" },
      { label: "Netzwerk", value: unavailable, detail: "Keine Schnittstelle im Backend" },
      { label: "Aktive Agenten", value: unavailable, detail: "Keine Agenten-Schnittstelle" },
    ],
    performance: [],
    gpuPerformance: [],
    model: {
      name: entry?.id ? modelName(entry.id) : (web.ok && web.value.llm?.model) || unavailable,
      family: unavailable,
      quantization: meta?.ftype ?? unavailable,
      context: meta?.n_ctx !== undefined ? `${meta.n_ctx} Token` : unavailable,
      parameters: meta?.n_params !== undefined ? formatParams(meta.n_params) : unavailable,
      location: entry?.id ?? unavailable,
      runtime: entry?.owned_by === "llamacpp" ? "llama.cpp" : unavailable,
      endpoint: unavailable,
      gpuLayers: null,
      batchSize: null,
      ubatchSize: null,
      temperature: null,
      topP: null,
      topK: null,
      toolCalling: null,
      status: mainReach.tone,
    },
    activities: toActivities(watchdog?.ok ? watchdog.value : undefined),
    ...(llmSummary?.ok &&
    typeof llmSummary.value.total_interactions === "number" &&
    Number.isFinite(llmSummary.value.total_interactions)
      ? {
          llmStats: {
            interactions: llmSummary.value.total_interactions,
            // get_summary() answers 0 when there are no interactions: only meaningful with data.
            avgLatencyMs:
              llmSummary.value.total_interactions > 0 &&
              typeof llmSummary.value.avg_latency_ms === "number" &&
              Number.isFinite(llmSummary.value.avg_latency_ms)
                ? llmSummary.value.avg_latency_ms
                : null,
            hours: llmSummary.value.hours ?? 24,
          },
        }
      : {}),
    ...(memoryReady && memory?.ok
      ? {
          memoryCounts: {
            facts: memory.value.facts?.total ?? null,
            vectors: memory.value.faiss?.error ? null : (memory.value.faiss?.vectors ?? null),
          },
        }
      : {}),
    agents: [],
    memories: [],
    tools: [],
    automations: [],
    voice: {
      input: unavailable,
      device: unavailable,
      sampleRate: null,
      channels: null,
      outputBackend: unavailable,
      tempPath: unavailable,
      language: unavailable,
      wakeEngine: unavailable,
      wakeKeyword: unavailable,
      sttBackend: unavailable,
      sttModel: unavailable,
      sttRuntime: unavailable,
      sttProvider: unavailable,
      sttThreads: null,
      tts: unavailable,
      ttsEndpoint: unavailable,
      ttsConnectTimeout: unavailable,
      ttsReadTimeout: unavailable,
      ttsWarmup: null,
      ttsFallback: unavailable,
      ttsAlternative: unavailable,
    },
    platform: { host: unavailable, linuxRuntime: unavailable, architecture: unavailable },
    hardware: {
      cpu: unavailable,
      gpu: unavailable,
      vramCapacity: unavailable,
      ramCapacity: unavailable,
    },
    services,
    memoryArchitecture: { stores: [], features: [] },
    // Code fact (core/privacy_gate.py exists), not runtime data; no interface to read or set it.
    privacy: { gateImplemented: true, modesImplemented: true, desktopConnected: false },
    metricsRetentionDays: null,
    subsystems: reach.map(([name, , r]) => ({ name, status: r.tone, detail: r.text })),
    devices: [],
  };
  return { phase: "ready", data: snapshot, updatedAt: new Date().toISOString() };
}

export const productionAdapter: JarvisAdapter = {
  mode: "production",
  async getSnapshot() {
    try {
      return await loadSnapshot();
    } catch {
      runtimeCapabilities = { start: false, stop: false, restart: false };
      return {
        phase: "error",
        message: "Runtime-Daten konnten nicht geladen werden.",
        updatedAt: new Date().toISOString(),
      };
    }
  },
  // Lifecycle capabilities are whatever the runtime supervisor reported in its last reading
  // (all false without one). Everything else has no backend interface.
  hasCapability(capability) {
    switch (capability) {
      case "runtime.start":
        return runtimeCapabilities.start;
      case "runtime.stop":
        return runtimeCapabilities.stop;
      case "runtime.restart":
        return runtimeCapabilities.restart;
      default:
        return false;
    }
  },
  async execute(capability) {
    const action =
      capability === "runtime.start"
        ? "start"
        : capability === "runtime.stop"
          ? "stop"
          : capability === "runtime.restart"
            ? "restart"
            : undefined;
    if (!action || !runtimeCapabilities[action])
      return {
        ok: false,
        phase: "not-implemented",
        message: "Nicht implementiert: dafür gibt es keine Schnittstelle.",
      };
    // The cached capabilities can be up to one refresh old: ask the supervisor again right
    // before dispatching, so a request never rests on a stale permission.
    const fresh = await readRuntime();
    runtimeCapabilities = fresh.capabilities;
    if (!fresh.capabilities[action])
      return {
        ok: false,
        phase: "error",
        message: "Vom Runtime-Supervisor derzeit nicht erlaubt.",
      };
    try {
      // The result only acknowledges the request; the state shown afterwards is the
      // supervisor's next reading (the hook reloads), never an assumption made here.
      const result = await getRuntimeControl()[action]();
      return {
        ok: result.accepted,
        phase: result.accepted ? "ready" : "error",
        message: result.message,
      };
    } catch {
      return { ok: false, phase: "error", message: "Runtime-Supervisor nicht erreichbar." };
    }
  },
};
