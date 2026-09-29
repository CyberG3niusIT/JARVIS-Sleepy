"""Web app construction contracts that must work in the configured runtime."""

from pathlib import Path
from types import SimpleNamespace
import asyncio
import json
import sqlite3
import threading
import time

from aiohttp.web_urldispatcher import StaticResource
import pytest


@pytest.mark.parametrize(
    ("configured", "tls_enabled", "expected"),
    [
        ("${JARVIS_WEB_AUTH_TOKEN}", False, ""),
        ("${JARVIS_WEB_AUTH_TOKEN}", True, ""),
        ("local-test-token", True, "local-test-token"),
        ("", True, ""),
    ],
)
def test_web_auth_token_does_not_treat_unresolved_env_placeholder_as_a_secret(
    configured, tls_enabled, expected
):
    import jarvis_web

    values = {
        "web.auth_token": configured,
        "web.tls": {"enabled": tls_enabled},
    }
    config = SimpleNamespace(
        get=lambda key, default=None: values.get(key, default)
    )
    assert jarvis_web._configured_web_auth_token(config) == expected


@pytest.mark.parametrize("configured", ["${JARVIS_WEB_AUTH_TOKEN}", ""])
def test_missing_web_token_rejects_public_https_configuration(tmp_path, configured):
    import jarvis_web

    cert = tmp_path / "tls.crt"
    key = tmp_path / "tls.key"
    cert.touch()
    key.touch()
    values = {
        "web.auth_token": configured,
        "web.tls": {"enabled": True, "cert": str(cert), "key": str(key)},
    }
    config = SimpleNamespace(get=lambda name, default=None: values.get(name, default))

    with pytest.raises(RuntimeError, match="must be configured when HTTPS is enabled"):
        jarvis_web._configured_web_auth_token(config)


def test_generated_image_route_uses_configured_output_directory(tmp_path, monkeypatch):
    import core.tool_registry
    import jarvis_web

    tool_images = tmp_path / "tool-images"
    flux_images = tmp_path / "flux-images"
    monkeypatch.setattr(core.tool_registry, "get_images_dir", lambda: str(tool_images))
    config = SimpleNamespace(
        get=lambda key, default=None: str(flux_images)
        if key == "image_generation.output_dir"
        else default
    )

    app = jarvis_web.create_app(config)

    generated_resource = next(
        resource
        for resource in app.router.resources()
        if isinstance(resource, StaticResource) and resource.canonical == "/generated"
    )
    assert Path(generated_resource._directory) == flux_images.resolve()
    assert flux_images.is_dir()
    assert tool_images.is_dir()


