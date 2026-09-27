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
  SkillCapability,
  Metric,
  RuntimeEnvelope,
  RuntimeStatus,
  RecentEventsPayload,
  StatusTone,
  VoiceEventSummary,
} from "./types";
import {
  mapLlmLatencySeries,
  mapMemoryCounts,
  mapRecentEvents,
  mapVoiceEventSummary,
} from "./live-data";

/**
 * Production adapter. Only values that a verified backend source delivers are shown; everything
 * else stays "Keine Live-Daten" / empty. Domain actions without a backend contract report
 * NOT_IMPLEMENTED; runtime lifecycle actions are handled by RuntimeControlTransport below.
 *
 * RUNTIME STATE: the backend data API has no interface that reports STARTING/READY/DEGRADED/
 * ERROR/STOPPED (only stdout/exit code of start.sh/stop.sh), and this adapter never derives one
 * from HTTP probes. Runtime state and lifecycle come solely from the RuntimeControlTransport
 * (runtime-control.ts); outside the native desktop the state is NOT_IMPLEMENTED and
 * all lifecycle capabilities are off. Reachability of single services is shown separately and
 * describes only that service's own answer.
 *
 * Verified sources (see Dokumentation/16_UI_CONTROL_HUB.md for evidence):
 *   web        GET /api/stats               jarvis_web.py:3352      reachability of jarvis_web.py, `llm.model`
 *   web        GET /api/events/aggregate    jarvis_web.py:4234      counts by severity/category -> content-free activity summary
 *   web        GET /api/events/recent       sanitized event identifiers and source timestamps -> chronological activity rows
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
  skills_loaded?: number;
  llm?: { model?: string } | null;
  memory?: { vectors?: number; proactive?: boolean } | null;
  context_window?: { usage_pct?: number } | null;
  reminders?: { active?: number } | null;
  news?: { feeds?: number } | null;
  calendar?: boolean;
  web_research?: boolean;
}
interface HealthTrendsPayload {
  trends?: Record<
    string,
    {
      stats?: {
        latest?: number | null;
        latest_ts?: number | null;
      };
      data?: { timestamp?: number; value?: number }[];
    }
  >;
}
interface MetricsSummaryPayload {
  total_interactions?: number;
  total_tokens?: number;
  avg_latency_ms?: number;
  fallback_count?: number;
  fallback_rate?: number;
  error_count?: number;
  hours?: number;
}
interface MetricsTimeseriesRow {
  bucket_start?: number;
  interactions?: number;
  prompt_tok?: number;
  completion_tok?: number;
  avg_latency?: number;
}
interface ToolsMetricsPayload {
  tools?: Record<string, number>;
  hours?: number;
}
interface MemorySummaryPayload {
  facts?: { total?: number; error?: string };
  faiss?: { vectors?: number; error?: string };
  context?: { usage_pct?: number; segments?: number; estimated_tokens?: number; error?: string };
}
interface TtsEventsPayload {
  total_syntheses?: number;
  successful_syntheses?: number;
  errors?: number;
  cache_hits?: number;
  cache_hit_rate?: number;
  avg_generation_s?: number;
  avg_rtf?: number;
  avg_ttfc_s?: number;
  data_points?: {
    generation_time_s?: number | null;
    rtf?: number | null;
    ttfc_s?: number | null;
  }[];
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
interface EventAggregatePayload {
  hours?: number;
  total?: number;
  severities?: Record<string, number>;
  categories?: Record<string, number>;
}
interface WatchdogAggregatePayload {
  total?: number;
  by_type?: Record<string, number>;
}
interface DesktopSnapshotPayload {
  llm?: {
    provider?: string | null;
    endpoint?: string | null;
    contextSize?: number | null;
    gpuLayers?: number | null;
    batchSize?: number | null;
    ubatchSize?: number | null;
    temperature?: number | null;
    topP?: number | null;
    topK?: number | null;
    toolCalling?: boolean | null;
  };
  voice?: {
    input?: string | null;
    device?: string | null;
    sampleRate?: number | null;
    channels?: number | null;
    outputBackend?: string | null;
    language?: string | null;
    wakeKeyword?: string | null;
    sttBackend?: string | null;
    sttModel?: string | null;
    sttLanguage?: string | null;
    sttProvider?: string | null;
    sttThreads?: number | null;
    tts?: string | null;
    ttsEndpoint?: string | null;
    ttsConnectTimeout?: number | null;
    ttsReadTimeout?: number | null;
    ttsWarmup?: boolean | null;
    ttsNormalization?: boolean | null;
  };
  skills?: SkillCapability[];
  tools?: {
    id: string;
    name: string;
    description: string;
    registered: boolean;
    skill: string | null;
  }[];
  capabilities?: {
    reminders?: boolean;
    pendingReminders?: number | null;
    pendingRemindersScoped?: boolean;
    calendar?: boolean;
    news?: boolean;
    weather?: boolean;
    memory?: boolean;
    contextWindow?: boolean;
    metrics?: boolean;
  };
  metricsRetentionDays?: number | null;
  memoryConfig?: {
    enabled?: boolean;
    proactiveSurfacing?: boolean;
    contextWindowEnabled?: boolean;
  };
}
interface SttEventsPayload {
  total?: number;
  empty?: number;
  errors?: number;
  success_rate?: number;
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

/** Last stored health snapshot of one metric, or undefined when the backend has none. */
function latestSnapshot(payload: HealthTrendsPayload | undefined, metric: string) {
  const stats = payload?.trends?.[metric]?.stats;
  if (!stats || typeof stats.latest !== "number") return undefined;
  return { value: stats.latest, ts: stats.latest_ts ?? undefined };
}

