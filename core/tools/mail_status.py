"""Metadata-only mail status tool. Message text never enters the general tool registry."""

from core.mail_integration import CONFIG_PATH, MailDenied, MailUnavailable, get_mail_service

TOOL_NAME = "mail_status"
ALWAYS_INCLUDED = True
SCHEMA = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "Zähle ungelesene E-Mails in allen aktiven Postfächern oder einem bestimmten Konto.",
        "parameters": {"type": "object", "properties": {
            "account": {"type": "string", "description": "Optionale vollständige Postfachadresse"}
        }}
    }
}
SYSTEM_PROMPT_RULE = (
    "Bei Fragen nach neuen oder ungelesenen E-Mails mail_status aufrufen. "
    "Die Zahl ist der aktuelle UNSEEN-Status im Posteingang; "
    "eingegangene Nachrichten seit der letzten Prüfung werden separat gemeldet. "
    "Niemals aus dem Status auf Inhalt oder Absender schließen."
)


def is_available() -> bool:
    return CONFIG_PATH.is_file()


def handler(args: dict) -> str:
    try:
        service = get_mail_service()
        account = str(args.get("account", "")).strip().lower()
        status = service.all_status()
        if account:
            details = next((item for item in status["accounts"] if item["account"] == account), None)
            if details is None:
                return "Dieses Postfach ist nicht aktiv oder derzeit nicht erreichbar."
            return (f"{account}: {details['new_24h']} seit 24 Stunden neu erfasst; "
                    f"{details['unread_inbox']} derzeit ungelesen im Posteingang.")
        lines = [f"{item['account']}: {item['new_24h']} neu seit 24 Stunden, "
                 f"{item['unread_inbox']} ungelesen"
                 for item in status["accounts"]]
        if status["unavailable"]:
            lines.append(f"{len(status['unavailable'])} Postfächer derzeit nicht erreichbar.")
        return "\n".join(lines) if lines else "Keine Postfächer erreichbar."
    except (MailDenied, MailUnavailable, OSError):
        return "E-Mail-Status derzeit nicht verfügbar."
