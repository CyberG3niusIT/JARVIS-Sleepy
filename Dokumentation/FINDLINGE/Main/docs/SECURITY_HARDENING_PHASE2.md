# Security-Härtung Phase 2

Stand: 30.09.2026. Lokale Änderungen auf dem Integrationsstand
`68da00ce056ee9bad9a41918c0a35c97002ef722`; keine Service- oder Konfigurationsänderung.

## HIGH-1: Pending Skill Confirmations

`developer_tools.confirm_action` und `file_editor.confirm_action` verwenden
`core.confirmation_matching.parse_confirmation`. Der vorhandene Router verwendet
dieselbe Klassifikation für die Weiterleitung an Pending-Skill-Handler.
Die bestehenden Pending-Tupel, Ablaufzeiten und Ausführungswege bleiben erhalten.

- Explizite Ablehnung gewinnt auch in gemischten Aussagen.
- Wörter werden vollständig erkannt; `jahr`, `januar`, `javascript` und `jarvis`
  bestätigen keine Aktion durch ein enthaltenes `ja`.
- Eine Zustimmung muss ausschließlich aus bekannten Zustimmungsphrasen und
  optionalen Höflichkeitswörtern beziehungsweise der Anrede `jarvis` bestehen.
- Deutsch und Englisch sind unterstützt. Unklare Texte führen im Handler zu
  einer Rückfrage und behalten die Pending-Aktion. Ablehnung löscht sie.
- Die Entscheidung benötigt weder LLM noch externe Dienste.

Regression: `tests/unit/test_confirmation_matching.py` ruft die echten Handler
mit ersetzten Shell-, Delete- und Overwrite-Seiteneffekten auf und prüft außerdem
die Weiterleitung im Router, Ablaufzeiten und einmalige Ausführung.

## HIGH-2: Öffentliche statische Ressourcen

Die Auth-Ausnahme gilt nur für GET/HEAD auf die von `create_app` ausdrücklich
registrierten statischen Ressourcen für Web-Assets, Tool-Bilder und generierte
Bilder, mit den bisher öffentlichen Asset-Endungen. Eine Dateiendung allein
macht einen dynamischen Handler nicht öffentlich. Die Namespaces `/api` und
`/ws` bleiben auch im statischen Catch-all geschützt.

Die leere Mail-Dashboard-Shell und die vorhandenen Governance-Ausnahmen bleiben
unverändert. Der Desktop-Modus prüft weiterhin zuerst seine bestehende Allowlist;
statische Ressourcen, WebSockets und andere nicht freigegebene Pfade bleiben 403.

Regression: `tests/unit/test_web_auth_static_routes.py` verwendet echte registrierte
Routen mit harmlosen API-Test-Handlern sowie temporären Bildverzeichnissen.
Die Tests prüfen öffentliche Assets, API-Lese-/Schreibpfade mit Dateiendungen,
WebSocket-Auth, Catch-all-Abgrenzung und den Desktop-Auth-/Allowlist-Vertrag.

## Laufzeitgrenze und offene Befunde

Verifikation am 30.09.2026:

- Gezielte WSL-Regressionen: **518 passed**, 311 Warnungen, kein Fail/Skip.
  Befehl: `/home/alex/jarvis-venv/bin/python3 -m pytest` mit
  `-q -p no:cacheprovider --tb=short --disable-warnings` und
  `PYTHONDONTWRITEBYTECODE=1`. Dateien unter `tests/unit/`:
  `test_confirmation_matching.py`, `test_web_auth_static_routes.py`,
  `test_jarvis_web_app.py`, `test_jarvis_web_desktop_mode.py`,
  `test_runtime_status.py`, `test_desktop_api_lifecycle.py`,
  `test_developer_tools_safety.py`, `test_developer_tools_confirmation_slot.py`,
  `test_developer_tools_cwd.py`, `test_voice_routing_hardening.py`.
- C#-Verträge: `dotnet run --project tests/WinUiBackendAdapters.Tests/WinUiBackendAdapters.Tests.csproj --no-build --no-launch-profile`:
  bestanden, ein Skip für den synthetischen HTTP-Hub, weil die echte API 8092 belegt.
- Beide PowerShell-Testskripte unter `tests/powershell/` bestanden in isolierten
  Zustandsverzeichnissen mit injizierten Lifecycle-/Keepalive-Aufrufen.
- `git diff --check`: bestanden.
- Lesender Supervisor-Status vor und nach Änderungen: **READY**;
  letzter Snapshot `2026-09-30T08:32:49Z`.

Die laufenden Prozesse werden nicht neu gestartet. Bestandene Tests beweisen die
geänderten Quellen; sie beweisen nicht, dass bereits gestartete Python-Prozesse
diese Änderungen geladen haben. Die READY-Statusabfrage ersetzt keinen erneuten
Voice-/WinUI-E2E-Test.

HIGH-3 (Web-Search-Persistenz), HIGH-4 (Governance `password_verified`), HIGH-5
(gemeinsamer GPU-Lock) und die im Audit genannten MEDIUM-Befunde bleiben offen.
Andere Confirmation-Pfade, etwa Plan- und Memory-Bestätigung, sind nicht Teil
dieser beiden Skill-Handler-Fixes und benötigen eine separate Prüfung.