def test_desktop_snapshot_contains_allowlisted_config_and_live_capability_names():
    import jarvis_web

    values = {
        "audio.sample_rate": 16000,
        "audio.channels": 1,
        "audio.output_backend": "windows",
        "llm.primary.provider": "gemma",
        "llm.primary.context_size": 8192,
        "llm.primary.gpu_layers": 999,
        "llm.primary.temperature": 0.7,
        "llm.primary.tool_calling": True,
        "metrics.retention_days": 180,
        "conversational_memory.enabled": True,
        "conversational_memory.proactive_surfacing": True,
        "context_window.enabled": True,
        "conversational_memory.db_path": "/home/alex/jarvis-data/data/memory.db",
        "system.language": "de-DE",
        "system.wake_word": "aura",
        "stt.backend": "qwen3",
        "stt.qwen3.num_threads": 6,
        "tts.engine": "chatterbox",
        "llm.primary.model_path": "/must/not/be/exposed.gguf",
        "llm.api.api_key_env": "SECRET_ENV_REFERENCE",
    }
    config = SimpleNamespace(get=lambda key, default=None: values.get(key, default))

    class Skill:
        name = "Wetter"
        category = "environment"
        description = "Wetterfragen"
        enabled = True
        intents = {"weather": object()}
        tools = {}

    class SkillManager:
        def list_skills(self):
            return ["weather"]

        def get_skill(self, name):
            return Skill()

    class ReminderManager:
        def list_reminders(self, **kwargs):
            raise AssertionError("desktop snapshot must not query unscoped reminders")

    snapshot = jarvis_web._desktop_snapshot(
        config,
        {
            "skill_manager": SkillManager(),
            "reminder_manager": ReminderManager(),
            "calendar_manager": None,
        },
    )

    assert snapshot["voice"]["sampleRate"] == 16000
    assert snapshot["voice"]["sttBackend"] == "qwen3"
    assert snapshot["llm"]["provider"] == "gemma"
    assert snapshot["llm"]["contextSize"] == 8192
    assert snapshot["llm"]["toolCalling"] is True
    assert snapshot["metricsRetentionDays"] == 180
    assert snapshot["memoryConfig"] == {
        "enabled": True,
        "proactiveSurfacing": True,
        "contextWindowEnabled": True,
    }
    assert snapshot["skills"] == [
        {
            "id": "weather",
            "name": "Wetter",
            "category": "environment",
            "description": "Wetterfragen",
            "enabled": True,
            "intents": 1,
            "tools": 0,
        }
    ]
    assert snapshot["capabilities"]["pendingReminders"] is None
    assert snapshot["capabilities"]["pendingRemindersScoped"] is False
    serialized = str(snapshot)
    assert "must/not/be/exposed" not in serialized
    assert "SECRET_ENV_REFERENCE" not in serialized
    assert "private reminder" not in serialized
    assert "/home/alex/jarvis-data/data/metrics.db" not in serialized
    assert "/home/alex/jarvis-data/data/memory.db" not in serialized


def test_desktop_routes_are_registered(tmp_path, monkeypatch):
    import core.tool_registry
    import jarvis_web

    output_dir = tmp_path / "generated"
    monkeypatch.setattr(core.tool_registry, "get_images_dir", lambda: str(output_dir))
    config = SimpleNamespace(
        get=lambda key, default=None: str(output_dir)
        if key == "image_generation.output_dir"
        else default
    )
    app = jarvis_web.create_app(config)

    registered_routes = {
        (route.method, route.resource.canonical)
        for route in app.router.routes()
    }
    assert ("GET", "/api/desktop/live") in registered_routes
    assert ("GET", "/api/desktop/snapshot") in registered_routes


def test_desktop_live_route_samples_each_request_without_cache(monkeypatch):
    import jarvis_web

    class Sampler:
        def __init__(self):
            self.sample_count = 0

        def sample(self):
            self.sample_count += 1
            return {
                "observedAt": f"2026-09-27T00:00:0{self.sample_count}+00:00",
                "source": "JARVIS-Host (Linux/WSL)",
                "cpuPercent": None if self.sample_count == 1 else 22.5,
                "memoryPercent": 41.5 + self.sample_count,
                "memoryUsedBytes": 415 + self.sample_count,
                "memoryTotalBytes": 1000,
                "sampleIntervalSeconds": None if self.sample_count == 1 else 1.0,
            }

    monkeypatch.setattr(jarvis_web, "LiveTelemetrySampler", Sampler)
    request = SimpleNamespace(app={})

    first_response = asyncio.run(jarvis_web.desktop_live_handler(request))
    second_response = asyncio.run(jarvis_web.desktop_live_handler(request))
    first_payload = json.loads(first_response.text)
    second_payload = json.loads(second_response.text)
    sampler = request.app["desktop_live_sampler"]

    assert first_response.status == second_response.status == 200
    assert first_response.headers["Cache-Control"] == second_response.headers["Cache-Control"] == "no-store"
    assert sampler.sample_count == 2
    assert first_payload["cpuPercent"] is None
    assert second_payload["cpuPercent"] == 22.5
    assert first_payload["observedAt"] != second_payload["observedAt"]
    assert first_payload["memoryUsedBytes"] != second_payload["memoryUsedBytes"]