function healthHistory(payload: HealthTrendsPayload | undefined, metric: string) {
  return (payload?.trends?.[metric]?.data ?? []).filter(
    (point): point is { timestamp: number; value: number } =>
      typeof point.timestamp === "number" &&
      Number.isFinite(point.timestamp) &&
      typeof point.value === "number" &&
      Number.isFinite(point.value),
  );
}

function systemPerformanceHistory(payload: HealthTrendsPayload | undefined) {
  const ramByTimestamp = new Map(
    healthHistory(payload, "ram.percent").map((point) => [point.timestamp, point.value]),
  );
  return healthHistory(payload, "cpu.load").map((point) => {
    const ram = ramByTimestamp.get(point.timestamp);
    return {
      time: new Date(point.timestamp * 1000).toLocaleTimeString("de-DE", {
        hour: "2-digit",
        minute: "2-digit",
      }),
      primary: point.value,
      ...(ram !== undefined ? { secondary: ram } : {}),
    };
  });
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

function toAggregateActivities(payload: EventAggregatePayload): Activity[] {
  const rows: Activity[] = [];
  for (const [severity, count] of Object.entries(payload.severities ?? {})) {
    if (!Number.isFinite(count) || count < 0) continue;
    rows.push({
      id: `aggregate-severity-${severity}`,
      time: `letzte ${payload.hours ?? 24} h`,
      source: "Ereignis-Aggregat",
      level:
        severity === "fatal" || severity === "error"
          ? "Fehler"
          : severity === "warn"
            ? "Warnung"
            : "Info",
      message: `${count} Ereignisse mit Severity „${severity}“`,
      context: "Zeitfenster · aggregiert",
    });
  }
  for (const [category, count] of Object.entries(payload.categories ?? {})) {
    if (!Number.isFinite(count) || count < 0) continue;
    rows.push({
      id: `aggregate-category-${category}`,
      time: `letzte ${payload.hours ?? 24} h`,
      source: "Ereignis-Kategorie",
      level: "Info",
      message: `${count} Ereignisse in „${category}“`,
      context: "aggregiert · ohne Ereignistext",
    });
  }
  return rows;
}

/** Uses only the content-free breakdown from /api/events/watchdog, never its event messages. */
function toWatchdogActivities(payload: WatchdogAggregatePayload): Activity[] {
  return Object.entries(payload.by_type ?? {})
    .filter(([, count]) => Number.isFinite(count) && count >= 0)
    .sort((left, right) => right[1] - left[1])
    .slice(0, 12)
    .map(([type, count]) => ({
      id: `watchdog-type-${type}`,
      time: "letzte 24 h",
      source: "Watchdog · aggregiert",
      level: "Info",
      message: `${count} Watchdog-Ereignisse vom Typ „${type}“`,
      context: "aggregiert · Ereignistexte nicht geladen",
    }));
}

const modelName = (id: string) => id.split(/[\\/]/).pop() || id;
const formatParams = (n: number) =>
  `${(n / 1e9).toLocaleString("de-DE", { maximumFractionDigits: 1 })} Mrd.`;

let runtimeCapabilities: RuntimeControlCapabilities = { start: false, stop: false, restart: false };

// Keep a small margin above the Rust host's hard 10-second child-process timeout.
const supervisorTimeoutMs = 12_000;

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
  const [
    health,
    memory,
    llmSummary,
    desktop,
    sttEvents,
    ttsEvents,
    toolMetrics,
    eventAggregate,
    recentEvents,
    llmTimeseries,
  ] = web.ok
    ? await Promise.all([
        probe<HealthTrendsPayload>(
          "web",
          "/api/events/health?hours=24&metrics=cpu.load,ram.percent",
        ),
        probe<MemorySummaryPayload>("web", "/api/memory/summary"),
        probe<MetricsSummaryPayload>("web", "/api/metrics/summary?hours=24"),
        probe<DesktopSnapshotPayload>("web", "/api/desktop/snapshot"),
        probe<SttEventsPayload>("web", "/api/events/stt?hours=24"),
        probe<TtsEventsPayload>("web", "/api/events/tts?hours=24"),
        probe<ToolsMetricsPayload>("web", "/api/metrics/tools?hours=24"),
        probe<EventAggregatePayload>("web", "/api/events/aggregate?hours=24"),
        probe<RecentEventsPayload>("web", "/api/events/recent?hours=24&limit=100"),
        probe<MetricsTimeseriesRow[]>("web", "/api/metrics/timeseries?hours=24&bucket=hour"),
      ])
    : [
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
      ];
  const watchdog =
    web.ok && eventAggregate && !eventAggregate.ok
      ? await probe<WatchdogAggregatePayload>("web", "/api/events/watchdog?hours=24")
      : undefined;
  const runtimeReading = await runtimePromise;
  runtimeCapabilities = runtimeReading.capabilities;
  const healthPayload = health?.ok ? health.value : undefined;
  const healthAnswered = health?.ok === true;
  // /api/memory/summary answers total 0 without an error when no memory manager exists;
  // /api/stats reports memory: null in that case, so only trust the counts when it is set.
  const memoryReady =
    web.ok && web.value.memory != null && memory?.ok && !memory.value.facts?.error;
  const memoryContextReady =
    web.ok &&
    web.value.context_window != null &&
    memory?.ok &&
    memory.value.context != null &&
    !memory.value.context.error;
  const desktopData = desktop?.ok ? desktop.value : undefined;
  const configuredLlm = desktopData?.llm;
  const configuredVoice = desktopData?.voice;
  const voiceEvents: VoiceEventSummary = mapVoiceEventSummary(
    sttEvents?.ok ? sttEvents.value : undefined,
    ttsEvents?.ok ? ttsEvents.value : undefined,
  );
  const mappedMemoryCounts = mapMemoryCounts({
    ...(web.ok ? { stats: web.value } : {}),
    ...(memory?.ok ? { summary: memory.value } : {}),
    webAvailable: web.ok,
  });
  const systemHistory = systemPerformanceHistory(healthPayload);
  const llmPerformance =
    llmTimeseries?.ok && Array.isArray(llmTimeseries.value)
      ? mapLlmLatencySeries(llmTimeseries.value)
      : [];
  const recentActivities = recentEvents?.ok ? mapRecentEvents(recentEvents.value) : [];

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
      // GPU readings may fall back to zero in the backend health check; do not present as live.
      { label: "GPU", value: unavailable, detail: "Backend-Wert nicht eindeutig" },
      snapshotMetric("RAM", healthPayload, "ram.percent", "Belegung", healthAnswered),
      { label: "VRAM", value: unavailable, detail: "Backend-Wert nicht eindeutig" },
      { label: "Netzwerk", value: unavailable, detail: "Keine Schnittstelle im Backend" },
      { label: "Aktive Agenten", value: unavailable, detail: "Keine Agenten-Schnittstelle" },
    ],
    performance: systemHistory,
    llmPerformance,
    gpuPerformance: [],
    model: {
      name: entry?.id ? modelName(entry.id) : (web.ok && web.value.llm?.model) || unavailable,
      family: unavailable,
      quantization: meta?.ftype ?? unavailable,
      context:
        meta?.n_ctx !== undefined
          ? `${meta.n_ctx} Token`
          : configuredLlm?.contextSize != null
            ? `${configuredLlm.contextSize} Token (konfiguriert)`
            : unavailable,
      parameters: meta?.n_params !== undefined ? formatParams(meta.n_params) : unavailable,
      location: entry?.id ?? unavailable,
      runtime:
        entry?.owned_by === "llamacpp" ? "llama.cpp" : (configuredLlm?.provider ?? unavailable),
      endpoint: configuredLlm?.endpoint ?? unavailable,
      gpuLayers: configuredLlm?.gpuLayers ?? null,
      batchSize: configuredLlm?.batchSize ?? null,
      ubatchSize: configuredLlm?.ubatchSize ?? null,
      temperature: configuredLlm?.temperature ?? null,
      topP: configuredLlm?.topP ?? null,
      topK: configuredLlm?.topK ?? null,
      toolCalling: configuredLlm?.toolCalling ?? null,
      status: mainReach.tone,
    },
    activities: eventAggregate?.ok
      ? toAggregateActivities(eventAggregate.value)
      : watchdog?.ok
        ? toWatchdogActivities(watchdog.value)
        : [],
    ...(recentEvents?.ok ? { recentEvents: recentActivities } : {}),
    ...(llmSummary?.ok &&
    typeof llmSummary.value.total_interactions === "number" &&
    Number.isFinite(llmSummary.value.total_interactions)
      ? {
          llmStats: {
            interactions: llmSummary.value.total_interactions,
            totalTokens:
              typeof llmSummary.value.total_tokens === "number" &&
              Number.isFinite(llmSummary.value.total_tokens)
                ? llmSummary.value.total_tokens
                : null,
            contextUsagePercent:
              web.ok &&
              typeof web.value.context_window?.usage_pct === "number" &&
              Number.isFinite(web.value.context_window.usage_pct)
                ? web.value.context_window.usage_pct
                : null,
            // get_summary() answers 0 when there are no interactions: only meaningful with data.
            avgLatencyMs:
              llmSummary.value.total_interactions > 0 &&
              typeof llmSummary.value.avg_latency_ms === "number" &&
              Number.isFinite(llmSummary.value.avg_latency_ms)
                ? llmSummary.value.avg_latency_ms
                : null,
            fallbackCount:
              typeof llmSummary.value.fallback_count === "number" &&
              Number.isFinite(llmSummary.value.fallback_count)
                ? llmSummary.value.fallback_count
                : null,
            fallbackRate:
              typeof llmSummary.value.fallback_rate === "number" &&
              Number.isFinite(llmSummary.value.fallback_rate)
                ? llmSummary.value.fallback_rate
                : null,
            errorCount:
              typeof llmSummary.value.error_count === "number" &&
              Number.isFinite(llmSummary.value.error_count)
                ? llmSummary.value.error_count
                : null,
            hours: llmSummary.value.hours ?? 24,
          },
        }
      : {}),
    ...(mappedMemoryCounts ? { memoryCounts: mappedMemoryCounts } : {}),
    agents: [],
    skills: desktopData?.skills ?? [],
    ...(desktopData?.capabilities || web.ok
      ? {
          liveFeatures: {
            skillsLoaded:
              web.ok &&
              typeof web.value.skills_loaded === "number" &&
              Number.isFinite(web.value.skills_loaded)
                ? web.value.skills_loaded
                : (desktopData?.skills?.length ?? null),
            reminders:
              desktopData?.capabilities?.reminders ?? (web.ok ? web.value.reminders != null : null),
            // /api/stats returns a process-global pending count, not a user-scoped count.
            pendingReminders: desktopData?.capabilities?.pendingReminders ?? null,
            pendingRemindersScoped: desktopData?.capabilities?.pendingRemindersScoped ?? false,
            calendar:
              desktopData?.capabilities?.calendar ??
              (web.ok && typeof web.value.calendar === "boolean" ? web.value.calendar : null),
            news: desktopData?.capabilities?.news ?? (web.ok ? web.value.news != null : null),
            newsFeeds:
              web.ok &&
              typeof web.value.news?.feeds === "number" &&
              Number.isFinite(web.value.news.feeds)
                ? web.value.news.feeds
                : null,
            webResearch:
              web.ok && typeof web.value.web_research === "boolean" ? web.value.web_research : null,
            weather: desktopData?.capabilities?.weather ?? null,
            memory: desktopData?.capabilities?.memory ?? (web.ok ? web.value.memory != null : null),
            contextWindow:
              desktopData?.capabilities?.contextWindow ??
              (web.ok ? web.value.context_window != null : null),
            metrics: desktopData?.capabilities?.metrics ?? null,
          },
        }
      : {}),
    memories: [],
    tools: (desktopData?.tools ?? []).map((tool) => ({
      id: tool.id,
      name: tool.name,
      type: "J.A.R.V.I.S-Tool",
      status: tool.registered ? "info" : "idle",
      description: tool.description || "Keine Beschreibung im Backend",
      scope: tool.skill ?? "Nicht skillgebunden",
      lastUse:
        toolMetrics?.ok && typeof toolMetrics.value.tools?.[tool.name] === "number"
          ? `Letzte 24 h: ${toolMetrics.value.tools[tool.name]} Aufrufe`
          : "Keine Live-Angabe",
      usageCount:
        toolMetrics?.ok && typeof toolMetrics.value.tools?.[tool.name] === "number"
          ? (toolMetrics.value.tools[tool.name] ?? null)
          : null,
    })),
    automations: [],
    voice: {
      input: configuredVoice?.input ?? unavailable,
      device: configuredVoice?.device ?? unavailable,
      sampleRate: configuredVoice?.sampleRate ?? null,
      channels: configuredVoice?.channels ?? null,
      outputBackend: configuredVoice?.outputBackend ?? unavailable,
      tempPath: unavailable,
      language: configuredVoice?.language ?? configuredVoice?.sttLanguage ?? unavailable,
      wakeEngine: configuredVoice?.sttBackend ?? unavailable,
      wakeKeyword: configuredVoice?.wakeKeyword ?? unavailable,
      sttBackend: configuredVoice?.sttBackend ?? unavailable,
      sttModel: configuredVoice?.sttModel ?? unavailable,
      sttRuntime: unavailable,
      sttProvider: configuredVoice?.sttProvider ?? unavailable,
      sttThreads: configuredVoice?.sttThreads ?? null,
      tts: configuredVoice?.tts ?? unavailable,
      ttsEndpoint: configuredVoice?.ttsEndpoint ?? unavailable,
      ttsConnectTimeout:
        configuredVoice?.ttsConnectTimeout == null
          ? unavailable
          : `${configuredVoice.ttsConnectTimeout} s`,
      ttsReadTimeout:
        configuredVoice?.ttsReadTimeout == null
          ? unavailable
          : `${configuredVoice.ttsReadTimeout} s`,
      ttsWarmup: configuredVoice?.ttsWarmup ?? null,
      ttsFallback: unavailable,
      ttsAlternative: unavailable,
    },
    voiceEvents,
    platform: { host: unavailable, linuxRuntime: unavailable, architecture: unavailable },
    hardware: {
      cpu: unavailable,
      gpu: unavailable,
      vramCapacity: unavailable,
      ramCapacity: unavailable,
    },
    services,
    memoryArchitecture: {
      stores: [],
      features: [
        {
          name: "Memory-Manager",
          implemented:
            desktopData?.memoryConfig?.enabled ?? (web.ok ? web.value.memory != null : null),
        },
        {
          name: "Proaktives Memory-Surfacing (konfiguriert)",
          implemented:
            desktopData?.memoryConfig?.proactiveSurfacing ??
            (web.ok && typeof web.value.memory?.proactive === "boolean"
              ? web.value.memory.proactive
              : null),
        },
        {
          name: "ContextWindow (konfiguriert)",
          implemented:
            desktopData?.memoryConfig?.contextWindowEnabled ??
            (web.ok ? web.value.context_window != null : null),
        },
      ],
    },
    // Code fact (core/privacy_gate.py exists), not runtime data; no interface to read or set it.
    privacy: { gateImplemented: true, modesImplemented: true, desktopConnected: false },
    metricsRetentionDays:
      typeof desktopData?.metricsRetentionDays === "number" &&
      Number.isFinite(desktopData.metricsRetentionDays) &&
      desktopData.metricsRetentionDays >= 0
        ? desktopData.metricsRetentionDays
        : null,
    subsystems: runtimeReading.components.map((component) => ({
      name: component.name,
      status:
        component.state === "READY"
          ? "online"
          : component.state === "DEGRADED"
            ? "warning"
            : component.state === "ERROR"
              ? "error"
              : component.state === "STOPPED" || component.state === "OFFLINE"
                ? "offline"
                : "info",
      detail: component.detail ?? component.state,
    })),
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
  // (all false without one). All non-lifecycle capabilities remain disabled until a backend
  // contract for those actions exists.
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
