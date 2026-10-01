# Security Policy

## Sicherheits- und Privacy-Modell

JARVIS ist **Local First**.

Lokale Kernfunktionen sollen ohne unnötige Cloud-Abhängigkeit funktionieren. Dazu können, abhängig von der realen Konfiguration und Runtime, lokale LLM-Inferenz, Speech-to-Text, Text-to-Speech, Routing, Memory und weitere lokale Dienste gehören.

JARVIS ist jedoch nicht pauschal ein vollständig offline arbeitendes System. Bestimmte explizit konfigurierte Fähigkeiten können Daten an externe Dienste übertragen, zum Beispiel:

- Websuche und Web Research
- Remote-LLM-Provider oder Fallbacks
- MCP-Server und Remote Tools
- Google APIs wie Calendar, Gmail, Contacts, Tasks oder Drive
- E-Mail-Provider
- externe Integrations- oder Fallback-Provider wie Composio
- weitere vom Owner ausdrücklich konfigurierte Dienste

Ob Daten das lokale System verlassen, bestimmt der **reale Datenfluss der jeweiligen Capability**. Eine UI-Einstellung, Dokumentation oder Produktbezeichnung allein stellt keine technische Privacy-Grenze dar.

JARVIS darf nicht behaupten, dass Daten lokal bleiben oder geschützt sind, wenn dies nicht durch den tatsächlichen Datenfluss, die Konfiguration und die wirksamen Privacy-/Authorization-Gates belegt ist.

## Sicherheitsgrundsätze

- Privacy-Gates und Permission-Gates dürfen nicht umgangen werden.
- Confirmation ersetzt keine Authorization. Authorization ersetzt keine Privacy-Prüfung.
- Sensitive oder externe Schreiboperationen müssen im Zweifel fail closed behandelt werden.
- Secrets dürfen nicht in Git, Logs, Prompts oder Testfixtures geschrieben werden.
- Externe Provider oder Fallbacks erhalten niemals weitergehende Rechte als der aufrufende Kontext.
- Ein Provider-Fallback darf Governance nicht umgehen.
- Externe Writes dürfen nach unklarem Timeout nicht automatisch über einen zweiten Provider wiederholt werden, wenn dadurch doppelte Seiteneffekte möglich sind.
- Clients dürfen keine Sicherheits-, Privacy- oder Backend-Zustände erfinden.
- Memory Learning und Self Extension dürfen keine Rechte, Policies oder Tool-Gates selbstständig erweitern.

## Secrets und Credentials

Zu sensitiven Geheimnissen zählen insbesondere:

- `.env`-Inhalte
- OAuth Client Secrets
- OAuth Tokens
- App-Passwörter
- API Keys
- MCP Credential Stores und Schlüssel
- private Schlüssel
- Session Tokens
- Zugangsdaten externer Provider

Solche Daten dürfen weder committed noch in Logs oder Testfixtures übernommen werden. Redaction und minimale Datenexposition haben Vorrang.

## Meldung von Schwachstellen

Sicherheits- oder Privacy-Schwachstellen bitte verantwortungsvoll und **nicht über ein öffentliches GitHub-Issue** melden.

Für dieses Repository ist GitHubs Private Vulnerability Reporting zu verwenden:

https://github.com/CyberG3niusIT/JARVIS-Sleepy/security/advisories/new

Falls der aktuelle Git-Remote hiervon abweicht, vor einer Meldung den tatsächlichen Repository-Remote prüfen.

## Scope

Diese Policy umfasst insbesondere:

- JARVIS Core, Routing und Conversation Pipeline
- Memory, Persistenz und Retrieval
- Privacy Gate, Authorization, Confirmation und Governance
- Capability-, Provider-, Tool-, Skill- und Agenten-Systeme
- MCP und andere externe Integrationen
- Google-, E-Mail- und sonstige OAuth-/API-Integrationen
- LLM-Provider und Provider-Fallbacks
- Speech Processing, STT, TTS und Voice Pipeline
- Desktop-/Windows-Steuerung und Automation
- Runtime Supervisor und Lifecycle
- Web-, Desktop- und Mobile-Frontends
- Face Enrollment, Kamera und Computer Vision
- Secrets Handling und Credential Stores
- Logging, Telemetrie und Debug-Pfade

## Third-Party- und Upstream-Komponenten

Schwachstellen, die ausschließlich in einer Upstream-Abhängigkeit entstehen, sollten zusätzlich beim jeweiligen Upstream-Projekt gemeldet werden.

Sicherheitsprobleme, die durch die JARVIS-Integration, Konfiguration, Privilegierung, Datenflüsse oder unsichere Verwendung einer solchen Abhängigkeit entstehen, bleiben Teil des JARVIS-Sicherheitsumfangs.

Third-Party-Komponenten behalten ihre jeweiligen Lizenz- und Security-Regeln.

## Offenlegung und Verifikation

Keine Aussage wie `sicher`, `privat`, `geschützt`, `isoliert` oder `offline` darf als technische Garantie verwendet werden, wenn der entsprechende Datenfluss oder Runtime-Zustand nicht verifiziert wurde.

Bei sicherheitsrelevanten Änderungen sind statische Prüfung, Unit-/Regressionstests sowie, falls relevant, Integration, Runtime, Hardware und End-to-End getrennt zu betrachten und zu dokumentieren.
