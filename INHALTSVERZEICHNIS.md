<div align="center">

# J.A.R.V.I.S

### REPOSITORY INDEX

`SLEEPY · SNAPSHOT 27.09.2026`

</div>

---

## Zweck

Dieses Inhaltsverzeichnis ist der zentrale technische Einstiegspunkt für den Snapshot-Branch `Sleepy-Aktuell-|-27.09`.

Es bildet die im Branch tatsächlich vorhandenen Repository-Bereiche funktional ab. Für Architektur- und Statusaussagen gilt weiterhin:

`Runtime → Repository → Tests → aktuelle Dokumentation`

---

## Schnellnavigation

- [00 // Einstieg](#00--einstieg)
- [01 // Runtime & Entry Points](#01--runtime--entry-points)
- [02 // Core](#02--core)
- [03 // Voice & Audio](#03--voice--audio)
- [04 // Models & Inference](#04--models--inference)
- [05 // Memory & Context](#05--memory--context)
- [06 // Tools, Skills & MCP](#06--tools-skills--mcp)
- [07 // Vision, Presence & Desktop Integration](#07--vision-presence--desktop-integration)
- [08 // Governance, Privacy & Security](#08--governance-privacy--security)
- [09 // Services & Runtime Control](#09--services--runtime-control)
- [10 // Desktop Control Hub](#10--desktop-control-hub)
- [11 // Mobile App](#11--mobile-app)
- [12 // Existing Web UI](#12--existing-web-ui)
- [13 // Tests & QA](#13--tests--qa)
- [14 // Documentation](#14--documentation)
- [15 // Scripts & Operations](#15--scripts--operations)
- [16 // Assets, Images & Reports](#16--assets-images--reports)
- [17 // Configuration & Dependencies](#17--configuration--dependencies)
- [18 // GitHub & Repository Metadata](#18--github--repository-metadata)

---

## 00 // Einstieg

| Pfad | Funktion |
|---|---|
| [README.md](README.md) | Snapshot-Identität und Systemüberblick |
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | Projektüberblick |
| [CHANGELOG.md](CHANGELOG.md) | Entwicklungshistorie |
| [SECURITY.md](SECURITY.md) | Security-Hinweise |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Entwicklungs- und Beitragsregeln |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Verhaltensregeln |
| [LICENSE](LICENSE) | Lizenz |
| [CLAUDE.md](CLAUDE.md) | Repository-spezifische Agenten-/Arbeitsanweisungen |
| [INHALTSVERZEICHNIS.md](INHALTSVERZEICHNIS.md) | Dieser zentrale Repository-Index |

---

## 01 // Runtime & Entry Points

### Windows Runtime Control

- [JARVIS-Runtime.ps1](JARVIS-Runtime.ps1)
- [JARVIS.Runtime.psm1](JARVIS.Runtime.psm1)
- [JARVIS-Start.ps1](JARVIS-Start.ps1)
- [JARVIS-Stop.ps1](JARVIS-Stop.ps1)
- [JARVIS-Restart.ps1](JARVIS-Restart.ps1)
- [JARVIS-Start.cmd](JARVIS-Start.cmd)
- [JARVIS-Stop.cmd](JARVIS-Stop.cmd)
- [JARVIS-Restart.cmd](JARVIS-Restart.cmd)

### Python / WSL Entry Points

- [jarvis_console.py](jarvis_console.py)
- [jarvis_continuous.py](jarvis_continuous.py)
- [jarvis_web.py](jarvis_web.py)
- [mcp_server.py](mcp_server.py)
- [start.sh](start.sh)
- [stop.sh](stop.sh)
- [restart.sh](restart.sh)
- [status.sh](status.sh)
- [startup_checks.sh](startup_checks.sh)
- [start_jarvis_gpu.sh](start_jarvis_gpu.sh)
- [start_chatterbox.sh](start_chatterbox.sh)
- [killswitch.sh](killswitch.sh)
- [jarvis_aliases.sh](jarvis_aliases.sh)

---

## 02 // Core

Zentrale Implementierung:

[core/](core/)

Wichtige Bereiche:

- Conversation und Routing
- LLM-Routing und Handover
- Memory und Context
- Tool-Registry und Tool-Gates
- Voice Pipeline
- Privacy und Governance
- Awareness und Presence
- Metrics, Logging und Health
- Desktop- und Webcam-Integration

Direkte Kernpfade:

- [core/conversation.py](core/conversation.py)
- [core/conversation_router.py](core/conversation_router.py)
- [core/pipeline.py](core/pipeline.py)
- [core/llm_router.py](core/llm_router.py)
- [core/model_handover.py](core/model_handover.py)
- [core/expert_policy.py](core/expert_policy.py)
- [core/memory_manager.py](core/memory_manager.py)
- [core/context_window.py](core/context_window.py)
- [core/tool_registry.py](core/tool_registry.py)
- [core/tool_executor.py](core/tool_executor.py)
- [core/privacy_gate.py](core/privacy_gate.py)
- [core/watchdog.py](core/watchdog.py)

---

## 03 // Voice & Audio

- [core/continuous_listener.py](core/continuous_listener.py)
- [core/stt.py](core/stt.py)
- [core/stt_qwen3.py](core/stt_qwen3.py)
- [core/vad.py](core/vad.py)
- [core/wake_word.py](core/wake_word.py)
- [core/tts.py](core/tts.py)
- [core/tts_cache.py](core/tts_cache.py)
- [core/tts_normalizer.py](core/tts_normalizer.py)
- [core/tts_normalizer_de.py](core/tts_normalizer_de.py)
- [core/speaker_id.py](core/speaker_id.py)
- [tools/chatterbox_server.py](tools/chatterbox_server.py)
- [voice_training/](voice_training/)

Aktuelle technische Dokumentation:

- [Dokumentation/06_VOICE_STT_TTS.md](Dokumentation/06_VOICE_STT_TTS.md)
- [Dokumentation/13_KNOWN_ISSUES.md](Dokumentation/13_KNOWN_ISSUES.md)

---

## 04 // Models & Inference

- [config.yaml](config.yaml)
- [core/llm_router.py](core/llm_router.py)
- [core/llm_server_client.py](core/llm_server_client.py)
- [core/model_handover.py](core/model_handover.py)
- [core/expert_policy.py](core/expert_policy.py)
- [core/gpu_swap.py](core/gpu_swap.py)
- [llama-server.service](llama-server.service)
- [flux-server.service](flux-server.service)
- [services/flux_server.py](services/flux_server.py)

Dokumentation:

- [Dokumentation/03_RUNTIME_AND_MODELS.md](Dokumentation/03_RUNTIME_AND_MODELS.md)
- [Dokumentation/10_CONFIGURATION.md](Dokumentation/10_CONFIGURATION.md)

---

## 05 // Memory & Context

- [core/memory_manager.py](core/memory_manager.py)
- [core/context_window.py](core/context_window.py)
- [core/interaction_cache.py](core/interaction_cache.py)
- [core/document_buffer.py](core/document_buffer.py)
- [core/people_manager.py](core/people_manager.py)
- [core/user_profile.py](core/user_profile.py)
- [core/tools/recall_memory.py](core/tools/recall_memory.py)
- [scripts/backfill_memory.py](scripts/backfill_memory.py)
- [scripts/memory_snapshot.py](scripts/memory_snapshot.py)

Dokumentation:

- [Dokumentation/05_MEMORY.md](Dokumentation/05_MEMORY.md)

---

## 06 // Tools, Skills & MCP

### Tool Runtime

- [core/tools/](core/tools/)
- [core/tool_registry.py](core/tool_registry.py)
- [core/tool_executor.py](core/tool_executor.py)
- [core/tool_gate.py](core/tool_gate.py)
- [core/mcp_client.py](core/mcp_client.py)
- [mcp_server.py](mcp_server.py)
- [.mcp.json](.mcp.json)

### Skills

- [skills/](skills/)
- [skills/personal/](skills/personal/)
- [skills/system/](skills/system/)

Dokumentation:

- [Dokumentation/07_TOOLS_MCP_SKILLS.md](Dokumentation/07_TOOLS_MCP_SKILLS.md)

---

## 07 // Vision, Presence & Desktop Integration

- [core/webcam_manager.py](core/webcam_manager.py)
- [core/webcam_server.py](core/webcam_server.py)
- [core/presence_detector.py](core/presence_detector.py)
- [core/desktop_manager.py](core/desktop_manager.py)
- [core/tools/capture_webcam.py](core/tools/capture_webcam.py)
- [core/tools/enroll_face.py](core/tools/enroll_face.py)
- [extensions/](extensions/)

Dokumentation:

- [Dokumentation/02_COMPONENTS.md](Dokumentation/02_COMPONENTS.md)
- [Dokumentation/COMPONENTS/OBSERVATION_AND_PRIVACY.md](Dokumentation/COMPONENTS/OBSERVATION_AND_PRIVACY.md)

---

## 08 // Governance, Privacy & Security

- [governance/](governance/)
- [core/governance.py](core/governance.py)
- [core/privacy_gate.py](core/privacy_gate.py)
- [core/privacy_control_watcher.py](core/privacy_control_watcher.py)
- [SECURITY.md](SECURITY.md)

Dokumentation:

- [Dokumentation/09_SECURITY_PRIVACY.md](Dokumentation/09_SECURITY_PRIVACY.md)
- [Dokumentation/04_AGENTS_AND_ORCHESTRATION.md](Dokumentation/04_AGENTS_AND_ORCHESTRATION.md)

---

## 09 // Services & Runtime Control

### Services

- [services/](services/)
- [systemd/](systemd/)
- [jarvis.service](jarvis.service)
- [llama-server.service](llama-server.service)
- [flux-server.service](flux-server.service)
- [jarvis-backup.service](jarvis-backup.service)
- [jarvis-backup.timer](jarvis-backup.timer)

### Operational Documentation

- [Dokumentation/11_INSTALLATION_OPERATION.md](Dokumentation/11_INSTALLATION_OPERATION.md)
- [Dokumentation/00_PROJECT_STATUS.md](Dokumentation/00_PROJECT_STATUS.md)

---

## 10 // Desktop Control Hub

Bestehender Desktop-Implementierungsstand:

[UI/](UI/)

Wichtige Bereiche:

- [UI/README.md](UI/README.md)
- [UI/WindowsApp/](UI/WindowsApp/)
- [UI/src-tauri/](UI/src-tauri/)
- [UI/src/](UI/src/)

Für den kommenden Lovable-Umbau gilt die bestehende UI ausdrücklich nicht als visuelle Source of Truth.

Redesign-Baseline:

- [Dokumentation/16_UI_CONTROL_HUB.md](Dokumentation/16_UI_CONTROL_HUB.md)
- [Dokumentation/18_DESKTOP_REDESIGN_LOVABLE.md](Dokumentation/18_DESKTOP_REDESIGN_LOVABLE.md)

---

## 11 // Mobile App

[Mobile-App/](Mobile-App/)

Wichtige Bereiche:

- [Mobile-App/README.md](Mobile-App/README.md)
- [Mobile-App/android/](Mobile-App/android/)
- [Mobile-App/src/](Mobile-App/src/)

Mobile ist Bestandteil des Snapshots, aber keine Designvorlage für den Desktop-Neuaufbau.

---

## 12 // Existing Web UI

[web/](web/)

Wichtige Dateien:

- [web/index.html](web/index.html)
- [web/app.js](web/app.js)
- [web/style.css](web/style.css)
- [web/dashboard.html](web/dashboard.html)
- [web/memory.html](web/memory.html)

Auch dieser Bestand ist Implementierungsreferenz, nicht visuelle Source of Truth für Lovable.

---

## 13 // Tests & QA

- [tests/](tests/)
- [tests/unit/](tests/unit/)
- [tests/integration/](tests/integration/)
- [tests/components/](tests/components/)
- [tests/routing/](tests/routing/)
- [scripts/test_suite_v3/](scripts/test_suite_v3/)

Dokumentation:

- [Dokumentation/12_TESTING_QA.md](Dokumentation/12_TESTING_QA.md)
- [Dokumentation/13_KNOWN_ISSUES.md](Dokumentation/13_KNOWN_ISSUES.md)

---

## 14 // Documentation

Zentrale aktuelle Dokumentation:

[Dokumentation/](Dokumentation/)

- [Dokumentation/README.md](Dokumentation/README.md)
- [Dokumentation/00_PROJECT_STATUS.md](Dokumentation/00_PROJECT_STATUS.md)
- [Dokumentation/01_ARCHITECTURE.md](Dokumentation/01_ARCHITECTURE.md)
- [Dokumentation/02_COMPONENTS.md](Dokumentation/02_COMPONENTS.md)
- [Dokumentation/03_RUNTIME_AND_MODELS.md](Dokumentation/03_RUNTIME_AND_MODELS.md)
- [Dokumentation/04_AGENTS_AND_ORCHESTRATION.md](Dokumentation/04_AGENTS_AND_ORCHESTRATION.md)
- [Dokumentation/05_MEMORY.md](Dokumentation/05_MEMORY.md)
- [Dokumentation/06_VOICE_STT_TTS.md](Dokumentation/06_VOICE_STT_TTS.md)
- [Dokumentation/07_TOOLS_MCP_SKILLS.md](Dokumentation/07_TOOLS_MCP_SKILLS.md)
- [Dokumentation/08_SCHOOL_MOBILITY.md](Dokumentation/08_SCHOOL_MOBILITY.md)
- [Dokumentation/09_SECURITY_PRIVACY.md](Dokumentation/09_SECURITY_PRIVACY.md)
- [Dokumentation/10_CONFIGURATION.md](Dokumentation/10_CONFIGURATION.md)
- [Dokumentation/11_INSTALLATION_OPERATION.md](Dokumentation/11_INSTALLATION_OPERATION.md)
- [Dokumentation/12_TESTING_QA.md](Dokumentation/12_TESTING_QA.md)
- [Dokumentation/13_KNOWN_ISSUES.md](Dokumentation/13_KNOWN_ISSUES.md)
- [Dokumentation/14_ROADMAP.md](Dokumentation/14_ROADMAP.md)
- [Dokumentation/15_CHANGELOG_DEVELOPMENT.md](Dokumentation/15_CHANGELOG_DEVELOPMENT.md)
- [Dokumentation/16_UI_CONTROL_HUB.md](Dokumentation/16_UI_CONTROL_HUB.md)
- [Dokumentation/17_TOOLING_UND_GITHUB.md](Dokumentation/17_TOOLING_UND_GITHUB.md)
- [Dokumentation/18_DESKTOP_REDESIGN_LOVABLE.md](Dokumentation/18_DESKTOP_REDESIGN_LOVABLE.md)
- [Dokumentation/INVENTORY.md](Dokumentation/INVENTORY.md)
- [Dokumentation/COMPONENTS/](Dokumentation/COMPONENTS/)
- [Dokumentation/ADR/](Dokumentation/ADR/)
- [Dokumentation/LEGACY/](Dokumentation/LEGACY/)

Historische Dokumentation im Repository-Root:

[docs/](docs/)

Die zentrale Dokumentation unter `Dokumentation/` hat für den Snapshot Vorrang vor älteren, widersprechenden Texten.

---

## 15 // Scripts & Operations

- [scripts/](scripts/)
- [tools/](tools/)
- [scripts/preflight_check.py](scripts/preflight_check.py)
- [scripts/audio_watchdog.py](scripts/audio_watchdog.py)
- [scripts/session_init.sh](scripts/session_init.sh)
- [scripts/unit_tests.sh](scripts/unit_tests.sh)
- [scripts/weekly_journal_audit.sh](scripts/weekly_journal_audit.sh)

---

## 16 // Assets, Images & Reports

- [assets/](assets/)
- [images/](images/)
- [reports/](reports/)
- [share/](share/)
- [voice_training/](voice_training/)

Diese Bereiche können historische oder rein unterstützende Artefakte enthalten. Ihr Vorhandensein ist kein Runtime-Nachweis.

---

## 17 // Configuration & Dependencies

- [config.yaml](config.yaml)
- [.env.example](.env.example)
- [.gitignore](.gitignore)
- [.gitattributes](.gitattributes)
- [pyproject.toml](pyproject.toml)
- [requirements.txt](requirements.txt)
- [requirements-ci.txt](requirements-ci.txt)
- [requirements-anthropic.txt](requirements-anthropic.txt)

Produktive Secrets, Tokens, lokale Datenbanken, Logs und Modellgewichte gehören nicht in Git.

---

## 18 // GitHub & Repository Metadata

- [.github/](.github/)
- [.github/CODEOWNERS](.github/CODEOWNERS)
- [.github/workflows/](.github/workflows/)
- [.github/ISSUE_TEMPLATE/](.github/ISSUE_TEMPLATE/)

Repository:

`CyberG3niusIT/JARVIS-Sleepy`

Snapshot-Branch:

`Sleepy-Aktuell-|-27.09`

---

<div align="center">

### J.A.R.V.I.S

`LOCAL FIRST · BACKEND IS SOURCE OF TRUTH`

**SLEEPY**

</div>
