import type { RecentEvent, RecentEventsPayload, TaskPlannerStatus } from "./types";

export interface MetricsTimeseriesRow {
  bucket_start?: number;
  interactions?: number;
  avg_latency?: number;
}

export interface MemoryCounts {
  facts: number | null;
  vectors: number | null;
  contextSegments: number | null;
  contextTokens: number | null;
  contextUsagePercent: number | null;
}

export interface MemoryStats {
  memory?: unknown | null;
  context_window?: unknown | null;
}

export interface MemorySummary {
  facts?: { total?: number; error?: string };
  faiss?: { vectors?: number; error?: string };
  context?: {
    usage_pct?: number;
    segments?: number;
    estimated_tokens?: number;
    error?: string;
  };
}

export interface SttEvents {
  total?: number;
  empty?: number;
  errors?: number;
  success_rate?: number;
}

export interface TtsEvents {
  total_syntheses?: number;
  errors?: number;
  cache_hits?: number;
  cache_hit_rate?: number;
  data_points?: {
    generation_time_s?: number | null;
    rtf?: number | null;
    ttfc_s?: number | null;
  }[];
}

export interface VoiceEventSummary {
  hours: number;
  stt?: {
    total: number;
    empty: number;
    errors: number;
    successRate: number | null;
  };
  tts?: {
    syntheses: number;
    errors?: number;
    cacheHits: number | null;
    cacheHitRate: number | null;
    avgGenerationSeconds: number | null;
    avgRealTimeFactor: number | null;
    avgTimeToFirstChunkSeconds: number | null;
  };
}

const eventCategories = new Set([
  "user_interaction",
  "decision",
  "inference",
  "tool_execution",
  "memory",
  "error_recovery",
  "performance",
  "self_assessment",
  "learning",
]);

function eventTimestamp(value: unknown): number | undefined {
  const epochMs =
    typeof value === "number" && Number.isFinite(value)
      ? Math.abs(value) >= 100_000_000_000
        ? value
        : value * 1000
      : typeof value === "string" && value.trim().length > 0
        ? Date.parse(value)
        : Number.NaN;
  return Number.isFinite(epochMs) && Math.abs(epochMs) <= 8.64e15 ? epochMs : undefined;
}

const eventSeverities = new Set(["trace", "debug", "info", "warn", "error", "fatal"]);

/** Projects only the sanitized fields from /api/events/recent; event labels are bounded identifiers. */
export function mapRecentEvents(
  payload: RecentEventsPayload | undefined,
  now = Date.now(),
): RecentEvent[] {
  if (!payload || !Array.isArray(payload.events)) return [];

  const rows = payload.events.flatMap((entry, index) => {
    if (entry === null || typeof entry !== "object" || Array.isArray(entry)) return [];
    const record = entry as Record<string, unknown>;
    const timestamp = eventTimestamp(record["timestamp"]);
    if (timestamp === undefined || timestamp > now + 5 * 60_000) return [];

    const candidateCategory =
      typeof record["category"] === "string" ? record["category"].toLowerCase() : "";
    const category = eventCategories.has(candidateCategory) ? candidateCategory : "unknown";
    const rawEvent = typeof record["event"] === "string" ? record["event"] : "";
    const event = /^[A-Za-z0-9_.:-]{1,80}$/.test(rawEvent) ? rawEvent : "unknown";
    const candidateSeverity =
      typeof record["severity"] === "string" ? record["severity"].toLowerCase() : "";
    const severity = eventSeverities.has(candidateSeverity)
      ? (candidateSeverity as RecentEvent["severity"])
      : "unknown";
    return [
      {
        timestamp,
        index,
        event: {
          timestamp: new Date(timestamp).toISOString(),
          category,
          event,
          severity,
        } satisfies RecentEvent,
      },
    ];
  });

  return rows
    .sort((left, right) => right.timestamp - left.timestamp || left.index - right.index)
    .slice(0, 100)
    .map(({ event }) => event);
}

const plannerStates = new Set<TaskPlannerStatus["state"]>([
  "unavailable",
  "pending",
  "running",
  "paused",
  "awaiting_confirmation",
  "completed",
  "failed",
  "cancelled",
  "idle",
]);

