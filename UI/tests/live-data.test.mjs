import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  mapMemoryCounts,
  mapVoiceEventSummary,
  mapLlmLatencySeries,
  mapRecentEvents,
  mapTaskPlannerStatus,
} from "../src/lib/jarvis/live-data.ts";

describe("mapLlmLatencySeries", () => {
  it("keeps measured hourly latency and drops empty or invalid buckets", () => {
    const points = mapLlmLatencySeries([
      { bucket_start: 1790402400, interactions: 26, avg_latency: 5274.84 },
      { bucket_start: 1790406000, interactions: 0, avg_latency: 4129.78 },
      { bucket_start: 1790413200, interactions: 1, avg_latency: Number.NaN },
      { bucket_start: Number.NaN, interactions: 1, avg_latency: 2541.46 },
    ]);

    assert.equal(points.length, 1);
    assert.equal(points[0].primary, 5274.84);
    assert.match(points[0].time, /\d{2}/);
  });
});

describe("mapMemoryCounts", () => {
  it("does not treat the backend's zero fallback as an active ContextWindow", () => {
    const counts = mapMemoryCounts({
      stats: { memory: null, context_window: null },
      summary: { context: { usage_pct: 0, segments: 0, estimated_tokens: 0 } },
      webAvailable: true,
    });

    assert.equal(counts, undefined);
  });

  it("keeps ContextWindow metrics when it is active without a Memory-Manager", () => {
    const counts = mapMemoryCounts({
      stats: { memory: null, context_window: { usage_pct: 2.1 } },
      summary: {
        context: { usage_pct: 2.1, segments: 40, estimated_tokens: 501 },
      },
      webAvailable: true,
    });

    assert.deepEqual(counts, {
      facts: null,
      vectors: null,
      contextSegments: 40,
      contextTokens: 501,
      contextUsagePercent: 2.1,
    });
  });

  it("does not publish context fallback zeros when the summary reports an error", () => {
    const counts = mapMemoryCounts({
      stats: { memory: null, context_window: { usage_pct: 1 } },
      summary: { context: { error: "unavailable", usage_pct: 0, segments: 0 } },
      webAvailable: true,
    });

    assert.equal(counts, undefined);
  });
});

describe("mapVoiceEventSummary", () => {
  it("does not report STT/TTS performance when the time window has no samples", () => {
    const summary = mapVoiceEventSummary(
      { total: 0, empty: 0, errors: 0, success_rate: 0 },
      {
        total_syntheses: 0,
        cache_hits: 0,
        cache_hit_rate: 0,
        avg_generation_s: 0,
        avg_rtf: 0,
        avg_ttfc_s: 0,
        data_points: [],
      },
    );

    assert.equal(summary.stt?.successRate, null);
    assert.equal(summary.tts?.cacheHits, null);
    assert.equal(summary.tts?.cacheHitRate, null);
    assert.equal(summary.tts?.avgGenerationSeconds, null);
    assert.equal(summary.tts?.avgRealTimeFactor, null);
    assert.equal(summary.tts?.avgTimeToFirstChunkSeconds, null);
  });

  it("preserves cache-only traffic and derives averages only from event samples", () => {
    const summary = mapVoiceEventSummary(undefined, {
      total_syntheses: 0,
      cache_hits: 4,
      cache_hit_rate: 100,
      avg_generation_s: 0,
      avg_rtf: 0,
      avg_ttfc_s: 0,
      data_points: [
        { generation_time_s: 1.2, rtf: 0.4, ttfc_s: 0.2 },
        { generation_time_s: null, rtf: null, ttfc_s: null },
      ],
    });

    assert.equal(summary.tts?.cacheHits, 4);
    assert.equal(summary.tts?.cacheHitRate, 100);
    assert.equal(summary.tts?.avgGenerationSeconds, 1.2);
    assert.equal(summary.tts?.avgRealTimeFactor, 0.4);
    assert.equal(summary.tts?.avgTimeToFirstChunkSeconds, 0.2);
  });
});