def test_desktop_live_route_reports_sampling_failure_without_fake_values(monkeypatch):
    import jarvis_web

    class BrokenSampler:
        def sample(self):
            raise OSError("host telemetry unavailable")

    monkeypatch.setattr(jarvis_web, "LiveTelemetrySampler", BrokenSampler)
    request = SimpleNamespace(app={})

    response = asyncio.run(jarvis_web.desktop_live_handler(request))

    assert response.status == 503
    assert json.loads(response.text) == {"error": "Live-Telemetrie nicht verfügbar"}
    assert "cpuPercent" not in response.text


def test_events_aggregate_returns_counts_without_observation_content(tmp_path, monkeypatch):
    import jarvis_web

    db_path = tmp_path / "events.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE observations (timestamp REAL, severity TEXT, category TEXT, message TEXT)"
    )
    conn.executemany(
        "INSERT INTO observations VALUES (?, ?, ?, ?)",
        [
            (time.time(), "error", "error_recovery", "PRIVATE_EVENT_CONTENT"),
            (time.time(), "warn", "inference", "PRIVATE_TRANSCRIPT_CONTENT"),
            (time.time() - 9 * 86400, "fatal", "memory", "OLD_PRIVATE_CONTENT"),
        ],
    )
    conn.commit()
    conn.close()

    class EventLogger:
        _db_lock = threading.Lock()

        def _get_conn(self):
            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            return connection

    monkeypatch.setattr("core.event_logger.get_event_logger", lambda: EventLogger())

    class Request:
        query = {"hours": "24"}

    response = asyncio.run(jarvis_web.events_aggregate_handler(Request()))
    payload = json.loads(response.text)
    assert payload == {
        "hours": 24.0,
        "total": 2,
        "severities": {"error": 1, "warn": 1},
        "categories": {"error_recovery": 1, "inference": 1},
    }
    assert "PRIVATE_" not in response.text
    assert "OLD_PRIVATE_CONTENT" not in response.text


def test_events_recent_returns_bounded_newest_first_safe_projection(tmp_path, monkeypatch):
    import jarvis_web

    db_path = tmp_path / "events.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE observations (timestamp REAL, category TEXT, event TEXT, severity TEXT, "
        "id TEXT, session_id TEXT, speaker_id TEXT, message TEXT, metadata TEXT, stage TEXT, "
        "status TEXT, model TEXT, latency_ms REAL)"
    )
    conn.executemany(
        "INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (time.time() - 3, "performance", "turn_latency", "info", "ID_PRIVATE", "SESSION_PRIVATE",
             "SPEAKER_PRIVATE", "MESSAGE_PRIVATE", "METADATA_PRIVATE", "STAGE_PRIVATE",
             "STATUS_PRIVATE", "MODEL_PRIVATE", 12.5),
            (time.time() - 1, "inference", "llm_call", "warn", "ID_PRIVATE", "SESSION_PRIVATE",
             "SPEAKER_PRIVATE", "MESSAGE_PRIVATE", "METADATA_PRIVATE", "STAGE_PRIVATE",
             "STATUS_PRIVATE", "MODEL_PRIVATE", 12.5),
            (time.time() - 9 * 86400, "old", "old_event", "error", "ID_PRIVATE", "SESSION_PRIVATE",
             "SPEAKER_PRIVATE", "MESSAGE_PRIVATE", "METADATA_PRIVATE", "STAGE_PRIVATE",
             "STATUS_PRIVATE", "MODEL_PRIVATE", 12.5),
        ],
    )
    conn.commit()
    conn.close()

    class EventLogger:
        _db_lock = threading.Lock()

        def _get_conn(self):
            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            return connection

    monkeypatch.setattr("core.event_logger.get_event_logger", lambda: EventLogger())

    class Request:
        query = {"hours": "24", "limit": "1"}

    response = asyncio.run(jarvis_web.events_recent_handler(Request()))
    payload = json.loads(response.text)

    assert response.status == 200
    assert payload["hours"] == 24.0
    assert payload["limit"] == 1
    assert len(payload["events"]) == 1
    assert payload["events"][0]["event"] == "llm_call"
    assert set(payload["events"][0]) == {"timestamp", "category", "event", "severity"}
    assert all(secret not in response.text for secret in (
        "ID_PRIVATE", "SESSION_PRIVATE", "SPEAKER_PRIVATE", "MESSAGE_PRIVATE",
        "METADATA_PRIVATE", "STAGE_PRIVATE", "STATUS_PRIVATE", "MODEL_PRIVATE",
    ))