/** Projects only the privacy-safe planner counters; never forwards arbitrary backend fields. */
export function mapTaskPlannerStatus(payload: unknown): TaskPlannerStatus | undefined {
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) return undefined;
  const record = payload as Record<string, unknown>;
  const timestamp = eventTimestamp(record["observedAt"]);
  const state = record["state"];
  const counts = [
    record["stepCount"],
    record["completedSteps"],
    record["runningSteps"],
    record["failedSteps"],
    record["pendingSteps"],
    record["skippedSteps"],
  ];
  if (
    typeof record["available"] !== "boolean" ||
    typeof state !== "string" ||
    !plannerStates.has(state as TaskPlannerStatus["state"]) ||
    (record["available"] && state === "unavailable") ||
    (!record["available"] && state !== "unavailable") ||
    typeof record["active"] !== "boolean" ||
    typeof record["paused"] !== "boolean" ||
    typeof record["awaitingConfirmation"] !== "boolean" ||
    typeof record["canPause"] !== "boolean" ||
    timestamp === undefined ||
    timestamp > Date.now() + 5 * 60_000 ||
    counts.some(
      (value) =>
        typeof value !== "number" || !Number.isSafeInteger(value) || value < 0 || value > 1_000_000,
    )
  ) {
    return undefined;
  }
  const [stepCount, completedSteps, runningSteps, failedSteps, pendingSteps, skippedSteps] =
    counts as [number, number, number, number, number, number];
  if (completedSteps + runningSteps + failedSteps + pendingSteps + skippedSteps > stepCount)
    return undefined;
  if (
    record["active"] !== (state === "running" && !record["paused"]) ||
    (state === "paused" && record["paused"] !== true) ||
    (state === "awaiting_confirmation" && record["awaitingConfirmation"] !== true)
  )
    return undefined;

  return {
    available: record["available"],
    state: state as TaskPlannerStatus["state"],
    active: record["active"],
    paused: record["paused"],
    awaitingConfirmation: record["awaitingConfirmation"],
    canPause: record["canPause"],
    stepCount,
    completedSteps,
    runningSteps,
    failedSteps,
    pendingSteps,
    skippedSteps,
    observedAt: new Date(timestamp).toISOString(),
  };
}

export function mapLlmLatencySeries(rows: readonly MetricsTimeseriesRow[]) {
  return rows
    .filter(
      (point) =>
        typeof point.bucket_start === "number" &&
        Number.isFinite(point.bucket_start) &&
        typeof point.interactions === "number" &&
        point.interactions > 0 &&
        typeof point.avg_latency === "number" &&
        Number.isFinite(point.avg_latency),
    )
    .map((point) => ({
      time: new Date(point.bucket_start! * 1000).toLocaleString("de-DE", {
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }),
      primary: point.avg_latency!,
    }));
}

export function mapMemoryCounts(input: {
  stats?: MemoryStats | null;
  summary?: MemorySummary | null;
  webAvailable: boolean;
}): MemoryCounts | undefined {
  const memoryReady =
    input.webAvailable &&
    input.stats?.memory != null &&
    input.summary != null &&
    !input.summary.facts?.error &&
    !input.summary.faiss?.error;
  const contextReady =
    input.webAvailable &&
    input.stats?.context_window != null &&
    input.summary?.context != null &&
    !input.summary.context.error;
  if (!memoryReady && !contextReady) return undefined;

  return {
    facts: memoryReady ? (input.summary?.facts?.total ?? null) : null,
    vectors: memoryReady ? (input.summary?.faiss?.vectors ?? null) : null,
    contextSegments: contextReady ? (input.summary?.context?.segments ?? null) : null,
    contextTokens: contextReady ? (input.summary?.context?.estimated_tokens ?? null) : null,
    contextUsagePercent: contextReady ? (input.summary?.context?.usage_pct ?? null) : null,
  };
}

function meanMeasuredValue(payload: TtsEvents, metric: "generation_time_s" | "rtf" | "ttfc_s") {
  const values = (payload.data_points ?? [])
    .map((point) => point[metric])
    .filter(
      (value): value is number => typeof value === "number" && Number.isFinite(value) && value > 0,
    );
  if (values.length === 0) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

export function mapVoiceEventSummary(
  stt: SttEvents | undefined,
  tts: TtsEvents | undefined,
  hours = 24,
): VoiceEventSummary {
  return {
    hours,
    ...(typeof stt?.total === "number"
      ? {
          stt: {
            total: stt.total,
            empty: stt.empty ?? 0,
            errors: stt.errors ?? 0,
            successRate:
              stt.total > 0 && typeof stt.success_rate === "number" ? stt.success_rate : null,
          },
        }
      : {}),
    ...(typeof tts?.total_syntheses === "number"
      ? {
          tts: {
            syntheses: tts.total_syntheses,
            ...(typeof tts.errors === "number" ? { errors: tts.errors } : {}),
            cacheHits:
              tts.total_syntheses + (tts.cache_hits ?? 0) > 0 && typeof tts.cache_hits === "number"
                ? tts.cache_hits
                : null,
            cacheHitRate:
              tts.total_syntheses + (tts.cache_hits ?? 0) > 0 &&
              typeof tts.cache_hit_rate === "number"
                ? tts.cache_hit_rate
                : null,
            avgGenerationSeconds: meanMeasuredValue(tts, "generation_time_s"),
            avgRealTimeFactor: meanMeasuredValue(tts, "rtf"),
            avgTimeToFirstChunkSeconds: meanMeasuredValue(tts, "ttfc_s"),
          },
        }
      : {}),
  };
}
