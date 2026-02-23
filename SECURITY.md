# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| Latest  | Yes                |
| Older   | No                 |

Only the latest version on the `main` branch receives security updates.

## Reporting a Vulnerability

**Please do not open a public issue for security vulnerabilities.**

Instead, use [GitHub Security Advisories](https://github.com/InterGenJLU/jarvis/security/advisories/new) to report vulnerabilities privately. This ensures the issue can be assessed and addressed before public disclosure.

### What to Include

- Description of the vulnerability
- Steps to reproduce or proof of concept
- Affected components (e.g., specific module, skill, API endpoint)
- Potential impact assessment

### What to Expect

- **Acknowledgment** within 72 hours
- **Assessment** of severity and impact
- **Fix timeline** communicated based on severity
- **Credit** given to the reporter in the fix commit (unless you prefer anonymity)

### What Qualifies as a Security Issue

- Remote code execution vulnerabilities
- API key or credential exposure
- Privilege escalation
- Injection vulnerabilities (command injection, path traversal, etc.)
- Sensitive data leakage

### What Does NOT Qualify

- Bugs that require local system access (JARVIS runs as a local assistant)
- Feature requests or general bugs (use [Issues](https://github.com/InterGenJLU/jarvis/issues) instead)
- Denial of service on a single-user local system

## Security Considerations

JARVIS is designed as a **local, single-user voice assistant**. It is not intended to be exposed to the public internet. Key security design decisions:

- API keys are stored in `.env` (gitignored, never committed)
- LLM inference runs locally via llama.cpp (no cloud dependency for primary inference)
- Shell command execution in developer tools skill uses a safety tier system
- No authentication layer exists — JARVIS assumes trusted local access