@pytest.mark.parametrize("query", [
    {"hours": "0"}, {"hours": "169"}, {"hours": "invalid"},
    {"limit": "0"}, {"limit": "201"}, {"limit": "invalid"},
])
def test_events_recent_rejects_out_of_range_query_values(monkeypatch, query):
    import jarvis_web

    class Request:
        pass

    request = Request()
    request.query = query
    monkeypatch.setattr("core.event_logger.get_event_logger", lambda: object())

    response = asyncio.run(jarvis_web.events_recent_handler(request))

    assert response.status == 400
    assert json.loads(response.text) == {"error": "Invalid hours or limit"}


def test_events_recent_normalizes_unrecognized_values(tmp_path, monkeypatch):
    import jarvis_web

    db_path = tmp_path / "events.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE observations (timestamp REAL, category TEXT, event TEXT, severity TEXT)")
    conn.execute(
        "INSERT INTO observations VALUES (?, ?, ?, ?)",
        (time.time(), "unregistered category", "privateaccountid123", "unregistered severity"),
    )
    conn.commit()
    conn.close()

    class EventLogger:
        _db_lock = threading.Lock()

        def _get_conn(self):
            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            return connection

    monkeypatch.setattr("core.event_logger.get_event_logger", lambda: EventLogger())

    class Request:
        query = {"hours": "24", "limit": "10"}

    response = asyncio.run(jarvis_web.events_recent_handler(Request()))

    assert json.loads(response.text)["events"] == [{
        "timestamp": pytest.approx(time.time(), abs=5),
        "category": "unknown",
        "event": "unknown",
        "severity": "unknown",
    }]


def test_events_recent_route_is_registered(tmp_path, monkeypatch):
    import core.tool_registry
    import jarvis_web

    output_dir = tmp_path / "generated"
    monkeypatch.setattr(core.tool_registry, "get_images_dir", lambda: str(output_dir))
    config = SimpleNamespace(get=lambda key, default=None: str(output_dir)
                             if key == "image_generation.output_dir" else default)
    app = jarvis_web.create_app(config)

    assert ("GET", "/api/events/recent") in {
        (route.method, route.resource.canonical) for route in app.router.routes()
    }


def test_agent_and_automation_status_routes_are_registered(tmp_path, monkeypatch):
    import core.tool_registry
    import jarvis_web

    output_dir = tmp_path / "generated"
    monkeypatch.setattr(core.tool_registry, "get_images_dir", lambda: str(output_dir))
    config = SimpleNamespace(get=lambda key, default=None: str(output_dir)
                             if key == "image_generation.output_dir" else default)
    app = jarvis_web.create_app(config)
    registered_routes = {(route.method, route.resource.canonical)
                         for route in app.router.routes()}

    assert ("GET", "/api/agents/status") in registered_routes
    assert ("GET", "/api/automations/status") in registered_routes


