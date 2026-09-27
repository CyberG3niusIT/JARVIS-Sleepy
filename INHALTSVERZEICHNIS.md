<div align="center">

# J.A.R.V.I.S

### REPOSITORY INDEX

`JARVIS Sleepy`

</div>

---

## Zweck

Dieses Dokument ist das zentrale Inhaltsverzeichnis des JARVIS-Sleepy-Repositories.

Es bildet die reale Repository-Struktur funktional ab und dient als Einstiegspunkt für Entwicklung, Review, Dokumentation und Betrieb.

> **Source of Truth:** Der Inhalt des aktuell ausgecheckten Branches hat Vorrang. Entwicklungs- und Snapshot-Branches können zusätzliche oder abweichende Dateien enthalten.

---

## Schnellnavigation

- [Projekt und Überblick](#01-projekt-und-überblick)
- [Runtime und Entry Points](#02-runtime-und-entry-points)
- [Core](#03-core)
- [Voice und Audio](#04-voice-und-audio)
- [Modelle und Inferenz](#05-modelle-und-inferenz)
- [Memory und Kontext](#06-memory-und-kontext)
- [Tools, Skills und MCP](#07-tools-skills-und-mcp)
- [Vision, Presence und Desktop](#08-vision-presence-und-desktop)
- [Governance, Privacy und Security](#09-governance-privacy-und-security)
- [Services und systemd](#10-services-und-systemd)
- [Web und bestehende UI](#11-web-und-bestehende-ui)
- [Tests und QA](#12-tests-und-qa)
- [Scripts und Betrieb](#13-scripts-und-betrieb)
- [Dokumentation](#14-dokumentation)
- [Assets, Images und Reports](#15-assets-images-und-reports)
- [Konfiguration und Dependencies](#16-konfiguration-und-dependencies)
- [GitHub und Repository-Metadaten](#17-github-und-repository-metadaten)
- [Nicht versionierte Laufzeitdaten](#18-nicht-versionierte-laufzeitdaten)

---

## 01. Projekt und Überblick

| Pfad | Zweck |
|---|---|
| [README.md](README.md) | Einstieg und Projektbeschreibung |
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | Technischer Projektüberblick |
| [CHANGELOG.md](CHANGELOG.md) | Entwicklungshistorie |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Beiträge und Entwicklungsregeln |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Verhaltensregeln |
| [SECURITY.md](SECURITY.md) | Security-Hinweise |
| [LICENSE](LICENSE) | Lizenz |
| [INHALTSVERZEICHNIS.md](INHALTSVERZEICHNIS.md) | Dieses Repository-Inhaltsverzeichnis |

---

## 02. Runtime und Entry Points

### Hauptprozesse

- [jarvis_continuous.py](jarvis_continuous.py)
- [jarvis_console.py](jarvis_console.py)
- [jarvis_web.py](jarvis_web.py)
- [mcp_server.py](mcp_server.py)

### Runtime-Steuerung

- [start.sh](start.sh)
- [stop.sh](stop.sh)
- [restart.sh](restart.sh)
- [status.sh](status.sh)
- [startup_checks.sh](startup_checks.sh)
- [start_jarvis_gpu.sh](start_jarvis_gpu.sh)
- [killswitch.sh](killswitch.sh)
- [jarvis_aliases.sh](jarvis_aliases.sh)

### Service-Dateien im Repository-Root

- [jarvis.service](jarvis.service)
- [llama-server.service](llama-server.service)
- [flux-server.service](flux-server.service)
- [jarvis-backup.service](jarvis-backup.service)
- [jarvis-backup.timer](jarvis-backup.timer)

---

## 03. Core

Zentrale Python-Implementierung:

[core/](core/)

### Conversation und Routing

- [core/conversation.py](core/conversation.py)
- [core/conversation_router.py](core/conversation_router.py)
- [core/conversation_state.py](core/conversation_state.py)
- [core/pipeline.py](core/pipeline.py)
- [core/responses.py](core/responses.py)
- [core/semantic_matcher.py](core/semantic_matcher.py)

### LLM und Modellrouting

- [core/llm_router.py](core/llm_router.py)
- [core/llm_server_client.py](core/llm_server_client.py)
- [core/gpu_swap.py](core/gpu_swap.py)

### Awareness und Systemkontext

- [core/awareness.py](core/awareness.py)
- [core/awareness_accumulator.py](core/awareness_accumulator.py)
- [core/self_awareness.py](core/self_awareness.py)
- [core/interaction_cache.py](core/interaction_cache.py)
- [core/trace_context.py](core/trace_context.py)

### Konfiguration und Logging

- [core/config.py](core/config.py)
- [core/logger.py](core/logger.py)
- [core/debug_logger.py](core/debug_logger.py)
- [core/event_logger.py](core/event_logger.py)
- [core/events.py](core/events.py)
- [core/metrics_tracker.py](core/metrics_tracker.py)
- [core/latency_tracker.py](core/latency_tracker.py)

---

## 04. Voice und Audio

### Speech-to-Text und Wake

- [core/stt.py](core/stt.py)
- [core/stt_qwen3.py](core/stt_qwen3.py)
- [core/wake_word.py](core/wake_word.py)
- [core/vad.py](core/vad.py)
- [core/continuous_listener.py](core/continuous_listener.py)
- [core/speech_chunker.py](core/speech_chunker.py)
- [core/speaker_id.py](core/speaker_id.py)
- [core/rnnoise_wrapper.py](core/rnnoise_wrapper.py)

### Text-to-Speech

- [core/tts.py](core/tts.py)
- [core/tts_cache.py](core/tts_cache.py)
- [core/tts_normalizer.py](core/tts_normalizer.py)
- [core/tts_normalizer_de.py](core/tts_normalizer_de.py)
- [tools/chatterbox_server.py](tools/chatterbox_server.py)

### Voice Training

- [voice_training/](voice_training/)
- [voice_training/prompts_de.txt](voice_training/prompts_de.txt)
- [tools/voice_training_collect.py](tools/voice_training_collect.py)
- [tools/voice_training_eval.py](tools/voice_training_eval.py)
- [tools/compare_whisper_models.py](tools/compare_whisper_models.py)

---

## 05. Modelle und Inferenz

### Lokale Inferenz

- [core/llm_router.py](core/llm_router.py)
- [core/llm_server_client.py](core/llm_server_client.py)
- [core/gpu_swap.py](core/gpu_swap.py)
- [llama-server.service](llama-server.service)
- [start_jarvis_gpu.sh](start_jarvis_gpu.sh)

### Bildgenerierung

- [services/flux_server.py](services/flux_server.py)
- [flux-server.service](flux-server.service)
- [core/tools/generate_image.py](core/tools/generate_image.py)

> Modellgewichte und große Runtime-Artefakte gehören nicht in Git.

---

## 06. Memory und Kontext

- [core/memory_manager.py](core/memory_manager.py)
- [core/context_window.py](core/context_window.py)
- [core/document_buffer.py](core/document_buffer.py)
- [core/interaction_cache.py](core/interaction_cache.py)
- [core/people_manager.py](core/people_manager.py)
- [core/user_profile.py](core/user_profile.py)
- [core/tools/recall_memory.py](core/tools/recall_memory.py)
- [scripts/backfill_memory.py](scripts/backfill_memory.py)
- [scripts/memory_snapshot.py](scripts/memory_snapshot.py)

---

## 07. Tools, Skills und MCP

### Tool-Infrastruktur

- [core/tool_registry.py](core/tool_registry.py)
- [core/tool_executor.py](core/tool_executor.py)
- [core/tool_gate.py](core/tool_gate.py)
- [core/tools/](core/tools/)
- [core/mcp_client.py](core/mcp_client.py)
- [mcp_server.py](mcp_server.py)
- [.mcp.json](.mcp.json)

### Core Tools

- [core/tools/capture_webcam.py](core/tools/capture_webcam.py)
- [core/tools/developer_tools.py](core/tools/developer_tools.py)
- [core/tools/enroll_face.py](core/tools/enroll_face.py)
- [core/tools/find_files.py](core/tools/find_files.py)
- [core/tools/generate_image.py](core/tools/generate_image.py)
- [core/tools/get_news.py](core/tools/get_news.py)
- [core/tools/get_system_info.py](core/tools/get_system_info.py)
- [core/tools/get_weather.py](core/tools/get_weather.py)
- [core/tools/manage_reminders.py](core/tools/manage_reminders.py)
- [core/tools/recall_memory.py](core/tools/recall_memory.py)
- [core/tools/take_screenshot.py](core/tools/take_screenshot.py)
- [core/tools/web_search.py](core/tools/web_search.py)

### Skills

[skills/](skills/)

#### Personal

- [skills/personal/conversation/](skills/personal/conversation/)
- [skills/personal/news/](skills/personal/news/)
- [skills/personal/reminders/](skills/personal/reminders/)
- [skills/personal/social_introductions/](skills/personal/social_introductions/)

#### System

- [skills/system/app_launcher/](skills/system/app_launcher/)
- [skills/system/developer_tools/](skills/system/developer_tools/)
- [skills/system/file_editor/](skills/system/file_editor/)
- [skills/system/filesystem/](skills/system/filesystem/)
- [skills/system/privacy/](skills/system/privacy/)
- [skills/system/system_info/](skills/system/system_info/)
- [skills/system/time_info/](skills/system/time_info/)
- [skills/system/weather/](skills/system/weather/)
- [skills/system/web_navigation/](skills/system/web_navigation/)

---

## 08. Vision, Presence und Desktop

### Vision und Kamera

- [core/webcam_manager.py](core/webcam_manager.py)
- [core/webcam_server.py](core/webcam_server.py)
- [core/presence_detector.py](core/presence_detector.py)
- [core/tools/capture_webcam.py](core/tools/capture_webcam.py)
- [core/tools/enroll_face.py](core/tools/enroll_face.py)

### Desktop-Integration

- [core/desktop_manager.py](core/desktop_manager.py)
- [extensions/](extensions/)
- [extensions/jarvis-desktop@jarvis/extension.js](extensions/jarvis-desktop@jarvis/extension.js)
- [extensions/jarvis-desktop@jarvis/metadata.json](extensions/jarvis-desktop@jarvis/metadata.json)
- [scripts/install_desktop_extension.sh](scripts/install_desktop_extension.sh)

---

## 09. Governance, Privacy und Security

### Privacy

- [core/privacy_gate.py](core/privacy_gate.py)
- [core/privacy_control_watcher.py](core/privacy_control_watcher.py)
- [skills/system/privacy/](skills/system/privacy/)
- [SECURITY.md](SECURITY.md)

### Governance

- [core/governance.py](core/governance.py)
- [governance/](governance/)
- [governance/commandments.md](governance/commandments.md)
- [scripts/jarvis-governance-setup](scripts/jarvis-governance-setup)
- [scripts/jarvis-approve](scripts/jarvis-approve)
- [scripts/jarvis-confirm](scripts/jarvis-confirm)
- [scripts/jarvis-circuit-reset](scripts/jarvis-circuit-reset)

### Self-Assessment

- [core/observation_collector.py](core/observation_collector.py)
- [core/modification_engine.py](core/modification_engine.py)

---

## 10. Services und systemd

### Services

- [services/](services/)
- [services/flux_server.py](services/flux_server.py)

### systemd

- [systemd/](systemd/)
- [systemd/README.md](systemd/README.md)
- [systemd/jarvis.service](systemd/jarvis.service)
- [systemd/llama-server.service](systemd/llama-server.service)
- [systemd/chatterbox.service](systemd/chatterbox.service)

---

## 11. Web und bestehende UI

[web/](web/)

### Hauptoberfläche

- [web/index.html](web/index.html)
- [web/app.js](web/app.js)
- [web/style.css](web/style.css)

### Dashboards

- [web/dashboard.html](web/dashboard.html)
- [web/dashboard.js](web/dashboard.js)
- [web/dashboard.css](web/dashboard.css)
- [web/dashboard_health.html](web/dashboard_health.html)
- [web/dashboard_health.js](web/dashboard_health.js)
- [web/dashboard_pipeline.html](web/dashboard_pipeline.html)
- [web/dashboard_pipeline.js](web/dashboard_pipeline.js)
- [web/dashboard_governance.html](web/dashboard_governance.html)
- [web/dashboard_governance.js](web/dashboard_governance.js)

### Memory UI

- [web/memory.html](web/memory.html)
- [web/memory.js](web/memory.js)
- [web/memory.css](web/memory.css)

> Dieser Bereich ist bestehende UI-Implementierung. Bei einem UI-Neuaufbau ist der aktuelle Backendzustand die Source of Truth, nicht das visuelle Verhalten historischer Oberflächen.

---

## 12. Tests und QA

[tests/](tests/)

### Component Tests

[tests/components/](tests/components/)

### Integration Tests

[tests/integration/](tests/integration/)

### Routing Tests

[tests/routing/](tests/routing/)

### Unit Tests

[tests/unit/](tests/unit/)

### Smoke Test

- [tests/test_smoke.py](tests/test_smoke.py)

### Test Suite v3

- [scripts/test_suite_v3/](scripts/test_suite_v3/)

---

## 13. Scripts und Betrieb

[scripts/](scripts/)

Wichtige Betriebs- und Wartungsskripte:

- [scripts/preflight_check.py](scripts/preflight_check.py)
- [scripts/audio_watchdog.py](scripts/audio_watchdog.py)
- [scripts/session_init.sh](scripts/session_init.sh)
- [scripts/unit_tests.sh](scripts/unit_tests.sh)
- [scripts/weekly_journal_audit.sh](scripts/weekly_journal_audit.sh)
- [scripts/ws_test.py](scripts/ws_test.py)
- [scripts/query_reminders.py](scripts/query_reminders.py)
- [scripts/pronunciation_audit.py](scripts/pronunciation_audit.py)

---

## 14. Dokumentation

[docs/](docs/)

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/CONSOLE_GUIDE.md](docs/CONSOLE_GUIDE.md)
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- [docs/DEVELOPMENT_INVENTORY.md](docs/DEVELOPMENT_INVENTORY.md)
- [docs/DEVELOPMENT_VISION.md](docs/DEVELOPMENT_VISION.md)
- [docs/EDGE_CASE_TESTING.md](docs/EDGE_CASE_TESTING.md)
- [docs/INTERACTION_ARTIFACT_CACHE_DESIGN.md](docs/INTERACTION_ARTIFACT_CACHE_DESIGN.md)
- [docs/INTERACTION_ARTIFACT_CACHE_RESEARCH.md](docs/INTERACTION_ARTIFACT_CACHE_RESEARCH.md)
- [docs/PRIORITY_ROADMAP.md](docs/PRIORITY_ROADMAP.md)
- [docs/SEMANTIC_INTENT_MATCHING.md](docs/SEMANTIC_INTENT_MATCHING.md)
- [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)
- [docs/SKILL_DEVELOPMENT.md](docs/SKILL_DEVELOPMENT.md)
- [docs/SKILL_EDITING_SYSTEM.md](docs/SKILL_EDITING_SYSTEM.md)
- [docs/STT_WORKER_PROCESS.md](docs/STT_WORKER_PROCESS.md)
- [docs/SYSTEM_SPECIFIC_NOTES.md](docs/SYSTEM_SPECIFIC_NOTES.md)
- [docs/TTS_VOICE_OPTIONS.md](docs/TTS_VOICE_OPTIONS.md)
- [docs/VOICE_TRAINING_GUIDE.md](docs/VOICE_TRAINING_GUIDE.md)

---

## 15. Assets, Images und Reports

### Assets

- [assets/](assets/)
- [assets/README.md](assets/README.md)

### Images

- [images/](images/)

### Reports

- [reports/](reports/)
- [reports/journal_audits/](reports/journal_audits/)

### Share

- [share/](share/)

---

## 16. Konfiguration und Dependencies

- [config.yaml](config.yaml)
- [.env.example](.env.example)
- [requirements.txt](requirements.txt)
- [.gitignore](.gitignore)
- [.gitattributes](.gitattributes)

Lokale Secrets und produktive Zugangsdaten gehören nicht in das Repository.

---

## 17. GitHub und Repository-Metadaten

[.github/](.github/)

- [.github/ISSUE_TEMPLATE/bug_report.md](.github/ISSUE_TEMPLATE/bug_report.md)
- [.github/ISSUE_TEMPLATE/feature_request.md](.github/ISSUE_TEMPLATE/feature_request.md)
- [.github/pull_request_template.md](.github/pull_request_template.md)

Remote:

```text
https://github.com/CyberG3niusIT/JARVIS-Sleepy.git
```

---

## 18. Nicht versionierte Laufzeitdaten

Folgende Daten gehören grundsätzlich nicht in den Repository-Index als versionierte Runtime-Artefakte:

- Modellgewichte
- lokale Datenbanken
- Memory-Indizes
- Audioaufnahmen
- Logs mit Nutzerdaten
- Credentials
- Tokens
- API-Keys
- lokale Backups
- virtuelle Umgebungen
- Caches

Die konkrete Ausschlusslogik wird durch [.gitignore](.gitignore) und die jeweilige Runtime-Konfiguration bestimmt.

---

<div align="center">

**J.A.R.V.I.S**

`LOCAL FIRST · BACKEND IS SOURCE OF TRUTH`

</div>