describe("mapRecentEvents", () => {
  it("projects source timestamps newest first and ignores private payload fields", () => {
    const now = Date.now();
    const rows = mapRecentEvents(
      {
        hours: 24,
        limit: 100,
        private: "PRIVATE_TOP_LEVEL_SENTINEL",
        events: [
          {
            timestamp: new Date(now - 60_000).toISOString(),
            category: "decision",
            event: "route_selected",
            severity: "info",
            message: "PRIVATE_MESSAGE_SENTINEL",
            metadata: { prompt: "PRIVATE_METADATA_SENTINEL" },
            id: "PRIVATE_IDENTIFIER_SENTINEL",
          },
          {
            timestamp: new Date(now).toISOString(),
            category: "error_recovery",
            event: "runtime_restart_failed",
            severity: "error",
            message: "PRIVATE_MESSAGE_SENTINEL",
          },
        ],
      },
      now,
    );

    assert.equal(rows.length, 2);
    assert.equal(rows[0].event, "runtime_restart_failed");
    assert.equal(rows[0].severity, "error");
    assert.equal(rows[0].timestamp, new Date(now).toISOString());
    assert.equal(rows[1].event, "route_selected");
    assert.equal(rows[1].category, "decision");
    assert.ok(
      rows.every(
        (row) =>
          !JSON.stringify(row).includes("PRIVATE_") &&
          Object.keys(row).sort().join(",") === "category,event,severity,timestamp",
      ),
    );
  });

  it("bounds and sanitizes identifiers, rejects invalid timestamps, and handles empty or unavailable sources", () => {
    const now = Date.now();
    const rows = mapRecentEvents(
      {
        events: [
          {
            timestamp: new Date(now).toISOString(),
            category: "PRIVATE_CATEGORY",
            event: "PRIVATE_EVENT!",
            severity: "PRIVATE_SEVERITY",
          },
          {
            timestamp: "not-a-timestamp",
            category: "performance",
            event: "measurement_recorded",
            severity: "debug",
          },
          {
            timestamp: new Date(now - 1000).toISOString(),
            category: "learning",
            event: "x".repeat(81),
            severity: "fatal",
          },
          ...Array.from({ length: 105 }, (_, index) => ({
            timestamp: new Date(now - index - 2000).toISOString(),
            category: "performance",
            event: `metric_${index}`,
            severity: "trace",
          })),
        ],
      },
      now,
    );

    assert.equal(rows.length, 100);
    assert.equal(rows[0].event, "unknown");
    assert.equal(rows[0].category, "unknown");
    assert.equal(rows[0].severity, "unknown");
    assert.ok(rows.every((row) => row.event.length <= 80 && !row.event.includes("PRIVATE_")));
    assert.deepEqual(mapRecentEvents({ events: [] }), []);
    assert.deepEqual(mapRecentEvents(undefined), []);
  });
});

describe("mapTaskPlannerStatus", () => {
  it("projects only the live task-planner contract and drops plan or request content", () => {
    const observedAt = new Date().toISOString();
    const status = mapTaskPlannerStatus({
      available: true,
      state: "running",
      active: true,
      paused: false,
      awaitingConfirmation: false,
      canPause: true,
      stepCount: 3,
      completedSteps: 1,
      runningSteps: 1,
      failedSteps: 0,
      pendingSteps: 1,
      skippedSteps: 0,
      observedAt,
      original_request: "PRIVATE_REQUEST_SENTINEL",
      step_text: "PRIVATE_STEP_SENTINEL",
    });

    assert.equal(status?.state, "running");
    assert.equal(status?.pendingSteps, 1);
    assert.equal(status?.observedAt, observedAt);
    assert.ok(!JSON.stringify(status).includes("PRIVATE_"));
    assert.equal(Object.keys(status ?? {}).length, 13);
  });

  it("rejects malformed, inconsistent, or stale-contract planner snapshots", () => {
    const base = {
      available: true,
      state: "idle",
      active: false,
      paused: false,
      awaitingConfirmation: false,
      canPause: false,
      stepCount: 0,
      completedSteps: 0,
      runningSteps: 0,
      failedSteps: 0,
      pendingSteps: 0,
      skippedSteps: 0,
      observedAt: new Date().toISOString(),
    };

    assert.equal(mapTaskPlannerStatus({ ...base, state: "unknown" }), undefined);
    assert.equal(mapTaskPlannerStatus({ ...base, available: "true" }), undefined);
    assert.equal(mapTaskPlannerStatus({ ...base, stepCount: -1 }), undefined);
    assert.equal(mapTaskPlannerStatus({ ...base, stepCount: 1, pendingSteps: 2 }), undefined);
    assert.equal(mapTaskPlannerStatus({ ...base, observedAt: "not-a-time" }), undefined);
    assert.equal(mapTaskPlannerStatus(undefined), undefined);
  });
});