@pytest.mark.parametrize(
    ("plan_status", "step_statuses", "paused", "pending_confirmation", "expected_state"),
    [
        ("pending", ["pending", "completed", "skipped"], False, False, "pending"),
        ("running", ["running", "completed", "failed", "pending"], False, False, "running"),
        ("running", ["running"], True, False, "paused"),
        ("completed", ["completed", "completed"], False, False, "completed"),
        ("failed", ["failed", "completed"], False, False, "failed"),
        ("cancelled", ["skipped", "completed"], False, False, "cancelled"),
        (None, [], False, True, "awaiting_confirmation"),
        (None, [], False, False, "idle"),
    ],
)
def test_agents_status_returns_only_fixed_privacy_safe_plan_projection(
    plan_status, step_statuses, paused, pending_confirmation, expected_state
):
    import jarvis_web

    class Planner:
        is_active = plan_status == "running" and not paused
        is_paused = paused
        has_pending_confirmation = pending_confirmation
        can_pause = True
        active_plan = None
        _pending_plan_confirmation = None

    planner = Planner()
    if plan_status is not None:
        planner.active_plan = SimpleNamespace(
            status=SimpleNamespace(value=plan_status),
            steps=[SimpleNamespace(status=SimpleNamespace(value=status))
                   for status in step_statuses],
            original_request="SECRET_REQUEST_SENTINEL",
            description="SECRET_PLAN_DESCRIPTION_SENTINEL",
        )
    if pending_confirmation:
        planner._pending_plan_confirmation = SimpleNamespace(
            steps=[SimpleNamespace(
                status=SimpleNamespace(value="pending"),
                description="SECRET_STEP_DESCRIPTION_SENTINEL",
                skill_name="SECRET_SKILL_SENTINEL",
                input_text="SECRET_INPUT_SENTINEL",
                result="SECRET_RESULT_SENTINEL",
            )],
            original_request="SECRET_CONFIRMATION_SENTINEL",
        )

    response = asyncio.run(jarvis_web.agents_status_handler(
        SimpleNamespace(app={"components": {"task_planner": planner}})
    ))
    payload = json.loads(response.text)

    assert response.status == 200
    assert set(payload) == {
        "available", "state", "active", "paused", "awaitingConfirmation",
        "canPause", "stepCount", "completedSteps", "runningSteps",
        "failedSteps", "pendingSteps", "skippedSteps", "observedAt",
    }
    assert payload["available"] is True
    assert payload["state"] == expected_state
    assert payload["active"] is (plan_status == "running" and not paused)
    assert payload["paused"] is paused
    assert payload["awaitingConfirmation"] is pending_confirmation
    assert payload["canPause"] is True
    counted_steps = step_statuses + (["pending"] if pending_confirmation else [])
    assert payload["stepCount"] == len(counted_steps)
    assert payload["completedSteps"] == counted_steps.count("completed")
    assert payload["runningSteps"] == counted_steps.count("running")
    assert payload["failedSteps"] == counted_steps.count("failed")
    assert payload["pendingSteps"] == counted_steps.count("pending")
    assert payload["skippedSteps"] == counted_steps.count("skipped")
    for secret in ("SECRET_REQUEST_SENTINEL", "SECRET_PLAN_DESCRIPTION_SENTINEL",
                   "SECRET_CONFIRMATION_SENTINEL", "SECRET_STEP_DESCRIPTION_SENTINEL",
                   "SECRET_SKILL_SENTINEL", "SECRET_INPUT_SENTINEL",
                   "SECRET_RESULT_SENTINEL"):
        assert secret not in response.text


def test_agents_status_reports_unavailable_without_planner_or_leaking_errors():
    import jarvis_web

    missing = asyncio.run(jarvis_web.agents_status_handler(
        SimpleNamespace(app={"components": {}})
    ))
    broken = asyncio.run(jarvis_web.agents_status_handler(
        SimpleNamespace(app={"components": {"task_planner": object()}})
    ))
    assert missing.status == 503
    missing_payload = json.loads(missing.text)
    assert missing_payload["available"] is False
    assert missing_payload["state"] == "unavailable"
    assert broken.status == 503
    assert json.loads(broken.text)["available"] is False
    assert "Traceback" not in broken.text


def test_automations_status_projects_only_safe_scheduler_metadata():
    import jarvis_web

    class Thread:
        def __init__(self, alive):
            self.alive = alive

        def is_alive(self):
            return self.alive

    class Reminder:
        _running = True
        _poll_thread = Thread(True)
        poll_interval = 17
        rundown_enabled = True
        rundown_hour = 8
        rundown_minute = 15
        weekly_rundown_enabled = False
        _weekly_day = "monday"
        reminders = [{"title": "PRIVATE_REMINDER_TITLE", "created_by": "PRIVATE_USER"}]

    class Health:
        _interval = 45

        def is_alive(self):
            return False

    class Collector:
        interval = 7200
        _thread = Thread(True)
        _last_run = 1780000000
        auto_consult = False
        _findings_history = [{"message": "PRIVATE_FINDING"}]

    response = asyncio.run(jarvis_web.automations_status_handler(SimpleNamespace(
        app={"components": {
            "reminder_manager": Reminder(),
            "health_scheduler": Health(),
            "observation_collector": Collector(),
        }}
    )))
    payload = json.loads(response.text)

    assert response.status == 200
    assert set(payload) == {"observedAt", "schedulers"}
    schedulers = {item["id"]: item for item in payload["schedulers"]}
    assert set(schedulers) == {"reminder_poller", "health_snapshot", "observation_collector"}
    assert schedulers["reminder_poller"] == {
        "id": "reminder_poller", "state": "running",
        "configuredIntervalSeconds": 17, "lastRunAt": None,
        "lastRunAvailable": False, "dailyRundownEnabled": True,
        "dailyRundownTime": "08:15", "weeklyRundownEnabled": False,
        "weeklyRundownDay": "monday",
    }
    assert schedulers["health_snapshot"] == {
        "id": "health_snapshot", "state": "stopped",
        "configuredIntervalSeconds": 45, "lastRunAt": None,
        "lastRunAvailable": False,
    }
    assert schedulers["observation_collector"] == {
        "id": "observation_collector", "state": "running",
        "configuredIntervalSeconds": 7200,
        "lastRunAt": "2026-05-28T20:26:40+00:00",
        "lastRunAvailable": True, "autoConsultEnabled": False,
    }
    assert "PRIVATE_" not in response.text


def test_automations_status_marks_missing_components_disabled_and_does_not_query_data():
    import jarvis_web

    response = asyncio.run(jarvis_web.automations_status_handler(
        SimpleNamespace(app={"components": {}})
    ))
    payload = json.loads(response.text)
    assert response.status == 200
    assert [item["state"] for item in payload["schedulers"]] == [
        "disabled", "disabled", "disabled"
    ]
    assert all(item["configuredIntervalSeconds"] is None for item in payload["schedulers"])
    assert all(item["lastRunAt"] is None and not item["lastRunAvailable"]
               for item in payload["schedulers"])


def test_automations_status_reports_configured_disabled_and_stopped_states():
    import jarvis_web

    class Thread:
        def is_alive(self):
            return False

    class Reminder:
        _running = False
        _poll_thread = Thread()
        poll_interval = 30
        rundown_enabled = False
        rundown_hour = 7
        rundown_minute = 5
        weekly_rundown_enabled = True
        _weekly_day = "friday"

    class Health(Thread):
        _interval = 600

    class Collector:
        _thread = None
        interval = 3600
        _last_run = 0
        auto_consult = True

    response = asyncio.run(jarvis_web.automations_status_handler(SimpleNamespace(
        app={"components": {
            "reminder_manager": Reminder(),
            "health_scheduler": Health(),
            "observation_collector": Collector(),
        }}
    )))
    schedulers = {item["id"]: item for item in json.loads(response.text)["schedulers"]}
    assert schedulers["reminder_poller"]["state"] == "stopped"
    assert schedulers["reminder_poller"]["dailyRundownEnabled"] is False
    assert schedulers["reminder_poller"]["dailyRundownTime"] == "07:05"
    assert schedulers["reminder_poller"]["weeklyRundownEnabled"] is True
    assert schedulers["reminder_poller"]["weeklyRundownDay"] == "friday"
    assert schedulers["health_snapshot"]["state"] == "stopped"
    assert schedulers["observation_collector"]["state"] == "stopped"
    assert schedulers["observation_collector"]["autoConsultEnabled"] is True
    assert schedulers["observation_collector"]["lastRunAt"] is None
    assert schedulers["observation_collector"]["lastRunAvailable"] is False
